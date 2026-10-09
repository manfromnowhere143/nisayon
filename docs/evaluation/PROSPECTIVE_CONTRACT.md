# Prospective scoring contract

**`nisayon.comparison.v2` and `nisayon.comparison.prospective-score.v2` · consumed and
produced by `python -m nisayon.evaluation prospective` · 19 September 2026, revised
twice the same day.** Revision 2 checked the terminal chain field by field instead of
accepting a digest anywhere in a record and added the eligibility boundary, the
`declaration_unusable` state and the cost scopes below
([`binding-probe-001`](results/audit-2026-09-19/binding-probe-001/before-summary.json)).
Revision 3 checks presence and shape of every field of the three record versions before
any value is compared: revision 2 compared `candidate`, `evidence_scope`, `suite_id`
and `frozen_inputs_sha256` only when present or truthy and treated an absent `observed`
block as ordered, so six omissions passed on the public path
([`required-fields-001`](results/audit-2026-09-19/required-fields-001/before-summary.json)).
The v2 ledger and the writer's receipts are unchanged; the synthetic fixtures, which had
claimed the record versions without their generated bindings, were repaired to the
writer's shape.

The v1 scorer ([SCORING_CONTRACT.md](SCORING_CONTRACT.md)) counts confirmed corrections
and reports one acceptance-policy diagnostic it calls a false acceptance: a claimed
acceptance the shared decision does not support, for any reason. That diagnostic is
retained unchanged, and the two historical ledgers still score byte for byte. It does
not by itself say that a proposed repair was empirically wrong: a claim against an
unresolved decision lacks evidence, a claim against a missing decision has none, and a
claim against a rejected decision has evidence against it. The prospective scorer keeps
those apart, and it reads the arm's claim from a receipt written before the terminal
check rather than from the flag the terminal check produced.

## What the execution lane writes

The receipt is the execution lane's `nisayon.arm-declaration.v1`
([interface proposal](../experiments/DECLARATION_INTERFACE.md) at execution commit
`4cbac86`): one `declaration.json` per assigned case and arm with `assignment`
(`suite_id`, `case_id`, `arm`, `frozen_inputs_sha256`), `candidate` (null unless the arm
claims; `configuration_sha256` binds it), `disposition` (`claim_acceptance`, `abstain`,
`refuse`, `unresolved`), `reason`, `evidence`, `source`, `settings`, `evidence_scope`
(`prospective_execution` or `retained_development_demonstration`), `observed`
(`event_id`, `recorded_at`, `sequence`) and `request_sha256`. The terminal service then
writes `terminal-start.json` (sequence 2) naming the declaration's digest before it
consumes reference evidence, and `terminal-result.json` (sequence 3) naming the start,
the declaration and the terminal decision by digest. A changed declaration is rejected
and its attempted bytes are retained; an identical retry returns the original bytes.

A v2 ledger is a v1 ledger whose trials add:

```json
{
  "declaration": {"path": "D01/A/declaration.json", "sha256": "…"},
  "terminal_start": {"path": "D01/A/terminal-start.json", "sha256": "…"},
  "terminal_result": {"path": "D01/A/terminal-result.json", "sha256": "…"},
  "additional_declarations": [{"path": "D01/A/attempt-1.json", "sha256": "…", "status": "rejected_change"}]
}
```

Every other field keeps its v1 meaning, so `python -m nisayon.evaluation score` reads a
v2 ledger unchanged. Paths resolve against the root (`--root`, default: the ledger's
directory); a path that escapes the root, a missing file, an undeclared or mismatched
digest is `declaration_unverifiable` or `terminal_binding_unverifiable`.

The execution lane's retained-declaration packet (`nisayon.retained-declaration-packet.v1`,
[RETAINED_DECLARATIONS.md](../experiments/RETAINED_DECLARATIONS.md)) is read directly:
`python -m nisayon.evaluation prospective PACKET_DIR --historical-root SUITE_DIR` builds
the v2 ledger from the packet's verified source-ledger copy and rows, resolves receipts
and terminal copies under the packet and the trials' decision, diagnosis, confirmation
and bundle records under the original suite. A receipt's `suite_id` may be the ledger's
suite id, its `case_ledger_sha256` or the packet freeze's id. Rows absent from the
freeze's assignments make the ledger incomplete; rows outside them are malformed.

## The required-field contract of the three record versions

