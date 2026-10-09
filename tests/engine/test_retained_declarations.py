"""Real retained metadata exercises the writer without rerunning physics."""

import csv
import io
import json
from pathlib import Path

import pytest

from nisayon.engine import retained_declarations as workflow
from nisayon.engine.declarations import inspect_declaration
from nisayon.engine.io import file_digest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/experiments/results/development-ablation-001"
PLAN = ROOT / "work/development/retained-declaration-plan-v1.json"


def test_real_twenty_assignments_keep_claims_and_historical_outcomes_separate(tmp_path):
    output = tmp_path / "demonstration"
    before = file_digest(SOURCE / "comparison-ledger.json")
    packet = workflow.run_demo(SOURCE, PLAN, output)
    assert len(packet["rows"]) == len(packet["assignments"]) == 20
    assert packet["new_model_calls"] == packet["new_simulator_executions"] == 0
    assert packet["evidence_scope"] == "retained_development_demonstration"
    declarations, terminal_starts = [], []
    for row in packet["rows"]:
        receipt = json.loads((output / row["declaration"]["path"]).read_text())
        terminal = json.loads((output / row["terminal_start"]["path"]).read_text())
        declarations.append(receipt["observed"]["recorded_at"])
        terminal_starts.append(terminal["observed"]["recorded_at"])
        assert row["historical_trial"]["costs"]["engineer_time"]["value"] is None
        assert row["recovery"]["state"] == "terminal_evidence_retained"
        assert not row["recovery"]["findings"]
        if row["case_id"].startswith("D05"):
            assert receipt["disposition"] == "claim_acceptance"
            assert row["retained_decision"] == row["historical_trial"]["status"] == "rejected"
        if row["case_id"].startswith("D10"):
            assert receipt["disposition"] == "unresolved" and receipt["candidate"] is None
    assert max(declarations) <= min(terminal_starts)
    assert file_digest(SOURCE / "comparison-ledger.json") == before
    table = workflow.render_packet(packet, output)
    assert all(row["case_id"] + "\t" + row["arm"] + "\t" in table for row in packet["rows"])
    costs = list(csv.DictReader(io.StringIO(workflow.render_costs(packet, output)), delimiter="\t"))
    shared = [row for row in costs if row["category"] == "recorded_command_wall"]
    assert len(shared) == 1 and float(shared[0]["value"]) == 2534.406124
    missing = [
        row
        for row in costs
        if row["scope"] == "historical_trial" and row["category"] == "engineer_time"
    ]
    assert len(missing) == 20 and all(
        row["value"] == "unknown" and row["missing"] for row in missing
    )
    _, preparation = workflow._bound(output, packet["historical_preparation_cost_ledger"])
    assert preparation["schema"] == "nisayon.execution.costs.v2"
    retained = {p: file_digest(p) for p in output.rglob("*") if p.is_file()}
    recovery = workflow.inspect_demo(output)
    assert recovery["assigned_trials"] == recovery["terminal_records_retained"] == 20
    assert recovery["declarations_missing"] == recovery["rows_with_findings"] == 0
    assert all(row["declaration_disposition"] is not None for row in recovery["rows"])
    assert retained == {p: file_digest(p) for p in output.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="new output directory"):
        workflow.run_demo(SOURCE, PLAN, output)


def test_failure_consuming_terminal_evidence_retains_all_preceding_declarations(
    tmp_path, monkeypatch
):
    original = workflow._bound

    def broken(root, reference):
        if reference["path"].endswith("confirmation/decision.json"):
            raise ValueError("Labelled injected terminal read failure")
        return original(root, reference)

    monkeypatch.setattr(workflow, "_bound", broken)
    output = tmp_path / "partial"
    with pytest.raises(ValueError, match="terminal read failure"):
        workflow.run_demo(SOURCE, PLAN, output)
    rows = json.loads((output / "declarations.json").read_text())["rows"]
    assert len(rows) == 20 and not (output / "packet.json").exists()
    recovered = [
        inspect_declaration(
            output / row["case_id"] / row["arm"] / "declaration", evidence_root=output
        )
        for row in rows
    ]
    assert recovered[0]["state"] == "terminal_started_outcome_unknown"
    assert all(r["state"] == "declared_awaiting_terminal" for r in recovered[1:])
    report = workflow.inspect_demo(output)
    assert report["assigned_trials"] == 20
    assert report["declarations_missing"] == report["terminal_records_retained"] == 0
    assert report["new_processing_cost"]["outer_command_wall_s"] is None


