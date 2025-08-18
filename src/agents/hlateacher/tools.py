import json
import os
from tavily import TavilyClient
from .chroma_knowledge_manager import ChromaKnowledgeManager

from pathlib import Path
from typing import List, Any

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class WebSearchTools:
    """Tools for performing web searches using the Tavily API."""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            self.tavily_available = False
            logger.warning("Tavily API key not found. Web search will be disabled.")
        else:
            self.client = TavilyClient(api_key=self.api_key)
            self.tavily_available = True

    async def search_web(self, query: str, max_results: int = 1) -> str:
        """Performs a web search and returns results as a JSON string."""
        if not self.tavily_available:
            logger.warning("Web search requested but Tavily client is not available.")
            return json.dumps({"error": "Tavily API key not configured."})
        try:
            logger.info(f"Performing web search for: {query}")
            # Use search method for async call as provided by Tavily client
            response = self.client.search(query=query, max_results=max_results, include_answer=False)
            results = response.get('results', [])
            logger.info(f"Web search found {len(results)} results.")
            return json.dumps(results)
        except Exception as e:
            logger.error(f"Error during web search: {e}")
            return json.dumps({"error": f"Failed to perform web search: {e}"})

class KnowledgeSearchTools:
    """Tools for searching the ChromaDB knowledge base."""
    def __init__(self, knowledge_manager: ChromaKnowledgeManager):
        self.knowledge_manager = knowledge_manager

    async def search_knowledge_base(self, query: str, limit: int = 1) -> str:
        """Search knowledge base and return formatted results."""
        if not self.knowledge_manager.is_initialized():
            logger.warning("Knowledge base search requested but ChromaDB is not initialized.")
            return json.dumps({"error": "Knowledge base not initialized."})
        try:
            logger.info(f"Performing knowledge base search for: {query}")
            results = await self.knowledge_manager.search_async(query, limit=limit)
            logger.info(f"Knowledge base search found {len(results)} results.")
            
            # Format results for better integration with prompts
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("metadata", {}).get("title", "Unknown"),
                    "content": result.get("content", ""),
                    "source": result.get("source", "Unknown"),
                    "relevance_score": result.get("relevance_score", 0.0),
                    "chunk_index": result.get("metadata", {}).get("chunk_index", 0),
                    "file_type": result.get("metadata", {}).get("file_type", "unknown")
                })
            
            return json.dumps({
                "status": "success",
                "results": formatted_results,
                "total_found": len(formatted_results)
            })
            
        except Exception as e:
            logger.error(f"Error during knowledge base search: {e}")
            return json.dumps({"error": f"Failed to search knowledge base: {e}"})
    


# Utility functions for document processing
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file."""
    try:
        from PyPDF2 import PdfReader
        
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except ImportError:
        print("PyPDF2 not available")
        return ""
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return ""


def extract_text_from_docx(docx_path: str) -> str:
    """Extract text from DOCX file."""
    try:
        from docx import Document
        
        doc = Document(docx_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except ImportError:
        print("python-docx not available")
        return ""
    except Exception as e:
        print(f"Error extracting DOCX: {e}")
        return ""


def documents_parser(documents_file_path: str) -> str:
    """Parse various document types."""
    if documents_file_path.endswith(".pdf"):
        return extract_text_from_pdf(documents_file_path)
    elif documents_file_path.endswith(".docx"):
        return extract_text_from_docx(documents_file_path)
    elif documents_file_path.endswith((".txt", ".md")):
        try:
            with open(documents_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading text file: {e}")
            return ""
    else:
        raise ValueError(f"Unsupported file type: {documents_file_path}")