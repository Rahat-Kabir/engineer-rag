from __future__ import annotations
from pathlib import Path
from typing import Iterator

import frontmatter

from rag_core.config import settings
from rag_core.schemas import Document


def _doc_id_from_path(path: Path) -> str:
    """Path under articles/ without index.md, posix-style.

    e.g. data/articles/companies/openai/tool-calling/index.md
         -> companies/openai/tool-calling
    """
    rel = path.relative_to(settings.articles_dir).parent
    return rel.as_posix()


def load_one(path: Path) -> Document:
    post = frontmatter.load(path)
    meta = post.metadata or {}
    doc_id = _doc_id_from_path(path)
    title = meta.get("title") or path.parent.name.replace("-", " ").title()

    return Document(
        doc_id=doc_id,
        path=path.resolve(),
        title=title,
        body=post.content,
        source_url=meta.get("source_url"),
        authors=list(meta.get("authors") or []),
        published_at=str(meta["published_at"]) if meta.get("published_at") else None,
        topics=list(meta.get("topics") or []),
        company=meta.get("company"),
        extra={k: v for k, v in meta.items() if k not in {
            "title", "source_url", "authors", "published_at", "topics", "company"
        }},
    )


def iter_documents() -> Iterator[Document]:
    root = settings.articles_dir
    if not root.exists():
        return
    for md in sorted(root.rglob("index.md")):
        yield load_one(md)
