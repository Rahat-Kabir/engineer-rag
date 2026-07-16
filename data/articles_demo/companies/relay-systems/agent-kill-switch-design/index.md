---
title: "Designing a kill switch for an agent that can move money"
authors: [Relay Systems Engineering]
published_at: 2025-06-10
topics: [agents, safety, payments]
company: relay-systems
fictional: true
---

# Designing a kill switch for an agent that can move money

Arbiter resolves payment disputes with four tools: `lookup_transaction`,
`issue_refund`, `deny_dispute`, and `escalate_to_human`. Three of those tools
change a customer-visible outcome, and one of them moves money. We therefore
treated operational control as part of the product rather than as an emergency
feature to add later. Before the first autonomous dispute was processed, we
required a control that an on-call engineer could use in under 60 seconds
without deploying code or changing a prompt.

## The autonomy tiers

Arbiter has three autonomy tiers, selected from the dispute amount and a small
set of policy flags. Tier 0 is advisory: Arbiter may inspect the transaction
and draft a recommendation, but every action requires a human. Tier 1 permits
autonomous denial or refund for disputes under $500, provided the account is
not marked high-risk and the transaction is at least 24 hours old. Tier 2 is
reserved for internal test accounts and allows the same tools without the
customer-risk restrictions; it is disabled in production.

The $500 boundary is a policy threshold, not a claim that the model becomes
unsafe at $501. We chose it after reviewing 90 days of disputes: 93.4% of
cases were below $500, while the remaining 6.6% represented 71% of disputed
dollars. That split gave Arbiter enough volume to reduce the median queue age
without granting autonomous control over the expensive tail. The threshold
lives in the policy service, not in Arbiter's system prompt, and changing it
requires approval from both Payments Risk and the agent-platform owner.

## What the kill switch actually does

Pulling the kill switch sets Arbiter to suggest-only mode. It does not stop
the worker process, clear the queue, or prevent the model from reasoning.
Arbiter continues to call `lookup_transaction`, writes a proposed resolution,
and sends that proposal to the disputes console, but calls to
`issue_refund` and `deny_dispute` are rejected by the tool gateway. Requests
already admitted by the gateway are allowed to complete, so the control is a
mode transition rather than a process kill.

We made that distinction explicit because "off" is a misleading operational
word. A stopped worker would hide what Arbiter would have done and would add
roughly 1,800 cases per hour to the manual queue during peak periods.
Suggest-only mode preserves the recommendation stream while placing a person
between the recommendation and the write. In a drill on May 27, the on-call
engineer changed the mode in 34 seconds, and the final autonomous tool call
completed 11 seconds later.

## Where the control is enforced

The source of truth is a row in our policy service named
`arbiter_execution_mode`, with values `autonomous` or `suggest_only`. The tool
gateway reads that value on every write request and caches it for no more than
five seconds. Arbiter also reads the mode before planning, but that check is
informational; enforcement belongs at the tool boundary because a stale model
context must never preserve authority that operations has removed.

Each rejected write returns a structured result with the code
`AUTONOMY_DISABLED`. Arbiter is instructed to convert that result into an
escalation, not to retry it. We tested the boundary by changing the mode
between planning and execution in 2,000 simulated disputes. All 2,000 writes
were rejected, including 317 plans that had already selected
`issue_refund` before the switch changed.

## Who can pull it

The control is available to the Payments on-call, the agent-platform on-call,
and the incident commander. It requires hardware-key authentication, records
the operator and incident reference, and pages both owning teams whenever it
changes. No approval is required to move from autonomous to suggest-only;
restoring autonomy requires two people, one from Payments and one from the
agent platform.

We deliberately made the two directions asymmetric. Removing authority should
be fast and available under uncertainty. Restoring authority should require a
shared statement that the triggering condition is understood. During monthly
drills, operators must pull the switch, verify that a synthetic refund is
blocked, and restore autonomy; the median drill time is 4 minutes 12 seconds.

## Signals that justify using it

We page on three conditions: refund volume above 1.8 times the trailing
four-week baseline, tool-error rate above 4% for five minutes, or disagreement
between Arbiter and a shadow policy model above 12% in a 200-case window.
None of these signals proves that Arbiter is wrong. They indicate that the
system has entered a state where continued autonomous writes are harder to
justify than temporary manual review.

Operators are also allowed to pull the switch on judgment alone. We do not
require a dashboard threshold if a customer report, ledger anomaly, or
unexpected tool trace suggests a systemic problem. The runbook says, in bold,
"You do not need to diagnose before reducing authority." Diagnosis can happen
after the system is in a safer mode.

## What the kill switch does not solve

The kill switch cannot make a bad tool contract safe, detect a subtle policy
error, or undo an action that already succeeded. It also depends on an
operator noticing a reason to use it. We consider it one containment layer
among several: amount limits reduce exposure, the policy service defines
authority, the gateway enforces it, and the switch lets operations remove it.

The important design choice is not the button in the console. It is that
authority is represented as explicit, revocable state at the point where an
agent's intention becomes an external action. If your agent can move money,
send messages, or modify production data, give operations a way to remove
that authority without asking the agent to cooperate.
