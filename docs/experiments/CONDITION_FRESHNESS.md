# Condition freshness across worktrees

Fable reproduced a correctness defect at `3858962`: the first-case command in
another worktree accepted seeds 3000–3031 again. Its history covered only v1/v2,
and its local reservation directory did not contain execution's v3 reservations.
Evaluating the same unchanged runs with v3 history correctly invalidated reuse.
Fable retains both decisions and the extra executions; their costs remain.

Execution now checks [committed consumed conditions](../../work/development/consumed-conditions.json)
before simulation. Each entry names measured conditions and a retained artifact
digest. The condition namespace is the task/policy, so changing a case label
does not make an observed seed fresh. The first-case command also copies v3
and every retained evaluator decision into its bound history.

New exclusive reservations live in Nisayon's common Git metadata, shared by
its worktrees. Existing local reservations remain checked. A partial reservation
or an interrupted execution remains spent. Completed suite reservations must
be added to the committed ledger with the archived freeze, including conditions
that were reserved but never observed. New independent clones need the latest
committed evidence; live reservations are not a distributed lock across clones.

The first-case default was seeds 4000–4031 when this correction was implemented.
An explicit reused range must fail before policy loading or physics. A second
invocation on the default range will also fail once it is reserved; select a
new declared range explicitly. A re-run on old conditions is reproduction,
never fresh confirmation. Worktree coordination and hashes do not establish
reserved-case custody or unseen fault mechanisms.

The guard also checks the conditions inside each bound artifact. A labelled
software reproducer exposed a gap in the initial fix: a correctly hashed file
containing seed 777 could be indexed as seed 888, letting 777 be reserved again.
The [original failure](results/condition-binding-001/original-failure.json)
is retained; no simulator conditions were observed in this fixture. The latest
physical confirmation's index was correct, so this does not invalidate it.

The corrected reader rejects index/artifact and policy-namespace mismatches,
derives the full seed set from the artifact, and discovers retained compact
bundles and frozen suites even if their index entry is absent. Case renaming,
failed runs and declared-but-unexecuted assignments cannot make those seeds
fresh. The current physical history contains 131 distinct consumed seed values.
An independent clone still needs the published artifacts; this does not solve
coordination with an unpublished remote run or provide reserved-case custody.

Tests use two actual temporary Git worktrees to check reservation exclusion,
check committed-history rejection without local reservations, and reject missing
or altered history. No reserved answers or fresh scientific measurements are
created by those labelled fixtures.

The positive joint confirmation at `2c5c3d77e82427a9ae38a7a97f3d85317d858333`
then consumed **4000–4031**. All 32 fresh pairs passed, separately from the
post-freeze seed-0 reproduction; suppression was rejected and derived replay
invalidated. The [retained result](results/lift-freshness-001/summary.json)
contains 69 runs, 3,636 rows and 226 verified files. Protocol digest:
`5a6e4a1e89f4d780118a15a3779a17be44849bdb19e124001302414631018486`.
The outer command cost 115.519064 s, including its 87.833964 s execution and
27.303238 s evaluation children. Completed known execution command walls were
1,787.337835 s; material categories remain unknown. These costs are not added
to one another. This is another confirmation of the existing mechanism, not
another development incident.

The committed consumed ledger now includes those seeds too. The default range
therefore fails closed on reuse; choose an explicitly new range for a genuinely
fresh run. Retained confirmation archives are now discovered dynamically,
including failed/invalid records and each newly published result. A fixed
v1/v2 list cannot silently omit the latest protocol again.

The actual first-case entry point at `b4f7420e6de0c82d0f21f8917cc3160907379157`
now rejects seeds 3000–3031 in both a new detached worktree and an independent
local clone without `.nisayon/conditions`. Neither creates an execution output
directory. [Both retained checks](results/condition-freshness-001/manifest.json)
include a harness failure: the first compared `/var/...` with the equivalent
resolved `/private/var/...` path as strings. Both commands had already rejected
reuse. The superseding check resolves the expected root before comparing it;
the actual execution code is unchanged. No physics or new confirmation ran.

```sh
.venv/bin/nisayon run --label consumed-seed-cross-checkout-reproduction --timeout 180 -- \
  .venv/bin/python scripts/experiments/verify_condition_freshness.py \
  --output artifacts/condition-freshness-reproduction-NEXT.json
```

The latest accepted store was also copied to a temporary root with all thirteen
bound history artifacts. The copied 226-file / 69-run store verified, and Fable
returned the same retained per-run outcomes, identities, confirmation pairs and
decision. Seven deliberately altered-copy checks rejected missing/changed raw
traces, invocation/configuration mismatches, a dropped assignment, and
missing/changed history. The original store stayed unchanged. This checks
relocation and byte integrity, not another simulator execution or independence.
The [report](results/lift-freshness-portability-001/portability.json) binds the
expected decision; command `2b505a160d8743939c49a0ac04eb4994` cost 35.579051 s.

```sh
.venv/bin/nisayon run --label portable-fresh-confirmation-with-history --timeout 180 -- \
  .venv/bin/python scripts/experiments/verify_portable_execution.py \
  --root artifacts/lift-freshness-confirmation-001/execution \
  --expected-decision artifacts/lift-freshness-confirmation-001/evaluation/decision.json \
  --output artifacts/lift-freshness-portability-NEXT.json
```
