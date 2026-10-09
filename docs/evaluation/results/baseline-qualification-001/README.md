# baseline-qualification-001 · evaluation lane report

**20 September 2026 · block start 15:59:21 UTC.** Finding and correction:
[`FINDING.md`](FINDING.md), [`finding-001.json`](finding-001.json), before-assessments in
[`before/`](before/), after-assessments in [`after/`](after/). Frozen expectations:
[`qualification-expectations.v1.json`](qualification-expectations.v1.json). Machine
readback of every record, command and outcome:
[`qualification-readback-001.json`](qualification-readback-001.json). Reference contract:
[`../../PROCESSOR_REFERENCE.md`](../../PROCESSOR_REFERENCE.md), version 2.

## 1. The provenance promotion, before and after

| Labelled copy of `conventional-a-v1.json` | Only change | v1 binding (`2779e423…`) | v2 binding (`e550b4e` and later) |
|---|---|---|---|
| `original` | none | unresolved | unresolved; action bytes match `so100.buffer.action`, state bytes match nothing |
| `provenance-label-only` | three labels → `verified_training_statistics` | **supported** | unresolved; two over-claims named |
| `artifact-label-only` | one label → `artifact` | **artifact_bound** | unresolved; one over-claim named |

Scope: the public flat-record path and its adapters. No sealed store was altered and no
historical assessment claimed a supported binding. The rule now enforced: a
`stats_provenance` label is a declaration, reported beside what the evaluator
established; byte provenance is established only from statistics read from, or matched
element for element against, the digest-verified artifact; interpretation and selection
are not carried by the observation contract; a supported binding needs all four and is
therefore unreachable from this contract, which the assessment states. The supported
software correction and the unresolved deployment conclusion are unchanged. Twelve
controls and seventeen tests pass. The historical arm A, arm B, store and
first-observation records reread under version 2 keep every outcome, binding and row
([`../external-decision-001/assessments-v2/`](../external-decision-001/assessments-v2/)).

## 2. Qualification of the computed conventional baseline

Implementation reviewed: `scripts/experiments/conventional_processor_diagnostic.py` at
execution commit `e66f478` (sha256 `e24f066c…`), consumed here by a normal merge of
`f9b5008`. Standard library only; its own safetensors reader, configuration parser,
float32 arithmetic, the reporter's full suffix rule and obligation-derived verdicts; it
shares the retained upstream bytes, the public witnesses and remedies, and generic
facilities. Both lanes know these exposed inputs; this is implementation separation, not
independent authorship or blinded diagnosis.

| Expectation | Result |
|---|---|
| E1 sealed incident observation agrees with reference v2 | holds: 10 of 10 rows agree, C0 and C1 rejected, C2 supported with binding unresolved, no false acceptance or refusal (`c8a43689`) |
| E2 opaque identifiers and order follow contents | holds, read from the sealed `result.json` |
| E3 removing the state std from the supported candidate overturns support | holds: `incomplete_statistics` on `observation.state` |
| E4 complete content under the previously rejected name gains support | holds |
| E5 no Nisayon imports, own decision computation | holds by AST inspection and the sealed implementation identity |
| E6 label-only copy of the frozen plan must leave the deployment conclusion unresolved | **fails**: the diagnostic returns `deployment_applicability: supported` citing "the retained deployment record", which does not exist; the software outcome is unchanged (`9ddd09d8`; reference v2 `431a1a94` keeps the binding unresolved and names the false binding acceptance) |

**Verdict at `e66f478`.** The computed baseline is qualified for the declared software
decision. It is not qualified for its deployment-binding conclusion: `_deployment_binding`
returns supported when the candidate carries the labels `verified_deployment_record` and
`verified_training_statistics`, which are plan text, not evidence. The one decision that
changed in E6 is C2's deployment applicability; no observation caused it; the source
premise is that function.

**Verdict at `f69727a` (execution correction, consumed by merge).** `_deployment_binding`
now takes no candidate field and returns unresolved with the contract limit stated. E6
rerun on the same labelled plan copy (`c5ad6dee`): C2 supported as software, deployment
applicability unresolved; reference v2 (`04a9e4c7`) agrees on every candidate, records no
false binding acceptance, and still names the two over-claimed labels as declarations
that were not established. Both qualification questions now hold; the sealed run-002
result and the earlier E6 failure are retained unchanged.

Qualification is not a Nisayon advantage, a repair of the old fixed-verdict comparison,
or a deployment binding.

## 3. The real deployment binding

Unresolved. This lane concurs with the execution lane's
`deployment-binding-001.json`: the two permitted metadata links found a current dataset
revision whose statistics match none of C2's twenty-four values and no recorded selector;
neither a provenance-bearing original `observation.state` statistic set nor the
deployment's recorded configuration exists in the retained inputs. Recovered original
statistics alone would establish byte provenance and interpretation, not selection. The
single evidence decision that would move this: obtain, under custody, the original
training invocation or `train_config.json` with the selected dataset revision, state
coordinate order and units, normalization mode and statistics origin, together with the
target deployment's recorded configuration that selects them. No fetch of the old
checkpoint, no range extraction, no contact.

## Lane checks

The first lane check on clean `2ed2a31` (`4ef63630`, 238.987 s) passed lint and
formatting and ran 871 tests with two failures, both in the execution lane's
`test_conventional_processor_diagnostic.py`, which resolved the gitignored
`artifacts/external-decision-001/source-capture` directory that exists only in the
execution checkout; every evaluation-owned test passed, and `make` stopped before the
documentation check. Retained as a failed check. Supplements on the same commit: the
documentation check (`4f034202`, 117 documents, no errors) and the evaluation-owned tests
(`024e37ce`, all passed). The execution lane replaced the dependency with a generated
fixture at `fe8c0d6`; the single combined-check retry is recorded in the lane record.

## Costs and time

Recorded lane commands for this block sum to 3.495 s wall before the lane check; the
coordinator's two probes (0.216 s wall, 0.169 s child CPU) are counted once; lane
artifacts 106,514 bytes; zero source downloads. Engineering effort, provider charges,
energy and peak memory are unknown. Times from committed and recorded clocks: merge of
main 15:59:28Z, finding 16:02:11Z, correction 16:08:02Z, expectations frozen 16:11:05Z,
E6 run and assessment by 16:12Z. Active effort is not inferred from the span; the earlier
five-hour requirement remains unfulfilled.
