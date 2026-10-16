# Repository integration and reproduction review

**16 October 2026 · N046 · software and presentation qualification.**

The repository now exposes the implemented experiment path, bounded decision
probes, retained failures and current confirmation research through N045. The
README links each claim to its code, protocol and evidence. A separate data-flow
diagram identifies the implementation; the general compiler, adaptive selector
and robot deployment bridge remain proposed.

## Checked source and reproduction

A `git clone --no-local --single-branch` of public candidate `4b0fec5` created a
new Git object store and a new base environment. Three private development commit
objects are absent and there are no object alternates. `uv sync --frozen` succeeds
with Python 3.12.13 and the existing lockfile. The same physical host can still
access other directories; this is a source-installation check, not independent
scientific evaluation.

The initial full `make check` passes **1,251 tests, with 80 explicit skips**, lint,
and formatting for 598 Python files. The skips require optional simulation
packages or a private raw store. Documentation checks pass for 219 local Markdown
files, including the generated pytest-cache README. The
[raw log](initial-full-check.log) retains all skip reasons. No retained experiment
environment was synchronized and no dependency was upgraded.

The README examples also matter. Both compact comparisons re-score successfully
with current source, and separately with the retained historical source archives.
Current-source scoring retains the D08 binding warning; it does not replace the
original rules or validate replay. The six-case late-reset example runs and
reports robot task outcome as unmeasured. No simulator trajectory executes.

The decision-probe example initially fails because its output parent does not
exist in a clean checkout. The [failure](decision-example-initial.stderr.log)
remains retained. The correction creates missing parent directories and opens
the result exclusively. A CLI regression exercises an absent nested parent and
then verifies that repeating the command fails without changing the result.
All **56 focused checks** pass after the correction, as do changed-file lint and
formatting. The corrected example preserves the constructed result: full cause
identification costs four, while decision selection and a competent conventional
calculation each cost one. This is declared observation cost, not measured owner
savings. Its algorithm and task-confirmation boundary are unchanged.

[validation.json](validation.json) identifies the initial commit, corrected-file
digests, commands, timings, environment and retained logs. Exact final public
commits and Linux/macOS results are recorded in
[GitHub Actions](https://github.com/manfromnowhere143/nisayon/actions/workflows/ci.yml).
The local record does not stand in for those platform results.

## Presentation and publication scope

All eight Mermaid diagrams render and were visually checked in light and dark
themes. The [diagram record](diagram-review.json) binds their source and image
digests. The review found no clipped labels or overlapping nodes in those renders;
GitHub's renderer can differ. All 27 reviewed local heading links resolve.

[review.json](review.json) records the code-inspection scope and publication
checks. Existing machine-readable result files and source archives retain their
bytes. The only removed public path is the internal queue; its historical public
versions remain in Git. Current private correspondence, session memory, client
settings and development ancestors are excluded. The source export manifest
binds copied files and declares the five public continuity/documentation overlays.
Earlier public validation receipts, upstream source licenses and provenance remain.

Credential-pattern matches were task-schema identifiers, including the earlier
record of the same false positives. Fifteen archives were inspected by member;
no reserved-answer path was opened. Six small constructed NumPy traces in the
N039 archive are explicitly distinguished from owner data, policy weights and
simulator stores. Whitespace inside historical raw logs and literal patches is
retained because those bytes are evidence.

The review does not establish a new robot result, complete-effort advantage,
independent hidden-case evaluation or customer adoption. The next decisive test
still needs an independently owned incident, fresh task confirmation and lower
complete effort, followed by a separate untouched reuse case.
