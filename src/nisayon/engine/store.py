"""Portable, content-bound execution stores with strict relative paths."""

from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path, PurePosixPath

from .io import digest, file_digest, write_json
from .telemetry import MISSING_REASON, policy_digest
from .telemetry import configuration as telemetry_configuration


def resolve_member(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError(f"Invalid artifact path: {name!r}")
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or str(relative) != name:
        raise ValueError(f"Artifact path is not canonical and relative: {name!r}")
    if name == ".":
        raise ValueError("Artifact must be a file")
    root = root.resolve(strict=True)
    path = root.joinpath(*relative.parts)
    for ancestor in [path, *path.parents]:
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise ValueError(f"Artifact symlinks are not supported: {name!r}")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"Artifact escapes store or is not a file: {name!r}")
    return resolved


def create_manifest(root: Path, names: list[str], *, name: str = "artifact-manifest.json") -> dict:
    if len(names) != len(set(names)) or name in names:
        raise ValueError("Manifest cannot contain duplicate entries or itself")
    members = []
    for member in sorted(names):
        path = resolve_member(root, member)
        members.append({"path": member, "sha256": file_digest(path), "bytes": path.stat().st_size})
    document = {
        "schema": "nisayon.artifact_manifest.v1",
        "files": {member["path"]: member["sha256"] for member in members},
        "file_sizes": {member["path"]: member["bytes"] for member in members},
        "premise": "Hashes verify the identified bytes; they do not attest simulator truth.",
    }
    write_json(root / name, document)
    return {"path": name, "sha256": file_digest(root / name)}


def verify_manifest(root: Path, reference: dict) -> dict[str, dict]:
    manifest = resolve_member(root, reference["path"])
    if file_digest(manifest) != reference["sha256"]:
        raise ValueError("Artifact manifest digest mismatch")

    def no_duplicate_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Duplicate JSON manifest key: {key}")
            value[key] = item
        return value

    document = json.loads(manifest.read_text(), object_pairs_hook=no_duplicate_keys)
    if document.get("schema") == "nisayon.execution.artifacts.v1":
        # Previously frozen producer shape is retained and still verified.
        entries = document["files"]
    elif document.get("schema") == "nisayon.artifact_manifest.v1":
        entries = [
            {"path": name, "sha256": sha, "bytes": document.get("file_sizes", {}).get(name)}
            for name, sha in document["files"].items()
        ]
    else:
        raise ValueError("Unsupported artifact manifest schema")
    members = {}
    for member in entries:
        name = member["path"]
        if name in members or name == reference["path"]:
            raise ValueError("Duplicate or self-referential artifact manifest entry")
        path = resolve_member(root, name)
        if (member["bytes"] is not None and path.stat().st_size != member["bytes"]) or file_digest(
            path
        ) != member["sha256"]:
            raise ValueError(f"Artifact bytes mismatch: {name}")
        members[name] = member
    return members


def _require_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise ValueError(f"Execution identity or evidence mismatch: {label}")


