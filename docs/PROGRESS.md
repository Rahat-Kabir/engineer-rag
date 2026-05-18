# engineer-rag — progress

_Last updated: 2026-05-18_

## What's working today

End-to-end RAG over a curated corpus, queryable from a Streamlit chat UI:

```
data/articles/**/index.md
   → loader (frontmatter + body)
   → paragraph chunker (≤500 / ≥80 tokens, image refs stripped)
   → OpenAI embedding (text-embedding-3-small, 1536d) + BM25 sparse (fastembed)
   → Qdrant upsert with named vectors {dense, bm25} (deterministic UUID5 ids)
   → hybrid search: dense + sparse, fused with RRF in Qdrant (top 30)
   → Voyage cross-encoder rerank (rerank-2.5) → top N
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
| 5b.2 | Cross-encoder rerank (Voyage rerank-2.5) | [done] |
| 5c | Faithfulness eval (Claude as judge, per-claim grading) | [done] |
| 6 | FastAPI + Dockerfiles + SQLite for chat history & feedback | later |
| 7 | Next.js + shadcn UI | later |

## Stack (locked)

- Python 3.13 (`>=3.12`), uv workspace
- Qdrant 1.18 (Docker, single container), named vectors `dense` + `bm25`
- OpenAI `text-embedding-3-small` (1536d, cosine) for dense
- `fastembed` with `Qdrant/bm25` for sparse (IDF computed server-side by Qdrant)
- Voyage `rerank-2.5` as cross-encoder reranker (optional; falls back to hybrid-only if `VOYAGE_API_KEY` unset)
- Claude (`claude-opus-4-7` default, `claude-sonnet-4-6` cheaper) as faithfulness judge — cross-family to avoid same-model bias
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
│   ├── retrieval/            # search (hybrid + Voyage rerank), rerank
│   ├── eval/                 # gold loader, retrieval metrics, faithfulness
│   ├── generation/           # answer, validator, prompts/answer.md
│   ├── eval/                 # gold loader, recall@k, MRR
│   └── storage/              # qdrant
├── apps/ui_streamlit/src/ui_streamlit/app.py
├── scripts/                  # ingest.py, query.py, eval.py, eval_faithfulness.py, inspect.py
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
- Retrieval is **hybrid + cross-encoder rerank** (Voyage `rerank-2.5`, top 30 → top N). Falls back to hybrid-only if `VOYAGE_API_KEY` is unset.
- No persistence: Streamlit chat history resets on refresh.
- No streaming. Answers appear after full LLM response.
- Hallucinated `[N]` citations are filtered out of the displayed sources but the answer text isn't rewritten.
- **Refusal eval is flaky.** OpenAI embeddings have small non-determinism; borderline refusal cases flip between runs. Treat single-run deltas <3% as noise.
- **Faithfulness eval has parser noise.** ~30% of LLM-formatted lines are either marker-only orphans or uncited sentences. These are surfaced separately (`parse_skipped`, `uncited`) so they don't pollute the hallucination rate, but they reduce the effective denominator (graded claims ≈ 66 / ~85 candidates).

## Baseline — current (Phase 5b.2 hybrid + Voyage rerank, 2026-05-18)

54 gold questions across 10 articles (50 retrieval + 4 refusal). Pipeline:
dense (OpenAI) + BM25 sparse (fastembed) → RRF (top 30) → Voyage `rerank-2.5`
→ top N.

```
Recall@5:        0.980  (49/50)
Recall@10:       0.980  (49/50)
MRR:             0.919
Refusal-correct: 1.000  (4/4)
```

~44 of 50 questions now hit at rank 1.

### Phase progression (same corpus + gold set, 2026-05-17 → 2026-05-18)

| Stage | Recall@5 | Recall@10 | MRR |
|---|---|---|---|
| Dense-only (5a baseline) | 0.780 | 0.860 | 0.630 |
| + Hybrid (5b.1)          | 0.920 | 0.960 | 0.755 |
| + Voyage rerank (5b.2)   | **0.980** | **0.980** | **0.919** |

5b.2 lift over 5b.1: **+0.060 Recall@5, +0.164 MRR**. Cumulative lift over
dense-only baseline: **+0.200 Recall@5, +0.289 MRR**.

### Soft spots (remaining miss)

Only 1 retrieval miss left:

- "how does Cloudwalk use Codex day to day?" — rerank picked the wrong sibling
  chunk. `ai-native-engineering-team#4` and `#5` are semantically near-duplicates;
  Voyage ranked #4 above the chunk that actually mentions Cloudwalk (#5).
  Diagnosis: chunker boundary ambiguity.

## Faithfulness baseline (Phase 5c, 2026-05-18)

Same 50 retrieval gold questions, judged per-claim by Claude (`claude-sonnet-4-6`).
Answer prompt tightened to require inline citations and forbid uncited factual
sentences.

```
Per-claim (N = 66 graded claims):
  Supported:    0.788  (52 / 66)
  Partial:      0.182  (12 / 66)
  Unsupported:  0.030  (2 / 66)    ← hallucination rate

Per-answer (N = 43 answered, 7 produced no gradable claims):
  Fully grounded:     0.698  (30 / 43)
  Has hallucination:  0.047  (2 / 43)

Parser quality:
  Parse-skipped:  28   (orphan citation markers — fixed in code; LLM still produces some)
  Uncited:        46   (sentences with no [N] marker — flagged, not graded)
```

Two real hallucinations caught — both wrong-citation cases (claim attributed to
wrong source chunk). Exactly the class of bug this eval was built to surface.

## Phase 5b (retrieval improvements)

Each change is a separate experiment; keep what improves the eval baseline.

1. ~~Hybrid search (dense + BM25/sparse + RRF fusion in Qdrant)~~ **[done]** —
   +0.140 Recall@5, +0.125 MRR. Kept.
2. ~~Cross-encoder rerank (Voyage `rerank-2.5`, top 30 → top N)~~ **[done]** —
   +0.060 Recall@5, +0.164 MRR. Kept.
3. Contextual chunk headers (`[Title] > [Section]` prepended).
4. Image captioning (VLM caption webp/png at ingest, inject before chunking).
5. Content-hash dedup (skip unchanged articles on re-ingest).

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
