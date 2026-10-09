"""The prospective decision-quality scorer: declarations against terminal references.

Controls cover a supported acceptance, an independently contradicted scoped acceptance,
unsupported acceptances (unresolved and invalid), a missing and a corrupt reference, a
correct abstention, adjudicable missed corrections (own and paired reference), an
all-abstain arm, zero denominators, a missing assigned case, a candidate mismatch,
ambiguous and changed declarations, retries, unverified ordering and partial costs.
Arithmetic is checked against hand-computed values. The historical v1 scores of the two
real ledgers must reproduce byte for byte, and the prospective table from those ledgers
must read as retrospective.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nisayon.evaluation.prospective import (
    BLOCKING as BLOCKING_CODES,
)
from nisayon.evaluation.prospective import (
    CLAIM,
    clopper_pearson,
    render_prospective,
    score_prospective,
    score_prospective_file,
)
from nisayon.evaluation.prospective_fixtures import (
    PROSPECTIVE_SCENARIOS,
    SPEC,
    prospective_ledger,
    write_prospective_ledger,
)
from nisayon.evaluation.scoring import score_file
from nisayon.evaluation.scoring_fixtures import fair_ledger, write_ledger

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "docs/experiments/results"
AUDIT = REPO / "docs/evaluation/results/audit-2026-09-18"
KEYS = {
    "N": "assigned_cases",
    "D": "declared_acceptances",
    "C": "confirmed_correct",
    "F": "contradicted",
    "U": "unsupported",
    "K": "unknown",
    "product": "product_accepted",
    "prospective": "prospective_trials",
}
REFUSALS = {
    "correct": "correct_refusal",
    "missed": "missed_correct_opportunity",
    "unadjudicated": "refusal_unadjudicated",
}


def _write(scenario, tmp_path: Path) -> Path:
    path = write_prospective_ledger(scenario.build(), tmp_path)
    if scenario.after_write is not None:
        scenario.after_write(tmp_path)
    return path


@pytest.mark.parametrize("item", PROSPECTIVE_SCENARIOS, ids=[s.name for s in PROSPECTIVE_SCENARIOS])
def test_prospective_scenarios(item, tmp_path):
    path = _write(item, tmp_path)
    report = score_prospective_file(path, tmp_path)
    codes = {f["code"] for f in report["findings"]}
    assert report["fair"] is item.expected_fair, report["findings"]
    assert set(item.expected_codes) <= codes, codes
    for arm_id, expected in item.expected_arms.items():
        arm = report["arms"][arm_id]
        for key, value in expected.items():
            if key in KEYS:
                assert arm[KEYS[key]] == value, (arm_id, key, arm)
            elif key in REFUSALS:
                assert arm["refusals"][REFUSALS[key]] == value, (arm_id, key, arm["refusals"])
            else:
                assert arm["non_acceptance_states"][key] == value, (arm_id, key, arm)
        assert arm["declared_acceptances"] == (
            arm["confirmed_correct"] + arm["contradicted"] + arm["unsupported"] + arm["unknown"]
        )
        assert arm["assigned_cases"] == arm["declared_acceptances"] + sum(
            arm["non_acceptance_states"].values()
        )
    assert render_prospective(report).startswith("Prospective decision-quality report")


def test_declaration_for_another_arm_is_a_mismatch(tmp_path):
    ledger = prospective_ledger()
    path = write_prospective_ledger(ledger, tmp_path)
    record = tmp_path / "declarations/A-D01-gripper-sign/declaration.json"
    data = json.loads(record.read_text())
    data["assignment"]["arm"] = "B"
    raw = (json.dumps(data, indent=2) + "\n").encode()
    record.write_bytes(raw)
    import hashlib

    ledger_data = json.loads(path.read_text())
    for trial in ledger_data["trials"]:
        if trial["arm"] == "A" and trial["case_id"].startswith("D01"):
            trial["declaration"]["sha256"] = hashlib.sha256(raw).hexdigest()
            trial["terminal_start"] = None
            trial["terminal_result"] = None
    report = score_prospective(ledger_data, tmp_path)
    assert report["fair"] is False
    assert any(
        f["code"] == "declaration_mismatch" and "arm 'B'" in f["detail"] for f in report["findings"]
    )


def test_receipt_missing_in_a_v2_ledger_blocks(tmp_path):
    ledger = prospective_ledger()
    del ledger["trials"][0][SPEC]
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    assert report["fair"] is False
    assert "declaration_missing" in {f["code"] for f in report["findings"]}
    assert report["arms"]["A"]["non_acceptance_states"]["no_declaration"] == 1


def test_arithmetic_against_hand_computed_values(tmp_path):
    # Arm A on five cases: three claims (two supported, one contradicted), one refusal
    # adjudicated correct (own candidate rejected), one unresolved case with no reference.
    ledger = prospective_ledger()
    ledger["cases"].append(
        {
            "id": "D05-recurrent-carry",
            "family": "reset",
            "intended_class": "repairable",
            "budget": {"max_rollouts": 64, "max_wall_seconds": 1800, "max_final_candidates": 1},
            "frozen": {"case": "D05-recurrent-carry"},
        }
    )
    from nisayon.evaluation.prospective_fixtures import REJECTED_PROGRESS, _default_spec
    from nisayon.evaluation.schema import digest_of
    from nisayon.evaluation.scoring_fixtures import trial

    candidate = digest_of({"repair": "reset"})
    for arm, claimed in (("A", True), ("B", False)):
        t = trial(
            arm,
            "D05-recurrent-carry",
            "confirmed" if claimed else "rejected",
            candidate=candidate,
            decision="rejected",
            rollouts=4,
            confirmation_rollouts=67,
            start=60 + (0 if arm == "A" else 10),
            claimed=claimed,
        )
        t["received_frozen_sha256"] = digest_of({"case": "D05-recurrent-carry"})
        t["decision"]["reasons"] = REJECTED_PROGRESS
        t[SPEC] = _default_spec(t)
        if not claimed:
            t[SPEC].update(disposition="refuse", candidate=None)
        ledger["trials"].append(t)
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    a, b = report["arms"]["A"], report["arms"]["B"]
    # A: N=5, claims D01, D07, D05 → C=2, F=1; refusals D08 (invalid control) correct, D10 unadj.
    assert (
        a["assigned_cases"],
        a["declared_acceptances"],
        a["confirmed_correct"],
        a["contradicted"],
    ) == (5, 3, 2, 1)
    assert a["rates"]["F_over_N"] == pytest.approx(1 / 5)
    assert a["rates"]["F_over_D"] == pytest.approx(1 / 3)
    assert a["rates"]["C_over_N"] == pytest.approx(2 / 5)
    assert a["rates"]["D_over_N"] == pytest.approx(3 / 5)
    assert a["rates"]["reference_coverage_of_claims"] == pytest.approx(1.0)
    assert a["rates"]["F_over_C_supplementary"] == pytest.approx(1 / 2)
    assert a["rates"]["contradicted_upper_bound_if_unadjudicated_wrong"] == pytest.approx(1 / 5)
    assert a["refusals"] == {
        "correct_refusal": 1,
        "missed_correct_opportunity": 0,
        "refusal_unadjudicated": 1,
    }
    assert a["contradiction_codes"] == {"progress_lost": 1}
    # B: refuses D05 and the reference rejects it: a correct refusal, not a contradicted claim.
    assert (b["declared_acceptances"], b["contradicted"], b["refusals"]["correct_refusal"]) == (
        2,
        0,
        2,
    )
    # Cost per correct claim divides every trial's known cost by C, failures included.
    total = sum(t["costs"]["simulator_wall"] for t in report["trials"] if t["arm"] == "A")
    assert a["costs"]["per_correct_claim"]["simulator_wall"]["value"] == pytest.approx(total / 2)
    assert a["costs"]["per_declared_acceptance"]["simulator_wall"]["value"] == pytest.approx(
        total / 3
    )
    # D05's product acceptance fails closed although the arm claimed it.
    d05 = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D05"))
    assert d05["claim_category"] == "contradicted" and d05["product_accepted"] is False
    assert a["v1_false_acceptances"] == 1, "the v1 diagnostic still counts the claim"


def test_zero_denominators_are_undefined_not_zero(tmp_path):
    ledger = next(s for s in PROSPECTIVE_SCENARIOS if s.name == "all_abstain").build()
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    rates = report["arms"]["A"]["rates"]
    assert rates["F_over_D"] is None and rates["F_over_C_supplementary"] is None
    assert rates["reference_coverage_of_claims"] is None
    assert rates["F_over_N"] == 0.0 and rates["C_over_N"] == 0.0 and rates["D_over_N"] == 0.0
    assert rates["F_over_N_exact_95"] == (0.0, pytest.approx(0.6024, abs=1e-3))  # 0/4
    costs = report["arms"]["A"]["costs"]
    assert costs["per_correct_claim"]["simulator_wall"]["value"] is None
    assert costs["per_correct_claim"]["simulator_wall"]["missing"] == "no confirmed correct claim"
    ledger = next(s for s in PROSPECTIVE_SCENARIOS if s.name == "zero_confirmed_claims").build()
    report = score_prospective_file(
        write_prospective_ledger(ledger, tmp_path / "z"), tmp_path / "z"
    )
    rates = report["arms"]["A"]["rates"]
    assert rates["F_over_D"] == 1.0 and rates["F_over_C_supplementary"] is None
    assert report["arms"]["A"]["costs"]["per_correct_claim"]["simulator_wall"]["value"] is None


def test_clopper_pearson_against_known_values():
    lower, upper = clopper_pearson(0, 10)
    assert lower == 0.0 and upper == pytest.approx(1 - 0.025 ** (1 / 10), abs=1e-6)
    lower, upper = clopper_pearson(10, 10)
    assert upper == 1.0 and lower == pytest.approx(0.025 ** (1 / 10), abs=1e-6)
    lower, upper = clopper_pearson(6, 10)
    assert (lower, upper) == (pytest.approx(0.2624, abs=5e-4), pytest.approx(0.8784, abs=5e-4))
    assert clopper_pearson(0, 0) is None and clopper_pearson(3, 2) is None


def test_v1_score_of_a_v2_ledger_is_unchanged_in_meaning(tmp_path):
    ledger = prospective_ledger()
    path = write_prospective_ledger(ledger, tmp_path)
    v2 = score_file(path, tmp_path)
    v1 = score_file(write_ledger(fair_ledger(), tmp_path / "v1"), tmp_path / "v1")
    assert v2["fair"] and v1["fair"]
    assert v2["arms"]["A"]["outcomes"] == v1["arms"]["A"]["outcomes"]
    assert v2["arms"]["B"]["false_acceptances"] == v1["arms"]["B"]["false_acceptances"] == 0


@pytest.mark.parametrize(
    "suite",
    ["development-ablation-001", "bounded-agent-comparison-001"],
)
def test_historical_v1_scores_reproduce_byte_for_byte(suite):
    ledger = RESULTS / suite / "comparison-ledger.json"
    retained = AUDIT / f"{suite}-committed-copy.score.json"
    if not (ledger.is_file() and retained.is_file()):
        pytest.skip("retained records absent")
    expected = json.loads(retained.read_text())
    score = score_file(ledger, ledger.parent)
    if suite == "development-ablation-001":
        # Retained at r2 (1e9031b), before the per-arm ``budget`` field arrived with the
        # equal-budget check in 6e112c4; the pre-refactor scorer at 6f29489 produces the
        # same output as this one, with that key present.
        for arm in score["arms"].values():
            assert arm.pop("budget") is None
    assert score == expected


def test_real_ledgers_read_as_retrospective_tables():
    ledger = RESULTS / "development-ablation-001/comparison-ledger.json"
    if not ledger.is_file():
        pytest.skip("retained record absent")
    report = score_prospective_file(ledger, ledger.parent)
    assert report["fair"] is True
    assert report["declarations"]["reading"] == "retrospective"
    assert report["declarations"]["prospective_trials"] == 0
    for arm_id in ("A", "B"):
        arm = report["arms"][arm_id]
        assert (arm["assigned_cases"], arm["declared_acceptances"], arm["confirmed_correct"]) == (
            10,
            6,
            6,
        )
        assert arm["contradicted"] == arm["unsupported"] == arm["unknown"] == 0
        assert arm["non_acceptance_states"]["refuse"] == 1  # D05: executed, not claimed
        assert arm["non_acceptance_states"]["unsupported_capability"] == 1  # D06
        assert arm["non_acceptance_states"]["invalid_experiment"] == 1  # D08
        assert arm["non_acceptance_states"]["unresolved"] == 1  # D10
        assert arm["refusals"] == {
            "correct_refusal": 3,
            "missed_correct_opportunity": 0,
            "refusal_unadjudicated": 1,
        }
        assert arm["product_accepted"] == arm["v1_confirmed"] == 6
        assert arm["costs"]["cumulative_resource_time_scope"].startswith("own_trial_wall")
    d05 = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D05"))
    assert (
        d05["refusal"]["adjudication"] == "correct_refusal"
        and "rejected" in d05["refusal"]["source"]
    )
    assert d05["reference"]["codes"] == ["progress_lost"]
    bounded = RESULTS / "bounded-agent-comparison-001/comparison-ledger.json"
    report = score_prospective_file(bounded, bounded.parent)
    assert report["fair"] and all(
        (a["assigned_cases"], a["declared_acceptances"], a["confirmed_correct"]) == (3, 3, 3)
        for a in report["arms"].values()
    )


def test_derived_control_from_real_records_counts_only_real_contradiction(tmp_path):
    """A labelled derived control: arm A's declarations are rewritten on the real ledger.

    A claims D05 (its real terminal decision is rejected on progress_lost) and abstains on
    D07 (its real terminal decision is accepted). The contradiction and the missed
    opportunity are read from real bytes; the declarations are synthetic and say so.
    """
    from nisayon.evaluation.prospective_fixtures import build_derived_control

    ledger = RESULTS / "development-ablation-001/comparison-ledger.json"
    if not ledger.is_file():
        pytest.skip("retained record absent")
    derived = build_derived_control(ledger, tmp_path)
    report = score_prospective(json.loads(derived.read_text()), tmp_path)
    a, b = report["arms"]["A"], report["arms"]["B"]
    assert (a["declared_acceptances"], a["confirmed_correct"], a["contradicted"]) == (6, 5, 1)
    assert a["refusals"]["missed_correct_opportunity"] == 1
    assert a["product_accepted"] == 5 and b["product_accepted"] == 6
    assert (b["declared_acceptances"], b["confirmed_correct"], b["contradicted"]) == (6, 6, 0)
    assert report["declarations"]["prospective_trials"] == 0
    assert "declaration_order_unverified" in {f["code"] for f in report["findings"]}
    d05 = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D05"))
    assert d05["claim_category"] == "contradicted" and d05["reference"]["codes"] == [
        "progress_lost"
    ]
    assert d05["declaration"]["evidence_scope"] == "retained_development_demonstration"


def test_prospective_command(tmp_path):
    path = write_prospective_ledger(prospective_ledger(), tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "prospective",
            str(path),
            "--root",
            str(tmp_path),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["fair"] is True
    text = subprocess.run(
        [sys.executable, "-m", "nisayon.evaluation", "prospective", str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert text.stdout.startswith("Prospective decision-quality report: fair")
    assert CLAIM in text.stdout


PACKET = Path("/Users/danielwahnich/workspace/nisayon-codex/artifacts/retained-declarations-002")
SUITE = RESULTS / "development-ablation-001"


@pytest.mark.skipif(
    not ((PACKET / "packet.json").is_file() and (SUITE / "comparison-ledger.json").is_file()),
    reason="the execution lane's declaration packet or the suite is absent",
)
def test_execution_declaration_packet_scores_against_the_committed_suite():
    """Codex's retained-declaration packet: receipts under the packet, records under the suite.

    The plan claims the seven retained diagnostic candidates per arm, including D05, whose
    terminal decision is rejected, and refuses D06 and D08. Nothing is prospective: the
    receipts carry the demonstration scope and postdate the decisions they are bound to.
    """
    from nisayon.evaluation.prospective import score_prospective_packet

    report = score_prospective_packet(PACKET, SUITE)
    assert report["fair"] is True, [f for f in report["findings"] if f["code"] in BLOCKING_CODES]
    assert report["declarations"]["reading"] == "development_demonstration"
    assert report["declarations"]["prospective_trials"] == 0
    assert report["packet"]["new_simulator_executions"] == 0
    assert report["packet"]["new_model_calls"] == 0
    assert report["packet"]["missing_rows"] == []
    codes = {f["code"] for f in report["findings"]}
    assert "declaration_mismatch" not in codes and "declaration_unverifiable" not in codes
    assert "declaration_timestamp_after_reference" in codes  # receipts postdate the decisions
    for arm_id in ("A", "B"):
        arm = report["arms"][arm_id]
        assert (arm["assigned_cases"], arm["declared_acceptances"]) == (10, 7)
        assert (arm["confirmed_correct"], arm["contradicted"]) == (6, 1)
        assert arm["unsupported"] == arm["unknown"] == 0
        assert arm["contradiction_codes"] == {"progress_lost": 1}
        assert arm["refusals"] == {
            "correct_refusal": 2,
            "missed_correct_opportunity": 0,
            "refusal_unadjudicated": 1,
        }
        assert arm["product_accepted"] == arm["v1_confirmed"] == 6
        assert arm["v1_false_acceptances"] == 0, "the v1 diagnostic never saw these receipts"
    d05 = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D05"))
    assert d05["claim_category"] == "contradicted" and d05["ordering"]["verified"] is True
    assert d05["declaration"]["evidence_scope"] == "retained_development_demonstration"
    assert d05["product_accepted"] is False


def _minimal_packet(folder: Path, *, drop_row: bool = False, foreign_row: bool = False) -> Path:
    """A two-assignment packet in the execution lane's layout, built from the fixtures."""
    import hashlib

    from nisayon.evaluation.prospective_fixtures import (
        bind_result,
        configuration_for,
        receipt,
        terminal_records,
    )

    ledger = fair_ledger()
    ledger["cases"] = [c for c in ledger["cases"] if c["id"].startswith("D01")]
    ledger["trials"] = [t for t in ledger["trials"] if t["case_id"].startswith("D01")]
    write_ledger(ledger, folder / "suite")
    source = json.loads((folder / "suite/ledger.json").read_text())
    (folder / "packet/sources").mkdir(parents=True)

    def put(relative: str, data: dict) -> dict:
        raw = (json.dumps(data, indent=2) + "\n").encode()
        target = folder / "packet" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}

    source_ref = put("sources/comparison-ledger.json", source)
    assigned = [{"case_id": "D01-gripper-sign", "arm": arm} for arm in ("A", "B")]
    freeze_ref = put(
        "freeze.json",
        {
            "schema": "nisayon.retained-declaration-freeze.v1",
            "id": "packet-fixture-001",
            "source_ledger": source_ref,
            "source_locator": str(folder / "suite"),
            "assigned": assigned,
        },
    )
    rows = []
    for trial in source["trials"]:
        if drop_row and trial["arm"] == "B":
            continue
        spec = {
            "disposition": "claim_acceptance",
            "candidate": configuration_for(trial["decision"]["candidate_digest"]),
            "scope": "retained_development_demonstration",
            "minute": None,
            "reason": "packet fixture",
            "terminal": True,
            "additional": [],
        }
        record = receipt({"suite": {"id": "packet-fixture-001"}}, trial, spec)
        base = f"D01-gripper-sign/{trial['arm']}/declaration"
        declaration = put(f"{base}/declaration.json", record)
        trial["declaration"] = declaration
        # The packet keeps a byte-identical copy of the terminal decision, as the execution
        # lane's packet does; the result names it by digest.
        decision_bytes = (folder / "suite" / trial["decision"]["path"]).read_bytes()
        copy_path = folder / "packet" / f"D01-gripper-sign/{trial['arm']}/terminal/decision.json"
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        copy_path.write_bytes(decision_bytes)
        start_record, result_record = terminal_records(
            trial,
            record,
            evidence=[
                {
                    "path": f"D01-gripper-sign/{trial['arm']}/terminal/decision.json",
                    "sha256": hashlib.sha256(decision_bytes).hexdigest(),
                }
            ],
            ended=trial["timeline"]["ended_at"],
        )
        start = put(f"{base}/terminal-start.json", start_record)
        result = put(f"{base}/terminal-result.json", bind_result(result_record, start))
        rows.append(
            {
                "case_id": "D01-gripper-sign" if not foreign_row else "D99-unknown",
                "arm": trial["arm"],
                "declaration": declaration,
                "terminal_start": start,
                "terminal_result": result,
                "historical_trial": trial,
                "retained_decision": "accepted",
            }
        )
    put(
        "packet.json",
        {
            "schema": "nisayon.retained-declaration-packet.v1",
            "freeze": freeze_ref,
            "evidence_scope": "retained_development_demonstration",
            "rows": rows,
            "new_model_calls": 0,
            "new_simulator_executions": 0,
        },
    )
    return folder / "packet"


