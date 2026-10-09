# Repository custody and next-investment decision

**Observed 22 September 2026.** The public research release is intact and the
private execution state is recoverable. No new scientific result is ready for
publication. The next useful operation is the smallest prospective completion of
the A1 runtime and competence gate, followed—only if the checkpoint is competent—by
one fixed-weight, task-level normalizer intervention against a fully capable
conventional workflow.

This is a repository and research-direction audit. It did not construct or reset a
simulator, execute a policy, consume an assigned attempt, train a model, or change an
experimental verdict.

## Repository readback

| Surface | Read back state |
|---|---|
| Private `main` | Clean `e4827080ffe170a339d44c70009cd87a02fb79df` before this audit |
| Execution lane | Clean `build/execution` at the same revision before this audit |
| Evaluation lane | Clean `build/evaluation` at `912e200cd487e0e1f31675d848206119d2cd4de8` |
| Public snapshot | Local `release/v0.1.0`, remote `main`, and dereferenced tag `v0.1.0` all equal `886710e819c218b89b61ea7a4899ef01d2f2cd24` |
| Public release | Published, neither draft nor prerelease; `validation.json` is 15,330 bytes with SHA-256 `d1e13bbc90b0c54ec1e9fbbc34f21aee4b07fab0d5fab000e92bbb46f5421d91` |
| Git integrity | All six worktrees were clean; the release worktree passed `git fsck --full --no-dangling` |
| Attribution | The current private and public tips retain Daniel Wahnich's configured identity; no assistant trailer was introduced |

The public repository is current for the declared **0.1.0 source-snapshot release**.
It is intentionally not a mirror of private `main`. The private branch has 614 commits
not reachable from the public snapshot, plus private settings, memory, research records
and execution code that
the [release boundary](../../../RELEASE.md) expressly excludes. Pushing private
`main` would violate that boundary. No push, tag movement, release edit or package
publication occurred in this audit.

The unresolved A1 line does not justify a new public release yet. A later release may
publish a supported or negative adjudicated result, but it must again be built as a
reviewed source snapshot without datasets, checkpoints, simulator stores, private
history or client state.

## Private evidence custody

The committed records and the ignored payloads answer different questions. Git
retains the protocols, receipts, digests, failures and decisions. The large or
rights-sensitive bytes remain outside Git in the execution worktree.

| Object | Retained bytes | SHA-256 read back on 22 September |
|---|---:|---|
| Rights-qualified Lift PH dataset | 21,084,088 | `2067777cb8b532e9263dd09fd6448c41cc31224bb27be4a3b734010ae13eb540` |
| robosuite 1.5.1 wheel | 152,011,410 | `39810a9e9f193455fcb13a9b4846424abef77481ac3091892c2077c88dcdc153` |
| A1 inference checkpoint | 7,961,224 | `bef2eb39bf2bdc873a03ba85e946a3e4e5383efcb870ff1a45816b76f24ef532` |
| Sealed A1 packet identity | 1,381 | `5c0e4deba795a9d6364856bbe3f8cfdb54a6e966c61fd2495eb39aa92becc3f2` |

The failed runtime command's `run.json`, stdout and empty stderr are also present at
`.nisayon/runs/a0028c7bf2f548ea97539cd9ba150e40/`; their current digests are bound in
[`audit.json`](audit.json). The execution worktree currently allocates 11,913,084 KiB
under `artifacts/` and 1,725,524 KiB under `.nisayon/`. The data volume reported
13,329,272 KiB available, above the frozen 5 GiB floor. No cleanup was needed. Deleting
evidence merely because the filesystem reports 99% utilization would be the wrong
trade: current headroom is adequate for the already bounded restart, and the large
runtime is part of the retained execution state.

