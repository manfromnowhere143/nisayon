"""Build the matched conventional and Nisayon processor observation records.

The conventional arm is an ordinary deterministic diagnostic over the same retained
bytes and remedies. It shares the reviewed upstream mixin extractor with the producer,
but it does not call the producer's assignment or decision functions and does not build
an evidence store. The Nisayon arm is exported read-only from a sealed producer store.
Both records target the separately committed evaluation interface.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from nisayon.engine.declarations import _write_once
from nisayon.engine.io import digest, file_digest
from nisayon.engine.processor_case import (
    _bind_suffix,
    _processor,
    _read,
    _run_feature,
    extract_mixin,
    inspect_store,
    resolve_inputs,
    validate_case,
)
from nisayon.engine.store import resolve_member

SCHEMA = "nisayon.processor-observation.v1"
CASE_SCHEMA = "nisayon.external-processor-case.v1"
EVALUATION_INTERFACE_COMMIT = "2c8226676982edbcd3e7cb4a0575f65e126056d5"
CANDIDATE_NAMES = {
    "C0": "as_is",
    "C1": "suffix_match",
    "C2": "explicit_override",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _implementation_identity(repo: Path) -> dict:
    if _git(repo, "status", "--porcelain"):
        raise ValueError("Commit current changes before recording a conventional observation")
    members = [
        "scripts/experiments/processor_observations.py",
        "src/nisayon/engine/processor_case.py",
        "uv.lock",
    ]
    return {
        "commit": _git(repo, "rev-parse", "HEAD"),
        "files": {member: file_digest(repo / member) for member in members},
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
    }


def _input_reference(path: Path, relative_to: Path) -> dict:
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "sha256": file_digest(path),
        "bytes": path.stat().st_size,
    }


def _input_references(inputs: dict, root: Path) -> dict:
    return {
        "preprocessor_config": _input_reference(inputs["sources"]["preprocessor-config"], root),
        "postprocessor_config": _input_reference(inputs["sources"]["postprocessor-config"], root),
        "preprocessor_stats": _input_reference(inputs["sources"]["preprocessor-state"], root),
        "postprocessor_stats": _input_reference(inputs["sources"]["postprocessor-state"], root),
        "processor_source": _input_reference(inputs["sources"]["normalize-source"], root),
    }


def _execution(
    case: dict,
    inputs: dict,
    mixin: type,
    *,
    execution_id: str,
    candidate: str,
    processor_name: str,
    feature: str,
    feature_type: str,
    direction: str,
    witness: list[float],
    order: list[str] | None = None,
    provenance: str = "artifact",
) -> dict:
    item = inputs["processors"][processor_name]
    explicit = case["candidates"][2]["stats"] if candidate == "explicit_override" else None
    processor = _processor(
        mixin,
        item["step"]["config"],
        item["state"],
        explicit_stats=explicit,
        order=order,
    )
    selected = feature if feature in processor._tensor_stats else None
    matches = [key for key in processor._tensor_stats if key.endswith("." + feature)]
    if candidate == "suffix_match":
        selected, matches = _bind_suffix(processor, feature)
    observed = _run_feature(
        processor,
        feature=feature,
        feature_type=feature_type,
        inverse=direction == "inverse",
        values=witness,
    )
    row = {
        "id": execution_id,
        "candidate": candidate,
        "processor": processor_name,
        "feature": feature,
        "direction": direction,
        "status": observed["status"],
        "input": observed["input"],
        "output": observed["output"],
        "error": observed["error"],
        "stats_provenance": provenance,
        "stats_order": order,
        "observed_bound_key": selected,
        "observed_matches": matches,
        "nested_cost": observed["cost"],
    }
    if candidate == "explicit_override":
        row["override_stats"] = explicit
    return row


def conventional(case_path: Path, source_root: Path, repo: Path) -> dict:
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    case = _read(case_path)
    if case.get("schema") != CASE_SCHEMA:
        raise ValueError("Conventional workflow requires the frozen processor case")
    validate_case(case)
    inputs = resolve_inputs(case, source_root)
    mixin, extraction = extract_mixin(inputs["sources"]["normalize-source"])
    visual = next(
        key
        for key, value in inputs["processors"]["preprocessor"]["step"]["config"]["features"].items()
        if value["type"] == "VISUAL"
    )
    executions = [
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C0-state",
            candidate="as_is",
            processor_name="preprocessor",
            feature="observation.state",
            feature_type="STATE",
            direction="forward",
            witness=case["witnesses"]["state"],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C0-action",
            candidate="as_is",
            processor_name="postprocessor",
            feature="action",
            feature_type="ACTION",
            direction="inverse",
            witness=case["witnesses"]["action"],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C0-identity",
            candidate="as_is",
            processor_name="preprocessor",
            feature=visual,
            feature_type="VISUAL",
            direction="forward",
            witness=case["witnesses"]["visual"],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C1-state",
            candidate="suffix_match",
            processor_name="preprocessor",
            feature="observation.state",
            feature_type="STATE",
            direction="forward",
            witness=case["witnesses"]["state"],
            order=case["suffix_orders"][0],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C1-action-original-order",
            candidate="suffix_match",
            processor_name="postprocessor",
            feature="action",
            feature_type="ACTION",
            direction="inverse",
            witness=case["witnesses"]["action"],
            order=case["suffix_orders"][0],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C1-action-reordered",
            candidate="suffix_match",
            processor_name="postprocessor",
            feature="action",
            feature_type="ACTION",
            direction="inverse",
            witness=case["witnesses"]["action"],
            order=case["suffix_orders"][1],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C2-state",
            candidate="explicit_override",
            processor_name="preprocessor",
            feature="observation.state",
            feature_type="STATE",
            direction="forward",
            witness=case["witnesses"]["state"],
            provenance="reporter_transcription",
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C2-action",
            candidate="explicit_override",
            processor_name="postprocessor",
            feature="action",
            feature_type="ACTION",
            direction="inverse",
            witness=case["witnesses"]["action"],
        ),
        _execution(
            case,
            inputs,
            mixin,
            execution_id="A-C2-identity",
            candidate="explicit_override",
            processor_name="preprocessor",
            feature=visual,
            feature_type="VISUAL",
            direction="forward",
            witness=case["witnesses"]["visual"],
        ),
    ]
    return {
        "schema": SCHEMA,
        "arm": "A",
        "evaluation_interface_commit": EVALUATION_INTERFACE_COMMIT,
        "incident": case["incident"],
        "case_sha256": digest(case),
        "inputs": _input_references(inputs, source_root.resolve(strict=True)),
        "executions": executions,
        "decision": {
            "candidates": {
                "as_is": {
                    "outcome": "rejected_candidate",
                    "reason": "State and action obligations are skipped.",
                },
                "suffix_match": {
                    "outcome": "rejected_candidate",
                    "reason": "State is still skipped and the action binding changes with store order.",
                },
                "explicit_override": {
                    "outcome": "supported_software_correction",
                    "reason": "The named override transforms state and action and preserves IDENTITY; deployment applicability remains unresolved.",
                },
            },
            "deployment_applicability": "unresolved",
            "robot_task_outcome": "unmeasured",
        },
        "resolved_premises": inputs["premises"],
        "call_path": inputs["call_path"],
        "extraction": extraction,
        "implementation": _implementation_identity(repo),
        "costs": {
            "command_wall_seconds_before_write": time.perf_counter() - started_wall,
            "command_process_cpu_seconds_before_write": time.process_time() - started_cpu,
            "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
            "nested_execution_costs": "Retained per execution; do not add to the command cost.",
            "engineering_effort": None,
            "provider_charges": None,
            "energy": None,
            "network_overhead": None,
        },
        "limits": {
            "full_upstream_pipeline_executed": False,
            "policy_or_model_executed": False,
            "robot_task_observed": False,
            "regression_store_retained": False,
            "shared_upstream_executor": True,
        },
        "recorded_at": _now(),
    }


def export_nisayon(store: Path) -> dict:
    inspection = inspect_store(store)
    if inspection["integrity"] != "verified_complete_store":
        raise ValueError(f"Nisayon result is not a verified complete store: {inspection['errors']}")
    root = store.resolve(strict=True)
    case = _read(resolve_member(root, "inputs/frozen-case.json"))
    index = _read(resolve_member(root, "inputs/source-index.json"))
    sources = {row["id"]: row for row in index["sources"]}
    summary = _read(resolve_member(root, "summary.json"))
    wanted = [
        name
        for name in case["assignments"]
        if name.startswith(("incident-C0", "incident-C1", "incident-C2"))
    ]
    executions = []
    for name in wanted:
        raw = _read(resolve_member(root, f"executions/{name}.json"))
        candidate_code = name.split("-")[1]
        observation = raw["observation"]
        row = {
            "id": name,
            "candidate": CANDIDATE_NAMES[candidate_code],
            "processor": raw["processor"],
            "feature": raw["feature"],
            "direction": raw["direction"],
            "status": observation["status"],
            "input": observation["input"],
            "output": observation["output"],
            "error": observation["error"],
            "stats_provenance": (
                "reporter_transcription" if name == "incident-C2-state" else "artifact"
            ),
            "stats_order": (
                case["suffix_orders"][1]
                if name.endswith("-reordered")
                else case["suffix_orders"][0]
                if candidate_code == "C1"
                else None
            ),
            "observed_bound_key": raw["statistics_key"],
            "observed_matches": raw["statistics_matches"],
            "nested_cost": raw["assignment_cost"],
        }
        if candidate_code == "C2":
            row["override_stats"] = case["candidates"][2]["stats"]
        executions.append(row)
    producer = {
        {
            "C0_as_is": "as_is",
            "C1_suffix_match": "suffix_match",
            "C2_explicit_override": "explicit_override",
        }[row["candidate"]]: {
            "outcome": row["outcome"],
            "reasons": row["reasons"],
        }
        for row in summary["decisions"]["candidates"]
        if row["candidate"] != "C3_remigration"
    }

    def reference(source_id: str) -> dict:
        row = sources[source_id]
        return {"path": row["member"], "sha256": row["sha256"], "bytes": row["bytes"]}

    return {
        "schema": SCHEMA,
        "arm": "B",
        "evaluation_interface_commit": EVALUATION_INTERFACE_COMMIT,
        "incident": case["incident"],
        "case_sha256": digest(case),
        "inputs": {
            "preprocessor_config": reference("preprocessor-config"),
            "postprocessor_config": reference("postprocessor-config"),
            "preprocessor_stats": reference("preprocessor-state"),
            "postprocessor_stats": reference("postprocessor-state"),
            "processor_source": reference("normalize-source"),
        },
        "executions": executions,
        "decision": {
            "candidates": producer,
            "overall": summary["decisions"]["software_decision"],
            "deployment_applicability": summary["decisions"]["deployment_decision"],
            "robot_task_outcome": summary["decisions"]["robot_task_outcome"],
        },
        "resolved_premises": summary["resolved_configuration"]["premises"],
        "call_path": summary["resolved_configuration"]["call_path"],
        "extraction": summary["source_extraction"],
        "implementation": summary["invocation"]["source_identity"],
        "costs": summary["costs"],
        "limits": summary["limits"] | {"regression_store_retained": True},
        "raw_store": {
            "summary_sha256": file_digest(root / "summary.json"),
            "manifest_sha256": file_digest(root / "artifact-manifest.json"),
            "seal_sha256": file_digest(root / "seal.json"),
            "inspection_integrity": inspection["integrity"],
            "inspection_execution_performed": inspection["execution_performed"],
            "inspection_retry_performed": inspection["retry_performed"],
        },
        "recorded_at": _now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    conventional_parser = commands.add_parser("conventional")
    conventional_parser.add_argument("--case", type=Path, required=True)
    conventional_parser.add_argument("--sources", type=Path, required=True)
    conventional_parser.add_argument("--out", type=Path, required=True)
    export = commands.add_parser("export-nisayon")
    export.add_argument("--store", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    result = (
        conventional(args.case, args.sources, repo)
        if args.command == "conventional"
        else export_nisayon(args.store)
    )
    _write_once(args.out, result)
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "arm": result["arm"],
                "executions": len(result["executions"]),
                "output": str(args.out),
                "sha256": file_digest(args.out),
                "robot_task_observed": False,
                "scientific_acceptance": "not_granted",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
