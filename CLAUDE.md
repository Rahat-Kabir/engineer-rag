# engineer-rag

Engineering RAG over a curated corpus of technical articles. Quality > scale.
Folder-based ingest (`data/articles/**/index.md`), not a crawler.

## Core Principles

- **Think Before Coding**: State assumptions. If uncertain, ask. Don't guess.
- **Simplicity First**: No overengineering. No "flexibility" that wasn't asked for.
- **Surgical Changes**: Only touch what is necessary. Don't reformat adjacent code.
- **Goal-Driven**: Create verifiable success criteria, then make them pass.
- **Fail Fast**: Don't swallow exceptions. Prefer a clear failure over silent
  fallback. Only catch with a specific recovery plan.
- **Ask Before Picking Tech**: Models, embedders, vector stores, libraries.
  Always confirm with the user before introducing a new one.

## Stack (locked)

- **Python**: 3.12+ (uv currently resolving 3.13). uv workspace.
- **Vectors**: Qdrant (Docker, single container). Named vectors `dense` (cosine,
  1536d) + `bm25` (sparse, IDF computed server-side).
- **Embedder**: OpenAI `text-embedding-3-small` (dense) + `fastembed`
  `Qdrant/bm25` (sparse).
- **LLM**: configurable via `LLM_MODEL` (currently `gpt-5.4-mini`).
- **UI**: Streamlit (dev/debug). FastAPI + Next.js planned (Phase 6+).
- **Persistence**: SQLite planned for chat/feedback (Phase 6). No Postgres.
- **No LangChain / LlamaIndex.** Built from primitives.

## Architecture rules

- **`packages/rag_core/` is the brain.** Apps are thin.
- **Streamlit imports `rag_core` directly.** No HTTP API yet; added in Phase 6
  alongside Next.js.
- **One Dockerfile only when needed.** Currently zero. Only Qdrant runs in
  Docker. App runs via `uv run`.
- **Folder-based ingest only.** Never add a URL crawler without discussion.
- **Idempotent ingest.** Deterministic chunk IDs (`{doc_id}#{idx}`) and UUID5
  point IDs. Re-ingest deletes + re-upserts; safe to run anytime.
- **Tests deferred** until modules stop changing (revisit after Phase 5).

## uv workspace conventions

- Add a dep to a specific package: `uv add --package rag_core <pkg>` (or
  `--package ui_streamlit`).
- Add a dep to root: `uv add <pkg>`.
- Never edit `pyproject.toml` `dependencies` arrays by hand.
- After any `pyproject.toml` change: `uv sync`.

## Corpus & metadata rules

- Articles live at `data/articles/<taxonomy>/<slug>/index.md` (current taxonomy:
  `companies/<company>/<slug>/`).
- Frontmatter fields: `title`, `source_url`, `authors`, `published_at`,
  `topics`, `company`. All optional except `title` (which falls back to folder
  name).
- **Never invent metadata.** If `source_url` (or any field) wasn't provided by
  the user, leave it out of the frontmatter. Don't guess URLs from context.
- Images (`*.webp`, `*.png`) co-located with `index.md`. Currently stripped at
  chunk time; VLM captioning lands in Phase 5.

## Global

- `AGENTS.md` is the source of truth. `CLAUDE.md` must stay byte-identical.
  Any edit to `AGENTS.md` must be mirrored to `CLAUDE.md` in the same change.
- After adding a new file, tool, or feature, **ask the user** whether to
  update `README.md`, `CLAUDE.md` / `AGENTS.md` (Project Structure section),
  and `docs/PROGRESS.md`. Don't update them silently.
- Phase status, known limitations, and next-up work live in
  [`docs/PROGRESS.md`](docs/PROGRESS.md). Read it before claiming "what's
  built" or "what's next."

## Project Structure

```
engineer-rag/
├── AGENTS.md                  # mirrored to CLAUDE.md (source of truth)
├── CLAUDE.md
├── README.md
├── pyproject.toml             # workspace root (uv)
├── uv.lock
├── docker-compose.yml         # qdrant only
├── .env / .env.example
│
├── docs/
│   └── PROGRESS.md            # phase status, decisions, limitations, next
│
├── data/
│   ├── articles/                       # corpus (gitignored except README)
│   │   ├── companies/
│   │   │   ├── anthropic/<slug>/index.md   # + co-located *.webp / *.png
│   │   │   ├── openai/<slug>/index.md
│   │   │   └── google/<slug>/index.md
│   │   └── person/
│   │       └── <author>/<slug>/index.md
│   └── eval/
│       └── gold.jsonl                  # gold questions: {question, expected_chunk_ids}
│
├── packages/
│   └── rag_core/
│       ├── pyproject.toml
│       └── src/rag_core/
│           ├── __init__.py
│           ├── config.py            # pydantic-settings (.env)
│           ├── schemas.py           # Document, Chunk, Citation, RetrievedChunk, QueryResult
│           ├── ingest/
│           │   ├── loader.py        # walks data/articles/**/index.md, parses frontmatter
│           │   ├── chunk.py         # paragraph chunker, ≤500 / ≥80 tokens, image refs stripped
│           │   ├── embed.py         # OpenAI batched dense embeddings
│           │   ├── sparse.py        # fastembed BM25 sparse vectors
│           │   └── pipeline.py      # orchestrator: ensure → load → chunk → embed+sparse → upsert
│           ├── retrieval/
│           │   └── search.py        # hybrid search: dense + BM25 sparse, fused with RRF (rerank in Phase 5b.2)
│           ├── generation/
│           │   ├── answer.py        # answer_question() → QueryResult
│           │   └── prompts/answer.md
│           ├── eval/
│           │   └── run.py           # gold loader, recall@k, MRR, refusal-correct
│           └── storage/
│               └── qdrant.py        # ensure_collection / upsert_chunks / delete_doc / search
│
├── apps/
│   └── ui_streamlit/
│       ├── pyproject.toml
│       └── src/ui_streamlit/
│           └── app.py               # chat UI, citations, debug toggle
│
└── scripts/
    ├── ingest.py                    # uv run python -m scripts.ingest
    ├── query.py                     # uv run python -m scripts.query "..."
    ├── eval.py                      # uv run python -m scripts.eval
    └── inspect.py                   # uv run python -m scripts.inspect {docs|chunks|chunk}
```

_Planned but not built yet:_ `apps/api/` (FastAPI, Phase 6), `apps/ui_next/`
(Next.js, Phase 7), `tests/`.

## Operating commands

```powershell
docker compose up -d qdrant
uv sync
uv run python -m scripts.ingest
uv run python -m scripts.query "what is context rot?"
uv run streamlit run apps/ui_streamlit/src/ui_streamlit/app.py

# Eval and inspect
uv run python -m scripts.eval
uv run python -m scripts.inspect docs
uv run python -m scripts.inspect chunks <doc_id>
uv run python -m scripts.inspect chunk  <chunk_id>
```

## Collaboration

User prefers step-by-step development with discussion at each step. Before
large feature work:

- Explain the next small slice.
- Keep scope narrow.
- Build it.
- Verify it runs.
- Describe what changed and what was intentionally left unbuilt.

Response style: short and direct. No filler, no recap-summary at the end of
responses. State results and decisions; skip the narration.
