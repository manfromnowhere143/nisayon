"""Exercise declaration ordering on exposed native development records.

No simulator or model is called. The declarations are explicitly authored for
this demonstration; they are not retroactively attributed to the historical arms.
Endpoint semantics belong to the separately versioned evaluation report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from .declarations import begin_terminal, declare, finish_terminal, inspect_declaration
from .identity import code_identity
from .io import digest, file_digest, write_json
from .store import resolve_member

SCOPE = "retained_development_demonstration"
UNKNOWN_COSTS = {
    "engineer_effort_s": "Not measured by command walls",
    "provider_charges_usd": "No attributable provider invoice",
    "energy_j": "No energy meter",
    "unrecorded_processing_s": "Only retained command and stage walls are measured",
}


def _bytes(path: Path) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024**2 + 1)
    if len(raw) > 16 * 1024**2:
        raise ValueError("Retained metadata exceeds the bounded 16 MiB read: " + str(path))
    return raw


def _read(path: Path) -> tuple[dict, str]:
    raw = _bytes(path)
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected an object: " + str(path))
    return value, hashlib.sha256(raw).hexdigest()


def _ref(root: Path, path: Path) -> dict:
    return {"path": str(path.relative_to(root)), "sha256": file_digest(path)}


def _bound(root: Path, reference: dict) -> tuple[Path, dict]:
    if not isinstance(reference, dict) or not isinstance(reference.get("sha256"), str):
        raise ValueError("Expected an exact file reference")
    source = resolve_member(root, reference["path"])
    value, sha = _read(source)
    if sha != reference["sha256"]:
        raise ValueError("Changed source bytes: " + reference["path"])
    return source, value


def _copy(source: Path, target: Path, *, expected: str | None = None) -> None:
    raw = _bytes(source)
    before = expected or hashlib.sha256(raw).hexdigest()
    if hashlib.sha256(raw).hexdigest() != before:
        raise ValueError("Source changed before retention: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as retained:
        retained.write(raw)
    if file_digest(target) != before:
        raise ValueError("Retained copy differs from source snapshot: " + str(source))


def _name(value: object) -> str:
    if not isinstance(value, str) or Path(value).name != value or value in {"", ".", ".."}:
        raise ValueError("Assignment IDs must be simple path components")
    return value


def run_demo(source: Path, plan_path: Path, output: Path) -> dict:
    """Freeze all declarations before reading any terminal decision in this run.

    The input ledger already exposes outcomes. Observed local read order cannot
    turn these old records into prospective or independently held evidence.
    """
    source, plan_path = source.resolve(strict=True), plan_path.resolve(strict=True)
    output = output.absolute()
    if output.exists():
        raise ValueError("Use a new output directory; prior attempts are retained")
    source_ledger, source_suite = source / "comparison-ledger.json", source / "frozen-suite.json"
    ledger, ledger_sha = _read(source_ledger)
    suite, suite_sha = _read(source_suite)
    plan, plan_sha = _read(plan_path)
    if (
        ledger.get("schema") != "nisayon.comparison.v1"
        or suite.get("schema") != "nisayon.development.frozen-suite.v1"
        or plan.get("schema") != "nisayon.retained-declaration-plan.v1"
        or plan.get("evidence_scope") != SCOPE
    ):
        raise ValueError("Only explicitly labelled retained development inputs are supported")
    if digest(suite) != ledger["suite"]["case_ledger_sha256"]:
        raise ValueError("Historical frozen suite changed")
    if plan["source_suite_sha256"] != digest(suite):
        raise ValueError("Declaration plan belongs to another historical suite")
    if ledger["cases"] != suite["cases"] or ledger["arms"] != suite["arms"]:
        raise ValueError("Ledger assignment contract differs from frozen suite")
    cases = {_name(case["id"]): case for case in suite["cases"]}
    arms = [_name(arm["id"]) for arm in suite["arms"]]
    assigned = {(case_id, arm) for case_id in cases for arm in arms}
    trials = {(t["case_id"], t["arm"]): t for t in ledger["trials"]}
    if (
        len(cases) != len(suite["cases"])
        or len(arms) != len(set(arms))
        or len(trials) != len(ledger["trials"])
        or set(trials) != assigned
        or set(plan["cases"]) != set(cases)
    ):
        raise ValueError("Duplicate, missing or unassigned case/arm/plan row")
    if shutil.disk_usage(output.parent.resolve(strict=True)).free < 5 * 1024**3:
        raise ValueError("Pause artifact growth below 5 GiB free space")
    start = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    for original, name, sha in (
        (source_ledger, "comparison-ledger.json", ledger_sha),
        (source_suite, "frozen-suite.json", suite_sha),
        (plan_path, "declaration-plan.json", plan_sha),
    ):
        _copy(original, output / "sources" / name, expected=sha)
    preparation_reference = None
    if ledger.get("preparation_cost_ledger"):
        original, _ = _bound(source, ledger["preparation_cost_ledger"])
        retained = output / "sources/preparation-costs.json"
        _copy(original, retained, expected=ledger["preparation_cost_ledger"]["sha256"])
        preparation_reference = _ref(output, retained)
    freeze = {
        "schema": "nisayon.retained-declaration-freeze.v1",
        "id": plan["id"],
        "evidence_scope": SCOPE,
        "frozen_at": datetime.now(UTC).isoformat(),
        "code": code_identity(),
        "source_locator": str(source),
        "source_ledger": _ref(output, output / "sources/comparison-ledger.json"),
        "source_suite": _ref(output, output / "sources/frozen-suite.json"),
        "plan": _ref(output, output / "sources/declaration-plan.json"),
        "assigned": [{"case_id": c, "arm": a} for c, a in sorted(assigned)],
        "common_terminal_rule": ledger["suite"]["obligation"],
        "origin": "Explicit development statements, authored after historical evidence was exposed",
        "online_audit": "Historical diagnostic audits remain separate from terminal evidence",
        "new_model_calls": 0,
        "new_simulator_executions": 0,
    }
    write_json(output / "freeze.json", freeze)
    rows = []
    # Every assigned arm receives its declaration before any new terminal-start.
    for case_id, arm in sorted(assigned):
        trial = trials[case_id, arm]
        frozen = cases[case_id]["frozen"]
        if trial["received_frozen_sha256"] != digest(frozen):
            raise ValueError("Historical arm received different frozen inputs")
        diagnosis_path, diagnosis = _bound(source, trial["diagnosis"])
        if diagnosis["case_id"] != case_id or diagnosis["arm"] != arm:
            raise ValueError("Historical diagnosis belongs to another assignment")
        local = output / case_id / arm
        retained_diagnosis = local / "sources/diagnosis.json"
        _copy(diagnosis_path, retained_diagnosis, expected=trial["diagnosis"]["sha256"])
        statement = plan["cases"][case_id]
        candidate = diagnosis["candidate"]
        if statement["disposition"] == "claim_acceptance" and candidate is None:
            raise ValueError("Development claim has no retained candidate")
        receipt = declare(
            local / "declaration",
            {
                "assignment": {
                    "suite_id": plan["id"],
                    "case_id": case_id,
                    "arm": arm,
                    "frozen_inputs_sha256": digest(frozen),
                },
                "candidate": {"configuration": candidate, "configuration_sha256": digest(candidate)}
                if candidate is not None
                else None,
                "disposition": statement["disposition"],
                "reason": statement["reason"],
                "evidence": [
                    _ref(output, retained_diagnosis),
                    _ref(output, output / "freeze.json"),
                ],
                "source": freeze["code"],
                "settings": {
                    "method": "explicit_development_statement_on_exposed_records",
                    "plan": freeze["plan"],
                    "candidate_source": "Exact historical diagnosis candidate; no post-terminal substitution",
                    "historical_solver_kind": ledger["suite"]["solver_kind"],
                    "not_attributed_to_historical_arm": True,
                },
                "evidence_scope": SCOPE,
            },
            evidence_root=output,
        )
        rows.append(
            {
                "case_id": case_id,
                "arm": arm,
                "declaration": receipt,
                "historical_trial": trial,
                "processing_started_at": datetime.now(UTC).isoformat(),
            }
        )
    write_json(
        output / "declarations.json", {"freeze": _ref(output, output / "freeze.json"), "rows": rows}
    )
    for row in rows:
        phase_start = time.perf_counter()
        local = output / row["case_id"] / row["arm"]
        declaration_root = local / "declaration"
        started = begin_terminal(declaration_root, row["declaration"], evidence_root=output)
        trial = row["historical_trial"]
        original, decision = _bound(source, trial["decision"])
        if decision["case_id"] != row["case_id"] + "-" + row["arm"]:
            raise ValueError("Terminal decision belongs to another case or arm")
        retained = local / "terminal/decision.json"
        _copy(original, retained, expected=trial["decision"]["sha256"])
        evidence = [_ref(output, retained)]
        if trial.get("confirmation"):
            original, confirmation = _bound(source, trial["confirmation"])
            _, declared = _bound(output, row["declaration"])
            if confirmation["candidate_digest"] != trial["decision"][
                "candidate_digest"
            ] or confirmation["candidate_digest"] != (declared["candidate"] or {}).get(
                "configuration_sha256"
            ):
                raise ValueError("Terminal candidate differs from historical frozen candidate")
            retained = local / "terminal/confirmation-result.json"
            _copy(original, retained, expected=trial["confirmation"]["sha256"])
            evidence.append(_ref(output, retained))
        terminal = finish_terminal(declaration_root, started, evidence, evidence_root=output)
        row.update(
            terminal_start=started,
            terminal_result=terminal,
            terminal_evidence=evidence,
            retained_decision=decision["decision"],
            new_terminal_processing_wall_s=time.perf_counter() - phase_start,
            recovery=inspect_declaration(declaration_root, evidence_root=output),
        )
        write_json(local / "demonstration-row.json", row)
    packet = {
        "schema": "nisayon.retained-declaration-packet.v1",
        "freeze": _ref(output, output / "freeze.json"),
        "evidence_scope": SCOPE,
        "assignments": freeze["assigned"],
        "rows": rows,
        "historical_preparation_cost_ledger": preparation_reference,
        "processing_wall_s": time.perf_counter() - start,
        "processing_cost_scope": "New read/receipt processing only; nested stage/writer walls are not additive",
        "missing_costs": {
            key: {
                "value": None,
                "unit": {"s": "s", "usd": "USD", "j": "J"}[key.rsplit("_", 1)[-1]],
                "reason": reason,
            }
            for key, reason in UNKNOWN_COSTS.items()
        },
        "scientific_claim": "No effectiveness estimate; historical outcomes and declarations are separate",
        "reference_limit": "Shared terminal checker and shared retained evidence do not establish independent physical truth",
        "new_model_calls": 0,
        "new_simulator_executions": 0,
    }
    write_json(output / "packet.json", packet)
    return packet


def render_packet(packet: dict, root: Path) -> str:
    lines = [
        "Exposed-record development declarations; no new experiment or effectiveness estimate.",
        "case\tarm\tdeclaration\thistorical status\tterminal record\told physical runs\told own wall (s)\tnew terminal read (s)",
    ]
    for row in packet["rows"]:
        _, declaration = _bound(root, row["declaration"])
        old = row["historical_trial"]
        lines.append(
            "\t".join(
                map(
                    str,
                    (
                        row["case_id"],
                        row["arm"],
                        declaration["disposition"],
                        old["status"],
                        row["retained_decision"],
                        old["diagnostic_rollouts"] + old["confirmation_rollouts"],
                        old["costs"]["own_trial_wall"]["value"],
                        round(row["new_terminal_processing_wall_s"], 6),
                    ),
                )
            )
        )
    lines.append("Missing: " + "; ".join(packet["missing_costs"]))
    lines.append("Terminal checker outcomes are not yet prospective claim classifications.")
    return "\n".join(lines) + "\n"


def render_costs(packet: dict, root: Path) -> str:
    """Export reported quantities and gaps; overlapping scopes are never added."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(
        ("scope", "case", "arm", "category", "value", "unit", "known_part", "missing", "accounting")
    )
    for row in packet["rows"]:
        old = row["historical_trial"]
        for category, quantity in old["costs"].items():
            writer.writerow(
                (
                    "historical_trial",
                    row["case_id"],
                    row["arm"],
                    category,
                    quantity["value"] if quantity["value"] is not None else "unknown",
                    quantity["unit"],
                    quantity.get("known_part", ""),
                    quantity.get("missing", ""),
                    old["cost_scope"],
                )
            )
        writer.writerow(
            (
                "new_processing",
                row["case_id"],
                row["arm"],
                "terminal_read_wall",
                row["new_terminal_processing_wall_s"],
                "s",
                "",
                "",
                "Nested in packet processing and outer command wall",
            )
        )
        recovery = row["recovery"]
        writer.writerow(
            (
                "new_processing",
                row["case_id"],
                row["arm"],
                "writer_attempt_walls",
                "unknown"
                if recovery["attempts_with_unknown_cost"]
                else recovery["known_writer_wall_s"],
                "s",
                recovery["known_writer_wall_s"],
                f"{recovery['attempts_with_unknown_cost']} attempts with unknown cost"
                if recovery["attempts_with_unknown_cost"]
                else "",
                recovery["cost_scope"],
            )
        )
    if packet["historical_preparation_cost_ledger"]:
        _, preparation = _bound(root, packet["historical_preparation_cost_ledger"])
        writer.writerow(
            (
                "historical_shared_preparation",
                "all",
                "shared",
                "recorded_command_wall",
                preparation["known_command_wall_sum_s"],
                "s",
                "",
                "Unrecorded categories listed separately",
                preparation["interpretation"] + " No amortization across assignments.",
            )
        )
        for missing in preparation["unmeasured"]:
            writer.writerow(
                (
                    "historical_shared_preparation",
                    "all",
                    "shared",
                    missing["category"],
                    "unknown",
                    missing["unit"],
                    "",
                    missing["reason"],
                    "Not zero; not amortized",
                )
            )
    else:
        writer.writerow(
            (
                "historical_shared_preparation",
                "all",
                "shared",
                "preparation_costs",
                "unknown",
                "unknown",
                "",
                "No preparation cost ledger was retained",
                "Not zero; not amortized",
            )
        )
    writer.writerow(
        (
            "new_processing",
            "all",
            "shared",
            "packet_processing_wall",
            packet["processing_wall_s"],
            "s",
            "",
            "",
            packet["processing_cost_scope"],
        )
    )
    for category, missing in packet["missing_costs"].items():
        writer.writerow(
            (
                "new_processing",
                "all",
                "shared",
                category,
                "unknown",
                missing.get("unit", "unknown"),
                "",
                missing["reason"],
                "Not zero",
            )
        )
    return output.getvalue()


