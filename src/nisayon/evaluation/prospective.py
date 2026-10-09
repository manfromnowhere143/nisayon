"""Prospective decision-quality scoring: an arm's declaration against a terminal reference.

The v1 scorer (:mod:`nisayon.evaluation.scoring`) counts confirmed corrections and reports
an acceptance-policy diagnostic it calls a false acceptance: a claimed acceptance the shared
decision does not support, whatever the reason. That diagnostic and its historical output
stay as they are. This module adds the distinction a quality study needs and never re-runs
anything:

* a **declaration** is the arm's claim, recorded before terminal reference evidence
  (``nisayon.arm-declaration.v1`` receipts written by the execution lane). A
  ``nisayon.comparison.v1`` ledger has no receipts, so its declarations are derived from
  ``arm_claimed_acceptance`` and labelled retrospective; they were written by the same run
  that produced the decision and cannot show a pre-reference disagreement;
* a **supported** claim has a verified terminal decision ``accepted`` on the declared
  candidate, bound to the execution the trial names;
* a **contradicted** claim has a verified terminal decision ``rejected``: a valid
  observation against the frozen obligation, named by code;
* an **unsupported** claim has a terminal decision that could not decide: ``unresolved``
  (insufficient evidence) or ``invalid`` (the experiment could not answer);
* an **unknown** claim has no verifiable terminal reference: missing, corrupt, not bound
  to this trial, or adjudicating a different candidate than the one declared.

Product acceptance stays fail-closed: only a supported claim counts as accepted. Per arm,
``D = C + F + U + K`` and ``N = D + non-acceptances``. Rates carry their denominators; a
zero denominator leaves the rate undefined, never zero.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path

from .codes import REJECTED
from .schema import Malformed, load_json, parse_wall_time
from .scoring import BLOCKING as SCORING_BLOCKING
from .scoring import (
    LEDGER_SCHEMA,
    _same_digest,
    _verify_record,
    parse_ledger,
    score_comparison,
    verify_trial_decision,
)

LEDGER_SCHEMA_V2 = "nisayon.comparison.v2"
REPORT_SCHEMA = "nisayon.comparison.prospective-score.v2"
DECLARATION_SCHEMA = "nisayon.arm-declaration.v1"
CLAIM = "claim_acceptance"
DISPOSITIONS = {CLAIM, "abstain", "refuse", "unresolved"}
PROSPECTIVE_SCOPE = "prospective_execution"
DEMONSTRATION_SCOPE = "retained_development_demonstration"
DERIVED_SCOPE = "retrospective_v1_ledger"

SUPPORTED = "supported"
CONTRADICTED = "contradicted"
UNSUPPORTED_INSUFFICIENT = "unsupported_insufficient_evidence"
UNSUPPORTED_INVALID = "unsupported_invalid_experiment"
UNKNOWN_MISSING = "unknown_reference_missing"
UNKNOWN_UNVERIFIABLE = "unknown_reference_unverifiable"
UNKNOWN_UNBOUND = "unknown_reference_unbound"
UNKNOWN_MISMATCH = "unknown_reference_candidate_mismatch"
UNSUPPORTED = (UNSUPPORTED_INSUFFICIENT, UNSUPPORTED_INVALID)
UNKNOWN = (UNKNOWN_MISSING, UNKNOWN_UNVERIFIABLE, UNKNOWN_UNBOUND, UNKNOWN_MISMATCH)
CLAIM_CATEGORIES = (SUPPORTED, CONTRADICTED, *UNSUPPORTED, *UNKNOWN)
NON_ACCEPTANCE_STATES = (
    "abstain",
    "refuse",
    "unresolved",
    "invalid_experiment",
    "unsupported_capability",
    "timeout",
    "not_attempted",
    "no_declaration",
    "declaration_unusable",
)
CORRECT_REFUSAL = "correct_refusal"
MISSED = "missed_correct_opportunity"
UNADJUDICATED = "refusal_unadjudicated"
BLOCKING = {
    "declaration_unverifiable",
    "declaration_malformed",
    "declaration_mismatch",
    "declaration_missing",
    "declaration_ambiguous",
    "terminal_binding_unverifiable",
}
# v1 findings that make a trial's own decision unusable as a product acceptance; the
# other v1 blocking codes (unmatched arms, unit conflicts, undeclared agents) block the
# comparison, not the verified decision of one trial.
PRODUCT_BLOCKING = {
    "decision_unverifiable",
    "decision_not_bound_to_trial",
    "trial_record_unverifiable",
    "decision_shared_between_arms",
    "frozen_inputs_differ",
    "trial_duplicated",
    "invalid_case_confirmed",
}
# The cost categories a complete prospective ledger accounts for, mapped to the ledger
# components that report them. A category nobody reports stays unknown, never zero.
COST_CATEGORIES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("preparation_and_import", ("preparation_wall", "import_wall"), "shared preparation ledger"),
    ("diagnosis", ("diagnostic_wall",), "phase wall"),
    ("proposal_validation", ("proposal_validation_wall",), "phase wall"),
    (
        "simulation_including_prefixes",
        ("simulator_wall", "prefix_simulator_wall"),
        "nested in phase walls; never added to them",
    ),
    ("confirmation", ("confirmation_wall",), "phase wall"),
    ("retries_and_failures", ("retry_wall", "failed_attempt_wall"), "retries also counted"),
    ("model_calls_and_tokens", ("agent_tokens", "model_calls"), "tokens; charges separate"),
    (
        "adjudication",
        ("adjudication_wall",),
        "falls back to evaluation_wall_s of verified decisions, nested in confirmation",
    ),
    ("human_effort", ("engineer_time",), "unknown unless tracked"),
    ("provider_and_compute_charges", ("provider_and_compute_charges",), "unknown unless billed"),
    ("energy", ("energy",), "unknown unless metered"),
)
_HEX64 = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")


def _norm(digest: object) -> str | None:
    if not isinstance(digest, str):
        return None
    found = _HEX64.match(digest.strip())
    return found.group(1).lower() if found else None


def _reference(raw: object) -> dict | None:
    if isinstance(raw, dict) and isinstance(raw.get("path"), str) and raw["path"].strip():
        return {"path": raw["path"], "sha256": raw.get("sha256")}
    return None


def _load_bound(reference: dict, root: Path | None) -> tuple[dict | None, str | None]:
    """The record's JSON when its bytes verify under the root, else why not."""
    problem = _verify_record(reference, root)
    if problem is not None:
        return None, problem
    try:
        record = load_json((root / reference["path"]).resolve())
    except Malformed as error:
        return None, f"malformed: {error}"
    if not isinstance(record, dict):
        return None, "not a JSON object"
    return record, None


