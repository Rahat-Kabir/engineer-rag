from __future__ import annotations
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseVector,
    Modifier,
    PointStruct,
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
)

from rag_core.config import settings
from rag_core.schemas import Chunk, RetrievedChunk

_NAMESPACE = uuid.UUID("6f1e0a9a-9c1e-4a1c-9a3a-000000000001")

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "bm25"


def _client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, timeout=60)


def point_id_for(chunk_id: str) -> str:
    """Deterministic UUID5 so re-ingest upserts cleanly."""
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


def ensure_collection(client: QdrantClient | None = None) -> None:
    qdrant_client = client or _client()
    if qdrant_client.collection_exists(settings.qdrant_collection):
        return
    qdrant_client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=settings.embed_dim, distance=Distance.COSINE
            ),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF),
        },
    )


def upsert_chunks(
    chunks: list[Chunk],
    dense_vectors: list[list[float]],
    sparse_vectors: list[SparseVector],
) -> int:
    assert len(chunks) == len(dense_vectors) == len(sparse_vectors), (
        "chunks, dense, and sparse vector lengths must match"
    )
    client = _client()
    ensure_collection(client)
    points = [
        PointStruct(
            id=point_id_for(chunk.chunk_id),
            vector={
                DENSE_VECTOR_NAME: dense_vector,
                SPARSE_VECTOR_NAME: sparse_vector,
            },
            payload=chunk.model_dump(mode="json"),
        )
        for chunk, dense_vector, sparse_vector in zip(
            chunks, dense_vectors, sparse_vectors
        )
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    return len(points)


def delete_doc(doc_id: str) -> None:
    client = _client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )


def search(
    dense_query: list[float],
    sparse_query: SparseVector,
    limit: int = 8,
    prefetch_limit: int = 30,
) -> list[RetrievedChunk]:
    """Hybrid search: dense + BM25 sparse, fused with RRF."""
    client = _client()
    query_result = client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=prefetch_limit),
            Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=prefetch_limit),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    retrieved_chunks: list[RetrievedChunk] = []
    for point in query_result.points:
        retrieved_chunks.append(
            RetrievedChunk(chunk=Chunk(**point.payload), score=point.score)
        )
    return retrieved_chunks
