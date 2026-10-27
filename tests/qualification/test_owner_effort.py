"""Synthetic accounting controls, never observations of owner productivity."""

import copy
import importlib.util
import io
import json
import os
import select
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "examples/qualification/owner_effort"
SPEC = importlib.util.spec_from_file_location("owner_effort", PACKAGE / "effort.py")
effort = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(effort)


def measured(value):
    return {"value": value, "reference": "synthetic receipt", "reason": ""}


def unknown():
    return {"value": None, "reference": "", "reason": "Not measured"}


@pytest.fixture
def ledger():
    outcome = {
        "decision": "replace",
        "valid": True,
        "reference": "synthetic oracle",
        "owner_acceptance": "accepted",
        "owner_reference": "synthetic owner receipt",
    }
    return {
        "schema": "nisayon.owner-effort.v1",
        "kind": "synthetic_control",
        "scope": "Synthetic initial and reuse cases; all work through a fixed maintenance horizon",
        "protocol_reference": "synthetic protocol",
        "actors": {
            "owner": {"role": "owner", "usd_per_hour": measured(3600)},
            "builder": {"role": "engineering", "usd_per_hour": measured(3600)},
        },
        "cases": {
            name: {
                "stage": name,
                "selection_reference": "synthetic selection",
                "expected": "replace",
                "baseline": copy.deepcopy(outcome),
                "candidate": copy.deepcopy(outcome),
            }
            for name in ("initial", "reuse")
        },
        "activity_files": [],
        "coverage": {
            arm: {
                phase: {
                    "actors": {
                        person: {
                            "complete": True,
                            "reference": "synthetic complete coverage",
                            "reason": "",
                        }
                        for person in ("owner", "builder")
                    },
                    "charges_usd": {name: measured(0) for name in effort.CHARGES},
                }
                for phase in effort.PHASES
            }
            for arm in effort.ARMS
        },
    }


def activity(
    root,
    ledger,
    name,
    begin,
    duration,
    *,
    arm="baseline",
    actor="owner",
    phase="setup",
    case="initial",
    status="completed",
    open_prefix=False,
):
    directory = root / "activities"
    directory.mkdir(exist_ok=True)
    start = datetime(2026, 10, 24, tzinfo=UTC) + timedelta(seconds=begin)
    rows = [
        {
            "event": "start",
            "id": name,
            "actor": actor,
            "arm": arm,
            "case": case,
            "phase": phase,
            "reference": "synthetic activity",
            "utc": start.isoformat(),
            "ns": int(begin * 1e9),
        }
    ]
    if not open_prefix:
        rows.append(
            {
                "event": "stop",
                "id": name,
                "utc": (start + timedelta(seconds=duration)).isoformat(),
                "ns": int((begin + duration) * 1e9),
                "status": status,
            }
        )
    path = directory / f"{name}.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    ledger["activity_files"].append(str(path.relative_to(root)))
    return path


def totals(report, unit="USD"):
    return {
        arm: report["finite_comparisons"][unit][f"{arm}_costs"]["total"] for arm in effort.ARMS[:2]
    }


def test_shared_preparation_prevents_free_amortization_and_keeps_synthetic_label(ledger, tmp_path):
    activity(tmp_path, ledger, "base", 0, 100)
    activity(tmp_path, ledger, "candidate", 100, 40, arm="candidate")
    activity(tmp_path, ledger, "preparation", 140, 100, arm="shared", case="preparation")
    report = effort.assess(ledger, tmp_path)
    assert totals(report) == {"baseline": 200, "candidate": 140}
    assert report["study_phase_totals"]["USD"]["setup"] == 240
    assert report["status"] == "contradicted"
    assert report["finite_comparisons"]["USD"]["status"] == "contradicted"
    assert "no_owner_experiment" in report["reasons"]


def test_exact_twofold_gate_is_finite_arithmetic_not_owner_experiment(ledger, tmp_path):
    activity(tmp_path, ledger, "base", 0, 100)
    activity(tmp_path, ledger, "candidate", 100, 50, arm="candidate")
    report = effort.assess(ledger, tmp_path)
    assert report["status"] == "unresolved"
    assert report["finite_comparisons"]["USD"]["status"] == "supported_within_declared_scope"
    assert report["baseline_minus_candidate_owner_seconds_by_phase"]["setup"] == 50


