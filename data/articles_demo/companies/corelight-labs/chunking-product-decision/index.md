---
title: "Why Threadline chunks by paragraphs, not pages"
authors: [Corelight Labs Engineering]
published_at: 2025-04-22
topics: [rag, chunking, retrieval]
company: corelight-labs
fictional: true
---

# Why Threadline chunks by paragraphs, not pages

Threadline is our retrieval product for engineering handbooks, incident
reviews, and architecture records. Its first prototype treated every imported
page as one chunk because that preserved document structure and made citations
easy to explain. It also produced poor retrieval: a six-page incident review
became one vector, and the paragraph describing the actual root cause competed
with timelines, acknowledgements, and remediation tables. We spent six weeks
testing smaller units before choosing paragraph-aware chunks.

## The page baseline

Our baseline corpus contained 18,400 documents and 2,100 evaluation questions.
Page chunks averaged 1,740 tokens, with the longest reaching 9,600 tokens after
PDF extraction collapsed page boundaries. Recall@5 was 0.71, and answerers
cited the correct page only 64% of the time. Latency was acceptable at 310 ms
p95 for retrieval, but the retrieved context routinely contained five times
more text than the answer required.

The failures were not limited to long documents. Architecture records often
put the decision in the first paragraph and rejected alternatives near the
end. A query about why a choice was rejected matched the page's dominant
decision language instead of the smaller alternatives section. The embedding
represented the page honestly; the page was simply the wrong retrieval unit.

## Experiment A: 480-token paragraph groups

The first successful experiment grouped adjacent paragraphs until the chunk
would exceed 480 tokens. Headings stayed attached to the first paragraph below
them, and paragraphs longer than the limit were split by sentence. On the
2,100-question set, this configuration raised Recall@5 from 0.71 to 0.84. The
largest gains came from postmortems, where root-cause paragraphs stopped
sharing a vector with the full incident timeline.

The 480-token version produced 93,000 chunks, 3.8 times the page baseline.
Indexing time rose from 19 to 44 minutes, but retrieval p95 moved only from
310 to 336 ms because Threadline still searched the same top-level collection.
Reviewers preferred its citations: 82% were judged narrow enough to verify
without opening the source document.

## Experiment B: 620-token paragraph groups

The second experiment used the same paragraph grouping but allowed 620 tokens
before opening a new chunk. It preserved short explanatory sequences that the
480-token version sometimes separated, especially a design claim followed by
its qualification. In a 300-question answer-quality review, unsupported
bridging statements fell from 14 cases to 8 because the model more often saw
the qualification beside the claim.

The 620-token version also reduced average generation input by 18% compared
with retrieving an equivalent number of 480-token chunks. Fewer adjacent
chunks were needed to recover a complete explanation, so Threadline sent
6,900 context tokens per answer instead of 8,400. Index size was 76,000
chunks, and retrieval p95 was 329 ms.

## The rule we shipped

We shipped a target of 620 tokens with a hard ceiling of 700 and a soft floor
of 90. Paragraphs accumulate in order until the next paragraph would cross the
target. A final fragment below 90 tokens merges backward unless that would
cross the hard ceiling; headings and fenced code blocks are never separated
from the first explanatory paragraph that follows them.

This rule is intentionally less elegant than fixed windows. It requires
Markdown and HTML structure to survive extraction, and it has special handling
for code blocks, tables, and one-line callouts. In return, the chunks resemble
units a writer intended readers to understand together. On the launch corpus,
the median chunk was 544 tokens and 92% fell between 250 and 700.

## Overlap was mostly a tax

We tested 10%, 20%, and 30% sliding overlap on top of paragraph groups.
Twenty-percent overlap improved Recall@5 by 0.6 percentage points but expanded
the index by 22% and caused duplicate citations in 17% of generated answers.
The reranker often placed two versions of the same paragraph beside each
other, consuming top-k slots without adding evidence.

Threadline therefore uses no default token overlap. Instead, it stores the
previous and next chunk IDs and may fetch one neighbor after retrieval when a
chunk ends with a colon, an unfinished list, or a forward reference such as
"the following constraints." Neighbor expansion fires on 7.3% of queries and
adds fewer duplicate candidates than universal overlap.

## Titles help, but only as metadata

We initially prepended the document title to every chunk before embedding.
That improved retrieval for documents with distinctive names but harmed
collections where hundreds of pages shared a handbook title. "Platform
Operations Manual" became the most repeated phrase in the index and weakened
the terms that distinguished one section from another.

The current representation stores title, heading path, and document type as
separate fields. Dense embeddings use the heading path plus chunk text, while
lexical search indexes all fields with different weights. This gave us the
title benefit without repeating a generic title inside every generated
citation.

## What this decision does not settle

Chunking is tied to the corpus and questions. Threadline's rule works for
technical prose with headings and medium-length paragraphs; it is not a
universal recommendation for legal contracts, chat logs, or source code. We
keep separate evaluation slices for postmortems, runbooks, architecture
records, and API guides because an aggregate metric can hide a format-specific
regression.

The lasting decision was not "620 tokens is correct." It was that chunks
should preserve authored units first and satisfy a token budget second. The
numbers gave us a practical boundary, but paragraph structure gave Threadline
a retrieval unit that engineers could inspect and citations they could trust.
