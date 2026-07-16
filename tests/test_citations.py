from rag_core.generation.answer import (
    _build_citations,
    _extract_cited_indices,
    _format_context,
)
from rag_core.schemas import Chunk, RetrievedChunk


def make_retrieved_chunk(index: int, text: str | None = None) -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=f"documents/example#{index}",
        doc_id="documents/example",
        chunk_index=index,
        text=text or f"Chunk text {index}",
        token_count=10,
        title=f"Example {index}",
    )
    return RetrievedChunk(chunk=chunk, score=1.0 - index / 10)


def test_extract_cited_indices_dedupes_and_preserves_first_appearance() -> None:
    answer = "Second source [2], first source [1], and second again [2]."

    assert _extract_cited_indices(answer, max_n=6) == [2, 1]


def test_extract_cited_indices_drops_out_of_range_markers() -> None:
    answer = "Valid [1], too high [7], zero [0], and valid [6]."

    assert _extract_cited_indices(answer, max_n=6) == [1, 6]


def test_extract_cited_indices_returns_empty_when_no_markers_exist() -> None:
    assert _extract_cited_indices("An answer without citations.", max_n=6) == []


def test_build_citations_preserves_original_markers_and_chunk_mapping() -> None:
    retrieved = [make_retrieved_chunk(index) for index in range(6)]

    citations = _build_citations(retrieved, cited=[2, 1, 6])

    assert [(citation.marker, citation.chunk_id) for citation in citations] == [
        (2, "documents/example#1"),
        (1, "documents/example#0"),
        (6, "documents/example#5"),
    ]


def test_build_citations_flattens_and_limits_snippet() -> None:
    text = ("First line.\nSecond line.\n" + "detail " * 80).strip()
    retrieved = [make_retrieved_chunk(0, text=text)]

    citation = _build_citations(retrieved, cited=[1])[0]

    assert len(citation.snippet) <= 240
    assert "\n" not in citation.snippet
    assert citation.snippet.startswith("First line. Second line.")


def test_format_context_numbers_chunks_and_includes_chunk_ids() -> None:
    retrieved = [make_retrieved_chunk(index) for index in range(3)]

    context = _format_context(retrieved)

    assert "[1] documents/example#0" in context
    assert "[2] documents/example#1" in context
    assert "[3] documents/example#2" in context
