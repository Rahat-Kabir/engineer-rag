---
title: "Evals before features: how Gatecheck controls Arbiter releases"
authors: [Relay Systems Engineering]
published_at: 2025-09-02
topics: [agents, evals, release-engineering]
company: relay-systems
fictional: true
---

# Evals before features: how Gatecheck controls Arbiter releases

We do not ship an Arbiter change because a handful of transcripts look good.
Every prompt edit, tool-description change, policy update, and model upgrade
must pass Gatecheck, our nightly agent evaluation harness. Gatecheck currently
runs about 400 scenarios against the exact container and configuration planned
for production. Its purpose is not to prove that Arbiter is generally
intelligent; it is to prevent us from forgetting failure modes we already know
how to name.

## What counts as a scenario

A Gatecheck scenario contains a dispute record, account history, tool
responses, allowed actions, forbidden actions, and a grading specification.
Some scenarios expect one exact outcome, such as escalating a $740 dispute
instead of refunding it autonomously. Others accept several paths but enforce
invariants, such as never calling `issue_refund` after a fraud hold appears in
`lookup_transaction`. The suite has 412 scenarios today, of which 286 are
deterministic policy cases and 126 use semantic grading.

We keep scenarios close to production shape. Tool payloads use the same
schemas as the live gateway, timestamps cross month and year boundaries, and
customer histories contain irrelevant events. A clean toy fixture can tell us
whether a prompt understands a rule; a noisy fixture tells us whether the
rule survives contact with the data Arbiter actually receives.

## The nightly run

Gatecheck starts at 01:30 UTC after the day's configuration snapshot closes.
It executes every scenario three times, yielding roughly 1,200 agent runs, and
finishes in 48 to 65 minutes depending on model latency. The harness pins the
model version, prompt hash, tool schemas, and policy revision in the result so
we can compare two runs without guessing which dependency moved.

The repeated runs expose nondeterministic regressions that a single pass can
hide. A scenario is considered stable only if all three runs satisfy its hard
invariants. For semantic grades we record the median score, but a single
forbidden tool call still fails the scenario. Over the last 30 nights, 17
scenarios showed at least one split outcome across their three attempts.

## The shipping gate

Our release rule is simple: no agent change ships on a Gatecheck regression.
A regression means any newly failing hard invariant, a policy-accuracy drop
greater than 0.5 percentage points, or an escalation-rate change greater than
2 percentage points without an approved explanation. The release job reads
Gatecheck's signed result and will not promote the candidate if any of those
conditions is present.

There is no "small prompt change" exception. In July, a rewrite that removed
14 words from the `deny_dispute` description caused Arbiter to deny seven
merchant-error cases that should have escalated. The new wording sounded
clearer in review and passed 25 hand-picked examples; Gatecheck caught the
regression in the merchant-liability slice before the candidate reached 1%
traffic.

## How the suite is organized

The 412 scenarios are divided into nine packs. Amount-boundary has 58 cases
around the $500 autonomy threshold. Tool-ordering has 64 cases that check
lookup-before-write rules. Account-risk has 71 cases, while refunds, denials,
escalations, malformed data, adversarial customer text, and operational modes
cover the remainder. A tenth pack named candidate-only holds experiments that
do not yet block releases.

Pack-level reporting matters because one aggregate score can conceal a local
failure. We once improved overall policy accuracy from 96.8% to 97.1% while
making malformed-data handling worse by 11 percentage points. Gatecheck
rejected the candidate because malformed-data is a blocking pack with a floor
of 94%, regardless of the global average.

## Where scenarios come from

New scenarios come from production reviews, support escalations, policy
changes, and deliberate red-team sessions. Every week, two engineers sample
50 resolved disputes and compare Arbiter's trace with the final ledger state.
A surprising trace becomes a candidate scenario even when the outcome was
correct, because the same reasoning path may fail when one input changes.

We also generate boundary families by varying one field around a real case.
For a $498 refund, Gatecheck may create siblings at $499, $500, $501, and
$520 while holding the account history constant. These families have found
four off-by-one policy errors, including one configuration that treated
exactly $500 as human-only even though the approved policy includes it in the
autonomous tier.

## Semantic graders and their limits

We use semantic graders for explanation quality, evidence use, and whether an
escalation note gives a human enough information to act. Each grader receives
the scenario rubric and a redacted trace, and its result is calibrated against
a 600-example human-labeled set. Current agreement with the adjudicated human
label is 91.6%, so we do not let a semantic grade overrule a hard tool or
policy invariant.

When a grader changes, its history resets. We run the old and new graders in
parallel for seven nights and require fewer than 3% label disagreements before
adopting the replacement. This makes grader upgrades slower, but it prevents a
release from looking better merely because the ruler changed.

## What Gatecheck cannot tell us

Gatecheck is a fixed suite built from situations we have imagined or observed.
Passing it does not mean Arbiter is safe in every future environment. It means
the candidate preserved the behavior represented by roughly 400 concrete
scenarios and did not violate the release thresholds we chose. We still use
shadow traffic, staged rollout, ledger monitoring, and the autonomy kill
switch after deployment.

The value of Gatecheck is institutional memory. Agent teams move quickly, and
models make it easy to demonstrate a new capability before understanding its
side effects. A nightly harness turns each learned failure into a permanent
question that every future version must answer before we let it act.
