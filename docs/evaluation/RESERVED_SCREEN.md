# Checks for the reserved screen

**`python -m nisayon.evaluation reserved MANIFEST [...]` · proposed 18 September 2026 ·
no reserved answers exist in this repository.**

The research plan's twenty reserved incidents can only be evaluated if the
answers are held by someone the solver session cannot reach. Neither Git
worktree, neither model, and no unguessable filename provides that. What the
evaluation lane can do now is state the checks a reserved trial must pass and
run them on openly labelled development examples, so that when custody exists
the checks are ready and nothing needs inventing.

## The sealed manifest

```json
{
  "schema": "nisayon.reserved_manifest.v1",
  "suite_id": "reserved-screen-v1",
  "evidence_origin": "synthetic_development",
  "sealed_at": "2026-09-20T09:00:00+00:00",
  "sealed_by_role": "case custodian",
  "custody": {
    "case_generation": "separate account",
    "solver_access": "none",
    "evaluator_access": "read-only",
    "statement": "…"
  },
  "protocol": {
    "obligation": "first-case-obligation-v0.2",
    "evaluator_commit": "…",
    "frozen_at": "2026-09-20T08:00:00+00:00",
    "retrieval_cutoff": {"at": "2026-09-20T08:30:00+00:00", "memory_tree_sha256": "…"}
  },
  "families": {"single_mechanism": 6, "interacting": 6, "invalid_control": 4, "non_identifiable": 2, "vacuous_trap": 2},
  "cases": [{"id": "R01", "family": "single_mechanism", "sealed_sha256": "…", "answer_sha256": "…"}],
  "arms": ["A", "B"]
}
```

`sealed_sha256` binds the case bytes the solver will receive;
`answer_sha256` binds the custodian's answer, whose content stays outside
every shared tree.

## What is checked

| Check | Finding |
|---|---|
| the custody statement gives the solver no access and separates case generation from evaluation | `custody_not_separated` (the reserved trial stays unrun) |
| protocol freeze precedes the retrieval cutoff, which precedes the seal, which precedes the solver session | `protocol_not_frozen_before_seal` |
| family counts equal the research plan's 6, 6, 4, 2, 2 and the sealed cases match them | `family_counts_differ` |
| no reserved case id or byte digest appears in development ledgers, decisions or documents | `reserved_case_leaked` |
| the case files the solver receives match their seals | `sealed_case_mismatch` |
| no sealed answer's bytes are present in the shared trees named on the command line | `answer_present_in_shared_tree` |
| the comparison ledger assigns every reserved case to every arm and names no other case | `assignment_incomplete` |

`ready` is true only when no blocking finding remains. It is a statement about
the records, not about custody: a solver with filesystem access to the
answers defeats every check above, which is why the reserved trial is left
unrun until a real boundary exists.

## Screen package checks

The execution lane freezes a public harness as `nisayon.screen.execution-package.v1`
(`python -m nisayon.engine.screen prepare`). `python -m nisayon.evaluation package
PACKAGE [--root CHECKOUT]` checks it against the evaluator in the checkout:

| Check | Finding |
|---|---|
| the package names the evaluator's obligation (`first-case-obligation-v0.2`) | `obligation_differs` |
| every file under `src/nisayon/evaluation/` the package binds has the same bytes here, and no evaluator file is unlisted | `evaluator_sources_stale` (re-freeze the package after evaluator corrections); `evaluator_sources_unbound` when none is listed |
| agent token and monetary ceilings are set | `ceiling_unset` |
| a matched isolated agent provider and a reserved custody boundary are named | `capability_missing` |
| the diagnostic budget per arm declares rollouts and wall seconds | `budget_undeclared` |
| the confirmation obligation is 32 fresh pairs, a post-freeze reproduction and every assigned outcome retained | `confirmation_obligation_differs` |
| a completed development ledger is bound | `development_evidence_absent` (reported) |

The package qualified at execution `2c5c3d7` is `NOT READY` on all three of
stale evaluator sources, unset ceilings and missing capabilities; that is the
honest state, and the first two are the package's to fix once the evaluator
corrections are merged. A passing package binds the evaluator; it establishes
no custody.

## What exists today

Labelled development examples in `src/nisayon/evaluation/reserved_fixtures.py`
exercise each finding, including the intended one: the shared-worktree
example is not ready because its custody statement gives the solver access.
No manifest for real reserved cases has been written, and none should be
written by either development session.

[Evaluator overview](README.md) · [Scoring contract](SCORING_CONTRACT.md) · [Trust boundary](TRUST_BOUNDARY.md)