@pytest.mark.parametrize(
    "baseline,candidate,extra,shared",
    [
        (2, 1, 2**-54, 0),
        (2, 1, 0, 2**-54),
        (2**54, 2**53 + 1, 0, 0),
        (2 * 10**400, 10**400, 1, 0),
    ],
)
def test_cost_aggregation_cannot_erase_a_failed_target(
    ledger, tmp_path, baseline, candidate, extra, shared
):
    for arm, value in (("baseline", baseline), ("candidate", candidate), ("shared", shared)):
        ledger["coverage"][arm]["setup"]["charges_usd"]["provider"] = measured(value)
    ledger["coverage"]["candidate"]["setup"]["charges_usd"]["compute"] = measured(extra)
    report = effort.assess(ledger, tmp_path)
    assert report["finite_comparisons"]["USD"]["status"] == "contradicted"
    assert "no_owner_experiment" in report["reasons"]
    json.dumps(report, allow_nan=False)


def test_microsecond_accounting_does_not_falsely_reject_exact_equality(ledger, tmp_path):
    activity(tmp_path, ledger, "base", 0, 0.6)
    activity(tmp_path, ledger, "candidate-one", 1, 0.1, arm="candidate")
    activity(tmp_path, ledger, "candidate-two", 2, 0.2, arm="candidate")
    report = effort.assess(ledger, tmp_path)
    for unit in ("USD", "owner_active_seconds"):
        assert report["finite_comparisons"][unit]["status"] == "supported_within_declared_scope"
        exact = report["exact_quantities"][f"/phase_ledgers/{unit}/candidate/phases/setup/value"]
        assert (exact["numerator"], exact["denominator"]) == ("3", "10")
        assert exact["display"] == "rounded"
    assert report["status"] == "unresolved"


def test_hourly_rate_division_preserves_nonzero_cost_below_float_range(ledger, tmp_path):
    tiny = float.fromhex("0x0.0000000000001p-1022")
    for actor in ledger["actors"].values():
        actor["usd_per_hour"] = measured(tiny)
    activity(tmp_path, ledger, "base", 0, 2)
    activity(tmp_path, ledger, "candidate", 0, 1, actor="builder", arm="candidate")
    report = effort.assess(ledger, tmp_path)
    assert report["finite_comparisons"]["USD"]["status"] == "supported_within_declared_scope"
    exact = report["exact_quantities"]["/phase_ledgers/USD/candidate/phases/setup/value"]
    assert int(exact["numerator"]) == 1
    assert int(exact["denominator"]) == 3600 * 2**1074
    assert exact["display"] == "rounded"
    assert totals(report)["candidate"] == 0  # Display only; exact cost above is nonzero.
    json.dumps(report, allow_nan=False)


def test_report_roundtrip_retains_exact_rate_semantics_and_marks_missingness(ledger, tmp_path):
    ledger["actors"]["owner"]["usd_per_hour"] = measured(0.1)
    activity(tmp_path, ledger, "base", 0, 0.000001)
    ledger["coverage"]["candidate"]["review"]["charges_usd"]["provider"] = unknown()
    report = json.loads(json.dumps(effort.assess(ledger, tmp_path), allow_nan=False))
    assert report["schema"] == "nisayon.owner-effort-report.v2"
    exact = report["exact_quantities"]["/phase_ledgers/USD/baseline/phases/setup/value"]
    n, d = (0.1).as_integer_ratio()
    assert int(exact["numerator"]) * d * 3_600_000_000 == int(exact["denominator"]) * n
    assert "/phase_ledgers/USD/candidate/phases/review/value" not in report["exact_quantities"]
    assert report["phase_ledgers"]["USD"]["candidate"]["phases"]["review"]["value"] is None
    assert report["finite_comparisons"]["USD"]["status"] == "unresolved"


