"""A candidate that changes the controller-target convention must be visible as a component.

The execution lane's Lift deployment record can now declare ``controller_target``
(``restored`` or ``nominal``); an omitted field keeps the original restored-state
convention. The evaluator reads the repair a candidate carries from the fields where it
differs from the changed deployment and checks each against the declared repair scope. A
field the evaluator does not know cannot fail that check, so a candidate could carry a
convention change past a scope that allows the gripper sign only. These bundles follow
the mini document's strict shape with ``configuration.deployment`` on every run.
"""

from __future__ import annotations

import copy
import json

from test_evaluation_first_case import CODE, POLICY, PREDICATES, mini_document, stamp

from nisayon.evaluation import evaluate_bundle
from nisayon.evaluation.first_case import (
    deployment,
    producer_digest,
    read_document,
    translate,
    write_document,
)


def with_deployments(document: dict, candidate: dict, *, scope: list[str] | None = None) -> dict:
    """Every run carries its deployment; candidate runs carry ``candidate`` consistently."""
    document = copy.deepcopy(document)
    digest = producer_digest(candidate)
    for run in document["runs"]:
        dep = candidate if run["plan_id"] == "correction" else deployment(run["plan_id"], POLICY)
        run["configuration"] = {"deployment": dep}
        run["candidate_sha256"] = producer_digest(dep)
    document["confirmation"]["candidate_sha256"] = digest
    if scope is not None:
        document["case"]["allowed_repair_scope"] = scope
    return document


def write_with_protocol(document: dict, candidate: dict, folder):
    folder.mkdir(parents=True, exist_ok=True)
    protocol = {
        "schema": "nisayon.lift.protocol.v2",
        "candidate": candidate,
        "predicates": PREDICATES,
        "condition_ids": document["confirmation"]["condition_ids"],
        "frozen_at": stamp(10),
        "code": CODE,
    }
    document["confirmation"]["protocol_sha256"] = producer_digest(protocol)
    path = write_document(document, folder / "bundle.json")
    (folder / "frozen-protocol.json").write_text(json.dumps(protocol))
    (folder / "manifest.json").write_text(
        json.dumps({"schema": "nisayon.execution.artifacts.v1", "files": [], "premise": "test"})
    )
    return path


def correction_entry(decision: dict) -> dict:
    return next(e for e in decision["candidates"].values() if e["id"] == "correction")


def component_paths(path) -> list[str]:
    """The component paths the translation records for the exploration candidate run."""
    bundle, _, _ = translate(read_document(path), path)
    return [c["path"] for c in bundle.runs["correction-0"]["candidate"]["components"]]


def deployment_label(path) -> str:
    bundle, _, _ = translate(read_document(path), path)
    return bundle.runs["correction-0"]["candidate"]["deployment"]


def test_gripper_repair_with_smuggled_target_change_is_outside_the_declared_scope(tmp_path):
    candidate = {**deployment("correction", POLICY), "controller_target": "nominal"}
    document = with_deployments(mini_document(), candidate)
    path = write_with_protocol(document, candidate, tmp_path)
    assert component_paths(path) == ["repair_gripper_sign", "controller_target"]
    decision = evaluate_bundle(path)
    entry = correction_entry(decision)
    assert "candidate_outside_repair_scope" in {f["code"] for f in entry["obligation_failures"]}
    assert entry["status"] == "rejected"
    assert decision["decision"] != "accepted"


def test_explicit_restored_target_equals_the_omitted_legacy_convention(tmp_path):
    candidate = {**deployment("correction", POLICY), "controller_target": "restored"}
    document = with_deployments(mini_document(), candidate)
    path = write_with_protocol(document, candidate, tmp_path)
    assert component_paths(path) == ["repair_gripper_sign"]
    decision = evaluate_bundle(path)
    entry = correction_entry(decision)
    assert entry["status"] == "accepted", entry["obligation_failures"]
    assert decision["decision"] == "accepted"


def test_declared_target_scope_admits_a_target_only_candidate(tmp_path):
    """A candidate that differs from the changed deployment only in the target convention
    carries exactly that component; a scope that names it admits the candidate."""
    candidate = {**deployment("regression", POLICY), "mode": "correction"}
    candidate["controller_target"] = "nominal"
    document = with_deployments(mini_document(), candidate, scope=["controller_target"])
    path = write_with_protocol(document, candidate, tmp_path)
    assert component_paths(path) == ["controller_target"]
    assert deployment_label(path) == "transport_gripper_sign=-1, controller_target=nominal"
    decision = evaluate_bundle(path)
    entry = correction_entry(decision)
    assert "candidate_outside_repair_scope" not in {f["code"] for f in entry["obligation_failures"]}
    assert entry["status"] == "accepted", entry["obligation_failures"]


def test_target_only_candidate_is_outside_a_gripper_scope(tmp_path):
    candidate = {**deployment("regression", POLICY), "mode": "correction"}
    candidate["controller_target"] = "nominal"
    document = with_deployments(mini_document(), candidate)
    path = write_with_protocol(document, candidate, tmp_path)
    assert component_paths(path) == ["controller_target"]
    decision = evaluate_bundle(path)
    entry = correction_entry(decision)
    assert "candidate_outside_repair_scope" in {f["code"] for f in entry["obligation_failures"]}
    assert entry["status"] == "rejected"
