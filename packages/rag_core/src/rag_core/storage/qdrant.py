from __future__ import annotations
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from rag_core.config import settings
from rag_core.schemas import Chunk, RetrievedChunk

_NAMESPACE = uuid.UUID("6f1e0a9a-9c1e-4a1c-9a3a-000000000001")


def _client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def point_id_for(chunk_id: str) -> str:
    """Deterministic UUID5 so re-ingest upserts cleanly."""
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


def ensure_collection(client: QdrantClient | None = None) -> None:
    c = client or _client()
    if c.collection_exists(settings.qdrant_collection):
        return
    c.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=settings.embed_dim, distance=Distance.COSINE),
    )


def upsert_chunks(chunks: list[Chunk], vectors: list[list[float]]) -> int:
    assert len(chunks) == len(vectors), "chunks and vectors length mismatch"
    c = _client()
    ensure_collection(c)
    points = [
        PointStruct(
            id=point_id_for(ch.chunk_id),
            vector=vec,
            payload=ch.model_dump(mode="json"),
        )
        for ch, vec in zip(chunks, vectors)
    ]
    c.upsert(collection_name=settings.qdrant_collection, points=points)
    return len(points)


def delete_doc(doc_id: str) -> None:
    c = _client()
    c.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )


def search(query_vector: list[float], limit: int = 8) -> list[RetrievedChunk]:
    c = _client()
    res = c.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    out: list[RetrievedChunk] = []
    for p in res.points:
        out.append(RetrievedChunk(chunk=Chunk(**p.payload), score=p.score))
    return out