def test_overflow_display_does_not_lose_exact_equality(ledger, tmp_path):
    for arm, value in (("baseline", 2 * 10**400), ("candidate", 10**400)):
        ledger["coverage"][arm]["setup"]["charges_usd"]["provider"] = measured(value)
    report = effort.assess(ledger, tmp_path)
    assert report["finite_comparisons"]["USD"]["status"] == "supported_within_declared_scope"
    exact = report["exact_quantities"]["/phase_ledgers/USD/candidate/phases/setup/value"]
    assert exact == {"numerator": str(10**400), "denominator": "1", "display": "overflow"}
    assert totals(report)["candidate"] is None
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("nanoseconds,microseconds", [(500, 0), (1500, 2), (2500, 2)])
def test_time_resolution_uses_exact_round_to_even(ledger, tmp_path, nanoseconds, microseconds):
    path = activity(tmp_path, ledger, "tiny", 0, 0)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["ns"] = nanoseconds
    _, begin, end, complete = effort.read_activity(
        "\n".join(json.dumps(row) for row in rows).encode()
    )
    assert complete
    assert end - begin == timedelta(microseconds=microseconds)


def test_clock_disagreement_cannot_round_down_to_the_one_second_limit(ledger, tmp_path):
    path = activity(tmp_path, ledger, "long", 0, 1_000_000_000)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["ns"] = 1_000_000_001 * 1_000_000_000
    effort.read_activity("\n".join(json.dumps(row) for row in rows).encode())
    rows[1]["ns"] += 1
    with pytest.raises(ValueError, match="clocks disagree"):
        effort.read_activity("\n".join(json.dumps(row) for row in rows).encode())


def test_serialized_exact_phase_costs_reconstruct_the_failed_target(ledger, tmp_path):
    from fractions import Fraction

    from nisayon.engine.cost_target import assess_cost_target

    ledger["coverage"]["baseline"]["setup"]["charges_usd"]["provider"] = measured(2)
    ledger["coverage"]["candidate"]["setup"]["charges_usd"]["provider"] = measured(1)
    ledger["coverage"]["candidate"]["setup"]["charges_usd"]["compute"] = measured(2**-54)
    report = json.loads(json.dumps(effort.assess(ledger, tmp_path), allow_nan=False))
    pair = report["phase_ledgers"]["USD"]
    for arm, phases in pair.items():
        for phase, item in phases["phases"].items():
            exact = report["exact_quantities"][f"/phase_ledgers/USD/{arm}/phases/{phase}/value"]
            item["value"] = Fraction(int(exact["numerator"]), int(exact["denominator"]))
    outcome = {"case": {"decision": "replace", "valid": True, "reference": "synthetic"}}
    checked = assess_cost_target(
        {"case": "replace"},
        baseline=outcome,
        candidate=outcome,
        baseline_costs=pair["baseline"],
        candidate_costs=pair["candidate"],
    )
    assert checked["status"] == report["finite_comparisons"]["USD"]["status"] == "contradicted"
    assert checked["cost_ratio_baseline_over_candidate"] == 2  # Rounded display, not acceptance.


def test_overlapping_timers_for_one_activity_count_once_and_people_add(ledger, tmp_path):
    activity(tmp_path, ledger, "one", 0, 10)
    activity(tmp_path, ledger, "nested", 2, 2)
    activity(tmp_path, ledger, "overlap", 5, 10)
    activity(tmp_path, ledger, "builder", 0, 10, actor="builder")
    report = effort.assess(ledger, tmp_path)
    assert totals(report)["baseline"] == 25
    assert totals(report, "owner_active_seconds")["baseline"] == 15
    assert report["overlapping_timers_unioned_for"] == ["owner"]


@pytest.mark.parametrize("change", [{"arm": "candidate"}, {"phase": "review"}, {"case": "reuse"}])
def test_conflicting_simultaneous_human_allocations_are_invalid(ledger, tmp_path, change):
    activity(tmp_path, ledger, "one", 0, 10)
    activity(tmp_path, ledger, "other", 5, 10, **change)
    with pytest.raises(ValueError, match="conflicting allocations"):
        effort.assess(ledger, tmp_path)