def test_packet_adapter_builds_a_v2_ledger_and_names_absent_rows(tmp_path):
    from nisayon.evaluation.prospective import packet_ledger, score_prospective_packet
    from nisayon.evaluation.schema import Malformed

    packet = _minimal_packet(tmp_path)
    ledger = packet_ledger(packet)
    assert ledger["schema"] == "nisayon.comparison.v2"
    assert ledger["suite"]["declaration_suite_id"] == "packet-fixture-001"
    assert {t["arm"] for t in ledger["trials"]} == {"A", "B"}
    report = score_prospective_packet(packet, tmp_path / "suite")
    assert report["fair"] is True, report["findings"]
    assert report["arms"]["A"]["confirmed_correct"] == 1
    assert report["declarations"]["reading"] == "development_demonstration"
    dropped = _minimal_packet(tmp_path / "dropped", drop_row=True)
    ledger = packet_ledger(dropped)
    assert ledger["execution_complete"] is False
    assert ledger["packet_missing_rows"] == [{"case_id": "D01-gripper-sign", "arm": "B"}]
    report = score_prospective_packet(dropped, tmp_path / "dropped/suite")
    assert report["arms"]["B"]["non_acceptance_states"]["not_attempted"] == 1
    assert "trial_missing" in {f["code"] for f in report["findings"]}
    foreign = _minimal_packet(tmp_path / "foreign", foreign_row=True)
    with pytest.raises(Malformed):
        packet_ledger(foreign)
    tampered = _minimal_packet(tmp_path / "tampered")
    (tampered / "sources/comparison-ledger.json").write_text("{}")
    with pytest.raises(Malformed):
        packet_ledger(tampered)


