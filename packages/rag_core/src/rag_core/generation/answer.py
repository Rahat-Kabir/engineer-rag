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
    for i, r in enumerate(retrieved, 1):
        c = r.chunk
        lines.append(f"[{i}] {c.chunk_id}\n{c.text}\n")
    return "\n".join(lines)


def _extract_cited_indices(answer: str, max_n: int) -> list[int]:
    """Parse [N] markers from the answer, deduped, in first-appearance order, clamped to valid range."""
    seen: list[int] = []
    for m in _CITATION_RE.finditer(answer):
        n = int(m.group(1))
        if 1 <= n <= max_n and n not in seen:
            seen.append(n)
    return seen


def _build_citations(retrieved: list[RetrievedChunk], cited: list[int]) -> list[Citation]:
    out: list[Citation] = []
    for n in cited:
        c = retrieved[n - 1].chunk
        snippet = c.text[:240].replace("\n", " ").strip()
        out.append(
            Citation(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                title=c.title,
                source_url=c.source_url,
                snippet=snippet,
            )
        )
    return out


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
    user_msg = f"Question: {question}\n\nSources:\n{context}"

    client = _client()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        max_completion_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_msg},
        ],
    )
    answer_text = (resp.choices[0].message.content or "").strip()

    cited = _extract_cited_indices(answer_text, max_n=len(retrieved))
    citations = _build_citations(retrieved, cited)

    return QueryResult(
        question=question,
        answer=answer_text,
        citations=citations,
        retrieved=retrieved,
    )