@pytest.mark.parametrize("open_prefix", [True, False])
def test_open_and_interrupted_retry_cannot_be_covered_by_complete_attestation(
    ledger, tmp_path, open_prefix
):
    activity(
        tmp_path,
        ledger,
        "retry",
        0,
        10,
        phase="retries",
        arm="candidate",
        open_prefix=open_prefix,
        status="interrupted",
    )
    report = effort.assess(ledger, tmp_path)
    assert "candidate/retries/owner" in report["incomplete_activity_or_coverage"]
    assert totals(report)["candidate"] is None
    assert report["known_active_seconds_by_arm_phase_person"]["candidate/retries/owner"] == (
        0 if open_prefix else 10
    )


def test_omitting_interrupted_record_or_duplicate_record_is_invalid(ledger, tmp_path):
    activity(tmp_path, ledger, "retry", 0, 10, open_prefix=True)
    path = ledger["activity_files"].pop()
    with pytest.raises(ValueError, match="every activity"):
        effort.assess(ledger, tmp_path)
    ledger["activity_files"] = [path, path]
    with pytest.raises(ValueError, match="Duplicate activity path"):
        effort.assess(ledger, tmp_path)


@pytest.mark.parametrize("phase", effort.PHASES)
def test_any_unmeasured_cost_phase_blocks_complete_cost_target(ledger, tmp_path, phase):
    activity(tmp_path, ledger, "base", 0, 100)
    activity(tmp_path, ledger, "candidate", 100, 1, arm="candidate")
    ledger["coverage"]["candidate"][phase]["charges_usd"]["compute"] = unknown()
    report = effort.assess(ledger, tmp_path)
    assert report["finite_comparisons"]["USD"]["status"] == "unresolved"
    assert "complete_cost:complete_costs_unmeasured" in report["reasons"]
    assert totals(report)["candidate"] is None


def test_unmeasured_wage_preserves_seconds_but_prevents_economic_total(ledger, tmp_path):
    activity(tmp_path, ledger, "base", 0, 100)
    ledger["actors"]["owner"]["usd_per_hour"] = unknown()
    report = effort.assess(ledger, tmp_path)
    assert totals(report, "owner_active_seconds")["baseline"] == 100
    assert totals(report)["baseline"] is None


def test_unmeasured_time_at_zero_wage_stays_unknown(ledger, tmp_path):
    ledger["actors"]["owner"]["usd_per_hour"] = measured(0)
    ledger["coverage"]["candidate"]["review"]["actors"]["owner"] = {
        "complete": False,
        "reference": "",
        "reason": "No activity tracker",
    }
    report = effort.assess(ledger, tmp_path)
    assert totals(report)["candidate"] is None
    assert totals(report, "owner_active_seconds")["candidate"] is None


@pytest.mark.parametrize("field", ["selection_reference", "expected"])
def test_missing_selection_or_truth_cannot_qualify_owner_savings(ledger, tmp_path, field):
    ledger["kind"] = "owner_comparison"
    ledger["cases"]["reuse"][field] = None
    assert effort.assess(ledger, tmp_path)["status"] == "unresolved"


@pytest.mark.parametrize(
    "acceptance,status", [("pending", "unresolved"), ("rejected", "contradicted")]
)
def test_owner_acceptance_is_separate_from_passing_tests(ledger, tmp_path, acceptance, status):
    ledger["kind"] = "owner_comparison"
    activity(tmp_path, ledger, "base", 0, 100)
    activity(tmp_path, ledger, "candidate", 100, 1, arm="candidate")
    ledger["cases"]["reuse"]["candidate"]["owner_acceptance"] = acceptance
    report = effort.assess(ledger, tmp_path)
    assert report["finite_comparisons"]["USD"]["status"] == "supported_within_declared_scope"
    assert report["status"] == status


