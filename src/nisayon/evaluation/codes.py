"""Reason codes for evaluation findings.

Each code has one severity. A decision takes the strongest severity among the
findings that bear on it: ``invalid`` (the experiment or protocol cannot answer
the question), ``rejected`` (a valid observation shows an obligation failed),
``unresolved`` (a named gap prevents a decision) or ``info`` (retained context).
"""

from __future__ import annotations

INVALID = "invalid"
REJECTED = "rejected"
UNRESOLVED = "unresolved"
INFO = "info"

# Record integrity
MALFORMED_RECORD = "malformed_record"
ARTIFACT_MISSING = "artifact_missing"
ARTIFACT_DIGEST_MISMATCH = "artifact_digest_mismatch"
IDENTITY_MISMATCH = "identity_mismatch"
SYNTHETIC_PRESENTED_AS_MEASUREMENT = "synthetic_fixture_presented_as_measurement"

# Execution and measurement validity
PROCESS_INCOMPLETE = "process_incomplete"
RECORDED_OBSERVATION_IN_FULL_RERUN = "recorded_observation_in_full_rerun"
AFFECTED_FUTURE_OBSERVATION_REUSED = "affected_future_observation_reused"
RECORDED_OBSERVATION_FROM_UNDECLARED_SOURCE = "recorded_observation_from_undeclared_source"
DIVERGENCE_PRECEDES_ACTIVATION = "divergence_precedes_declared_activation"
SOURCE_RUN_MISSING = "source_run_missing"
PREFIX_REUSE_CONDITION_MISMATCH = "prefix_reuse_initial_condition_mismatch"
OBSERVATION_AFTER_ACTION = "observation_after_action"
UNKNOWN_OBSERVATION_REFERENCE = "unknown_observation_reference"
NON_MONOTONE_CLOCK = "non_monotone_clock"
CHUNK_SCHEDULE_INCONSISTENT = "chunk_schedule_inconsistent"
RESET_EVIDENCE_INCOMPLETE = "reset_evidence_incomplete"
RESET_CONDITION_MISMATCH = "reset_condition_mismatch"
CANDIDATE_NOT_ON_CHANGED_REVISION = "candidate_run_not_on_changed_revision"
MEASUREMENT_UNIT_UNDECLARED = "measurement_unit_undeclared"
PREDICATE_UNMEASURABLE = "predicate_unmeasurable"

# Task obligations (valid observations that fail a declared obligation)
OUTCOME_FAILED = "outcome_failed_observed"
PROGRESS_LOST = "progress_lost"
CONSTRAINT_VIOLATED = "constraint_violated"
TIMING_OBLIGATION_VIOLATED = "timing_obligation_violated"
REGRESSION_ON_FRESH_CONDITION = "regression_on_fresh_condition"
REPRODUCTION_NOT_FIXED = "reproduction_not_fixed"
DIAGNOSTIC_ORACLE_IN_CANDIDATE = "diagnostic_oracle_in_candidate"
CANDIDATE_OUTSIDE_REPAIR_SCOPE = "candidate_outside_repair_scope"

# Case premises
REFERENCE_NOT_ESTABLISHED = "reference_not_established"
REGRESSION_NOT_REPRODUCED = "regression_not_reproduced"

# Confirmation protocol
CONFIRMATION_MISSING = "confirmation_missing"
PROTOCOL_MISMATCH = "protocol_mismatch"
CANDIDATE_NOT_FROZEN = "candidate_not_frozen"
RUN_PRECEDES_FREEZE = "run_precedes_freeze"
CONFIRMATION_CONDITION_REUSED = "confirmation_condition_reused"
CONTAMINATION_DECLARED = "contamination_declared"
CONDITION_UNASSIGNED = "condition_unassigned"
ASSIGNED_OUTCOME_MISSING = "assigned_outcome_missing"
MULTIPLE_RUNS_PER_CONDITION_ROLE = "multiple_runs_per_condition_role"
ASSIGNMENT_ROLE_MISMATCH = "assignment_role_mismatch"
ASSIGNED_RUN_INVALID = "assigned_run_invalid"
ASSIGNED_RUN_UNRESOLVED = "assigned_run_unresolved"
REPRODUCTION_NOT_CONFIRMED = "reproduction_not_confirmed"
CONFIRMATION_UNINFORMATIVE = "confirmation_conditions_uninformative"
PAIRED_INITIAL_STATE_MISMATCH = "paired_initial_state_mismatch"