def _wall(value: object, path: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return parse_wall_time({"value": value, "clock": "wall_utc"}, path)
    except Malformed:
        return None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator > 0 else None


def clopper_pearson(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float] | None:
    """Exact binomial interval by bisection on the binomial tails; None when ``trials`` is 0.

    It treats the trials as exchangeable, which repeated seeds and incident families
    violate; the report says so beside every interval.
    """
    if trials <= 0 or not 0 <= successes <= trials:
        return None
    half = alpha / 2

    def upper_tail(p: float) -> float:  # P[X >= successes]
        return sum(
            math.comb(trials, k) * p**k * (1 - p) ** (trials - k)
            for k in range(successes, trials + 1)
        )

    def lower_tail(p: float) -> float:  # P[X <= successes]
        return sum(
            math.comb(trials, k) * p**k * (1 - p) ** (trials - k) for k in range(0, successes + 1)
        )

    def solve(function, target: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(200):
            mid = (low + high) / 2
            if function(mid) < target:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    lower = 0.0 if successes == 0 else solve(upper_tail, half)
    upper = 1.0 if successes == trials else 1.0 - solve(lambda p: lower_tail(1 - p), half)
    return (round(lower, 6), round(upper, 6))


def _writer_digest(value: object) -> str:
    """The execution writer's canonical digest (``nisayon.engine.io.digest``): sorted keys,
    compact separators, ASCII-escaped, no NaN. Kept here so the consumer verifies the
    writer's bindings with its own implementation of the documented form."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


_WRITER_SHA = re.compile(r"^[0-9a-f]{64}$")

# The finite required-field contract of the three record versions, derived from the
# writer's validation (``_validate_payload``, ``declare``, ``begin_terminal``,
# ``finish_terminal``, ``_observed_time``, ``_checked_*``) rather than from what the
# scorer happened to check. ``requirement`` is one of required, conditional, nullable
# (null allowed but the key required), optional (writer-emitted, not validated).
REQUIRED_FIELD_TABLE: tuple[dict, ...] = (
    {
        "record": "declaration",
        "field": "schema",
        "requirement": "required",
        "rule": "== nisayon.arm-declaration.v1",
    },
    {
        "record": "declaration",
        "field": "assignment",
        "requirement": "required",
        "rule": "object with exactly suite_id, case_id, arm, frozen_inputs_sha256",
    },
    {
        "record": "declaration",
        "field": "assignment.suite_id",
        "requirement": "required",
        "rule": "non-empty string; equals the ledger's suite id, case_ledger_sha256 or the packet freeze id",
    },
    {
        "record": "declaration",
        "field": "assignment.case_id",
        "requirement": "required",
        "rule": "non-empty string; the trial's case or case-arm",
    },
    {
        "record": "declaration",
        "field": "assignment.arm",
        "requirement": "required",
        "rule": "non-empty string; the trial's arm",
    },
    {
        "record": "declaration",
        "field": "assignment.frozen_inputs_sha256",
        "requirement": "required",
        "rule": "bare lowercase 64-hex; equals the trial's received_frozen_sha256",
    },
    {
        "record": "declaration",
        "field": "candidate",
        "requirement": "nullable",
        "rule": "null only when disposition is not claim_acceptance; otherwise object with exactly configuration (object) and configuration_sha256 == writer digest of configuration",
    },
    {
        "record": "declaration",
        "field": "disposition",
        "requirement": "required",
        "rule": "one of claim_acceptance, abstain, refuse, unresolved",
    },
    {
        "record": "declaration",
        "field": "reason",
        "requirement": "required",
        "rule": "non-empty string",
    },
    {
        "record": "declaration",
        "field": "evidence",
        "requirement": "required",
        "rule": "list (may be empty) of {path, sha256 bare 64-hex} references",
    },
    {
        "record": "declaration",
        "field": "source",
        "requirement": "required",
        "rule": "non-empty object",
    },
    {
        "record": "declaration",
        "field": "settings",
        "requirement": "required",
        "rule": "non-empty object",
    },
    {
        "record": "declaration",
        "field": "evidence_scope",
        "requirement": "required",
        "rule": "prospective_execution or retained_development_demonstration",
    },
    {
        "record": "declaration",
        "field": "request_sha256",
        "requirement": "required",
        "rule": "== writer digest of the eight caller fields",
    },
    {
        "record": "declaration",
        "field": "source_sha256",
        "requirement": "required",
        "rule": "== writer digest of source",
    },
    {
        "record": "declaration",
        "field": "settings_sha256",
        "requirement": "required",
        "rule": "== writer digest of settings",
    },
    {
        "record": "declaration",
        "field": "observed",
        "requirement": "required",
        "rule": "object: event_id non-empty string, recorded_at ISO 8601 with offset, sequence integer 1 (not a boolean)",
    },
    {
        "record": "declaration",
        "field": "authority",
        "requirement": "optional",
        "rule": "writer-emitted note; not validated",
    },
    {
        "record": "terminal-start",
        "field": "schema",
        "requirement": "required",
        "rule": "== nisayon.terminal-start.v1",
    },
    {
        "record": "terminal-start",
        "field": "declaration",
        "requirement": "required",
        "rule": "reference {path, sha256}; sha256 equals the trial's declaration digest and path its declaration path",
    },
    {
        "record": "terminal-start",
        "field": "assignment",
        "requirement": "required",
        "rule": "equals the declaration's complete assignment",
    },
    {
        "record": "terminal-start",
        "field": "candidate",
        "requirement": "nullable",
        "rule": "key required; equals the declaration's candidate (null only when that is null)",
    },
    {
        "record": "terminal-start",
        "field": "evidence_scope",
        "requirement": "required",
        "rule": "equals the declaration's evidence_scope",
    },
    {
        "record": "terminal-start",
        "field": "observed",
        "requirement": "required",
        "rule": "as the declaration's, sequence 2, recorded_at not before the declaration's",
    },
    {
        "record": "terminal-start",
        "field": "order_scope",
        "requirement": "optional",
        "rule": "writer-emitted note; not validated",
    },
    {
        "record": "terminal-result",
        "field": "schema",
        "requirement": "required",
        "rule": "== nisayon.terminal-result.v1",
    },
    {
        "record": "terminal-result",
        "field": "terminal_start",
        "requirement": "required",
        "rule": "reference; sha256 equals the trial's terminal-start digest and path its path",
    },
    {
        "record": "terminal-result",
        "field": "terminal_evidence",
        "requirement": "required",
        "rule": "non-empty list of references that verify under the root and include the trial's decision digest",
    },
    {
        "record": "terminal-result",
        "field": "declaration",
        "requirement": "required",
        "rule": "reference equal to the start's declaration reference",
    },
    {
        "record": "terminal-result",
        "field": "assignment",
        "requirement": "required",
        "rule": "equals the declaration's assignment",
    },
    {
        "record": "terminal-result",
        "field": "request_sha256",
        "requirement": "required",
        "rule": "== writer digest of {terminal_start, terminal_evidence}",
    },
    {
        "record": "terminal-result",
        "field": "observed",
        "requirement": "required",
        "rule": "as the declaration's, sequence 3, recorded_at not before the start's",
    },
)
ASSIGNMENT_KEYS = {"suite_id", "case_id", "arm", "frozen_inputs_sha256"}
CALLER_FIELDS = (
    "assignment",
    "candidate",
    "disposition",
    "reason",
    "evidence",
    "source",
    "settings",
    "evidence_scope",
)


def _check_writer_reference(value: object, label: str) -> list[str]:
    """A writer reference is an object with a non-empty path and a bare 64-hex digest."""
    if not isinstance(value, dict):
        return [f"{label} is not a path/digest reference"]
    problems = []
    if not isinstance(value.get("path"), str) or not value["path"].strip():
        problems.append(f"{label}.path is not a non-empty string")
    if not isinstance(value.get("sha256"), str) or not _WRITER_SHA.match(value["sha256"]):
        problems.append(f"{label}.sha256 is not a bare lowercase 64-hex digest")
    return problems


def _check_observed(record: dict, expected: int, label: str) -> tuple[list[str], datetime | None]:
    """The writer's observed block: event id, timezone-aware clock, integer sequence."""
    if "observed" not in record:
        return [f"{label}.observed is absent"], None
    observed = record["observed"]
    if not isinstance(observed, dict):
        return [f"{label}.observed is not an object"], None
    problems = []
    if not isinstance(observed.get("event_id"), str) or not observed["event_id"].strip():
        problems.append(f"{label}.observed.event_id is not a non-empty string")
    sequence = observed.get("sequence")
    if type(sequence) is not int:
        problems.append(
            f"{label}.observed.sequence is not an integer (found {type(sequence).__name__})"
        )
    elif sequence != expected:
        problems.append(f"{label}.observed.sequence is {sequence}, not {expected}")
    recorded = observed.get("recorded_at")
    stamp = None
    if not isinstance(recorded, str):
        problems.append(f"{label}.observed.recorded_at is not a string")
    else:
        stamp = _wall(recorded, f"{label}.observed.recorded_at")
        if stamp is None:
            problems.append(f"{label}.observed.recorded_at is not ISO 8601 with a UTC offset")
    return problems, stamp


def _check_assignment(value: object, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}.assignment is not an object"]
    problems = []
    keys = set(value)
    if keys != ASSIGNMENT_KEYS:
        missing = sorted(ASSIGNMENT_KEYS - keys)
        extra = sorted(keys - ASSIGNMENT_KEYS)
        problems.append(
            f"{label}.assignment keys are incomplete or extended"
            + (f"; missing {missing}" if missing else "")
            + (f"; unexpected {extra}" if extra else "")
        )
    for name in ("suite_id", "case_id", "arm"):
        if name in value and (not isinstance(value[name], str) or not value[name].strip()):
            problems.append(f"{label}.assignment.{name} is not a non-empty string")
    if "frozen_inputs_sha256" in value and (
        not isinstance(value["frozen_inputs_sha256"], str)
        or not _WRITER_SHA.match(value["frozen_inputs_sha256"])
    ):
        problems.append(f"{label}.assignment.frozen_inputs_sha256 is not a bare 64-hex digest")
    return problems


def _check_declaration_structure(record: dict) -> tuple[list[str], datetime | None]:
    """The declaration record against its version's contract; returns problems and the
    observed clock. Values are not compared with the trial here."""
    problems: list[str] = []
    if record.get("schema") != DECLARATION_SCHEMA:
        problems.append(f"schema {record.get('schema')!r} is not {DECLARATION_SCHEMA}")
    missing = [name for name in CALLER_FIELDS if name not in record]
    if missing:
        problems.append(f"caller fields absent: {missing}")
    problems.extend(_check_assignment(record.get("assignment"), "declaration"))
    # Type before membership: an unhashable substitute (an object, a list) must be a
    # finding, never an exception that loses the report.
    disposition = record.get("disposition")
    if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
        problems.append(f"disposition {disposition!r} is not one of {sorted(DISPOSITIONS)}")
    scope = record.get("evidence_scope")
    if not isinstance(scope, str) or scope not in (PROSPECTIVE_SCOPE, DEMONSTRATION_SCOPE):
        problems.append(f"evidence_scope {scope!r} is not a known scope")
    if not isinstance(record.get("reason"), str) or not record["reason"].strip():
        problems.append("reason is not a non-empty string")
    for name in ("source", "settings"):
        if not isinstance(record.get(name), dict) or not record[name]:
            problems.append(f"{name} is not a non-empty object")
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        problems.append("evidence is not a list")
    else:
        for index, item in enumerate(evidence):
            problems.extend(_check_writer_reference(item, f"evidence[{index}]"))
    if "candidate" in record:
        candidate = record["candidate"]
        if candidate is None:
            if disposition == CLAIM:
                problems.append("a claim_acceptance declaration names no candidate")
        elif not isinstance(candidate, dict):
            problems.append("candidate is neither null nor an object")
        elif set(candidate) != {"configuration", "configuration_sha256"}:
            problems.append("candidate keys are not exactly configuration and configuration_sha256")
        elif not isinstance(candidate["configuration"], dict):
            problems.append("candidate.configuration is not an object")
        elif not isinstance(candidate["configuration_sha256"], str) or not _WRITER_SHA.match(
            candidate["configuration_sha256"]
        ):
            problems.append("candidate.configuration_sha256 is not a bare 64-hex digest")
        elif candidate["configuration_sha256"] != _writer_digest(candidate["configuration"]):
            problems.append("candidate.configuration_sha256 is not the digest of its configuration")
    if not missing:
        payload = {name: record[name] for name in CALLER_FIELDS}
        for field, value in (
            ("request_sha256", payload),
            ("source_sha256", record.get("source")),
            ("settings_sha256", record.get("settings")),
        ):
            declared = record.get(field)
            if not isinstance(declared, str) or not _WRITER_SHA.match(declared):
                problems.append(f"{field} is absent or not a bare 64-hex digest")
            elif value is not None and declared != _writer_digest(value):
                problems.append(f"{field} is not the writer digest of its content")
    observed_problems, stamp = _check_observed(record, 1, "declaration")
    problems.extend(observed_problems)
    return problems, stamp


def _receipt(
    record: dict, trial: dict, suite_ids: set[str], arm_id: str
) -> tuple[dict, list[str], list[str]]:
    """Interpret a verified declaration receipt for this trial.

    Returns the declaration, the structural problems (the record does not satisfy its
    version's contract: ``declaration_malformed``) and the identity problems (a well-formed
    receipt that belongs to another case, arm, suite or frozen input:
    ``declaration_mismatch``). Presence and shape are checked before any value is
    compared, so an absent field never passes as agreement.
    """
    malformed, recorded_at = _check_declaration_structure(record)
    mismatch: list[str] = []
    assignment = record.get("assignment") if isinstance(record.get("assignment"), dict) else {}
    case_id = assignment.get("case_id")
    if not isinstance(case_id, str) or case_id not in (
        trial["case_id"],
        f"{trial['case_id']}-{arm_id}",
    ):
        mismatch.append(f"receipt is for case {case_id!r}, not {trial['case_id']!r}")
    if assignment.get("arm") != arm_id:
        mismatch.append(f"receipt is for arm {assignment.get('arm')!r}, not {arm_id!r}")
    declared_suite = assignment.get("suite_id")
    if not suite_ids:
        mismatch.append("the ledger names no suite identity to bind the receipt's suite_id")
    elif not isinstance(declared_suite, str) or declared_suite not in suite_ids:
        mismatch.append(f"receipt is for suite {declared_suite!r}, not one of {sorted(suite_ids)}")
    frozen = assignment.get("frozen_inputs_sha256")
    received = _norm(trial.get("received_frozen_sha256"))
    if received is None:
        mismatch.append("the trial names no received frozen-input digest to bind the receipt")
    elif not isinstance(frozen, str) or not _same_digest(frozen, received):
        mismatch.append("receipt's frozen inputs differ from the inputs the trial received")
    candidate = record.get("candidate") if isinstance(record.get("candidate"), dict) else {}
    declaration = {
        "origin": "receipt",
        "disposition": record.get("disposition"),
        "candidate_digest": candidate.get("configuration_sha256"),
        "evidence_scope": record.get("evidence_scope"),
        "recorded_at": recorded_at.isoformat() if recorded_at else None,
        "sequence": (record.get("observed") or {}).get("sequence")
        if isinstance(record.get("observed"), dict)
        else None,
        "reason": record.get("reason"),
        "source": record.get("source"),
        "_recorded_at": recorded_at,
    }
    return declaration, malformed, mismatch


def _derived(trial: dict, status: str) -> dict:
    """A declaration derived from a v1 trial: retrospective, ordering unverifiable."""
    claimed = trial.get("arm_claimed_acceptance") is True or trial["declared_status"] == "confirmed"
    executed = [p for p in trial["proposals"] if p.get("executed")]
    declared = (trial.get("decision") or {}).get("candidate_digest")
    candidate = None
    if claimed:
        matching = [p for p in executed if _same_digest(p.get("candidate_digest"), declared)]
        chosen = (matching or executed or [None])[-1]
        candidate = chosen.get("candidate_digest") if chosen else declared
    if claimed:
        disposition = CLAIM
    elif trial["declared_status"] == "unresolved" or status == "unresolved":
        disposition = "unresolved"
    elif trial["proposals"]:
        disposition = "refuse"
    else:
        disposition = "abstain"
    return {
        "origin": "derived_from_v1_arm_claimed_acceptance",
        "disposition": disposition,
        "candidate_digest": candidate,
        "evidence_scope": DERIVED_SCOPE,
        "recorded_at": None,
        "sequence": None,
        "reason": "; ".join(str(p.get("reason")) for p in trial["proposals"] if p.get("reason"))
        or None,
        "source": None,
        "_recorded_at": None,
    }


TERMINAL_START_SCHEMA = "nisayon.terminal-start.v1"
TERMINAL_RESULT_SCHEMA = "nisayon.terminal-result.v1"


def _link(
    record: dict, field: str, expected: str | None, expected_path: str | None, label: str
) -> list[str]:
    """``record[field]`` must be a writer reference to the expected digest (and path)."""
    if field not in record:
        return [f"{label}.{field} is absent"]
    problems = _check_writer_reference(record[field], f"{label}.{field}")
    if problems:
        return problems
    reference = record[field]
    if expected is None or not _same_digest(reference["sha256"], expected):
        problems.append(
            f"{label}.{field} names digest {reference['sha256'][:19]!r}, not the expected one"
        )
    if expected_path is not None and reference["path"] != expected_path:
        problems.append(f"{label}.{field}.path is {reference['path']!r}, not {expected_path!r}")
    return problems


def _terminal_chain(
    raw: dict,
    root: Path | None,
    declaration: dict | None,
    declaration_digest: str | None,
    declaration_at: datetime | None,
    decision_digest: str | None,
) -> dict:
    """Verify the execution lane's terminal-start and terminal-result records field by field.

    Each required field must be present with its documented shape before its value is
    compared (``REQUIRED_FIELD_TABLE``): an absent key, a null where the contract allows
    none, a boolean where an integer sequence is required or two incomplete objects that
    agree with each other never establish a binding. A digest anywhere else (a reason, a
    comment, another role) satisfies nothing. Byte containment and field agreement
    establish local ordering, not custody.
    """
    start_ref = _reference(raw.get("terminal_start"))
    result_ref = _reference(raw.get("terminal_result"))
    chain = {"verified": False, "how": "", "start": start_ref, "result": result_ref}
    if start_ref is None and result_ref is None:
        chain["how"] = "no terminal-start or terminal-result record named"
        return chain
    problems: list[str] = []
    declaration_path = (_reference(raw.get("declaration")) or {}).get("path")
    assignment = (declaration or {}).get("assignment")
    candidate = (declaration or {}).get("candidate")
    scope = (declaration or {}).get("evidence_scope")
    start_digest = None
    start_at = None
    if start_ref is None:
        problems.append("terminal-start not named")
    else:
        start, problem = _load_bound(start_ref, root)
        if problem:
            problems.append(f"terminal-start: {problem}")
        elif start.get("schema") != TERMINAL_START_SCHEMA:
            problems.append(
                f"terminal-start schema {start.get('schema')!r} is not {TERMINAL_START_SCHEMA}"
            )
        else:
            start_digest = _norm(start_ref["sha256"])
            problems.extend(
                _link(start, "declaration", declaration_digest, declaration_path, "terminal-start")
            )
            problems.extend(_check_assignment(start.get("assignment"), "terminal-start"))
            if "assignment" in start and start["assignment"] != assignment:
                problems.append("terminal-start assignment differs from the declaration's")
            if "candidate" not in start:
                problems.append("terminal-start.candidate is absent")
            elif start["candidate"] != candidate:
                problems.append("terminal-start candidate differs from the declaration's")
            if "evidence_scope" not in start:
                problems.append("terminal-start.evidence_scope is absent")
            elif start["evidence_scope"] != scope:
                problems.append("terminal-start evidence_scope differs from the declaration's")
            observed_problems, start_at = _check_observed(start, 2, "terminal-start")
            problems.extend(observed_problems)
            if start_at is not None and declaration_at is not None and start_at < declaration_at:
                problems.append("terminal-start precedes the declaration in the writer's clock")
    if result_ref is None:
        problems.append("terminal-result not named")
    else:
        result, problem = _load_bound(result_ref, root)
        if problem:
            problems.append(f"terminal-result: {problem}")
        elif result.get("schema") != TERMINAL_RESULT_SCHEMA:
            problems.append(
                f"terminal-result schema {result.get('schema')!r} is not {TERMINAL_RESULT_SCHEMA}"
            )
        else:
            problems.extend(
                _link(
                    result, "declaration", declaration_digest, declaration_path, "terminal-result"
                )
            )
            problems.extend(
                _link(
                    result,
                    "terminal_start",
                    start_digest,
                    (start_ref or {}).get("path"),
                    "terminal-result",
                )
            )
            problems.extend(_check_assignment(result.get("assignment"), "terminal-result"))
            if "assignment" in result and result["assignment"] != assignment:
                problems.append("terminal-result assignment differs from the declaration's")
            evidence = result.get("terminal_evidence")
            if "terminal_evidence" not in result:
                problems.append("terminal-result.terminal_evidence is absent")
            elif not isinstance(evidence, list) or not evidence:
                problems.append("terminal-result names no terminal evidence")
            else:
                names_decision = False
                for index, item in enumerate(evidence):
                    shape = _check_writer_reference(item, f"terminal_evidence[{index}]")
                    if shape:
                        problems.extend(shape)
                        continue
                    problem = _verify_record(item, root)
                    if problem:
                        problems.append(f"terminal_evidence[{index}] {item['path']!r}: {problem}")
                    if decision_digest is not None and _same_digest(
                        item["sha256"], decision_digest
                    ):
                        names_decision = True
                if not names_decision:
                    problems.append(
                        "terminal_evidence does not include the trial's terminal decision"
                    )
            request_digest = result.get("request_sha256")
            if not isinstance(request_digest, str) or not _WRITER_SHA.match(request_digest):
                problems.append(
                    "terminal-result.request_sha256 is absent or not a bare 64-hex digest"
                )
            elif "terminal_start" in result and "terminal_evidence" in result:
                expected = _writer_digest(
                    {
                        "terminal_start": result["terminal_start"],
                        "terminal_evidence": result["terminal_evidence"],
                    }
                )
                if request_digest != expected:
                    problems.append(
                        "terminal-result.request_sha256 is not the writer digest of its "
                        "terminal_start and terminal_evidence"
                    )
            observed_problems, result_at = _check_observed(result, 3, "terminal-result")
            problems.extend(observed_problems)
            if result_at is not None and start_at is not None and result_at < start_at:
                problems.append("terminal-result precedes the terminal-start in the writer's clock")
    chain["verified"] = not problems
    chain["how"] = (
        "; ".join(problems)
        if problems
        else "declaration → terminal-start → terminal-result → decision, fields verified"
    )
    return chain


def _classify_reference(verification: dict, declaration: dict, trial: dict) -> tuple[str, str]:
    if trial.get("decision") is None:
        return UNKNOWN_MISSING, "no terminal decision record named"
    if not verification["verified"]:
        return UNKNOWN_UNVERIFIABLE, verification["how"]
    if not verification["bound"]:
        return UNKNOWN_UNBOUND, verification["binding_problem"] or "not bound"
    decision = verification["decision"]
    candidate = verification.get("candidate")
    declared = declaration.get("candidate_digest")
    if declaration["disposition"] == CLAIM and declared and candidate:
        if not _same_digest(declared, candidate):
            return UNKNOWN_MISMATCH, (
                f"the declaration claims candidate {str(declared)[:19]!r}; the terminal "
                f"decision adjudicates {str(candidate)[:19]!r}"
            )
    if declaration["disposition"] == CLAIM and decision == "accepted":
        proposals = trial["proposals"]
        if (
            proposals
            and candidate
            and not any(_same_digest(p.get("candidate_digest"), candidate) for p in proposals)
        ):
            return UNKNOWN_MISMATCH, "the accepted candidate is not among the arm's proposals"
    if decision == "accepted":
        return SUPPORTED, "verified decision accepted on the declared candidate"
    if decision == "rejected":
        codes = sorted(
            {r["code"] for r in verification.get("reasons", []) if r.get("severity") == REJECTED}
        )
        return CONTRADICTED, f"verified decision rejected: {', '.join(codes) or 'no code'}"
    if decision == "unresolved":
        codes = sorted({r["code"] for r in verification.get("reasons", []) if r.get("code")})
        return UNSUPPORTED_INSUFFICIENT, f"verified decision unresolved: {', '.join(codes) or '-'}"
    if decision == "invalid":
        codes = sorted({r["code"] for r in verification.get("reasons", []) if r.get("code")})
        return UNSUPPORTED_INVALID, f"verified decision invalid: {', '.join(codes) or '-'}"
    return UNKNOWN_UNVERIFIABLE, f"decision {decision!r} is not a known verdict"


def _adjudicate_refusal(
    category: str, verification: dict, case: dict, paired: list[str]
) -> tuple[str, str]:
    """Whether a non-acceptance was right, from references that actually exist."""
    if category == SUPPORTED:
        return MISSED, "the arm's own frozen candidate was accepted by the terminal reference"
    if category == CONTRADICTED:
        return CORRECT_REFUSAL, f"own candidate reference: {verification.get('decision')}"
    if case.get("intended_class") == "invalid":
        return CORRECT_REFUSAL, "pre-registered invalid-experiment control; no correction exists"
    codes = {r.get("code") for r in verification.get("reasons", [])}
    premise_codes = sorted(codes & {"regression_not_reproduced", "reference_not_established"})
    if premise_codes:
        # A premise refuted by valid measurements (both runs complete: no fault to repair)
        # adjudicates the refusal; a premise left unestablished by insufficient evidence
        # (unmeasured reset state, missing stamps) adjudicates nothing.
        runs = [
            r
            for r in (verification.get("run_measurements") or {}).values()
            if r.get("role") in ("reference", "regression")
        ]
        if runs and all(r.get("measurement") == "valid" for r in runs):
            return CORRECT_REFUSAL, (
                f"case premise refuted by valid measurements: {', '.join(premise_codes)}"
            )
        return UNADJUDICATED, (
            f"case premise unestablished on insufficient evidence: {', '.join(premise_codes)}"
        )
    if paired:
        return MISSED, (
            f"paired arm {', '.join(paired)} had a candidate accepted under the same frozen "
            "obligation; the refusal left an adjudicated correction on the table"
        )
    return UNADJUDICATED, "no terminal reference adjudicates this refusal either way"


def _non_acceptance_state(declaration: dict | None, status: str, problem: str | None) -> str:
    if status == "not_attempted":
        return "not_attempted"
    if declaration is None and problem is not None:
        return "declaration_unusable"
    if status in ("invalid", "unsupported", "timeout"):
        return {"invalid": "invalid_experiment", "unsupported": "unsupported_capability"}.get(
            status, status
        )
    if declaration is None:
        return "no_declaration"
    return declaration["disposition"]


def _extra_receipts(
    raw: dict,
    root: Path | None,
    bound: dict | None,
    bound_digest: str | None,
    decided_at: datetime | None,
) -> tuple[list[dict], list[dict]]:
    """Retries and attempted changes the writer retained beside the bound declaration."""
    entries: list[dict] = []
    findings: list[dict] = []
    for item in raw.get("additional_declarations") or []:
        reference = _reference(item)
        if reference is None:
            continue
        record, problem = _load_bound(reference, root)
        entry = {"path": reference["path"], "classification": None, "detail": None}
        if problem:
            entry["classification"] = "unverifiable"
            entry["detail"] = problem
            findings.append(
                {"code": "declaration_unverifiable", "detail": f"{reference['path']}: {problem}"}
            )
            entries.append(entry)
            continue
        marked_rejected = (
            (isinstance(item, dict) and item.get("status") == "rejected_change")
            or record.get("accepted") is False
            or record.get("rejected") is True
        )
        same_content = bound is not None and all(
            record.get(key) == bound.get(key)
            for key in ("assignment", "candidate", "disposition", "evidence_scope")
        )
        recorded = _wall(
            (record.get("observed") or {}).get("recorded_at")
            if isinstance(record.get("observed"), dict)
            else None,
            "additional.observed.recorded_at",
        )
        if _norm(reference["sha256"]) == bound_digest:
            entry["classification"] = "bound_declaration"
        elif same_content:
            entry["classification"] = "retry_identical"
            entry["detail"] = "same assignment, candidate, disposition and scope; counted once"
            findings.append(
                {
                    "code": "declaration_retry_identical",
                    "detail": f"{reference['path']}: a retried receipt with the same content; "
                    "counted once, its cost stays retained",
                }
            )
        else:
            when = "unknown"
            if recorded and decided_at:
                when = "after" if recorded > decided_at else "before"
            if marked_rejected:
                entry["classification"] = f"change_attempted_{when}_reference"
                entry["detail"] = "the writer rejected the change; the original stands"
                findings.append(
                    {
                        "code": "declaration_change_attempted",
                        "detail": f"{reference['path']}: a changed declaration was attempted "
                        f"{when} the terminal reference and rejected by the writer; the bound "
                        "declaration is scored",
                    }
                )
            else:
                entry["classification"] = "ambiguous"
                entry["detail"] = "a second accepted declaration with different content"
                findings.append(
                    {
                        "code": "declaration_ambiguous",
                        "detail": f"{reference['path']}: a second accepted declaration differs "
                        "from the bound one and is not marked as a rejected change; the arm's "
                        "claim is not unique",
                    }
                )
        entries.append(entry)
    return entries, findings


def score_prospective(
    ledger: object, root: Path | None = None, historical_root: Path | None = None
) -> dict:
    """Score a comparison ledger prospectively; see the module docstring.

    ``root`` resolves declaration and terminal receipts; ``historical_root`` resolves the
    trials' decision, diagnosis and confirmation records when they live elsewhere (a
    declaration packet beside the original suite). It defaults to ``root``.
    """
    started = time.perf_counter()
    records_root = root if historical_root is None else historical_root
    v1 = score_comparison(ledger, records_root)
    report: dict = {
        "schema": REPORT_SCHEMA,
        "fair": False,
        "ledger_schema": None,
        "suite": v1.get("suite"),
        "declarations": None,
        "arms": {},
        "trials": [],
        "findings": list(v1["findings"]),
        "v1_score": {"fair": v1["fair"], "solver_kind": v1["solver_kind"]},
        "limits": [
            "A declaration derived from a v1 ledger was written by the run that produced the "
            "decision; it cannot show a pre-reference disagreement and is labelled retrospective.",
            "Byte containment establishes local ordering and integrity, not custody.",
            "Contradicted means a verified decision rejected the claimed candidate under the "
            "frozen obligation on the simulated task and measured predicates; it is not physical "
            "truth, and the terminal evaluator and simulator are common to both arms.",
            "Unknown truth is not false truth: F/N is the observed contradicted rate, and the "
            "upper bound counts every unadjudicated claim as wrong.",
            "Exact binomial intervals treat cases as exchangeable; repeated seeds and incident "
            "families violate that, and overlapping intervals do not establish equivalence.",
            "An arm that never accepts has zero contradicted claims by construction; read C/N "
            "and D/N with F/N.",
            "Cost per correct includes the cost of every assigned trial, including failures and "
            "refusals; unknown components stay unknown.",
        ],
    }
    findings = report["findings"]
    if any(f["code"] == "malformed_ledger" for f in findings):
        return report
    parsed = parse_ledger(ledger)
    report["ledger_schema"] = parsed["schema"]
    v2 = parsed["schema"] == LEDGER_SCHEMA_V2
    suite_ids = set(parsed["suite_ids"])
    cases, arms = parsed["cases"], parsed["arms"]
    by_key: dict[tuple[str, str], tuple[dict, dict]] = {}
    for trial, raw in zip(parsed["trials"], parsed["raw_trials"], strict=True):
        by_key.setdefault((trial["arm"], trial["case_id"]), (trial, raw))

    trials: dict[tuple[str, str], dict] = {}
    for arm_id in arms:
        for case_id, case in cases.items():
            status = v1["cases"][case_id]["outcomes"][arm_id]
            entry: dict = {
                "arm": arm_id,
                "case_id": case_id,
                "family": case.get("family"),
                "intended_class": case.get("intended_class"),
                "status": status,
                "declaration": None,
                "ordering": {"verified": False, "how": "", "timestamp_order": "unknown"},
                "prospective": False,
                "reference": None,
                "claim_category": None,
                "non_acceptance_state": None,
                "refusal": None,
                "product_accepted": False,
                "declaration_problem": None,
                "eligibility": None,
                "additional_receipts": [],
                "costs": {},
            }
            if (arm_id, case_id) not in by_key:
                entry["non_acceptance_state"] = "not_attempted"
                entry["reference"] = {"category": None, "how": "no trial", "decision": None}
                trials[(arm_id, case_id)] = entry
                continue
            trial, raw = by_key[(arm_id, case_id)]
            entry["costs"] = {name: quantity.value for name, quantity in trial["costs"].items()}
            if isinstance(raw.get("packet_row"), dict):
                entry["packet_row"] = raw["packet_row"]
            verification = verify_trial_decision(trial, records_root, arm_id)
            decided_at = _wall(verification.get("decided_at"), "decision.decided_at")
            decision_digest = _norm((trial.get("decision") or {}).get("sha256"))
            declaration: dict | None = None
            declaration_digest = None
            bound_record = None
            reference = _reference(raw.get("declaration"))
            if reference is not None:
                record, problem = _load_bound(reference, root)
                if problem:
                    entry["declaration_problem"] = f"unverifiable: {problem}"
                    findings.append(
                        {
                            "code": "declaration_unverifiable",
                            "detail": f"arm {arm_id!r} names a declaration for {case_id!r} that "
                            f"cannot be verified: {problem}",
                            "arm": arm_id,
                            "case_id": case_id,
                        }
                    )
                else:
                    declaration, malformed, problems = _receipt(record, trial, suite_ids, arm_id)
                    declaration["path"] = reference["path"]
                    declaration["sha256"] = _norm(reference["sha256"])
                    declaration_digest = declaration["sha256"]
                    bound_record = record
                    if malformed:
                        # The record does not satisfy its version's contract; it is
                        # retained and named, and it is not this trial's claim.
                        entry["declaration_problem"] = "malformed: " + "; ".join(malformed)
                        entry["unusable_declaration"] = {
                            k: v for k, v in declaration.items() if k != "_recorded_at"
                        }
                        findings.append(
                            {
                                "code": "declaration_malformed",
                                "detail": f"arm {arm_id!r}, case {case_id!r}: the receipt does "
                                "not satisfy nisayon.arm-declaration.v1: " + "; ".join(malformed),
                                "arm": arm_id,
                                "case_id": case_id,
                            }
                        )
                    cited = [
                        (_reference(item), index)
                        for index, item in enumerate(record.get("evidence") or [])
                    ]
                    unverifiable = [
                        f"evidence[{index}] {(item or {}).get('path')!r}: "
                        f"{_verify_record(item, root) if item else 'not a path/digest reference'}"
                        for item, index in cited
                        if item is None or _verify_record(item, root) is not None
                    ]
                    if unverifiable:
                        findings.append(
                            {
                                "code": "declaration_evidence_unverifiable",
                                "detail": f"arm {arm_id!r}, case {case_id!r}: the receipt cites "
                                "evidence that does not verify under the root: "
                                + "; ".join(unverifiable),
                                "arm": arm_id,
                                "case_id": case_id,
                            }
                        )
                    if problems:
                        # A receipt for another case, arm, suite or frozen input is not
                        # this trial's claim; it is retained, named and not scored.
                        entry["declaration_problem"] = (
                            (
                                entry["declaration_problem"] + "; "
                                if entry["declaration_problem"]
                                else ""
                            )
                            + "mismatch: "
                            + "; ".join(problems)
                        )
                        entry["unusable_declaration"] = {
                            k: v for k, v in declaration.items() if k != "_recorded_at"
                        }
                        findings.append(
                            {
                                "code": "declaration_mismatch",
                                "detail": f"arm {arm_id!r}, case {case_id!r}: "
                                + "; ".join(problems),
                                "arm": arm_id,
                                "case_id": case_id,
                            }
                        )
                    if malformed or problems:
                        declaration = None
                        bound_record = None
            elif not v2:
                declaration = _derived(trial, status)
            else:
                findings.append(
                    {
                        "code": "declaration_missing",
                        "detail": f"arm {arm_id!r} has no declaration receipt for {case_id!r}; "
                        "a v2 ledger needs one for every assigned case",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
            if declaration is not None:
                if declaration["origin"] == "receipt":
                    chain = _terminal_chain(
                        raw,
                        root,
                        bound_record,
                        declaration_digest,
                        declaration.get("_recorded_at"),
                        decision_digest,
                    )
                    entry["ordering"]["verified"] = chain["verified"]
                    entry["ordering"]["how"] = chain["how"]
                    if chain["start"] is None and chain["result"] is None:
                        findings.append(
                            {
                                "code": "declaration_order_unverified",
                                "detail": f"arm {arm_id!r}, case {case_id!r}: the declaration is "
                                "not bound by a terminal-start/terminal-result chain; its order "
                                "against the reference rests on timestamps only",
                                "arm": arm_id,
                                "case_id": case_id,
                            }
                        )
                    elif not chain["verified"]:
                        findings.append(
                            {
                                "code": "terminal_binding_unverifiable",
                                "detail": f"arm {arm_id!r}, case {case_id!r}: {chain['how']}",
                                "arm": arm_id,
                                "case_id": case_id,
                            }
                        )
                    recorded = declaration.pop("_recorded_at")
                    if recorded and decided_at:
                        entry["ordering"]["timestamp_order"] = (
                            "consistent" if recorded < decided_at else "inconsistent"
                        )
                        if recorded >= decided_at:
                            findings.append(
                                {
                                    "code": "declaration_timestamp_after_reference",
                                    "detail": f"arm {arm_id!r}, case {case_id!r}: the receipt's "
                                    "recorded_at is not before the decision's decided_at",
                                    "arm": arm_id,
                                    "case_id": case_id,
                                }
                            )
                    entry["prospective"] = (
                        chain["verified"] and declaration["evidence_scope"] == PROSPECTIVE_SCOPE
                    )
                    extras, extra_findings = _extra_receipts(
                        raw, root, bound_record, declaration_digest, decided_at
                    )
                    entry["additional_receipts"] = extras
                    for finding in extra_findings:
                        findings.append({**finding, "arm": arm_id, "case_id": case_id})
                else:
                    declaration.pop("_recorded_at", None)
                    entry["ordering"]["how"] = (
                        "derived from arm_claimed_acceptance; recorded with the decision"
                    )
            entry["declaration"] = declaration
            category, how = _classify_reference(
                verification, declaration or {"disposition": None, "candidate_digest": None}, trial
            )
            entry["reference"] = {
                "category": category,
                "how": how,
                "decision": verification.get("decision"),
                "candidate_digest": verification.get("candidate"),
                "path": (trial.get("decision") or {}).get("path"),
                "decided_at": verification.get("decided_at"),
                "evaluation_wall_s": verification.get("evaluation_wall_s"),
                "codes": sorted(
                    {r["code"] for r in verification.get("reasons", []) if r.get("code")}
                ),
                "premises": verification.get("premises") or {},
            }
            entry["_verification"] = verification
            trials[(arm_id, case_id)] = entry

    # Second pass: claims, refusals (which may look at the paired arm), product acceptance.
    for (arm_id, case_id), entry in trials.items():
        declaration = entry["declaration"]
        category = entry["reference"]["category"]
        if declaration is not None and declaration["disposition"] == CLAIM:
            entry["claim_category"] = category
            # A claim on a trial that exceeded its diagnostic budget keeps its category
            # (the reference answers the quality question) but is not a product acceptance:
            # the v1 scorer counts that trial as a timeout, not a confirmation.
            entry["over_budget"] = entry["status"] == "timeout"
            entry["product_accepted"] = category == SUPPORTED and not entry["over_budget"]
            # finalized by the eligibility pass below (decision-level blockers)
            if entry["over_budget"]:
                findings.append(
                    {
                        "code": "claim_over_budget",
                        "detail": f"arm {arm_id!r} claimed acceptance on {case_id!r} after "
                        "exceeding its diagnostic budget; the claim is classified "
                        f"{category!r} and is not a product acceptance",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
            if category == CONTRADICTED:
                findings.append(
                    {
                        "code": "claim_contradicted",
                        "detail": f"arm {arm_id!r} claimed acceptance on {case_id!r}; "
                        f"{entry['reference']['how']}",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
            elif category == UNKNOWN_MISSING:
                findings.append(
                    {
                        "code": "reference_missing",
                        "detail": f"arm {arm_id!r} claimed acceptance on {case_id!r} and no terminal "
                        "decision is named; the claim is unknown, not false",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
            elif category == UNKNOWN_MISMATCH:
                findings.append(
                    {
                        "code": "reference_candidate_mismatch",
                        "detail": f"arm {arm_id!r}, case {case_id!r}: {entry['reference']['how']}",
                        "arm": arm_id,
                        "case_id": case_id,
                    }
                )
        else:
            entry["non_acceptance_state"] = _non_acceptance_state(
                declaration, entry["status"], entry.get("declaration_problem")
            )
            if entry["status"] != "not_attempted":
                paired = sorted(
                    other
                    for (other, other_case), other_entry in trials.items()
                    if other_case == case_id
                    and other != arm_id
                    and other_entry["reference"]["category"] == SUPPORTED
                    and (other_entry["declaration"] or {}).get("disposition") == CLAIM
                )
                adjudication, source = _adjudicate_refusal(
                    category, entry.get("_verification") or {}, cases[case_id], paired
                )
                entry["refusal"] = {"adjudication": adjudication, "source": source}
                if adjudication == MISSED:
                    findings.append(
                        {
                            "code": "refusal_missed_correct_opportunity",
                            "detail": f"arm {arm_id!r} did not accept on {case_id!r}; {source}",
                            "arm": arm_id,
                            "case_id": case_id,
                        }
                    )
        entry.pop("_verification", None)

    # Eligibility boundary: reference outcome, claim correctness, study validity and
    # product eligibility are different things. A blocking finding on a trial makes it
    # unusable for the study; a blocking finding on its decision (or an over-budget claim)
    # removes it from product acceptance; neither rewrites the verified reference.
    report_blockers = sorted(
        {
            f["code"]
            for f in findings
            if f["code"] in BLOCKING or f["code"] in SCORING_BLOCKING
            if not f.get("case_id")
        }
    )
    for (arm_id, case_id), entry in trials.items():
        mine = [
            f for f in findings if f.get("case_id") == case_id and f.get("arm") in (arm_id, None)
        ]
        study_blockers = sorted(
            {f["code"] for f in mine if f["code"] in BLOCKING or f["code"] in SCORING_BLOCKING}
        )
        product_blockers = sorted({f["code"] for f in mine if f["code"] in PRODUCT_BLOCKING})
        if entry.get("over_budget"):
            product_blockers.append("claim_over_budget")
        supported = entry["claim_category"] == SUPPORTED
        entry["product_accepted"] = supported and not product_blockers
        entry["eligibility"] = {
            "study": not study_blockers and not report_blockers,
            "study_blockers": study_blockers + [f"report:{c}" for c in report_blockers],
            "product": "eligible"
            if entry["product_accepted"]
            else "ineligible"
            if supported
            else "not_accepted",
            "product_blockers": product_blockers if supported else [],
        }

    for arm_id, arm in arms.items():
        arm_trials = [entry for (a, _), entry in trials.items() if a == arm_id]
        n = len(arm_trials)
        claims = [t for t in arm_trials if t["claim_category"] is not None]
        counts = {category: 0 for category in CLAIM_CATEGORIES}
        for t in claims:
            counts[t["claim_category"]] += 1
        d = len(claims)
        c = counts[SUPPORTED]
        f = counts[CONTRADICTED]
        u = sum(counts[k] for k in UNSUPPORTED)
        k = sum(counts[k] for k in UNKNOWN)
        states = {state: 0 for state in NON_ACCEPTANCE_STATES}
        for t in arm_trials:
            if t["non_acceptance_state"] is not None:
                states[t["non_acceptance_state"]] += 1
        refusals = {CORRECT_REFUSAL: 0, MISSED: 0, UNADJUDICATED: 0}
        for t in arm_trials:
            if t["refusal"] is not None:
                refusals[t["refusal"]["adjudication"]] += 1
        contradiction_codes: dict[str, int] = {}
        for t in claims:
            if t["claim_category"] == CONTRADICTED:
                for code in t["reference"]["codes"]:
                    contradiction_codes[code] = contradiction_codes.get(code, 0) + 1
        origins = {t["declaration"]["origin"] for t in arm_trials if t["declaration"]}
        prospective_trials = sum(1 for t in arm_trials if t["prospective"])
        assert d == c + f + u + k, "claim categories must partition the declared acceptances"
        assert n == d + sum(states.values()), "every assigned case is a claim or a non-acceptance"
        if d == 0:
            findings.append(
                {
                    "code": "method_never_accepts",
                    "detail": f"arm {arm_id!r} declared no acceptance on {n} assigned cases; zero "
                    "contradicted claims is not evidence of quality (C/N = 0, D/N = 0)",
                    "arm": arm_id,
                }
            )
        v1_arm = v1["arms"][arm_id]
        costs = v1_arm["costs"]
        adjudication_wall = [
            t["reference"]["evaluation_wall_s"]
            for t in arm_trials
            if t["reference"] and isinstance(t["reference"].get("evaluation_wall_s"), int | float)
        ]
        per_correct: dict[str, dict] = {}
        per_declared: dict[str, dict] = {}
        for name, item in costs.items():
            partial = bool(item["missing_trials"] or item.get("unreported_trials"))
            for target, denominator, label in (
                (per_correct, c, "no confirmed correct claim"),
                (per_declared, d, "no declared acceptance"),
            ):
                if denominator == 0:
                    target[name] = {"value": None, "unit": item["unit"], "missing": label}
                elif item["known_trials"] == 0:
                    target[name] = {
                        "value": None,
                        "unit": item["unit"],
                        "missing": "not measured in any trial",
                    }
                else:
                    target[name] = {
                        "value": round(item["known_total"] / denominator, 9),
                        "unit": item["unit"],
                        **(
                            {"note": "known part only; some trials did not report this component"}
                            if partial
                            else {}
                        ),
                    }
        categories = []
        for category, components, note in COST_CATEGORIES:
            present = [name for name in components if name in costs]
            known = [name for name in present if costs[name]["known_trials"] > 0]
            if category == "adjudication" and not known and adjudication_wall:
                categories.append(
                    {
                        "category": category,
                        "status": "reported_by_decisions",
                        "components": ["decision.evaluation_wall_s"],
                        "known_total": round(sum(adjudication_wall), 6),
                        "unit": "s",
                        "trials": len(adjudication_wall),
                        "note": note,
                    }
                )
                continue
            categories.append(
                {
                    "category": category,
                    "status": "reported"
                    if known
                    else "declared_unknown"
                    if present
                    else "not_reported",
                    "components": present,
                    "note": note,
                }
            )
        resource = None
        resource_scope = None
        if "own_trial_wall" in costs and costs["own_trial_wall"]["known_trials"]:
            resource = costs["own_trial_wall"]["known_total"]
            resource_scope = "own_trial_wall (sum of disjoint phase walls; simulator wall nested)"
        elif all(
            name in costs and costs[name]["known_trials"]
            for name in ("diagnostic_wall", "confirmation_wall")
        ):
            resource = round(
                costs["diagnostic_wall"]["known_total"] + costs["confirmation_wall"]["known_total"],
                9,
            )
            resource_scope = "diagnostic_wall + confirmation_wall (disjoint phases)"
        report["arms"][arm_id] = {
            "kind": arm["kind"],
            "validity_layer": arm["validity_layer"],
            "selection": arm["selection"],
            "assigned_cases": n,
            "declared_acceptances": d,
            "confirmed_correct": c,
            "contradicted": f,
            "unsupported": u,
            "unknown": k,
            "claim_categories": counts,
            "contradiction_codes": contradiction_codes,
            "non_acceptance_states": states,
            "refusals": refusals,
            "product_accepted": sum(1 for t in arm_trials if t["product_accepted"]),
            "product_blocked_acceptances": sum(
                1 for t in arm_trials if t["eligibility"]["product"] == "ineligible"
            ),
            "study_eligible_trials": sum(1 for t in arm_trials if t["eligibility"]["study"]),
            "usable_as_study_result": None,
            "v1_confirmed": v1_arm["outcomes"]["confirmed"],
            "v1_false_acceptances": v1_arm["false_acceptances"],
            "declaration_origins": sorted(origins),
            "prospective_trials": prospective_trials,
            "rates": {
                "D_over_N": _rate(d, n),
                "C_over_N": _rate(c, n),
                "F_over_N": _rate(f, n),
                "F_over_D": _rate(f, d),
                "U_over_D": _rate(u, d),
                "K_over_D": _rate(k, d),
                "reference_coverage_of_claims": _rate(c + f, d),
                "F_over_C_supplementary": _rate(f, c),
                "contradicted_upper_bound_if_unadjudicated_wrong": _rate(f + u + k, n),
                "F_over_N_exact_95": clopper_pearson(f, n),
                "C_over_N_exact_95": clopper_pearson(c, n),
                "correct_refusals_over_non_acceptances": _rate(refusals[CORRECT_REFUSAL], n - d),
                "missed_over_non_acceptances": _rate(refusals[MISSED], n - d),
            },
            "costs": {
                "components": costs,
                "categories": categories,
                "per_correct_claim": per_correct,
                "per_declared_acceptance": per_declared,
                "cumulative_resource_time_s": resource,
                "cumulative_resource_time_scope": resource_scope,
                "cumulative_simulator_wall_s": v1_arm["cumulative_simulator_wall_s"],
                "diagnostic_elapsed_wall_s": v1_arm["diagnostic_elapsed_wall_s"],
                "full_elapsed_wall_s": v1_arm["elapsed_wall_s"],
                "full_elapsed_wall_scope": v1_arm["elapsed_wall_scope"],
                "retries": v1_arm["retries"],
                "rollouts": v1_arm["rollouts"],
            },
        }
    origins_all = {t["declaration"]["origin"] for t in trials.values() if t["declaration"]}
    prospective_all = sum(1 for t in trials.values() if t["prospective"])
    report["declarations"] = {
        "origins": sorted(origins_all),
        "prospective_trials": prospective_all,
        "trials": len(trials),
        "reading": _reading(trials, prospective_all),
    }
    report["trials"] = [trials[key] for key in sorted(trials)]
    preparation = ledger.get("preparation_cost_ledger") if isinstance(ledger, dict) else None
    if isinstance(preparation, dict) and _reference(preparation):
        problem = _verify_record(_reference(preparation), records_root)
        report["shared_preparation_ledger"] = {
            "path": preparation.get("path"),
            "bound": problem is None,
            "how": problem or "bytes verified under the root; shared across arms, not amortized",
        }
    report["costs_by_scope"] = _costs_by_scope(ledger, records_root, report, trials, started)
    report["fair"] = v1["fair"] and not any(f["code"] in BLOCKING for f in findings)
    blocking = sorted(
        {f["code"] for f in findings if f["code"] in BLOCKING or f["code"] in SCORING_BLOCKING}
    )
    for arm in report["arms"].values():
        arm["usable_as_study_result"] = report["fair"]
    report["eligibility"] = {
        "usable_as_study_result": report["fair"],
        "blocking_findings": blocking,
        "statement": (
            "no blocking finding; arm totals are usable study results under the stated "
            "reading and limits"
            if report["fair"]
            else "blocking findings present: arm totals are descriptive only and are not a "
            "usable study result; per-trial product eligibility is stated separately and "
            "never rewrites a verified reference outcome"
        ),
    }
    return report


def _costs_by_scope(
    ledger: object, records_root: Path | None, report: dict, trials: dict, started: float
) -> dict:
    """Known totals and unknown categories by scope, each counted once.

    Historical trial costs are the arms' per-component totals (phase walls with the
    simulator wall nested, never added). Shared preparation is one suite-level ledger,
    read from its bound bytes, not amortized and not added to any arm. New processing is
    the packet's outer wall with per-row terminal reads and writer attempts listed as
    nested components. The scoring wall is this run's own cost, charged to the evaluation
    lane. Unknown categories stay unknown.
    """
    built = ledger.get("built_from_packet") if isinstance(ledger, dict) else None
    scopes: dict = {
        "historical_trials": {
            "per_arm": {
                arm_id: {
                    name: {
                        "known_total": item["known_total"] if item["known_trials"] else None,
                        "unit": item["unit"],
                        "known_trials": item["known_trials"],
                        "missing_trials": item["missing_trials"],
                    }
                    for name, item in arm["costs"]["components"].items()
                }
                for arm_id, arm in report["arms"].items()
            },
            "scope": "phase walls of the assigned trials, failures included; the simulator wall "
            "is nested in the phase walls and own_trial_wall is their disjoint sum",
        },
        "historical_shared_preparation": None,
        "new_processing": None,
        "evaluation_scoring": {
            "scoring_wall_s": round(time.perf_counter() - started, 6),
            "scope": "this scoring run, an evaluation-lane cost; not charged to any arm or to "
            "the historical intervention",
        },
        "unknown": [],
        "rule": "scopes are reported side by side and never summed; nested walls are listed, "
        "not added; unknown categories are not zero",
    }
    unknown: list[dict] = []
    preparation = (
        _reference(ledger.get("preparation_cost_ledger")) if isinstance(ledger, dict) else None
    )
    if preparation is not None:
        record, problem = _load_bound(preparation, records_root)
        entry: dict = {"path": preparation["path"], "bound": problem is None}
        if record is not None:
            entry.update(
                {
                    "schema": record.get("schema"),
                    "known_command_wall_sum_s": record.get("known_command_wall_sum_s"),
                    "summed_commands": len(record.get("summed_command_ids") or []),
                    "nested_not_added": len(record.get("nested_not_added") or []),
                    "unmeasured_commands": len(record.get("unmeasured_command_ids") or []),
                    "amortization": record.get("amortization"),
                    "scope": record.get("scope"),
                }
            )
            for item in record.get("unmeasured") or []:
                if isinstance(item, dict):
                    unknown.append(
                        {
                            "scope": "historical_shared_preparation",
                            "category": item.get("category"),
                            "unit": item.get("unit"),
                            "reason": item.get("reason"),
                        }
                    )
        else:
            entry["how"] = problem
        entry["note"] = "one suite-level ledger shared by both arms; not amortized and not added "
        "to per-arm totals"
        scopes["historical_shared_preparation"] = entry
    if built:
        per_arm: dict = {}
        for (arm_id, _case), t in trials.items():
            row = t.get("packet_row") or {}
            arm = per_arm.setdefault(
                arm_id,
                {
                    "terminal_read_wall_s": 0.0,
                    "terminal_reads": 0,
                    "writer_attempt_wall_s": 0.0,
                    "writer_attempts_known": 0,
                    "writer_attempts_unknown_cost": 0,
                    "writer_attempts_incomplete": 0,
                },
            )
            wall = row.get("new_terminal_processing_wall_s")
            if isinstance(wall, int | float):
                arm["terminal_read_wall_s"] = round(arm["terminal_read_wall_s"] + wall, 9)
                arm["terminal_reads"] += 1
            for attempt in row.get("attempts") or []:
                cost = attempt.get("cost_wall_s")
                if isinstance(cost, int | float) and cost >= 0:
                    arm["writer_attempt_wall_s"] = round(arm["writer_attempt_wall_s"] + cost, 9)
                    arm["writer_attempts_known"] += 1
                else:
                    arm["writer_attempts_unknown_cost"] += 1
                if attempt.get("status") not in ("completed", "identical_retry"):
                    arm["writer_attempts_incomplete"] += 1
        scopes["new_processing"] = {
            "packet_processing_wall_s": built.get("processing_wall_s"),
            "packet_processing_scope": built.get("processing_cost_scope"),
            "per_arm_nested": per_arm,
            "new_model_calls": built.get("new_model_calls"),
            "new_simulator_executions": built.get("new_simulator_executions"),
            "note": "terminal reads and writer attempts are nested in the packet's outer wall "
            "and may overlap; they are listed, not added to it or to the historical trials",
        }
        for name, item in (built.get("missing_costs") or {}).items():
            if isinstance(item, dict):
                unknown.append(
                    {
                        "scope": "new_processing",
                        "category": name,
                        "unit": item.get("unit"),
                        "reason": item.get("reason"),
                    }
                )
    for arm_id, arm in report["arms"].items():
        for name, item in arm["costs"]["components"].items():
            if item["known_trials"] == 0 and item["missing_trials"]:
                unknown.append(
                    {
                        "scope": "historical_trials",
                        "arm": arm_id,
                        "category": name,
                        "unit": item["unit"],
                        "reason": "declared unknown in every trial",
                    }
                )
    scopes["unknown"] = unknown
    return scopes


def _reading(trials: dict, prospective_all: int) -> str:
    declared = [t["declaration"] for t in trials.values() if t["declaration"]]
    if not declared:
        return "no_declarations"
    if prospective_all == len(trials):
        return "prospective"
    origins = {d["origin"] for d in declared}
    scopes = {d.get("evidence_scope") for d in declared}
    if origins <= {"derived_from_v1_arm_claimed_acceptance"}:
        return "retrospective"
    if origins == {"receipt"} and scopes <= {DEMONSTRATION_SCOPE}:
        return "development_demonstration"
    return "mixed"


PACKET_SCHEMA = "nisayon.retained-declaration-packet.v1"


def packet_ledger(packet_dir: Path) -> dict:
    """A ``nisayon.comparison.v2`` ledger built from an execution-lane declaration packet.

    The packet copies the source ledger under ``sources/`` and binds it in ``freeze.json``;
    the suite, cases and arms come from that verified copy. Each row's historical trial is
    taken as the packet retained it, with the row's declaration, terminal-start and
    terminal-result references (packet-relative). Historical record paths stay relative to
    the original suite, so the caller scores with ``historical_root`` set to that suite.
    """
    packet_dir = Path(packet_dir)
    packet = load_json(packet_dir / "packet.json")
    if not isinstance(packet, dict) or packet.get("schema") != PACKET_SCHEMA:
        raise Malformed("packet.schema", f"expected {PACKET_SCHEMA}")
    freeze_ref = _reference(packet.get("freeze"))
    if freeze_ref is None or _verify_record(freeze_ref, packet_dir) is not None:
        raise Malformed("packet.freeze", "the freeze record does not verify under the packet")
    freeze = load_json(packet_dir / freeze_ref["path"])
    if not isinstance(freeze, dict):
        raise Malformed("freeze", "not an object")
    source_ref = _reference(freeze.get("source_ledger"))
    if source_ref is None or _verify_record(source_ref, packet_dir) is not None:
        raise Malformed("freeze.source_ledger", "the source ledger copy does not verify")
    source = load_json(packet_dir / source_ref["path"])
    if not isinstance(source, dict) or source.get("schema") != LEDGER_SCHEMA:
        raise Malformed("freeze.source_ledger", f"expected a {LEDGER_SCHEMA} ledger")
    assigned = {
        (item.get("case_id"), item.get("arm"))
        for item in (freeze.get("assigned") or [])
        if isinstance(item, dict)
    }
    ledger = {
        "schema": LEDGER_SCHEMA_V2,
        "evidence_origin": packet.get("evidence_scope"),
        "built_from_packet": {
            "packet": str(packet_dir),
            "freeze": freeze_ref,
            "source_ledger": source_ref,
            "source_locator": freeze.get("source_locator"),
            "historical_preparation_cost_ledger": packet.get("historical_preparation_cost_ledger"),
            "scientific_claim": packet.get("scientific_claim"),
            "reference_limit": packet.get("reference_limit"),
            "new_model_calls": packet.get("new_model_calls"),
            "new_simulator_executions": packet.get("new_simulator_executions"),
            "processing_wall_s": packet.get("processing_wall_s"),
            "processing_cost_scope": packet.get("processing_cost_scope"),
            "missing_costs": packet.get("missing_costs"),
        },
        "suite": {
            **source["suite"],
            "declaration_suite_id": freeze.get("id"),
            "declaration_frozen_at": freeze.get("frozen_at"),
        },
        "cases": source["cases"],
        "arms": source["arms"],
        "trials": [],
        "execution_complete": source.get("execution_complete"),
        "preparation_cost_ledger": source.get("preparation_cost_ledger"),
    }
    seen: set[tuple] = set()
    for index, row in enumerate(packet.get("rows") or []):
        rpath = f"packet.rows[{index}]"
        if not isinstance(row, dict):
            raise Malformed(rpath, "not an object")
        key = (row.get("case_id"), row.get("arm"))
        if assigned and key not in assigned:
            raise Malformed(rpath, f"{key} is not an assignment of the freeze")
        if key in seen:
            raise Malformed(rpath, f"{key} appears twice")
        seen.add(key)
        trial = row.get("historical_trial")
        if not isinstance(trial, dict):
            raise Malformed(f"{rpath}.historical_trial", "missing")
        trial = dict(trial)
        if trial.get("case_id") != key[0] or trial.get("arm") != key[1]:
            raise Malformed(f"{rpath}.historical_trial", "names another case or arm than the row")
        for name in ("declaration", "terminal_start", "terminal_result"):
            reference = _reference(row.get(name))
            if reference is not None:
                trial[name] = reference
        recovery = row.get("recovery") if isinstance(row.get("recovery"), dict) else {}
        trial["packet_row"] = {
            "retained_decision": row.get("retained_decision"),
            "new_terminal_processing_wall_s": row.get("new_terminal_processing_wall_s"),
            "recovery_state": recovery.get("state"),
            "attempts": [
                {
                    "operation": a.get("operation"),
                    "status": a.get("status"),
                    "cost_wall_s": a.get("cost_wall_s"),
                    "lock_wait_wall_s": a.get("lock_wait_wall_s"),
                }
                for a in (recovery.get("attempts") or [])
                if isinstance(a, dict)
            ],
        }
        ledger["trials"].append(trial)
    missing = sorted(assigned - seen)
    if missing:
        ledger["execution_complete"] = False
        ledger["packet_missing_rows"] = [{"case_id": c, "arm": a} for c, a in missing]
    return ledger


def score_prospective_packet(packet_dir: Path, historical_root: Path | None = None) -> dict:
    """Score an execution-lane declaration packet against the original suite's records."""
    packet_dir = Path(packet_dir)
    ledger = packet_ledger(packet_dir)
    if historical_root is None:
        locator = ledger["built_from_packet"].get("source_locator")
        if isinstance(locator, str) and Path(locator).is_dir():
            historical_root = Path(locator)
        else:
            raise Malformed(
                "historical_root",
                "the packet's source locator is not a local directory; pass --historical-root",
            )
    report = score_prospective(ledger, packet_dir, historical_root)
    report["packet"] = {
        **ledger["built_from_packet"],
        "historical_root": str(historical_root),
        "missing_rows": ledger.get("packet_missing_rows", []),
    }
    return report


def score_prospective_file(
    path: Path, root: Path | None = None, historical_root: Path | None = None
) -> dict:
    """Score a ledger file, or a packet directory / ``packet.json``."""
    path = Path(path)
    if path.is_dir() or path.name == "packet.json":
        return score_prospective_packet(path if path.is_dir() else path.parent, historical_root)
    return score_prospective(
        load_json(path), path.parent if root is None else root, historical_root
    )


def _fmt(value: object) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, tuple | list) and len(value) == 2:
        return f"[{value[0]:.3f}, {value[1]:.3f}]"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_prospective(report: dict) -> str:
    suite = (report.get("suite") or {}).get("id")
    reading = (report.get("declarations") or {}).get("reading")
    lines = [
        f"Prospective decision-quality report: {'fair' if report['fair'] else 'NOT FAIR'}"
        + (f" · suite {suite}" if suite else "")
        + (f" · declarations {reading}" if reading else "")
        + (f" · ledger {report['ledger_schema']}" if report.get("ledger_schema") else "")
    ]
    eligibility = report.get("eligibility") or {}
    if eligibility:
        lines.append(
            "Eligibility: "
            + (
                "usable study result (no blocking finding)"
                if eligibility.get("usable_as_study_result")
                else "NOT a usable study result; blocking: "
                + ", ".join(eligibility.get("blocking_findings") or [])
                + ". Arm totals are descriptive only; product eligibility is per trial below "
                "and never rewrites a verified reference outcome."
            )
        )
    if report["findings"]:
        lines.append("Findings:")
        for finding in report["findings"]:
            lines.append(f"  - {finding['code']}: {finding['detail']}")
    if report["arms"]:
        lines.append(
            "Arms (N assigned · D declared acceptances = C confirmed correct + F contradicted + U unsupported + K unknown):"
        )
        lines.append(
            f"  {'arm':<5}{'N':<4}{'D':<4}{'C':<4}{'F':<4}{'U':<4}{'K':<4}"
            f"{'abstain':<9}{'refuse':<8}{'unres':<7}{'inval':<7}{'unsup':<7}{'tout':<6}{'n/a':<5}"
            f"{'dmg':<5}{'correct-ref':<13}{'missed':<8}{'unadj':<7}{'product':<9}{'blocked':<9}"
            f"{'prospective':<12}v1 conf/false"
        )
        for arm_id, arm in report["arms"].items():
            s, r = arm["non_acceptance_states"], arm["refusals"]
            lines.append(
                f"  {arm_id:<5}{arm['assigned_cases']:<4}{arm['declared_acceptances']:<4}"
                f"{arm['confirmed_correct']:<4}{arm['contradicted']:<4}{arm['unsupported']:<4}"
                f"{arm['unknown']:<4}{s['abstain']:<9}{s['refuse']:<8}{s['unresolved']:<7}"
                f"{s['invalid_experiment']:<7}{s['unsupported_capability']:<7}{s['timeout']:<6}"
                f"{s['not_attempted'] + s['no_declaration']:<5}{s['declaration_unusable']:<5}"
                f"{r[CORRECT_REFUSAL]:<13}"
                f"{r[MISSED]:<8}{r[UNADJUDICATED]:<7}{arm['product_accepted']:<9}"
                f"{arm['product_blocked_acceptances']:<9}"
                f"{arm['prospective_trials']}/{arm['assigned_cases']:<10}"
                f"{arm['v1_confirmed']}/{arm['v1_false_acceptances']}"
            )
        lines.append(
            "Rates (undefined where the denominator is zero; intervals are exact binomial, exchangeability assumed):"
        )
        for arm_id, arm in report["arms"].items():
            rates = arm["rates"]
            lines.append(
                f"  {arm_id}: D/N {_fmt(rates['D_over_N'])} · C/N {_fmt(rates['C_over_N'])} "
                f"{_fmt(rates['C_over_N_exact_95'])} · F/N {_fmt(rates['F_over_N'])} "
                f"{_fmt(rates['F_over_N_exact_95'])} · F/D {_fmt(rates['F_over_D'])} · "
                f"coverage (C+F)/D {_fmt(rates['reference_coverage_of_claims'])} · "
                f"upper bound if unadjudicated wrong {_fmt(rates['contradicted_upper_bound_if_unadjudicated_wrong'])} · "
                f"F/C (supplementary) {_fmt(rates['F_over_C_supplementary'])}"
            )
            if arm["contradiction_codes"]:
                lines.append(f"     contradiction codes: {arm['contradiction_codes']}")
        lines.append(
            "Costs (known totals over every assigned trial; per correct claim; unknown stays unknown):"
        )
        for arm_id, arm in report["arms"].items():
            costs = arm["costs"]
            lines.append(
                f"  {arm_id}: cumulative resource {_fmt(costs['cumulative_resource_time_s'])} s "
                f"({costs['cumulative_resource_time_scope'] or 'not reported'}) · simulator nested "
                f"{_fmt(costs['cumulative_simulator_wall_s'])} s · full elapsed "
                f"{_fmt(costs['full_elapsed_wall_s'])} s · rollouts {costs['rollouts']} · retries {costs['retries']}"
            )
            for name, item in costs["per_correct_claim"].items():
                value = (
                    item["value"]
                    if item["value"] is not None
                    else f"undefined ({item.get('missing')})"
                )
                lines.append(
                    f"     per correct {name}: {value} {item['unit']}"
                    + (f" ({item['note']})" if item.get("note") else "")
                )
            unknown = [c["category"] for c in costs["categories"] if c["status"] != "reported"]
            lines.append(f"     categories not reported or unknown: {', '.join(unknown) or 'none'}")
    scopes = report.get("costs_by_scope") or {}
    if scopes:
        lines.append("Costs by scope (never summed across scopes; nested walls listed, not added):")
        shared = scopes.get("historical_shared_preparation")
        if shared:
            lines.append(
                f"  shared preparation: {_fmt(shared.get('known_command_wall_sum_s'))} s recorded "
                f"command wall over {shared.get('summed_commands')} commands "
                f"({shared.get('nested_not_added')} nested not added, "
                f"{shared.get('unmeasured_commands')} unmeasured); bound {shared.get('bound')}; "
                "shared by both arms, not amortized"
            )
        new = scopes.get("new_processing")
        if new:
            lines.append(
                f"  new processing: packet outer wall {_fmt(new.get('packet_processing_wall_s'))} s; "
                + "; ".join(
                    f"{arm}: terminal reads {v['terminal_read_wall_s']} s over {v['terminal_reads']}, "
                    f"writer attempts {v['writer_attempt_wall_s']} s over {v['writer_attempts_known']} "
                    f"(unknown cost {v['writer_attempts_unknown_cost']}, incomplete "
                    f"{v['writer_attempts_incomplete']})"
                    for arm, v in new.get("per_arm_nested", {}).items()
                )
                + f"; model calls {new.get('new_model_calls')}, simulator executions "
                f"{new.get('new_simulator_executions')}"
            )
        scoring = scopes.get("evaluation_scoring") or {}
        lines.append(
            f"  evaluation scoring: {_fmt(scoring.get('scoring_wall_s'))} s (this run; evaluation lane)"
        )
        unknown = scopes.get("unknown") or []
        if unknown:
            lines.append(
                "  unknown: "
                + "; ".join(
                    f"{u.get('scope')}{'/' + u['arm'] if u.get('arm') else ''}: {u.get('category')}"
                    for u in unknown
                )
            )
    if report["trials"]:
        lines.append("Cases (declaration → reference):")
        for entry in report["trials"]:
            declaration = entry["declaration"] or {}
            reference = entry["reference"] or {}
            outcome = entry["claim_category"] or entry["non_acceptance_state"]
            refusal = entry["refusal"]["adjudication"] if entry["refusal"] else ""
            marks = []
            if entry["prospective"]:
                marks.append("prospective")
            elig = entry.get("eligibility") or {}
            if elig and not elig.get("study"):
                marks.append("study-ineligible[" + ",".join(elig.get("study_blockers") or []) + "]")
            if elig.get("product") == "ineligible":
                marks.append(
                    "product-ineligible[" + ",".join(elig.get("product_blockers") or []) + "]"
                )
            lines.append(
                f"  {entry['arm']:<3}{entry['case_id']:<28}{str(declaration.get('disposition')):<17}"
                f"→ {str(reference.get('decision')):<11}{outcome:<40}{refusal}"
                + ("  " + " ".join(marks) if marks else "")
            )
    lines.append("Limits:")
    for limit in report["limits"]:
        lines.append(f"  - {limit}")
    return "\n".join(lines)


__all__ = [
    "BLOCKING",
    "CLAIM",
    "CLAIM_CATEGORIES",
    "DECLARATION_SCHEMA",
    "LEDGER_SCHEMA",
    "LEDGER_SCHEMA_V2",
    "NON_ACCEPTANCE_STATES",
    "REPORT_SCHEMA",
    "clopper_pearson",
    "render_prospective",
    "score_prospective",
    "score_prospective_file",
]