def test_claim_over_budget_is_classified_but_not_product_accepted(tmp_path):
    ledger = prospective_ledger()
    trial = next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D07"))
    trial["diagnostic_rollouts"] = 99  # over the case budget of 64
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D07"))
    assert entry["status"] == "timeout" and entry["over_budget"] is True
    assert entry["claim_category"] == "supported" and entry["product_accepted"] is False
    arm = report["arms"]["A"]
    assert (arm["declared_acceptances"], arm["confirmed_correct"]) == (2, 2)
    assert arm["product_accepted"] == 1 == arm["v1_confirmed"]
    assert "claim_over_budget" in {f["code"] for f in report["findings"]}
    assert "budget_exceeded" in {f["code"] for f in report["findings"]}


def test_unknown_claim_arithmetic_against_hand_computed_values(tmp_path):
    # Arm B: claims D01 (supported), D07 (supported) and D10 with no terminal decision
    # (unknown); refuses D08. N = 4, D = 3, C = 2, F = 0, U = 0, K = 1.
    ledger = prospective_ledger()
    trial = next(t for t in ledger["trials"] if t["arm"] == "B" and t["case_id"].startswith("D10"))
    trial["arm_claimed_acceptance"] = True
    trial["decision"] = None
    from nisayon.evaluation.prospective_fixtures import configuration_for

    trial[SPEC].update(
        disposition=CLAIM,
        candidate=configuration_for(trial["proposals"][-1]["candidate_digest"]),
        terminal=False,
    )
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    b = report["arms"]["B"]
    assert (b["assigned_cases"], b["declared_acceptances"]) == (4, 3)
    assert (b["confirmed_correct"], b["contradicted"], b["unsupported"], b["unknown"]) == (
        2,
        0,
        0,
        1,
    )
    rates = b["rates"]
    assert rates["D_over_N"] == pytest.approx(3 / 4)
    assert rates["C_over_N"] == pytest.approx(2 / 4)
    assert rates["F_over_N"] == 0.0 and rates["F_over_D"] == 0.0
    assert rates["K_over_D"] == pytest.approx(1 / 3)
    assert rates["reference_coverage_of_claims"] == pytest.approx(2 / 3)
    assert rates["contradicted_upper_bound_if_unadjudicated_wrong"] == pytest.approx(1 / 4)
    assert rates["F_over_C_supplementary"] == 0.0
    assert b["product_accepted"] == 2, "an unknown claim is never product-accepted"
    assert "reference_missing" in {f["code"] for f in report["findings"]}


