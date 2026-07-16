---
title: "Blue-green rollouts for model-serving upgrades"
authors: [Ferrostack Engineering]
published_at: 2025-08-11
topics: [deployment, model-serving, reliability]
company: ferrostack
fictional: true
---

# Blue-green rollouts for model-serving upgrades

A model upgrade changes more than weights. Tokenization, memory use, output
shape, latency, and failure behavior may all move at once, even when the API
schema stays stable. We deploy model-serving revisions with blue-green
environments so the previous stack remains warm until the candidate has
survived both synthetic checks and live traffic. Our standard rollout takes
90 minutes and can return all traffic to blue in under four minutes.

## What blue and green contain

An environment includes the model artifact, runtime image, tokenizer, request
router, autoscaling policy, and response-normalization code. Blue is the
currently serving revision; green is created from an immutable release
manifest and receives its own 18-replica pool. Sharing the router is the only
exception, because one routing layer must divide traffic and record comparable
metrics.

We do not update green in place. If a preflight check fails, the environment is
destroyed and rebuilt from a new manifest. Artifacts produced by our internal
Forgeglass pipeline are identified by a digest, and the manifest records that
digest beside the runtime and tokenizer versions. A rollout therefore refers
to one exact combination rather than to a mutable model name.

## Preflight before live traffic

Green first runs 2,400 contract cases covering input limits, Unicode handling,
output dimensions, deterministic normalization, and known error responses.
It then receives a 20-minute shadow replay of the previous day's traffic,
including the top 50 longest requests and every request shape that caused a
timeout. Shadow responses are recorded but never returned to callers.

Preflight fails if output dimensions differ, non-finite vectors exceed one per
million values, p99 latency is more than 15% above blue, or normalized output
drift exceeds the release-specific bound. For a compatible embedding upgrade,
that drift bound is a median cosine distance of 0.08 over the 2,400 cases.
Forgeglass artifacts do not receive an exception from these checks.

## The canary windows

Live rollout uses four windows: 1%, 5%, 25%, and 50% of traffic before the
final switch. The first two windows last 15 minutes each, 25% lasts 20 minutes,
and 50% lasts 30 minutes. Traffic assignment is stable by customer workspace,
so one user's repeated queries do not alternate between model revisions.

At 1%, we focus on crashes, schema errors, and extreme latency. At 5%, enough
traffic exists to compare token buckets and regions. The 25% and 50% windows
measure downstream behavior, including vector-index acceptance, cache hit
rate, and the percentage of callers that retry. Promotion between windows is
automatic only when every blocking signal is green.

## Rollback criteria

The router returns traffic to blue if green's error rate exceeds blue by 0.4
percentage points for five minutes, if p99 latency exceeds blue by 20% for
three consecutive windows, or if any output contains a non-finite value.
We also roll back when downstream vector writes fail above 0.2%, because a
correct response that the index cannot store is not a successful upgrade.

Two criteria use absolute limits regardless of comparison: GPU memory above
92% for ten minutes and queue depth above 150,000 tokens per replica. These
protect us when both environments are affected by traffic growth but green
has less headroom. An incident commander may roll back on judgment without
waiting for a threshold.

## Keeping blue genuinely ready

Blue stays at full replica count through the 50% window and for 45 minutes
after green reaches 100%. Requests continue warming blue's tokenizer and model
cache at 0.5% shadow traffic, so rollback does not land on cold workers. Only
after the hold period do we scale blue to two replicas for another 24 hours.

This costs roughly 1.7 extra accelerator-days per standard rollout. We tried
scaling blue down during the 25% window and saved 22% of rollout compute, but
a later rollback took 17 minutes while replicas loaded weights. The saved
compute was not worth extending exposure during an incident.

## Comparing behavior, not just uptime

Infrastructure metrics can pass while retrieval quality moves. For embedding
revisions, we dual-write a sample of green vectors into an isolated index and
run 600 fixed nearest-neighbor queries. Promotion requires Recall@10 no more
than one percentage point below blue and median rank displacement below 2.5
positions.

We also inspect live disagreement. For 0.2% of eligible requests, both
environments produce an output and a comparator records cosine distance,
nearest-neighbor overlap, and execution time. The duplicate result is never
returned to the caller. A sudden disagreement cluster by language or input
length can stop the rollout even when the global averages look normal.

## Database and cache compatibility

Model serving is mostly stateless, but its surrounding systems are not.
Response caches include the model digest in their keys, preventing green from
reading blue's cached output. Vector collections record embedding dimension
and revision, and the writer refuses a mismatched vector before it reaches
storage.

When an upgrade requires a new dimension, blue-green extends to the index:
we create a green collection, backfill it, and keep both collections updated
until query evaluation passes. The serving rollout cannot begin before the
green collection reports 100% document coverage and less than 0.05% write
lag over a six-hour window.

## A rollback we were glad to make

On July 23, a candidate passed preflight and the 1% window, then showed a
language-specific latency problem at 5%. Inputs containing mixed Japanese and
ASCII text reached 410 ms p99, compared with 96 ms on blue. Global p99 moved
only 8%, but the token-bucket dashboard crossed its 20% comparative limit for
that slice.

The router returned all traffic to blue in 3 minutes 18 seconds. Investigation
found a tokenizer memory-allocation change in the candidate runtime. Because
blue remained warm, callers saw a brief latency increase rather than a
17-minute capacity recovery.

## The release is the system

We consider a model ready only when the whole serving revision can be
deployed, observed, and reversed. A strong offline score cannot compensate for
an incompatible tokenizer, an unstable queue, or a vector index that rejects
the output. Blue-green gives us time to compare those properties under real
traffic without making the candidate the only path home.

The design is intentionally conservative. Ninety minutes of staged traffic and
a day of blue capacity cost more than replacing replicas in place. They also
turn rollback from a rebuild into a routing decision, which is the difference
between having a rollback document and having a rollback capability.
