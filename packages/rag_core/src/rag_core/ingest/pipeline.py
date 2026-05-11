from __future__ import annotations
from dataclasses import dataclass

from rag_core.ingest.chunk import chunk_document
from rag_core.ingest.embed import embed_texts
from rag_core.ingest.loader import iter_documents
from rag_core.storage.qdrant import delete_doc, ensure_collection, upsert_chunks


@dataclass
class IngestStats:
    documents: int = 0
    chunks: int = 0


def run_ingest() -> IngestStats:
    ensure_collection()
    stats = IngestStats()
    for doc in iter_documents():
        chunks = chunk_document(doc)
        if not chunks:
            continue
        delete_doc(doc.doc_id)  # idempotent re-ingest
        vectors = embed_texts([c.text for c in chunks])
        upsert_chunks(chunks, vectors)
        stats.documents += 1
        stats.chunks += len(chunks)
        print(f"  + {doc.doc_id}  ({len(chunks)} chunks)")
    return stats
