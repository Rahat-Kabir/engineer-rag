# engineer-rag — progress

_Last updated: 2026-05-17_

## What's working today

End-to-end RAG over a curated corpus, queryable from a Streamlit chat UI:

```
data/articles/**/index.md
   → loader (frontmatter + body)
   → paragraph chunker (≤500 / ≥80 tokens, image refs stripped)
   → OpenAI embedding (text-embedding-3-small, 1536d) + BM25 sparse (fastembed)
   → Qdrant upsert with named vectors {dense, bm25} (deterministic UUID5 ids)
   → hybrid search: dense + sparse, fused with RRF in Qdrant
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
| 5b | Retrieval improvements (each measured against eval) | [in progress] |
| 5b.1 | Hybrid search (dense + BM25 sparse, RRF fusion) | [done] |
| 6 | FastAPI + Dockerfiles + SQLite for chat history & feedback | later |
| 7 | Next.js + shadcn UI | later |

## Stack (locked)

- Python 3.13 (`>=3.12`), uv workspace
- Qdrant 1.18 (Docker, single container), named vectors `dense` + `bm25`
- OpenAI `text-embedding-3-small` (1536d, cosine) for dense
- `fastembed` with `Qdrant/bm25` for sparse (IDF computed server-side by Qdrant)
- LLM: `gpt-5.4-mini` (configurable via `LLM_MODEL`)
- Pydantic v2, pydantic-settings
- Streamlit (dev/debug UI)

## Repo layout (current)

```
engineer-rag/
├── packages/rag_core/src/rag_core/
│   ├── config.py
│   ├── schemas.py            # Document, Chunk, Citation, RetrievedChunk, QueryResult
│   ├── ingest/               # loader, chunk, embed, sparse, pipeline
│   ├── retrieval/            # search (hybrid: dense + BM25 sparse, RRF)
│   ├── generation/           # answer, validator, prompts/answer.md
│   ├── eval/                 # gold loader, recall@k, MRR
│   └── storage/              # qdrant
├── apps/ui_streamlit/src/ui_streamlit/app.py
├── scripts/                  # ingest.py, query.py, eval.py, inspect.py
├── data/
│   ├── articles/             # README + your articles (corpus folders gitignored)
│   └── eval/gold.jsonl       # 54 gold questions
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
- Retrieval is **hybrid (dense + BM25 sparse, RRF)** — no cross-encoder rerank yet.
- No persistence: Streamlit chat history resets on refresh.
- No streaming. Answers appear after full LLM response.
- Hallucinated `[N]` citations are filtered out of the displayed sources but the answer text isn't rewritten.
- **No answer-quality metric.** Hallucination rate / faithfulness is unmeasured. Eval only covers retrieval.
- **Refusal eval is flaky.** OpenAI embeddings have small non-determinism; borderline refusal cases flip between runs. Treat single-run deltas <3% as noise.

## Baseline — current (Phase 5b.1 hybrid, 2026-05-17)

54 gold questions across 10 articles (50 retrieval + 4 refusal). Hybrid retrieval:
dense (OpenAI `text-embedding-3-small`) + BM25 sparse (fastembed) fused with RRF.

```
Recall@5:        0.920  (46/50)
Recall@10:       0.960  (48/50)
MRR:             0.755
Refusal-correct: 1.000  (4/4)
```

### Previous baselines (for reference)

**Phase 5a dense-only (2026-05-17, same corpus + gold set):**

```
Recall@5:        0.780  (39/50)
Recall@10:       0.860  (43/50)
MRR:             0.630
Refusal-correct: 0.750  (3/4)
```

Phase 5b.1 (hybrid) lift over dense-only: **+0.140 Recall@5, +0.125 MRR**.
5 of 7 known misses flipped to hits — exactly the exact-phrase / named-entity
cases predicted ("bloated tool sets", "Anthropic's definition of an agent",
"message roles", "METR task length doubling", AGENTS.md multi-chunk).

**Phase 5a, original 2-article baseline (15 questions):** Recall@5 0.929, MRR
0.828. Kept only for historical context — too small a corpus + gold set to be
meaningful signal.

### Soft spots (remaining misses)

Only 2 retrieval misses left, both at rank 6–7 — prime cross-encoder rerank
territory (Phase 5b.2):

- "what is the role of the initializer agent versus the coding agent?" —
  regressed from rank 7 (dense) to miss (hybrid). BM25 added noise: "agent" and
  "coding agent" are everywhere in the corpus.
- "how does Cloudwalk use Codex day to day?" — BM25 didn't boost the rare token
  "Cloudwalk" enough to overcome Peter's many "codex" matches.

Plus one near-miss kept hitting rank 6–7:
- "where should hosted shell agents write their artifacts?" — `/mnt/data` is in
  the right chunk but the chunk is dominated by other tips.

## Phase 5b (retrieval improvements)

Each change is a separate experiment; keep what improves the eval baseline.

1. ~~Hybrid search (dense + BM25/sparse + RRF fusion in Qdrant)~~ **[done]** —
   +0.140 Recall@5, +0.125 MRR. Kept.
2. Cross-encoder rerank (Cohere `rerank-3.5`, top 30 → top 6) **[next]** —
   target: the 2 remaining misses and the rank 6–7 near-misses.
3. Structural chunking (split on `##`/`###`, then size-bound) — invalidates
   existing gold chunk_ids; do after rerank.
4. Contextual chunk headers (`[Title] > [Section]` prepended).
5. Image captioning (VLM caption webp/png at ingest, inject before chunking).
6. Content-hash dedup (skip unchanged articles on re-ingest).

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
