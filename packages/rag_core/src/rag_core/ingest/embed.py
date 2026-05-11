from __future__ import annotations
from openai import OpenAI

from rag_core.config import settings

_BATCH = 128


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _client()
    out: list[list[float]] = []
    for i in range(0, len(texts), _BATCH):
        batch = texts[i : i + _BATCH]
        resp = client.embeddings.create(model=settings.embed_model, input=batch)
        out.extend(d.embedding for d in resp.data)
    return out


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
