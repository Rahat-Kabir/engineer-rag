# engineer-rag — progress

_Last updated: 2026-05-11_

## What's working today

End-to-end RAG over a curated corpus, queryable from a Streamlit chat UI:

```
data/articles/**/index.md
   → loader (frontmatter + body)
   → paragraph chunker (≤500 / ≥80 tokens, image refs stripped)
   → OpenAI embedding (text-embedding-3-small, 1536d)
   → Qdrant upsert (deterministic UUID5 ids, idempotent re-ingest)
   → dense search (cosine, top-k)
   → LLM answer with [N] inline citations + chunk-level sources
   → Streamlit chat UI (history, citation cards, debug toggle)
```

## Phases

| # | Phase | Status |
|---|---|---|
| 0 | Skeleton: uv workspace, git, .gitignore, README, docker-compose (Qdrant only) | [done] |
| 1 | Spine: ingest (loader/chunk/embed/pipeline) + dense search + CLI scripts | [done] |
| 2 | Generation: LLM answer, citation extraction, validator, refusal prompt | [done] |
| 3 | Streamlit UI: chat, citations, retrieved-chunks debug, sidebar controls | [done] |
| 4 | Tests for stable modules | [skipped] revisit after Phase 5 |
| 5a | Eval harness: gold dataset, recall@k, MRR, scripts/eval.py | [done] |
| 5b | Retrieval improvements (each measured against eval) | [next] |
| 6 | FastAPI + Dockerfiles + SQLite for chat history & feedback | later |
| 7 | Next.js + shadcn UI | later |

## Stack (locked)

- Python 3.13 (`>=3.12`), uv workspace
- Qdrant 1.18 (Docker, single container)
- OpenAI `text-embedding-3-small` (1536d, cosine)
- LLM: `gpt-5.4-mini` (configurable via `LLM_MODEL`)
- Pydantic v2, pydantic-settings
- Streamlit (dev/debug UI)

## Repo layout (current)

```
engineer-rag/
├── packages/rag_core/src/rag_core/
│   ├── config.py
│   ├── schemas.py            # Document, Chunk, Citation, RetrievedChunk, QueryResult
│   ├── ingest/               # loader, chunk, embed, pipeline
│   ├── retrieval/            # search (dense only)
│   ├── generation/           # answer, validator, prompts/answer.md
│   └── storage/              # qdrant
├── apps/ui_streamlit/src/ui_streamlit/app.py
├── scripts/                  # ingest.py, query.py
├── data/articles/            # README + your articles (corpus folders gitignored)
├── docker-compose.yml        # qdrant only
├── pyproject.toml            # workspace root
└── .env / .env.example
```

## Corpus

Corpus is private. The repo ships empty — bring your own articles
(see project `README.md` → "Adding a new article").

## Key decisions made

- **Folder-based ingest** (curated), not URL crawling.
- **One Dockerfile only when needed.** Currently zero (only Qdrant runs in Docker; app runs via `uv run`).
- **No LangChain / LlamaIndex.** Built from primitives.
- **SQLite (later) for chat/feedback**, not Postgres. Qdrant is the only DB right now.
- **Streamlit imports `rag_core` directly.** No API yet. FastAPI lands when Next.js starts.
- **Tests deferred** until modules stop changing.

## Known limitations

- Re-ingest re-embeds **every** chunk every run (no content-hash dedup yet). Cost is negligible (~$0.0001/run for current corpus), but won't scale.
- Chunker is paragraph-based, not heading-aware. Sections can leak across chunk boundaries.
- Image references (`*.webp`, `*.png`) are silently stripped at chunk time. No VLM captioning yet.
- Retrieval is **dense only**. No BM25/sparse, no rerank, no hybrid fusion.
- No persistence: Streamlit chat history resets on refresh.
- No streaming. Answers appear after full LLM response.
- Hallucinated `[N]` citations are filtered out of the displayed sources but the answer text isn't rewritten.

## Baseline (Phase 5a, 2026-05-11)

15 gold questions across 2 articles (14 retrieval + 1 refusal).

```
Recall@5:        0.929  (13/14)
Recall@10:       1.000  (14/14)
MRR:             0.828
Refusal-correct: 1.000  (1/1)
```

Soft spots (Phase 5b targets):

- "why are bloated tool sets a problem?" hit at rank 7 (outside top-5). Exact phrase "bloated tool sets" is in the chunk; embedder misses. Hybrid (BM25) should catch.
- "what is Anthropic's definition of an agent?" hit at rank 4. Bridging "Anthropic's definition" → "LLMs autonomously using tools in a loop" is hard for dense alone.
- "how should I use system/user/assistant message roles?" hit at rank 5. Multiple chunks touch on roles; reranking would help isolate the role-specific one.

## Then: Phase 5b (retrieval improvements, in priority order)

Each change is a separate experiment; keep what improves the eval baseline.

1. Structural chunking (split on `##`/`###`, then size-bound)
2. Contextual chunk headers (`[Title] > [Section]` prepended)
3. Hybrid search (dense + BM25/sparse + RRF fusion in Qdrant)
4. Cross-encoder rerank (Cohere `rerank-3.5`, top 30 to top 6)
5. Image captioning (VLM caption webp/png at ingest, inject before chunking)
6. Content-hash dedup (skip unchanged articles on re-ingest)

## Operating commands

```powershell
docker compose up -d qdrant
uv sync
uv run python -m scripts.ingest
uv run python -m scripts.query "what is context rot?"
uv run streamlit run apps/ui_streamlit/src/ui_streamlit/app.py
```
