from __future__ import annotations
from rag_core.config import settings
from rag_core.ingest.embed import embed_query
from rag_core.ingest.sparse import sparse_query
from rag_core.retrieval.rerank import is_enabled as rerank_enabled, rerank
from rag_core.schemas import RetrievedChunk
from rag_core.storage.qdrant import search as qdrant_search


def search(question: str, limit: int = 8) -> list[RetrievedChunk]:
    """Hybrid search (dense + BM25, RRF) + optional Voyage cross-encoder rerank.

    Flow:
      1. Hybrid prefetch — top `rerank_prefetch` candidates from Qdrant.
      2. If Voyage is configured, rerank to `limit`.
         Otherwise return top `limit` from hybrid directly.
    """
    dense = embed_query(question)
    sparse = sparse_query(question)

    if rerank_enabled():
        candidates = qdrant_search(dense, sparse, limit=settings.rerank_prefetch)
        return rerank(question, candidates, top_k=limit)

    return qdrant_search(dense, sparse, limit=limit)
