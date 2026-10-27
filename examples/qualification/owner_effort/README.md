# Record owner effort without inferring it from agent runtime

This executable example records operator-reported active work and composes it
with explicit engineering rates and charges. It answers a narrow accounting
question: how much declared work belongs to each workflow, and are the inputs
complete enough to evaluate the retained twofold target? It cannot establish
attention, owner consent, causal savings or competitive superiority.

The [prospective comparison](../../../docs/OWNER_COMPARISON.md) remains unenrolled.
The [measurement result and research](../../../docs/experiments/results/owner-effort-2026-10-24/README.md)
describe the checks and current evidence boundary. The qualification SDK and the frozen
Kornia contract are unchanged. The
[exact cost calculation](../../../docs/COST_TARGET.md)
supersedes the original floating-point aggregation in this example. It uses the existing
[finite cost evaluator](../../../src/nisayon/engine/cost_target.py).

## Start a prospective ledger

Use the locked base environment from a source checkout. Choose a new output
directory. No owner code, model, robot or network service is executed.

```sh
mkdir -p artifacts/owner-comparison/activities
uv run --frozen python examples/qualification/owner_effort/effort.py init \
  artifacts/owner-comparison/ledger.json \
  --scope 'Initial decision and one separate reuse; maintenance horizon not yet agreed' \
  --protocol-reference docs/OWNER_COMPARISON.md
uv run --frozen python examples/qualification/owner_effort/effort.py assess \
  artifacts/owner-comparison/ledger.json
```

The initial report is `unresolved`. Every phase is unmeasured, selection and
expected decisions are absent, owner reviews are pending, and no activity was
observed. Zero retained seconds means an empty measured prefix; it is not a
zero-cost experiment. `kind: prepared` cannot earn a supported owner result.

Before enrollment, freeze the decision, exact source revisions, permitted
records, comparator, full assignment list, quality controls, independent
selection procedure, rates, cost allocation and maintenance horizon in a
referenced protocol. Use one stable identity for each actual human, even if that
person performs several roles. Add all people to every phase's coverage. The
`initial` and `reuse` case names are placeholders. `preparation` is reserved for
work that precedes cases. Change `kind` only when a real comparison starts;
changing a string does not supply enrollment evidence.

## Record active work

Run this in the person's terminal when active work begins. Press Enter before
waiting, switching tasks or leaving. Start another file on resuming. Recording
overhead, ledger preparation and review are also work; include them in the
appropriate phase. Earlier unmetered preparation remains unknown.

```sh
uv run --frozen python examples/qualification/owner_effort/effort.py track \
  artifacts/owner-comparison/activities/review-001.jsonl \
  --actor owner --arm candidate --case initial --phase review \
  --reference 'frozen packet identity and review task'
```

Keep every resulting file in `activities/` and list its relative path in the
ledger's `activity_files`. Assessment rejects an unlisted file, conflicting
allocation, duplicate identity, malformed record or symlink. It reads the
entire directory so an interrupted retry cannot be dropped by deleting one list
entry. File deletion or falsified declarations outside the tool remain possible;
retain an external frozen assignment and file inventory for actual trials.

The timer flushes a start record before waiting and appends a stop on Enter or
handled interruption. EOF and Ctrl-C retain an interrupted interval; termination
can leave an open prefix. These prevent a complete phase total, even if its
coverage says complete. An interrupted interval's observed duration is retained.
Existing output files are never overwritten. Correct an invalid record through
a separately retained, explained revision; do not silently repair the original.

Duration uses a monotonic clock, aligned to UTC for overlap checks, at
microsecond resolution, with ties rounded to even using the integer clock
difference. A disagreement greater than one second invalidates the
record. This is a bounded single-clock capture method: clock synchronization
across machines and long suspension are not qualified. It does not detect idle
time. Overlapping timers for the same person, case, arm and phase are unioned;
overlap across different allocations is invalid. Different people's time adds.