def test_early_interruption_keeps_missing_assignments_distinct_from_nonclaims(
    tmp_path, monkeypatch
):
    declare = workflow.declare
    seen = 0

    def interrupted(*args, **kwargs):
        nonlocal seen
        seen += 1
        if seen == 3:
            raise OSError("Labelled interruption before third declaration")
        return declare(*args, **kwargs)

    monkeypatch.setattr(workflow, "declare", interrupted)
    output = tmp_path / "partial-statements"
    with pytest.raises(OSError, match="before third declaration"):
        workflow.run_demo(SOURCE, PLAN, output)
    assert not (output / "declarations.json").exists()
    report = workflow.inspect_demo(output)
    assert report["assigned_trials"] == 20 and report["declarations_missing"] == 18
    assert report["terminal_records_retained"] == report["rows_with_findings"] == 0
    assert len(workflow.render_recovery(report).splitlines()) == 21
    assert [row["declaration_disposition"] for row in report["rows"][2:]] == [None] * 18


def test_recovery_exposes_a_cross_arm_statement_without_losing_other_assignments(tmp_path):
    output = tmp_path / "changed-statement"
    packet = workflow.run_demo(SOURCE, PLAN, output)
    first, second = packet["rows"][:2]
    target = output / first["declaration"]["path"]
    target.write_bytes((output / second["declaration"]["path"]).read_bytes())
    report = workflow.inspect_demo(output)
    assert report["assigned_trials"] == 20
    assert report["rows_with_findings"] == 1
    assert report["rows"][0]["declaration_disposition"] is None
    assert (
        "Declaration differs from this frozen assignment"
        in report["rows"][0]["recovery"]["findings"]
    )


@pytest.mark.parametrize("corruption", ["syntax", "not_object", "wrong_schema"])
def test_damaged_cost_record_keeps_receipts_and_every_assignment_visible(tmp_path, corruption):
    output = tmp_path / "damaged-cost"
    packet = workflow.run_demo(SOURCE, PLAN, output)
    first = packet["rows"][0]
    receipt = output / first["declaration"]["path"]
    before = receipt.read_bytes()
    cost = next((receipt.parent / "attempts").glob("*.result.json"))
    damaged = json.loads(cost.read_text())
    damaged["schema"] = "unrecognized-attempt-result"
    cost.write_text(
        "{damaged labelled test copy"
        if corruption == "syntax"
        else json.dumps([] if corruption == "not_object" else damaged)
    )
    report = workflow.inspect_demo(output)
    assert report["assigned_trials"] == report["terminal_records_retained"] == 20
    assert report["declarations_missing"] == 0 and report["rows_with_findings"] == 1
    assert report["new_processing_cost"]["attempts_with_unknown_cost"] == 1
    assert report["rows"][0]["declaration_disposition"] == "claim_acceptance"
    assert receipt.read_bytes() == before


@pytest.mark.parametrize(
    "corruption", ["observed_shape", "observed_clock", "terminal_evidence", "reference_shape"]
)
def test_malformed_receipt_preserves_other_assignments_and_exposes_the_damaged_bytes(
    tmp_path, corruption
):
    output = tmp_path / "damaged-receipt"
    packet = workflow.run_demo(SOURCE, PLAN, output)
    first = packet["rows"][0]
    target = (
        output
        / first["declaration" if corruption.startswith("observed") else "terminal_result"]["path"]
    )
    value = json.loads(target.read_text())
    if corruption == "observed_shape":
        value["observed"] = []
    elif corruption == "observed_clock":
        value["observed"]["recorded_at"] = None
    elif corruption == "terminal_evidence":
        value["terminal_evidence"] = None
    else:
        value["terminal_evidence"] = [None]
    target.write_text(json.dumps(value))
    damaged = target.read_bytes()
    report = workflow.inspect_demo(output)
    assert report["assigned_trials"] == 20 and report["declarations_missing"] == 0
    assert report["rows_with_findings"] == 1
    assert report["rows"][0]["recovery"]["findings"]
    assert all(row["declaration_disposition"] is not None for row in report["rows"])
    assert all(row["terminal_record_decision"] is not None for row in report["rows"][1:])
    assert target.read_bytes() == damaged


def test_a_different_plan_suite_is_rejected_before_freezing(tmp_path):
    plan = json.loads(PLAN.read_text())
    plan["source_suite_sha256"] = "0" * 64
    modified = tmp_path / "wrong-plan.json"
    modified.write_text(json.dumps(plan))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="another historical suite"):
        workflow.run_demo(SOURCE, modified, output)
    assert not output.exists()
