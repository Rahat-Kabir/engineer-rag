# engineer-rag — experiments & eval results

**All eval numbers live in this file.** `docs/PROGRESS.md` (phase status) and
`README.md` (curated snapshot) point here and must be re-synced when a
baseline moves — never edited independently. Every retrieval or generation
change is an experiment: measured against a gold set, kept only if the
baseline improves, recorded here either way.

## How to run

```powershell
uv run python -m scripts.eval                        # retrieval + refusal (demo corpus, default)
uv run python -m scripts.eval --private              # same, private corpus
uv run python -m scripts.eval_faithfulness           # per-claim grounding judge (demo)
uv run python -m scripts.eval_faithfulness --private # same, private corpus
```

Two corpora (see PROGRESS.md → Corpora): **demo** (committed, synthetic,
default — anyone can reproduce its numbers) and **private** (local only).
Each pairs its own gold set with its own Qdrant collection.

### Metrics

- **Recall@k** — share of questions whose expected chunk appears in the top k.
- **MRR** — mean reciprocal rank of the first expected chunk.
- **Refusal-correct** — share of should-refuse questions answered with zero
  citations. Note: borderline cases flip between runs due to embedding
  non-determinism; treat single-run deltas under ~3% as noise.
- **Faithfulness** — Claude (cross-family judge) grades each parsed cited
  claim as supported / partial / unsupported against its cited chunks.
  Coverage caveat: only parseable cited sentences are graded; uncited
  sentences and marker-only lines are counted separately and reduce the
  effective denominator.

## Current baselines

### Demo corpus (2026-07-16, post answer-contract experiment)

11 articles / 33 chunks, `demo-gold.jsonl` (39 questions), collection
`articles_demo`. Retrieval saturating at 33 chunks is expected — the demo
corpus exists for reproducibility, not headroom.

```
Recall@5:        1.000  (35/35)
Recall@10:       1.000  (35/35)
MRR:             0.971  (33 of 35 at rank 1)
Refusal-correct: 0.750  (3/4)

Faithfulness (47 graded claims):
  Supported 91.5% · Partial 8.5% · Unsupported 0
  Fully grounded answers 26/30 · parsed-as-refusal 5
  Uncited 32 · parse-skipped 29  (coverage ~43%)
```

### Private corpus (2026-07-16, post answer-contract experiment)

10 articles / 74 chunks, `private-gold.jsonl` (54 questions), collection
`articles`.

```
Recall@5:        0.980  (49/50)
Recall@10:       0.980  (49/50)
MRR:             0.919
Refusal-correct: 1.000  (4/4)

Faithfulness (83 graded claims):
  Supported 63.9% · Partial 30.1% · Unsupported 6.0% (5 claims)
  Fully grounded answers 26/48 · parsed-as-refusal 2
  Uncited 34 · parse-skipped 29  (coverage ~57%)
```