def inspect_demo(root: Path) -> dict:
    """Recover every frozen assignment from local receipts, without executing it."""
    root = root.resolve(strict=True)
    freeze_path = resolve_member(root, "freeze.json")
    freeze, freeze_sha = _read(freeze_path)
    if (
        freeze.get("schema") != "nisayon.retained-declaration-freeze.v1"
        or freeze.get("evidence_scope") != SCOPE
    ):
        raise ValueError("Expected a frozen retained development demonstration")
    _, suite = _bound(root, freeze["source_suite"])
    _, ledger = _bound(root, freeze["source_ledger"])
    _, plan = _bound(root, freeze["plan"])
    cases = {_name(case["id"]): case for case in suite["cases"]}
    arms = [_name(arm["id"]) for arm in suite["arms"]]
    assigned = [(_name(item["case_id"]), _name(item["arm"])) for item in freeze["assigned"]]
    trials = {(trial["case_id"], trial["arm"]): trial for trial in ledger["trials"]}
    if (
        digest(suite) != ledger["suite"]["case_ledger_sha256"]
        or digest(suite) != plan["source_suite_sha256"]
        or freeze["id"] != plan["id"]
        or len(cases) != len(suite["cases"])
        or len(arms) != len(set(arms))
        or len(assigned) != len(set(assigned))
        or set(assigned) != {(case_id, arm) for case_id in cases for arm in arms}
        or len(trials) != len(ledger["trials"])
        or set(trials) != set(assigned)
    ):
        raise ValueError("Retained freeze differs from the bound assignment sources")
    rows = []
    for case_id, arm in assigned:
        recovery = inspect_declaration(root / case_id / arm / "declaration", evidence_root=root)
        row = {
            "case_id": case_id,
            "arm": arm,
            "declaration_disposition": None,
            "declaration_missing": "declaration" not in recovery["references"],
            "terminal_record_decision": None,
            "recovery": recovery,
            "historical_costs": trials[case_id, arm]["costs"],
            "historical_cost_scope": trials[case_id, arm]["cost_scope"],
        }
        try:
            if not row["declaration_missing"]:
                _, statement = _bound(root, recovery["references"]["declaration"])
                if statement["assignment"] != {
                    "suite_id": plan["id"],
                    "case_id": case_id,
                    "arm": arm,
                    "frozen_inputs_sha256": digest(cases[case_id]["frozen"]),
                }:
                    raise ValueError("Declaration differs from this frozen assignment")
                row["declaration_disposition"] = statement["disposition"]
            if "terminal-result" in recovery["references"]:
                _, terminal = _bound(root, recovery["references"]["terminal-result"])
                if (
                    not isinstance(terminal.get("terminal_evidence"), list)
                    or not terminal["terminal_evidence"]
                ):
                    raise ValueError("Terminal result has no readable evidence list")
                reference = terminal["terminal_evidence"][0]
                _, decision = _bound(root, reference)
                if (
                    reference["sha256"] != trials[case_id, arm]["decision"]["sha256"]
                    or decision["case_id"] != case_id + "-" + arm
                ):
                    raise ValueError("Terminal evidence differs from the historical assignment")
                row["terminal_record_decision"] = decision["decision"]
        except (KeyError, IndexError, ValueError, OSError) as error:
            recovery["findings"].append(str(error))
        rows.append(row)
    return {
        "schema": "nisayon.retained-declaration-recovery.v1",
        "evidence_scope": SCOPE,
        "inspected_at": datetime.now(UTC).isoformat(),
        "root_locator": str(root),
        "freeze": {"path": "freeze.json", "sha256": freeze_sha},
        "assigned_trials": len(assigned),
        "declarations_missing": sum(row["declaration_missing"] for row in rows),
        "terminal_records_retained": sum(
            row["terminal_record_decision"] is not None for row in rows
        ),
        "rows_with_findings": sum(bool(row["recovery"]["findings"]) for row in rows),
        "rows": rows,
        "new_processing_cost": {
            "known_writer_attempt_wall_s": sum(
                row["recovery"]["known_writer_wall_s"] for row in rows
            ),
            "attempts_with_unknown_cost": sum(
                row["recovery"]["attempts_with_unknown_cost"] for row in rows
            ),
            "scope": "Receipt writer attempts only; nested in command walls, possibly overlapping. Missing declarations are not zero-cost decisions.",
            "outer_command_wall_s": None,
            "missing": "Locate the original invocation command record; this read-only snapshot cannot reconstruct its elapsed work or any lost timing.",
        },
        "scientific_acceptance": "Not assessed. These are exposed development records; missing declarations are not abstentions and terminal states are not prospective claim classifications.",
        "continuation": "Inspect partial receipts and original command records. No execution is resumed or retried; use a separate output for a new demonstration attempt.",
    }


