import os
import chromadb
import asyncio
from typing import List, Dict, Any
from pathlib import Path
from chromadb.config import Settings
from src.utils.logger import setup_logger
from dotenv import load_dotenv

logger = setup_logger(__name__)
load_dotenv()

class ChromaKnowledgeManager:
    """Manages interaction with a local, persistent ChromaDB collection for RAG."""

    def __init__(self, 
                 db_path: str = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY", "."), "data/chroma/hla_knowledge"),
                 collection_name: str = "hla_knowledge_base",
                 knowledge_path: str = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY", "."), "data/knowledge/Articles")):
        
        self._db_path = db_path
        self._collection_name = collection_name
        self._knowledge_path = Path(knowledge_path)
        self._client = None
        self._collection = None
        self._initialized = False
        
        # Ensure paths exist
        Path(self._db_path).mkdir(parents=True, exist_ok=True)
        self._knowledge_path.mkdir(parents=True, exist_ok=True)

    async def initialize(self) -> bool:
        """Initialize ChromaDB and index documents from knowledge folder."""
        if self._initialized:
            return True
        try:
            logger.info(f"Initializing ChromaDB persistent client at path: {self._db_path}")
            
            self._client = chromadb.PersistentClient(
                path=self._db_path,
                settings=Settings(
                    allow_reset=True,
                    anonymized_telemetry=False
                )
            )
            
            self._collection = await asyncio.to_thread(
                self._client.get_or_create_collection, 
                name=self._collection_name
            )
            
            # Index documents from knowledge folder
            await self._index_documents()
            
            logger.info(f"Successfully loaded ChromaDB collection: '{self._collection_name}' with {self._collection.count()} documents.")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB collection '{self._collection_name}': {e}")
            self._initialized = False
            return False

    def is_initialized(self) -> bool:
        """Returns True if the knowledge manager is initialized, False otherwise."""
        return self._initialized

    async def search_async(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Performs an asynchronous search in the ChromaDB collection."""
        if not self.is_initialized():
            raise RuntimeError("ChromaKnowledgeManager is not initialized. Call initialize() first.")
        
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,  # Use the default executor
                self._perform_search,
                query,
                limit
            )
            return results
        except Exception as e:
            logger.error(f"An error occurred during asynchronous search: {e}")
            return []

    def _perform_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """The synchronous part of the search logic."""
        if self._collection.count() == 0:
            logger.warning(f"Cannot search in empty collection: '{self._collection_name}'")
            return []
            
        results = self._collection.query(
            query_texts=[query],
            n_results=min(limit, self._collection.count()), # Ensure n_results <= collection size
            include=["metadatas", "documents", "distances"]
        )
        
        formatted_results = []
        ids = results.get('ids', [[]])[0]
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]

        for i, doc_id in enumerate(ids):
            distance = distances[i] if distances[i] is not None else 1.0
            formatted_results.append({
                "id": doc_id,
                "content": documents[i],
                "metadata": metadatas[i],
                "source": metadatas[i].get('source', 'Unknown'),
                "relevance_score": 1 - distance
            })
        
        return formatted_results

    async def _index_documents(self):
        """Index documents from the knowledge folder into ChromaDB."""
        if not self._knowledge_path.exists():
            logger.warning(f"Knowledge path does not exist: {self._knowledge_path}")
            return
            
        supported_extensions = {'.pdf', '.txt', '.md', '.docx'}
        documents = []
        metadatas = []
        ids = []
        
        for file_path in self._knowledge_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    # Check if document is already indexed
                    doc_id = str(file_path.relative_to(self._knowledge_path))
                    
                    # Extract text content
                    content = await self._extract_text_content(file_path)
                    if not content.strip():
                        continue
                    
                    # Split into chunks
                    chunks = self._split_into_chunks(content)
                    
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{doc_id}_chunk_{i}"
                        documents.append(chunk)
                        metadatas.append({
                            "source": str(file_path),
                            "title": file_path.stem,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "file_type": file_path.suffix
                        })
                        ids.append(chunk_id)
                        
                    logger.info(f"Processed document: {file_path.name} ({len(chunks)} chunks)")
                    
                except Exception as e:
                    logger.error(f"Error processing document {file_path}: {e}")
                    continue
        
        # Add documents to ChromaDB
        if documents:
            try:
                await asyncio.to_thread(
                    self._collection.add,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Indexed {len(documents)} document chunks into ChromaDB")
            except Exception as e:
                logger.error(f"Error adding documents to ChromaDB: {e}")
        else:
            logger.warning("No documents found to index")

    async def _extract_text_content(self, file_path: Path) -> str:
        """Extract text content from various file types."""
        try:
            if file_path.suffix.lower() == '.pdf':
                return await self._extract_from_pdf(file_path)
            elif file_path.suffix.lower() == '.docx':
                return await self._extract_from_docx(file_path)
            elif file_path.suffix.lower() in ['.txt', '.md']:
                return await self._extract_from_text(file_path)
            else:
                return ""
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {e}")
            return ""

    async def _extract_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            from PyPDF2 import PdfReader
            with open(file_path, 'rb') as f:
                reader = PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
        except ImportError:
            logger.warning("PyPDF2 not available, skipping PDF extraction")
            return ""
        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
            return ""

    async def _extract_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            from docx import Document
            doc = Document(file_path)
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except ImportError:
            logger.warning("python-docx not available, skipping DOCX extraction")
            return ""
        except Exception as e:
            logger.error(f"Error extracting DOCX {file_path}: {e}")
            return ""

    async def _extract_from_text(self, file_path: Path) -> str:
        """Extract text from text files."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            return ""

    def _split_into_chunks(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        if not text.strip():
            return []
            
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk.strip())
                
        return chunks if chunks else [text]