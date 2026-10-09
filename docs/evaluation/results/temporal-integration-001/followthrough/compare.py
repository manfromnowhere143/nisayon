"""Join the before and after reassessments and account for every changed reading.

Reads ``before/assessments.json`` (version 1 at the consumed source) and
``after/assessments.json`` (version 2), plus the full assessments, and writes
``comparison.json``: per population, per assignment, the old and new statuses side by
side with the reason for each change, named by the issue that caused it (A..F). A change
with no recognised reason is listed as ``unexplained`` and fails the script.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREDICATES = (
    "generation_fencing",
    "request_binding",
    "configuration_binding",
    "queue_reset",
    "duplicate_dispatch",
    "dispatch_order",
    "freshness",
    "acknowledgement",
    "useful_execution",
)


def load(stage: Path) -> tuple[dict, dict[str, dict]]:
    record = json.loads((stage / "assessments.json").read_text())
    full: dict[str, dict] = {}
    for population in record["populations"]:
        for entry in json.loads((stage / "full" / f"{population['name']}.json").read_text()):
            full[entry["assignment_id"]] = entry["assessment"]
    return record, full


def reason_for(predicate: str, before: str, after: str, assessment: dict) -> tuple[str, str]:
    """Name the issue behind a changed status from the version-2 findings themselves."""
    findings = assessment["predicates"][predicate]["findings"]
    details = " | ".join(f["detail"] for f in findings)
    if predicate == "configuration_binding" and "activation" in details:
        return "B", "activation context derived from recorded transitions differs at dispatch"
    if predicate == "acknowledgement":
        if "send attempt(s) have no acknowledgement" in details:
            return "C", "an attempt without its own acknowledgement was masked by a later one"
        return "C", details[:160]
    if predicate == "freshness":
        readings = assessment.get("age_readings", [])
        if any(r["chronology"] == "conflicting_declarations" for r in readings):
            return "clock", "a clock pair declared twice with different relations is conflicting"
        if any(
            r["chronology"] in ("unsupported_declaration", "undeclared_clock", "unit_mismatch")
            for r in readings
        ):
            return "clock", "declarations outside the supported domain leave the pair unmapped"
        if assessment.get("evidence", {}).get("identity_conflicts"):
            return "identity", "the queued action keeps the identity it was admitted with"
        if any(
            r["classification"] == "beyond" and r["chronology"] == "same_clock" for r in readings
        ):
            return "E", "exact same-clock arithmetic exposes an excess that float conversion lost"
        if any(r["premise"] for r in readings):
            return "D", "chain evidence bounds a mapped interval that crossed zero"
        if any(r["classification"] in ("chronology_unresolved", "inconsistent") for r in readings):
            return "D", "chronology not established by the declared mapping"
        return "D/E", details[:160]
    if predicate == "useful_execution":
        return "legacy", "grid arithmetic (must not change; inspect)"
    return "unexplained", details[:160]


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    before_record, before_full = load(root / "before")
    after_record, after_full = load(root / "after")
    populations = []
    unexplained = 0
    for population_before, population_after in zip(
        before_record["populations"], after_record["populations"], strict=True
    ):
        assert population_before["name"] == population_after["name"]
        rows = []
        changed_predicates: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        contract_pairs: Counter[str] = Counter()
        assigned: Counter[str] = Counter()
        assigned_contract: Counter[str] = Counter()
        valid_acknowledged: Counter[str] = Counter()
        alignment: Counter[str] = Counter()
        observation_context: Counter[str] = Counter()
        identity: Counter[str] = Counter()
        clock_status: Counter[str] = Counter()
        completeness_pairs: Counter[str] = Counter()
        for rb, ra in zip(population_before["rows"], population_after["rows"], strict=True):
            assert rb["assignment_id"] == ra["assignment_id"]
            assert rb["trace_sha256"] == ra["trace_sha256"], rb["assignment_id"]
            sb, sa = rb["summary"], ra["summary"]
            full = after_full[ra["assignment_id"]]
            changes = []
            for predicate in PREDICATES:
                b, a = sb["predicates"][predicate], sa["predicates"][predicate]
                if b != a:
                    issue, why = reason_for(predicate, b, a, full)
                    if issue in ("unexplained", "legacy"):
                        unexplained += 1
                    changed_predicates[predicate] += 1
                    reasons[issue] += 1
                    changes.append(
                        {
                            "predicate": predicate,
                            "before": b,
                            "after": a,
                            "issue": issue,
                            "reason": why,
                        }
                    )
            usefulness = full.get("assigned_usefulness") or {}
            retro = full.get("retrospective") or {}
            row = {
                "assignment_id": ra["assignment_id"],
                "case_id": ra["case_id"],
                "remedy_id": ra["remedy_id"],
                "trace_sha256": ra["trace_sha256"],
                "temporal_contract": {"v1": sb["temporal_contract"], "v2": sa["temporal_contract"]},
                "predicates": {
                    p: {"v1": sb["predicates"][p], "v2": sa["predicates"][p]} for p in PREDICATES
                },
                "changes": changes,
                "assigned_usefulness": {
                    k: usefulness.get(k)
                    for k in (
                        "status",
                        "membership",
                        "minimum_dispatches",
                        "opportunities",
                        "opportunities_dispatched",
                        "opportunities_refused",
                        "raw_dispatch_attempts",
                        "opportunities_valid",
                        "opportunities_acknowledged",
                        "opportunities_valid_acknowledged",
                        "valid_acknowledged_status",
                    )
                },
                "assigned_contract": full.get("assigned_contract"),
                "chunk_target_alignment": retro.get("chunk_target_alignment", {}).get("status"),
                "observation_context": retro.get("observation_context", {}).get("status"),
                "chunk_identity": retro.get("chunk_identity", {}).get("status"),
                "clock_status": full.get("evidence", {}).get("clocks", {}).get("status"),
                "completeness": {
                    "v1": sb.get("evidence_completeness"),
                    "v2": sa.get("evidence_completeness"),
                },
                "admissions_stricter_than_frozen_rule": len(
                    retro.get("admissions_stricter_than_frozen_rule", [])
                ),
                "software_execution": sa["software_execution"],
            }
            rows.append(row)
            contract_pairs[f"{sb['temporal_contract']}->{sa['temporal_contract']}"] += 1
            assigned[str(usefulness.get("status"))] += 1
            assigned_contract[str(full.get("assigned_contract"))] += 1
            valid_acknowledged[str(usefulness.get("valid_acknowledged_status"))] += 1
            alignment[str(row["chunk_target_alignment"])] += 1
            observation_context[str(row["observation_context"])] += 1
            identity[str(row["chunk_identity"])] += 1
            clock_status[str(row["clock_status"])] += 1
            completeness_pairs[f"{row['completeness']['v1']}->{row['completeness']['v2']}"] += 1
        populations.append(
            {
                "name": population_after["name"],
                "count": len(rows),
                "assignments_with_changed_predicates": sum(1 for r in rows if r["changes"]),
                "changed_predicate_counts": dict(changed_predicates),
                "change_reasons": dict(reasons),
                "temporal_contract_v1_to_v2": dict(contract_pairs),
                "assigned_usefulness_status": dict(assigned),
                "assigned_contract": dict(assigned_contract),
                "valid_acknowledged_status": dict(valid_acknowledged),
                "chunk_target_alignment": dict(alignment),
                "observation_context": dict(observation_context),
                "chunk_identity": dict(identity),
                "clock_status": dict(clock_status),
                "completeness_before_to_after": dict(completeness_pairs),
                "rows": rows,
            }
        )
    comparison = {
        "schema": "nisayon.temporal-followthrough-comparison.v1",
        "before": {"source": before_record["source"], "label": before_record["label"]},
        "after": {"source": after_record["source"], "label": after_record["label"]},
        "populations": populations,
        "unexplained_changes": unexplained,
        "boundary": "software readings of retained traces under two versions of the reference; "
        "no execution, no robot outcome, no acceptance",
    }
    (root / "comparison.json").write_text(json.dumps(comparison, indent=1, sort_keys=True) + "\n")
    for p in populations:
        print(
            f"{p['name']}: {p['count']} rows, {p['assignments_with_changed_predicates']} with changed "
            f"predicates {p['changed_predicate_counts']} reasons {p['change_reasons']}; contract "
            f"{p['temporal_contract_v1_to_v2']}; assigned {p['assigned_usefulness_status']}; "
            f"assigned contract {p['assigned_contract']}; valid+ack {p['valid_acknowledged_status']}; "
            f"alignment {p['chunk_target_alignment']}; observation {p['observation_context']}"
        )
    print("unexplained changes:", unexplained)
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