def verify_execution(bundle: dict, root: Path) -> dict:
    """Check producer evidence before scientific evaluation; no acceptance decision."""
    if bundle.get("record_contract") != "nisayon.execution.v2":
        raise ValueError("Strict verification requires the v2 execution contract")
    members = verify_manifest(root, bundle["artifact_manifest"])
    invocation_ref = bundle["invocation"]
    _require_equal(
        members[invocation_ref["path"]]["sha256"], invocation_ref["sha256"], "invocation bytes"
    )
    invocation = json.loads(resolve_member(root, invocation_ref["path"]).read_text())
    identity = invocation["execution_identity"]
    identity_hash = digest(identity)
    _require_equal(identity_hash, invocation["execution_identity_sha256"], "invocation identity")
    _require_equal(identity["code"], bundle["code"], "bundle code")
    costs = bundle["preparation_cost_ledger"]
    _require_equal(members[costs["path"]]["sha256"], costs["sha256"], "preparation cost ledger")
    for history in bundle.get("history", []):
        _require_equal(
            members[history["path"]]["sha256"], history["sha256"], "retained history bytes"
        )
    confirmation = bundle.get("confirmation")
    if confirmation is not None:
        frozen = json.loads(resolve_member(root, "frozen-protocol.json").read_text())
        if "frozen-protocol.json" not in members:
            raise ValueError("Frozen protocol absent from artifact manifest")
        _require_equal(digest(frozen), confirmation["protocol_sha256"], "frozen protocol")
        _require_equal(frozen["code"], identity["code"], "frozen code")
        _require_equal(identity["code"]["source_changes"], [], "committed scored source")
        _require_equal(frozen["case_sha256"], digest(bundle["case"]), "frozen case")
        _require_equal(frozen["predicates"], bundle["case"]["predicates"], "frozen predicates")
        _require_equal(frozen["assignments"], bundle["assignments"], "frozen assignments")
        _require_equal(frozen.get("history", []), bundle.get("history", []), "frozen history")
        _require_equal(
            frozen["execution_identity_sha256"], identity_hash, "frozen execution identity"
        )
        _require_equal(confirmation["contamination"], [], "confirmation contamination")
    assignments = {a["run_id"]: a for a in bundle["assignments"]}
    if len(assignments) != len(bundle["assignments"]):
        raise ValueError("Duplicate run assignment")
    ids = set()
    by_id = {r["id"]: r for r in bundle["runs"]}
    trace_rows = 0
    measurement_gaps = []
    for run in bundle["runs"]:
        run_id = run["id"]
        if run_id in ids:
            raise ValueError(f"Duplicate simulator run: {run_id}")
        ids.add(run_id)
        assignment = assignments[run_id]
        _require_equal(run["plan_id"], assignment["mode"], f"{run_id} assigned mode")
        _require_equal(run["seed"], assignment["seed"], f"{run_id} assigned seed")
        if "candidate_sha256" in assignment:
            _require_equal(
                run["candidate_sha256"],
                assignment["candidate_sha256"],
                f"{run_id} assigned candidate",
            )
        if confirmation is not None:
            if datetime.fromisoformat(run["started_at"]) <= datetime.fromisoformat(
                frozen["frozen_at"]
            ):
                raise ValueError(f"Scored run did not start after freeze: {run_id}")
            _require_equal(run["assignment_role"], assignment["role"], f"{run_id} assigned role")
            if "configuration_sha256_by_candidate" in frozen:
                _require_equal(
                    run["configuration_sha256"],
                    frozen["configuration_sha256_by_candidate"][run["candidate_sha256"]],
                    f"{run_id} frozen deployment configuration",
                )
            if "configuration_sha256_by_run_id" in frozen:
                _require_equal(
                    run["configuration_sha256"],
                    frozen["configuration_sha256_by_run_id"][run_id],
                    f"{run_id} frozen run configuration",
                )
        _require_equal(run["invocation_id"], invocation["id"], f"{run_id} invocation")
        _require_equal(run["execution_identity_sha256"], identity_hash, f"{run_id} identity")
        _require_equal(run["code_sha256"], digest(identity["code"]), f"{run_id} code")
        _require_equal(
            run["dependencies_sha256"], digest(identity["dependencies"]), f"{run_id} dependencies"
        )
        _require_equal(run["policy_sha256"], identity["policy_sha256"], f"{run_id} policy")
        _require_equal(
            run["configuration_sha256"], digest(run["configuration"]), f"{run_id} configuration"
        )
        if bundle.get("attempt_contract") == "nisayon.execution.attempt.v1":
            attempt_path = f"attempts/{run_id}.json"
            if attempt_path not in members:
                raise ValueError(f"Missing pre-execution attempt record: {run_id}")
            attempt = json.loads(resolve_member(root, attempt_path).read_text())
            _require_equal(attempt["assignment"], assignment, f"{run_id} attempt assignment")
            _require_equal(
                attempt["configuration"], run["configuration"], f"{run_id} attempt configuration"
            )
            _require_equal(
                attempt["configuration_sha256"],
                run["configuration_sha256"],
                f"{run_id} attempt configuration digest",
            )
            _require_equal(
                attempt["invocation_id"], run["invocation_id"], f"{run_id} attempt invocation"
            )
            if datetime.fromisoformat(attempt["declared_at"]) >= datetime.fromisoformat(
                run["started_at"]
            ):
                raise ValueError(f"Attempt record did not precede execution: {run_id}")
        telemetry = run["configuration"].get("telemetry", telemetry_configuration("full"))
        profile = telemetry["profile"]
        _require_equal(telemetry, telemetry_configuration(profile), f"{run_id} telemetry contract")
        if profile == "policy_state_unavailable":
            _require_equal(run["policy_state_reset"]["status"], "unknown", f"{run_id} reset gap")
            _require_equal(
                run["policy_state_reset"].get("missing_reason"),
                MISSING_REASON,
                f"{run_id} reset missingness reason",
            )
            measurement_gaps.append(
                {"run_id": run_id, "field": "policy_state", "reason": MISSING_REASON}
            )
        _require_equal(
            run["configuration"]["environment"], identity["environment"], f"{run_id} environment"
        )
        _require_equal(
            run["configuration"]["translated_policy_sha256"],
            identity["translated_policy_sha256"],
            f"{run_id} translated policy",
        )
        _require_equal(
            run["candidate_sha256"],
            digest(run["configuration"]["deployment"]),
            f"{run_id} candidate",
        )
        _require_equal(run["source_identity_unchanged"], True, f"{run_id} source stability")
        run_path = f"{run_id}.run.json"
        if run_path not in members:
            raise ValueError(f"Missing run record from manifest: {run_id}")
        _require_equal(
            json.loads(resolve_member(root, run_path).read_text()), run, f"{run_id} run record"
        )
        for artifact in run["artifacts"]:
            _require_equal(
                members[artifact["path"]]["sha256"], artifact["sha256"], f"{run_id} artifact"
            )
        raw_artifacts = [a for a in run["artifacts"] if a["path"].endswith(".jsonl.gz")]
        if run["process_status"] == "completed" and len(raw_artifacts) != 1:
            raise ValueError(f"Completed run lacks one raw trace: {run_id}")
        if not raw_artifacts:
            if run["trace"]:
                raise ValueError(f"Inline trace without raw trace: {run_id}")
            continue
        with gzip.open(resolve_member(root, raw_artifacts[0]["path"]), "rt") as stream:
            initial = json.loads(next(stream))
            _require_equal(digest(initial["reset"]), run["initial_state_sha256"], f"{run_id} reset")
            raw_rows = [json.loads(line) for line in stream]
        _require_equal(len(raw_rows), len(run["trace"]), f"{run_id} trace length")
        if "policy_reset" in run:
            reset = run["policy_reset"]
            _require_equal(reset, initial["policy_reset_event"], f"{run_id} reset event")
            _require_equal(
                policy_digest(initial["policy_reset"], profile),
                reset["after_sha256"],
                f"{run_id} reset state",
            )
            _require_equal(
                policy_digest(initial["policy_before_episode_reset"], profile),
                reset["before_sha256"],
                f"{run_id} incoming policy",
            )
            if profile == "policy_state_unavailable":
                # Null is declared missing evidence, never a digest of a cleared
                # state. Integrity can verify this omission, not the reset itself.
                _require_equal(initial["policy_reset"], None, f"{run_id} unavailable reset")
            elif reset["episode_reset_applied"]:
                _require_equal(
                    initial["policy_reset"],
                    {"hidden": None, "counter": 0},
                    f"{run_id} cleared policy",
                )
            else:
                _require_equal(reset["mode"], "carry_prefix", f"{run_id} supported carry mode")
                _require_equal(
                    reset["before_sha256"], reset["after_sha256"], f"{run_id} policy carry"
                )
            if run.get("prefix_run"):
                prefix = run["prefix_run"]
                if "run_id" in prefix:
                    _require_equal(
                        prefix["run_id"], prefix["id"], f"{run_id} prefix identity aliases"
                    )
                _require_equal(
                    members[prefix["path"]]["sha256"], prefix["sha256"], f"{run_id} prefix bytes"
                )
                previous = by_id[prefix["id"]]
                _require_equal(
                    previous["trace"][-1]["policy_state_after_sha256"],
                    reset["before_sha256"],
                    f"{run_id} executed prefix state",
                )
        captures = {}
        for row, raw in zip(run["trace"], raw_rows, strict=True):
            if profile == "policy_state_unavailable":
                _require_equal(
                    raw.get("policy_state_before_step_reset"),
                    None,
                    f"{run_id} unavailable pre-reset policy state",
                )
            for field in ["observation", "next_observation", "state_before", "state_after"]:
                _require_equal(digest(raw[field]), row[field + "_sha256"], f"{run_id} {field}")
            _require_equal(
                policy_digest(raw["policy_state_before"], profile),
                row["policy_state_sha256"],
                f"{run_id} policy state",
            )
            if "policy_state_after_sha256" in row:
                _require_equal(
                    policy_digest(raw["policy_state_after"], profile),
                    row["policy_state_after_sha256"],
                    f"{run_id} resulting policy state",
                )
            if "captured_observation_sha256" in row:
                _require_equal(
                    row["captured_observation_step"],
                    row["step"],
                    f"{run_id} current acquisition identity",
                )
                _require_equal(
                    digest(raw["captured_observation"]),
                    row["captured_observation_sha256"],
                    f"{run_id} current acquisition value",
                )
                _require_equal(
                    raw["captured_observation_capture"],
                    row["captured_observation_capture"],
                    f"{run_id} current acquisition time",
                )
                captures[row["captured_observation_step"]] = (
                    raw["captured_observation"],
                    raw["captured_observation_capture"],
                )
                _require_equal(
                    (raw["observation"], raw["observation_capture"]),
                    captures[row["observation_step"]],
                    f"{run_id} actually consumed prior acquisition",
                )
            for field in [
                "step",
                "intended_action",
                "executed_action",
                "observation_capture",
                "next_observation_capture",
            ]:
                _require_equal(raw[field], row[field], f"{run_id} {field}")
            capture = row["observation_capture"]
            _require_equal(
                capture["step"], row["observation_step"], f"{run_id} observation identity"
            )
            _require_equal(
                min(s["simulation_s"] for s in capture["components"].values()),
                row["observation_sim_time_s"],
                f"{run_id} acquisition time",
            )
            _require_equal(
                raw["state_before"]["sim_time_s"], row["action_sim_time_s"], f"{run_id} action time"
            )
            _require_equal(
                raw["state_after"]["sim_time_s"], row["next_sim_time_s"], f"{run_id} next time"
            )
            trace_rows += 1
    _require_equal(ids, set(assignments), "all assigned outcomes retained")
    return {
        "status": "verified",
        "artifact_files": len(members),
        "simulator_runs": len(ids),
        "trace_rows": trace_rows,
        "declared_measurement_gaps": measurement_gaps,
        "scientific_acceptance": "not_decided_by_integrity_checks",
    }
