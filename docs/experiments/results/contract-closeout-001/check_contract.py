"""Finite producer-contract controls through the public CLI; no physical execution."""

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

from nisayon.engine.declarations import FIELDS, begin_terminal, declare, finish_terminal
from nisayon.engine.io import digest, file_digest, write_json
from nisayon.evaluation.prospective_fixtures import prospective_ledger, write_prospective_ledger

HERE = Path(__file__).resolve().parent
ROLES = {"declaration": "declaration", "start": "terminal_start", "result": "terminal_result"}
MISSING = {"omit": True}


def replace(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return file_digest(path)


def target(ledger):
    return next(t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01"))


def reference(path, root):
    return {"path": str(path.relative_to(root)), "sha256": file_digest(path)}


def writer_control(root):
    """Retain the owner's old synthetic bytes, then write separate complete receipts.

    The scoring fixture supplies known synthetic outcomes. Fresh local writer clocks
    order their consumption; they do not make those outcomes prospective research.
    """
    original = root / "original-fixture"
    old_path = write_prospective_ledger(prospective_ledger(), original)
    ledger = json.loads(old_path.read_text())
    template = root / "writer-positive"
    shutil.copytree(original, template)
    basis = template / "basis.json"
    write_json(basis, {"evidence_origin": "synthetic_development", "basis": "public fixture"})
    changes = []
    for trial in ledger["trials"]:
        old = json.loads((template / trial["declaration"]["path"]).read_text())
        payload = {k: copy.deepcopy(old[k]) for k in FIELDS}
        payload["assignment"]["frozen_inputs_sha256"] = trial[
            "received_frozen_sha256"
        ].removeprefix("sha256:")
        if payload["candidate"] is not None:
            configuration = {
                "repair": "sign+timing" if trial["case_id"].startswith("D07") else "sign"
            }
            assert old["candidate"]["configuration_sha256"].removeprefix("sha256:") == digest(
                configuration
            )
            payload["candidate"] = {
                "configuration": configuration,
                "configuration_sha256": digest(configuration),
            }
        payload["evidence"] = [reference(basis, template)]
        receipt_root = template / "writer" / f"{trial['arm']}-{trial['case_id']}"
        old_refs = {k: trial.get(k) for k in ROLES.values()}
        trial["declaration"] = declare(receipt_root, payload, evidence_root=template)
        if trial.get("decision"):
            start = begin_terminal(receipt_root, trial["declaration"], evidence_root=template)
            decision = {k: trial["decision"][k] for k in ("path", "sha256")}
            trial["terminal_start"] = start
            trial["terminal_result"] = finish_terminal(
                receipt_root, start, [decision], evidence_root=template
            )
        changes.append(
            {
                "arm": trial["arm"],
                "case_id": trial["case_id"],
                "old": old_refs,
                "writer": {k: trial.get(k) for k in ROLES.values()},
            }
        )
    replace(template / "ledger.json", ledger)
    write_json(
        root / "fixture-transition.json",
        {
            "old_fixture_source_sha256": file_digest(
                Path("src/nisayon/evaluation/prospective_fixtures.py")
            ),
            "changes": changes,
            "explanation": "Only new synthetic controls: canonical candidate configurations and bare "
            "frozen/candidate digests, evidence basis, generated request/source/settings digests, "
            "and all observed event identifiers/clocks now come from the actual writer. Original "
            "fixture copies remain alongside these receipts. No original real packet is repaired.",
        },
    )
    return template


def field_rows():
    """An explicit finite field table, derived from declarations.py and its interface."""
    rows = []
    tops = {
        "declaration": {
            "schema": "string",
            "assignment": "object",
            "candidate": "nullable_object",
            "disposition": "string",
            "reason": "string",
            "evidence": "list",
            "source": "object",
            "settings": "object",
            "evidence_scope": "string",
            "observed": "object",
            "request_sha256": "string",
            "source_sha256": "string",
            "settings_sha256": "string",
        },
        "start": {
            "schema": "string",
            "declaration": "object",
            "assignment": "object",
            "candidate": "nullable_object",
            "evidence_scope": "string",
            "observed": "object",
        },
        "result": {
            "schema": "string",
            "declaration": "object",
            "terminal_start": "object",
            "assignment": "object",
            "terminal_evidence": "list",
            "request_sha256": "string",
            "observed": "object",
        },
    }
    for role, fields in tops.items():
        fields.update(
            {
                f"assignment.{k}": "string"
                for k in ("suite_id", "case_id", "arm", "frozen_inputs_sha256")
            }
        )
        fields.update(
            {
                "observed.event_id": "string",
                "observed.recorded_at": "string",
                "observed.sequence": "integer",
            }
        )
        if role != "result":
            fields.update(
                {"candidate.configuration": "object", "candidate.configuration_sha256": "string"}
            )
        for link in {
            "declaration": ["evidence.0"],
            "start": ["declaration"],
            "result": ["declaration", "terminal_start", "terminal_evidence.0"],
        }[role]:
            fields.update({f"{link}.path": "string", f"{link}.sha256": "string"})
        for path, shape in fields.items():
            rows.append(
                {
                    "role": role,
                    "path": path,
                    "shape": shape,
                    "required": "conditional"
                    if path.startswith(("candidate.", "evidence.0", "terminal_evidence.0"))
                    else "required",
                    "nullable": path == "candidate" and role != "result",
                }
            )
    return rows


def matrix():
    cases = []

    def add(name, role, path, value, *, outcome="reject", codes=None, disposition=None):
        cases.append(
            {
                "name": name,
                "role": role,
                "path": path,
                "value": value,
                "outcome": outcome,
                "codes": codes
                or (
                    ["declaration_malformed"]
                    if role == "declaration"
                    else ["terminal_binding_unverifiable"]
                ),
                "disposition": disposition,
            }
        )

    for row in field_rows():
        role, path, shape = row["role"], row["path"], row["shape"]
        for boundary, value in (
            ("absent", MISSING),
            ("null", None),
            ("type", [] if shape in ("object", "nullable_object") else {}),
        ):
            # A claim forbids null candidates. The three allowed null dispositions
            # and an absent candidate in a nonclaim have separate paired controls.
            add(f"{role}_{path.replace('.', '_')}_{boundary}", role, path, value)
    for role in ROLES:
        seq = {"declaration": 1, "start": 2, "result": 3}[role]
        for suffix, value in (
            ("boolean", True),
            ("float", float(seq)),
            ("string", str(seq)),
            ("wrong", seq + 1),
        ):
            add(f"{role}_sequence_{suffix}", role, "observed.sequence", value)
        for suffix, value in (("naive", "2026-09-19T15:00:00"), ("invalid", "not-a-time")):
            add(f"{role}_clock_{suffix}", role, "observed.recorded_at", value)
        add(f"{role}_schema_version", role, "schema", f"nisayon.{role}.v99")
        add(f"{role}_event_empty", role, "observed.event_id", "")
        for key in ("suite_id", "case_id", "arm", "frozen_inputs_sha256"):
            value = "0" * 64 if key.endswith("sha256") else "another-assignment"
            add(
                f"{role}_{key}_mismatch",
                role,
                f"assignment.{key}",
                value,
                codes=["declaration_mismatch"] if role == "declaration" else None,
            )
        add(f"{role}_frozen_digest_syntax", role, "assignment.frozen_inputs_sha256", "not-a-digest")
        add(f"{role}_assignment_extra", role, "assignment.extra", True)
    for role in ("declaration", "start"):
        add(f"{role}_candidate_digest_mismatch", role, "candidate.configuration_sha256", "0" * 64)
        add(
            f"{role}_candidate_digest_syntax",
            role,
            "candidate.configuration_sha256",
            "not-a-digest",
        )
        add(
            f"{role}_candidate_config_mismatch",
            role,
            "candidate.configuration",
            {"repair": "other"},
        )
        add(f"{role}_candidate_extra", role, "candidate.extra", True)
        add(f"{role}_scope_unknown", role, "evidence_scope", "unrecognized")
    for path in ("reason", "source", "settings"):
        add(f"declaration_{path}_empty", "declaration", path, "" if path == "reason" else {})
    add("declaration_disposition_unknown", "declaration", "disposition", "invalid_experiment")
    for path in ("request_sha256", "source_sha256", "settings_sha256"):
        add(f"declaration_{path}_mismatch", "declaration", path, "0" * 64)
    add("result_request_mismatch", "result", "request_sha256", "0" * 64)
    add("result_evidence_empty", "result", "terminal_evidence", [])
    for role, paths in (
        ("start", ["declaration"]),
        ("result", ["declaration", "terminal_start", "terminal_evidence.0"]),
    ):
        for path in paths:
            for suffix, value in (
                ("empty", ""),
                ("wrong", "basis.json"),
                ("escape", "../basis.json"),
            ):
                add(f"{role}_{path.replace('.', '_')}_path_{suffix}", role, f"{path}.path", value)
            add(f"{role}_{path.replace('.', '_')}_digest_wrong", role, f"{path}.sha256", "0" * 64)
    for role in ("start", "result"):
        add(f"{role}_clock_reversed", role, "observed.recorded_at", "2000-01-01T00:00:00+00:00")
        add(
            f"{role}_clock_equal",
            role,
            "observed.recorded_at",
            {"same_clock": True},
            outcome="pass",
        )
    for disposition in ("abstain", "refuse", "unresolved"):
        add(
            f"null_candidate_{disposition}",
            "declaration",
            "candidate",
            None,
            outcome="pass",
            disposition=disposition,
        )
        add(
            f"absent_candidate_{disposition}",
            "declaration",
            "candidate",
            MISSING,
            disposition=disposition,
        )
        add(
            f"absent_start_candidate_{disposition}",
            "start",
            "candidate",
            MISSING,
            disposition=disposition,
        )
    for role, path in (("declaration", "authority"), ("start", "order_scope")):
        add(f"optional_{path}_absent", role, path, MISSING, outcome="pass")
    add("declaration_evidence_empty", "declaration", "evidence", [], outcome="pass")
    add(
        "demonstration_scope",
        "declaration",
        "evidence_scope",
        "retained_development_demonstration",
        outcome="demonstration",
    )
    return cases


def set_field(record, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        record = record[int(part)] if isinstance(record, list) else record[part]
    key = int(parts[-1]) if isinstance(record, list) else parts[-1]
    if value == MISSING:
        del record[key]
    else:
        record[key] = copy.deepcopy(value)


def mutate(root, case):
    ledger_path = root / "ledger.json"
    ledger = json.loads(ledger_path.read_text())
    trial = target(ledger)
    paths = {role: root / trial[field]["path"] for role, field in ROLES.items()}
    records = {role: json.loads(path.read_text()) for role, path in paths.items()}
    dec, start, result = (records[k] for k in ROLES)
    if case["disposition"]:
        dec["disposition"], dec["candidate"] = case["disposition"], None
        start["candidate"] = None
    value = case["value"]
    if value == {"same_clock": True}:
        previous = dec if case["role"] == "start" else start
        value = previous["observed"]["recorded_at"]
    set_field(records[case["role"]], case["path"], value)
    # Propagate declaration identities to both downstream copies, even when incomplete.
    # Matching incomplete objects cannot establish the missing contract field.
    if case["role"] == "declaration":
        for key in ("assignment", "candidate", "evidence_scope"):
            if key in dec:
                start[key] = copy.deepcopy(dec[key])
            else:
                start.pop(key, None)
        if "assignment" in dec:
            result["assignment"] = copy.deepcopy(dec["assignment"])
        else:
            result.pop("assignment", None)
    for key in ("source", "settings"):
        if not (case["role"] == "declaration" and case["path"] == key + "_sha256"):
            dec[key + "_sha256"] = digest(dec.get(key))
    if not (case["role"] == "declaration" and case["path"] == "request_sha256"):
        dec["request_sha256"] = digest({k: dec[k] for k in FIELDS if k in dec})
    trial["declaration"]["sha256"] = replace(paths["declaration"], dec)
    # Refresh byte references except the field intentionally being challenged.

    def refresh_link(role, field, expected):
        if case["role"] != role or case["path"].split(".")[0] != field:
            records[role][field] = copy.deepcopy(expected)
        elif case["path"] == field + ".path":
            # Changing the path must not accidentally test a stale byte digest.
            records[role][field]["sha256"] = expected["sha256"]

    for role in ("start", "result"):
        refresh_link(role, "declaration", trial["declaration"])
    trial["terminal_start"]["sha256"] = replace(paths["start"], start)
    refresh_link("result", "terminal_start", trial["terminal_start"])
    if not (case["role"] == "result" and case["path"] == "request_sha256"):
        result["request_sha256"] = digest(
            {k: result[k] for k in ("terminal_start", "terminal_evidence") if k in result}
        )
    trial["terminal_result"]["sha256"] = replace(paths["result"], result)
    replace(ledger_path, ledger)


def inspect_case(root, case, assigned):
    command = [
        sys.executable,
        "-m",
        "nisayon.evaluation",
        "prospective",
        str(root / "ledger.json"),
        "--root",
        str(root),
        "--out",
        str(root / "report.json"),
    ]
    process = subprocess.run(command, capture_output=True, timeout=30, check=False)
    (root / "stdout.log").write_bytes(process.stdout)
    (root / "stderr.log").write_bytes(process.stderr)
    failures = []
    observation = {
        "name": case["name"],
        "command": command,
        "returncode": process.returncode,
        "failures": failures,
    }
    if not (root / "report.json").exists():
        failures.append("CLI did not retain a report")
        return observation
    report = json.loads((root / "report.json").read_text())
    entry = target(report)
    rejecting = case["outcome"] == "reject"
    wanted = 1 if rejecting else 0

    def require(condition, why):
        if not condition:
            failures.append(why)

    require(process.returncode == wanted, f"expected CLI exit {wanted}")
    require(
        {(t["arm"], t["case_id"]) for t in report["trials"]} == assigned,
        "all assignments must remain",
    )
    require(
        all(a["assigned_cases"] == 4 for a in report["arms"].values()), "N must stay four per arm"
    )
    require(report["fair"] is not rejecting, "fair disagrees with contract")
    require(
        report["eligibility"]["usable_as_study_result"] is not rejecting,
        "study eligibility disagrees with contract",
    )
    require(
        entry["reference"]["decision"] == "accepted",
        "separately bound reference must remain accepted",
    )
    require(
        entry["prospective"] == (not rejecting and case["outcome"] != "demonstration"),
        "prospective disagrees with contract",
    )
    findings = [
        f
        for f in report["findings"]
        if f.get("arm") == "A" and f.get("case_id") == entry["case_id"]
    ]
    if rejecting:
        require(
            any(f["code"] in case["codes"] for f in findings),
            f"missing specific blocker: {case['codes']}",
        )
        require(
            "NOT a usable study result" in process.stdout.decode(),
            "text must expose study ineligibility",
        )
        require(entry["eligibility"]["study"] is False, "affected trial must be study-ineligible")
        if case["role"] == "declaration":
            require(
                entry["non_acceptance_state"] == "declaration_unusable",
                "malformed declaration must stay assigned but unusable",
            )
            require(report["arms"]["A"]["declared_acceptances"] == 1, "unusable claim must leave D")
            require(
                report["arms"]["A"]["confirmed_correct"] == 1,
                "damaging a declaration must not increase C/N",
            )
        elif not case["disposition"]:
            require(
                entry["claim_category"] == "supported",
                "terminal metadata cannot contradict a supported claim",
            )
            require(
                entry["product_accepted"] is True,
                "independent product meaning must survive terminal metadata failure",
            )
    observation.update(
        {
            "fair": report["fair"],
            "prospective": entry["prospective"],
            "reference": entry["reference"],
            "claim_category": entry["claim_category"],
            "non_acceptance_state": entry["non_acceptance_state"],
            "eligibility": entry["eligibility"],
            "study_eligibility": report["eligibility"],
            "findings": findings,
            "report_sha256": file_digest(root / "report.json"),
        }
    )
    return observation


def audit(out):
    out.mkdir(parents=True, exist_ok=False)
    cases = matrix()
    write_json(out / "matrix.json", {"fields": field_rows(), "cases": cases})
    template = writer_control(out)
    assigned = {
        (t["arm"], t["case_id"])
        for t in json.loads((template / "ledger.json").read_text())["trials"]
    }
    positive = {"name": "writer_positive", "outcome": "pass", "role": None, "disposition": None}
    observations = [inspect_case(template, positive, assigned)]
    for case in cases:
        root = out / "mutations" / case["name"]
        shutil.copytree(
            template,
            root,
            ignore=shutil.ignore_patterns("attempts", "report.json", "stdout.log", "stderr.log"),
        )
        mutate(root, case)
        observations.append(inspect_case(root, case, assigned))
    summary = {
        "schema": "nisayon.execution-contract-conformance.v1",
        "tested_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "checker_sha256": file_digest(Path(__file__)),
        "case_count": len(observations),
        "passed": sum(not r["failures"] for r in observations),
        "failed": sum(bool(r["failures"]) for r in observations),
        "observations": observations,
    }
    write_json(out / "summary.json", summary)
    write_json(
        out / "files.json",
        {
            str(p.relative_to(out)): {"sha256": file_digest(p), "bytes": p.stat().st_size}
            for p in sorted(out.rglob("*"))
            if p.is_file()
        },
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.out)
    print(json.dumps({k: v for k, v in result.items() if k != "observations"}))
    for row in result["observations"]:
        if row["failures"]:
            print(row["name"], "; ".join(row["failures"]))
    raise SystemExit(bool(result["failed"]))
