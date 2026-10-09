"""Actual retained evidence and mutations; no simulator or raw-store copies."""

import copy
import gzip
import json
import os
from pathlib import Path

import pytest

from nisayon.engine.confirmation_costs import reconcile, trial_costs
from nisayon.engine.confirmation_pairs import assigned_pairs, iter_pairs, run_observation
from nisayon.engine.confirmation_view import (
    INPUTS,
    PinnedInputs,
    build_view,
    load_export,
    main,
    validate_view,
)
from nisayon.engine.io import digest, file_digest

ROOT = Path(__file__).resolve().parents[2]
COMPARISON = "development-ablation-001"


def retained(case):
    root = ROOT / "docs/experiments/results" / COMPARISON / case / "A/confirmation"
    bundle = json.loads(gzip.decompress((root / "execution/bundle.json.gz").read_bytes()))
    protocol = json.loads((root / "execution/frozen-protocol.json").read_text())
    result = json.loads((root / "confirmation-result.json").read_text())
    identity = {
        "comparison": COMPARISON,
        "case_id": case,
        "arm": "A",
        "original_incident_id": case,
        "repetition_id": None,
        "candidate_sha256": result["candidate_digest"],
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": digest(protocol),
    }
    return bundle, protocol, identity


@pytest.fixture(scope="module")
def complete():
    return retained("D01-gripper-sign")


def pairs(data, issues=()):
    return assigned_pairs(*data, binding_issues=list(issues))


def test_complete_actual_membership_and_file_order_independence(complete):
    result = pairs(complete)
    assert len(result["assignments"]) == 67
    assert len(result["pairs"]) == 33
    assert {p["state"] for p in result["pairs"]} == {"complete"}
    assert result["unpaired_assignment_indices"] == [1]  # retained regression reproduction
    bundle, protocol, identity = complete
    shuffled = {**bundle, "runs": list(reversed(bundle["runs"]))}
    other = pairs((shuffled, protocol, identity))
    for left, right in zip(result["pairs"], other["pairs"], strict=True):
        assert left["id"] == right["id"]
        for side in ("reference", "candidate"):
            assert (
                result["observations"][left[side]["record_indices"][0]]
                == other["observations"][right[side]["record_indices"][0]]
            )


def test_executed_prefix_and_progress_loss_remain_visible():
    data = retained("D05-recurrent-carry")
    result = pairs(data)
    assert len(result["assignments"]) == 134
    assert len(result["pairs"]) == 33
    assert len(result["unpaired_assignment_indices"]) == 68  # 67 prefixes + regression
    assert {p["state"] for p in result["pairs"]} == {"complete"}
    observations = result["observations"]
    assert any(r["progress"]["status"] == "lost" for r in observations)
    assert {r["progress"]["unit"] for r in observations} == {"m"}
    assert any(r["recorded_task_outcome"] == "failed" for r in observations)
    assert any(r["reset"]["prefix_run"] for r in observations)
    assert any(r["cost_parent_run_id"] for r in observations)


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ("missing", "candidate_record_count_0"),
        ("duplicate", "candidate_record_count_2"),
        ("candidate", "candidate_run_identity_mismatch"),
        ("condition", "candidate_run_identity_mismatch"),
        ("case_arm", "candidate_run_identity_mismatch"),
        ("arm", "wrong_bundle_arm"),
        ("nan", "candidate_invalid_or_incomplete_measurements"),
        ("missing_height", "candidate_invalid_or_incomplete_measurements"),
        ("duplicate_assignment", "candidate_assignment_count_2"),
        ("missing_assignment", "candidate_assignment_count_0"),
        ("wrong_outcome", "candidate_outcome_disagrees_with_measurement"),
    ],
)
def test_mutations_preserve_the_assigned_denominator(complete, mutation, expected):
    bundle, protocol, identity = copy.deepcopy(complete)
    run_id = bundle["confirmation"]["candidate_run_ids"][0]
    run = next(r for r in bundle["runs"] if r["id"] == run_id)
    if mutation == "missing":
        bundle["runs"].remove(run)
    elif mutation == "duplicate":
        bundle["runs"].append(copy.deepcopy(run))
    elif mutation in ("candidate", "condition", "case_arm"):
        key = {"candidate": "candidate_sha256", "condition": "condition_id", "case_arm": "case_id"}[
            mutation
        ]
        run[key] = "wrong"
    elif mutation == "arm":
        bundle["arm"] = "B"
    elif mutation == "nan":
        run["trace"][0]["cube_height_m"] = float("nan")
    elif mutation == "missing_height":
        del run["trace"][0]["cube_height_m"]
    elif mutation == "wrong_outcome":
        run["task_outcome"] = "unknown"
    else:
        assignment = next(a for a in protocol["assignments"] if a["run_id"] == run_id)
        if mutation == "duplicate_assignment":
            protocol["assignments"].append(copy.deepcopy(assignment))
        else:
            protocol["assignments"].remove(assignment)
    result = pairs((bundle, protocol, identity))
    assert len(result["pairs"]) == 33
    assert result["pairs"][1]["state"] == "incomplete_or_invalid"
    assert expected in result["pairs"][1]["issues"]
    if mutation == "duplicate":
        assert len(result["observations"]) == 68
    if mutation in ("nan", "missing_height"):
        observed = result["observations"][result["pairs"][1]["candidate"]["record_indices"][0]]
        assert observed["progress"]["value"] is None
        assert observed["measured_task_outcome"] == "unmeasured"


