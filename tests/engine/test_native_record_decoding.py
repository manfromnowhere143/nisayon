"""Constructed evidence-boundary controls; no policy or simulator execution."""

import gzip
import json

import pytest

from nisayon.engine import store
from nisayon.engine.io import digest, file_digest, write_json


@pytest.fixture
def packet(tmp_path):
    identity = {
        "code": {"source_changes": []},
        "dependencies": {},
        "policy_sha256": "constructed-policy",
        "environment": {},
        "translated_policy_sha256": "constructed-policy",
    }
    configuration = {
        "deployment": {},
        "environment": {},
        "translated_policy_sha256": "constructed-policy",
    }
    assignment = {"run_id": "control", "mode": "reference", "seed": 0, "role": "software_control"}
    capture = {"step": 0, "components": {"constructed": {"simulation_s": 0.0}}}
    next_capture = {"step": 1, "components": {"constructed": {"simulation_s": 0.05}}}
    reset = {"constructed": True}
    raw = {
        "step": 0,
        "observation": {"constructed": [0]},
        "next_observation": {"constructed": [1]},
        "state_before": {"sim_time_s": 0.0},
        "state_after": {"sim_time_s": 0.05},
        "policy_state_before": {"hidden": None, "counter": 0},
        "intended_action": [0.0],
        "executed_action": [0.0],
        "observation_capture": capture,
        "next_observation_capture": next_capture,
    }
    trace_path = tmp_path / "control.jsonl.gz"
    lines = [json.dumps({"reset": reset}), json.dumps(raw)]
    trace_path.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0))
    run = {
        "id": "control",
        "plan_id": "reference",
        "seed": 0,
        "evidence_origin": "synthetic_development",
        "assignment_role": assignment["role"],
        "started_at": "2026-01-01T00:00:02+00:00",
        "invocation_id": "constructed",
        "execution_identity_sha256": digest(identity),
        "code_sha256": digest(identity["code"]),
        "dependencies_sha256": digest(identity["dependencies"]),
        "policy_sha256": identity["policy_sha256"],
        "configuration": configuration,
        "configuration_sha256": digest(configuration),
        "candidate_sha256": digest(configuration["deployment"]),
        "source_identity_unchanged": True,
        "process_status": "completed",
        "task_outcome": "failed",
        "initial_state_sha256": digest(reset),
        "trace": [
            {
                **{
                    key: raw[key]
                    for key in (
                        "step",
                        "intended_action",
                        "executed_action",
                        "observation_capture",
                        "next_observation_capture",
                    )
                },
                **{
                    key + "_sha256": digest(raw[key])
                    for key in (
                        "observation",
                        "next_observation",
                        "state_before",
                        "state_after",
                    )
                },
                "policy_state_sha256": digest(raw["policy_state_before"]),
                "observation_step": 0,
                "observation_sim_time_s": 0.0,
                "action_sim_time_s": 0.0,
                "next_sim_time_s": 0.05,
            }
        ],
        "artifacts": [{"path": trace_path.name, "sha256": file_digest(trace_path)}],
    }
    case = {"id": "constructed-record-boundary", "predicates": {}}
    frozen = {
        "frozen_at": "2026-01-01T00:00:00+00:00",
        "code": identity["code"],
        "case_sha256": digest(case),
        "predicates": case["predicates"],
        "assignments": [assignment],
        "execution_identity_sha256": digest(identity),
    }
    write_json(tmp_path / "frozen-protocol.json", frozen)
    write_json(tmp_path / "control.run.json", run)
    write_json(
        tmp_path / "invocation.json",
        {
            "id": "constructed",
            "execution_identity": identity,
            "execution_identity_sha256": digest(identity),
        },
    )
    write_json(tmp_path / "preparation-costs.json", {"costs": []})
    write_json(
        tmp_path / "attempts/control.json",
        {
            "assignment": assignment,
            "configuration": configuration,
            "configuration_sha256": digest(configuration),
            "invocation_id": "constructed",
            "declared_at": "2026-01-01T00:00:01+00:00",
        },
    )
    bundle = {
        "record_contract": "nisayon.execution.v2",
        "attempt_contract": "nisayon.execution.attempt.v1",
        "invocation": {"path": "invocation.json"},
        "preparation_cost_ledger": {"path": "preparation-costs.json"},
        "code": identity["code"],
        "case": case,
        "assignments": [assignment],
        "runs": [run],
        "confirmation": {"protocol_sha256": digest(frozen), "contamination": []},
    }
    rebind(tmp_path, bundle)
    return tmp_path, bundle


