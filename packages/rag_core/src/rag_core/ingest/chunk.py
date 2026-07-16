from __future__ import annotations
import re
import tiktoken

from rag_core.schemas import Document, Chunk

_ENC = tiktoken.get_encoding("cl100k_base")

MAX_TOKENS = 500
MIN_TOKENS = 80

_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


def _count(text: str) -> int:
    return len(_ENC.encode(text))


def _strip_image_refs(text: str) -> str:
    """Remove markdown image references from the body."""
    return _IMG_RE.sub("", text)


def _split_long(text: str, max_tokens: int) -> list[str]:
    """Hard split a too-long block into <= max_tokens pieces by token slicing."""
    token_ids = _ENC.encode(text)
    if len(token_ids) <= max_tokens:
        return [text]
    pieces = []
    for start_index in range(0, len(token_ids), max_tokens):
        pieces.append(_ENC.decode(token_ids[start_index : start_index + max_tokens]))
    return pieces


def chunk_document(doc: Document) -> list[Chunk]:
    body = _strip_image_refs(doc.body).strip()
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", body)
        if paragraph.strip()
    ]

    blocks: list[str] = []
    for paragraph in paragraphs:
        for piece in _split_long(paragraph, MAX_TOKENS):
            blocks.append(piece)

    chunk_texts: list[str] = []
    current_chunk_text = ""
    current_chunk_token_count = 0
    for block in blocks:
        block_token_count = _count(block)
        if (
            current_chunk_text
            and current_chunk_token_count + block_token_count > MAX_TOKENS
        ):
            chunk_texts.append(current_chunk_text)
            current_chunk_text = block
            current_chunk_token_count = block_token_count
        else:
            current_chunk_text = (
                f"{current_chunk_text}\n\n{block}" if current_chunk_text else block
            )
            current_chunk_token_count += block_token_count
    if current_chunk_text:
        # Avoid leaving a tiny final chunk with too little context for retrieval.
        if chunk_texts and current_chunk_token_count < MIN_TOKENS:
            chunk_texts[-1] = chunk_texts[-1] + "\n\n" + current_chunk_text
        else:
            chunk_texts.append(current_chunk_text)

    chunks: list[Chunk] = []
    for chunk_index, text in enumerate(chunk_texts):
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{chunk_index}",
                doc_id=doc.doc_id,
                chunk_index=chunk_index,
                text=text,
                token_count=_count(text),
                title=doc.title,
                source_url=doc.source_url,
                company=doc.company,
                topics=doc.topics,
            )
        )
    return chunks