Remaining retrieval miss (private, unchanged since 5b.2): "how does
Cloudwalk use Codex day to day?" — `ai-native-engineering-team#4` and `#5`
are semantically near-duplicates; Voyage ranks #4 above the chunk that
actually mentions Cloudwalk (#5). Diagnosis: chunker boundary ambiguity.
Target of the contextual-chunk-headers experiment (5b.3).

### Open issues, in priority order

1. **Wrong-source citations on synthesis sentences** — 5 unsupported and
   most partials on private. Top generation target
   (citation-attribution experiment).
2. **One refusal-bait failure left** — "how much does Relay charge?";
   in-corpus dollar figures lure an answer.
3. **Coverage still ~50%** — parse-skipped ≈29 per corpus (marker-only
   lines persist despite the answer contract).

## Experiment log (chronological)

### 5a — Dense-only baseline (2026-05-17)

Private corpus, 50 retrieval questions. The starting point every later
experiment is measured against:

```
Recall@5: 0.780    Recall@10: 0.860    MRR: 0.630
```

### 5b.1 — Hybrid search (2026-05-18) — kept

Dense-only → dense + BM25 sparse, fused with RRF in Qdrant (top 30).

```
Recall@5: 0.780 → 0.920    Recall@10: 0.860 → 0.960    MRR: 0.630 → 0.755
```

**+0.140 Recall@5, +0.125 MRR.** Kept.

### 5b.2 — Voyage cross-encoder rerank (2026-05-18) — kept

Hybrid top 30 → `rerank-2.5` → top N.

```
Recall@5: 0.920 → 0.980    Recall@10: 0.960 → 0.980    MRR: 0.755 → 0.919
```

**+0.060 Recall@5, +0.164 MRR.** Cumulative lift over dense-only:
**+0.200 Recall@5, +0.289 MRR.** ~44 of 50 questions hit at rank 1. Kept.

| Stage | Recall@5 | Recall@10 | MRR |
|---|---|---|---|
| Dense-only (5a baseline) | 0.780 | 0.860 | 0.630 |
| + Hybrid (5b.1)          | 0.920 | 0.960 | 0.755 |
| + Voyage rerank (5b.2)   | **0.980** | **0.980** | **0.919** |

### 5c — Faithfulness baseline (2026-05-18)

**Private corpus** — same 50 retrieval gold questions, judged per-claim by
Claude (`claude-sonnet-4-6`). Answer prompt tightened to require inline
citations and forbid uncited factual sentences.

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

Two real hallucinations caught — both wrong-citation cases (claim
attributed to wrong source chunk). Exactly the class of bug this eval was
built to surface.

### Demo corpus baseline (2026-07-16)

First eval of the committed demo corpus (11 synthetic articles with
engineered traps; see PROGRESS.md → Corpora). Pipeline identical to
private: hybrid + Voyage rerank.

```
Recall@5:        1.000  (35/35)
Recall@10:       1.000  (35/35)
MRR:             0.971  (33 of 35 at rank 1)
Refusal-correct: 0.250  (1/4)
```

The refusal number was the honest finding: all three refusal-*bait*
questions (topics the corpus mentions but never explains, e.g. Ferrostack's
"Forgeglass" pipeline) were answered with citations instead of the refusal
sentence. The answer prompt resisted out-of-domain questions but not
near-topic ones. Fixed by the answer-contract experiment below.

A demo faithfulness run the same day exposed the second problem: only 35
claims graded out of ~128 candidate lines (~27% coverage), with 10 of 35
answerable questions parsed as refusals — the claim parser and the model's
citation formatting, not faithfulness itself, were the bottleneck.

### Answer-contract experiment (2026-07-16) — kept

Two findings converged on one root cause: the demo refusal-bait failures
(1/4) and the faithfulness eval's weak coverage (~27% of demo answer text
graded) were both under-specification in the answer prompt.
`prompts/answer.md` was rewritten as a strict output contract: every
sentence and bullet ends with its own `[N]` on the same line (including
list lead-ins), no orphan markers, the exact refusal sentence, and
"mentioning is not answering" (refuse when sources name a topic but do not
answer the actual question).

Demo corpus, before → after:

```
Refusal-correct:            1/4   → 3/4    (Forgeglass + context-rot bait now refuse)
Graded claims:              35    → 47     (coverage ~27% → ~43% of answer lines)
Supported:                  82.9% → 91.5%
Unsupported:                0     → 0
Fully grounded answers:     19/25 → 26/30
Answers parsed as refusals: 10    → 5
Retrieval:                  unchanged (1.000 / MRR 0.971)
```

Private corpus, before → after:

```
Retrieval + refusal:        unchanged (0.980 / MRR 0.919 / refusal 4/4)
Graded claims:              66    → 83     (coverage ~47% → ~57%)
Answers parsed as refusals: 7     → 2
Supported:                  78.8% → 63.9%
Partial:                    18.2% → 30.1%
Unsupported:                3.0% (2) → 6.0% (5)
Fully grounded answers:     30/43 → 26/48
```

Reading the private numbers honestly: the supported rate did not drop
because generation got worse — the contract forces more of each answer to
be cited and parseable, so the judge now grades sentences that previously
escaped grading. The old 78.8% was measured on the easiest, cleanest-cited
slice of the answers. The newly visible failures are mostly the
wrong-source-citation class (a true fact attributed to the wrong chunk,
usually on synthesis sentences combining two sources) — the same class as
the two 5c baseline hallucinations. Kept because the demo improved on every
axis, private coverage and parse-refusals improved, and per-claim rates are
now measured over more of what the model actually says.
