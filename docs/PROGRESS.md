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
| 4 | Tests for stable modules (33 pure-function unit tests) | [done] 2026-07-16 |
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
├── tests/                    # pure-function unit tests (chunker, citations, gold, metrics, parsing)
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
  (35 retrieval + 4 refusal). Baselines: see `EXPERIMENTS.md`.

The private corpus itself stays as before: curated by hand, local only
(see project `README.md` → "Adding a new article").

## Key decisions made

- **Folder-based ingest** (curated), not URL crawling.
- **One Dockerfile only when needed.** Currently zero (only Qdrant runs in Docker; app runs via `uv run`).
- **No LangChain / LlamaIndex.** Built from primitives.
- **SQLite (later) for chat/feedback**, not Postgres. Qdrant is the only DB right now.
- **Streamlit imports `rag_core` directly.** No API yet. FastAPI lands when Next.js starts.
- **Tests after stabilization.** Deferred until modules stopped changing;
  landed 2026-07-16 as 33 pure-function unit tests (`uv run pytest` — no
  API keys or Docker needed). CI deferred by choice.

## Known limitations

- Re-ingest re-embeds **every** chunk every run (no content-hash dedup yet). Cost is negligible (~$0.0001/run for current corpus), but won't scale.
- Chunker is paragraph-based, not heading-aware. Sections can leak across chunk boundaries. The tail-merge can also push the final chunk slightly over MAX_TOKENS (bounded by MIN_TOKENS − 1 extra; pinned by a unit test).
- Image references (`*.webp`, `*.png`) are silently stripped at chunk time. No VLM captioning yet.
- Retrieval is **hybrid + cross-encoder rerank** (Voyage `rerank-2.5`, top 30 → top N). Falls back to hybrid-only if `VOYAGE_API_KEY` is unset.
- No persistence: Streamlit chat history resets on refresh.
- No streaming. Answers appear after full LLM response.
- Hallucinated `[N]` citations are filtered out of the displayed sources but the answer text isn't rewritten.
- **Refusal eval is flaky.** OpenAI embeddings have small non-determinism; borderline refusal cases flip between runs. Treat single-run deltas <3% as noise.
- **Faithfulness eval has parser noise.** A large share of LLM-formatted lines are marker-only orphans or uncited sentences. These are surfaced separately (`parse_skipped`, `uncited`) so they don't pollute the hallucination rate, but they cap grading coverage at roughly half of answer text (current coverage per corpus: see `EXPERIMENTS.md`). One known mechanism: on prose lines over 200 chars, a marker placed after the sentence terminator ("Fact. [1]") attaches to the *next* sentence during splitting.

## Baselines & experiments

All eval numbers and the full experiment log (before/after, kept/reverted)
live in [`EXPERIMENTS.md`](EXPERIMENTS.md) — the single source of truth;
this file carries no copies. Current state in words: retrieval is saturated
on both corpora; the open issues are wrong-source citations on synthesis
sentences, one remaining refusal-bait failure, and claim-parser coverage.

## Phase 5b (retrieval improvements)

Each change is a separate experiment; keep what improves the eval baseline.

1. ~~Hybrid search (dense + BM25/sparse + RRF fusion in Qdrant)~~ **[done]** —
   kept (numbers in `EXPERIMENTS.md`).
2. ~~Cross-encoder rerank (Voyage `rerank-2.5`, top 30 → top N)~~ **[done]** —
   kept (numbers in `EXPERIMENTS.md`).
3. Contextual chunk headers (`[Title] > [Section]` prepended) — **next**;
   targets the one remaining miss.
4. Image captioning — **deferred**: corpus has only 2 images, nothing to
   measure. Revisit when image-heavy articles land.
5. Content-hash dedup — do when corpus growth makes re-ingest cost matter.

## Next up (updated 2026-07-16)

Project direction settled: **the repo is the product** — a reference
implementation of eval-driven RAG that anyone can clone, run, and reproduce.
Retrieval eval is saturated (one miss left), so the order is:

1. ~~Demo corpus content~~ **[done 2026-07-16]** — 11 articles, 39-question
   gold set, baseline recorded. "Clone and it works" is true.
2. ~~README rewrite~~ **[done 2026-07-16]** — identity-first, mermaid
   pipeline, measured results, reproducible demo numbers.
3. ~~Refusal prompt experiment~~ **[done 2026-07-16]** — grew into the
   answer-contract experiment (see `EXPERIMENTS.md`). Refusal 1/4 → 3/4,
   coverage up on both corpora. Kept.
4. **Citation-attribution experiment** — wrong-source citations on
   synthesis sentences are now the top generation issue (5 unsupported
   claims on private). Candidate ideas: per-fact citation guidance in the
   prompt, or a post-generation citation check.
5. **5b.3 contextual chunk headers** — measure against eval, keep or revert.
   Closes Phase 5b.
6. ~~Phase 4 tests~~ **[done 2026-07-16]** — 33 pure-function unit tests
   (written by Codex, audited). Two behavior findings recorded in Known
   limitations: chunker tail-merge overshoot, sentence-split marker
   migration. CI deferred by choice.
7. **Phase 6 (main arc)** — FastAPI (`POST /query` + SSE streaming) → SQLite
   chat history → feedback endpoint. Streamlit stays as debug UI. Unblocks
   Phase 7 (Next.js).
8. **Ongoing** — grow the private corpus and gold set together; that restores
   eval headroom and makes future retrieval ideas measurable again.

Deferred: image captioning (see above), further retrieval tuning (no
measurable headroom), claim-parser hardening (only after the prompt-side
fixes plateau, and only with an old-vs-new parser parallel run — changing
the parser changes the ruler).

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
