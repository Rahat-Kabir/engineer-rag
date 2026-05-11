from __future__ import annotations
from rag_core.ingest.embed import embed_query
from rag_core.schemas import RetrievedChunk
from rag_core.storage.qdrant import search as qdrant_search


def search(question: str, limit: int = 8) -> list[RetrievedChunk]:
    vec = embed_query(question)
    return qdrant_search(vec, limit=limit)