Derived from the writer's own validation (`nisayon.engine.declarations`:
`_validate_payload`, `declare`, `begin_terminal`, `finish_terminal`, `_observed_time`
and the `_checked_*` readers), not from what the scorer happened to check; the machine
form is `REQUIRED_FIELD_TABLE` in `prospective.py` and every non-optional row has a
mutation control in `CONTRACT_MUTATIONS` (absence, explicit null, a type substitute and
a semantic mismatch are distinct boundaries; 72 controls plus the six omissions and a
chain produced by the actual writer). *Required* means the key must be present with the
stated shape; *nullable* means the key is required and null is allowed only where stated;
*optional* means writer-emitted and not validated. Digests inside the records are the
writer's canonical form (sorted keys, compact separators, ASCII-escaped, bare lowercase
hex); the scorer recomputes them with its own implementation of that form.

| Record | Field | Requirement | Rule |
|---|---|---|---|
| declaration | `schema` | required | == nisayon.arm-declaration.v1 |
| declaration | `assignment` | required | object with exactly suite_id, case_id, arm, frozen_inputs_sha256 |
| declaration | `assignment.suite_id` | required | non-empty string; equals the ledger's suite id, case_ledger_sha256 or the packet freeze id |
| declaration | `assignment.case_id` | required | non-empty string; the trial's case or case-arm |
| declaration | `assignment.arm` | required | non-empty string; the trial's arm |
| declaration | `assignment.frozen_inputs_sha256` | required | bare lowercase 64-hex; equals the trial's received_frozen_sha256 |
| declaration | `candidate` | nullable | null only when disposition is not claim_acceptance; otherwise object with exactly configuration (object) and configuration_sha256 == writer digest of configuration |
| declaration | `disposition` | required | one of claim_acceptance, abstain, refuse, unresolved |
| declaration | `reason` | required | non-empty string |
| declaration | `evidence` | required | list (may be empty) of {path, sha256 bare 64-hex} references |
| declaration | `source` | required | non-empty object |
| declaration | `settings` | required | non-empty object |
| declaration | `evidence_scope` | required | prospective_execution or retained_development_demonstration |
| declaration | `request_sha256` | required | == writer digest of the eight caller fields |
| declaration | `source_sha256` | required | == writer digest of source |
| declaration | `settings_sha256` | required | == writer digest of settings |
| declaration | `observed` | required | object: event_id non-empty string, recorded_at ISO 8601 with offset, sequence integer 1 (not a boolean) |
| declaration | `authority` | optional | writer-emitted note; not validated |
| terminal-start | `schema` | required | == nisayon.terminal-start.v1 |
| terminal-start | `declaration` | required | reference {path, sha256}; sha256 equals the trial's declaration digest and path its declaration path |
| terminal-start | `assignment` | required | equals the declaration's complete assignment |
| terminal-start | `candidate` | nullable | key required; equals the declaration's candidate (null only when that is null) |
| terminal-start | `evidence_scope` | required | equals the declaration's evidence_scope |
| terminal-start | `observed` | required | as the declaration's, sequence 2, recorded_at not before the declaration's |
| terminal-start | `order_scope` | optional | writer-emitted note; not validated |
| terminal-result | `schema` | required | == nisayon.terminal-result.v1 |
| terminal-result | `terminal_start` | required | reference; sha256 equals the trial's terminal-start digest and path its path |
| terminal-result | `terminal_evidence` | required | non-empty list of references that verify under the root and include the trial's decision digest |
| terminal-result | `declaration` | required | reference equal to the start's declaration reference |
| terminal-result | `assignment` | required | equals the declaration's assignment |
| terminal-result | `request_sha256` | required | == writer digest of {terminal_start, terminal_evidence} |
| terminal-result | `observed` | required | as the declaration's, sequence 3, recorded_at not before the start's |

A declaration that fails a structural rule is `declaration_malformed` (blocking) and,
like a receipt that belongs to another case, arm, suite or frozen input
(`declaration_mismatch`), leaves the trial in the `declaration_unusable` state: it stays
assigned, its verified reference outcome is retained, and it is not a claim. A start or
result that fails a rule is `terminal_binding_unverifiable` (blocking): the declaration
stays the arm's claim, the reference decides its category, the trial is not prospective
and the report is not a usable study result. Legacy `nisayon.comparison.v1` ledgers
carry no receipts and are read as before; no new requirement is inferred into them, and
a malformed new record is never routed to the legacy path.

## What the scorer establishes per trial

