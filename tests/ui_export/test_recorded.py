"""Check the retained meanings, including failed obligations and unavailable evidence."""

import copy
import gzip
import json
from pathlib import Path

import pytest

from nisayon.ui_export.bytes import ExportError
from nisayon.ui_export.library import CASES, Archive
from nisayon.ui_export.semantics import check_context
from nisayon.ui_export.source import Sources
from nisayon.ui_export.validate import select, validate_generation

ROOT = Path(__file__).resolve().parents[2]
COMPACT = ROOT / "docs/experiments/results/development-ablation-001"
RECORDED = ROOT / "fixtures/ui/recorded"


@pytest.fixture(scope="module", params=CASES)
def recorded(request):
    return request.param, validate_generation(RECORDED / request.param, strict_optional=True)


def chosen(generation, run, index=0, phase="before"):
    case = next(iter(generation["cases"].values()))
    return select(
        generation,
        {
            "generation_sha256": generation["generation_sha256"],
            "case_key": case["case_key"],
            "run": run["key"],
            "row_index": index,
            "phase": phase,
            "clock": "simulation",
        },
    )


def test_every_recorded_original_matches_its_exact_bundle(recorded):
    case_id, generation = recorded
    case = next(iter(generation["cases"].values()))
    stages = {run["stage"] for run in case["runs"]}
    originals = {}
    for stage in stages:
        bundle = json.loads(
            gzip.decompress(
                (COMPACT / case_id / "B" / stage / "execution/bundle.json.gz").read_bytes()
            )
        )
        originals[stage] = {run["id"]: run for run in bundle["runs"]}
    for run in case["runs"]:
        original = originals[run["stage"]][run["key"]["run_id"]]
        rows = generation["objects"][run["samples"]["path"]]["rows"]
        assert [sample["original"] for sample in rows] == original["trace"]
        assert run["costs"] == original["costs"]
        assert run["cost_parent_run_id"] == original.get("cost_parent_run_id")
        assert run["sample_count"] == len(original["trace"])
        assert run["reconstruction"] is not None
    assert len(case["runs"]) == sum(len(runs) for runs in originals.values())
    trial = json.loads((COMPACT / case_id / "B/trial.json").read_text())
    assert case["trial"]["status"] == trial["status"]
    assert case["trial"]["costs"] == trial["costs"]
    assert case["trial"]["costs"]["engineer_time"]["value"] is None


def test_required_case_distinctions(recorded):
    case_id, generation = recorded
    case = next(iter(generation["cases"].values()))
    diagnostic = {r["key"]["run_id"]: r for r in case["runs"] if r["stage"] == "diagnostic"}
    decisions = [generation["objects"][ref["path"]] for ref in case["decisions"]]
    assert decisions[0]["decision"] == "unresolved"
    if case_id in {"D01-gripper-sign", "D03-observation-backlog", "D05-recurrent-carry"}:
        assert case["confirmation"]["summary"]["fresh_declared"] == 32
        assert len(case["confirmation"]["pairs"]) == 33
    if case_id == "D01-gripper-sign":
        assert decisions[-1]["decision"] == "accepted"
        event = next(f for f in case["findings"] if f["run"] == diagnostic["regression-0"]["key"])
        assert (event["code"], event["row_index"], event["step"]) == (
            "gripper_transport_mismatch",
            0,
            0,
        )
    elif case_id == "D03-observation-backlog":
        run = diagnostic["regression-0"]
        assert run["task_outcome"] == "completed"
        assert run["evaluator"]["timing"] == "violated"
        assert [
            chosen(generation, run, i)["sample"]["observation_age_s"] for i in range(4)
        ] == pytest.approx([0, 0.05, 0.10, 0.15])
        event = next(f for f in case["findings"] if f["run"] == run["key"])
        assert (event["code"], event["step"]) == ("observation_age_violation", 1)
    elif case_id == "D05-recurrent-carry":
        assert case["trial"]["status"] == decisions[-1]["decision"] == "rejected"
        pair = next(
            p
            for p in case["confirmation"]["pairs"]
            if p["condition_id"] == "seed-10423-prefix-10-21"
        )
        assert pair["verdict"] == "both_failed"
        assert pair["reference_outcome"] == pair["candidate_outcome"] == "failed"
        reason = decisions[-1]["reasons"][0]
        assert reason == {
            "code": "progress_lost",
            "severity": "rejected",
            "detail": "lift.cube_raised: gain 0.002936 m is below the minimum 0.01",
            "run_id": "confirmation-correction-10423",
        }
        assert "step" not in reason and "row_index" not in reason
        run = next(r for r in case["runs"] if r["key"] == pair["candidate_run"])
        assert run["sample_count"] == 400
        first, last = chosen(generation, run)["sample"], chosen(generation, run, 399)["sample"]
        assert last["original"]["cube_height_m"] - first["original"]["cube_height_m"] < 0.01
        assert any(r["cost_parent_run_id"] for r in case["runs"])
    elif case_id == "D06-stateless-inference":
        assert case["trial"]["status"] == "unsupported"
        assert diagnostic["regression-0"]["task_outcome"] == "completed"
    elif case_id == "D08-old-future-replay":
        assert case["trial"]["status"] == "invalid"
        assert len(case["runs"]) == 2
        assert case["trial"]["proposals"][0]["executed"] is False
        assert case["trial"]["proposals"][0]["rejected_before_execution"] is True
        assert "invalid-replay-control" in decisions[0]["runs"]
        assert decisions[0]["bundle_sha256"] != decisions[0]["execution_bundle_sha256"]
        assert all(
            c["available_as_recorded_run"] is False for c in case["trial"]["derived_controls"]
        )
        with pytest.raises(ExportError, match="unknown selected run"):
            fake = copy.deepcopy(diagnostic["regression-0"])
            fake["key"]["run_id"] = "invalid-replay-control"
            chosen(generation, fake)
    elif case_id == "D10-opaque-policy-state":
        assert case["trial"]["status"] == "unresolved"
        for run in case["runs"]:
            assert run["evaluator"]["measurement"] == "unresolved"
            rows = generation["objects"][run["samples"]["path"]]["rows"]
            assert all(s["memory"]["before"] == s["memory"]["after"] == "unavailable" for s in rows)
            assert all(s["memory"]["before_sha256"] is None for s in rows)
            assert chosen(generation, run)["frame"] is not None


def test_swapped_condition_and_evaluator_are_rejected(recorded):
    _, generation = recorded
    case = copy.deepcopy(next(iter(generation["cases"].values())))
    case["runs"][0]["condition_id"] = "seed-other"
    sources = {s["id"]: s for s in generation["manifest"]["sources"]}
    with pytest.raises(ExportError, match="condition mismatch"):
        check_context(case, sources, generation["objects"])
    case = copy.deepcopy(next(iter(generation["cases"].values())))
    case["runs"][0]["evaluator"]["measurement"] = "invented-valid"
    with pytest.raises(ExportError, match="evaluator projection"):
        check_context(case, sources, generation["objects"])


def test_changed_archive_child_is_rejected(tmp_path):
    import shutil

    shutil.copy(COMPACT / "archive-manifest.json", tmp_path / "archive-manifest.json")
    relative = "D06-stateless-inference/B/trial.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes((COMPACT / relative).read_bytes() + b" ")
    with pytest.raises(ExportError, match="byte length mismatch"):
        Archive(tmp_path, Sources()).json(relative)
