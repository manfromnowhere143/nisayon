# What the evaluator can and cannot establish

**A statement of premises, with the demonstrations that fix them.**

The evaluator reads records. Four different things are at stake in a record,
and each check reaches only one of them.

| Layer | What a passing check means | How it is checked | What it does not mean |
|---|---|---|---|
| Byte integrity | The bytes named by a digest are the bytes present | `trace_ref` and artifact digests, the manifest, the frozen protocol digest, the cost ledger digest | that the bytes describe an execution |
| Internal consistency | The record does not contradict itself | observation and state chains, acquisition stamps against consumed packets, host ordering, identity agreement across assigned runs, raw rows against compact rows, `task_success` against the height threshold | that a simulator produced it |
| Trusted execution provenance | The execution happened as described, under the frozen protocol | **not established offline** | |
| Physical validity | The simulated outcome would hold on a robot | **never established by records** | |

## Demonstrations

`tests/evaluation/test_evaluation_real_v2_attacks.py` exercises derived copies
of the real Lift v2 record:

- Removing evidence never produces acceptance: no frozen protocol, no manifest,
  stripped acquisition stamps or stripped identity each leave a named gap.
- Reordering records does not change the decision; a content-identical copied
  store verifies under a different path; an altered byte in the copy is rejected.
- Rewriting a threshold after the freeze is caught against the frozen protocol.
  Rewriting the frozen protocol and its digest consistently is **not** caught by
  the bundle alone; it is caught when a retained earlier decision for the same
  candidate and condition set is supplied as history.
- Replacing an assigned run's compact rows with another passing run's rows keeps
  the compact record consistent. Without the raw store the evaluator cannot tell.
  With the store, the raw-versus-compact check rejects it. A forger who also
  rewrites the raw file and the manifest is **not** detectable by this evaluator.
- A replay relabelled as closed loop with recomputed validity flags becomes a
  spare attempt on a scored condition and voids the confirmation; its copied
  observations still show the task failing.
- The known-fixture digest guard recognizes this repository's own synthetic
  traces when they are presented as measurements. It detects nothing else.

## Order and identity the evaluator supplies itself

Two records that spent the same conditions can only be ordered by evidence a
producer did not write. Every decision now carries `decided_at`, `bundle_sha256`
and `task.policy_sha256`. Retained decisions order each other by `decided_at`,
so a re-execution whose freeze is declared earlier than the original's still
meets the original's earlier decision and is invalid; declared freeze times
order only decisions that predate the stamps. Consumption is keyed by the task
policy as well as the case id, so renaming a case frees nothing, and every
executed run's condition counts, not only the declared list. This is ordering
among retained records, not custody: a record that was never retained, or a
history that was pruned, is outside what the evaluator can see, and the
`history_absent` note says so.

## What would move the boundary

Provenance is a property of custody and execution authority, not of hashes.
Three things would establish it for a scored run and none exists today:

1. Re-execution of the frozen protocol from the retained recipe on a machine
   the solver session cannot write to, compared row by row with the retained
   record.
2. Execution records written by a service the solver cannot modify, with the
   invocation identity recorded outside the solver's reach.
3. For reserved cases, separate custody of case generation and evaluation,
   with a sealed manifest published before any solver session starts.

Until then, an acceptance is a statement about a record under its stated
premises. The decision's `evidence` block lists which premises were measured,
inherited or unverified for that record.

[Evaluator overview](README.md) · [Confirmation obligation](CONFIRMATION_OBLIGATION.md)