BINDING_VARIANTS = (
    "commentary_digests",
    "replaced_link_digest_elsewhere",
    "wrong_schema",
    "wrong_arm",
    "missing_terminal_evidence",
)


@pytest.mark.parametrize("variant", BINDING_VARIANTS)
def test_terminal_chain_is_bound_field_by_field_not_by_digest_anywhere(variant, tmp_path):
    """The 19 September binding probe through the public scorer and CLI.

    At bfae56d the first four variants scored fair with the tampered trial counted as
    prospective (retained: results/audit-2026-09-19/binding-probe-001/before-summary.json).
    A digest in a comment, another field or another role must not satisfy a link.
    """
    from nisayon.evaluation.prospective_fixtures import binding_probe_control

    path = binding_probe_control(tmp_path, variant=variant)
    report = score_prospective_file(path, tmp_path)
    assert report["fair"] is False
    codes = {f["code"] for f in report["findings"]}
    assert "terminal_binding_unverifiable" in codes
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    assert entry["prospective"] is False and entry["ordering"]["verified"] is False
    # The reference outcome and the claim's correctness are untouched by the broken chain;
    # the trial is study-ineligible and the report says its totals are not usable.
    assert entry["reference"]["decision"] == "accepted"
    assert entry["claim_category"] == "supported"
    assert entry["eligibility"]["study"] is False
    assert "terminal_binding_unverifiable" in entry["eligibility"]["study_blockers"]
    assert entry["eligibility"]["product"] == "eligible" and entry["product_accepted"] is True
    assert report["eligibility"]["usable_as_study_result"] is False
    assert report["arms"]["A"]["usable_as_study_result"] is False
    assert report["arms"]["A"]["study_eligible_trials"] < report["arms"]["A"]["assigned_cases"]
    # The other trials keep their prospective standing; the tampered one loses only its own.
    assert report["declarations"]["prospective_trials"] == 5
    text = render_prospective(report)
    assert (
        "NOT a usable study result" in text
        and "study-ineligible[terminal_binding_unverifiable]" in text
    )
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "prospective",
            str(path),
            "--root",
            str(tmp_path),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert cli.returncode == 1, cli.stderr
    assert json.loads(cli.stdout)["fair"] is False


