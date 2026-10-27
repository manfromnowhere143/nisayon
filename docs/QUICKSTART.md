# Try native qualification

Start with the exposed normalization example. No Git checkout, model download,
simulator or GPU is required. This is a developer preview for local software
comparisons, not a robot deployment service. Use a new directory and Python 3.12
on macOS or Linux. Python 3.13 is allowed by the adapter; this release's retained
installation check uses 3.12.

## Install v0.2.0

The [release](https://github.com/manfromnowhere143/nisayon/releases/tag/v0.2.0)
contains the wheel, source distribution, runtime lock and SHA-256 list. The
installation file pins the wheel and every runtime dependency with hashes.
Historical v0.1.0 predates the qualifier and remains unchanged.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r \
  https://github.com/manfromnowhere143/nisayon/releases/download/v0.2.0/requirements-install.txt
.venv/bin/nisayon-qualify example owner-project
```

The example command creates `case.json`, `policy.py` and `sdk_example.py` in a
new directory. It refuses an existing directory and does not run owner code.
Inspect these small files before executing them. No package is installed into
an existing robotics environment by these commands.

## Run with the CLI

Current GitHub source also provides a complete workflow command:

```sh
.venv/bin/nisayon qualify owner-project/case.json \
  --project owner-project --out qualification-001
```

This command executes trusted owner code. It freezes the plan, runs the existing
native checks, assesses the result and exports and rechecks
`qualification-001/review.nisayon.zip`. `result.json` names each artifact and
reports scoped software acceptance separately from unresolved deployment
acceptance. `nisayon-qualify qualify` exposes the same operation. These additions
are available from this checkout; the tagged v0.2.0 wheel retains the separate
commands below. Use `uv sync --frozen` here to install the current source.

The current source SDK also exposes [executable dependency checks and measured claims](../examples/qualification/executable_checks/README.md).
The OpenPI and retained Newton examples show observation reuse, fresh checks,
explicit measurement coverage and read-only reconstruction. These APIs are
available from current source; the tagged v0.2.0 wheel does not contain them.

An output directory must be new. Partial and failed runs remain retained;
retries require a new directory. `--timeout` bounds each native call and
`--total-seconds` bounds the runner, including its preflight. Neither bounds the
entire planning, sealing and review workflow. Workflow, runner and attempt
timers overlap; human effort and complete cost remain unknown. Portable replay
does not supply an independent adjudicator or confer deployment authorization.

For an inspection pause before execution, use the existing separate commands:

```sh
.venv/bin/nisayon-qualify plan owner-project/case.json \
  --project owner-project --out run-001 --plan plan-001.json
.venv/bin/nisayon-qualify run plan-001.json
.venv/bin/nisayon-qualify inspect run-001
.venv/bin/nisayon-qualify export run-001 --out review-001.nisayon.zip
.venv/bin/nisayon-qualify review review-001.nisayon.zip
```

Planning prints `execution: not_started`; `run-001` does not yet exist. Running
creates six native attempts: reference, negative control and candidate on each
of two inputs. The expected result is `software_decision: adopt`,
`execution_validity: valid`, and `deployment_decision: unresolved`. The negative
control reverses one action component; the assessor must detect it.

Open `review-001.nisayon.zip` in the
[software review interface](https://nisayon.danielwahnich.dev/#view=qualify).
The browser checks transport bytes and shows the saved assessment. The Python
`review` command independently recomputes the assessment from retained records;
this means a separate calculation, not an independent person or organization.
Neither executes the owner project during review. Local file import is not an
upload. Export preserves original inputs, logs and paths: inspect the contents
before sharing your own case.

## Compose reuse and confirmation (current source)

The engine can freeze two stages together. Supply a second `CaseSpec`
with the same question, targets, declared files, premises and comparison rule,
but distinct inputs and their justified expected outputs. The case and probe
IDs may differ. The engine refuses a relaxed confirmation criterion or input
overlap, including equal integer/float representations and signed zeros.

```sh
nisayon qualify owner-project/case.json \
  --confirmation owner-project/confirmation.json \
  --condition-store qualification-conditions \
  --project owner-project --out change-001
nisayon-qualify review-change change-001
```

This executes the explicit trusted owner functions. Both plans are frozen before
either stage starts. Valid investigation acceptance permits confirmation to run;
acceptance requires both stages. A valid failure rejects. Invalid controls,
missing premises, missing outcomes or changed identities leave the result
unresolved. The unchanged single-case command still has its narrower scope.

For a subsequent run, `--previous change-001/investigation` offers retained
investigation evidence for rechecking. Only an unchanged, valid scoped claim is
reused. Otherwise the investigation runs again, with an applicability explanation.
Confirmation always requires new execution and new conditions. This conservative
workflow does not yet execute the finer dependency planner or rescore old
observations under a changed criterion.

Share and retain the explicit condition store for the entire workload. Inputs
are consumed before execution, including interrupted and unused assignments.
Renaming cases or changing the candidate does not reset consumption. The store
cannot discover exposure in another store, undeclared experiments or an external
population. Local non-reuse is neither blinding nor independent confirmation.
The SDK therefore retains unresolved deployment authority and unobserved
independent adjudication even when the declared software relation is accepted.

`protocol.json`, `reservations.json`, `receipt.json` and the referenced stage
`.nisayon.zip` files form the portable record. Copy them together to review on
another machine; raw run directories and owner code are not required.
`review-change` verifies bindings and recomputes the decision instead of trusting
`result.json`. Individual stage bundles open in the existing software review
instrument. The instrument does not yet render the aggregate change receipt.

`--total-seconds` applies to **each** native stage (at most two). Planning, sealing
and review are additional work. Historical reused attempts are counted separately
from new execution; they are not a measured saving in complete engineering cost.
These additions require the current source checkout; they are not in the tagged
v0.2.0 wheel.

## Use the Python SDK

The installed example contains a complete importable workflow, including review:

```sh
.venv/bin/python owner-project/sdk_example.py --out python-result-001
```

Its core is:

```python
from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    plan_change,
    run_plan,
    assess_change,
)

