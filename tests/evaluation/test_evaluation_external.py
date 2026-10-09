"""Field assessment of an external record against the obligation, and the native positive path.

The retained RoboLab inventory was built from the verified sample bytes with h5py; the
h5py path re-runs only where the source packet is present. A native record must stay
positive under the same table; inconsistent inventories are rejected with a reason.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from nisayon.evaluation.external import (
    ASSESSMENT_SCHEMA,
    INVENTORY_SCHEMA,
    assess_inventory,
    native_inventory,
    render_assessment,
)
from nisayon.evaluation.first_case import read_document
from nisayon.evaluation.schema import Malformed

REPO = Path(__file__).resolve().parents[2]
RETAINED = REPO / "docs/evaluation/results/external-record-robolab-001/inventory-002.json"
FIRST_INVENTORY = REPO / "docs/evaluation/results/external-record-robolab-001/inventory.json"
PACKET = Path(
    "/Users/danielwahnich/.codex/reports/nisayon-engine-handoff-2026-09-19-b9iisnns/source-check/robolab"
)
NATIVE = REPO / "docs/experiments/results/lift-v3/bundle.json.gz"


def _statuses(assessment: dict) -> dict:
    return {row["obligation"]: row["status"] for row in assessment["obligations"]}


def _gaps(assessment: dict) -> dict:
    return {row["obligation"]: row["gap_code"] for row in assessment["obligations"]}


@pytest.mark.skipif(not RETAINED.is_file(), reason="retained inventory absent")
def test_robolab_inventory_assessment_names_usable_measurements_and_gaps():
    inventory = json.loads(RETAINED.read_text())
    assert inventory["schema"] == INVENTORY_SCHEMA
    assessment = assess_inventory(inventory)
    assert assessment["schema"] == ASSESSMENT_SCHEMA
    assert assessment["rejected"] is False, assessment["rejections"]
    assert assessment["repair_comparison_applicable"] is False
    statuses = _statuses(assessment)
    assert statuses["task_outcome"] == "measurable_with_evaluator_predicate"
    assert statuses["constraints_action"] == "measurable"
    assert statuses["initial_state"] == "measurable"
    assert statuses["raw_trace_consistency"] == "measurable"
    assert statuses["timing_observation_age"] == "absent"
    assert statuses["observation_record"] == "absent"
    assert statuses["reset_evidence"] == "absent"
    assert statuses["identity"] == "declared_only"
    assert statuses["constraints_step_period"] == "declared_only"
    assert statuses["artifact_manifest"] == "absent"
    assert statuses["frozen_candidate_and_protocol"] == "inapplicable"
    assert statuses["fresh_conditions"] == "inapplicable"
    assert statuses["intervention_validity"] == "inapplicable"
    gaps = _gaps(assessment)
    assert gaps["timing_observation_age"] == "timing_unmeasured"
    assert gaps["reset_evidence"] == "reset_evidence_incomplete"
    assert gaps["identity"] == "identity_unbound"
    assert gaps["frozen_candidate_and_protocol"] == "confirmation_missing"
    assert gaps["task_outcome"] == "predicate_not_preregistered"
    assert assessment["declared_success"] is True
    assert "not a repair comparison" in assessment["reading"]
    measured = inventory["direct_measurements"]
    assert measured["initial_state_rows_identical"] is True
    assert measured["initial_state_leading_axis"] == [2]
    assert measured["gripper_column_values"] == [0.0, 1.0]
    text = render_assessment(assessment)
    assert text.startswith("External record assessment: assessed")
    assert "first-case-obligation-v0.2 unchanged" in text


@pytest.mark.skipif(not RETAINED.is_file(), reason="retained inventory absent")
def test_inconsistent_inventories_are_rejected_with_a_reason():
    inventory = json.loads(RETAINED.read_text())
    broken = copy.deepcopy(inventory)
    actions = next(f for f in broken["episodes"][0]["fields"] if f["path"] == "actions")
    actions["shape"] = [647, 8]
    assessment = assess_inventory(broken)
    assert assessment["rejected"] and any(
        r["code"] == "row_count_inconsistent" for r in assessment["rejections"]
    )
    differing = copy.deepcopy(inventory)
    differing["direct_measurements"]["initial_state_rows_identical"] = False
    assessment = assess_inventory(differing)
    assert _statuses(assessment)["initial_state"] == "ambiguous"
    assert any(r["code"] == "initial_state_ambiguous" for r in assessment["rejections"])
    unbound = copy.deepcopy(inventory)
    unbound["source"]["sha256"] = None
    assessment = assess_inventory(unbound)
    assert any(f["code"] == "source_unbound" for f in assessment["findings"])
    with pytest.raises(Malformed):
        assess_inventory({"schema": "something else"})
    with pytest.raises(Malformed):
        assess_inventory({"schema": INVENTORY_SCHEMA, "episodes": []})


@pytest.mark.skipif(not NATIVE.is_file(), reason="native record absent")
def test_native_record_stays_positive_under_the_same_table():
    document = read_document(NATIVE)
    inventory = native_inventory(document, path=str(NATIVE))
    assessment = assess_inventory(inventory)
    assert assessment["rejected"] is False
    assert all(row["status"] == "measurable" for row in assessment["obligations"]), _statuses(
        assessment
    )
    assert all(row["gap_code"] is None for row in assessment["obligations"])
    assert assessment["repair_comparison_applicable"] is True
    assert assessment["reading"].startswith("a valid native record")


@pytest.mark.skipif(not (PACKET / "data.hdf5").is_file(), reason="source packet absent")
def test_robolab_bytes_reproduce_the_retained_inventory():
    h5py = pytest.importorskip("h5py")
    from nisayon.evaluation.external import inspect_robolab_hdf5

    inventory = inspect_robolab_hdf5(
        PACKET / "data.hdf5", env_cfg=PACKET / "env_cfg.json", manifest=PACKET / "manifest.json"
    )
    assert inventory["source"]["sha256"] == (
        "edf09c3fa8e0773694e3d4ea2174e10f7410571f29e874e1562570470eba064a"
    )
    assert inventory["source"]["bytes"] == 393616
    assert inventory["episodes"][0]["rows"] == 648
    assert inventory["producer_declarations"]["policy"] == "pi05"
    assert inventory["producer_declarations"]["step_period_s"] == pytest.approx(1 / 15)
    assert inventory["inspection"]["tool"].startswith(f"h5py {h5py.__version__}")
    if RETAINED.is_file():
        retained = json.loads(RETAINED.read_text())
        assert inventory["episodes"] == retained["episodes"]
        assert inventory["direct_measurements"] == retained["direct_measurements"]
        assert inventory["consistency"] == retained["consistency"]
        assert inventory["producer_declarations"] == retained["producer_declarations"]


READER_COMPACT = REPO / "docs/experiments/results/robolab-record-001/summary-distinct-frames.json"
READER_FULL = Path(
    "/Users/danielwahnich/workspace/nisayon-codex/artifacts/robolab-import-006/external-record.json"
)


def _table(assessment: dict) -> dict:
    return {
        row["obligation"]: (row["status"], row["gap_code"]) for row in assessment["obligations"]
    }


@pytest.mark.skipif(
    not (READER_COMPACT.is_file() and RETAINED.is_file()), reason="reader output absent"
)
def test_execution_reader_output_lands_on_the_same_obligation_table():
    """Codex's reader (nisayon.external-record.v1) and the direct h5py inspection agree."""
    from nisayon.evaluation.external import inventory_from_external_record

    compact = json.loads(READER_COMPACT.read_text())
    converted = inventory_from_external_record(compact)
    assert converted["unmapped_fields"] == []
    assert converted["source"]["sha256"] == json.loads(RETAINED.read_text())["source"]["sha256"]
    from_reader = assess_inventory(converted)
    from_bytes = assess_inventory(json.loads(RETAINED.read_text()))
    assert from_reader["rejected"] is False
    assert _table(from_reader) == _table(from_bytes)
    assert converted["direct_measurements"]["initial_state_rows_identical"] is True
    assert converted["direct_measurements"]["initial_state_leading_axis"] == [2]
    if READER_FULL.is_file():
        full = inventory_from_external_record(json.loads(READER_FULL.read_text()))
        assert _table(assess_inventory(full)) == _table(from_bytes)
        retained = json.loads(RETAINED.read_text())["direct_measurements"]
        assert full["direct_measurements"]["action_bounds"] == retained["action_bounds"]
        assert full["direct_measurements"]["gripper_column_values"] == [0.0, 1.0]


