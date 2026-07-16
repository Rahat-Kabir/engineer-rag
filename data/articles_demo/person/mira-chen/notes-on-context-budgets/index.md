---
title: "Notes on Threadline's context budget"
authors: [Mira Chen]
published_at: 2026-02-09
topics: [rag, context, product-design]
fictional: true
---

# Notes on Threadline's context budget

Corelight Labs published "How Threadline spends a context budget," and it is
one of the better descriptions of context assembly I have seen. They use a
16,000-token working envelope, protect at least 7,000 tokens for evidence,
keep the latest two conversation turns verbatim, and expose a budget trace.
That is refreshingly concrete. I agree with the accounting and disagree with
two policies hiding inside it.

## Budgets are better than stuffing

The most important thing Corelight gets right is admitting that context
selection is a product decision. A model accepting 100,000 tokens does not
mean an application should send 100,000. Threadline measured a 38% latency
increase when expanding its working envelope from 16,000 to 32,000, for only
1.2 percentage points of completeness.

Their trace is equally important. Recording chunks rejected for space,
neighbor expansions, history tokens, and evidence tokens lets an engineer
separate retrieval failure from allocation failure. Every RAG system I review
has dashboards for retrieval latency; very few can explain why a retrieved
chunk did not reach the model.

## I would not reserve evidence by token count alone

Threadline protects 7,000 tokens for evidence and may grow that allocation to
11,000. This is understandable, but token volume is a poor proxy for
evidentiary value. One 180-token architecture decision can answer a question
more completely than five long runbook chunks.

I would reserve evidence slots by role before filling tokens: at least one
direct-answer chunk, one qualification or constraint chunk when available,
and one independent source for claims that cross documents. Only after those
roles are satisfied would I optimize the remaining token budget by rank.
This adds classification complexity, but it prevents a long top-ranked
document from consuming the budget while technically obeying the 45% document
cap.

## Rank scores are not confidence

Corelight admits chunks above a reranker floor of 0.18 and uses rank order to
spend the budget. A cross-encoder score is useful for ordering candidates, but
it is not calibrated evidence that a chunk supports the answer. Scores also
shift by query length, document style, and collection.

I would calibrate admission separately for question families. In a 500-query
sample, I would label direct support, useful context, and irrelevant retrieval,
then fit thresholds for identifier lookup, causal questions, comparisons, and
procedural questions. If the calibrated direct-support probability stays low,
Threadline should refuse even when it can fill all 7,000 evidence tokens.

## Their disagreement rule is too neutral

Threadline retains two conflicting chunks and asks the model to describe the
disagreement. That is safer than silently choosing one, but Corelight refuses
to prefer a newer document unless the older one is explicitly marked
superseded. In real internal corpora, supersession metadata is incomplete.
Neutrality can present an obsolete runbook as equally authoritative.

I would use a source-authority policy with visible reasons: approved decision
records outrank informal notes, active runbooks outrank archived ones, and
documents owned by the responsible team outrank copied summaries. Date should
be a weak signal, not a verdict. When two sources remain comparable, show the
conflict and route the answer toward verification.

## History should earn its place

Corelight keeps the latest two turns verbatim and gives history up to 5,000
tokens. That is a reasonable conversational default and a risky technical
default. The previous answer may contain an incorrect assumption, and copying
it verbatim can make the next answer treat generated text as established fact.

I would preserve the user's last two turns but represent prior assistant
answers as claims linked to their original citations. A claim whose source is
not retrieved again should be marked conversational context, not evidence.
For pronouns such as "that second option," keep the referenced options, but do
not automatically preserve every explanatory paragraph around them.

## Whole chunks are the right default

I agree with Threadline's refusal to truncate chunks mid-paragraph. Arbitrary
token slicing often keeps a recommendation and drops its exception. Their
conditional neighbor expansion is also sensible: it fires on 7.3% of queries
and adds one neighbor only when structure suggests the chunk is incomplete.

I would extend the structural signals to tables and numbered procedures. If a
retrieved chunk contains step four of a six-step rollback, the allocator
should either fetch the complete procedure or label the evidence incomplete.
A fluent answer built from steps four and five is more dangerous than a
visible refusal.

## Fixed answer space is not always enough

Threadline reserves 1,000 tokens for the answer. That is generous for fact
lookup and tight for a comparison involving five cited sources. If evidence
selection discovers multiple conflicts or a long procedure, the answer budget
should expand by borrowing from conversation history rather than compressing
the result into uncited shorthand.

I would define answer classes before generation: direct, procedural,
comparative, conflict, and refusal. Give direct answers 500 tokens, procedures
1,200, comparisons 1,500, and conflict reports up to 1,800. The classifier can
be wrong, but the budget trace will expose the decision and evaluation can
measure whether each class has enough room.

## Test the allocator as its own system

Corelight says each allocation rule has an evaluation slice. I would make the
allocator independently replayable: provide a question, ranked candidates,
history, and token limits, then record the exact admitted context without
calling the answer model. This supports deterministic tests for document caps,
neighbor expansion, conflict retention, and history removal.

I would also maintain 200 adversarial budget cases. Include one very long
high-ranked distractor, several short direct sources, conflicting revisions,
an oversized user log, and conversation history containing an earlier
hallucination. Measure evidence coverage and authority quality before measuring
the final prose.

## The policy I would ship

I would keep Threadline's 16,000-token envelope, complete chunks, conditional
neighbors, and visible trace. I would replace the fixed evidence floor with
role-based evidence reservations, calibrate admission by question family,
attach authority to conflicts, and prevent old assistant prose from becoming
evidence merely because it is recent.

Corelight's central claim is correct: more context is not free certainty.
My disagreement is about what should win when context competes. Tokens are the
accounting unit, but direct support, source authority, and conversational
provenance are the values the allocator should spend them on.
