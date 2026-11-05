from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from pathlib import Path

import faiss
import httpx
import numpy as np
from docx import Document
from filelock import FileLock
from pypdf import PdfReader
from sklearn.feature_extraction.text import HashingVectorizer

from hlagent.data import sha256
from hlagent.models import Evidence


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+\*\d+(?::\d+)*[A-Za-z]?|[\w]+", text.lower())


def extract_document(path: Path):
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF requires a readable copy")
        pages = [(f"page {i + 1}", page.extract_text() or "") for i, page in enumerate(reader.pages)]
        if not any(t.strip() for _, t in pages):
            raise ValueError("OCR required: no extractable PDF text")
        yield from pages
    elif path.suffix.lower() == ".docx":
        document = Document(path)
        heading = "Document"
        for i, paragraph in enumerate(document.paragraphs):
            if paragraph.style and paragraph.style.name.startswith("Heading"):
                heading = paragraph.text
            if paragraph.text.strip():
                yield f"{heading}, paragraph {i + 1}", paragraph.text
        for i, table in enumerate(document.tables):
            yield f"table {i + 1}", "\n".join(" | ".join(c.text for c in row.cells) for row in table.rows)
    else:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for start in range(0, len(lines), 30):
            yield f"lines {start + 1}-{min(start + 30, len(lines))}", "\n".join(lines[start:start + 30])