def test_external_record_converter_rejects_other_schemas_and_flags_mapping_issues():
    from nisayon.evaluation.external import inventory_from_external_record

    with pytest.raises(Malformed):
        inventory_from_external_record({"schema": "nisayon.first_case.v1"})
    document = {
        "schema": "nisayon.external-record.v1",
        "format": "robolab_hdf5_bounded_v1",
        "source": {"path": "data.hdf5", "sha256": "ab" * 32, "bytes": 10},
        "mapping_sources": {"robolab_commit": "deadbeef"},
        "data_attributes": {"total": 3, "policy": "x"},
        "producer_configuration": {"sim_dt": 0.01, "decimation": 2, "actions": {"body": {}}},
        "mapping_issues": ["shape inconsistency: states hold 2 rows, actions 3"],
        "episodes": [
            {
                "id": "demo_0",
                "attributes": {"num_samples": 3, "success": False},
                "action_rows": 3,
                "fields": {
                    "actions": {
                        "shape": [3, 2],
                        "dtype": "<f4",
                        "finite": True,
                        "source_dataset": "/data/demo_0/actions",
                        "mapping": {
                            "semantic": "action_manager_input",
                            "alignment": "pre_step_action_manager_input",
                        },
                    },
                    "states/x": {
                        "shape": [2, 2],
                        "dtype": "<f4",
                        "finite": True,
                        "source_dataset": "/data/demo_0/states/x",
                        "mapping": {"semantic": "recorded_scene_state", "alignment": "post_step"},
                    },
                    "odd": {
                        "shape": [3],
                        "dtype": "<i8",
                        "source_dataset": "/data/demo_0/odd",
                        "mapping": {"semantic": "unknown_numeric", "alignment": None},
                    },
                },
                "initial_state": {"emission_counts": [1], "rows_identical": True},
            }
        ],
    }
    inventory = inventory_from_external_record(document)
    assert inventory["unmapped_fields"] == ["/data/demo_0/odd"]
    assert inventory["producer_declarations"]["step_period_s"] == pytest.approx(0.02)
    assessment = assess_inventory(inventory)
    assert assessment["rejected"] is True
    codes = {r["code"] for r in assessment["rejections"]}
    assert {"row_count_inconsistent", "record_inconsistent"} <= codes


