# Preserve execution budgets when an evaluation resumes

19 October 2026. Proposed correction for
[EMERGE-Policy](https://github.com/EMERGE-Policy/EMERGE-Policy/tree/e4c7134ad2aeb6dded049106ada1c28985b66e69)
at `e4c7134ad2aeb6dded049106ada1c28985b66e69`. Upstream adoption is unproved.

An interrupted evaluation can resume with a different action limit, settling
period, episode timeout or feedback allowance. The existing plan comparison
accepts the changed settings, skips completed episodes and combines the retained
and newly produced results in one summary. A controlled two-episode example
combines action limits of 16 and 620. That changes the evaluation conditions
without making the difference part of the resume identity.

The [patch](resume-execution-settings.patch) records these four execution
settings in the standard LIBERO, LIBERO-Plus and LIBERO-Pro plans. It compares
effective action limits for the selected suites, including inherited defaults.
An explicit limit equal to the default remains compatible. A changed default,
changed budget or missing historical execution identity is rejected before
scheduling a pending episode or replacing the plan and outcome records.

Existing plans without these settings are not automatically migrated: their
past budgets cannot be inferred from today's command. They remain intact and
require a separate output directory. An initially empty directory can still be
started with `--resume`. The plan schemas advance to v2, v3 and v3 respectively.

## What was executed

The [fixture](tests/test_resume_contract.py) imports the native modules and
calls each complete `main()` entrypoint. Argument parsing, plan comparison,
pending/completed selection, sequential scheduling, result append and summary
writing execute. Task enumeration, benchmark setup and the rollout call are
controlled boundaries. The first controlled episode is persisted; the second
raises an interruption. The resume then exercises the actual plan gate.

| Source or control | Selected cases | Result |
| --- | ---: | --- |
| Unchanged pinned source | 30 | 9 pass, 21 fail the intended rejection contracts |
| Proposed patch, applied to a fresh source copy | 30 | 30 pass, no skips or errors |
| Incomplete correction that stores an unresolved action limit | 6 | All six default-equivalence/default-change controls fail |

The first fixture attempt omitted empty suite entries needed by LIBERO-Plus.
Eight cases failed before reaching that behavior; it is retained separately.
After correcting the fixture, all three entrypoints reach the intended checks.
No assertion was weakened. The final patch differs from the first passing
patch only by an explicit explanation for old plans without execution settings.
[Results and identities](results.json), [retained records](records/commands.json)
and [original fixture](fixtures-v1/test_resume_contract.py.txt) preserve these steps.

The test results are software observations. No model, agent, simulator episode,
hardware run or full upstream suite was executed. The two controlled episode
records deliberately report task failure and are not robot outcomes. This
review establishes neither an effect on published paper results nor owner
savings, independent reuse or general reproduction of the framework.

This patch binds four execution settings. Model/service identities, inherited
agent configuration, all source changes, concurrency and other timing settings
remain separate concerns. Benchmark setup is controlled in this test; the
claim of preserved files concerns the plan and retained outcome records, not
every setup file the full application might generate.

## Reproduce

Use new directories and the recorded Python 3.12 environment. The package list
is a minimal dependency set for these entrypoints, not a complete installation
of the upstream robotics stack. The retained run used macOS on ARM64.

```sh
packet="$PWD/docs/contributions/emerge-resume-review"
uv venv --python 3.12 /tmp/emerge-resume-env
uv pip install --python /tmp/emerge-resume-env/bin/python -r "$packet/requirements.txt"
/tmp/emerge-resume-env/bin/python "$packet/prepare_source.py" /tmp/emerge-resume-source
EMERGE_SOURCE=/tmp/emerge-resume-source PYTHONDONTWRITEBYTECODE=1 \
  /tmp/emerge-resume-env/bin/python -B -m pytest "$packet/tests" -q
```

The unchanged source should produce 9 passes and 21 failures. Apply the patch
to that downloaded source and run the same fixture:

```sh
cd /tmp/emerge-resume-source
git apply "$packet/resume-execution-settings.patch"
EMERGE_SOURCE=/tmp/emerge-resume-source PYTHONDONTWRITEBYTECODE=1 \
  /tmp/emerge-resume-env/bin/python -B -m pytest "$packet/tests" -q
```

All 30 selected cases should pass. Source acquisition checks both Git blob
identity and SHA-256 for each of the 41 files. The public packet contains the
proposed patch and original test, without redistributing full upstream modules,
model weights, datasets, private correspondence or credentials.

The original framework and evaluator are the EMERGE-Policy contributors' work.
Their [package metadata](https://github.com/EMERGE-Policy/EMERGE-Policy/blob/e4c7134ad2aeb6dded049106ada1c28985b66e69/pyproject.toml)
declares MIT; no root LICENSE file is present in the pinned tree, while
`docs/LICENSE` contains Apache 2.0. These are retained source facts, not a claim
that the different license locations have been reconciled.
