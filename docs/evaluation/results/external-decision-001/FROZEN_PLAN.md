# Frozen plan: comparison, interface and costs for external-decision-001

**Version 1, 20 September 2026, committed before any scored output.** A correction to
this plan is a new version; observations stay attached to the version they were scored
under. Case, obligations and candidates are in [`QUALIFICATION.md`](QUALIFICATION.md).

## Input membership and exposure

One externally authored incident: LeRobot issue 4415 with its two comments, at model
revision `c83c3163…` and code commit `5aa74557…`. Eight constructed controls from the
challenge set. The incident is public and both lanes have read the proposed remedy;
the controls are written by this lane. Counts are reported separately and never pooled.
No reserved incident is opened.

## The two arms

**A, conventional.** An engineer with the issue thread, the pinned upstream code, the
retained configuration and statistics files, torch, and the documented upstream remedies.
The frozen procedure: read the thread; list the statistics keys and the processor
features and modes; read `_apply_transform` and `load_state_dict`; try the reporter's
suffix patch and the documented explicit override; verify each with a non-trivial
input in both directions; decide. Deterministic, no model calls. The arm may use the
same cheap numeric witness that B uses.

**B, Nisayon.** The same inputs and candidate space. The execution lane's command
resolves the loaded configuration, runs the frozen checks (obligation per feature and
direction, witness non-vacuity, selector ambiguity and order dependence, identity
legitimacy, structured error versus silent skip), tries each candidate, emits a decision
with reasons, and retains the regression. This lane's evaluator assesses that record
against the independent reference.

**The precise difference.** B makes the per-feature, per-direction obligation table, the
non-vacuity and order-dependence checks and the retained regression explicit and
machine-checked. A performs the same checks by hand from the same information. Both arms
must preserve the useful valid path: C2 with complete statistics must be accepted, and an
IDENTITY feature must not be flagged.

**C, adaptive selection** stays proposed. It is added only if A versus B leaves a real
selection problem that a finite procedure cannot settle; nothing so far suggests one.

## Predicates and outcomes

Per candidate, per arm: `supported_software_correction`, `rejected_candidate` (with the
unmet obligation named), `invalid_input`, or `unresolved` (with the missing observation
named). A process crash is reported as a crash, not as any of these. Per witness: expected
class, expected value, observed value, within tolerance, non-vacuous.

Reported separately: false acceptance (a candidate accepted while an obligation is
unmet), false refusal (C2 with complete statistics or an IDENTITY feature refused),
supported corrections, unresolved outcomes. Refusing everything does not win.

## Stopping rules

Score once per arm on the incident input and once on the eight controls. If A and B reach
the same decision on the incident, the result is a tie and is retained as such; the case
is not replaced. If B disagrees with the independent reference, the producer and reference
records and the smallest reproducer are retained and the owner corrects its
implementation without overwriting the earlier evidence. If the premises P1–P4 fail on the
actual bytes, the hypothesis table is revised in a new version.

## What the evaluator needs from the execution record

The execution lane owns the record schema. The assessment can be produced from any record
that carries:

1. Input identity: repository, revision, path, byte count and sha256 for each configuration
   and statistics file, the pinned source commit and sha256, and the retained local path.
2. Resolved configuration as read from the bytes: for each processor, the normalizer step's
   index and registry name, `features` (name, type, shape), `norm_map`, `eps`,
   `normalize_observation_keys`, and the flat statistics keys with dtype and shape.
3. Extraction recipe: which imports were replaced, by what, and the validity boundary
   (which upstream functions ran unmodified).
4. Executions, each with a candidate label, processor, feature, direction, float32 input
   values, float32 output values, the statistics key the candidate bound (or the list of
   matches if ambiguous), and a status of `completed`, `error` (with the message) or
   `interrupted`.
5. The producer's decision per candidate with reasons, and the overall decision.
6. Costs with denominators: wall and CPU per command, nested versus parent, bytes fetched,
   and explicit `unmeasured` entries.

The evaluator never reads a producer field to decide the expected class or value.

## Budgets and cost scope

Evaluation lane: 2 MiB new source retrieval (3,022 bytes used for two tree listings),
32 MiB new retained artifacts, 600 CPU seconds of software research separate from
required checks. Measured by this lane: source fetches (wall and process CPU), evaluator
commands under the recorder, focused tests, and the required lane check under the
recorder and the shared storage monitor. Unmeasured and reported as unknown: engineering
effort, provider charges, energy, network overhead, peak memory outside sampled checks.
Shared preparation (the coordinator's packet, the two lanes' reading and review) is not
attributed to either arm.

Cost comparison rule: unamortized first; parent and nested command costs are never
summed; a static rejection, a fast command and lower complete engineering effort are
three different claims and are reported as such. An arm's absent expensive run is not a
cost saved.

## Time accounting

Original mission `2026-09-17T21:30:41Z`; earlier phase clocks and pauses as recorded in
the temporal closeout; the earlier five-useful-hours requirement remains unfulfilled and
is not claimed. This block: evaluation start `12:55:20Z`, execution start `12:55:13Z`.
Active effort is not inferred from elapsed spans.
