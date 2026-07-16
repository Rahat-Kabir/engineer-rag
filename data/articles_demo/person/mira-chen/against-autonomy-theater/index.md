---
title: "Against autonomy theater"
authors: [Mira Chen]
published_at: 2025-12-08
topics: [agents, safety, operations]
fictional: true
---

# Against autonomy theater

Relay Systems published "Designing a kill switch for an agent that can move
money" in June, and the post is competent. Their agent Arbiter had a $500
autonomy threshold, a gateway-enforced suggest-only mode, hardware-key access,
and monthly drills. Then November happened: 217 disputes were refunded twice,
Relay lost $38,400, and the kill switch was pulled 41 minutes after the first
bad refund. This is not evidence that kill switches are useless. It is
evidence that teams keep presenting containment as control.

## The switch worked exactly as designed

I want to be fair to Relay because the easy criticism is wrong. Their switch
did drop Arbiter to suggest-only mode, the gateway blocked new writes, and an
operator changed the mode in minutes after the anomaly page. The postmortem
also makes clear that the underlying defect was a non-idempotent refund tool,
not a model spontaneously deciding to steal money.

But "worked as designed" is a floor, not a safety argument. The switch did
nothing during the 41-minute window before the page. Every one of the 217
disputes was under the celebrated $500 threshold, proving that a bounded
individual action can still create an unbounded aggregate incident. Relay's
controls limited each decision while leaving the rate of decisions largely
outside the same safety story.

## Thresholds are comforting because they are countable

The $500 threshold sounds precise. It lets a review document say that expensive
cases require a human and that 93.4% of cases can still be automated. Yet the
incident total was $38,400 because the system repeated a small permitted action
at machine speed. A per-action boundary without a per-window exposure boundary
is only half a limit.

I would have required a rolling budget beside the individual threshold:
Arbiter may autonomously refund no more than $4,000 in 15 minutes and no more
than 1.4 times the expected dispute count for that hour. Crossing either limit
should remove write authority automatically, not merely page a person. The
numbers would need tuning, but the control shape is more important than my
invented values.

## Suggest-only still trusts the same reasoning

Relay describes suggest-only as the safer state because a person sits between
Arbiter's recommendation and the write. Necessary, yes. Sufficient, no. During
a systemic failure, the human queue fills with recommendations generated from
the same tool responses and the same mistaken assumptions that produced the
incident.

If the interface presents 300 nearly identical refund recommendations, the
human becomes a low-bandwidth confirmation service. Relay says median
resolution time rises from four hours to 26 hours in suggest-only mode, which
creates pressure to approve quickly and restore autonomy. A useful degraded
mode needs changed information and sampling rules, not only an extra click.

## Detection is part of authority

The June post separates the kill switch from anomaly detection, but users
experience them as one control loop. A switch that operators can pull in
34 seconds is not a 34-second control if the system takes 41 minutes to tell
them something is wrong. The effective response time starts at the first
harmful action.

Relay's anomaly page fired when refund volume reached 2.1 times the hourly
baseline. That caught a broad spike, but it was insensitive to repeated refund
keys and ambiguous timeout patterns. I would monitor action identity and tool
uncertainty directly: repeated money movement on one dispute, a rise in
`unknown` outcomes, and retries after timeout should each be able to revoke
authority before aggregate volume looks unusual.

## The tool contract was the real safety boundary

Relay's postmortem reaches the right conclusion: `issue_refund` needed an
idempotency key, and ambiguous outcomes needed verify-then-act behavior. Those
changes prevent the duplicate even if the model retries, the page is late, and
the operator is asleep. That is stronger than any prompt instruction or
console switch because it removes the invalid state transition.

This is why I object to autonomy diagrams that begin with model confidence and
end with a red emergency button. The meaningful questions live in the middle.
Can the tool perform the same action twice? Does it distinguish failure from
unknown outcome? Is authority checked at execution time? Can the system enforce
a cumulative exposure budget without model cooperation?

## Drills can rehearse the wrong success

Relay's monthly drill asks an operator to pull the switch, verify that a
synthetic refund is blocked, and restore autonomy. That is useful plumbing
verification. It does not rehearse diagnosis under a partially failing
gateway, customer-support noise, a growing manual queue, and pressure from a
payments team watching resolution time climb.

I would run quarterly game days where the correct response is not announced.
One scenario should contain a harmless latency increase that does not justify
shutdown; another should contain slow-success ambiguity; a third should show a
bad recommendation pattern while tools remain healthy. Measure time to detect,
time to reduce authority, amount exposed, and whether operators restore
autonomy before understanding the fault.

## What I would keep from Relay's design

I would keep gateway enforcement, asymmetric permissions for disabling and
restoring autonomy, and the rule that operators do not need a diagnosis before
reducing authority. I would also keep the agent running in a constrained mode,
because traces from the degraded period are useful and completely stopping the
worker can hide the decision pattern.

I would add automatic rolling budgets, uncertainty-aware revocation, sampled
human review before a threshold breach, and tools that make duplicate writes
impossible. I would also report the full control-loop latency, not the console
interaction time. A button is not a safety system; it is one actuator inside
one.

## Stop selling the red button

The industry likes kill switches because they photograph well. They turn a
messy argument about distributed systems, monitoring, incentives, and operator
capacity into a visible object. Relay Systems did more work than most teams,
and their own incident still shows the gap between having a switch and
controlling autonomy.

Use the switch. Drill it. Put enforcement outside the model. Then assume it
will be pulled late, by a tired person, after several individually permitted
actions have composed into something your threshold diagram never showed.
Design the rest of the system for that reality.
