# External processor decision

**20 September 2026 · integrated and validated.** This case asks a narrow question:
under the pinned LeRobot code and the retained post-migration SmolVLA processor files,
which candidate restores both required normalization transforms without choosing a
dataset by dictionary order?

The answer is useful but bounded. The shipped configuration skips state normalization
and action unnormalization. The reporter's suffix remedy repairs only action and binds
different datasets when the same statistics are reordered. A documented explicit
override transforms both features and preserves legitimate visual `IDENTITY`, but the
state statistics are only a reporter transcription and the artifact has no retained
dataset selector. The software mechanism is supported; applying it to the base
deployment remains unresolved. No model, policy, robot task or deployment outcome ran.

Machine records: [frozen case](frozen-case.v1.json),
[workflow readback](workflow-readback-001.json),
[integrated readback](integration-readback-001.json),
[validation](validation-001.json),
[first observation](first-observation-001.json), and
[source receipt](source-capture-001.json). The independent
[evaluation verdict](../../../evaluation/results/external-decision-001/VERDICT.md)
and its assessments are retained under `docs/evaluation/results/external-decision-001/`.

## Incident and exposure

The sole externally authored incident is [LeRobot issue 4415](https://github.com/huggingface/lerobot/issues/4415),
opened 11 August 2026. Both lanes read the report and proposed suffix remedy before this
work. This is retrospective development, not blind or prospective diagnosis.

- Model repository: `lerobot/smolvla_base`, revision
  `c83c3163b8ca9b7e67c509fffd9121e66cb96205`.
- LeRobot source: `5aa74557f84c54d4b458f8b9643c5aa2982acfed`.
- Reviewed normalizer: SHA-256 `f0cd88be…`.
- The two 640-byte processor state files are byte-identical, SHA-256 `490ab239…`.
- They contain three dataset-prefixed action mean/std groups and no state group.
- The exact-revision model README has no license declaration. Model files remain private
  local research inputs; redistribution is unresolved. Pinned LeRobot source is
  Apache-2.0 under the retained license evidence.

There is no recorded working/changed robot deployment pair. The case therefore qualifies
as one reduced software mechanism, not as a reproduced robot failure.

## What actually ran

The command parses the retained pipeline JSON and safetensors bytes, verifies the pinned
static loader path, and AST-extracts the upstream `_NormalizationMixin` class. Its
normalization methods execute unmodified on small float32 arrays. Local equivalents
replace only enums, the feature dataclass, tensor conversion helpers and type boundaries.
LeRobot package import, Hub loading, converters, device selection, policy inference and
robot integration are omitted and named in every execution record.

Four frozen candidates were considered:

| Candidate | Result | Reason |
|---|---|---|
| C0, as shipped | Rejected | `observation.state` forward and `action` inverse both return unchanged because no exact statistics key exists. |
| C1, suffix match | Rejected | No state statistics exist; three action groups match, and changing store order changes the selected output. |
| C2, explicit override | Supported software mechanism | Complete named state/action statistics transform non-vacuous witnesses and visual `IDENTITY` remains unchanged. Applicability is unresolved. |
| C3, re-migration | Unresolved | Earlier-checkpoint statistics would require prohibited weight access or a separately retained migration source. |

The eight constructed controls remain distinct from the incident: legitimate identity,
fixed-point vacuity, exact prefixed-key skip, ambiguous suffix order, partial suffix
repair, complete override, wrong-stat round-trip cancellation and missing-standard-
deviation error. They are diagnostic controls, not independent incidents.

## Matched workflows

Both workflows receive the issue, exact inputs, source explanation, candidate remedies,
witnesses and stopping rule. Arm A was intended to represent a competent conventional
diagnostic. Arm B adds explicit obligations, attempt-before-execution retention,
constructed controls, a sealed regression and verified saved readback.

| Reading | Arm A | Arm B |
|---|---:|---:|
| Incident executions exposed to the reference | 9 | 9 |
| Candidate decisions | reject C0/C1; support C2 | reject C0/C1; support C2 |
| Robot task | unmeasured | unmeasured |
| Command wall | 1.056043 s | 1.438086 s |
| Nested process CPU | 2.220642 s | 3.242857 s |
| Sealed regression | no | yes, 18/18 assignments |

The decision is a tie, so the frozen stopping rule keeps this incident and does not open
another. The tie does not measure decision quality. Arm A shares the extracted upstream
mixin, executor helpers, witnesses and nine executions with B, and
`scripts/experiments/processor_observations.py` writes A's candidate outcomes as
constants instead of deriving them from those observations. The matched decision is
therefore guaranteed by construction. A is faster on this single warm local execution,
and B retains the stronger regression record, but neither difference establishes
comparative value. Engineering effort, provider charges, energy, network overhead and
peak memory are unknown; an absent expensive run is not counted as a saving.

Evaluation commit `9fd4cf7` was tested independently and its records-only delivery
`2f471d5` was merged normally at `85727de`. The reference agrees with all eighteen
incident executions across A and B, reports no false acceptance or refusal, leaves
C2's deployment binding unresolved, and passes all eight controls. Integrated public
reads also agree for A, B and the raw sealed store. This supports the software decision,
not an A/B advantage, recovered robot task or deployment outcome.

## Reproduce

Source capture is replayable without cloning the upstream repository or fetching weights:

```sh
uv run --frozen nisayon run --label external-source-capture -- \
  uv run --frozen python scripts/experiments/retrieve_external_decision_sources.py \
  --output artifacts/external-decision-001/source-capture-reproduction
```

Run B to a fresh output directory:

```sh
uv run --frozen nisayon external-decision run \
  --case docs/experiments/results/external-decision-001/frozen-case.v1.json \
  --sources artifacts/external-decision-001/source-capture \
  --out artifacts/external-decision-001/workflows/nisayon-b-reproduction

uv run --frozen nisayon external-decision inspect \
  artifacts/external-decision-001/workflows/nisayon-b-reproduction
```

Run the conventional workflow to a fresh record:

```sh
uv run --frozen python scripts/experiments/processor_observations.py conventional \
  --case docs/experiments/results/external-decision-001/frozen-case.v1.json \
  --sources artifacts/external-decision-001/source-capture \
  --out artifacts/external-decision-001/workflows/conventional-a-reproduction.json
```

Assess each `nisayon.processor-observation.v1` record with its named input root:

```sh
uv run --frozen python -m nisayon.evaluation processor RECORD.json \
  --root INPUT_ROOT --json
```

Existing result paths refuse overwrite. Choose a new path for a new attempt.

## Recovery and malformed boundaries

An intentional stop at `incident-C1-action-original-order` retained four completed
records and one attempt intent. Read-only inspection reported a verified prefix. Explicit
`--resume` retained a second attempt, recovery receipt and resumption identity before
sealing all 18 assignments. Inspection of the sealed store performs no execution or
retry. The focused tests also reject an overlapping safetensors boundary, retain a
missing-`std` error rather than a silent skip, reject the partial suffix correction and
preserve the useful explicit-override and identity paths.

## Costs and resources

The first reduced observation cost 1.721048 command seconds and 2.801048 nested process
CPU seconds. Source retrieval added 132,460 bytes; its principal command cost 3.6326 s
wall and 0.047892 s process CPU, plus a 0.237944 s call-path addendum. Known nested
software-research CPU through the matched workflows and recovery is 11.324128 s; CPU for
the interrupted prefix is unknown. Parent and nested costs are not added.

At the workflow readback, this phase held 823,523 logical artifact bytes in 136 files
and 132,460 new source bytes, within the 32 MiB and 2 MiB lane allocations. Free disk was
26,662,264,832 bytes, above the 5 GiB floor. Point readings do not bound unseen temporary
peaks. The five earlier failed-check files and the historical resource overrun remain
preserved.

The integrated pre-check read at command `826b7b56` measures a conservative
626,339,046 retained bytes, including inherited reserves, and 26,467,643,392 free disk
bytes. New retained payload is 1,523,166 bytes for execution and 544,312 bytes for
evaluation, each below 32 MiB. New source is 132,460 and 3,022 bytes respectively;
with the 139,534-byte coordinator packet, the phase uses 275,016 of 6 MiB and cumulative
known source is 4,374,474 bytes. The five earlier failed-check files remain unchanged.
Execution reserves 256 MiB of the shared 512 MiB temporary scope for one monitored
combined check. Evaluation has released its reservation.

The first monitored attempt on `d61ec2f` completed the underlying repository check:
864 tests, lint, 359 formatting checks and 114 documents passed. Its outer command
`b2fc52cd` then failed while annotating the resource receipt because phase fields are
nested under `baseline` for a full-check result. No sample trace was serialized, so no
peak is inferred. The [failed attempt](failed-full-check-001.json) is retained. The
application and tests are unchanged; a records-only wrapper correction precedes one
monitored retry, and the reservation remains active until that receipt exists.

The corrected monitored run `7400c134` passes on clean `1b9193b`: 864 tests in
243.20 s, lint, 359 formatting checks and 114 document checks; outer wall time is
258.216583 s. The 950 storage samples observe a 155,090,028-byte temporary peak;
626,420,694 baseline plus that peak is 781,510,722 bytes. No violation occurred,
minimum sampled free disk was 26,320,437,248 bytes, all five earlier failed files are
unchanged and the test root retains zero bytes. Sampling cannot bound unseen peaks.
The 256 MiB reservation is released.

A post-closeout audit found a phase-owned temporary checkout outside the monitor's
declared project roots. It held 176,944,824 bytes: the exact `2c82266` tree plus 24
generated Python bytecode files, with no unique experiment output. Adding it and two
small diagnostic readbacks to the contemporaneous baseline yields 958,483,829 bytes
including the sampled test peak, below 1 GiB; combined phase and test temporary use is
332,063,135 bytes, below 512 MiB. The reproducible checkout was released by command
`592e8fc4`; two diagnostics totalling 28,283 bytes remain. The
[resource supplement](resource-supplement-001.json) preserves the correction. The
post-release project snapshot is 626,652,189 bytes with 26,658,975,744 free disk bytes.
This changes no decision.

The phase used no physics, learned inference or training, model weights, paid/cloud
compute, hardware, reserved access, outreach, publication or push. All twenty reserved
incidents remain closed.
