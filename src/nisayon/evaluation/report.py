"""Plain-text rendering of decisions and control summaries."""

from __future__ import annotations


def finding_codes(decision: dict) -> set[str]:
    codes = {reason["code"] for reason in decision.get("reasons", [])}
    for run in decision.get("runs", {}).values():
        codes.update(f["code"] for f in run.get("findings", []))
    confirmation = decision.get("confirmation") or {}
    codes.update(f["code"] for f in confirmation.get("findings", []))
    codes.update(n["code"] for n in decision.get("notes", []))
    return codes


def render_text(decision: dict) -> str:
    lines = [
        f"Decision: {decision['decision'].upper()}",
        f"Scope: {decision['scope']}",
        f"Case: {decision.get('case_id')} · evidence origin: {decision.get('evidence_origin')}",
    ]
    evidence = decision.get("evidence")
    if evidence:
        lines.append(
            "Evidence: "
            + " · ".join(f"{key} {value}" for key, value in evidence.items() if key != "custody")
        )
    premises = decision.get("premises", {})
    lines.append(
        "Premises: reference established="
        f"{premises.get('reference_established')} · regression reproduced={premises.get('regression_reproduced')}"
    )
    if decision["reasons"]:
        lines.append("Reasons:")
        for reason in decision["reasons"]:
            where = (
                f" [{reason['run_id']}"
                + (f" step {reason['step']}" if reason.get("step") is not None else "")
                + "]"
                if reason.get("run_id")
                else ""
            )
            path = f" at {reason['path']}" if reason.get("path") else ""
            lines.append(
                f"  - {reason['severity']}: {reason['code']}{where}{path}: {reason['detail']}"
            )
    else:
        lines.append("Reasons: none; every declared obligation is met on the declared conditions")
    runs = decision.get("runs", {})
    if runs:
        lines.append("Runs:")
        header = f"  {'run':<36}{'role':<11}{'rev':<9}{'cond':<10}{'process':<10}{'measure':<11}{'outcome':<10}{'progress':<10}{'constr':<10}timing"
        lines.append(header)
        for run_id, run in runs.items():
            lines.append(
                f"  {run_id:<36}{run['role']:<11}{str(run['revision']):<9}{str(run['condition_id']):<10}"
                f"{str(run['process']):<10}{run['measurement']:<11}{run['outcome']['observed']:<10}"
                f"{run['progress']:<10}{run['constraints']:<10}{run['timing']}"
            )
    confirmation = decision.get("confirmation")
    if confirmation and confirmation.get("summary"):
        summary = confirmation["summary"]
        lines.append(
            f"Confirmation: reproduction {summary['reproduction']} · fresh assigned "
            f"{summary['fresh_assigned']}/{summary['fresh_declared']} · pass {summary['fresh_pass']} · "
            f"regression {summary['fresh_regression']} · both failed {summary['fresh_both_failed']} · "
            f"improved {summary['fresh_improved']} · gap/invalid {summary['fresh_gap_or_invalid']}"
        )
    if confirmation and confirmation.get("pairs"):
        lines.append("Confirmation pairs:")
        for pair in confirmation["pairs"]:
            lines.append(
                f"  {pair['condition_id']:<10}{pair['role']:<14}ref {pair['reference_run_id']} ({pair['reference_outcome']}) · "
                f"cand {pair['candidate_run_id']} ({pair['candidate_outcome']}, {pair['candidate_measurement']}) → {pair['verdict']}"
            )
    if decision.get("candidates"):
        lines.append("Candidates:")
        for entry in decision["candidates"].values():
            failures = sorted({f["code"] for f in entry["obligation_failures"]})
            lines.append(
                f"  {entry['id']:<14}{entry['status']:<12}{entry['digest'][:19]}  runs {len(entry['runs'])}"
                + (f"  failures {failures}" if failures else "")
            )
    if decision.get("notes"):
        lines.append("Notes:")
        for note in decision["notes"]:
            lines.append(f"  - {note['code']}: {note['detail']}")
    producer = decision.get("producer") or {}
    if producer.get("code"):
        lines.append(
            f"Producer: {producer.get('schema')} · execution code {producer['code'].get('git_head')}"
        )
    costs = decision.get("costs", {})
    if costs.get("per_item"):
        lines.append("Costs (known totals; unknown costs are not zero):")
        for name, item in costs["per_item"].items():
            lines.append(
                f"  {name}: {item['known_total']} {item['unit']} over {item['known_runs']} runs; "
                f"missing in {item['missing_runs']} runs"
                + (f" ({'; '.join(item['missing_reasons'])})" if item["missing_reasons"] else "")
            )
    if decision.get("unparsed_records"):
        lines.append("Unparsed records:")
        for item in decision["unparsed_records"]:
            lines.append(f"  - {item['file']}: {item['error']}")
    lines.append("Limits:")
    for limit in decision.get("limits", []):
        lines.append(f"  - {limit}")
    return "\n".join(lines)


def render_controls(summary: dict) -> str:
    lines = [
        f"Synthetic controls ({summary['evidence_origin']}): {summary['scenarios']} scenarios, "
        f"{'all match' if summary['all_ok'] else 'MISMATCH'}",
        f"  {'scenario':<46}{'expected':<12}{'observed':<12}status",
    ]
    for result in summary["results"]:
        status = "ok" if result["ok"] else "MISMATCH"
        lines.append(
            f"  {result['scenario']:<46}{result['expected_decision']:<12}{result['observed_decision']:<12}{status}"
        )
        for code in result["missing_codes"]:
            lines.append(f"      missing expected code: {code}")
        for item in result["measurement_mismatches"]:
            lines.append(f"      measurement: {item}")
    lines.append(f"  {summary['note']}")
    return "\n".join(lines)
