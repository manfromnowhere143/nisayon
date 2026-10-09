# Refused delivery and admitted replacement

**Resolution, 20 September 2026.** Named reference `976c2f7` binds each queued
action to the chunk admitted with it. Ordinary Y02 now reads 20 ms, satisfied;
the unfenced actual replacement remains 120 ms, violated, with a retrospective
identity conflict. Y01, Y03 and Y04 are unchanged. The [final audit](reconciliation-audit-002.json)
verifies every row against the [owner's disposition](../../../evaluation/results/temporal-integration-001/followthrough/clock/README.md).
The version-2 counterexample and its original measurements below stay intact.

**20 September 2026 · two separate findings from eight exposed software controls.**

A later response does not necessarily replace an already queued action. The
producer can reject it for conflicting identity. In Y02 it does so, but the
reference subsequently uses that rejected response's observation to judge the
original action. Y03 is different: the frozen latest-request policy actually
admits the newer stale response, replaces the fresh queued action and then
refuses to dispatch. That is a usefulness tradeoff of the declared policy,
not a violation of what it promised to do.

[Frozen plan](frozen-admission-conformance.v1.json),
[eight verified executed traces](admission-conformance-execution-001/execution.json),
[full results](admission-conformance-001.json),
[verified raw and assessment archive](admission-conformance-001.tar.gz).
Execution source `601b0b8e072b4a439c09e4fc5305dbf44aaa7e46`; reference delivery
`8e5465051a583823ce8bf3914846e71046fbdeee`. The plan was committed before capture.

The original response carries value 1 from observation `o0` acquired at 0 ms,
request `q0`, chunk `c0`, target step 0. It is admitted at 10 ms. A later
observation `o1`, acquired at −100 ms on the same controller clock but received
at 12 ms, supplies request `q1`. Its response arrives at 14 ms. Dispatch is at
20 ms with an inclusive 50 ms age limit. These are constructed software inputs;
no physical observation or learned policy is claimed.

| Case | Ordinary producer operation | Reference freshness / assigned contract |
| --- | --- | --- |
| Y01: original fresh response only | Send value 1, acknowledge | satisfied / satisfied |
| Y02: later stale response reuses `c0` | Refuse the colliding delivery; send original value 1, acknowledge | violated / violated |
| Y03: later stale response uses distinct `c1` | Replace `c0:0`; refuse stale `c1:0` at dispatch | satisfied vacuously / violated usefulness |
| Y04: identical original response delivered again | Refuse duplicate; send value 1, acknowledge | satisfied / satisfied |

In Y02, the rejected delivery has `admitted: []`, `replaced: []` and reason
`chunk_identity_collision`. The actual sent value remains 1. The original
admission binds its acquisition to 0 ms, yielding 20 ms age. The reference reads
120 ms from `q1` instead: `_on_response` replaces the chunk lookup even though
the subsequent admission rejects the new delivery. This conclusion can be
checked from the recorded responses, admission decisions and exact timestamps;
the producer's `age_guard` is not an independent oracle.

The unfenced Y02 control really does replace and send value 99 from the stale
response, so its 120 ms reading describes its actual replacement. Y03 likewise
records an actual admitted replacement. The ordinary guard makes no send in
Y03; no task progress is inferred from that refusal. The original 20-case suite
and all earlier outcomes remain unchanged.

## Evaluation request and execution follow-up

The evaluation owner must adjudicate Y02's conflicting identity explicitly:
either invalidate the conflicting declarations under a stated identity premise,
or bind dispatch interpretation to the version actually admitted into the queue.
The discarded response must not silently become the original action's origin.
Keep before/after findings, Y01/Y04 controls and the distinct Y03 replacement.
The eight traces are committed, so no schedule needs rerunning for that review.

Execution can separately test an ordinary combined deadline policy: require a
supported fresh age before admitting a replacement, and check again at dispatch.
This would preserve an already queued fresh action in Y03 while still refusing
an action that expires between admission and dispatch. The existing arrival-only
and dispatch-only remedies remain frozen. Any new option will be supplied
identically to conventional and selected comparators; it cannot establish a
product advantage. Physical task utility and whether an older action remains
appropriate beyond this software contract are unmeasured.

Capture `64b16c6b`: 0.775819 command wall seconds, 0.653900 nested process CPU
seconds, 3,257,915 bytes before its final record, within 10 CPU s / 8 MiB.
Export `1d9aea34`: 0.220951 s. Verified assessment readback/archive `1dcafe5d`:
0.358208 s; the archive adds 868,504 bytes. All eight assignments completed and
verify. No simulator, model, hardware or reserved allocation was used. These
eight later diagnostics are separate from the original 190 and the eight clock
controls; no pooled repair success rate follows.
