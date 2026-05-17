"""Inspect Qdrant contents.

Usage:
    uv run python -m scripts.inspect docs
    uv run python -m scripts.inspect chunks <doc_id>
    uv run python -m scripts.inspect chunk  <chunk_id>
"""
from __future__ import annotations
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from qdrant_client.models import Filter, FieldCondition, MatchValue

from rag_core.config import settings
from rag_core.storage.qdrant import _client


def _scroll_all(flt: Filter | None = None) -> list[dict]:
    c = _client()
    out: list[dict] = []
    offset = None
    while True:
        points, offset = c.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=flt,
            limit=256,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        out.extend(p.payload for p in points)
        if offset is None:
            break
    return out


def cmd_docs() -> None:
    payloads = _scroll_all()
    counts = Counter(p["doc_id"] for p in payloads)
    titles = {p["doc_id"]: p.get("title", "") for p in payloads}

    print(f"{len(counts)} documents, {sum(counts.values())} chunks\n")
    width = max((len(d) for d in counts), default=10)
    for doc_id, n in sorted(counts.items()):
        print(f"  {doc_id:<{width}}  {n:>3} chunks  | {titles[doc_id]}")


def cmd_chunks(doc_id: str) -> None:
    flt = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
    payloads = _scroll_all(flt)
    if not payloads:
        print(f"No chunks found for doc_id: {doc_id}")
        return

    payloads.sort(key=lambda p: p["chunk_index"])
    print(f"{doc_id}  —  {len(payloads)} chunks\n")
    for p in payloads:
        preview = p["text"][:160].replace("\n", " ")
        print(f"  [{p['chunk_index']:>2}] {p['chunk_id']}  ({p['token_count']} tok)")
        print(f"       {preview}{'…' if len(p['text']) > 160 else ''}\n")


def cmd_chunk(chunk_id: str) -> None:
    flt = Filter(must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))])
    payloads = _scroll_all(flt)
    if not payloads:
        print(f"No chunk found: {chunk_id}")
        return

    p = payloads[0]
    print(f"chunk_id:    {p['chunk_id']}")
    print(f"doc_id:      {p['doc_id']}")
    print(f"chunk_index: {p['chunk_index']}")
    print(f"title:       {p.get('title', '')}")
    print(f"source_url:  {p.get('source_url', '')}")
    print(f"company:     {p.get('company', '')}")
    print(f"topics:      {p.get('topics', [])}")
    print(f"token_count: {p['token_count']}")
    print(f"\n--- text ---\n{p['text']}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
    if cmd == "docs":
        cmd_docs()
    elif cmd == "chunks" and len(args) == 2:
        cmd_chunks(args[1])
    elif cmd == "chunk" and len(args) == 2:
        cmd_chunk(args[1])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
