# data/articles/

Your corpus lives here. The ingest pipeline walks this folder, finds every
`index.md`, and turns each one into a retrievable article.

## Example

```
data/articles/
├── my-notes/llm-debugging/
│   ├── index.md
│   └── diagram-1.webp
└── papers/attention/
    └── index.md
```

## Rules

- Any file named **exactly `index.md`** (lowercase), at any depth under
  `data/articles/`, gets ingested.
- The folder taxonomy is your choice — organize by company, topic, year,
  whatever fits.
- One `index.md` per folder = one article.
- Images (`*.webp`, `*.png`) sit next to `index.md` and are co-located with
  the article.

## Frontmatter

Optional YAML frontmatter at the top of `index.md`:

```markdown
---
title: LLM debugging tips
source_url: https://example.com/post
authors: [Author Name]
published_at: 2026-05-11
topics: [llm, debugging]
company: openai
---

# LLM debugging tips

Article body here...
```

Only `title` is recommended. If you skip it, the folder name is used.

See the project [README](../../README.md) for full ingest commands and the
"Adding a new article" walkthrough.
