# Processor reference: contract for external-decision-001

**20 September 2026.** The independent reference that assesses a processor observation
record for the LeRobot 4415 case. Qualification and the frozen plan are under
[`results/external-decision-001/`](results/external-decision-001/QUALIFICATION.md).
Implementation: `src/nisayon/evaluation/processor_reference.py` (reference) and
`src/nisayon/evaluation/processor_controls.py` (eight constructed controls).

## Run it

```sh
uv run --frozen python -m nisayon.evaluation processor RECORD.json [RECORD2.json …] [--root DIR] [--manifest CAPTURE.json] [--json] [--out FILE]
uv run --frozen python -m nisayon.evaluation processor-store STORE_DIR --case FROZEN_CASE.json --sources SOURCE_ROOT [--arm A|B] [--json] [--out FILE]
uv run --frozen python -m nisayon.evaluation processor-controls [--out DIR] [--summary FILE]
uv run --frozen pytest tests/evaluation/test_evaluation_processor_reference.py
```

`processor` reads one `nisayon.processor-observation.v1` record, or several execution
lane `nisayon.external-processor-observation.v1` records (one operation each) merged into
one assessment when their input digests agree; `--manifest` supplies the counterpart
pipeline's files from the execution lane's source-capture manifest when a record carries
one pipeline. `processor-store` reads an execution lane case store (`executions/` and
`summary.json`) with its frozen case, taking the suffix orders and the explicit-override
statistics from the case rather than from the producer's records. Both exit 0 whenever
they produced an assessment, whatever it says, and 2 on a malformed record with the path
that failed. `processor-controls` exits 1 if any control's check fails.

## What the reference reads

A record with `schema: nisayon.processor-observation.v1` and:

- `arm`: `A` or `B`.
- `inputs`: `preprocessor_config`, `postprocessor_config`, `preprocessor_stats`,
  `postprocessor_stats`, each `{path, sha256, bytes?}`; optional `processor_source`.
  Paths resolve against `--root` (default: the record's directory). The bytes are read
  and digested; a mismatch with the declared digest is a finding that makes the record
  `invalid_input`.
- `executions[]`: `id`, `candidate` (`as_is`, `suffix_match`, `explicit_override`),
  `processor`, `feature`, `direction` (`forward`, `inverse`), `input` (float32 values),
  `status` (`completed` with `output`, `error` with `error`, or `interrupted`),
  `stats_provenance` (default `artifact`), optional `stats_order` (the producer's store
  iteration order, keys of the retained store), and for `explicit_override` the
  `override_stats` `{feature: {stat: values}}` the candidate supplied.
- optional `reference_statistics` `{provenance, values}`: statistics the assessor is told
  are the right ones for the deployment; a bound statistic that differs rejects the
  candidate however well the transform runs.
- optional `decision.candidates.{name}.outcome`: the producer's own verdicts, compared but
  never used to derive an expectation.

The configuration is parsed from the saved pipeline layout: the single step whose
`registry_name` is `normalizer_processor` (preprocessor) or `unnormalizer_processor`
(postprocessor), with `config.features`, `config.norm_map`, `config.eps` and optional
`config.normalize_observation_keys`. The statistics are read from the safetensors
container (8-byte length, JSON header, raw little-endian data; F32 and F64 values are
decoded, other dtypes are reported) and grouped by splitting each flat name on its last
dot, exactly as the pinned `load_state_dict` does.

## Expected class per execution

From the contract at LeRobot `5aa74557` (`normalize_processor.py` sha256 `f0cd88be…`):

| Class | When |
|---|---|
| `not_applicable` | the step does not touch this feature in this direction at inference (a preprocessor's inverse, a postprocessor's observation, an undeclared feature, a key excluded by `normalize_observation_keys`); the preprocessor's forward action is applicable only for a diagnostic round trip and is outside the obligation table |
| `identity_mode` | the feature type maps to `IDENTITY`: unchanged output is correct |
| `skipped_no_stats` | no statistics key resolves the lookup key under the candidate's rule (line 330): the input is returned |
| `transformed` | one key resolves and the required statistics are present |
| `ambiguous` | the suffix candidate resolves more than one key; the first in store order is bound, and alternatives are computed to show whether the output depends on order |
| `error` | the bound key lacks a required statistic, or their lengths differ: the pinned step raises |
| `unsupported_mode` | a mode outside the pinned set: the pinned step raises |

The lookup key is the constant `action` for `ACTION` features (line 299) and the feature
name otherwise. `as_is` and `explicit_override` use exact lookup; `suffix_match` is the
reporter's rule: exact key, else keys ending in `"." + key` or `"_" + key`, first match.

## Expected value and tolerance

For `MEAN_STD`, forward `(x − mean) / (std + eps)` and inverse `x · std + mean`, computed
in exact rational arithmetic from the float32 statistics and input. The two are not exact
inverses because the pinned step adds `eps` only on the forward side. A bit-level float32
emulation (one rounding per elementwise operation) is reported alongside.

Acceptance: `|observed − exact| ≤ 4 × (sum of the float32 units in the last place of each
rounded intermediate and of the result) + 1e-6`. Inverse rounds the product and the sum;
forward rounds the difference, the denominator and the quotient. Near a fixed point the
rounded product is far larger than the output, so its unit dominates; an output-only
tolerance would wrongly reject a correct float32 result there (tested). Torch's CPU
float32 path matches the emulation bit for bit on the tested inputs.

A `transformed` witness is vacuous when every element of its expected output is within
tolerance of the input (an input at `mean / (1 − std)` elementwise for the inverse). A
vacuous witness agrees with the reference but cannot support a candidate. A forward then
inverse round trip with the same statistics returns the input whatever the statistics
are, so a round trip never vouches for them.

## Version 2: declared provenance is not a premise (`external-decision-001/v2`)

**20 September 2026, after the label-only promotion was reproduced** (finding and
before/after records under
[`results/baseline-qualification-001/`](results/baseline-qualification-001/FINDING.md)).
Version 1 decided `deployment_binding` from the set of `stats_provenance` labels on the
explicit-override rows, so a record could promote its binding by relabelling. Version 2
keeps the candidate outcomes of version 1 and changes only what the binding is derived
from:

- `stats_provenance` is a declaration in the vocabulary `artifact`,
  `reporter_transcription`, `dataset_metadata`, `synthetic_control`,
  `verified_training_statistics`. It is retained, reported beside what the evaluator
  established, and never used to decide anything.
- Four facts are reported separately under `binding_evidence`: numeric agreement (every
  repair row transformed, agreeing and non-vacuous), byte provenance, interpretation and
  selection.
- Byte provenance per feature is established by the evaluator alone:
  `established_from_artifact` when the bound statistics were read by the evaluator from
  the digest-verified state file (`as_is`, `suffix_match`); `matches_artifact_set` when an
  override's required statistics equal, element for element, one statistics set the
  evaluator read from the verified artifact (the matched key is named); otherwise
  `not_established`. A candidate's byte provenance is established only when every repair
  feature is.
- Interpretation (which model, dataset and feature semantics the statistics belong to)
  and selection (which statistics the target deployment actually chose) are
  `not_carried_by_contract`: `nisayon.processor-observation.v1` has no field that could
  establish them, and a label cannot. A supported binding needs all four facts, so it is
  unreachable from this contract and every supported software correction reports
  `deployment_binding: unresolved` with `binding_missing` naming what is absent. The
  assessment carries `binding_contract_limit` saying so.
- A label that claims more than the evaluator established (`artifact` on statistics the
  artifact does not hold; `verified_training_statistics` or `dataset_metadata` on
  anything) is the finding `provenance_declared_not_established`, severity unresolved. It
  never fails the process and never changes the software outcome.

Authentic training statistics, if they were ever supplied and verified, would establish
byte provenance and, with their feature semantics, interpretation. They would still not
establish selection: that needs the recorded configuration or invocation that links the
selector to the target deployment, which is outside this contract.

Version-1 assessments retained under `results/external-decision-001/assessments/` are
historical; their version-2 rereads under `assessments-v2/` show every outcome, binding
and execution row unchanged.

## Frozen candidate rule (`external-decision-001/v1`, outcomes unchanged in v2)

The obligation table lists, per processor, every feature the step touches at inference:
`repair` rows (non-IDENTITY mode) and `identity_legitimacy` rows (IDENTITY mode). Per
candidate:

- `invalid_input`: any execution's observed output contradicts the pinned contract
  (outside tolerance, changed where a skip is expected, completed where a raise is
  expected), or an input digest differs from its bytes.
- `rejected_candidate`: a repair row is `skipped_no_stats`, `ambiguous`, `error` or
  `unsupported_mode` (statically for `as_is` and `suffix_match`, which depend only on the
  artifact; from executions for `explicit_override`); a bound statistic differs from the
  declared reference; or an identity row changed.
- `unresolved`: no informative (`transformed`, agreeing, non-vacuous) execution covers a
  repair row, or an execution was interrupted.
- `supported_software_correction`: every repair row has an informative execution and
  no row above applies. In version 1 its `deployment_binding` followed the declared
  labels (`supported`, `artifact_bound` or `unresolved`); that was the defect. In version
  2 it is `unresolved` unless numeric agreement, byte provenance, interpretation and
  selection are all established, and the last two cannot be under this contract.

Overall: `invalid_input` if any candidate or input is invalid; else
`supported_software_correction` if any candidate is; else `unresolved` if any is; else
`rejected_candidate`. Producer verdicts are compared per candidate; a producer
acceptance the reference does not support is a false acceptance, and a producer rejection
of a candidate the reference supports is a false refusal.

## What it cannot say

Nothing here observes a robot task or a deployment outcome. A supported software
correction says the processor step, on these bytes and inputs, transforms every feature
it must with one bound key; it does not say the statistics are the training statistics,
and one exposed incident supports no population claim. Value expectations exist for
`MEAN_STD` only; other modes are classified but their values are left unresolved.

## Controls

`processor-controls` writes and checks twelve records, each answering one frozen
question. Four were added with version 2 (16:20 UTC, after the finding): a
`verified_training_statistics` label alone does not move the binding and is a named
finding; an `artifact` label on statistics the artifact does not hold establishes
nothing; one feature whose override bytes match the artifact does not bind the
candidate; a synthetic artifact carrying complete plain statistics establishes byte
provenance for both features while the binding stays unresolved. The original eight:
an IDENTITY visual left unchanged is correct and one changed is a rejection; a fixed-point
witness is vacuous and cannot support; prefixed keys are skipped under exact lookup and
accepting as-is is a false acceptance; three prefixed datasets make the suffix candidate
ambiguous and order-dependent; a unique suffix match repairs the action and leaves the
state skipped; a complete explicit override is supported with the binding unresolved; a
round trip with wrong statistics returns the input and is still rejected against the
reference; a silent skip where the pinned step raises is invalid input. They are
constructed with round synthetic statistics and are not incidents.
