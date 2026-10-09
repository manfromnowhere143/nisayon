"""Paired public-CLI controls for omitted fields required by the revised contract."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.evaluation.prospective_fixtures import prospective_ledger, write_prospective_ledger


def replace(path: Path, document: dict) -> str:
    path.write_text(json.dumps(document, indent=2) + "\n")
    return file_digest(path)


def audit(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    observations = []
    for variant in (
        "positive",
        "start_observed_absent",
        "result_observed_absent",
        "start_candidate_absent",
        "start_scope_absent",
        "declaration_suite_absent",
        "declaration_frozen_inputs_absent",
    ):
        root = out / variant
        ledger_path = write_prospective_ledger(prospective_ledger(), root)
        ledger = json.loads(ledger_path.read_text())
        trial = next(
            t for t in ledger["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01")
        )
        declaration_path = root / trial["declaration"]["path"]
        start_path = root / trial["terminal_start"]["path"]
        result_path = root / trial["terminal_result"]["path"]
        declaration = json.loads(declaration_path.read_text())
        start = json.loads(start_path.read_text())
        result = json.loads(result_path.read_text())
        if variant.startswith("declaration_"):
            key = "suite_id" if variant == "declaration_suite_absent" else "frozen_inputs_sha256"
            del declaration["assignment"][key]
            start["assignment"] = declaration["assignment"]
            result["assignment"] = declaration["assignment"]
            digest = replace(declaration_path, declaration)
            trial["declaration"]["sha256"] = digest
            start["declaration"]["sha256"] = digest
            result["declaration"]["sha256"] = digest
        elif variant == "start_observed_absent":
            del start["observed"]
        elif variant == "result_observed_absent":
            del result["observed"]
        elif variant == "start_candidate_absent":
            del start["candidate"]
        elif variant == "start_scope_absent":
            del start["evidence_scope"]
        digest = replace(start_path, start)
        trial["terminal_start"]["sha256"] = digest
        result["terminal_start"]["sha256"] = digest
        trial["terminal_result"]["sha256"] = replace(result_path, result)
        replace(ledger_path, ledger)
        command = [
            sys.executable,
            "-m",
            "nisayon.evaluation",
            "prospective",
            str(ledger_path),
            "--root",
            str(root),
            "--out",
            str(root / "report.json"),
        ]
        process = subprocess.run(command, capture_output=True, timeout=30, check=False)
        (root / "stdout.log").write_bytes(process.stdout)
        (root / "stderr.log").write_bytes(process.stderr)
        assert process.returncode in (0, 1), process.stderr
        report = json.loads((root / "report.json").read_text())
        entry = next(
            t for t in report["trials"] if t["arm"] == "A" and t["case_id"].startswith("D01")
        )
        observations.append(
            {
                "variant": variant,
                "returncode": process.returncode,
                "fair": report["fair"],
                "prospective": entry["prospective"],
                "ordering": entry["ordering"],
                "eligibility": report.get("eligibility"),
                "reference": entry["reference"],
                "claim_category": entry["claim_category"],
                "findings": report["findings"],
                "report_sha256": file_digest(root / "report.json"),
            }
        )
    result = {
        "schema": "nisayon.integration-required-fields-probe.v1",
        "scope": "Labelled synthetic fixtures only; outer hashes re-bound so semantic checks run",
        "expected": "Positive remains valid; required-field omissions cannot qualify as prospective",
        "observations": observations,
    }
    write_json(out / "summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.out)
    print(json.dumps(result, indent=2))