def rebind(root, bundle):
    """Rehash deliberately edited software fixtures, never retained experiments."""
    for ref in [bundle["invocation"], bundle["preparation_cost_ledger"]]:
        ref["sha256"] = file_digest(root / ref["path"])
    trace = bundle["runs"][0]["artifacts"][0]
    observed = file_digest(root / trace["path"])
    if observed != trace["sha256"]:
        trace["sha256"] = observed
        (root / "control.run.json").write_text(json.dumps(bundle["runs"][0]))
    members = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "manifest.json")
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "nisayon.artifact_manifest.v1",
                "files": {str(p.relative_to(root)): file_digest(p) for p in members},
                "file_sizes": {str(p.relative_to(root)): p.stat().st_size for p in members},
            }
        )
    )
    bundle["artifact_manifest"] = {"path": manifest.name, "sha256": file_digest(manifest)}


def test_intact_packet_verifies_without_claiming_scientific_acceptance(packet):
    root, bundle = packet
    result = store.verify_execution(bundle, root)
    assert result["status"] == "verified" and result["trace_rows"] == 1
    assert result["scientific_acceptance"] == "not_decided_by_integrity_checks"
    assert bundle["runs"][0]["task_outcome"] == "failed"


@pytest.mark.parametrize(
    "name,key,line",
    [
        ("invocation.json", "id", None),
        ("frozen-protocol.json", "frozen_at", None),
        ("attempts/control.json", "invocation_id", None),
        ("control.run.json", "task_outcome", None),
        ("control.jsonl.gz", "reset", 0),
        ("control.jsonl.gz", "executed_action", 1),
    ],
)
def test_conflicting_record_keys_fail_even_when_all_file_hashes_match(packet, name, key, line):
    root, bundle = packet
    path = root / name
    if line is None:
        text = path.read_text()
    else:
        lines = gzip.decompress(path.read_bytes()).decode().splitlines()
        text = lines[line]
    text = text.replace(f'"{key}":', f'"{key}": "contradictory", "{key}":', 1)
    if line is None:
        path.write_text(text)
    else:
        lines[line] = text
        path.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0))
    rebind(root, bundle)
    with pytest.raises(ValueError, match="[Dd]uplicate JSON"):
        store.verify_execution(bundle, root)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_metadata_cannot_hide_in_a_verified_invocation(packet, number):
    root, bundle = packet
    path = root / "invocation.json"
    path.write_text(path.read_text().replace("{", '{"additional_measurement": ' + number + ",", 1))
    rebind(root, bundle)
    with pytest.raises(ValueError, match="[Nn]on-finite"):
        store.verify_execution(bundle, root)


@pytest.mark.parametrize(
    "name",
    [
        "invocation.json",
        "frozen-protocol.json",
        "attempts/control.json",
        "control.run.json",
        "control.jsonl.gz",
    ],
)
def test_decoded_bytes_must_match_the_manifest_after_initial_scan(packet, monkeypatch, name):
    root, bundle = packet
    original_verify = store.verify_manifest

    def replace_after_scan(*args):
        members = original_verify(*args)
        path = root / name
        if name.endswith(".gz"):
            raw = gzip.decompress(path.read_bytes()).replace(b"{", b"{ ", 1)
            path.write_bytes(gzip.compress(raw, mtime=0))
        else:
            path.write_bytes(b" " + path.read_bytes())
        return members

    monkeypatch.setattr(store, "verify_manifest", replace_after_scan)
    with pytest.raises(ValueError, match="[Bb]ytes mismatch"):
        store.verify_execution(bundle, root)
