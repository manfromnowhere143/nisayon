# Confirm the current validation attempt

20 October 2026. Proposed correction for
[NVIDIA ASPIRE](https://github.com/NVlabs/ASPIRE/tree/fa00f0ef2bc1d91d594b9aa502c22133c9f538f7).
Upstream adoption remains unproved.

An earlier successful run can make a new validation attempt pass without
producing an outcome. Through the normal command line, the child rejects an
empty program and exits 1. If its output tree contains an earlier successful
record, the parent reports success and exits 0. With no earlier record, the
same command correctly fails. The earlier files remain unchanged.

The [patch](current-attempt.patch) allocates a retained output directory for
each invocation and searches only that directory. It records the directory
even when execution produces no outcome. Previous records remain available.
This also separates a late completion from an earlier attempt, which a simple
comparison of outcome files before and after the command cannot do.

Exit status remains diagnostic. ASPIRE
[documents](https://github.com/NVlabs/ASPIRE/blob/fa00f0ef2bc1d91d594b9aa502c22133c9f538f7/docs/run-artifacts.md)
BEHAVIOR completing its evidence before exiting 139 during simulator teardown.
A blanket rejection of nonzero exits would change that behavior and still
would not reject stale evidence after a zero exit. No BEHAVIOR simulator was
run in this review; this compatibility condition is exercised with controlled
records and exit statuses.

The new directory is
`<output-dir>/<case>/runs/<seed>/attempt-<suffix>/`.
The native producer keeps its existing seed and run directories beneath it.
Consumers should use the summary's `run_dir`; `attempt_root` also identifies an
incomplete attempt. Existing records are neither migrated nor deleted.

## Evidence

The [CLI reproduction](reproduce_cli.py) executes the complete native
`validate --plan` command and its real `run` child. It uses the native recorder
to manufacture the earlier success, then empties the program. The resulting
input rejection happens before simulator construction. The success flags are
test fixtures, not observed robot outcomes.

| Source | Selected native tests and 11 new controls | Normal CLI with old success | Sealed/unsealed fixture controls |
| --- | --- | --- | --- |
| Main `fa00f0e` | 50 pass, 6 fail | Incorrectly passes | 8/12 agree; 4 stale acceptances |
| RetiefLouw PR #25 `c826d90` | 59 pass, 6 fail | Incorrectly passes | 8/12 agree; 4 stale acceptances |
| Main plus this correction | 56 pass | Correctly rejects | 12/12 agree |
| PR #25 plus this correction | 65 pass | Correctly rejects | 12/12 agree |

All selected test bodies execute with no errors or skips. The unchanged native
tests pass in both baselines. The six failures are among the eleven new
[attempt controls](test_validation_attempts.py), covering stale outcomes,
directory sort order and late completion. Fresh equal outcomes and successful
records followed by a teardown exit remain accepted. Earlier evidence is checked
for byte preservation.

[Two deliberately incomplete fixes](check_incomplete_fixes.py) fail the same
controls. An exit status guard fails five; selecting newly appearing outcome
paths fails the late completion case. These are constructed development
controls, not an independent benchmark or a separate reuse trial.

The [sealed probe](probe_sealed.py) uses the upstream test fixture, including
its fabricated three-byte video files. It executes the native case runner and
verifier with controlled metadata and a child that supplies the specified exit
status. It does not qualify recorded video, the complete sealed CLI, or a robot
task. The sealed and unsealed rows test one defect under two conditions, not
four independent discoveries.

RetiefLouw's [PR #25](https://github.com/NVlabs/ASPIRE/pull/25) separately rejects
missing or invalid sealed metadata. That contribution remains theirs. This
patch is based on main, does not incorporate their code, and was also applied
alongside it for the combined check.

[Results](results.json), [source identities](sources.json) and the
[record index](records/index.json) bind the observations. Public logs normalize
local path prefixes; the index retains original and exported SHA-256 values.
Two initial CLI reader errors are recorded separately: the result uses `seeds`,
and the CLI prints a concise error rather than a traceback. Neither failed
reader attempt is counted as qualification. Initial dependency preparation and
the development control revision are also retained in the result history.

## Reproduce

Use fresh directories. This is a CPU test environment on Python 3.12, with
NumPy 1.26.4 and SciPy 1.17.1 respecting the upstream overrides. It is not the
complete ASPIRE simulator installation. Do not initialize hardware or services.

```sh
packet="$PWD/docs/contributions/aspire-validation-review"
uv venv --python 3.12 /tmp/aspire-attempt-env
uv pip install --python /tmp/aspire-attempt-env/bin/python -r "$packet/requirements.txt"
git clone https://github.com/NVlabs/ASPIRE.git /tmp/aspire-attempt-source
git -C /tmp/aspire-attempt-source checkout --detach fa00f0ef2bc1d91d594b9aa502c22133c9f538f7
/tmp/aspire-attempt-env/bin/python -B "$packet/reproduce_cli.py" \
  --source /tmp/aspire-attempt-source --output /tmp/aspire-cli-before
```

The old-success case reports parent exit 0 and child exit 1. Apply the patch:

```sh
cd /tmp/aspire-attempt-source
git apply "$packet/current-attempt.patch"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" \
  /tmp/aspire-attempt-env/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/test_validation_sealing.py tests/test_validation_engine.py \
  tests/test_validation.py tests/test_validation_libero_plan.py \
  tests/test_cli.py tests/test_validation_attempts.py
/tmp/aspire-attempt-env/bin/python -B "$packet/reproduce_cli.py" \
  --source /tmp/aspire-attempt-source --output /tmp/aspire-cli-after
/tmp/aspire-attempt-env/bin/python -B "$packet/probe_sealed.py" \
  --source /tmp/aspire-attempt-source --output /tmp/aspire-sealed-after
```

Expect 56 passing selected tests, both CLI cases rejected, and 12 agreeing
sealed/unsealed controls. To reproduce the combined check, start a separate
checkout at PR #25's pinned revision before applying the patch; expect 65 tests.
Run `check_incomplete_fixes.py` against an unchanged base checkout with a new
output directory to reproduce the two rejected alternatives.

The correction assumes the producer respects its output directory. It does
not authenticate evidence against a malicious writer, serialize simultaneous
campaign summary updates, validate all task identities, or change existing
outcome predicates. No full upstream suite, model, provider, simulator task,
physical task, paper score effect, owner saving or independent reuse is claimed.

The underlying framework belongs to NVIDIA and the ASPIRE contributors. The
patch is offered under their [Apache 2.0 license](UPSTREAM_LICENSE.txt);
[upstream notices](UPSTREAM_NOTICE.txt) are preserved.
