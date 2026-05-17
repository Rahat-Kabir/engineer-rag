from __future__ import annotations
from rag_core.ingest.embed import embed_query
from rag_core.ingest.sparse import sparse_query
from rag_core.schemas import RetrievedChunk
from rag_core.storage.qdrant import search as qdrant_search


def search(question: str, limit: int = 8) -> list[RetrievedChunk]:
    """Hybrid search: dense embedding + BM25 sparse, fused with RRF in Qdrant."""
    dense = embed_query(question)
    sparse = sparse_query(question)
    return qdrant_search(dense, sparse, limit=limit)
