# engineer-rag — progress

_Last updated: 2026-07-16_

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
│   └── storage/              # qdrant
├── apps/ui_streamlit/src/ui_streamlit/app.py
├── scripts/                  # ingest.py, query.py, eval.py, eval_faithfulness.py, inspect.py
├── data/
│   ├── articles/             # private corpus (gitignored; only README in git)
│   ├── articles_demo/        # demo corpus (committed, synthetic; being written)
│   └── eval/                 # demo-gold.jsonl (growing) + private-gold.jsonl (54 questions)
├── docker-compose.yml        # qdrant only
├── pyproject.toml            # workspace root
└── .env / .env.example
```

## Corpora — two-profile system (2026-07-16)

The project direction is **repo-as-reference**: someone who clones it should
be able to ingest, query, and reproduce the eval numbers without bringing any
data. To make that possible without republishing copyrighted articles, there
are two corpora, selected by `CORPUS_PROFILE` (`.env`) or `--demo`/`--private`
on any script:

| | Demo (default) | Private |
|---|---|---|
| Articles | `data/articles_demo/` (committed, synthetic) | `data/articles/` (local, gitignored) |
| Qdrant collection | `articles_demo` | `articles` |
| Gold set | `data/eval/demo-gold.jsonl` | `data/eval/private-gold.jsonl` |

The profile derives all three together in `config.py`, so gold sets and
collections can never be mismatched. Demo is the built-in default so a fresh
clone works out of the box.

- **Wiring**: done (2026-07-16).
- **Demo corpus**: done (2026-07-16). 11 synthetic articles / 33 chunks across
  three fictional companies (Relay Systems, Corelight Labs, Ferrostack) and a
  fictional staff engineer's blog (Mira Chen), engineered with eval traps:
  multi-source facts split across documents, deliberate disagreements between
  articles, near-duplicate sibling sections (reranker stress), and refusal
  bait (topics mentioned but never explained). Demo gold set: 39 questions
  (35 retrieval + 4 refusal). Baseline below.

The private corpus itself stays as before: curated by hand, local only
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

## Demo corpus baseline (2026-07-16)

**Demo corpus** (11 articles / 33 chunks, `data/eval/demo-gold.jsonl` 39
questions, collection `articles_demo`). Pipeline: hybrid + Voyage rerank,
same as private. Reproducible by anyone: `scripts.ingest --demo` then
`scripts.eval --demo`.

```
Recall@5:        1.000  (35/35)
Recall@10:       1.000  (35/35)
MRR:             0.971  (33 of 35 at rank 1)
Refusal-correct: 0.250  (1/4)
```

The refusal number is the honest finding: all three refusal-*bait* questions
(topics the corpus mentions but never explains, e.g. Ferrostack's
"Forgeglass" pipeline) were answered with citations instead of the refusal
sentence. The answer prompt resists out-of-domain questions but not
near-topic ones. Targeted fix: a prompt experiment (generation change →
re-run faithfulness per Definition of Done). Retrieval saturating at 33
chunks is expected — the demo corpus is for reproducibility, not headroom.

## Baseline — current (Phase 5b.2 hybrid + Voyage rerank, 2026-05-18)

**Private corpus** (10 articles, `data/eval/private-gold.jsonl`, collection
`articles`). 54 gold questions (50 retrieval + 4 refusal). Pipeline:
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

**Private corpus** — same 50 retrieval gold questions
(`data/eval/private-gold.jsonl`), judged per-claim by Claude (`claude-sonnet-4-6`).
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
3. Contextual chunk headers (`[Title] > [Section]` prepended) — **next**;
   targets the one remaining miss.
4. Image captioning — **deferred**: corpus has only 2 images, nothing to
   measure. Revisit when image-heavy articles land.
5. Content-hash dedup — do when corpus growth makes re-ingest cost matter.

## Next up (updated 2026-07-16)

Project direction settled: **the repo is the product** — a reference
implementation of eval-driven RAG that anyone can clone, run, and reproduce.
Retrieval eval is saturated (Recall@5 0.980, one miss left), so the order is:

1. ~~Demo corpus content~~ **[done 2026-07-16]** — 11 articles, 39-question
   gold set, baseline recorded. "Clone and it works" is true.
2. **README rewrite** — reposition around the eval story (measured pipeline
   progression + reproducible demo numbers). Skeleton agreed.
3. **Refusal prompt experiment** — demo baseline exposed near-topic refusal
   failures (1/4). Generation change → re-run faithfulness per DoD.
4. **5b.3 contextual chunk headers** — measure against eval, keep or revert.
   Closes Phase 5b.
5. **Phase 4 tests** — modules are stable now. Pure functions first: chunker,
   citation validator, loader, eval metrics. Safety net before the Phase 6
   refactor.
6. **Phase 6 (main arc)** — FastAPI (`POST /query` + SSE streaming) → SQLite
   chat history → feedback endpoint. Streamlit stays as debug UI. Unblocks
   Phase 7 (Next.js).
7. **Ongoing** — grow the private corpus and gold set together; that restores
   eval headroom and makes future retrieval ideas measurable again.

Deferred: image captioning (see above), further retrieval tuning (no
measurable headroom), faithfulness prompt iteration (hard-hallucination
rate already ~3%; revisit the 46 uncited sentences later).

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
