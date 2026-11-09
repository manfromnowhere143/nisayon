"""Project committed software-mechanism reports, never their private model inputs.

This is a display projection of retained assessments. It executes no producer,
reference evaluator, policy, simulator, model download or deployment correction.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

TEMPORAL = "docs/experiments/results/temporal-integration-001/reconciliation-audit-002.json"
PROCESSOR = {
    "case": "docs/experiments/results/external-decision-001/frozen-case.v1.json",
    "integration": "docs/experiments/results/external-decision-001/integration-readback-001.json",
    "workflows": "docs/experiments/results/external-decision-001/workflow-readback-001.json",
    "assessment": "docs/evaluation/results/external-decision-001/assessments/arm-B-store-nisayon-b-v1.assessment.json",
}


def read_committed(engine: Path, path: str, commit: str):
    data = (engine / path).read_bytes()
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("Mechanism report exceeds admission limit")
    if data != subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=engine):
        raise ValueError("Uncommitted mechanism report: " + path)
    return json.loads(data), {
        "path": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_length": len(data),
        "engine_commit": commit,
    }


def take(value, keys):
    # An absent field remains absent; it must not silently become numeric zero.
    return {key: value[key] for key in keys if key in value}


def exact_clocks(value):
    """Transmit integer clock stamps losslessly, including beyond JS safe integers."""
    if isinstance(value, list):
        return [exact_clocks(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: exact_clocks(v) for k, v in value.items()}
    if {"clock", "unit", "value"}.issubset(value):
        result["value"] = str(value["value"]) if value["value"] is not None else None
        result["exact_integer"] = isinstance(value["value"], int) and not isinstance(
            value["value"], bool
        )
    return result


def temporal_record(audit):
    if (
        audit["schema"] != "nisayon.temporal-reconciliation-audit.v2"
        or audit["execution_performed"] is not False
        or audit["scientific_acceptance"] != "not_granted"
    ):
        raise ValueError("Unsupported temporal audit authority")
    populations = []
    for i, population in enumerate(audit["populations"]):
        rows = []
        for j, row in enumerate(population["rows"]):
            rows.append(
                {
                    **take(
                        row,
                        (
                            "identity",
                            "assignment",
                            "snapshot_sha256",
                            "trace_sha256",
                            "process_outcome",
                            "integrity",
                            "temporal_contract",
                            "assigned_contract",
                            "assigned_usefulness",
                            "robot_task_outcome",
                            "owner_assessment_equal",
                            "original_costs_unchanged",
                            "named_correction_delta",
                        ),
                    ),
                    "source_pointer": f"/populations/{i}/rows/{j}",
                }
            )
        if population["assignments"] != len(rows):
            raise ValueError("Temporal population membership disagrees")
        populations.append({"name": population["name"], "assignments": len(rows), "rows": rows})
    if sum(p["assignments"] for p in populations) != audit["owner_coverage"]["assignments"]:
        raise ValueError("Temporal coverage count disagrees")
    prefixes = []
    for i, prefix in enumerate(audit["prefixes"]):
        prefixes.append(
            {
                **take(
                    prefix,
                    (
                        "identity",
                        "snapshot_sha256",
                        "trace_sha256",
                        "process_outcome",
                        "integrity",
                        "retry_performed",
                    ),
                ),
                **take(
                    prefix["reference_assessment"],
                    (
                        "temporal_contract",
                        "assigned_contract",
                        "assigned_usefulness",
                        "robot_task_outcome",
                    ),
                ),
                "source_pointer": f"/prefixes/{i}",
            }
        )
    return exact_clocks(
        {
            "schema": "nisayon.ui-temporal-contracts.v1",
            "scope": audit["boundary"],
            "coverage": audit["owner_coverage"],
            "populations": populations,
            "pairs": audit["conventional_selected_pairs"],
            "prefixes": prefixes,
            "audit_costs": audit["current_costs"],
            "execution_connected": False,
        }
    )


def processor_record(records, sources):
    case, integration, workflows, assessment = (
        records[k] for k in ("case", "integration", "workflows", "assessment")
    )
    if (
        case["schema"] != "nisayon.external-processor-case.v1"
        or integration["schema"] != "nisayon.external-decision-integration-readback.v1"
        or assessment["schema"] != "nisayon.processor-reference.assessment.v1"
    ):
        raise ValueError("Unsupported processor report schema")
    if workflows["case"]["file_sha256"] != sources["case"]["sha256"]:
        raise ValueError("Processor workflow and frozen case disagree")
    if (
        assessment["incident"] != case["incident"]
        or assessment["adapted_from"]["case_id"] != case["id"]
    ):
        raise ValueError("Processor assessment and incident disagree")
    inputs = {entry["id"]: entry for entry in case["sources"]}
    for assessed, source_id in (
        ("preprocessor_config", "preprocessor-config"),
        ("preprocessor_stats", "preprocessor-state"),
        ("postprocessor_config", "postprocessor-config"),
        ("postprocessor_stats", "postprocessor-state"),
    ):
        observed, declared = assessment["inputs"][assessed], inputs[source_id]
        if observed["sha256"] != declared["sha256"] or observed["bytes"] != declared["bytes"]:
            raise ValueError("Processor assessment input binding disagrees")
    decisions = assessment["reference_decision"]["per_candidate"]
    for name, decision in decisions.items():
        if integration["decision"][name] != decision["outcome"]:
            raise ValueError("Integrated processor decision disagrees with its reference")
    candidates = []
    for index, candidate in enumerate(case["candidates"]):
        name = candidate["id"].split("_", 1)[1]
        decision = decisions.get(name)
        if decision is None and name != "remigration":
            raise ValueError("Candidate has no retained assessment")
        candidates.append(
            {
                "id": candidate["id"],
                "name": name,
                "description": candidate["description"],
                "decision": decision
                if decision is not None
                else {
                    "outcome": integration["decision"]["remigration"],
                    "reason": candidate["description"],
                },
                "source_pointer": f"/candidates/{index}",
            }
        )
    # Statistics arrays, safetensors and model configuration contents are not
    # redistributed. These are classifications of constructed witnesses only.
    executions = [
        {
            **take(
                row,
                (
                    "id",
                    "candidate",
                    "processor",
                    "feature",
                    "direction",
                    "status",
                    "expected",
                    "agreement",
                    "vacuous",
                    "findings",
                    "stats_provenance",
                ),
            ),
            "source_pointer": f"/executions/{i}",
        }
        for i, row in enumerate(assessment["executions"])
    ]
    return {
        "schema": "nisayon.ui-processor-decision.v1",
        "scope": case["scope"],
        "exposure": case["exposure"],
        "incident": case["incident"],
        "candidates": candidates,
        "obligations": case["obligations"],
        "executions": executions,
        "decision": integration["decision"],
        "comparison": integration["comparison"],
        "confirmation_scope": integration["confirmation_scope"],
        "costs": {arm: value["command"] for arm, value in workflows["arms"].items()},
        "unknown_costs": case["unknown_costs"],
        "sources": sources,
        "boundary": assessment["boundary"],
        "execution_connected": False,
    }


def mechanism_reports(engine: Path, output: Path, put):
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=engine, text=True).strip()
    audit, temporal_source = read_committed(engine, TEMPORAL, commit)
    records, sources = {}, {}
    for key, path in PROCESSOR.items():
        records[key], sources[key] = read_committed(engine, path, commit)
    reports = {}
    for name, record, source in (
        ("temporal", temporal_record(audit), temporal_source),
        ("processor", processor_record(records, sources), sources["integration"]),
    ):
        reports[name] = put(
            output,
            {
                "schema": "nisayon.ui-retained-report.v1",
                "source": source,
                "scope": "Display projection of committed software assessments. No new evaluation; no robot or deployment outcome.",
                "record": record,
            },
        )
    if (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=engine, text=True).strip()
        != commit
    ):
        raise ValueError("Engine changed while projecting mechanisms")
    return reports