def render_recovery(report: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(("case", "arm", "declaration", "receipt state", "terminal record", "findings"))
    for row in report["rows"]:
        writer.writerow(
            (
                row["case_id"],
                row["arm"],
                row["declaration_disposition"] or "missing_or_unreadable",
                row["recovery"]["state"],
                row["terminal_record_decision"] or "unknown",
                "; ".join(row["recovery"]["findings"]),
            )
        )
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument(
        "--inspect", type=Path, help="Read an existing partial or complete demonstration"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.inspect is not None:
        if args.source is not None or args.plan is not None:
            parser.error("Inspection uses only --inspect and --output")
        if args.output.resolve().is_relative_to(args.inspect.resolve()):
            parser.error("Inspection output must be outside the original demonstration")
        report = inspect_demo(args.inspect)
        write_json(args.output, report)
        print(render_recovery(report), end="")
        return
    if args.source is None or args.plan is None:
        parser.error("A new demonstration requires --source and --plan")
    packet = run_demo(args.source, args.plan, args.output)
    report = render_packet(packet, args.output.resolve(strict=True))
    with (args.output / "records.tsv").open("x") as stream:
        stream.write(report)
    costs = render_costs(packet, args.output.resolve(strict=True))
    with (args.output / "costs.tsv").open("x") as stream:
        stream.write(costs)
    print(report, end="")
    print("\nAll reported cost categories and gaps (overlapping scopes are not added):")
    print(costs, end="")


if __name__ == "__main__":
    main()
