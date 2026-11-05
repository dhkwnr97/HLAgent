"""ChromaDB knowledge base with embeddings computed by Pydantic AI (no Chroma embedding function).

The collection records the embedding model it was built with; querying with another model is refused
(vectors from different models are not comparable) and the user is asked to re-index.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hlagent import paths
from hlagent.logging_utils import get_logger

log = get_logger(__name__)

COLLECTION = "hla_kb"
_DOI = re.compile(r"10\.\d{4,9}/[^\s,;]+")


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    page: int
    title: str = ""
    doi: str = ""

    def meta(self) -> dict[str, Any]:
        return {"source": self.source, "page": self.page, "title": self.title, "doi": self.doi}


@dataclass
class Hit:
    id: str
    text: str
    source: str
    page: int
    title: str
    doi: str
    score: float  # cosine similarity (1 - distance)

    def cite(self) -> str:
        t = self.title or self.source
        return f"{t} (p.{self.page}){', doi:' + self.doi if self.doi else ''}"


def split_text(text: str, max_chars: int = 1800, overlap: int = 200) -> list[str]:
    """Paragraph-packing splitter: keeps paragraphs whole when possible, hard-splits very long ones."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > max_chars:
            head, p = p[:max_chars], p[max_chars - overlap :]
            if cur:
                out.append(cur)
                cur = ""
            out.append(head)
        if len(cur) + len(p) + 2 <= max_chars:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                out.append(cur)
            cur = (cur[-overlap:] + "\n\n" + p) if cur and overlap else p
    if cur:
        out.append(cur)
    return [c for c in out if len(c) >= 40]


def file_id(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def load_document(path: Path) -> list[Chunk]:
    """PDF (pymupdf4llm page chunks) or Markdown/text file -> chunks with page provenance."""
    fid = file_id(path)
    chunks: list[Chunk] = []
    if path.suffix.lower() == ".pdf":
        import contextlib
        import io

        import pymupdf4llm

        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):  # OCR notices
            pages = pymupdf4llm.to_markdown(str(path), page_chunks=True)
        meta = pages[0]["metadata"] if pages else {}
        title = (meta.get("title") or "").strip()
        if (
            len(title.split()) < 3 and pages
        ):  # PDF metadata titles are often file codes; use the first heading
            heads = [h.strip() for h in re.findall(r"^#{1,3}\s+\**(.+?)\**\s*$", pages[0]["text"], re.M)]
            heads = [h for h in heads if len(h.split()) >= 4]  # skip labels such as "Review Article"
            title = heads[0] if heads else title
        m = _DOI.search(" ".join(str(meta.get(k, "")) for k in ("subject", "keywords", "title")))
        doi = m.group(0).rstrip(".") if m else ""
        if not doi and pages:
            m = _DOI.search(pages[0]["text"])
            doi = m.group(0).rstrip(".") if m else ""
        for pg in pages:
            pno = int(pg["metadata"].get("page_number") or pg["metadata"].get("page") or 0)
            for i, t in enumerate(split_text(pg["text"])):
                chunks.append(Chunk(f"{fid}:{pno}:{i}", t, path.name, pno, title, doi))
    elif path.suffix.lower() in (".md", ".txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        h = re.search(r"^#\s+(.+)$", text, re.M)
        for i, t in enumerate(split_text(text)):
            chunks.append(Chunk(f"{fid}:0:{i}", t, path.name, 0, h.group(1).strip() if h else path.stem))
    return chunks


class KnowledgeBase:
    def __init__(self, embedder, model_spec: str, path: Path | None = None):
        import chromadb

        self.embedder = embedder
        self.model_spec = model_spec
        self.client = chromadb.PersistentClient(path=str(path or paths.chroma_dir()))

    def _collection(self, create: bool = True):
        if create:
            return self.client.get_or_create_collection(
                COLLECTION,
                embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
                metadata={"embedding_model": self.model_spec},
            )
        return self.client.get_collection(COLLECTION, embedding_function=None)

    def built_with(self) -> str | None:
        try:
            return (self._collection(create=False).metadata or {}).get("embedding_model")
        except Exception:  # noqa: BLE001 - collection absent
            return None

    def count(self) -> int:
        try:
            return self._collection(create=False).count()
        except Exception:  # noqa: BLE001
            return 0

    def reset(self) -> None:
        try:
            self.client.delete_collection(COLLECTION)
        except Exception:  # noqa: BLE001 - nothing to delete
            pass

    def sources(self) -> list[str]:
        try:
            got = self._collection(create=False).get(include=["metadatas"])
        except Exception:  # noqa: BLE001
            return []
        return sorted({str(m["source"]) for m in got["metadatas"] or []})

    def add(self, chunks: list[Chunk], batch: int = 64) -> int:
        if not chunks:
            return 0
        built = self.built_with()
        if built and built != self.model_spec:
            raise RuntimeError(
                f"Knowledge base was built with {built}; re-index with {self.model_spec} (hlagent ingest --rebuild)."
            )
        col = self._collection()
        have = set(col.get(ids=[c.id for c in chunks])["ids"])
        new = [c for c in chunks if c.id not in have]
        for i in range(0, len(new), batch):
            part = new[i : i + batch]
            emb = self.embedder.embed_documents_sync([c.text for c in part]).embeddings
            col.add(
                ids=[c.id for c in part],
                documents=[c.text for c in part],
                embeddings=[list(e) for e in emb],
                metadatas=[c.meta() for c in part],
            )
        return len(new)

    def query(self, text: str, k: int = 6) -> list[Hit]:
        built = self.built_with()
        if built is None:
            return []
        if built != self.model_spec:
            raise RuntimeError(
                f"Knowledge base was built with {built} but the current embedding model is "
                f"{self.model_spec}; re-index (hlagent ingest --rebuild)."
            )
        col = self._collection(create=False)
        if col.count() == 0:
            return []
        q = self.embedder.embed_query_sync(text).embeddings[0]
        r = col.query(
            query_embeddings=[list(q)],
            n_results=min(k, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        if r["documents"] is None or r["metadatas"] is None or r["distances"] is None:
            return []
        hits = []
        for i, d, m, dist in zip(
            r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0], strict=True
        ):
            hits.append(
                Hit(
                    i,
                    d,
                    m.get("source", ""),
                    int(m.get("page", 0)),
                    m.get("title", ""),
                    m.get("doi", ""),
                    round(1.0 - float(dist), 4),
                )
            )
        return hits


def ingest_folder(folder: Path, kb: KnowledgeBase, rebuild: bool = False) -> dict[str, int]:
    if rebuild:
        kb.reset()
    out: dict[str, int] = {}
    for f in sorted(folder.glob("*")):
        if f.suffix.lower() not in (".pdf", ".md", ".txt"):
            continue
        try:
            out[f.name] = kb.add(load_document(f))
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the rest
            log.warning("ingest failed for %s: %s", f.name, e)
            out[f.name] = -1
    return out
