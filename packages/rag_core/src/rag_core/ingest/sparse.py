from __future__ import annotations
from functools import lru_cache

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

_MODEL = "Qdrant/bm25"


@lru_cache(maxsize=1)
def _model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=_MODEL)


def _to_sparse(emb) -> SparseVector:
    return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())


def sparse_texts(texts: list[str]) -> list[SparseVector]:
    if not texts:
        return []
    return [_to_sparse(e) for e in _model().embed(texts)]


def sparse_query(text: str) -> SparseVector:
    return _to_sparse(next(iter(_model().query_embed([text]))))