def test_reference_success_candidate_failure_is_not_averaged(complete):
    bundle, protocol, identity = copy.deepcopy(complete)
    run_id = bundle["confirmation"]["candidate_run_ids"][0]
    run = next(r for r in bundle["runs"] if r["id"] == run_id)
    # Explicit synthetic mutation of the measured height and reported outcome;
    # this is a pair-reader test, never a verified physical run.
    for row in run["trace"]:
        row["cube_height_m"] = 0.81
    run["task_outcome"] = "failed"
    result = pairs((bundle, protocol, identity), ["labelled_mutation_not_raw_verified"])
    view = {"trials": [{"state": "incomplete_or_invalid", "confirmation": result}]}
    row = list(iter_pairs(view))[1]
    assert row["reference_observations"][0]["recorded_task_outcome"] == "completed"
    assert row["candidate_observations"][0]["recorded_task_outcome"] == "failed"
    assert row["state"] == "incomplete_or_invalid"


def test_equal_seeds_in_different_arms_are_distinct(complete):
    first = pairs(complete)
    bundle, protocol, identity = complete
    second = pairs((bundle, protocol, {**identity, "arm": "B"}))
    assert not {p["id"] for p in first["pairs"]} & {p["id"] for p in second["pairs"]}


def test_declared_controller_convention_uses_the_actual_producer_field(complete):
    bundle, protocol, _ = complete
    run = copy.deepcopy(bundle["runs"][0])
    legacy = run_observation(run, protocol["predicates"])["controller_target_convention"]
    assert legacy["recorded"] is None and legacy["omission"]
    for convention in ("restored", "nominal"):
        run["configuration"]["deployment"]["controller_target"] = convention
        observed = run_observation(run, protocol["predicates"])["controller_target_convention"]
        assert observed["recorded"] == convention and observed["omission"] is None


def test_missing_confirmation_cost_is_not_zero():
    missing = trial_costs({}, None, assigned=True)
    unscheduled = trial_costs({}, None, assigned=False)
    assert missing["physical_rollouts"] is None
    assert missing["preparation_plus_phase_wall_s"] is None
    assert unscheduled["physical_rollouts"] == 0
    assert unscheduled["confirmation"] == "not_scheduled"


def test_costs_include_rejected_prefix_case_and_timer_discrepancy():
    root = ROOT / "docs/experiments/results" / COMPARISON
    ledger = json.loads((root / "comparison-ledger.json").read_text())
    score = json.loads((root / "comparison-score.json").read_text())
    trials = []
    for t in ledger["trials"]:
        ref = t.get("confirmation")
        result = json.loads((root / ref["path"]).read_text()) if ref else None
        trials.append(
            {
                "comparison": COMPARISON,
                "arm": t["arm"],
                "costs": trial_costs(t, result, assigned=bool(ref)),
            }
        )
    report = reconcile(trials, {COMPARISON: score})
    a = report["groups"][0]
    assert a["assigned_trials"] == 10 and a["confirmation_phases"] == 7
    assert a["components"]["physical_rollouts"]["known_sum"] == 536
    assert a["components"]["nested_reset_rollout_trace_write_wall_s"]["known_sum"] == pytest.approx(
        612.048496
    )
    assert a["phase_timer_discrepancy_s"] < 0
    assert abs(a["computed_minus_score_confirmation_wall_s"]) < 1e-8
    assert a["score_costs_unchanged"]["engineer_time"]["missing_trials"] == 10


def test_changed_metadata_is_pinned_and_explicit(tmp_path, monkeypatch):
    # Point only the checked local-file lookup at a labelled copy. Git bytes
    # still come from the actual pinned source, and cannot be silently replaced.
    spec = json.loads((ROOT / INPUTS).read_text())
    reader = PinnedInputs(ROOT, spec["source_commit"])
    name = f"docs/experiments/results/{COMPARISON}/comparison-score.json"
    original = reader.document(name)
    local = tmp_path / "score.json"
    local.write_text('{"label":"changed source control"}')
    monkeypatch.setattr("nisayon.engine.confirmation_view.resolve_member", lambda root, path: local)
    other = PinnedInputs(ROOT, spec["source_commit"])
    assert other.document(name) == original
    assert other.issues(name)


