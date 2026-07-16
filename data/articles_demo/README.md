# data/articles_demo/

The committed **demo corpus**: a small set of synthetic engineering articles
so a fresh clone can ingest, query, and run the evals without bringing any
data. This is the corpus every command uses by default (`CORPUS_PROFILE=demo`).

**Everything here is fiction.** The companies, people, products, and numbers
in these articles are invented for demo and eval purposes. They are original
works written for this repository (no real article is copied or paraphrased)
and are covered by the repository license.

Layout and frontmatter rules are identical to the private corpus — see
[data/articles/README.md](../articles/README.md).

The corpus: 11 articles across three fictional companies — **Relay Systems**
(fintech running an LLM agent in production), **Corelight Labs** (devtools,
builds the "Threadline" RAG product), **Ferrostack** (infrastructure) — plus
the personal blog of **Mira Chen**, a fictional staff engineer who disagrees
with all three. The articles carry deliberate eval traps: facts split across
documents (multi-source), explicit disagreements, near-duplicate sibling
sections, and topics mentioned but never explained (refusal bait). The demo
gold set (`data/eval/demo-gold.jsonl`) targets these traps.