@pytest.mark.skipif(not READER_COMPACT.is_file(), reason="reader output absent")
def test_external_command_reads_the_execution_reader_document(tmp_path):
    import subprocess
    import sys

    out = tmp_path / "assessment.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "external",
            str(READER_COMPACT),
            "--json",
            "--out",
            str(out),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assessment = json.loads(out.read_text())
    assert assessment["schema"] == ASSESSMENT_SCHEMA and assessment["rejected"] is False
    assert assessment["repair_comparison_applicable"] is False
    text = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "external", str(READER_COMPACT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert text.returncode == 0 and text.stdout.startswith("External record assessment: assessed")


@pytest.mark.skipif(
    not (RETAINED.is_file() and FIRST_INVENTORY.is_file()), reason="retained inventories absent"
)
def test_second_inventory_differs_from_the_first_only_in_the_end_effector_frame_label():
    first = json.loads(FIRST_INVENTORY.read_text())
    second = json.loads(RETAINED.read_text())
    assert first["direct_measurements"] == second["direct_measurements"]
    assert first["consistency"] == second["consistency"]
    assert first["producer_declarations"] == second["producer_declarations"]
    differing = [
        (a["path"], a["frame"], b["frame"])
        for a, b in zip(
            first["episodes"][0]["fields"], second["episodes"][0]["fields"], strict=True
        )
        if a != b
    ]
    assert differing and all(path.startswith("ee_pose/") for path, _, _ in differing)
    assert all("robot-root frame" in new for _, _, new in differing)
    assert _table(assess_inventory(first)) == _table(assess_inventory(second))