def test_damaged_declaration_stays_assigned_and_counts_do_not_improve(tmp_path):
    path = write_prospective_ledger(prospective_ledger(), tmp_path)
    receipt_path = tmp_path / "declarations/A-D01-gripper-sign/declaration.json"
    receipt_path.write_text(receipt_path.read_text() + " ")  # bytes no longer match
    report = score_prospective_file(path, tmp_path)
    assert report["fair"] is False
    a = report["arms"]["A"]
    assert a["assigned_cases"] == 4, "the damaged assignment stays in N"
    assert a["declared_acceptances"] == 1 and a["confirmed_correct"] == 1
    assert a["non_acceptance_states"]["declaration_unusable"] == 1
    assert a["non_acceptance_states"]["no_declaration"] == 0
    assert a["rates"]["C_over_N"] == pytest.approx(1 / 4), (
        "C/N does not rise when a claim is damaged"
    )
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    assert entry["declaration"] is None and entry["declaration_problem"].startswith("unverifiable")
    assert entry["non_acceptance_state"] == "declaration_unusable"
    assert entry["reference"]["decision"] == "accepted", "the verified reference is retained"
    assert entry["claim_category"] is None and entry["product_accepted"] is False
    assert entry["eligibility"] == {
        "study": False,
        "study_blockers": ["declaration_unverifiable"],
        "product": "not_accepted",
        "product_blockers": [],
    }


