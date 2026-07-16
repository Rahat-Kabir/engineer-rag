---
title: "Getting embedding serving below 45 ms p99"
authors: [Ferrostack Engineering]
published_at: 2025-05-20
topics: [embeddings, latency, infrastructure]
company: ferrostack
fictional: true
---

# Getting embedding serving below 45 ms p99

Our embedding service sits on the synchronous path for search, recommendations,
and retrieval-augmented generation. In January, its p50 latency was 31 ms and
its p99 was 184 ms, which looked acceptable in averages and felt broken to
users. A RAG request often embeds a query before performing vector search, so
the tail delayed every later stage. Over eight weeks we brought p99 to 43 ms
without changing the embedding model or buying larger accelerators.

## The original serving path

The service received text over HTTP, tokenized it on a general worker, sent a
single-item tensor to one of 12 GPU replicas, normalized the output, and
returned 1,024 floats. Each replica ran on a shared accelerator with 24 GB of
memory and accepted up to 64 concurrent requests. At 2,800 requests per
second, GPU utilization averaged only 41%, yet queue time at p99 reached
96 ms.

The contradiction came from request shape. Ninety-two percent of inputs were
shorter than 128 tokens, while 1.6% exceeded 2,000. A long request occupied the
same per-replica scheduling lane as dozens of short queries. The GPU had spare
compute across the fleet, but individual queues were blocked behind
unpredictable token counts.

## Measuring the tail correctly

Our first dashboards measured latency at the service process, excluding the
edge proxy and client retries. We moved the primary service-level indicator to
the caller and attached a request ID across all hops. That changed reported
p99 from 151 to 184 ms and revealed that 21 ms came from connection setup on
clients that did not reuse HTTP connections.

We also split metrics by input-token bucket: 1–128, 129–512, 513–2,048, and
above 2,048. The aggregate p99 was dominated by long inputs even though short
queries represented nearly all interactive traffic. We set separate
objectives: under 45 ms p99 for inputs up to 128 tokens and under 180 ms for
inputs up to 2,048.

## Token-aware queues

The largest improvement came from replacing one FIFO queue per replica with
three token-aware lanes. Inputs up to 128 tokens enter the interactive lane,
129–512 enter standard, and larger inputs enter bulk. A weighted scheduler
gives interactive requests six turns for every two standard and one bulk turn,
while guaranteeing bulk at least 10% of execution slots.

This reduced short-input queue time from 96 to 24 ms at p99. Bulk requests
became 13 ms slower at p50 but remained inside their 180 ms objective. More
importantly, a batch of document-ingestion traffic could no longer make an
interactive search query wait behind a 6,000-token paragraph.

## Dynamic micro-batching

Single-query inference left the accelerator underused, but fixed batching
added delay while waiting for a batch to fill. We introduced micro-batches
with a 2.5 ms collection window for the interactive lane and 8 ms for the
other lanes. Batches are limited by 2,048 total tokens rather than by request
count, which keeps execution time predictable.

At normal load, interactive batches contain 7.4 requests on average and run
in 6.8 ms. During low traffic, the 2.5 ms window expires with one or two
requests, preserving latency. GPU utilization increased from 41% to 68%, and
we handled 4,100 requests per second on the same 12 replicas during a replay
test.

## Moving tokenization off the request worker

Tokenization consumed only 3.7 ms at p50 but reached 29 ms at p99 when Python
workers competed for CPU. We moved it into a dedicated Rust sidecar with a
bounded pool of 16 threads and memory-mapped vocabulary files. The serving
process now sends text over a local socket and receives token IDs plus the
input length used for lane selection.

The sidecar brought tokenization p99 to 7 ms. We tested 40 million production
strings against the previous tokenizer and found byte-identical token IDs for
all but 23 malformed Unicode inputs. Those inputs are now rejected with a
specific validation error instead of being normalized differently by
different clients.

## Connection reuse and payload size

Client connection pooling removed another 17 ms from end-to-end p99. We
published a small client package that keeps eight warm HTTP/2 connections per
process and refreshes them after 10,000 requests. Within three weeks, pooled
clients represented 97% of traffic, and connection setup disappeared from the
normal request trace.

We return embeddings as packed little-endian float arrays rather than JSON
numbers. A 1,024-dimension response fell from about 14 KB to 4 KB, and response
serialization dropped from 4.2 to 0.6 ms at p99. The client validates the
dimension and model revision before exposing the vector to callers.

## Admission control

Before this work, overload produced long queues and eventually synchronized
timeouts. We now reject requests when estimated queued tokens exceed 180,000
per replica or when interactive wait time is projected above 35 ms. Rejections
carry a retry-after range derived from the lane, and ingestion clients back
off while interactive clients may fail over to a second region.

In a 6,000-request-per-second load test, the old service reached 1.8 seconds
p99 before failing. The new service held successful interactive requests at
48 ms p99 and rejected 7.2% explicitly. A clean rejection is operationally
better than pretending every request can fit and allowing all of them to miss
their deadline.

## Final result

For inputs up to 128 tokens, end-to-end latency is now 18 ms p50, 31 ms p95,
and 43 ms p99. Inputs from 129 to 512 tokens are 57 ms p99, while the
513–2,048 bucket is 142 ms. The service supports 46% more sustained throughput
on the same hardware and has not exceeded the interactive objective in the
last 21 days.

No single optimization produced the result. Tail latency came from queue
shape, tokenization contention, connection setup, serialization, and overload
behavior. The model was never the slowest part. Once we measured the request
from the caller and separated workloads by cost, the path to a lower p99
became ordinary serving engineering.
