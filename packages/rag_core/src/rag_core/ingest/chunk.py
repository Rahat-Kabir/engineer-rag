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
    ids = _ENC.encode(text)
    if len(ids) <= max_tokens:
        return [text]
    out = []
    for i in range(0, len(ids), max_tokens):
        out.append(_ENC.decode(ids[i : i + max_tokens]))
    return out


def chunk_document(doc: Document) -> list[Chunk]:
    body = _strip_image_refs(doc.body).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]

    blocks: list[str] = []
    for p in paragraphs:
        for piece in _split_long(p, MAX_TOKENS):
            blocks.append(piece)

    merged: list[str] = []
    buf = ""
    buf_tokens = 0
    for b in blocks:
        bt = _count(b)
        if buf and buf_tokens + bt > MAX_TOKENS:
            merged.append(buf)
            buf, buf_tokens = b, bt
        else:
            buf = f"{buf}\n\n{b}" if buf else b
            buf_tokens += bt
    if buf:
        if merged and buf_tokens < MIN_TOKENS:
            merged[-1] = merged[-1] + "\n\n" + buf
        else:
            merged.append(buf)

    chunks: list[Chunk] = []
    for i, text in enumerate(merged):
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}#{i}",
                doc_id=doc.doc_id,
                chunk_index=i,
                text=text,
                token_count=_count(text),
                title=doc.title,
                source_url=doc.source_url,
                company=doc.company,
                topics=doc.topics,
            )
        )
    return chunks