| Step | Check | Finding when it fails |
|---|---|---|
| receipt | bytes under the root match the declared digest and the record satisfies every rule of the table above (structure first), then names this trial's case, arm, suite and received frozen-input digest | `declaration_unverifiable`, `declaration_malformed`, `declaration_mismatch` (all blocking) |
| receipt present | a v2 trial without a receipt | `declaration_missing` (blocking); a v1 trial derives its declaration from `arm_claimed_acceptance` and is labelled `derived_from_v1_arm_claimed_acceptance` |
| receipt usable | a receipt whose bytes do not verify, or that belongs to another case, arm, suite or frozen input, is retained and named but is not this trial's claim | the trial stays assigned in the `declaration_unusable` non-acceptance state; D excludes it, N keeps it, so no rate improves when a claim is damaged |
| ordering | `terminal-start.json` and `terminal-result.json` satisfy every rule of the table above, presence and shape before equality: the start's `declaration` reference, complete `assignment`, `candidate`, `evidence_scope` and `observed` at sequence 2 not before the declaration; the result's `terminal_start` and `declaration` references, complete `assignment`, non-empty verified `terminal_evidence` including the trial's decision, `request_sha256` and `observed` at sequence 3 not before the start. A digest in a reason, a comment, another field or another role satisfies nothing; two incomplete objects that agree with each other bind nothing | `terminal_binding_unverifiable` (blocking); no chain at all is `declaration_order_unverified` (reported), and `prospective` stays false |
| cited evidence | the receipt's `evidence` references verify under the root | `declaration_evidence_unverifiable` (reported: the claim stands, its cited basis does not verify) |
| timestamps | the receipt's `recorded_at` precedes the decision's `decided_at` | `declaration_timestamp_after_reference` (reported; weak evidence either way) |
| retries and changes | an identical extra receipt counts once (`declaration_retry_identical`); a differing receipt the writer marked rejected is `declaration_change_attempted` before or after the reference; a differing accepted receipt is `declaration_ambiguous` (blocking) | |
| reference | the trial's decision verifies and binds exactly as in v1 (`verify_trial_decision`) | v1 findings apply |

`prospective` is true for a trial only when the chain verifies and the scope is
`prospective_execution`. The report's `declarations.reading` is `prospective` when every
trial is, `retrospective` when every declaration is derived from a v1 ledger,
`development_demonstration` when every receipt carries the demonstration scope, and
`mixed` otherwise. Byte containment establishes local ordering and integrity; it does
not establish custody, and a writer holding every key could fabricate the chain.

## Claim categories and the reference

For a `claim_acceptance` declaration the terminal reference is the verified decision
bound to the execution the trial names, under the suite's obligation
(`first-case-obligation-v0.2`, simulated task, measured predicates, fresh conditions):

| Category | Reference | Meaning |
|---|---|---|
| `supported` (C) | `accepted` on the declared candidate, among the arm's proposals | the frozen scoped obligation holds on verified evidence |
| `contradicted` (F) | `rejected`: a valid observation against the obligation (`progress_lost`, `regression_on_fresh_condition`, `reproduction_not_fixed`, `constraint_violated`, `timing_obligation_violated`, …), codes reported | evidence against the claim |
| `unsupported_insufficient_evidence` (U) | `unresolved` | the reference could not decide; not contradicted |
| `unsupported_invalid_experiment` (U) | `invalid` | the experiment could not answer |
| `unknown_reference_missing` (K) | no decision named | interrupted or never adjudicated |
| `unknown_reference_unverifiable` (K) | bytes missing, corrupt or another case | no verifiable reference |
| `unknown_reference_unbound` (K) | not bound to this trial's execution | someone else's decision |
| `unknown_reference_candidate_mismatch` (K) | the decision adjudicates another candidate | the claim was never adjudicated |

`D = C + F + U + K` per arm, and product acceptance is `supported` only: an unsupported
or unknown claim is never accepted, exactly as in v1, and a supported claim on a trial
that exceeded its diagnostic budget keeps its category but is not a product acceptance
(`claim_over_budget`; v1 counts that trial as a timeout). A non-acceptance is one of
`abstain`, `refuse`, `unresolved`, `invalid_experiment`, `unsupported_capability`,
`timeout`, `not_attempted`, `no_declaration` or `declaration_unusable`, and
`N = D + non-acceptances`.

## Eligibility boundary

