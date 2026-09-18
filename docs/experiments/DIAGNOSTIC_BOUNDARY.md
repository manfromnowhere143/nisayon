# Diagnostic boundary qualification

At `226496e8238af9bd323cabcdfc44952dd93a80b2`, three known cases exercised
the new diagnostic store and Fable's evaluator before any scored comparison.
Command `a84987f71501427bac87add23d707a25` cost 38.723826 seconds. There are
zero scored incidents and zero fresh confirmation pairs in this qualification.
The unchanged records are under `artifacts/development-boundary-001`; the
[retained manifest](results/development-boundary-001/manifest.json) binds
compressed bundles, decisions and results.

D01 and D03 produced correction candidates; neither is accepted before fresh
confirmation. D03 completed the task with stale observations as expected.
D05 reproduced the carried-state task failure, but B stopped on two integration
findings instead of selecting a correction:

- The prefix uses the older reference deployment record while plan `reference`
  names the typed deployment. The hashes correctly disagree. Execution will
  give typed prefixes a distinct explicit probe plan and freeze their actual
  configuration per run, including the shorter horizon.
- `policy_state_reset.source_step` is a zero-based row index (20); the prefix
  contains 21 rows and `prefix_run.steps` declares 21. Fable's adapter compares
  the row count directly with the index and reports incomplete reset evidence.
  The state chain itself agrees. Fable owns this adapter correction; do not
  change the producer's index into a count or suppress the finding.

Reproduce the second finding without new physics:

```sh
.venv/bin/python -m nisayon.evaluation evaluate \
  artifacts/development-boundary-001/D05-recurrent-carry/execution/bundle.json \
  --artifact-root artifacts/development-boundary-001/D05-recurrent-carry/execution
```

Requests to Fable before scored reset confirmation: check the declared source
index against the actual last row, independently check `prefix_run.steps`
against the row count, and retain a negative control for each mismatch. Also
honor a frozen `configuration_sha256_by_run_id` map: a typed reference prefix
and the main reference share a deployment but have different rollout horizons.

The comparison scorer currently applies its wall ceiling to `timeline`.
Execution will name that field's diagnostic interval explicitly and retain the
separate confirmation interval and total time to confirmation. This preserves
the agreed diagnostic budget without disguising confirmation time. Request:
allow an explicit diagnostic interval plus a full trial timeline so the scorer's
reported elapsed wall can describe the complete result. Physical confirmation
counts are 67 main runs (post-freeze reference, regression, candidate and 32
pairs), plus every executed prefix; they are not hardcoded to 65.

Fable `95e11ba747004c748ebad206b8ca6ab338fab358` is integrated. Its independent
exploration reproduced five runs and found the same state/observation chains;
this is another checkout on the same host, not external replication. Its v3
review accepts the strict result and corrects the earlier v0.1 report labels.
Its published partial cost ledger is now available; future execution ledgers
will bind it without adding overlapping scopes together.

The remaining control paths qualified at execution commit
`5fa5ad2fcdf75b22812c8879efb044234622d6a2`. Command
`c2771fe144f8465bb2d426e08a8fd05b` cost **79.820030 s**, with 15 physical
rollouts and no fresh confirmation. All stores verified. The
[second retained summary](results/development-boundary-002/summary.json)
and compressed bundles/decisions preserve every outcome:

| Assignment | Observed diagnostic result |
|---|---|
| D06 every-action reset | Unsupported fault injection; both runs completed |
| D07 sign and observation backlog | Five runs separate the two obligations and produce a combined candidate |
| D08 old-future replay | Derived control invalid on affected future observation reuse; two physical source runs |
| D09 suppression proposal | Real suppression is validly measured, fails the task and loses progress; legitimate correction candidate remains |
| D10 unavailable recurrent telemetry | Reference completes and regression fails, but both remain unresolved for reset evidence |

D10 no longer has a false raw-digest mismatch. D09 is rejected on task/progress,
with suppression declared deployable and in scope. D06 is retained and is not
replaced by a more favorable incident. These are qualifications of the
procedure, not five completed scored comparisons.

One further evaluator accounting request: D05's first diagnostic decision sums
10.475404710 s over parent and prefix items, while the measured parent-only
total is 9.054182 s. The two prefix durations are already inside their parents.
The execution comparison uses `measured_run_costs` to exclude that duplication;
please preserve `cost_parent_run_id` through translation and apply the same
hierarchy to the evaluator's aggregate. Do not add that raw item sum to phase
or command time.

## Conventional baseline qualification

Arm A's ordinary checks and fixed known-remedy selector are implemented, but
the real diagnostic path has not yet run on the complete proposed assignment
set. Qualify it while the shared scorer/reset corrections are pending. This
also gives the evaluator a current typed-prefix D05 record, without the old
prefix deployment-identity defect obscuring the remaining index interpretation.

```sh
.venv/bin/nisayon run --label conventional-baseline-qualification --timeout 600 -- \
  .venv/bin/python -m nisayon.engine.qualify_development \
  --output artifacts/development-baseline-qualification-001 --arm A \
  --case D01-gripper-sign --case D02-cartesian-axis \
  --case D03-observation-backlog --case D04-observation-hold \
  --case D05-recurrent-carry --case D06-stateless-inference \
  --case D07-sign-and-backlog --case D08-old-future-replay \
  --case D09-action-suppression --case D10-opaque-policy-state
```

The command freezes the chosen arm, all ten known cases, source identity and
diagnostic limits before running. It preserves every result and uses the same
final diagnostic checker. It assigns no fresh conditions, accepts no correction
and produces no comparative score. The earlier B qualifications used different
revisions and schedules; their timings cannot be used as a matched A/B result.
All setup and failed diagnostic work remain preparation for the later scored
suite. The declaration and arm selection were committed at `c7f61d4` before
execution. The [retained result](results/development-baseline-qualification-001/summary.json)
contains every assignment and 33 physical runs, including three actual prefixes.
All ten stores verified. The ordinary procedure produced seven candidates ready
for a future freeze (D01–D05, D07 and D09), retained D06 as unsupported, rejected
D08's replay, and left D10 unresolved. D09's actual suppression failed and was
rejected; the legitimate sign candidate remained. No correction was accepted.

Command `9a3a4e6c12364e81a586ca010285b290` cost 102.711786 s. Diagnostic phases
sum to 99.099503 s and physical run components to 78.411858 s; both are nested
within the command. These are measured baseline diagnostic costs, not a matched
comparison or time to confirmed correction.

The current D05 store separates the remaining evaluator bug from the fixed
producer identity problem. All three prefix records are now valid, as are the
main reference and correction. Only the carried regression is unresolved on
`reset_evidence_incomplete`: its `source_step` is the final index 20 of 21 rows.
The exact current reproducer is:

```sh
.venv/bin/python -m nisayon.evaluation evaluate \
  artifacts/development-baseline-qualification-001/D05-recurrent-carry/execution/bundle.json \
  --artifact-root /Users/danielwahnich/workspace/nisayon-codex/artifacts/development-baseline-qualification-001/D05-recurrent-carry/execution
```

The same new decision double-counts all three prefix durations: it sums
12.780944084 s, while the execution hierarchy gives 10.630919 s. This supersedes
the old two-prefix diagnostic example as the clean typed-record reproducer;
the old records and decisions remain preserved.
