---
title: "What hybrid retrieval fixed in Threadline"
authors: [Corelight Labs Engineering]
published_at: 2025-07-15
topics: [rag, retrieval, search]
company: corelight-labs
fictional: true
---

# What hybrid retrieval fixed in Threadline

Threadline launched internally with dense vector search because our early
questions were semantic: engineers asked for concepts in words different from
the source documents. Dense retrieval handled those cases well, but it failed
on the identifiers that dominate real engineering work. Incident IDs, feature
flags, error codes, and configuration keys are not concepts to paraphrase.
They are strings that need to match.

## The failure pattern

In our first month, 38% of failed searches contained at least one identifier
such as `PAY-1842`, `cache_fill_v3`, or `E_CONN_DRAIN`. Dense search often
returned a document about the right subsystem while missing the page that
contained the exact identifier. A query for `E_CONN_DRAIN` retrieved three
general connection-pooling guides before the incident review where the code
was defined.

The reverse failure also appeared. Engineers asked "why do workers pause
before retrying?" while the runbook used the phrase "exponential backoff with
jitter." Lexical search matched `retrying` in unrelated pages and missed the
runbook. Neither retriever was broken; each preserved a different kind of
evidence.

## The evaluation baseline

We assembled 1,600 questions from search logs and document-owner interviews.
Six hundred were identifier-heavy, 700 were semantic paraphrases, and 300
mixed both. Dense-only retrieval reached Recall@5 of 0.78 overall, with 0.62
on identifiers and 0.89 on paraphrases. BM25 reached 0.74 overall, reversing
the shape: 0.91 on identifiers and 0.61 on paraphrases.

We also tracked mean reciprocal rank because a correct result at position five
is less useful than one at position one. Dense-only MRR was 0.59 and BM25 was
0.56. Both systems had enough signal to retrieve many answers, but neither
consistently placed the best chunk first.

## Combining candidate lists

Threadline now retrieves 30 dense candidates and 30 lexical candidates, then
combines them with reciprocal rank fusion. We chose RRF after testing weighted
score addition, because dense similarity and BM25 scores changed scale across
collections. RRF uses rank rather than raw score, so a collection with longer
documents does not silently alter the balance.

Hybrid retrieval raised overall Recall@5 to 0.91 and MRR to 0.72. Identifier
Recall@5 reached 0.94, while semantic paraphrases held at 0.90. The mixed slice
improved most, from 0.69 under dense-only to 0.93, because an exact subsystem
name could enter through BM25 while the surrounding intent entered through
the vector retriever.

## Why we still rerank

Fusion improves candidate coverage, not final ordering. The top results often
include a lexical exact match that merely mentions an identifier and a dense
match that explains the surrounding system. We pass the fused top 30 through
a cross-encoder reranker and return the best eight chunks. That step raised
MRR from 0.72 to 0.83 while leaving Recall@5 at 0.91.

Reranking adds 118 ms at p95, taking the full retrieval path from 204 to
322 ms. We accepted the cost because Threadline answers usually spend 1.6 to
3.4 seconds in generation. More importantly, the reranker reduced cases where
an exact but incidental mention displaced the paragraph that answered the
question.

## Field weighting matters

Our lexical index separates body text, heading path, document title, and
identifiers extracted by a conservative pattern matcher. Exact identifier
matches receive three times the body-text weight, while headings receive 1.5
times. Without that distinction, common handbook titles dominated BM25 and
short code strings were diluted by long paragraphs.

We do not extract arbitrary uppercase words as identifiers. The matcher
requires known forms such as ticket prefixes, underscore-separated config
keys, or error-code namespaces. An early broad matcher classified words like
`MUST` and `HTTP` as identifiers and lowered the identifier slice by four
points through noisy matches.

## Queries are not rewritten by default

We tested model-based query rewriting before retrieval. It helped terse
questions such as "drain issue" but sometimes expanded exact identifiers into
plausible, nonexistent phrases. In 19 of 500 identifier queries, the rewritten
version omitted or changed the string the engineer had typed. Those failures
were hard to notice because the rewritten query still sounded reasonable.

Threadline therefore searches the original query. A rewrite is generated only
when the first retrieval pass has no result above a conservative relevance
floor, and both original and rewritten queries contribute candidates. This
fallback activates on 4.6% of searches and is logged visibly in the retrieval
trace.

## The operational lesson

Hybrid search adds moving parts: two indexes, fusion, field weights, and a
reranker. We keep it understandable by exposing each stage in Threadline's
debug view. An engineer can see whether a chunk entered through dense search,
BM25, or both, its rank in each list, its fused position, and its final
reranker score.

The important lesson was not that hybrid retrieval always wins. It was that
our corpus contains two languages at once: human explanations and machine
identifiers. Dense search understands the first, lexical search protects the
second, and measured fusion lets Threadline serve engineers without pretending
one representation captures both perfectly.
