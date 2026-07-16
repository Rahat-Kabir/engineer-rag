# engineer-rag — Agent Instructions

## Overview

Engineering RAG over a curated corpus of technical articles. Quality > scale:
folder-based ingest (`data/articles/**/index.md`), never a crawler — corpus
curation is the point. The pipeline (ingest → hybrid search → rerank → cited
answer) works end-to-end with an eval harness; the next arc is tests, then
FastAPI + persistence. `packages/rag_core/` is the brain; apps stay thin.

## Docs

- `docs/PROGRESS.md` — phase status, eval baselines, known limitations,
  next-up work. Read it before claiming "what's built" or "what's next";
  update it when a phase completes or a baseline moves.


## Architecture


- **Python**: 3.12+ (uv currently resolving 3.13). uv workspace.
- **Corpora**: two profiles via `CORPUS_PROFILE` env or `--demo`/`--private`
  script flags. `demo` (default): `data/articles_demo/` (committed,
  synthetic) → collection `articles_demo` → `data/eval/demo-gold.jsonl`.
  `private`: `data/articles/` (gitignored) → collection `articles` →
  `data/eval/private-gold.jsonl`. The profile derives all three together in
  `config.py` so they can never be mismatched.
- **Vectors**: Qdrant (Docker, single container). Named vectors `dense`
  (cosine, 1536d) + `bm25` (sparse, IDF computed server-side).
- **Embedder**: OpenAI `text-embedding-3-small` (dense) + `fastembed`
  `Qdrant/bm25` (sparse).
- **Reranker**: Voyage `rerank-2.5` (optional; off when `VOYAGE_API_KEY` is
  unset, retrieval falls back to hybrid-only).
- **Faithfulness judge**: Anthropic Claude (`claude-opus-4-7` default,
  `claude-sonnet-4-6` cheaper).
- **LLM**: configurable via `LLM_MODEL`; `config.py` defines the default and
  `.env` overrides it.
- **UI**: Streamlit imports `rag_core` directly (dev/debug UI). No HTTP API
  yet; FastAPI + Next.js land in Phases 6–7.
- **Persistence**: SQLite planned for chat/feedback (Phase 6). No Postgres.
- **Docker**: only Qdrant runs in Docker; the app runs via `uv run`. Zero
  Dockerfiles until one is needed.
- **Tests**: `tests/` doesn't exist yet.

### Key Decisions

- **No LangChain / LlamaIndex — built from primitives.** The point of the
  project is learning how RAG works inside.
- **Folder-based ingest, never a crawler.** Curation over scale; a crawler
  would change the quality model of the whole corpus.
- **Demo profile is the default.** A fresh clone must work out of the box
  ("the repo is the product"); the private corpus is opt-in via `.env`/flag.
- **Demo corpus is synthetic.** Original fiction (invented companies),
  engineered to exercise retrieval — never republished copyrighted articles.
- **Idempotent ingest.** Deterministic chunk IDs (`{doc_id}#{idx}`) and UUID5
  point IDs; re-ingest deletes + re-upserts, so it's safe to run anytime.
- **Cross-family faithfulness judge.** Claude grades GPT answers to avoid
  same-model bias.
- **Reranker optional by design.** Retrieval degrades gracefully to
  hybrid-only instead of failing when `VOYAGE_API_KEY` is unset.
- **SQLite (Phase 6), not Postgres.** Chat/feedback persistence doesn't need
  a server DB; Qdrant stays the only container.
- **Every retrieval change is an experiment.** Measured against the gold-set
  eval and kept only if the baseline improves (see Definition of Done).

## Key Files

Non-obvious files only — the tree itself is self-explanatory (Glob it).

| File | ~Lines | Purpose |
|---|---|---|
| `packages/rag_core/src/rag_core/config.py` | 60 | Every env knob (pydantic-settings over `.env`); corpus profile derives articles dir + collection + gold path |
| `packages/rag_core/src/rag_core/generation/prompts/answer.md` | 15 | Answer prompt, incl. citation + refusal rules |
| `packages/rag_core/src/rag_core/ingest/pipeline.py` | 30 | Ingest orchestrator: ensure → load → chunk → embed+sparse → upsert |
| `packages/rag_core/src/rag_core/retrieval/search.py` | 25 | Hybrid prefetch → RRF → optional Voyage rerank → top N |
| `packages/rag_core/src/rag_core/eval/faithfulness.py` | 325 | Per-claim grounding judge (Claude), parse/skip bookkeeping |
| `data/eval/private-gold.jsonl` | 54 items | Private-corpus gold questions `{question, expected_chunk_ids}`; empty list = refusal case. `demo-gold.jsonl` is the demo-corpus set (39 items incl. trap questions) |

