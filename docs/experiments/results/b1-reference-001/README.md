# A competent reference and the boundary of historical replay

**9 October 2026 · complete: observation reconstruction passes; unchanged policy transfer fails.**

All 59 recorded states reconstruct every selected observation byte for byte.
The public checkpoint nevertheless completes **0/10** fresh development tasks in
robosuite 1.5.1; all ten episodes execute normally. Its weights are unchanged.
The nominal and restored-target replay variants have maximum mixed-state
coordinate errors of 0.13009 and 0.19067 respectively. Restoring the controller
target does not recover the historical trajectory. All B1 slots are consumed.

The [verified readback](readback.json) binds 91 raw evidence files and all 4,119
control steps. A subsequent source comparison identifies a same-shaped semantic
change: the relative position in `object[7:10]` reverses direction between 1.4.1
and 1.5.1. Its task effect is a separate hypothesis tested in
[B2](../b2-semantic-transfer-001/README.md). B1's failure is preserved.

## Frozen procedure

A1 qualified the declared runtime but rejected its 100-update checkpoint at 1/10
task completions. B1 selects the already-held public Lift BC-RNN checkpoint that
worked in Nisayon's earlier robosuite 1.4.1 experiments. Its competence in the
dataset's 1.5.1 runtime must be measured. No new weights, training or environment
installation is needed. This is a single-lane, non-independent assessment.

The [protocol](protocol.json) binds source and input hashes, one attempt per mode,
the resource ceilings and ten new development seeds, 180000–180009. Freeze the
protocol and source in Git before any simulator operation. The local reservation
service must accept all ten conditions before policy execution. The completed A1
allocation remains consumed; B1 is a separate experiment under the operator's
instruction to continue toward a competent reference.

## Questions and tests

1. **Do recorded states reconstruct their observations?** Load the 59 states of
   already-exposed `demo_0` and record each observation. Execute only its final
   action, following the upstream extraction procedure. Require every selected
   observation coordinate to match within 1e-6 before policy qualification.
   This is observation reconstruction, not a replayed task completion.
2. **Does the controller's joint target explain dynamic divergence?** Run the
   same 59 recorded actions with nominal and restored-position targets. Both
   variants call the same controller refresh exactly once. Report full errors;
   neither hypothesis is selected for ordinary policy resets. The actual
   historical controller target is not retained, so a smaller error alone would
   not establish historical provenance or complete runtime equivalence.
3. **Is the public checkpoint competent here?** Execute ten fresh development
   episodes with unchanged weights, ordinary resets and a 400-step horizon.
   Require at least 8/10 successes and zero execution failures. Retain intended
   and clipped actions, consumed observations, states, task height, reward and
   all assigned outcomes. The clipping boundary matches the earlier qualified
   Lift deployment. Success means cube centre above table height plus 0.04 m;
   it does not establish sustained grasp or physical safety.

The model was trained **without observation normalization**. Even a successful
B1 qualification cannot supply evidence for a learned normalizer repair. It
would supply a competent reference for integration and runtime experiments.

## Source findings and limits

The dataset explicitly declares `lite_physics=false`; the newer default is not
an omitted configuration difference. The upstream
[observation extraction source](https://github.com/ARISE-Initiative/robomimic/blob/v0.5.0/robomimic/scripts/dataset_states_to_obs.py)
loads recorded states for intermediate observations and steps only the last
action. Its current implementation explains why matching observation metadata
need not imply dynamic trajectory equivalence. The acquired dataset's exact
generation invocation remains unproven. The
[reset wrapper](https://github.com/ARISE-Initiative/robomimic/blob/v0.5.0/robomimic/envs/env_robosuite.py)
performs a reset before XML restoration; A1's replay already performs that reset
at the call site. An extra reset is not justified by this source difference.

The [model zoo](https://robomimic.github.io/docs/model_zoo/robomimic_v0.1.html)
requires older package branches for its published benchmark. B1 does not import
that success rate. Local qualification, the published benchmark and full
historical fidelity remain separate questions. Source bodies and exact digests
are retained in the [source ledger](source-ledger.json).

## Execution and costs

Use the isolated interpreter recorded in the protocol with
`python -B -m scripts.experiments.run_b1_reference --protocol
docs/experiments/results/b1-reference-001/protocol.json --mode MODE --output
artifacts/b1-reference-001/MODE`. Run through the existing resource monitor and
`nisayon run`; monitor invocation records bind this B1 protocol, while the reused
monitor utility retains its older A1 schema label. Do not run bare simulator
commands or reuse an output directory.

The complete allocation permits 119 diagnostic control steps and at most 4,000
policy steps: 4,119 controls, at most 102,975 contract-counted physics substeps,
13 explicit resets and three XML resets. Constructors and state assignments are
counted separately; these API counts do not describe hidden internal operations.
The [preflight](preflight.json) verifies both unchanged environments and retained
assets. Command wall, sampled CPU/RSS, source bytes and simulator operations are
measured; engineer effort and provider cost remain unknown. No repair-efficiency
or competitive advantage is tested by this qualification.
