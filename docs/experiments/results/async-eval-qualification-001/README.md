# Preserve the episode that actually ran

**12 October 2026 · N023: supported native regression coverage; economic value unresolved.**

An evaluation can finish, report a successful episode, and retain an observation
from a different episode. The native checks here reproduce both forms of evidence
contamination in LeRobot. The scoring correction already belongs to upstream
[PR #4485](https://github.com/huggingface/lerobot/pull/4485). The additional
[terminal-observation correction](terminal-observation.patch) preserves the
episode's actual last state and camera frame without changing live policy inputs.
The combined candidate passes **41 checks with zero skips**.

This is a concrete increase in automated coverage against the selected upstream
tests. It does not demonstrate cheaper work than a competent engineer or agent,
an autonomous detector, customer adoption, or physical task improvement.

## Selection and result

The [intake readback](intake.json) found no new outside responses on nine pending
requests or the earlier LeRobot review. One new change, [PR #4932](https://github.com/huggingface/lerobot/pull/4932),
was selected by title before reading its body or source. The [plan](plan.json)
bounded inspection to this evaluator change and four engineering hours. It
reuses the native testing approach from N021; the deterministic tests are
source-informed development controls, not a blind benchmark.

PR #4932 fixes worker registration and optional task-attribute probing. Its head
is `d6db556a7552b32e1f24d1ee1a71587ceee22c24`, with base
`b9cb121cb7d4e3e26ec5c906d08dda68d151ba52`. The three new upstream async tests
fail on the base and pass on the PR. The separate recording defect exists in
both revisions. The original author reports a Jetson PushT run; this work does
not replicate that robot-policy experiment.

| Source | 13 selected upstream checks | 24 state, metric and lifecycle controls | 4 nested-image controls |
|---|---|---|---|
| Base `b9cb121` | 10 pass, 3 fail | 13 pass, 11 fail | Not run |
| PR #4932 `d6db556a` | 13 pass | 16 pass, 8 fail | 2 pass, 2 fail |
| PR #4932 plus upstream #4485 | Not rerun separately | 20 pass, 4 fail | Not run |
| Both upstream changes plus terminal-observation correction | 13 pass | 24 pass | 4 pass |

There are 41 distinct final checks and 143 valid test executions across these
variants. Those executions are neither independent incidents nor robot trials.
[Evidence](evidence.json) binds results, failure messages, commands, source files,
costs and limits. Individual result JSON files retain test names and runtime
metadata. The original [24 controls](controls.json) were frozen before execution
and remained byte-identical throughout.

## What crosses the episode boundary

Gymnasium 1.4.0's `SAME_STEP` mode returns the next episode's reset observation
when an environment terminates or truncates. It places the actual terminal
observation in `info["final_obs"]`. The evaluator previously appended the returned
reset observation; `_compile_episode_data()` included it in the finished episode.

The [unchanged witness](head-witness.json) records `[41, 141]` for an episode
that starts at 41 and applies target 42. The correct trajectory is `[41, 42]`.
Its longer companion records `[42, 43, 44, 142]` instead of
`[42, 43, 44, 45]`. The extra 100 belongs to the subsequent reset. The same
problem affects nested RGB observations. `NEXT_STEP` controls pass.

The correction builds the recorded successor from Gym's terminal observation,
using the declared observation space to assemble the batch. Live inference
continues to receive the reset observation. The [corrected witness](candidate-witness.json)
has the expected saved sequences and exactly the same policy inputs as the
unchanged run. Actual environment steps recompute their states from supplied
actions; future observations are never replayed after changing an action.

The metric defect includes a step beyond the first cumulative `done`, and padded
zeros can dominate negative reward maxima. In this native fixture it turns one
failed and one successful original episode into a reported 2/2 successes. The
unchanged [upstream correction](upstream-4485.patch), by CoffeeDrivenCoder at
`f689403357200e6c31f43fc6b5b77ae850693962`, restores 1/2 and the correct rewards.
It leaves the terminal-observation failures intact. This confirms and composes
existing upstream work; it does not claim that diagnosis or correction as ours.

## Scope, failed attempts and costs

[test_episode_contract.py](test_episode_contract.py) uses a scripted CPU
`PreTrainedPolicy`, real linked relative/absolute processors, native
`eval_policy → rollout → env.step`, and Sync/Async Gym environments. It checks
task-attribute priority, worker survival, unequal episode lengths, termination,
truncation, seeds, processor reuse, exact actions, metrics and saved observations.
The async path uses `forkserver`, matching the upstream factory.
[test_terminal_images.py](test_terminal_images.py) additionally checks nested RGB
arrays through the native channel conversion and scaling. No evaluator,
processor, converter or worker implementation is replaced.

The initial image extension used 2×2 RGB arrays. Both source variants rejected
that unsupported layout before the terminal assertions: eight invalid fixture
executions, retained separately and excluded from the table. The
[corrected fixture record](image-controls-corrected.json) freezes 64×96 arrays
before reexecution; the original [plan](image-controls.json), bytes, logs and
failures remain available. Neither the source correction nor the 24 original
controls changed to obtain the image result.

A new environment contains Python 3.12.13, Torch 2.11.0, Gymnasium 1.4.0 and 70
hash-locked dependency packages. The first installation reused the older native
lock, and `pip check` rejected filelock 4.1.1 against this source's `<4` bound.
The new [lock](requirements.lock) selects filelock 3.32.7 while constraining every
other dependency to its retained version. Final `pip check` passes. The existing
86-package Nisayon environment, its Python, lock and environment configuration
remain unchanged; no retained environment was synchronized.

The complete base and head archives contain 1,212 and 1,213 original files.
Every original byte remains unchanged. Both correction variants differ from
the head in only `src/lerobot/scripts/lerobot_eval.py`. Head is installed normally;
explicit `PYTHONPATH` selects each full source tree, and the runner checks actual
import locations and hashes. This is native execution, not selected source-body
extraction. [Sources](sources.json) bind archives, metadata, reviews, duplicate
searches and installed Gym contract code.

Valid native test commands total **539.292 seconds of process wall time**;
some independent processes overlapped. Selection to the evidence checkpoint
took **1,059.666 seconds of session elapsed time**, excluding earlier intake
and later delivery/closeout. Installation, invalid attempts and readbacks add
cost and are retained separately. These are engineering cost records, not a
speed comparison. Human integration/review time, provider charges and future
maintenance remain unknown. No GPU, cloud resource, physics simulator, learned
checkpoint or hardware was used. Existing codec-library and pytest-plugin
warnings remain in the logs; video encoding is unqualified.

## Reproduce in a separate environment

From this checkout, create a new directory. The lock targets macOS arm64 and
Python 3.12.13; other profiles need separate qualification.

```sh
QUAL_CHECKS="$PWD/docs/experiments/results/async-eval-qualification-001"
QUAL_LAB=$(mktemp -d /tmp/nisayon-episode-check.XXXXXX)
curl --fail --location --output "$QUAL_LAB/source.tar.gz" \
  https://codeload.github.com/huggingface/lerobot/tar.gz/d6db556a7552b32e1f24d1ee1a71587ceee22c24
printf '%s  %s\n' \
  7b4c70160dab1404a9fd4f75a6a1b938501924657227a83c621efbbca518c0b9 \
  "$QUAL_LAB/source.tar.gz" | shasum -a 256 -c -
tar -xzf "$QUAL_LAB/source.tar.gz" -C "$QUAL_LAB"
QUAL_SRC="$QUAL_LAB/lerobot-d6db556a7552b32e1f24d1ee1a71587ceee22c24"
uv venv --python 3.12.13 "$QUAL_LAB/venv"
uv pip sync --python "$QUAL_LAB/venv/bin/python" --require-hashes \
  --only-binary :all: "$QUAL_CHECKS/requirements.lock"
uv pip install --python "$QUAL_LAB/venv/bin/python" --no-deps \
  --no-build-isolation -e "$QUAL_SRC"
uv pip check --python "$QUAL_LAB/venv/bin/python"
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1
export HF_HOME="$QUAL_LAB/hf-cache"
export PYTHONPATH="$QUAL_SRC/src:$QUAL_SRC:$QUAL_CHECKS"
"$QUAL_LAB/venv/bin/python" "$QUAL_CHECKS/run_checks.py" \
  --source "$QUAL_SRC" --upstream-tests "$QUAL_SRC" --group upstream \
  --output "$QUAL_LAB/head-upstream.json"
"$QUAL_LAB/venv/bin/python" "$QUAL_CHECKS/run_checks.py" \
  --source "$QUAL_SRC" --upstream-tests "$QUAL_SRC" --group contract \
  --output "$QUAL_LAB/head-contract.json"
"$QUAL_LAB/venv/bin/python" -m pytest -q --timeout=40 \
  "$QUAL_CHECKS/test_terminal_images.py"
```

Expect 13 passes, then eight failures/16 passes, then two failures/two passes.
Collection/import failures do not match that reproduction. Copy the source and
apply the two retained patches to the copy:

```sh
cp -R "$QUAL_SRC" "$QUAL_LAB/candidate"
patch -d "$QUAL_LAB/candidate" -p1 -i "$QUAL_CHECKS/upstream-4485.patch"
patch -d "$QUAL_LAB/candidate" -p1 -i "$QUAL_CHECKS/terminal-observation.patch"
export PYTHONPATH="$QUAL_LAB/candidate/src:$QUAL_SRC:$QUAL_CHECKS"
"$QUAL_LAB/venv/bin/python" "$QUAL_CHECKS/run_checks.py" \
  --source "$QUAL_LAB/candidate" --upstream-tests "$QUAL_SRC" --group upstream \
  --output "$QUAL_LAB/candidate-upstream.json"
"$QUAL_LAB/venv/bin/python" "$QUAL_CHECKS/run_checks.py" \
  --source "$QUAL_LAB/candidate" --upstream-tests "$QUAL_SRC" --group contract \
  --output "$QUAL_LAB/candidate-contract.json"
"$QUAL_LAB/venv/bin/python" -m pytest -q --timeout=40 \
  "$QUAL_CHECKS/test_terminal_images.py"
```

Expect 13 + 24 + 4 passes, zero skips. Raw execution records and the isolated
environment remain under `artifacts/async-eval-qualification-001`.

## Delivered and next decision

One [technical review](https://github.com/huggingface/lerobot/pull/4932#pullrequestreview-5489640347)
contains the terminal-only patch and both executed test files, with upstream
credit and explicit limitations. Exact author, commit, body and review ID were
read back; see the [delivery receipt](review.json). No repository commit was
published and no new incident request was sent.

This earns a reusable regression for a second source change. It does not yet
earn a generic platform or a commercial advantage. Respond to maintainer evidence
or changed source, then measure adoption/review and repeat-use costs. N015 still
requires an owner's consequential decision and a fair comparison against their
strongest existing workflow. Do not repeat these exposed fixtures as fresh
confirmation or count delivery as acceptance.