def test_false_acceptance_cannot_win_with_lower_cost(ledger, tmp_path):
    activity(tmp_path, ledger, "base", 0, 100)
    ledger["cases"]["reuse"]["expected"] = "reject"
    ledger["cases"]["reuse"]["baseline"]["decision"] = "reject"
    report = effort.assess(ledger, tmp_path)
    assert report["status"] == "contradicted"
    assert report["finite_comparisons"]["USD"]["candidate_quality"]["false_acceptance_cases"] == [
        "reuse"
    ]


def test_same_wrong_decision_in_both_arms_is_not_matched_quality(ledger, tmp_path):
    ledger["cases"]["reuse"]["expected"] = "reject"
    report = effort.assess(ledger, tmp_path)
    assert not report["finite_comparisons"]["USD"]["quality_matched"]
    assert report["status"] == "contradicted"


@pytest.mark.parametrize("value", [True, -1, float("inf"), float("nan"), "0"])
def test_invalid_charges_are_rejected(ledger, tmp_path, value):
    ledger["coverage"]["candidate"]["review"]["charges_usd"]["provider"] = measured(value)
    with pytest.raises(ValueError):
        effort.assess(ledger, tmp_path)


def test_receiptless_zero_and_unexplained_unknown_are_invalid(ledger, tmp_path):
    item = ledger["coverage"]["candidate"]["review"]["charges_usd"]["provider"]
    item["reference"] = ""
    with pytest.raises(ValueError):
        effort.assess(ledger, tmp_path)
    item["value"] = None
    with pytest.raises(ValueError):
        effort.assess(ledger, tmp_path)


@pytest.mark.parametrize("change", ["clock", "identity", "extra", "partial_json", "duplicate_key"])
def test_corrupt_activity_is_not_silently_dropped(ledger, tmp_path, change):
    path = activity(tmp_path, ledger, "one", 0, 10)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if change == "clock":
        rows[1]["ns"] += 10_000_000_000
    elif change == "identity":
        rows[1]["id"] = "different"
    elif change == "extra":
        rows.append(rows[-1])
    elif change == "partial_json":
        path.write_text(path.read_text()[:-5])
    else:
        path.write_text(
            path.read_text().replace('"event": "start"', '"event":"stop","event":"start"')
        )
    if change in ("clock", "identity", "extra"):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError):
        effort.assess(ledger, tmp_path)


def test_unassigned_case_and_missing_required_categories_fail(ledger, tmp_path):
    activity(tmp_path, ledger, "one", 0, 10, case="unassigned")
    with pytest.raises(ValueError, match="unassigned"):
        effort.assess(ledger, tmp_path)
    ledger["activity_files"] = []
    (tmp_path / "activities/one.jsonl").unlink()
    del ledger["coverage"]["shared"]["adoption"]
    with pytest.raises(ValueError, match="Required fields"):
        effort.assess(ledger, tmp_path)


def test_symlink_activity_and_escape_are_rejected(ledger, tmp_path):
    path = activity(tmp_path, ledger, "one", 0, 10)
    (tmp_path / "activities/alias.jsonl").symlink_to(path)
    with pytest.raises(ValueError, match="symlink"):
        effort.assess(ledger, tmp_path)
    (tmp_path / "activities/alias.jsonl").unlink()
    ledger["activity_files"] = ["../elsewhere.jsonl"]
    with pytest.raises(ValueError, match="inside"):
        effort.assess(ledger, tmp_path)


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize("input_text,exit_code", [("\n", 0), ("", 1)])
def test_interactive_timer_retains_complete_or_interrupted_prefix(
    monkeypatch, tmp_path, input_text, exit_code
):
    monkeypatch.setattr(effort.sys, "stdin", Terminal(input_text))
    path = tmp_path / "one.jsonl"
    assert (
        effort.track(
            path, actor="owner", arm="baseline", case="initial", phase="review", reference="test"
        )
        == exit_code
    )
    _record, begin, end, complete = effort.read_activity(path.read_bytes())
    assert end >= begin
    assert complete == (exit_code == 0)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        effort.track(
            path, actor="owner", arm="baseline", case="initial", phase="review", reference="test"
        )
    assert path.read_bytes() == before


