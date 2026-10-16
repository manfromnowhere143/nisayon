# Recovery summary semantics: RoboRecover source probe

**10 October 2026 · executed software controls, no robot-task evidence.**

At RoboRecover commit `089b9420e8b7c303e2338a8212a8b6c27c26a79b`, the RoboTwin
Pi0.5 evaluator's task and error-group summaries count a true
`eval_success_at_end` regardless of execution phase. An episode that finishes
during prefix replay can therefore contribute to those success fields while
having zero policy-inference steps. The same summary lists it in `failed_files`;
the entrypoint returns 2. Consumers need the status and phase, not just the rate.

Source: [RoboRecover evaluator](https://github.com/RUCKBReasoning/RoboRecover/blob/089b9420e8b7c303e2338a8212a8b6c27c26a79b/overlays/RoboTwin/script/eval_ood_replay_then_infer.py).
The early return is at lines 421–441; the writer calls `build_summary` at 238–240;
the aggregation is at 596–641; terminal status handling is at 779–788.
The full reviewed file SHA256 is
`e335523db8ad4a2e06def1180f0e734334dbbd3b873df69d46873e17face700d`.

The [probe](../../../../scripts/experiments/probe_roborecover_summary.py) checks
that digest, extracts the unmodified `EvalResult` and `build_summary` definitions
through Python's AST, and executes them with standard-library dependencies.
Upstream imports, simulator setup, model inference and dataset contents do not run.
The inputs are constructed software records, including an explicit imitation of
the source's replay-completion return. No claim is made that this state occurred
in an actual released experiment.

| Constructed control | Upstream success count | Other observed evidence |
|---|---:|---|
| Successful inference | 1/1 | Positive control |
| Failed inference | 0/1 | Failure remains in the denominator |
| State mismatch, missing success flag | 0/1 | Missing does not become success |
| Completion during prefix replay | 1/1 | Zero inference steps; also in failed files |
| Unequal repeats: A succeeds once, B fails three times | Trial rate 0.25 | Equal-scenario mean is 0.5 |

The last row compares two estimands. The pinned
[README](https://github.com/RUCKBReasoning/RoboRecover/blob/089b9420e8b7c303e2338a8212a8b6c27c26a79b/README.md)
asks readers to average scenarios equally, while `task_summary.success_rate`
pools records. It should not be interpreted as the documented scenario mean
when repeat counts differ. This is not evidence that the authors used unequal
counts or used this field in the paper's analysis.

The retained [result](result.json) contains every constructed input and observed
output, source/script identities, interpreter and measured probe time. The
checks confirm source behavior, not scientific success. A conventional code
review exposes the issue; no advantage over ordinary debugging was tested.

Reproduce in a new output directory, using Python 3.12 and no installed packages:

```sh
mkdir -p artifacts/recovery-summary-readback
curl --fail --location \
  https://raw.githubusercontent.com/RUCKBReasoning/RoboRecover/089b9420e8b7c303e2338a8212a8b6c27c26a79b/overlays/RoboTwin/script/eval_ood_replay_then_infer.py \
  --output artifacts/recovery-summary-readback/upstream.py
python3.12 -B scripts/experiments/probe_roborecover_summary.py \
  --source artifacts/recovery-summary-readback/upstream.py \
  --out artifacts/recovery-summary-readback/result.json
```

The probe refuses changed source bytes and an existing output filename. It
retains upstream attribution and does not distribute a modified upstream module.
The linked code is third-party work; it is not attributed to Nisayon.

Next: clarify whether these fields mean environment completion or successful
recovery inference, and whether a separate phase-qualified, scenario-weighted
field would help. Preserve raw outcomes, failures, original denominators and the
upstream error exit. After the review, the question was posted as
[RoboRecover #2](https://github.com/RUCKBReasoning/RoboRecover/issues/2) on
10 October at 06:08:34 UTC. It includes a separately tested self-contained
reproducer and its observed output. The
[outreach receipt](../frontier-review-2026-10-10/outreach.json) retains the exact
body and readback; the [research questions](../frontier-review-2026-10-10/QUESTIONS.md)
track the remaining evidence needed. Do not send the question again.