## Account for costs and acceptance

The eight existing phases are intake, setup, diagnosis, retries, confirmation,
review, adoption and maintenance. Setup includes adapter development; review
includes questions, rework inspection and delivery; adoption includes integration
and delivery work outside review. Freeze these boundaries to avoid overlapping
phase claims. All assigned work, including unsuccessful attempts, stays in scope.

For each arm and phase, `coverage` declares whether each person's active work is
fully recorded, with a receipt reference or missing-data reason. No activity can
be a measured zero only when a complete coverage receipt explicitly establishes
no work. Fill provider, compute and other charges in USD, with original invoices,
usage units and conversion records retained at their references. Use null with a
reason whenever unavailable. Human rates also need references; an unknown rate
blocks valuation of nonzero time. A zero wage cannot erase unmeasured work.
Account for capital, hosting or other resources in `other` when applicable.
Do not count a bundled compute charge again under provider charges.

`shared` is work both workflows genuinely require, including common measurement
preparation. Candidate-specific package development belongs to `candidate`.
Common preparation is charged once in each hypothetical arm's cost; initial
preparation is never divided across future customers or hypothetical reuses.
For baseline work B, candidate work N and shared work S, compare B+S with N+S.
The actual study's total is B+N+S, supplied separately in `study_phase_totals`;
adding the two comparison totals would double-count S. Retain earlier unknown
development costs if they belong to the claim's scope. A prospectively narrowed
scope must be named as a different claim, not silently substituted for the target.

Owner seconds remain a separate dimension. Agent wall time and parallel command
durations are not human effort and are not added to it. Keep command records and
raw provider/compute usage alongside this ledger using the existing recorders.
The input references and declared disjointness require review; the tool does not
authenticate invoices, owner identities or completeness.

Each assigned case retains expected and observed decisions plus separate owner
acceptance. Test success cannot fill the owner-review field. Owner rejection
contradicts the delivered value claim. Pending review, missing selection, unknown
costs or missing quality labels leave it unresolved. The existing strict quality
gate also requires a correctly confirmed correction in both arms, checks false
acceptance, and preserves unresolved outcomes. The finite target is not a
statistical noninferiority test. A caller who supplies invented truth or receipts
can get an invented result; the report identifies those supplied premises.

`baseline_minus_candidate_owner_seconds_by_phase` is a descriptive difference,
not causal effort avoided. The two `finite_comparisons` show owner seconds and
monetary arithmetic separately. Read the top-level status and reasons as well:
synthetic arithmetic cannot establish an owner result. An assessment exit code
of 0 means the report was produced; invalid input returns 2. The report binds
the exact ledger and activity bytes by SHA-256.

Cost aggregation, rate conversion, shared costs and target comparisons use exact
rational arithmetic. Each input integer or finite binary float preserves its
represented value; JSON decimal tokens still parse as binary floats. Precision
already lost before input is not recoverable. Exact arithmetic is not a claim
that a declared duration or wage is precisely measured.

The input ledger remains `nisayon.owner-effort.v1`. Reports now use
`nisayon.owner-effort-report.v2`: numeric fields are approximate displays, with
exact computed values in `exact_quantities`, indexed by JSON pointer. Numerators
and positive denominators are decimal strings, avoiding integer coercion in
other JSON readers. Each witness marks its display `exact`, `rounded` or
`overflow`. Overflow displays are null but have a witness; unknowns have none.
A printed cost ratio of 2 can conceal a small failed margin; read the exact
decision and quantities. To recheck arithmetic, reconstruct phase costs from
the witnesses, not rounded displays. The finite evaluator also accepts Python
`Fraction` values directly. Existing v1 reports and input receipts remain
historical artifacts; they are not silently rewritten.

```sh
uv run --frozen pytest tests/qualification/test_owner_effort.py \
  tests/engine/test_cost_target.py
```