def test_mismatched_receipt_is_unusable_not_someone_elses_claim(tmp_path):
    from nisayon.evaluation.prospective_fixtures import binding_probe_control

    path = binding_probe_control(tmp_path, variant="wrong_arm")
    # Also make the declaration itself claim arm B: the receipt is not this trial's.
    receipt_path = tmp_path / "declarations/A-D01-gripper-sign/declaration.json"
    record = json.loads(receipt_path.read_text())
    record["assignment"]["arm"] = "B"
    raw = (json.dumps(record, indent=2) + "\n").encode()
    receipt_path.write_bytes(raw)
    import hashlib

    ledger = json.loads(path.read_text())
    trial = next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    trial["declaration"]["sha256"] = hashlib.sha256(raw).hexdigest()
    report = score_prospective(ledger, tmp_path)
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    assert entry["non_acceptance_state"] == "declaration_unusable"
    assert entry["unusable_declaration"]["disposition"] == "claim_acceptance"
    assert entry["claim_category"] is None
    assert "declaration_mismatch" in {f["code"] for f in report["findings"]}


def test_report_level_blockers_make_every_trial_study_ineligible(tmp_path):
    ledger = prospective_ledger()
    ledger["arms"][0].update(
        kind="agent",
        agent={"model": "x-1", "settings_sha256": "aa", "context_boundary": "isolated"},
    )
    ledger["arms"][1].update(
        kind="agent",
        agent={"model": "x-2", "settings_sha256": "bb", "context_boundary": "isolated"},
    )
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    assert (
        report["fair"] is False and "arms_not_matched" in report["eligibility"]["blocking_findings"]
    )
    assert all(t["eligibility"]["study"] is False for t in report["trials"])
    assert all(
        "report:arms_not_matched" in t["eligibility"]["study_blockers"] for t in report["trials"]
    )
    # Product eligibility of a verified accepted decision is unaffected by the mismatch.
    supported = [t for t in report["trials"] if t["claim_category"] == "supported"]
    assert supported and all(t["eligibility"]["product"] == "eligible" for t in supported)


@pytest.mark.skipif(
    not ((PACKET / "packet.json").is_file() and (SUITE / "comparison-ledger.json").is_file()),
    reason="the execution lane's declaration packet or the suite is absent",
)
def test_packet_costs_by_scope_match_the_execution_lane_export():
    """Independent cross-check: the scoped sums equal the committed costs.tsv row sums."""
    import csv
    import io

    from nisayon.evaluation.prospective import score_prospective_packet

    table = RESULTS / "retained-declarations-002/costs.tsv"
    if not table.is_file():
        pytest.skip("cost export absent")
    rows = list(csv.DictReader(io.StringIO(table.read_text()), delimiter="\t"))
    sums: dict = {}
    for row in rows:
        if row["scope"] == "new_processing":
            try:
                value = float(row["value"])
            except ValueError:
                continue
            key = (row["arm"], row["category"])
            sums[key] = round(sums.get(key, 0.0) + value, 9)
    shared = next(
        row
        for row in rows
        if row["scope"] == "historical_shared_preparation"
        and row["category"] == "recorded_command_wall"
    )
    report = score_prospective_packet(PACKET, SUITE)
    scopes = report["costs_by_scope"]
    new = scopes["new_processing"]
    for arm in ("A", "B"):
        nested = new["per_arm_nested"][arm]
        assert nested["terminal_read_wall_s"] == pytest.approx(sums[(arm, "terminal_read_wall")])
        assert nested["writer_attempt_wall_s"] == pytest.approx(sums[(arm, "writer_attempt_walls")])
        assert (
            nested["writer_attempts_unknown_cost"] == 0
            and nested["writer_attempts_incomplete"] == 0
        )
    assert new["packet_processing_wall_s"] == pytest.approx(
        sums[("shared", "packet_processing_wall")]
    )
    assert new["new_model_calls"] == 0 and new["new_simulator_executions"] == 0
    prep = scopes["historical_shared_preparation"]
    assert prep["bound"] is True
    assert prep["known_command_wall_sum_s"] == pytest.approx(float(shared["value"]))
    assert prep["summed_commands"] == 71 and prep["nested_not_added"] == 10
    assert scopes["evaluation_scoring"]["scoring_wall_s"] > 0
    unknown = {(u["scope"], u["category"]) for u in scopes["unknown"]}
    assert ("new_processing", "engineer_effort_s") in unknown
    assert ("historical_shared_preparation", "human_preparation_and_review") in unknown
    assert ("historical_trials", "engineer_time") in unknown
    # Historical per-arm resource time is untouched by the new scopes.
    assert report["arms"]["A"]["costs"]["cumulative_resource_time_s"] == pytest.approx(881.95364367)
    text = render_prospective(report)
    assert "shared preparation: 2534.406 s" in text and "never summed across scopes" in text


