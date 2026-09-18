# First execution interface

The typed JSON boundary is [records.py](../../src/nisayon/engine/records.py).
Schema `nisayon.first_case.v1` binds a case, qualification, plans, runs and an
optional confirmation. The [measured case](LIFT_FIRST_CASE.md) exercises this
development interface. It describes evidence; Fable's evaluator owns acceptance.

The additive [v2 protocol](LIFT_PROTOCOL_V2.md) keeps that input schema and adds
`record_contract: nisayon.execution.v2`, invocation and configuration identities,
actual acquisition metadata, an artifact manifest, complete assigned run IDs and
a cost-ledger reference. Historical v1 files are not reinterpreted as v2 records.

An [example run](example-run.synthetic.json) is explicitly synthetic. It shows
serialization only; its placeholder digests are not artifacts or measured facts.

Each run embeds a compact trace. Full numeric state, observations and recurrent
policy state are retained separately under `artifact_root`. Trace source run IDs
make the deliberately invalid replay visible: its next observations retain the
original run's identity. The evaluator must also challenge the execution code;
self-reported provenance and hashes do not establish physical truth.

The first case uses robomimic's frozen low-dimensional BC-RNN Lift policy
on CPU, with a gripper-sign integration regression, a sign correction and a
zero-action progress-loss control. This recurrent policy has no action chunks.
Qualification measures compatibility with the selected modern MuJoCo stack;
upstream's old model-zoo success rates are not this experiment's evidence.

The frozen predicates require: cube centre exceeds table
height by 0.04 m within 400 control steps; finite bounded normalized actions;
fresh simulator feedback each step; simulation step period 0.05 s. Host inference
latency is measured but this synchronous CPU simulation has no realtime claim.
Thirty-two fresh development seeds were declared after exploratory selection,
with the candidate and predicates frozen before any of those runs. All outcomes
are retained. This is not blinded evaluation.

Request to evaluation lane: use this shape, publish any required-field revision
before reliance, and own the acceptance/control predicates. The execution lane
has supplied complete local bundles and committed real records in the measured case.