# Evidence sufficiency for declared obligations
TIMING_UNMEASURED = "timing_unmeasured"
CAPTURE_STAMPS_INCONSISTENT = "capture_stamps_inconsistent"
RESET_OBLIGATION_VIOLATED = "reset_obligation_violated"
IDENTITY_UNBOUND = "identity_unbound"
CANDIDATE_DEPLOYABILITY_UNDECLARED = "candidate_deployability_undeclared"
ARTIFACT_MANIFEST_MISSING = "artifact_manifest_missing"
ARTIFACT_STORE_UNVERIFIED = "artifact_store_unverified"
REPRODUCTION_NOT_POST_FREEZE = "reproduction_not_post_freeze"
PREREGISTRATION_MISSING = "preregistration_missing"
HISTORY_UNREADABLE = "history_unreadable"
CALIBRATION_ONLY = "calibration_only"

# Adapter-level evidence checks on execution-lane bundles
TRACE_CHAIN_BROKEN = "trace_chain_broken"
RAW_TRACE_MISMATCH = "raw_trace_mismatch"
MEASUREMENT_INCONSISTENT = "measurement_inconsistent"
POLICY_RESET_STATE_DIFFERS = "policy_reset_state_differs"
REPEAT_RUNS_DIFFER = "repeat_runs_differ"
PROTOCOL_UNVERIFIED = "protocol_unverified"

# Retained context
RAW_ARTIFACT_VERIFIED = "raw_artifact_verified"
RAW_ARTIFACT_UNVERIFIED = "raw_artifact_unverified"
REPRODUCTION_EVIDENCE_PRECEDES_FREEZE = "reproduction_evidence_precedes_freeze"
INTENDED_ACTION_OUT_OF_BOUNDS = "intended_action_out_of_bounds"
QUALIFICATION_REPEAT = "qualification_repeat"
PROTOCOL_VERIFIED = "protocol_verified"
HISTORY_ABSENT = "history_absent"
HISTORY_CONTAINS_THIS_RECORD = "history_contains_this_record"
HISTORY_LATER_RECORDS = "history_later_records"
RAW_TRACE_CONSISTENT = "raw_trace_consistent"
IDENTITY_INHERITED = "identity_inherited"
IDENTITY_VERIFIED = "identity_verified"
CANDIDATE_DEPLOYABILITY_ASSUMED = "candidate_deployability_assumed"
RESET_CARRIED_STATE = "reset_carried_state"
ARTIFACT_MANIFEST_VERIFIED = "artifact_manifest_verified"
PREDICATE_NOT_PREREGISTERED = "predicate_not_preregistered"
PRODUCER_CLAIM_DISAGREES = "producer_claim_disagrees"
PRODUCER_VALIDITY_CLAIM_IGNORED = "producer_validity_claim_ignored"
REFERENCE_FAILED_CONDITION = "reference_failed_on_condition"
CANDIDATE_IMPROVED_CONDITION = "candidate_completed_where_reference_failed"
INTERVENTION_DECLARED = "intervention_declared"