These checks establish **local custody and integrity, not backup durability**. No
off-machine backup of the ignored checkpoint, packet, wheel, dataset or raw run store
was verified. Uploading those objects would cross the private-distribution and
third-party-rights boundary, so this audit did not improvise a remote backup. The
public dataset and wheel can be reacquired by their pinned identities; the derived
checkpoint and sealed packet cannot be called remotely recoverable without a separate
private backup decision.

## Scientific position

The A1 pilot supports lawful custody of the selected public object, offline data and
implementation compatibility, effective observation normalization, 100 finite CPU
optimizer updates, a changed model state, checkpoint serialization, state recovery,
and feasibility for that measured workload. It does not support resumable training,
simulator compatibility, policy competence, a task repair or comparative value.

The first runtime probe constructed robosuite and completed one explicit reset. A
producer object-key mapping error then stopped it before `env.step`. The corrected
source exists, but the failure consumed the only originally assigned probe reset.
There were zero control steps, policy actions, replay attempts or development
episodes. Runtime compatibility and competence therefore remain unresolved.

The pasted `912e200` wheel receipt is genuine but historical. It verifies custody and
rights; it is not the prospective reset amendment required after the failed probe.
Running again under the old v1.3 ceiling would erase or exceed a counted operation.

Daniel has now asked Codex to be the only active lane. That changes coordination, not
the meaning of independence. A Codex-authored contract and Codex-reviewed packet can
support a prospectively controlled **single-lane** result; it cannot be described as
an independent evaluation. The clean options are:

1. retain the current gate until a genuinely separate evaluator freezes the narrow
   reset amendment and later assesses the sealed packet; or
2. explicitly supersede only the ownership and independence terms, freeze a
   machine-checkable solo amendment before execution, and label every resulting
   assessment producer-owned and non-independent.

Either option must retain the failed reset, add exactly one replacement
qualification-only construction/reset, move qualification and phase reset totals from
3/15 to 4/16, and leave every step ceiling, threshold, seed, assignment, no-retry rule
and resource limit unchanged.

## What the current frontier changes—and what it does not

The external review used primary project and paper sources available on 22 September
2026:

- [robomimic v0.4](https://github.com/ARISE-Initiative/robomimic/releases/tag/v0.4.0)
  added upstream robosuite 1.5 compatibility. The latest
  [robomimic v0.5 release](https://github.com/ARISE-Initiative/robomimic/releases/tag/v0.5.0)
  adds Diffusion Policy, action normalization, multi-dataset training and resumable
  training, but explicitly breaks loading observation statistics from old checkpoints.
  That makes v0.5 a candidate for a **new** policy line, not a silent migration of A1.
- [robosuite 1.5](https://github.com/ARISE-Initiative/robosuite/releases/tag/v1.5.0)
  introduced composite controllers, and 1.5.2 is now the upstream latest release.
  The current A1 contract is bound to 1.5.1 and its dataset metadata. Upgrading during
  qualification would change the question; 1.5.2 needs its own prospective contract.
- [SIMPLER](https://proceedings.mlr.press/v270/li25c.html) reports more than 1,500
  paired simulation/real evaluations across two embodiments and eight task families,
  while identifying control and visual disparity as the central validity problem.
  It is a strong later transfer substrate, not evidence that this Lift runtime is a
  real-world proxy.
- [LIBERO-Plus](https://arxiv.org/abs/2510.13626) reports large drops under controlled
  changes to camera, initial state and other conditions. Nominal success alone is
  therefore too weak for a deployment claim.
- [FAIL-Detect](https://www.roboticsproceedings.org/rss21/p073.html) treats runtime
  failure detection as sequential out-of-distribution detection with conformal
  uncertainty. It suggests a useful later comparator for detection, but it does not
  answer whether Nisayon improves repair decisions.
- [CoVer-VLA](https://arxiv.org/abs/2602.12281) reports that test-time verification can
  outperform additional policy training on its studied VLA tasks. That supports the
  importance of verification while raising the bar: Nisayon must measure its own
  incremental decision quality or complete cost against an equally informed verifier.
- [AutoEval](https://github.com/zhouzypaul/auto_eval) demonstrates a distributed
  policy/evaluation service with learned success detection for real robot tasks. It is
  a plausible future external confirmation surface, but using hardware or its service
  would require separate authority and a new safety and cost contract.

The implication is not “adopt the newest stack.” Finish the pinned falsification
question without changing its meaning. Then establish external validity and a real
decision advantage on a separately frozen line.

## Ranked next investment

### 1. Close A1 without tuning

Freeze the narrow reset amendment under one of the two ownership choices above. Run
only the corrected 20-step probe on new create-only paths. If it passes, run the two
seed-900 reset witnesses; then R-1/R-2; then exactly E-200…E-209. Seal before reading
comparative summaries. Preserve the existing 8-of-10 competence threshold. Do not
change the checkpoint, normalizer, horizon, seed or adapter after seeing outcomes.

This is the best immediate investment because every required input and executor is
already held, the resource envelope is measured, and the result decides whether A1 can
support any task-level experiment at all.

### 2. If A1 is competent, run one causal intervention—not another inventory

Hold policy weights, runtime, controller, reset conditions and seeds fixed. Change only
the effectively read normalizer statistics. Measure the complete chain separately:

`numeric map -> policy action -> closed-loop trajectory -> task outcome -> fresh confirmation`

Give the competent conventional arm the same bytes, arithmetic, shortcuts, stopping
rules and confirmation obligation. Its decisions must be computed from inputs rather
than encoded from candidate labels. Report decision errors and full cost, including
checking overhead and failures. A changed action is not a repair, and a successful
episode is not confirmation.

The strongest falsifiable value hypothesis is narrow: **can Nisayon reject an invalid
or irrelevant deployment candidate early enough to avoid a costly wrong confirmation,
without increasing false rejection or weakening fresh confirmation?** Prefix action
equality cannot justify skipping a closed-loop rollout. A safe skip requires a stated
sufficient condition covering the whole claimed trajectory, including policy state,
controller state, randomness and numerical behavior. Give that same condition to the
conventional arm; parity is the expected result when the shortcut is ordinary.

### 3. If A1 is not competent, stop using it as a value-test vehicle

Report the frozen result. Do not continue until success or tune on E-200…E-209. Prepare
one bounded continuation with a fixed optimizer-update budget, development-only
selection rule and untouched evaluation conditions. If a stronger policy is needed,
start a new upstream line—robomimic v0.4 for the smallest compatibility migration, or
v0.5 Diffusion Policy for a stronger baseline—with new checkpoint and normalizer
identities. Never reinterpret a v0.5 conversion as continuation of A1 because upstream
states that old observation-normalization statistics are incompatible.

### 4. Move the value claim to an independently authored incident

A constructed Lift intervention can prove mechanics, not prevalence or product value.
After the A1 gate, select one executable external integration failure before observing
candidate outcomes. Use a simulator whose evaluation relationship is itself measured,
or later an authorized AutoEval-style real system. Freeze perturbation families,
success and progress predicates, confirmation conditions, complete costs and the
conventional arm prospectively. The original external-incident objective remains
outstanding until this happens.

## Stop rules

- A material corrected-probe defect stops compatibility; fix only the smallest named
  mechanism under a new amendment.
- Fewer than 8 successes in the ten frozen development episodes rejects competence for
  this checkpoint. It does not reject the runtime.
- If Nisayon and the competent conventional workflow make the same valid decision at
  equivalent complete cost, preserve parity and retire the current value mechanism.
- If a rollout-skipping proof costs as much as the confirmation it avoids, or only
  covers sampled observations, reject the saving claim.
- With no valid confirmed repair, cost per confirmed repair remains undefined.

The high-ambition path is therefore disciplined: close the smallest unresolved
execution gate, run one outcome-bearing intervention, and then demand an external case
where Nisayon changes a decision or its complete cost. More metadata, more test counts
or a newer model are not substitutes for that evidence.
