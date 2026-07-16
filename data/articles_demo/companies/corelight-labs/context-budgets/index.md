---
title: "How Threadline spends a context budget"
authors: [Corelight Labs Engineering]
published_at: 2025-10-06
topics: [rag, context, generation]
company: corelight-labs
fictional: true
---

# How Threadline spends a context budget

Retrieval does not end when Threadline has ranked eight chunks. Those chunks
must share a finite context window with instructions, conversation history,
the user's question, and room for the answer. Sending everything that might be
useful sounds safe, but it made answers slower and less grounded in our tests.
Threadline now treats context as a budget allocated among explicit categories.

## The 16,000-token envelope

Our production answer path uses a 16,000-token working envelope even when the
selected model supports more. We reserve 1,200 tokens for system and citation
instructions, 1,000 for the answer, and 800 for the current question plus
formatting. The remaining 13,000 tokens are available to conversation history
and retrieved evidence, but evidence always receives at least 7,000.

The envelope is a latency and attention decision, not a provider limit. In a
900-question experiment, expanding from 16,000 to 32,000 tokens increased
median generation latency by 38% and improved answer completeness by only 1.2
percentage points. Unsupported claims rose from 3.1% to 4.4%, mostly when
lower-ranked chunks introduced adjacent but irrelevant facts.

## Evidence is allocated first

Threadline walks reranked chunks in order and admits each whole chunk while
the evidence allocation remains. It does not truncate a chunk in the middle
of a paragraph. The first 7,000 tokens are protected for evidence, and the
allocator may grow evidence to 11,000 by borrowing unused history space.

We also enforce document diversity after the first three chunks. No document
may occupy more than 45% of the evidence tokens unless every remaining
candidate falls below the reranker floor of 0.18. This prevented long runbooks
from crowding out a short architecture record that directly answered a
"why" question.

## History is summarized by turns

Conversation history receives at most 5,000 tokens and is selected from newest
to oldest. The latest two user-assistant turns are kept verbatim. Older turns
are represented by a rolling summary capped at 1,200 tokens, plus any prior
question explicitly referenced by phrases such as "that second option" or
"the earlier incident."

We regenerate the rolling summary every four turns rather than after every
message. In a 120-conversation test, per-turn summarization cost 27% more and
changed no judged answer outcome. Waiting longer than six turns caused the
summary to omit named constraints in 9% of conversations, so four became the
operational compromise.

## Neighbor chunks are conditional

A retrieved chunk can request one neighbor when its text ends with an
unfinished list, a forward reference, or a heading with fewer than 120 tokens
below it. Neighbor expansion occurs before final budget allocation and carries
a 0.85 score multiplier, so a neighbor cannot automatically outrank an
independently retrieved chunk. Threadline expands neighbors on 7.3% of queries.

This policy recovered important qualifications in architecture records without
reintroducing universal overlap. It added an average of 410 tokens on expanded
queries and improved citation completeness by 6 percentage points on the
qualification slice. Blindly adding both neighbors consumed 1,100 tokens on
average and produced no additional gain.

## Conflicts are retained, not resolved

When two high-ranked chunks disagree, the allocator keeps both if each clears
the relevance floor. Threadline marks their metadata with document dates and
instructs the answerer to describe the disagreement rather than silently pick
one. A newer document receives no automatic authority unless the older one is
explicitly marked superseded.

We introduced this after an operational guide and an architecture record gave
different retry limits: three attempts versus five. The answerer previously
selected whichever chunk appeared first. Preserving both added 520 tokens but
turned a confident wrong answer into a cited statement that the sources were
inconsistent.

## What gets dropped

The allocator drops low-ranked evidence before it compresses high-ranked
evidence. It then removes old verbatim history, then shortens the rolling
summary. System instructions, the current question, and answer space are
fixed. If fewer than 600 evidence tokens survive, Threadline refuses to
generate and returns the retrieval results for manual inspection.

That refusal condition fires on 0.8% of production questions, usually after a
user pastes a large log into the question. We considered truncating the user
input automatically, but that can remove the exact error line the user expects
Threadline to investigate. The UI instead asks the user to narrow the pasted
material.

## The budget trace

Every answer stores a budget trace: tokens requested, tokens admitted by
category, chunks rejected for space, neighbor expansions, and any history
summary used. The trace is visible in Threadline's debug panel and has become
one of our most useful support tools. When an answer misses a source, we can
distinguish "retrieval never found it" from "the allocator found it but spent
the budget elsewhere."

Our current median allocation is 7,800 evidence tokens, 2,300 history tokens,
1,050 instruction tokens, and 760 answer tokens. Those numbers move by query,
but the priorities do not: preserve the user's present question, protect
enough evidence to justify the answer, and treat old conversation as useful
only while it does not displace stronger sources.

## Context is a policy surface

Context-window size is a model capability; context budgeting is a product
policy. Threadline's allocator encodes what we value when useful information
competes: evidence over old conversation, complete paragraphs over arbitrary
truncation, and visible disagreement over convenient synthesis.

The policy will change as models and corpora change, which is why every
allocation rule has an evaluation slice and a trace. More context is not free
certainty. It is another resource whose contents should be selected,
measured, and explainable.