def test_actual_complete_read_and_dependency_invalidation(monkeypatch):
    if not (ROOT / "artifacts" / COMPARISON).exists():
        pytest.skip("Original raw store is local evidence, not a copied test fixture")
    spec = json.loads((ROOT / INPUTS).read_text())
    view, _ = build_view(ROOT, spec, selection=[[COMPARISON, "D01-gripper-sign", "A"]])
    assert view["trials"][0]["state"] == "complete"
    expected = digest(view)
    assert validate_view(view, ROOT, expected_content_sha256=expected)["status"] == "current"
    monkeypatch.setattr(
        "nisayon.engine.confirmation_view.dependencies", lambda repo: {"changed": "evaluation"}
    )
    assert validate_view(view, ROOT, expected_content_sha256=expected)["status"] == "invalidated"


def test_missing_raw_keeps_all_pairs_and_explicit_unavailability(tmp_path):
    spec = json.loads((ROOT / INPUTS).read_text())
    view, _ = build_view(
        ROOT, spec, raw_base=tmp_path, selection=[[COMPARISON, "D01-gripper-sign", "A"]]
    )
    rows = list(iter_pairs(view))
    assert len(rows) == 33
    assert all(p["state"] == "incomplete_or_invalid" for p in rows)
    assert any("raw_bundle_unavailable" in issue for issue in rows[0]["issues"])
    assert (
        validate_view(view, ROOT, expected_content_sha256=digest(view))["status"] == "invalidated"
    )


def test_reused_view_checks_content_and_raw_bytes_even_when_timestamp_unchanged(
    tmp_path, monkeypatch
):
    raw = tmp_path / "frozen-protocol.json"
    raw.write_text('{"original":"protocol"}')
    stat = raw.stat()
    monkeypatch.setattr(
        "nisayon.engine.confirmation_view.dependencies", lambda repo: {"evaluator": "v1"}
    )
    view = {
        "dependencies": {"evaluator": "v1"},
        "sources": [],
        "trials": [
            {
                "state": "complete",
                "case_id": "labelled-test",
                "arm": "A",
                "confirmation": {
                    "raw_source": {
                        "root_locator": str(tmp_path),
                        "files": [{"path": raw.name, "sha256": file_digest(raw)}],
                    }
                },
            }
        ],
    }
    expected = digest(view)
    assert validate_view(view, ROOT, expected_content_sha256=expected)["status"] == "current"
    altered = copy.deepcopy(view)
    altered["trials"][0]["arm"] = "B"
    assert (
        "derived_view_bytes_changed"
        in validate_view(altered, ROOT, expected_content_sha256=expected)["issues"]
    )
    raw.write_text('{"changed!":"protocol"}')
    os.utime(raw, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert raw.stat().st_mtime_ns == stat.st_mtime_ns
    assert validate_view(view, ROOT, expected_content_sha256=expected)["status"] == "invalidated"


def test_selected_analysis_order_controls_reads_not_only_output(monkeypatch):
    spec = json.loads((ROOT / INPUTS).read_text())
    visited = []

    def inspect(reader, comparison, case, arm, raw_base, ledger):
        visited.append([comparison, case["id"], arm])
        return {"comparison": comparison, "case_id": case["id"], "arm": arm}, {}

    monkeypatch.setattr("nisayon.engine.confirmation_view._trial", inspect)
    order = spec["profiling"]["trials_in_order"]
    _, timings = build_view(ROOT, spec, selection=order)
    assert visited == order == [row["trial"] for row in timings["trials"]]
    with pytest.raises(ValueError, match="unique assigned"):
        build_view(ROOT, spec, selection=[order[0], order[0]])


def test_changed_export_is_rejected_before_reuse(tmp_path):
    output = tmp_path / "view.json"
    output.write_text('{"label":"original"}')
    (tmp_path / "manifest.json").write_text(
        json.dumps({"view_sha256": file_digest(output), "files": {}})
    )
    output.write_text('{"label":"altered"}')
    with pytest.raises(ValueError, match="differs from its retained output manifest"):
        load_export(tmp_path, ROOT)


@pytest.mark.parametrize("kind", ["raw", "metadata"])
def test_cli_cannot_write_inside_original_evidence(monkeypatch, kind):
    base = ROOT / ("artifacts" if kind == "raw" else "docs/experiments/results")
    output = base / COMPARISON / "forbidden-view-test"
    monkeypatch.setattr(
        "sys.argv",
        [
            "confirmation_view",
            "--inputs",
            str(ROOT / INPUTS),
            "--repo",
            str(ROOT),
            "--out",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()
