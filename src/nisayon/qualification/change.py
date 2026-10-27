"""Compose scoped investigation reuse with separately executed confirmation.

This is a fixed two-stage software workflow, not a task adapter, adaptive search,
independent adjudicator or deployment authority. Stage bundles keep their existing
format so the instrument can inspect them without a new execution backend.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from nisayon.engine.io import canonical_bytes, decode_json, digest, file_digest, write_json

from .bundle import export_run, inspect_bundle
from .conditions import condition_ids, reserve_conditions
from .context import ExecutionContext, project_file
from .models import CaseSpec, ExperimentPlan, fields
from .reuse import _reuse_report
from .runner import plan_change, run_plan

STAGES = ("investigation", "confirmation")
RULE = "valid_investigation_and_confirmation_adopt_v1"
MAX_RECORD_BYTES = 4 * 1024 * 1024


def _same_claim(investigation: CaseSpec, confirmation: CaseSpec) -> dict:
    values = [case.record() for case in (investigation, confirmation)]
    claims = [{k: v for k, v in item.items() if k not in {"id", "probes"}} for item in values]
    if canonical_bytes(claims[0]) != canonical_bytes(claims[1]):
        raise ValueError("Confirmation must preserve the investigation claim and criterion")
    conditions = dict(zip(STAGES, map(condition_ids, (investigation, confirmation)), strict=True))
    if set(conditions["investigation"]) & set(conditions["confirmation"]):
        raise ValueError("Confirmation overlaps investigation conditions")
    return conditions


def _plans(value: dict) -> dict[str, ExperimentPlan]:
    plans = {stage: ExperimentPlan.from_dict(value[stage]) for stage in STAGES}
    left, right = [plans[stage].record() for stage in STAGES]
    for key in ("sources", "tool", "read_policy"):
        if left.get(key) != right.get(key):
            raise ValueError("Stages do not share frozen source and execution identities")
    contexts = [
        {k: v for k, v in item["context"].items() if k != "output_dir"} for item in (left, right)
    ]
    if contexts[0] != contexts[1]:
        raise ValueError("Stages do not share a frozen runtime and resource contract")
    return plans


def _read_record(root: Path, name: str, expected: str | None = None) -> dict:
    path = project_file(root, name)
    with path.open("rb") as stream:
        data = stream.read(MAX_RECORD_BYTES + 1)
    if len(data) > MAX_RECORD_BYTES:
        raise ValueError("Change record exceeds its supported bound")
    if expected is not None and hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Change record identity mismatch")
    value = decode_json(data)
    if not isinstance(value, dict):
        raise ValueError("Change record must be an object")
    return value


def _reference(root: Path, name: str) -> dict:
    return {"path": name, "sha256": file_digest(project_file(root, name))}


def _bundle(root: Path, reference: object) -> dict:
    reference = fields(reference, {"path", "sha256"})
    # inspect_bundle consumes and hashes the same bounded archive bytes.
    result = inspect_bundle(project_file(root, reference["path"]), include_plan=True)
    if result["bundle_sha256"] != reference["sha256"]:
        raise ValueError("Stage bundle identity mismatch")
    return result


def _decision(protocol: dict, reviews: dict, errors: dict) -> dict:
    obligations = [f"{stage}:{message}" for stage, message in errors.items()]
    outcomes = {}
    for stage in STAGES:
        review = reviews.get(stage)
        if review is None:
            outcomes[stage] = "not_executed"
            continue
        assessment = review["assessment"]
        valid = (
            review["review_status"] == "verified" and assessment["execution_validity"] == "valid"
        )
        outcomes[stage] = review["software_decision"] if valid else "unresolved"
        obligations += [f"{stage}:{item}" for item in assessment["obligations"]]
        if not valid:
            obligations.append(f"{stage}:invalid_or_unresolved_stage")
    first, second = [outcomes[stage] for stage in STAGES]
    if errors or first in {"not_executed", "unresolved"}:
        decision = "unresolved"
    elif first == "reject":
        decision = "reject"
    elif second in {"adopt", "reject"}:
        decision = second
    else:
        decision = "unresolved"
        obligations.append("confirmation:valid_confirmation_required")
    return {
        "software_decision": decision,
        "deployment_decision": "unresolved",
        "stages": outcomes,
        "investigation_action": protocol["investigation_action"],
        "obligations": sorted(set(obligations)),
        "independent_adjudication": "not_observed",
        "confirmation_scope": "Distinct declared inputs reserved in an explicit local store; external exposure, independence and population generalization remain unestablished.",
    }


def inspect_change(directory: str | Path) -> dict:
    """Recompute a composed decision from portable records without owner execution.

    The directory can be copied to another machine. Integrity is not authenticity:
    a coordinated rewrite of protocol and records is not prevented by hashes.
    """
    root = Path(directory).resolve(strict=True)
    receipt = fields(
        _read_record(root, "receipt.json"),
        {"schema", "protocol", "reservations", "bundles", "errors", "decision", "costs"},
    )
    if receipt["schema"] != "nisayon.qualification.change_receipt.v1":
        raise ValueError("Unsupported change receipt schema")
    reference = fields(receipt["protocol"], {"path", "sha256"})
    protocol = fields(
        _read_record(root, reference["path"], reference["sha256"]),
        {
            "schema",
            "plans",
            "conditions",
            "prior",
            "previous_conditions",
            "investigation_action",
            "rule",
        },
    )
    if protocol["schema"] != "nisayon.qualification.change_protocol.v1" or protocol["rule"] != RULE:
        raise ValueError("Unsupported change protocol or decision rule")
    plans = _plans(fields(protocol["plans"], set(STAGES)))
    cases = [CaseSpec.from_dict(plans[stage].record()["case"]) for stage in STAGES]
    conditions = _same_claim(*cases)
    if conditions != protocol["conditions"]:
        raise ValueError("Condition identities do not match the frozen cases")
    reservations = fields(receipt["reservations"], {"path", "sha256"})
    reserved = fields(
        _read_record(root, reservations["path"], reservations["sha256"]),
        {"schema", "records", "scope"},
    )
    if reserved["schema"] != "nisayon.qualification.reservations.v1":
        raise ValueError("Unsupported reservation schema")
    if set(reserved["records"]) != set(
        sum(conditions.values(), []) + protocol["previous_conditions"]
    ):
        raise ValueError("Incomplete condition reservation coverage")
    for key in conditions["confirmation"]:
        record = reserved["records"][key]
        if (
            record.get("condition_sha256") != key
            or record.get("purpose") != "confirmation"
            or record.get("first_protocol_sha256") != digest(protocol)
        ):
            raise ValueError("Confirmation was not reserved for this protocol")
    reuse = None
    previous = None
    action = "run"
    if protocol["prior"] is not None:
        previous = _bundle(root, protocol["prior"])
        previous_conditions = condition_ids(CaseSpec.from_dict(previous["plan"]["case"]))
        if previous_conditions != protocol["previous_conditions"]:
            raise ValueError("Previous condition identities do not match retained evidence")
        if set(previous_conditions) & set(conditions["confirmation"]):
            raise ValueError("Confirmation overlaps previously assigned conditions")
        reuse = _reuse_report(
            ExperimentPlan.from_dict(previous["plan"]),
            previous["assessment"],
            plans["investigation"],
        )
        if (
            previous["review_status"] == "verified"
            and reuse["verdict_applicability"] == "applicable_same_scoped_claim"
        ):
            action = "reuse"
    elif protocol["previous_conditions"]:
        raise ValueError("Previous conditions require their retained evidence")
    if protocol["investigation_action"] != action:
        raise ValueError("Investigation selection disagrees with rechecked applicability")
    bundles = fields(receipt["bundles"], set(STAGES))
    errors = fields(receipt["errors"], set(), set(STAGES))
    if any(not isinstance(value, str) or len(value) > 1000 for value in errors.values()):
        raise ValueError("Invalid stage failure record")
    reviews = {}
    for stage in STAGES:
        if bundles[stage] is None:
            continue
        review = _bundle(root, bundles[stage])
        expected = (
            previous["plan_sha256"]
            if stage == "investigation" and action == "reuse"
            else plans[stage].sha256
        )
        if review["plan_sha256"] != expected:
            raise ValueError("Stage evidence belongs to a different frozen plan")
        if stage == "investigation" and action == "reuse" and bundles[stage] != protocol["prior"]:
            raise ValueError("Reused investigation is not the rechecked prior bundle")
        reviews[stage] = review
    decision = _decision(protocol, reviews, errors)
    agrees = canonical_bytes(decision) == canonical_bytes(receipt["decision"])
    attempt_counts = {
        stage: len(review["assessment"]["attempts"]) for stage, review in reviews.items()
    }
    observed_new = sum(
        count
        for stage, count in attempt_counts.items()
        if stage != "investigation" or action == "run"
    )
    unknown_execution = bool(errors) or any(
        review["assessment"]["costs"] is None for review in reviews.values()
    )
    return {
        "schema": "nisayon.qualification.change_review.v1",
        **decision,
        "software_decision": decision["software_decision"] if agrees else "unresolved",
        "review_status": "verified" if agrees else "decision_mismatch",
        "protocol_sha256": digest(protocol),
        "recomputed_decision": decision,
        "reuse": reuse,
        "stage_reviews": {
            stage: {
                "plan_sha256": review["plan_sha256"],
                "bundle_sha256": review["bundle_sha256"],
                "review_status": review["review_status"],
                "software_decision": review["software_decision"],
                "execution_validity": review["assessment"]["execution_validity"],
                "costs": review["assessment"]["costs"],
            }
            for stage, review in reviews.items()
        },
        "new_native_attempts": None if unknown_execution else observed_new,
        "observed_new_native_attempts": observed_new,
        "reused_native_attempts": attempt_counts.get("investigation", 0)
        if action == "reuse"
        else 0,
        "costs": receipt["costs"],
        "limit": "Read-only consistency and software reassessment. No owner code executed, independent outcome adjudication or deployment authorization.",
    }


def qualify_change(
    investigation: CaseSpec,
    confirmation: CaseSpec,
    *,
    project: Path,
    output: Path,
    condition_store: Path,
    previous: Path | None = None,
    python: Path | None = None,
    timeout_seconds: float = 10,
    total_seconds: float = 120,
) -> dict:
    """Freeze both stages, reuse eligible evidence, then execute confirmation once.

    ``total_seconds`` bounds each native stage, not the entire workflow. Partial
    outputs and consumed conditions survive failure. The condition store is an
    explicit local ledger; it cannot discover undeclared external exposure.
    """
    started = time.perf_counter()
    destination = output.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    if project.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Output must not replace or contain the owner project")
    if condition_store.resolve().is_relative_to(destination.resolve()):
        raise ValueError("Share the condition store outside the per-invocation output")
    conditions = _same_claim(investigation, confirmation)
    contexts = {
        stage: ExecutionContext.from_project(
            project,
            output_dir=destination / stage,
            python=python,
            timeout_seconds=timeout_seconds,
            total_seconds=total_seconds,
        )
        for stage in STAGES
    }
    plans = {
        stage: plan_change(case, context=contexts[stage])
        for stage, case in zip(STAGES, (investigation, confirmation), strict=True)
    }
    plan_values = {stage: plan.record() for stage, plan in plans.items()}
    _plans(plan_values)
    destination.mkdir(parents=True, exist_ok=False)
    prior, prior_review, action = None, None, "run"
    previous_conditions = []
    if previous is not None:
        export_run(previous, destination / "previous.nisayon.zip")
        prior = _reference(destination, "previous.nisayon.zip")
        prior_review = _bundle(destination, prior)
        previous_conditions = condition_ids(CaseSpec.from_dict(prior_review["plan"]["case"]))
        if set(previous_conditions) & set(conditions["confirmation"]):
            raise ValueError("Confirmation overlaps previously assigned conditions")
        reuse = _reuse_report(
            ExperimentPlan.from_dict(prior_review["plan"]),
            prior_review["assessment"],
            plans["investigation"],
        )
        if (
            prior_review["review_status"] == "verified"
            and reuse["verdict_applicability"] == "applicable_same_scoped_claim"
        ):
            action = "reuse"
    protocol = {
        "schema": "nisayon.qualification.change_protocol.v1",
        "plans": plan_values,
        "conditions": conditions,
        "prior": prior,
        "previous_conditions": previous_conditions,
        "investigation_action": action,
        "rule": RULE,
    }
    if len(canonical_bytes(protocol)) > MAX_RECORD_BYTES:
        raise ValueError("Change protocol exceeds its supported bound")
    write_json(destination / "protocol.json", protocol)
    if _read_record(destination, "protocol.json") != protocol:
        raise ValueError("Frozen protocol readback differs")
    reservations = reserve_conditions(
        condition_store,
        investigation=sorted(set(conditions["investigation"] + previous_conditions)),
        confirmation=conditions["confirmation"],
        protocol_sha256=digest(protocol),
    )
    write_json(destination / "reservations.json", reservations)
    bundles, reviews, errors = dict.fromkeys(STAGES), {}, {}
    for stage in STAGES:
        if stage == "confirmation":
            first = _decision(protocol, reviews, errors)
            if first["stages"]["investigation"] != "adopt" or errors:
                break
        if stage == "investigation" and action == "reuse":
            bundles[stage], reviews[stage] = prior, prior_review
            continue
        try:
            run_plan(plans[stage], context=contexts[stage])
            export_run(contexts[stage].output_dir, destination / f"{stage}.nisayon.zip")
            bundles[stage] = _reference(destination, f"{stage}.nisayon.zip")
            reviews[stage] = _bundle(destination, bundles[stage])
        except (OSError, ValueError) as error:
            errors[stage] = f"{type(error).__name__}: {error}"[:1000]
            write_json(destination / f"{stage}-error.json", {"error": errors[stage]})
            break
    decision = _decision(protocol, reviews, errors)
    costs = {
        "workflow_wall_seconds": time.perf_counter() - started,
        "native_stage_budget_seconds": total_seconds,
        "maximum_native_stages": 2,
        "human_active_seconds": None,
        "setup_seconds": None,
        "compute_cost": None,
        "complete_cost": "unknown",
        "boundary": "Preflight through stage reviews, excluding final receipt serialization and readback. Stage and attempt times are nested; reused execution costs are historical, not new savings measurements.",
    }
    receipt = {
        "schema": "nisayon.qualification.change_receipt.v1",
        "protocol": _reference(destination, "protocol.json"),
        "reservations": _reference(destination, "reservations.json"),
        "bundles": bundles,
        "errors": errors,
        "decision": decision,
        "costs": costs,
    }
    write_json(destination / "receipt.json", receipt)
    result = inspect_change(destination)
    write_json(destination / "result.json", result)
    return result
