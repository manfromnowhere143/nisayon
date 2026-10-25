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
