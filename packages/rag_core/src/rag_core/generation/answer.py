from __future__ import annotations
import re
from pathlib import Path
from openai import OpenAI

from rag_core.config import settings
from rag_core.schemas import Citation, QueryResult, RetrievedChunk
from rag_core.retrieval.search import search

_PROMPT_PATH = Path(__file__).parent / "prompts" / "answer.md"
_CITATION_RE = re.compile(r"\[(\d+)\]")


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_context(retrieved: list[RetrievedChunk]) -> str:
    lines = []
    for citation_index, retrieved_chunk in enumerate(retrieved, 1):
        chunk = retrieved_chunk.chunk
        lines.append(f"[{citation_index}] {chunk.chunk_id}\n{chunk.text}\n")
    return "\n".join(lines)


def _extract_cited_indices(answer: str, max_n: int) -> list[int]:
    """Parse [N] markers from the answer, deduped, in first-appearance order, clamped to valid range."""
    cited_indices: list[int] = []
    for citation_match in _CITATION_RE.finditer(answer):
        citation_index = int(citation_match.group(1))
        if (
            1 <= citation_index <= max_n
            and citation_index not in cited_indices
        ):
            cited_indices.append(citation_index)
    return cited_indices


def _build_citations(retrieved: list[RetrievedChunk], cited: list[int]) -> list[Citation]:
    citations: list[Citation] = []
    for citation_index in cited:
        chunk = retrieved[citation_index - 1].chunk
        snippet = chunk.text[:240].replace("\n", " ").strip()
        citations.append(
            Citation(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                title=chunk.title,
                source_url=chunk.source_url,
                snippet=snippet,
            )
        )
    return citations


def answer_question(question: str, top_k: int = 6) -> QueryResult:
    retrieved = search(question, limit=top_k)
    if not retrieved:
        return QueryResult(
            question=question,
            answer="I don't have enough information in the provided sources to answer that.",
            citations=[],
            retrieved=[],
        )

    context = _format_context(retrieved)
    user_message = f"Question: {question}\n\nSources:\n{context}"

    client = _client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        max_completion_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_message},
        ],
    )
    answer_text = (response.choices[0].message.content or "").strip()

    cited = _extract_cited_indices(answer_text, max_n=len(retrieved))
    citations = _build_citations(retrieved, cited)

    return QueryResult(
        question=question,
        answer=answer_text,
        citations=citations,
        retrieved=retrieved,
    )
