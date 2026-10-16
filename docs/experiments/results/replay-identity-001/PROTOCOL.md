# N033: qualify the conventional replay baseline

13 October 2026. Frozen after source inspection, before native execution.

## Decision and alternatives

Nisayon still needs an independently owned correction with complete comparative
costs (N015). Another runtime, learner or collection of patches does not supply
that evidence. Qualify one existing replay implementation before proposing our
own. Use Retriever as a potential conventional baseline, not as a straw man.

[Retriever v1](https://arxiv.org/html/2607.17213v1), published 19 July 2026,
provides flows, explicit clocks and synchronization policies. Its determinism
theorem fixes initial state, committed external histories, clock/commit trace,
lag decisions and stochastic seeds or outputs; feedback must be strictly causal.
It does not promise arbitrary live schedules or counterfactual robot outcomes.
The paper reports controlled replay studies and a real-robot case study; neither
is replicated here.

The released [source](https://github.com/openretriever/retriever/tree/b0d766329c045b33eacf5e978e0279f277f7d558)
contains a sequential replay helper and native MCAP recording. Inspection shows
that the helper discards stored timestamps, while the whole-session reader
associates outputs with the first step within one millisecond. These are
hypotheses about the qualification boundary, not measured results. Sequential
replay is documented; requiring the caller to restore clocks is not a defect.

Alternatives: duplicate the runtime (defer); launch policy training (outside
allocation); keep sending incident requests (no new reason to repeat them);
test whether an existing recording preserves the identities needed for a
decision (execute). The recommended company milestone remains N015.

## Experiment and falsifiers

Use unchanged, fully imported Retriever code at the pinned revision, Python
3.12 and a separate minimal CPU environment. No extracted function bodies,
learned policy, robot, simulator, GPU or cloud resources. Lock dependencies and
retain environment, source, commands, raw outputs and all failed attempts.

1. Record three native pipeline steps with two distinct output streams. Compare
   exact output-to-step identity and step metadata through MCAPReader. Check
   100 ms, 4 ms, 1 ms, 0.5 ms and 0.1 ms spacing, repeated timestamps, and two
   additional controls containing missing output fields or no outputs. Repeated
   timestamps test the recording API, not the theorem's strictly ordered stream
   premise. Values and step identities, not approximate timestamp equality, are
   the oracle. Inspect the separate per-node reader on the same files to
   distinguish serialization loss from incorrect session reconstruction.
2. Replay a three-value source under its recorded irregular clock, then under
   a uniform clock. A deterministic timing-sensitive consumer must reproduce
   under the original clock. A changed decision under the uniform clock shows
   why value equality alone is insufficient. Run an insensitive consumer as a
   control. This is a constructed software obligation, not robot performance.
3. If session reconstruction fails while the per-node streams retain the
   values, make the smallest compatible reader correction. Prefer existing
   persisted step boundaries to another timestamp tolerance. Keep writer and
   replay semantics unchanged. Rerun the same controls and relevant upstream
   runtime/recording tests. These exposed controls are regressions, not fresh
   independent confirmation. A timestamp-only alternative must face the
   repeated-timestamp control.

Reject the baseline qualification if original-clock replay fails. Reject a
reader correction that changes well-separated outputs, loses explicit missing
values, misassigns a step, or needs a new file format. If both native readers
lose values, revisit serialization before blaming the join. If no defect is
observed, retain that result and do not manufacture a report. Do not infer an
asynchronous-backend guarantee from a stepped CPU fixture.

## Acceptance, resources and next dependency

Acceptance is exact native round-trip identity in the declared controls, a
reproduced clock-sensitive decision with the original schedule, passing relevant
upstream checks, and explicit scope. A supported small defect may receive one
focused upstream contribution under standing authority, after full thread and
source readback. Acceptance/adoption remains unknown until an owner responds.

Cap this source qualification at four hours of engineering and local CPU work.
Record command durations separately from elapsed investigation; owner review,
integration, maintenance and customer time remain unknown. Stop at a concrete
result. No Nisayon runtime adapter or product subsystem is authorized by this
protocol. The next advantage test requires an owner decision and matched costs.