SEVERITY: dict[str, str] = {
    MALFORMED_RECORD: INVALID,
    ARTIFACT_MISSING: UNRESOLVED,
    ARTIFACT_DIGEST_MISMATCH: INVALID,
    IDENTITY_MISMATCH: INVALID,
    SYNTHETIC_PRESENTED_AS_MEASUREMENT: INVALID,
    PROCESS_INCOMPLETE: UNRESOLVED,
    RECORDED_OBSERVATION_IN_FULL_RERUN: INVALID,
    AFFECTED_FUTURE_OBSERVATION_REUSED: INVALID,
    RECORDED_OBSERVATION_FROM_UNDECLARED_SOURCE: INVALID,
    DIVERGENCE_PRECEDES_ACTIVATION: INVALID,
    SOURCE_RUN_MISSING: UNRESOLVED,
    PREFIX_REUSE_CONDITION_MISMATCH: UNRESOLVED,
    OBSERVATION_AFTER_ACTION: INVALID,
    UNKNOWN_OBSERVATION_REFERENCE: INVALID,
    NON_MONOTONE_CLOCK: INVALID,
    CHUNK_SCHEDULE_INCONSISTENT: INVALID,
    RESET_EVIDENCE_INCOMPLETE: UNRESOLVED,
    RESET_CONDITION_MISMATCH: INVALID,
    CANDIDATE_NOT_ON_CHANGED_REVISION: INVALID,
    MEASUREMENT_UNIT_UNDECLARED: UNRESOLVED,
    PREDICATE_UNMEASURABLE: UNRESOLVED,
    OUTCOME_FAILED: REJECTED,
    PROGRESS_LOST: REJECTED,
    CONSTRAINT_VIOLATED: REJECTED,
    TIMING_OBLIGATION_VIOLATED: REJECTED,
    REGRESSION_ON_FRESH_CONDITION: REJECTED,
    REPRODUCTION_NOT_FIXED: REJECTED,
    DIAGNOSTIC_ORACLE_IN_CANDIDATE: REJECTED,
    CANDIDATE_OUTSIDE_REPAIR_SCOPE: REJECTED,
    REFERENCE_NOT_ESTABLISHED: UNRESOLVED,
    REGRESSION_NOT_REPRODUCED: UNRESOLVED,
    CONFIRMATION_MISSING: UNRESOLVED,
    PROTOCOL_MISMATCH: INVALID,
    CANDIDATE_NOT_FROZEN: INVALID,
    RUN_PRECEDES_FREEZE: INVALID,
    CONFIRMATION_CONDITION_REUSED: INVALID,
    CONTAMINATION_DECLARED: INVALID,
    CONDITION_UNASSIGNED: UNRESOLVED,
    ASSIGNED_OUTCOME_MISSING: UNRESOLVED,
    MULTIPLE_RUNS_PER_CONDITION_ROLE: INVALID,
    ASSIGNMENT_ROLE_MISMATCH: INVALID,
    ASSIGNED_RUN_INVALID: INVALID,
    ASSIGNED_RUN_UNRESOLVED: UNRESOLVED,
    REPRODUCTION_NOT_CONFIRMED: UNRESOLVED,
    CONFIRMATION_UNINFORMATIVE: UNRESOLVED,
    PAIRED_INITIAL_STATE_MISMATCH: UNRESOLVED,
    TIMING_UNMEASURED: UNRESOLVED,
    CAPTURE_STAMPS_INCONSISTENT: INVALID,
    RESET_OBLIGATION_VIOLATED: REJECTED,
    IDENTITY_UNBOUND: UNRESOLVED,
    CANDIDATE_DEPLOYABILITY_UNDECLARED: UNRESOLVED,
    ARTIFACT_MANIFEST_MISSING: UNRESOLVED,
    ARTIFACT_STORE_UNVERIFIED: UNRESOLVED,
    REPRODUCTION_NOT_POST_FREEZE: UNRESOLVED,
    PREREGISTRATION_MISSING: UNRESOLVED,
    HISTORY_UNREADABLE: UNRESOLVED,
    CALIBRATION_ONLY: UNRESOLVED,
    IDENTITY_INHERITED: INFO,
    IDENTITY_VERIFIED: INFO,
    CANDIDATE_DEPLOYABILITY_ASSUMED: INFO,
    RESET_CARRIED_STATE: INFO,
    ARTIFACT_MANIFEST_VERIFIED: INFO,
    PREDICATE_NOT_PREREGISTERED: INFO,
    TRACE_CHAIN_BROKEN: INVALID,
    RAW_TRACE_MISMATCH: INVALID,
    RAW_TRACE_CONSISTENT: INFO,
    MEASUREMENT_INCONSISTENT: INVALID,
    POLICY_RESET_STATE_DIFFERS: UNRESOLVED,
    REPEAT_RUNS_DIFFER: UNRESOLVED,
    PROTOCOL_UNVERIFIED: UNRESOLVED,
    RAW_ARTIFACT_VERIFIED: INFO,
    RAW_ARTIFACT_UNVERIFIED: INFO,
    REPRODUCTION_EVIDENCE_PRECEDES_FREEZE: INFO,
    INTENDED_ACTION_OUT_OF_BOUNDS: INFO,
    QUALIFICATION_REPEAT: INFO,
    PROTOCOL_VERIFIED: INFO,
    HISTORY_ABSENT: INFO,
    HISTORY_CONTAINS_THIS_RECORD: INFO,
    HISTORY_LATER_RECORDS: INFO,
    PRODUCER_CLAIM_DISAGREES: INFO,
    PRODUCER_VALIDITY_CLAIM_IGNORED: INFO,
    REFERENCE_FAILED_CONDITION: INFO,
    CANDIDATE_IMPROVED_CONDITION: INFO,
    INTERVENTION_DECLARED: INFO,
}

RANK = {INVALID: 3, REJECTED: 2, UNRESOLVED: 1, INFO: 0}


def strongest(severities: list[str]) -> str:
    """Return the strongest severity present, or ``info`` when there is none."""
    return max(severities, key=lambda s: RANK[s], default=INFO)
