# First-case exchange contract

**Proposed v0.1 · development interface, not a proof of experimental validity.**

Codex produces execution records. Fable 5 consumes them in an evaluator that
can be tested without installing the simulator. Use plain versioned JSON at
the boundary and typed Python internally. Introduce fields when this case needs
them; avoid a general ontology before an actual rollout exists.

| Record | Minimum content |
|---|---|
| Case | ID; task/policy/backend identities; working and changed revisions; declared progress, outcome, constraint and timing predicates; allowed repair scope |
| Qualification | Captured and omitted state; reset procedure; clocks/randomness; repeated-run comparisons and tolerances; actual version/hardware boundary |
| Experiment plan | Case; intervention, activation and reset semantics; full rerun or justified continuation; explicit recomputation and retained-data choices |
| Run | Schema and ID; plan/input identities; process status; trace/artifact references; measured task outcomes; validity evidence/reasons; cost records and missingness |
| Confirmation | Frozen candidate; predicate/protocol identity; declared fresh condition IDs; reference and candidate runs; every assigned outcome; any contamination |
| Decision | Accepted, rejected, unresolved or invalid in a named scope; reasons; source run IDs; measured costs and limits |

Use separate fields for process completion, observation validity, task outcome
and acceptance. No ambiguous global `success` field. Timestamps carry a clock
domain and units. Numeric unknowns use explicit missingness; reject NaN/Infinity
and invalid units instead of silently converting them. Relative artifact paths
resolve against an explicit artifact root, not whichever directory the reader
happens to occupy. Small result files identify exact input digests where useful;
digests bind bytes, not truth.

Trace design must expose enough to challenge at least: stale observations,
action/chunk scheduling, reset omissions, affected future observations reused
after an intervention, and lost task progress. If a predicate cannot be checked
from the record, the evaluator returns a named gap. It does not trust a producer's
`valid: true` as a proof of correct execution. Runtime measurements and adapter
tests still form part of the trusted scope.

For the first comparison, declare finite confirmation obligations. Pair conditions
by their identities; align missingness explicitly. Freeze a correction before
fresh confirmation and do not feed those outcomes into another attempt while
retaining the same confirmation label. Stochastic reliability claims need a
separate justified protocol.

Fable's initial fixtures must mark `evidence_origin: synthetic_development`.
They test evaluator behavior only. Codex's simulator records must identify their
actual origin and cannot reuse the synthetic fixtures as measured outcomes.
Both lanes include a valid positive control so rejection-only software cannot
appear correct by refusing every case.

Codex should commit the smallest usable typed contract and representative record
early. Fable implements only the fields needed to decide the first case. Record
a proposed revision and compatibility consequence in the lane status before
changing required fields; reconcile it at integration.