class KnowledgeIndex:
    def __init__(self, directory: Path, inbox: Path, embedding_model: str | None = None):
        self.directory, self.inbox, self.embedding_model = directory, inbox, embedding_model
        directory.mkdir(parents=True, exist_ok=True)
        inbox.mkdir(parents=True, exist_ok=True)
        self.db = directory / "knowledge.sqlite3"
        self.lock = FileLock(directory / "index.lock")
        self._model = None
        with sqlite3.connect(self.db) as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS documents(path TEXT PRIMARY KEY, sha TEXT, status TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, path TEXT, locator TEXT, text TEXT, sha TEXT);
                CREATE TABLE IF NOT EXISTS embeddings(key TEXT PRIMARY KEY, model TEXT, vector BLOB);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(id UNINDEXED, tokens);
            """)

    def sync(self) -> list[dict]:
        paths = sorted(p for p in self.inbox.rglob("*") if p.is_file() and not p.is_symlink() and
                       p.suffix.lower() in (".pdf", ".docx", ".txt", ".md"))
        with self.lock, sqlite3.connect(self.db) as con:
            previous = {r[0]: r[1] for r in con.execute("SELECT path,sha FROM documents")}
            changed = False
            for removed in set(previous) - {str(p) for p in paths}:
                con.execute("DELETE FROM chunks_fts WHERE id IN (SELECT id FROM chunks WHERE path=?)", (removed,))
                con.execute("DELETE FROM chunks WHERE path=?", (removed,))
                con.execute("DELETE FROM documents WHERE path=?", (removed,))
                changed = True
            for path in paths:
                checksum = sha256(path)
                if previous.get(str(path)) == checksum:
                    continue
                changed = True
                con.execute("DELETE FROM chunks_fts WHERE id IN (SELECT id FROM chunks WHERE path=?)", (str(path),))
                con.execute("DELETE FROM chunks WHERE path=?", (str(path),))
                try:
                    chunks = []
                    for location, text in extract_document(path):
                        for start in range(0, len(text), 1400):
                            excerpt = text[start:start + 1650].strip()
                            if not excerpt:
                                continue
                            locator = f"{location}, segment {start // 1400 + 1}"
                            key = hashlib.sha256((str(path) + checksum + locator).encode()).hexdigest()[:24]
                            chunks.append((key, str(path), locator, excerpt, checksum))
                    if not chunks:
                        raise ValueError("Document contains no indexable text")
                    con.executemany("INSERT INTO chunks VALUES (?,?,?,?,?)", chunks)
                    con.executemany("INSERT INTO chunks_fts VALUES (?,?)", [(c[0], " ".join(tokenize(c[3]))) for c in chunks])
                    status, error = "indexed", None
                except Exception as exc:
                    status, error = "needs_attention", str(exc)
                con.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?)", (str(path), checksum, status, error))
            con.commit()
            info_path = self.directory / "vectors.json"
            same_model = info_path.exists() and json.loads(info_path.read_text())["model"] == (self.embedding_model or "lexical-hashing-2048")
            if changed or not same_model or not (self.directory / "vectors.faiss").exists():
                self._rebuild(con)
        return self.status()

    def _embed(self, texts: list[str], query: bool = False) -> np.ndarray:
        if self.embedding_model:
            if self._model is None:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=self.embedding_model, threads=2,
                                             cache_dir=str(self.directory / "models"))
            method = self._model.query_embed if query else self._model.passage_embed
            vectors = np.asarray(list(method(texts)), dtype="float32")
            faiss.normalize_L2(vectors)
            return vectors
        # Transparent lexical fallback; never described as semantic embeddings.
        vectorizer = HashingVectorizer(n_features=2048, alternate_sign=False, analyzer=tokenize, norm="l2")
        return vectorizer.transform(texts).toarray().astype("float32")

    def _rebuild(self, con):
        rows = con.execute("SELECT id,text FROM chunks ORDER BY id").fetchall()
        info = {"ids": [r[0] for r in rows], "model": self.embedding_model or "lexical-hashing-2048"}
        if rows:
            vectors = []
            for _, content in rows:
                key = hashlib.sha256((info["model"] + content).encode()).hexdigest()
                stored = con.execute("SELECT vector FROM embeddings WHERE key=?", (key,)).fetchone()
                vector = np.frombuffer(stored[0], dtype="float32") if stored else self._embed([content])[0]
                if not stored:
                    con.execute("INSERT INTO embeddings VALUES (?,?,?)", (key, info["model"], vector.tobytes()))
                vectors.append(vector)
            vectors = np.asarray(vectors, dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            temp = self.directory / "vectors.partial"
            faiss.write_index(index, str(temp))
            temp.replace(self.directory / "vectors.faiss")
        else:
            (self.directory / "vectors.faiss").unlink(missing_ok=True)
        (self.directory / "vectors.json").write_text(json.dumps(info))

    def status(self) -> list[dict]:
        with sqlite3.connect(self.db) as con:
            return [dict(path=r[0], sha256=r[1], status=r[2], error=r[3])
                    for r in con.execute("SELECT path,sha,status,error FROM documents ORDER BY path")]

    def search(self, question: str, limit: int = 8) -> list[Evidence]:
        tokens = list(dict.fromkeys(tokenize(question)))[:40]
        if not tokens:
            return []
        with self.lock, sqlite3.connect(self.db) as con:
            rows = {r[0]: r for r in con.execute("SELECT id,path,locator,text,sha FROM chunks")}
            query = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
            lexical = [r[0] for r in con.execute("SELECT id FROM chunks_fts WHERE tokens MATCH ? ORDER BY bm25(chunks_fts) LIMIT 30", (query,))]
            scores = {key: 1 / (60 + i) for i, key in enumerate(lexical, 1)}
            vector_path = self.directory / "vectors.faiss"
            if vector_path.exists():
                info = json.loads((self.directory / "vectors.json").read_text())
                if info["model"] != (self.embedding_model or "lexical-hashing-2048"):
                    raise ValueError("Embedding model changed; reindex documents before searching")
                index = faiss.read_index(str(vector_path))
                values, indexes = index.search(self._embed([question], query=True), min(30, index.ntotal))
                for rank, (value, i) in enumerate(zip(values[0], indexes[0]), 1):
                    if i >= 0 and value > 0:
                        key = info["ids"][i]
                        scores[key] = scores.get(key, 0) + 1 / (60 + rank)
            # Preserve exact allele matches as an independent signal.
            alleles = [t for t in tokens if "*" in t]
            for key, row in rows.items():
                if alleles and any(a in row[3].lower() for a in alleles):
                    scores[key] = scores.get(key, 0) + 0.05
            found = []
            for key in sorted(scores, key=scores.get, reverse=True)[:limit]:
                if key not in rows:
                    continue
                _, path, locator, text, checksum = rows[key]
                found.append(Evidence(id=key, title=Path(path).name, locator=locator,
                                      text=text, source_hash=checksum))
            return found


def pubmed_search(question: str, limit: int = 5) -> list[Evidence]:
    from xml.etree import ElementTree as ET

    from hlagent.agents import safe_text
    endpoint = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    with httpx.Client(timeout=20) as client:
        response = client.get(endpoint + "esearch.fcgi", params={"db": "pubmed", "retmode": "json", "retmax": limit,
                                                                  "term": safe_text(question), "tool": "HLAgent"})
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        response = client.get(endpoint + "efetch.fcgi", params={"db": "pubmed", "retmode": "xml", "id": ",".join(ids)})
        response.raise_for_status()
    output = []
    for article in ET.fromstring(response.text).findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID")
        title = "".join(article.find(".//ArticleTitle").itertext())
        abstract = " ".join("".join(a.itertext()) for a in article.findall(".//AbstractText"))
        if abstract:
            output.append(Evidence(id="MED:" + pmid, title=title, locator="PubMed abstract", text=abstract[:6000],
                                   url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"))
    return output


def tavily_search(question: str, api_key: str, limit: int = 5) -> list[Evidence]:
    from hlagent.agents import safe_text
    response = httpx.post("https://api.tavily.com/search", headers={"Authorization": "Bearer " + api_key},
                          json={"query": safe_text(question), "max_results": limit, "include_answer": False}, timeout=20)
    response.raise_for_status()
    return [Evidence(id="web:" + hashlib.sha256(item["url"].encode()).hexdigest()[:16],
                     title=item["title"], locator="search excerpt; verify full source for interpretation",
                     text=item["content"], url=item["url"]) for item in response.json().get("results", [])]


def scholarly_search(question: str, limit: int = 5) -> list[Evidence]:
    """Read-only scholarly web search with cited abstract records, no automatic PDF downloads."""
    from hlagent.agents import safe_text
    response = httpx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                         params={"query": safe_text(question), "format": "json", "resultType": "core", "pageSize": limit},
                         timeout=20, follow_redirects=False)
    response.raise_for_status()
    evidence = []
    for item in response.json().get("resultList", {}).get("result", []):
        abstract = re.sub(r"<[^>]+>", " ", item.get("abstractText", "")).strip()
        if not abstract:
            continue
        identifier, source = item["id"], item["source"]
        url = "https://doi.org/" + item["doi"] if item.get("doi") else f"https://europepmc.org/article/{source}/{identifier}"
        evidence.append(Evidence(id=f"{source}:{identifier}", title=item.get("title", identifier),
                                 locator=f"abstract; {item.get('pubYear', 'unknown year')}", text=abstract[:6000], url=url))
    return evidence


def start_index_watcher(index: KnowledgeIndex, stop: threading.Event):
    def watch():
        while not stop.is_set():
            try:
                index.sync()
            except Exception as exc:
                (index.directory / "index-error.txt").write_text(str(exc))
            stop.wait(10)
    thread = threading.Thread(target=watch, name="hlagent-knowledge", daemon=True)
    thread.start()
    return thread
