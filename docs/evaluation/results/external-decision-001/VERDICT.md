# Verdict: external-decision-001, LeRobot issue 4415

**20 September 2026 · evaluation lane.** Rule `external-decision-001/v1` from
[`FROZEN_PLAN.md`](FROZEN_PLAN.md). Every number below is in
[`assessment-readback-001.json`](assessment-readback-001.json) with the command records
that produced it. Four questions, four separate answers.

## 1. Did the reported software behaviour reproduce?

Yes, as a reduced mechanism. On the pinned `normalize_processor.py` (`5aa74557`, sha256
`f0cd88be…`) executed unmodified with replaced imports, on the later revision's actual
bytes (`policy_preprocessor.json` `7683d648…`, `policy_postprocessor.json` `2b78bb74…`,
both 640-byte state files `490ab239…`), the postprocessor returns the six-value witness
`[0.5]×6` unchanged and the preprocessor returns the state witness
`[0, 40, 200, −20, 30, −10]` unchanged. The reference expects exactly that: the state
file holds six float32 tensors for `so100`, `so100-blue` and `so100-red` under
`<dataset>.buffer.action.{mean,std}`, no key resolves `action` and no key exists for
`observation.state`. The three visual features are IDENTITY and unchanged, which is
correct. The full `make_pre_post_processors` loader, the policy and any robot were not
executed; the loader path was read from source, not run.

What is now verified rather than reported: the dataset count is three; the artifact's
`so100` action statistics agree to two decimals with the values the reporter transcribed
from the pre-migration checkpoint; and the reporter's `torch.equal` result is the
behaviour of an exact-key miss, not of a fixed point (the witness is non-vacuous under
every retained statistics set).

## 2. Did a candidate meet the frozen software obligations?

| Candidate | Reference outcome | Why |
|---|---|---|
| C0 as-is | rejected | O1 state skipped, O2 action skipped |
| C1 suffix match | rejected | O1 has nothing to match; O2 resolves three keys, and the two frozen store orders bind different datasets and give different outputs (`so100-blue` first, then `so100` first), so O4 fails |
| C2 explicit override with selector `so100` | **supported software correction**, deployment binding **unresolved** | both repair rows transform with one bound key on non-vacuous witnesses (state 0.69 ulp, action 0.50 ulp from the exact expectation; bit-exact with the float32 emulation); IDENTITY preserved; the state statistics are the reporter's transcription |
| C3 re-migration | not executed | needs the earlier checkpoint, out of scope |

Both arms' producers reached the same three outcomes; the reference records no false
acceptance and no false refusal. The useful positive path is preserved: C2 is accepted,
and the IDENTITY features are not flagged.

The conditional matters. C2 fixes the mechanism with whatever statistics it is given.
For a fine-tuned model, the fine-tuning dataset's statistics are the right ones and the
documented override applies them. For the base model deployed as shipped, the only state
statistics that exist are twelve two-decimal numbers in a public comment. The reference
therefore reports the software correction as supported and the deployment binding as
unresolved, and it would report the same for any override whose provenance is not the
training artifact.

**Superseding note on the binding vocabulary (later on 20 September).** This verdict
was scored under rule version 1, whose `deployment_binding` followed declared provenance
labels; a relabelled copy could promote it. Under version 2 the same records give the
same outcomes and the same unresolved binding, now stated from evidence the evaluator
establishes itself: the action override equals the artifact's `so100` statistics, the
state override matches nothing in the artifact, and neither interpretation nor selection
is carried by the record contract. See `assessments-v2/` and
[`../baseline-qualification-001/FINDING.md`](../baseline-qualification-001/FINDING.md).

## 3. Was a robot task or deployment outcome observed?

No. Nothing in this block ran a policy, a simulator or hardware. Question 3 is
unmeasured by allocation, not answered.

## 4. Did the Nisayon workflow reduce complete measured work at matched correctness?

Not established, and this comparison cannot establish it. Two reasons, one about the
data and one about the design.

The data: arm A's command cost 1.056 s wall (2.221 s nested CPU) and arm B's 1.438 s
wall (3.243 s nested CPU) for eighteen assignments including the eight controls, with
220,876 retained bytes. These are single warm local executions. Engineering effort,
provider charges, energy, network overhead and peak memory are unknown for both arms. A
fast command is not a complete-cost result.

The design: arm A was built from the same extracted mixin, the same executor helpers,
the same frozen witnesses, suffix orders and C2 statistics, and the same nine executions
as arm B, and its per-candidate outcomes are constants written into the script rather
than derived from its observations. On an exposed incident with a public remedy, a
script author who knows the answer can write it down; the matched decision is therefore
guaranteed by construction and carries no information about decision quality. What B
adds and A lacks is real but different in kind: a write-once, sealed, read-back-verifiable
regression store, declared attempts with an exercised interruption and resume, and a
decision derived from observation predicates. Whether that is worth its cost is a
question this block did not measure.

The honest reading of the frozen plan's own stopping rule: the arms tie, the tie is
retained, and the case is not replaced. A useful result here is that ordinary tooling
with the issue thread resolves this software question just as well, once someone checks
both directions and the binding rather than the reporter's single witness.

## What would change the answers

- For question 2's binding: the `normalize_inputs.*_observation_state` buffers from the
  earlier checkpoint `3326b100…` (a 906 MB download, prohibited here), or statistics
  published by the model owner with a dataset selector. Either would let the reference
  compare the transcription exactly. Under version 2 that establishes byte provenance and,
  with the feature semantics, interpretation; selection still needs the recorded
  configuration or invocation that links the selector to the target deployment, so
  recovered training statistics alone do not move the binding to supported.
- For question 3: one recorded working/changed deployment pair with a task outcome, on
  a simulator or a robot, under the confirmation obligations already in the research
  plan.
- For question 4: a comparison in which arm A is executed by a party who did not write
  arm B, on an incident whose remedy is not public, with effort metered on both sides.

## Counts

One externally authored incident (issue 4415, two comments, one corroboration). Eight
constructed controls, all synthetic. Zero reserved incidents opened. No population claim.
