# engineer-rag

Ask your favorite engineering blogs questions, and get grounded answers
back, with citations to the exact paragraph each claim came from.

## Why this exists

I read a lot of engineering blogs (Anthropic, OpenAI, Netflix,Langchain,ManusAI, papers, my
own notes) and forget most of them. Generic chatbots hallucinate when I
ask about specifics. Bookmarks rot.

So I built a small RAG system over a corpus I curate by hand. The point
is one thing: answering technical questions with citations I can actually
trust.

It's also where I'm learning the parts of RAG that matter, chunking,
retrieval quality, evaluation, by building them from scratch instead of
using LangChain.

## Screenshot

![engineer-rag answering a question with cited sources from multiple articles](assets/demo_question1.png)

## What it does

- Reads Markdown articles from `data/articles/`; images can sit next to them
  for a later captioning phase.
- Chunks the text, embeds it (OpenAI dense + BM25 sparse), and stores it in Qdrant.
- Retrieves with hybrid search (dense + BM25, RRF fusion) and optional
  Voyage cross-encoder reranking.
- Answers your questions in a Streamlit chat. Answers are expected to cite
  source chunks, with links back to the original articles.
- Refuses to answer when the corpus doesn't actually cover the question.

## What it doesn't do (yet)

- No image understanding. Diagrams in articles are ignored at ingest time
  (they'll be captioned by a vision model later).
- Generation quality is measured at the claim level (Claude as judge), but the
  parser still loses some uncited / orphan-marker sentences — graded denominator
  is smaller than total claims. Numbers are honest, not yet exhaustive.
- No persistent chat history. Refreshing the page resets the conversation.
- No web crawler. Articles are curated by hand, not pulled from URLs.

## Quick start

### Prerequisites

You'll need:

- **Python 3.12+**: [python.org/downloads](https://www.python.org/downloads/)
- **uv** (Python package manager): [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/)
- **Docker** (for Qdrant): [docker.com/get-started](https://www.docker.com/get-started/)
- An **OpenAI API key**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- (Optional) A **Voyage AI API key** for cross-encoder reranking:
  [voyageai.com](https://www.voyageai.com/) — 200M tokens free; pipeline
  falls back to hybrid-only if unset.

### Run it

```powershell
# 1. Set your API key
copy .env.example .env        # Windows (PowerShell). macOS / Linux: cp .env.example .env
# then open .env and paste your OPENAI_API_KEY

# 2. Install dependencies
uv sync

# 3. Start the vector database
docker compose up -d qdrant

# 4. Ingest the demo corpus (synthetic articles committed in data/articles_demo/)
uv run python -m scripts.ingest

#    ...or use your own articles: drop them in data/articles/
#    (see "Adding a new article" below) and switch the profile
uv run python -m scripts.ingest --private

# 5. Open the chat UI
uv run streamlit run apps/ui_streamlit/src/ui_streamlit/app.py
```

The UI opens at **http://localhost:8501**. Ask a question; you'll get an
answer with `[1]`, `[2]` citations and clickable source cards.

Prefer the command line?

```powershell
uv run python -m scripts.query "what is context rot?"
```

## Demo corpus vs your corpus

The repo works with two corpora, selected by `CORPUS_PROFILE` in `.env` or a
`--demo` / `--private` flag on any script:

|                   | Demo (default)                               | Private                              |
| ----------------- | -------------------------------------------- | ------------------------------------ |
| Articles          | `data/articles_demo/` (committed, synthetic) | `data/articles/` (yours, gitignored) |
| Qdrant collection | `articles_demo`                              | `articles`                           |
| Gold set          | `data/eval/demo-gold.jsonl`                  | `data/eval/private-gold.jsonl`       |

The profile picks all three **together**, so an eval can never accidentally
run against the wrong corpus. The demo corpus is synthetic — fictional
companies, original writing — so it can be committed without copyright
issues, and its gold set makes both evals reproducible on any machine:

```powershell
uv run python -m scripts.eval                 # demo corpus (default)
uv run python -m scripts.eval --private      # your corpus
```

> **Status:** the demo articles are currently being written; until they land,
> the demo corpus ingests zero documents.

## Adding a new article

Articles you add are your **private corpus**: they live in `data/articles/`,
stay local (gitignored), and are used when you run with `--private` or
`CORPUS_PROFILE=private`.

### The one rule

Any file named exactly `index.md`, anywhere under `data/articles/`, gets
ingested. The folder structure is your choice. Organize by company, topic,
year, whatever fits.

| Path                                               | Ingested?                 |
| -------------------------------------------------- | ------------------------- |
| `data/articles/my-note/index.md`                   | yes                       |
| `data/articles/companies/anthropic/post1/index.md` | yes                       |
| `data/articles/papers/attention/index.md`          | yes                       |
| `data/articles/personal/2026/journal/index.md`     | yes                       |
| `data/articles/random/deeply/nested/path/index.md` | yes                       |
| `data/articles/foo.md`                             | no (not named `index.md`) |
| `data/articles/notes.txt`                          | no (not markdown)         |
| `data/articles/INDEX.md`                           | no (case matters)         |

### Format

Drop a folder, an `index.md`, and any images right next to it:

```
data/articles/my-notes/llm-debugging/
├── index.md
├── diagram-1.webp
└── diagram-2.png
```

Add YAML frontmatter at the top of `index.md`:

```markdown
---
title: LLM debugging tips
source_url: https://example.com/post # optional
authors: [Author Name] # optional
published_at: 2026-05-11 # optional
topics: [llm, debugging] # optional
company: openai # optional
---

# LLM debugging tips

Article body here...
```

Only `title` is recommended, and even that falls back to the folder name if
you skip it.

### Then re-run ingest

```powershell
uv run python -m scripts.ingest --private
```

The script walks `data/articles/`, finds every `index.md`, chunks it, embeds
it, and stores it in Qdrant. Re-running is safe — existing chunks are
replaced (idempotent).

## Architecture in 30 seconds

- **Folder-based ingest, not a crawler.** The corpus is something I tend by
  hand. Quality of the source set matters more than its size.
- **`packages/rag_core/` is the brain.** All the real logic (ingest,
  retrieval, generation, citations) lives there. Everything in `apps/`
  (Streamlit today, FastAPI + Next.js later) is a thin wrapper that calls
  into `rag_core`.

## Status & roadmap

The project is built phase by phase. For what's done, what's next, and
what's intentionally not built yet, see
[`docs/PROGRESS.md`](docs/PROGRESS.md).
