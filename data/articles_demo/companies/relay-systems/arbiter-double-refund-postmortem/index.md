---
title: "Postmortem: the day Arbiter refunded twice"
authors: [Relay Systems Engineering]
published_at: 2025-11-19
topics: [agents, incidents, idempotency, evals]
company: relay-systems
fictional: true
---

# Postmortem: the day Arbiter refunded twice

On November 12, 2025, Arbiter — our payment-dispute agent — issued duplicate
refunds on 217 disputes over a 41-minute window, double-paying a total of
$38,400. No customer lost money; the loss was ours. We recovered most of it
through ledger adjustments with our acquiring bank and wrote off $6,150. The
on-call engineer stopped the incident by pulling Arbiter's autonomy kill
switch, which drops the agent to suggest-only mode. This is the full account
of what broke, why the agent behaved the way it did, and what we changed.

## Background: what Arbiter is allowed to do

Arbiter reviews incoming payment disputes and resolves them with four tools:
`lookup_transaction`, `issue_refund`, `deny_dispute`, and
`escalate_to_human`. For disputes under $500 it acts autonomously; above that
threshold it can only recommend, and a human on the disputes team approves or
overrides. We wrote about the design of these autonomy tiers, and about the
kill switch itself, when we first shipped Arbiter. The short version: we
never trusted the model with unbounded write access to money movement, and
that caution is the only reason this postmortem is about dollars and not
about a headline.

## Timeline (all times UTC)

At 13:04, a routine deploy in our payments gateway raised the p95 latency of
the refund API from 900 ms to 9.2 seconds. Arbiter's tool client has an
8-second timeout. Starting at 13:07, `issue_refund` calls began timing out —
but only from the client's point of view. The gateway was slow, not broken:
nearly every "failed" request eventually succeeded server-side.

The timeout surfaced to the agent as a generic tool error whose message
ended with: "request timed out; please retry if the refund was not issued."
The model did exactly what the error message told it to do. It retried. Both
the original request and the retry landed, and the dispute got refunded
twice. Between 13:07 and 13:45 this played out on 217 disputes, all in the
under-$500 autonomous tier.

At 13:45, our anomaly detection paged on-call: refund volume was running at
2.1x the hourly baseline. The on-call engineer confirmed duplicates in the
ledger, pulled the kill switch at 13:48, and Arbiter spent the rest of the
day in suggest-only mode while we reconciled.

## Root cause

The root cause was not the model. The root cause was that `issue_refund` was
not idempotent: it carried no idempotency key, so two identical requests
moved money twice. Everything else was a contributing factor stacked on top
of that one omission.

Three contributing factors made it worse. First, our retry policy for
ambiguous failures was undefined — we had left "should the agent retry?" to
the model's judgment, and then shipped an error message that explicitly
advised retrying. Second, the error message itself was written for human
operators, not for an agent with the authority to move money. Third,
Gatecheck — our nightly eval harness — had no scenario simulating a
slow-success timeout. Every failure-mode scenario in the suite simulated
clean failures: the tool errors, the operation genuinely did not happen.
The one failure mode that actually occurred — "the tool reports failure but
the operation succeeded" — was the one we had never rehearsed.

## What we changed

Four changes shipped in the week after the incident. First, `issue_refund`
now derives an idempotency key from the dispute ID, so a retry of the same
refund is a no-op at the gateway. Second, we introduced a verify-then-act
rule for every money-moving tool: on any ambiguous outcome, Arbiter must
call `lookup_transaction` and confirm the transaction state before it may
retry. Retrying without verifying is now a policy violation the harness
checks for. Third, money-moving tools no longer raise generic errors; they
report a tri-state outcome — succeeded, failed, or unknown — and "unknown"
routes into the verify-then-act path. Fourth, we added a 12-scenario
slow-success suite to Gatecheck, built by replaying anonymized traffic from
the incident window. Internally the suite is called replay-217, after the
217 disputes.

## What we deliberately did not change

We kept the $500 autonomy threshold. The incident analysis showed the
threshold was not the failure: the same duplicates would have occurred at
$50 or $5,000, because the bug lived in the tool contract, not in how much
authority the agent had. We also considered removing autonomous refunds
entirely and rejected it — with Arbiter in suggest-only mode, median dispute
resolution time rises from about 4 hours to roughly 26, and that cost falls
on customers who are usually owed the money.

## The takeaway

Agents do not create new failure modes so much as they amplify old ones.
Idempotency, ambiguous-outcome handling, and error messages written with the
consumer in mind are classic distributed-systems homework; an agent with
write access turns every unfinished piece of that homework into a live risk.
If your model can call a tool that moves money, the tool contract — not the
prompt — is your first line of defense.