def test_hard_exit_keeps_start_prefix_and_noninteractive_invocation_is_rejected(
    monkeypatch, tmp_path
):
    class ExitTerminal(Terminal):
        def readline(self):
            assert len(path.read_text().splitlines()) == 1
            raise SystemExit(9)

    path = tmp_path / "one.jsonl"
    monkeypatch.setattr(effort.sys, "stdin", ExitTerminal())
    with pytest.raises(SystemExit):
        effort.track(
            path, actor="owner", arm="candidate", case="initial", phase="review", reference="test"
        )
    assert effort.read_activity(path.read_bytes())[2:] == (None, False)
    monkeypatch.setattr(effort.sys, "stdin", io.StringIO("\n"))
    with pytest.raises(ValueError, match="terminal"):
        effort.track(
            tmp_path / "other.jsonl",
            actor="owner",
            arm="candidate",
            case="initial",
            phase="review",
            reference="test",
        )
    assert not (tmp_path / "other.jsonl").exists()


def test_cli_hashes_inputs_and_does_not_run_owner_code(ledger, tmp_path):
    path = activity(tmp_path, ledger, "one", 0, 10)
    manifest = tmp_path / "ledger.json"
    manifest.write_text(json.dumps(ledger))
    result = subprocess.run(
        [sys.executable, str(PACKAGE / "effort.py"), "assess", str(manifest)],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert (
        report["activity_sha256"][str(path.relative_to(tmp_path))]
        == effort.hashlib.sha256(path.read_bytes()).hexdigest()
    )
    assert report["ledger_sha256"] == effort.hashlib.sha256(manifest.read_bytes()).hexdigest()
    manifest.write_text('{"schema": "one", "schema": "two"}')
    failed = subprocess.run(
        [sys.executable, str(PACKAGE / "effort.py"), "assess", str(manifest)],
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 2
    assert json.loads(failed.stderr)["status"] == "invalid"


def test_prepared_ledger_never_treats_absent_work_as_measured_zero(tmp_path):
    document = effort.prepared_ledger("planned initial and reuse", "planned protocol")
    report = effort.assess(document, tmp_path)
    assert report["status"] == "unresolved"
    assert report["finite_comparisons"] == {}
    assert len(report["incomplete_activity_or_coverage"]) == 48
    assert all(
        value is None
        for value in report["baseline_minus_candidate_owner_seconds_by_phase"].values()
    )
    for pair in report["phase_ledgers"].values():
        for arm in pair.values():
            assert all(item["value"] is None for item in arm["phases"].values())


def test_cost_shift_into_engineering_and_provider_charges_is_visible(ledger, tmp_path):
    activity(tmp_path, ledger, "base", 0, 100)
    activity(tmp_path, ledger, "candidate", 100, 10, arm="candidate")
    activity(tmp_path, ledger, "engineering", 0, 80, arm="candidate", actor="builder")
    ledger["coverage"]["candidate"]["review"]["charges_usd"]["provider"] = measured(30)
    report = effort.assess(ledger, tmp_path)
    assert totals(report, "owner_active_seconds") == {"baseline": 100, "candidate": 10}
    assert totals(report) == {"baseline": 100, "candidate": 120}
    assert report["status"] == "contradicted"


def test_process_kill_keeps_durable_open_prefix(tmp_path):
    pty = pytest.importorskip("pty")
    master, slave = pty.openpty()
    path = tmp_path / "killed.jsonl"
    process = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                str(PACKAGE / "effort.py"),
                "track",
                str(path),
                "--actor",
                "owner",
                "--arm",
                "candidate",
                "--case",
                "initial",
                "--phase",
                "review",
                "--reference",
                "synthetic termination control",
            ],
            stdin=slave,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        ready, _, _ = select.select([process.stdout], [], [], 10)
        assert ready, "Timer did not publish its durable-start notification"
        assert b"Active human interval started" in process.stdout.readline()
        process.kill()
        process.communicate(timeout=5)
        assert process.returncode < 0
        assert effort.read_activity(path.read_bytes())[2:] == (None, False)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        os.close(slave)
        os.close(master)
