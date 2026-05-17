from __future__ import annotations
from functools import lru_cache

import voyageai

from rag_core.config import settings
from rag_core.schemas import RetrievedChunk


@lru_cache(maxsize=1)
def _client() -> voyageai.Client:
    return voyageai.Client(api_key=settings.voyage_api_key)


def is_enabled() -> bool:
    return bool(settings.voyage_api_key)


def rerank(
    question: str,
    candidates: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    """Re-order candidates by Voyage cross-encoder relevance score.

    No-op if voyage_api_key is unset — returns candidates[:top_k] untouched.
    """
    if not candidates:
        return []
    if not is_enabled():
        return candidates[:top_k]

    docs = [c.chunk.text for c in candidates]
    res = _client().rerank(
        query=question,
        documents=docs,
        model=settings.rerank_model,
        top_k=top_k,
    )

    reordered: list[RetrievedChunk] = []
    for r in res.results:
        original = candidates[r.index]
        reordered.append(
            RetrievedChunk(chunk=original.chunk, score=float(r.relevance_score))
        )
    return reordered
