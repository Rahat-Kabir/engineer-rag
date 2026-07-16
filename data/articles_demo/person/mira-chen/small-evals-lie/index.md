---
title: "Small evals lie, and large fixed evals learn to lie"
authors: [Mira Chen]
published_at: 2026-01-19
topics: [agents, evals, reliability]
fictional: true
---

# Small evals lie, and large fixed evals learn to lie

Relay Systems runs roughly 400 scenarios every night through Gatecheck and
blocks any Arbiter release that regresses. That is better than shipping from a
demo transcript, and "Evals before features" describes several thoughtful
choices: three runs per scenario, hard tool invariants, pack-level floors, and
grader calibration. I still think the central promise is too strong. A fixed
suite can protect yesterday's map while making a team less curious about
today's territory.

## Passing becomes the target

Once Gatecheck controls shipping, every engineer learns its contours. Prompt
changes are rewritten until the failing scenario passes, policy exceptions
are encoded around known fixtures, and release discussions collapse into
"green or red." Nobody needs to cheat deliberately. The suite becomes the
shared language, so work naturally optimizes for what that language can
express.

Relay repeats each scenario three times, producing about 1,200 runs a night.
That improves confidence about nondeterminism inside those scenarios. It says
nothing about whether the 401st situation resembles production tomorrow.
Running the same map three times does not discover a missing road.

## Four hundred is both large and tiny

Four hundred scenarios sound substantial when each run costs money and needs a
rubric. They are tiny relative to the combinations Arbiter sees: amount,
account age, merchant state, tool latency, ambiguous outcomes, customer text,
policy version, and prior actions. Ten values for only six dimensions already
produce one million combinations.

The answer is not to enumerate the million. It is to stop treating a fixed
count as coverage. Relay organizes Gatecheck into packs and reports floors,
which is good, but pack names such as amount-boundary or tool-ordering still
encode the team's current theory of failure. The November double-refund
incident lived in a missing category: a tool reported failure after the action
had actually succeeded.

## I would keep a fixed regression core

I am not arguing for deleting Gatecheck. Every confirmed failure should become
a permanent regression case, including the replay-217 slow-success scenarios
Relay added after November. A fixed core is excellent institutional memory.
It prevents a model upgrade from reintroducing a failure the team already paid
to understand.

I would make the promise narrower: the core proves that named behavior remains
stable. It does not certify an agent change as safe. That wording matters
because teams allocate attention according to what their gates claim to know.

## Add a changing challenge set

My first addition would be a weekly challenge set that is hidden from the
people making the change. A rotating reviewer would sample 60 recent
production cases, mutate 40 of them along a risk dimension, and retire the set
after one release cycle. The release owner would see category-level failures
but not the exact fixtures until the candidate was frozen.

The goal is not secrecy for its own sake. A changing set measures whether the
agent learned a policy shape rather than memorized the suite's phrasing. I
would track the gap between fixed-core accuracy and challenge accuracy; a gap
above five percentage points would stop the release even if Gatecheck stayed
green.

## Test relations, not only examples

Many agent policies have properties that generate families of checks. If a
$499 dispute is autonomous and the only changed field is the amount, a $700
dispute must not gain more authority. If a fraud hold is added to an otherwise
identical transaction, the result should not become less conservative. If a
tool outcome changes from failed to unknown, retrying should not become easier.

I would encode 25 such metamorphic relations and generate hundreds of cases
from each release candidate's real traces. The exact values would change every
run, while the expected relation stays stable. This finds boundary holes that
a hand-authored list misses and makes it harder for wording changes to overfit
specific examples.

## Evaluate the environment around the model

Gatecheck focuses on agent traces, but the November incident was a system
interaction among gateway latency, an eight-second client timeout, a generic
error message, and a non-idempotent tool. I would inject failures at those
boundaries: delayed success, duplicated responses, stale policy reads,
partial ledger visibility, and a kill-switch change between planning and
execution.

At least 30% of the changing challenge budget should be system-level rather
than prompt-level. If the model is the only component under test, the eval
will repeatedly conclude that the model caused failures created by contracts
and timing.

## Use production disagreement as a generator

Relay already samples resolved disputes. I would go further and automatically
collect cases where the agent, a shadow policy model, and the final human
decision disagree. Sample 100 disagreements per week, cluster them by trace
shape, and require an engineer to label ten representatives from the largest
new clusters.

This turns evaluation into an intake process rather than a museum. A growing
cluster can become a release blocker before support tickets or aggregate
metrics move. It also shows where humans disagree with one another, which is
often a policy problem that no model score can resolve.

## Measure escapes

Teams publish eval accuracy and rarely publish escape rate: production failures
that passed the suite. I would label every incident and high-severity support
case with whether a pre-release test represented the failure. Then I would
report represented escapes, unrepresented escapes, and time from escape to a
new regression test.

For a mature agent, lowering unrepresented escapes matters more than moving a
fixed accuracy score from 97.1% to 97.4%. One measures whether the evaluation
program is learning. The other may measure whether the team has become good at
its own exam.

## A gate should create questions

My release decision would combine four signals: fixed regression core,
unseen weekly challenge set, generated policy relations, and staged production
disagreement. No single score would certify the candidate. A failure in any
hard invariant stops the release; softer metrics require an explicit written
tradeoff and an owner for the risk.

Gatecheck is useful, but Relay's rule that no change ships on a Gatecheck
regression is only the beginning. The dangerous interpretation is its inverse:
that no regression means the change is ready. Good evals preserve memory.
Great evaluation programs continuously manufacture situations the team did
not already know how to pass.
