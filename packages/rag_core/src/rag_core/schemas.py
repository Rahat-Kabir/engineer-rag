from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field


class Document(BaseModel):
    """A normalized article loaded from disk."""

    doc_id: str                      # stable id derived from path, e.g. "companies/openai/tool-calling"
    path: Path                       # absolute path to index.md
    title: str
    body: str                        # markdown body (frontmatter stripped)
    source_url: str | None = None
    authors: list[str] = Field(default_factory=list)
    published_at: str | None = None  # ISO date string from frontmatter
    topics: list[str] = Field(default_factory=list)
    company: str | None = None
    extra: dict = Field(default_factory=dict)


class Chunk(BaseModel):
    """A retrievable unit derived from a Document."""

    chunk_id: str                    # f"{doc_id}#{chunk_index}"
    doc_id: str
    chunk_index: int
    text: str
    token_count: int

    # duplicated from Document so Qdrant payload can filter on them
    title: str
    source_url: str | None = None
    company: str | None = None
    topics: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    marker: int                      # the [N] used in the answer text; display this, never renumber
    chunk_id: str
    doc_id: str
    title: str
    source_url: str | None = None
    snippet: str


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float


class QueryResult(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    retrieved: list[RetrievedChunk]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