def test_costs_by_scope_on_a_plain_ledger_reads_the_bound_preparation_ledger(tmp_path):
    import hashlib

    ledger = prospective_ledger()
    prep = {
        "schema": "nisayon.execution.costs.v2",
        "known_command_wall_sum_s": 12.5,
        "summed_command_ids": ["a", "b"],
        "nested_not_added": [{"id": "c", "included_by": "a"}],
        "unmeasured_command_ids": [],
        "unmeasured": [
            {"category": "human_preparation_and_review", "unit": "s", "reason": "no tracker"}
        ],
        "amortization": "none",
    }
    raw = (json.dumps(prep) + "\n").encode()
    (tmp_path / "preparation-costs.json").write_bytes(raw)
    ledger["preparation_cost_ledger"] = {
        "path": "preparation-costs.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    report = score_prospective_file(write_prospective_ledger(ledger, tmp_path), tmp_path)
    scopes = report["costs_by_scope"]
    assert scopes["historical_shared_preparation"]["known_command_wall_sum_s"] == 12.5
    assert scopes["historical_shared_preparation"]["nested_not_added"] == 1
    assert scopes["new_processing"] is None, "no packet, no new processing scope"
    assert scopes["historical_trials"]["per_arm"]["A"]["agent_tokens"]["known_total"] is None
    assert scopes["historical_trials"]["per_arm"]["A"]["simulator_wall"][
        "known_total"
    ] == pytest.approx(report["arms"]["A"]["costs"]["cumulative_simulator_wall_s"])
    assert any(u["category"] == "human_preparation_and_review" for u in scopes["unknown"])
    (tmp_path / "preparation-costs.json").write_bytes(raw + b" ")
    report = score_prospective_file(tmp_path / "ledger.json", tmp_path)
    assert report["costs_by_scope"]["historical_shared_preparation"]["bound"] is False
    assert (
        "known_command_wall_sum_s" not in report["costs_by_scope"]["historical_shared_preparation"]
    )


# --- the required-field contract (19 September 2026, revision 3) ---------------------


@pytest.mark.parametrize(
    "variant",
    (
        "positive",
        *__import__(
            "nisayon.evaluation.prospective_fixtures", fromlist=["OMISSION_VARIANTS"]
        ).OMISSION_VARIANTS,
    ),
)
def test_required_field_omissions_are_rejected_on_the_public_path(variant, tmp_path):
    """The execution lane's six omissions: measured accepted at b626a97 (retained in
    results/audit-2026-09-19/required-fields-001/before-summary.json), rejected now."""
    from nisayon.evaluation.prospective_fixtures import required_field_omission_control

    path = required_field_omission_control(tmp_path, variant=variant)
    report = score_prospective_file(path, tmp_path)
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "prospective",
            str(path),
            "--root",
            str(tmp_path),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    cli_report = json.loads(cli.stdout)
    assert report["arms"]["A"]["assigned_cases"] == 4, "every assignment stays visible"
    if variant == "positive":
        assert report["fair"] is True and entry["prospective"] is True and cli.returncode == 0
        assert report["eligibility"]["usable_as_study_result"] is True
        return
    assert report["fair"] is False and cli.returncode == 1, (variant, report["findings"])
    assert entry["prospective"] is False
    assert report["eligibility"]["usable_as_study_result"] is False
    assert cli_report["eligibility"]["usable_as_study_result"] is False
    codes = {
        f["code"]
        for f in report["findings"]
        if f.get("case_id") == entry["case_id"] and f.get("arm") == "A"
    }
    if variant.startswith("declaration_"):
        assert "declaration_malformed" in codes
        assert entry["non_acceptance_state"] == "declaration_unusable"
        assert entry["claim_category"] is None and entry["product_accepted"] is False
        assert report["arms"]["A"]["declared_acceptances"] == 1, "D excludes the unusable claim"
    else:
        assert "terminal_binding_unverifiable" in codes
        assert entry["claim_category"] == "supported", "the bound reference outcome is untouched"
        assert entry["reference"]["decision"] == "accepted"
        assert entry["eligibility"]["product"] == "eligible"
    assert entry["eligibility"]["study"] is False
    text = render_prospective(report)
    assert "NOT a usable study result" in text
    assert cli_report["fair"] is False


@pytest.mark.parametrize(
    "item",
    __import__(
        "nisayon.evaluation.prospective_fixtures", fromlist=["CONTRACT_MUTATIONS"]
    ).CONTRACT_MUTATIONS,
    ids=[
        m[0]
        for m in __import__(
            "nisayon.evaluation.prospective_fixtures", fromlist=["CONTRACT_MUTATIONS"]
        ).CONTRACT_MUTATIONS
    ],
)
def test_contract_mutation_matrix(item, tmp_path):
    """Every required, conditional and nullable field of the three record versions, with
    absence, explicit null, type substitutes and semantic mismatches as distinct boundaries."""
    from nisayon.evaluation.prospective import REQUIRED_FIELD_TABLE
    from nisayon.evaluation.prospective_fixtures import contract_mutation_control

    name, record, mutate, expected_code, field = item
    assert any(row["record"] == record and row["field"] == field for row in REQUIRED_FIELD_TABLE), (
        "every mutation targets a documented table row"
    )
    path = contract_mutation_control(tmp_path, record=record, mutate=mutate)
    report = score_prospective_file(path, tmp_path)
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    codes = {
        f["code"]
        for f in report["findings"]
        if f.get("case_id") == entry["case_id"] and f.get("arm") == "A"
    }
    assert expected_code in codes, (
        name,
        sorted(codes),
        entry["ordering"]["how"],
        entry.get("declaration_problem"),
    )
    assert report["fair"] is False and entry["prospective"] is False
    assert report["eligibility"]["usable_as_study_result"] is False
    assert report["arms"]["A"]["assigned_cases"] == 4
    assert entry["reference"]["decision"] == "accepted", "the verified reference is never rewritten"
    if record == "declaration":
        assert entry["non_acceptance_state"] == "declaration_unusable"
        assert entry["claim_category"] is None
    else:
        assert (
            entry["claim_category"] == "supported" and entry["eligibility"]["product"] == "eligible"
        )
    # The untouched trials keep their standing: the other prospective trials stay prospective.
    assert report["declarations"]["prospective_trials"] == 5


def test_required_field_table_covers_every_field_the_scorer_reads():
    from nisayon.evaluation.prospective import REQUIRED_FIELD_TABLE
    from nisayon.evaluation.prospective_fixtures import CONTRACT_MUTATIONS

    rows = {(row["record"], row["field"]) for row in REQUIRED_FIELD_TABLE}
    requirements = {row["requirement"] for row in REQUIRED_FIELD_TABLE}
    assert requirements == {"required", "conditional", "nullable", "optional"} or requirements == {
        "required",
        "nullable",
        "optional",
    }
    mutated = {(record, field) for _, record, _, _, field in CONTRACT_MUTATIONS}
    unmutated = sorted(
        (record, field)
        for record, field in rows - mutated
        if not any(
            row["record"] == record and row["field"] == field and row["requirement"] == "optional"
            for row in REQUIRED_FIELD_TABLE
        )
        and not field.startswith("assignment.case_id")
        and not field.startswith("assignment.arm")
    )
    # Every non-optional row has a mutation control; case_id/arm identity is covered by
    # the mismatch controls above and the packet adapter tests.
    assert unmutated == [], unmutated


def test_writer_emitted_chain_is_a_prospective_positive(tmp_path):
    """A declaration, start and result written by the actual execution writer verify."""
    from nisayon.engine import declarations as writer
    from nisayon.evaluation.prospective import _norm, _writer_digest

    ledger = prospective_ledger()
    path = write_prospective_ledger(ledger, tmp_path)
    ledger = json.loads(path.read_text())
    trial = next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    root = tmp_path / "declarations" / "writer-A-D01"
    configuration = {"repair": "sign"}
    assert _writer_digest(configuration) == _norm(trial["decision"]["candidate_digest"])
    payload = {
        "assignment": {
            "suite_id": ledger["suite"]["id"],
            "case_id": trial["case_id"],
            "arm": "A",
            "frozen_inputs_sha256": _norm(trial["received_frozen_sha256"]),
        },
        "candidate": {
            "configuration": configuration,
            "configuration_sha256": _writer_digest(configuration),
        },
        "disposition": "claim_acceptance",
        "reason": "writer-emitted positive control",
        "evidence": [],
        "source": {"git_head": "test"},
        "settings": {"method": "writer control"},
        "evidence_scope": "prospective_execution",
    }
    declaration = writer.declare(root, payload, evidence_root=tmp_path)
    start = writer.begin_terminal(root, declaration, evidence_root=tmp_path)
    decision_ref = {"path": trial["decision"]["path"], "sha256": trial["decision"]["sha256"]}
    result = writer.finish_terminal(root, start, [decision_ref], evidence_root=tmp_path)
    trial["declaration"], trial["terminal_start"], trial["terminal_result"] = (
        declaration,
        start,
        result,
    )
    path.write_text(json.dumps(ledger, indent=2) + "\n")
    report = score_prospective_file(path, tmp_path)
    entry = next(t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))
    assert report["fair"] is True, report["findings"]
    assert entry["prospective"] is True and entry["ordering"]["verified"] is True
    assert entry["declaration"]["origin"] == "receipt" and entry["claim_category"] == "supported"
    assert entry["eligibility"] == {
        "study": True,
        "study_blockers": [],
        "product": "eligible",
        "product_blockers": [],
    }
    # An identical retry through the writer returns the original bytes; a changed one is refused.
    assert writer.declare(root, payload, evidence_root=tmp_path) == declaration
    with pytest.raises(writer.DeclarationConflict):
        writer.declare(root, {**payload, "reason": "changed"}, evidence_root=tmp_path)