case = CaseSpec.read("owner-project/case.json")
context = ExecutionContext.from_project("owner-project", output_dir="python-run-002")
plan = plan_change(case, context=context)
evidence = run_plan(plan, context=context)
assessment = assess_change(case, evidence)
print(assessment.record())
```

## What is inside a completed run?

```text
run-001/
  plan.json                 frozen case, identities, probes and assignments
  reference-offset/         first reference call
    intent.json             request identity retained before execution
    request.json            exact input, target and declared sources
    observation.json        output, native calls, reads and environment
    record.json             completion/failure, arguments and measured time
    stdout.txt, stderr.txt  original logs
  reference-fractional/     second reference call
  negative_control-offset/  deliberate wrong-sign control
  negative_control-fractional/
  candidate-offset/
  candidate-fractional/
  completion.json           runner outcome and bounded elapsed measurement
  manifest.json             exact member digests
  seal.json                 plan and manifest identities
```

`inspect` computes the assessment; adding an assessment file inside the sealed
store would invalidate its membership. Keep assessments, plans and review files
outside the store. A completed process is not automatically a valid experiment.
Missing human, setup and provider costs remain unknown; nested runner/attempt
time must not be added together.

## Exercise rejection and reuse

Copy `case.json` to a new case and change only the candidate callable to
`wrong_sign`. Freeze it to a new plan and run directory. Expect a valid software
`reject` and CLI exit 1. Exit 3 means unresolved; exit 2 indicates an invocation
or malformed-input error. Read the JSON outcome rather than treating every
nonzero exit as the same event.

To inspect applicability without rerunning:

```sh
.venv/bin/nisayon-qualify plan owner-project/case.json \
  --project owner-project --out unused-run --plan reuse-plan.json
.venv/bin/nisayon-qualify reuse run-001 reuse-plan.json
```

With unchanged declared identities, the old verdict can remain applicable to
the same scoped claim. This creates no new execution and grants no automatic
acceptance. A changed source, data dependency, environment, oracle or population
requires the corresponding new evidence.

For your own comparison, declare trusted synchronous Python entry points,
source/data/lock files, a competent reference, a deliberate failure control,
inputs and justified expected outputs. Keep the interpreter and project explicit.
Behavioral and action-changing claims remain unresolved in this adapter.
See [the complete capability map](CAPABILITIES.md),
[case contract](NATIVE_QUALIFICATION.md), and [review format](PORTABLE_REVIEW.md).
