from pathlib import Path

from rag_core.ingest.chunk import MAX_TOKENS, MIN_TOKENS, chunk_document
from rag_core.schemas import Document


def make_document(body: str, doc_id: str = "synthetic/article") -> Document:
    return Document(
        doc_id=doc_id,
        path=Path("synthetic/article/index.md"),
        title="Synthetic article",
        body=body,
    )


def test_multi_paragraph_chunks_do_not_exceed_max_tokens() -> None:
    paragraph = "retrieval " * 220
    document = make_document("\n\n".join([paragraph, paragraph, paragraph]))

    chunks = chunk_document(document)

    assert len(chunks) > 1
    assert all(chunk.token_count <= MAX_TOKENS for chunk in chunks)


def test_tail_under_min_tokens_merges_backward() -> None:
    large_paragraph = "context " * 450
    tiny_tail = "tail " * 60
    document = make_document(f"{large_paragraph}\n\n{tiny_tail}")

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert "tail" in chunks[0].text
    assert chunks[0].token_count >= MIN_TOKENS


def test_single_long_paragraph_is_hard_split_into_pieces() -> None:
    document = make_document("token " * 650)

    chunks = chunk_document(document)

    assert len(chunks) == 2
    assert all(chunk.token_count <= MAX_TOKENS for chunk in chunks)
    assert chunks[0].token_count == MAX_TOKENS


def test_image_references_are_stripped_before_chunking() -> None:
    document = make_document(
        "The first paragraph explains retrieval.\n\n"
        "![architecture diagram](architecture.png)\n\n"
        "The final paragraph explains reranking."
    )

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert "architecture.png" not in chunks[0].text
    assert "![architecture diagram]" not in chunks[0].text
    assert "The first paragraph" in chunks[0].text
    assert "The final paragraph" in chunks[0].text


def test_chunk_ids_and_indices_follow_chunk_order() -> None:
    paragraph = "evaluation " * 300
    document = make_document(
        "\n\n".join([paragraph, paragraph, paragraph]),
        doc_id="companies/example/evals",
    )

    chunks = chunk_document(document)

    assert [chunk.chunk_id for chunk in chunks] == [
        f"companies/example/evals#{index}" for index in range(len(chunks))
    ]
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_empty_body_produces_no_chunks() -> None:
    document = make_document(" \n\n\t\n ")

    assert chunk_document(document) == []
