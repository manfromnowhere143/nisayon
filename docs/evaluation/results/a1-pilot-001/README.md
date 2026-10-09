# a1-pilot-001 · evaluation lane report

**21 September 2026 · phase start 09:38:59 UTC.** Acceptance criteria frozen before any
output ([`PILOT_ACCEPTANCE.md`](PILOT_ACCEPTANCE.md), 09:41 UTC); independent verdict
after the execution lane sealed its packet ([`PILOT_VERDICT.md`](PILOT_VERDICT.md),
10:08 UTC, seal-aware disposition 10:15 UTC); commands under [`commands/`](commands/index.json).

The pilot stopped at the rights gate before any dataset byte: the MIT-declared official
object and the pinned Stanford v1.4.1 object have different lengths, so their identity is
impossible and the retained terms cannot be bound to the pinned bytes. This lane
reproduced that decision from labelled copies of the retained responses with its own
parsing. Custody, executability and resource feasibility are unresolved; nothing was
trained, rolled out or decided; the original objective stays outstanding. The recommended
next step is one retained request for terms covering the Stanford host, then, under a new
authorization, the MIT-declared object with a compatibility check as the first stop rule.

## Continuation (10:21 UTC): scope correction, amendment and a training-path finding

Daniel's continuation authorized freezing a prospective amendment that substitutes a
rights-qualified public artifact. [`pilot-verdict-003.json`](pilot-verdict-003.json)
corrects the earlier wording (non-identity by length, no digest compared, only the
identity route closed) and keeps the original result. A control run through the pinned
training path with no dataset shows that robomimic 0.3.0 cannot apply observation
normalization to batched BC-RNN inputs, so the pilot needs a declared training-only
override before its first update. [`A1_AMENDMENT.md`](A1_AMENDMENT.md) binds the
MIT-declared repository object, the corrected training path, the 100-update contract
and the acceptance checks. Amendment v1.1 adds a second finding, double normalization in the pinned loop, and requires
a single application proved at batch level. Nothing under the amendment has run; the
amended pilot is prepared, not assessed.

## Assessor prepared (11:25 UTC)

`uv run --frozen python -m nisayon.evaluation a1-assess STORE --reference
acquired-reference-002.json --dataset PAYLOAD` reads a sealed packet without editing it,
verifies the seal and manifest, and grades Q1 to Q6 from evidence found by content:
acquisition receipt and payload digest, membership against the pre-output reference,
the override conformance control and an explicit no-environment statement, the
checkpoint's statistics against the float32 emulation at the frozen tolerances, a first
batch recomputed as a single application, one hundred finite per-update losses with a
parameter-change record and a CPU device, a reload witness, and costs with the packet's
bytes against the 16 MiB durable cap. Anything absent is reported as unresolved with the
item named; nothing is inferred from a flag. Three synthetic packets (empty, complete,
defective) exercise it in the tests. The action-bounds wording of the pre-output
reference is stated as measured signed bounds in
[`acquired-reference-002.json`](acquired-reference-002.json); reference 001 is unchanged.

## Executed pilot assessed (11:51 UTC)

The single reserved run executed all 100 updates and was sealed; the frozen assessor and
this lane's references assess it in [`PILOT_ASSESSMENT.md`](PILOT_ASSESSMENT.md) and
[`pilot-assessment-readback-001.json`](pilot-assessment-readback-001.json): permission
for the substitute object, offline compatibility, effective normalized training,
checkpoint state recovery and bounded resource feasibility are supported; simulator
compatibility, competence and any intervention are untested; comparative value is
unproven. One witness against this lane's own reference is dispositioned, with the first
assessment retained as before-evidence. The next experiment is prepared, not authorized.

## Integration verified (12:09 UTC)

Private main `f5d249f` holds the assessment under rebased hashes (`5a0954e`→`4ee6a58`,
`7a3e32a`→`318422a`; patch-identical, identity preserved) and the execution lane's
readback 002 with combined validation at `f04985e`. The one-time check is
[`integration-verification-001.json`](integration-verification-001.json).