## Commands

```powershell
docker compose up -d qdrant
uv sync
uv run python -m scripts.ingest
uv run python -m scripts.query "what is context rot?"
uv run streamlit run apps/ui_streamlit/src/ui_streamlit/app.py

# Eval and inspect
uv run python -m scripts.eval
uv run python -m scripts.eval_faithfulness
uv run python -m scripts.inspect docs
uv run python -m scripts.inspect chunks <doc_id>
uv run python -m scripts.inspect chunk  <chunk_id>
```

All scripts run against the **demo** corpus by default; add `--private`
(or set `CORPUS_PROFILE=private` in `.env`) to target the private corpus.

Ingest, query, both evals, and every Streamlit chat message hit paid APIs
(OpenAI; Voyage and Anthropic where configured) — the paid-call approval rule
applies. Only `inspect` and setup (`docker compose`, `uv sync`) are free.

## Conventions

- **uv workspace**: add a dep to a package with
  `uv add --package rag_core <pkg>` (or `--package ui_streamlit`); root deps
  with `uv add <pkg>`. Never edit `pyproject.toml` `dependencies` arrays by
  hand. After any `pyproject.toml` change: `uv sync`.
- **Corpus layout**: articles live at
  `<corpus root>/<taxonomy>/<slug>/index.md` (current private taxonomy:
  `companies/<company>/<slug>/`). Private root `data/articles/` is
  gitignored; demo root `data/articles_demo/` is committed.
- **Frontmatter**: `title`, `source_url`, `authors`, `published_at`, `topics`,
  `company` — all optional; a missing `title` falls back to the folder name.
- **Never invent metadata.** If `source_url` (or any field) wasn't provided by
  the user, leave it out of the frontmatter. Don't guess URLs from context.
- **Images** (`*.webp`, `*.png`) sit next to `index.md`; they're stripped at
  chunk time. Captioning is deferred until image-heavy articles land (see
  `docs/PROGRESS.md`).


## Definition of Done

- **Retrieval or chunking change**: re-run `uv run python -m scripts.eval`
  and record the numbers in `docs/PROGRESS.md`. Keep the change only if the
  baseline improves. Refusal deltas under ~3% between runs are
  embedding-nondeterminism noise, not signal.
- **Generation or prompt change**: additionally re-run
  `uv run python -m scripts.eval_faithfulness`.
- **New feature or behavior change**: prove it at the CLI (a script in
  `scripts/`) before wiring it into the UI.
- **Bug fix**: re-run whatever was broken and confirm it now works.
- **Docs and mechanical edits**: nothing to prove.

## Engineering Principles

- Simplicity. No overengineering, no "flexibility" that wasn't asked for.
- Surgical changes: touch only what's necessary; don't reformat adjacent code.
- Goal-driven: define verifiable success criteria, then make them pass.
- Fail fast: don't swallow exceptions; only catch with a specific recovery plan.
- Clean up orphans: removing code means removing its unused imports, tests,
  and dependencies too.

## Code Clarity

- Clear is better than clever. Do not write functionality in fewer lines if it
  makes the code harder to understand.
- Write more lines of code if additional lines improve readability and
  comprehension.
- Make things so clear that someone with zero context would completely
  understand the variable names, method names, what things do, and why they exist.
- When a variable or method name alone cannot fully explain something, add a
  comment explaining what is happening and why — in code you write or change.

## Do NOT

- Do not add features, refactor code, or make "improvements" beyond what was asked.
- Do not add docstrings, comments, or type annotations to code you did not change.
- Do not introduce new tech — library, framework, model, embedder, vector
  store, or provider — without asking first. The stack above is locked.
- Do not add a URL crawler. Ingest is folder-based, full stop.
- Do not invent article metadata (see Conventions).
- Do not write content into `CLAUDE.md` — it stays a one-line `@AGENTS.md`
  import pointer; this file is the source of truth.

## Self-Update

When you make changes to this project that affect the information in this
file, update this file to reflect those changes. Specifically:

- **New files**: add notable new source files to the Key Files table with
  their purpose and approximate line count.
- **Deleted files**: remove entries for files that no longer exist.
- **Architecture changes**: update the Architecture section if you introduce
  new patterns, frameworks, or significant structural changes.
- **Build changes**: update the Commands section if the build process changes.
- **New conventions**: if the user establishes a new coding convention during
  a session, add it to the appropriate conventions section.
- **Line count drift**: if a file's line count changes significantly
  (>50 lines), update the approximate count in the Key Files table.

Do NOT update this file for minor edits, bug fixes, or changes that don't
affect the documented architecture or conventions.
