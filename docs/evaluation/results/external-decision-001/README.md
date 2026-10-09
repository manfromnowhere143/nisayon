# external-decision-001 · evaluation lane report

**20 September 2026.** Case: [`QUALIFICATION.md`](QUALIFICATION.md). Frozen comparison:
[`FROZEN_PLAN.md`](FROZEN_PLAN.md). Reference contract:
[`../../PROCESSOR_REFERENCE.md`](../../PROCESSOR_REFERENCE.md). Premises against the
actual bytes: [`premises-readback-001.json`](premises-readback-001.json). Verdict:
[`VERDICT.md`](VERDICT.md). Bindings of every assessed record, command and outcome:
[`assessment-readback-001.json`](assessment-readback-001.json).

**Superseding note, 20 September 2026 (later the same day).** The assessments in
`assessments/` were produced under rule `external-decision-001/v1`, which derived the
deployment binding from declared provenance labels. That derivation was shown to be
promotable by relabelling (see
[`../baseline-qualification-001/FINDING.md`](../baseline-qualification-001/FINDING.md)).
The version-2 rereads in [`assessments-v2/`](assessments-v2/) leave every outcome,
binding and execution row of this report unchanged and add the evaluator-established
fact that C2's action override equals the artifact's `so100.buffer.action` set while its
state statistics match nothing in the artifact. The historical files are retained as
they were.

## Assessments of the execution lane's records

| Record | Execution commit | Reference decision | Retained |
|---|---|---|---|
| `first-observation-001.json` (as-is, postprocessor, `action`, inverse, `[0.5]×6`) | `d2759ce`, read at `3f6ef5d` | C0 and C1 rejected statically from the bytes; the execution agrees (`skipped_no_stats`); no producer decision | [`assessments/first-observation-001.assessment.json`](assessments/first-observation-001.assessment.json), command `1b4f2dd0` |
| arm A `conventional-a-v1.json` (9 executions, sha256 `33bc318b…`) | readback `2edf3f7`, case `e7c8a3a`, script `e1d38f8` | C0 rejected, C1 rejected, C2 supported software correction with binding unresolved; all 9 executions agree; producer agrees; no false acceptance or refusal | [`assessments/arm-A-conventional-a-v1.assessment.json`](assessments/arm-A-conventional-a-v1.assessment.json), command `ee28a38e` |
| arm B `nisayon-b-observation-v1.json` (9 executions, sha256 `f8abef20…`) | same | identical outcomes and agreements | [`assessments/arm-B-nisayon-b-observation-v1.assessment.json`](assessments/arm-B-nisayon-b-observation-v1.assessment.json), command `307cc313` |
| arm B raw store `nisayon-b-v1` (18 assignments; summary `581665e4…`, seal `54b8ca0b…`) with the frozen case | same | identical to the arm B observation row for row; the store adapter takes the suffix orders and C2 statistics from the frozen case | [`assessments/arm-B-store-nisayon-b-v1.assessment.json`](assessments/arm-B-store-nisayon-b-v1.assessment.json), command `22950760` |
| arm B interrupted-and-resumed store `diagnostics/interrupted-v1` (planned stop at `incident-C1-action-original-order`, explicit resume, two declared attempts retained) | same | identical to the sealed store row for row; producer agrees | [`assessments/arm-B-interrupted-v1.assessment.json`](assessments/arm-B-interrupted-v1.assessment.json), command `893e1ce6` |

All five input identities verified against the bytes in every assessment: preprocessor
configuration `7683d648…` (1,872 B), postprocessor configuration `2b78bb74…` (660 B),
both state files `490ab239…` (640 B), pinned `normalize_processor.py` `f0cd88be…`. Every
transformed execution is bit-exact with the reference's float32 emulation and within 0.69
ulp of the exact rational expectation.

## Costs

| Scope | Measured | Not measured |
|---|---|---|
| Evaluation-lane source retrieval | 3,022 B in two tree listings, 0.548 s wall, 0.019 s process CPU | network overhead |
| Evaluation commands (recorder) | controls 0.103 s; focused tests 1.859 s; four assessments 0.097, 0.094, 0.082 and 0.087 s | interpreter start-up variance |
| Execution arms as recorded by the producer | A 1.056 s wall / 2.221 s nested CPU; B 1.438 s wall / 3.243 s nested CPU, 220,876 retained bytes | engineering effort, provider charges, energy, peak memory |
| Required lane check on clean `9fd4cf7` | recorder `fda2495b`: 237.372 s wall; 859 passed, 1 skipped; lint; 352 files formatted; 113 documents; free disk 26,475,028,480 B before, 26,473,906,176 B after | temporary-storage peak beyond the two point readings |

Parent and nested costs are never summed. Shared preparation (the coordinator packet,
both lanes' reading and review) is attributed to neither arm.

## Time

Original mission `2026-09-17T21:30:41Z`; earlier phase clocks, pauses and the unfulfilled
five-hour requirement unchanged. This block, from committed and recorded clocks:
evaluation start `12:55:20Z`; qualification committed `13:05:09Z`; reference committed
`13:18:44Z`; first real assessment run `13:21:14Z`; both arms and the store assessed
`13:29:05Z`; verdict committed `13:32:09Z`; lane check `13:32:43Z`–`13:36:41Z`; no
pauses. Active effort outside recorded commands is unmeasured and is not inferred from
the span. The block is well short of the five useful hours the assignment asks for; what
remains after integration is the readback inspection, not more incident work, because
extending exposed cases or opening another lead is excluded by the mission.
