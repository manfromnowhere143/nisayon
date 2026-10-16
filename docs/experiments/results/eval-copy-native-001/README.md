# Connected processor copies through the native evaluator

**11 October 2026 · supported CPU software regression; product value unresolved.**

The linked-processor defect in LeRobot [PR #4450](https://github.com/huggingface/lerobot/pull/4450)
survives normal package imports and the full evaluator call chain. At
`ca864ff1c7727d15ea4bc6c5f1e21b105633a473`, the unchanged PR fails four of thirteen
checks. Applying only the previously proposed
[connected-context copy](../eval-copy-graph-001/candidate.patch) passes all thirteen,
with no skips. Fresh parallel pipelines raise a missing-state error; previously
used parallel pipelines apply `[101, 0.25]` where `[11, 0.25]` is required.

This extends the [earlier source audit](../eval-copy-graph-001/README.md), which
selected source definitions and substituted the task callback. The current
result closes that specific integration gap. It does not establish learned
policy performance, GPU compatibility, physical safety, or customer savings.

## Executed checks

| Check group | Unchanged PR | Connected copy |
|---|---|---|
| Three existing upstream evaluator tests | 3 pass | 3 pass |
| Six linked-pipeline and worker controls | 2 fail, 4 pass | 6 pass |
| Four native rollout controls | 2 fail, 2 pass | 4 pass |
| Total | 4 fail, 9 pass | 13 pass |

[test_linked_processors.py](test_linked_processors.py) uses the real processor
pipelines, converters, worker factory and task dispatcher. It substitutes only
`eval_one` with a scripted callback to inspect identities, independent tensor
storage, original-state preservation, and worker reuse under barrier-controlled
overlap. Sequential, disabled-relative and uncopyable-policy controls pass in
both variants. Both fresh and previously cached parallel controls fail in the
unchanged PR.

[test_native_rollout.py](test_native_rollout.py) replaces no evaluator,
processor, converter or Gym implementation. It exercises
`eval_policy_all → run_one → eval_one → eval_policy → rollout` with a scripted
`PreTrainedPolicy` subclass and native `SyncVectorEnv` instances. Each of four
tasks runs two deterministic three-step episodes. An environment applies the
absolute action and computes its next observation from that resulting state.
Every expected joint target and excluded gripper value is checked. Fresh and
previously cached sequential cases pass in both variants; both parallel cases
require the connected copy. The fixture's rewards and success flags are test
data, not robot-performance measurements.

The baseline's full-rollout cached-state failure records actual action
`[101, 0.25]` versus expected `[11, 0.25]`. The fresh-state failure reaches
`AbsoluteActionsProcessorStep` through the actual rollout stack. The candidate
restores the required actions without changing any other upstream source file.

The [baseline](baseline.json), [candidate](candidate.json), and
[evidence receipt](evidence.json) retain test identities, failure messages,
module hashes, installed versions and known costs. The initial nine-check run
also reproduced two failures and seven passes; it is retained separately and
is not pooled into the thirteen-check result. Controls and the rollout extension
were recorded before their execution. These are deterministic regressions, not
an independent statistical confirmation of a model.

## Environment and custody

The complete pinned upstream archive contains 1,035 files and 15,628,859 file
bytes. Every extracted baseline file was checked against the archive. The
candidate changes only `src/lerobot/scripts/lerobot_eval.py`. Normal imports
resolve to the selected installed source tree; no AST extraction, package stubs
or skipped dependency imports supply the native result.

A separate macOS arm64 environment uses Python 3.12.13, PyTorch 2.11.0,
torchvision 0.26.0, Gymnasium 1.4.0 and pytest 9.1.1. The 70 dependency packages
are installed from [requirements.lock](requirements.lock) with required hashes;
LeRobot is installed separately from the pinned source without dependency
resolution or build isolation. The lock selects base, dataset, evaluation and
test dependencies from the PR's metadata, rather than upstream's every-extra
profile. Both installed variants pass `uv pip check`.

All test tensors use CPU. Upstream's conftest prints its automatically detected
`DEVICE='mps'`; these selected tests do not use that fixture device. Native logs
retain an already-imported pytest-plugin warning and duplicate AVFoundation
class warnings from OpenCV/PyAV. Video capture and codecs are outside the checks.
This is one macOS dependency profile, not a Linux/GPU compatibility result.

The retained Nisayon environment's Python version, 86 installed package/version
pairs, `pyvenv.cfg` hash and repository lock hash match the pre-install snapshot.
No installation targeted either retained research environment. No model weights,
datasets, cloud resources or hardware were used. Raw archives, environments,
JUnit reports, stdout/stderr and command receipts remain under
`artifacts/eval-copy-native-001`; their relevant hashes are retained here.

## Reproduce

Run from the Nisayon execution worktree. This creates a separate temporary
environment; it does not synchronize the existing research environments. The
lock was resolved for macOS arm64 and Python 3.12.13. Other platforms require
their own recorded resolution and qualification.

```sh
COPY_CHECKS="$PWD/docs/experiments/results/eval-copy-native-001"
COPY_PATCH="$PWD/docs/experiments/results/eval-copy-graph-001/candidate.patch"
COPY_LAB=$(mktemp -d /tmp/nisayon-copy-native.XXXXXX)
curl --fail --location --output "$COPY_LAB/upstream.tar.gz" \
  https://codeload.github.com/huggingface/lerobot/tar.gz/ca864ff1c7727d15ea4bc6c5f1e21b105633a473
printf '%s  %s\n' \
  99d765f5b47c8b19d4630ef1cfc692c373fa790dac2ba5083d6e6461f5dfd6c2 \
  "$COPY_LAB/upstream.tar.gz" | shasum -a 256 -c -
tar -xzf "$COPY_LAB/upstream.tar.gz" -C "$COPY_LAB"
COPY_SOURCE="$COPY_LAB/lerobot-ca864ff1c7727d15ea4bc6c5f1e21b105633a473"
uv venv --python 3.12.13 "$COPY_LAB/venv"
uv pip sync --python "$COPY_LAB/venv/bin/python" --require-hashes \
  --only-binary :all: "$COPY_CHECKS/requirements.lock"
uv pip install --python "$COPY_LAB/venv/bin/python" --no-deps \
  --no-build-isolation -e "$COPY_SOURCE"
uv pip check --python "$COPY_LAB/venv/bin/python"
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HOME="$COPY_LAB/hf-cache" PYTHONPATH="$COPY_SOURCE" \
  "$COPY_LAB/venv/bin/python" "$COPY_CHECKS/run_checks.py" \
  --source "$COPY_SOURCE" --output "$COPY_LAB/baseline.json"
```

The baseline must return exit code 1 with the four specified failures and nine
passes. An import, collection or unrelated assertion failure is not a matching
reproduction. After inspecting that result, apply the one-file correction to a
second tree and repeat the same checks:

```sh
cp -R "$COPY_SOURCE" "$COPY_LAB/candidate"
patch -d "$COPY_LAB/candidate" -p1 -i "$COPY_PATCH"
uv pip install --python "$COPY_LAB/venv/bin/python" --no-deps \
  --no-build-isolation -e "$COPY_LAB/candidate"
uv pip check --python "$COPY_LAB/venv/bin/python"
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  HF_HOME="$COPY_LAB/hf-cache" PYTHONPATH="$COPY_LAB/candidate" \
  "$COPY_LAB/venv/bin/python" "$COPY_CHECKS/run_checks.py" \
  --source "$COPY_LAB/candidate" --output "$COPY_LAB/candidate.json"
```

The candidate must return exit code 0 with thirteen passes and no skips.
[run_checks.py](run_checks.py) verifies imported module locations and records
their hashes before running the tests with upstream's conftest and pytest
configuration. No downloads are requested during testing.

## Delivered and next decision

The existing [technical review](https://github.com/huggingface/lerobot/pull/4450#pullrequestreview-5483662010)
has a dated native-validation addendum and both executed regression files.
The original source-level report is preserved. Exact author, body, review ID
and commit were read back; the [receipt](review.json) also retains the failed
REST edit and successful authorized GraphQL edit. No additional review or
intake request was posted.

The original shared-state diagnosis and per-worker design belong to the
upstream authors. This work supplies the linked-processor counterexample and
its native regression. Maintainer acceptance, a rebased integration, arbitrary
policy copy behavior, per-worker model-memory cost and repeated owner use
remain unverified. N015 still needs a source-bound owner decision and complete
comparative costs. Further work here should respond to changed source or
maintainer evidence; these passing checks do not justify a generic platform.