Four things are kept apart and none rewrites another: the reference outcome (the
verified decision), the claim's correctness (its category), study validity and product
eligibility. Every trial carries `eligibility`: `study` is false when a blocking finding
names the trial (`declaration_*`, `terminal_binding_unverifiable`, or a v1 blocking code
such as `decision_unverifiable`) or when a report-level blocking finding exists
(`arms_not_matched`, `cost_unit_conflict`, an undeclared agent); `product` is
`eligible` for a supported claim whose decision has no decision-level blocker and that is
not over budget, `ineligible` for a supported claim that has one (with the codes), and
`not_accepted` otherwise. Arm totals carry `usable_as_study_result`, and the report's
`eligibility` block names the blocking findings; the text rendering states the boundary
before the table and marks each ineligible trial. A malformed or unbound receipt
therefore never becomes prospective evidence through its scope label, and a blocking
finding never leaves an acceptance in the summary without saying what it is eligible for.

A refusal is adjudicated only from references that exist: `correct_refusal` when the
arm's own candidate was rejected, when the case is a pre-registered invalid control, or
when a case premise is refuted by valid measurements (`regression_not_reproduced` with
both runs measured and complete); `missed_correct_opportunity` when the arm's own
candidate was accepted or the paired arm had a candidate accepted under the same frozen
obligation; otherwise `refusal_unadjudicated`. A premise left unestablished by
insufficient evidence (D10's null reset digests) adjudicates nothing, and a refusal is
never called wrong because an analyst can imagine a repair.

## Costs by scope

`costs_by_scope` reports, side by side and never summed: the historical trial costs per
arm (phase walls with the simulator wall nested; `own_trial_wall` is their disjoint sum);
the shared preparation ledger read from its bound bytes (`known_command_wall_sum_s`, the
number of summed, nested-not-added and unmeasured commands, its unmeasured categories;
one suite-level number shared by both arms, not amortized and not added to any arm);
the packet's new processing (its outer wall, with per-arm terminal reads and writer
attempts listed as nested components that may overlap, unknown-cost and incomplete
attempts counted, new model calls and simulator executions); this run's scoring wall as
an evaluation-lane cost; and every unknown category with its reason. On the real packet
the nested sums equal the execution lane's exported `costs.tsv` to the last digit (test).

## What the report carries

Per arm: N, D, C, F, U, K, every non-acceptance state, the refusal adjudications, the
product-accepted count beside the v1 confirmed count and v1 false-acceptance diagnostic,
the contradiction codes, how many trials are prospective, and the rates D/N, C/N, F/N,
F/D (when D > 0), U/D, K/D, reference coverage (C+F)/D, F/C as a supplementary quantity
(undefined when C = 0), the upper bound (F+U+K)/N that counts every unadjudicated claim
as wrong, exact binomial intervals for F/N and C/N, and correct or missed refusals over
non-acceptances. Costs reuse the v1 aggregation per component (known total, trials that
reported it, trials that declared it unknown), add cost per correct claim and per
declared acceptance with every assigned trial in the numerator, the cumulative resource
time (the sum of disjoint phase walls; simulator wall stays nested), the diagnostic and
full elapsed walls, rollouts and retries, and a category table (preparation, diagnosis,
proposal validation, simulation including prefixes, confirmation, retries, model calls,
adjudication, human effort, provider charges, energy) that says which are reported,
declared unknown or not reported. An all-abstaining arm gets `method_never_accepts`.

`fair` is the v1 fairness with the blocking findings above added. The exit code records
execution: 0 when fair, 1 otherwise.

## Retained output

[`results/audit-2026-09-19/`](results/audit-2026-09-19/README.md) holds the two
historical ledgers read as retrospective tables (D = C = 6 and 3 per arm, nothing
contradicted, three correct refusals and one unadjudicated per arm on the ten cases), a
labelled derived control on the ten-case ledger
([derived-control-001](results/audit-2026-09-19/derived-control-001.prospective.txt):
arm A's receipts claim D05 and abstain on D07 while every record stays the retained one,
so the one contradicted claim and the one missed opportunity are read from real bytes and
the declarations say they are synthetic), and the execution lane's real packet
([retained-declarations-002](results/audit-2026-09-19/retained-declarations-002.prospective.txt):
fair, `development_demonstration`, per arm N 10, D 7, C 6, F 1 on D05 with
`progress_lost`, two correct refusals and one unadjudicated, nothing prospective because
the receipts postdate the decisions they bind). None of these is an effectiveness
estimate. The study these semantics serve is in [PROSPECTIVE_STUDY.md](PROSPECTIVE_STUDY.md).

[Scoring contract v1](SCORING_CONTRACT.md) · [Study](PROSPECTIVE_STUDY.md) · [Evaluator overview](README.md)
