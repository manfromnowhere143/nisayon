"""Bind the finite campaign through existing SDK checks and portable bundles.

These handlers review retained observations. Always-run confirmation is fresh
analysis of separately executed conditions, never a claim of fresh simulation.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import zipfile
from pathlib import Path

from audit_hardening import decode, strict_trial

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import DependencyModel, EvidenceState, execute_checks, inspect_checks
from nisayon.qualification.check_bundle import export_checks, inspect_check_bundle

HERE = Path(__file__).resolve().parent
SCOPE = "Finite constant-force block campaign; retained data and model-relative decisions. No population or hardware acceptance."


def observe(ctx):
    cases = {c["id"]: c for c in ctx.input("physical")}
    protocol = ctx.input("protocol")
    runtime = ctx.input("runtime")
    if ctx.input("population") != {
        "tasks": protocol["tasks"],
        "confirmation_tasks": protocol["confirmation_tasks"],
    }:
        raise ValueError("population differs from frozen protocol")
    if runtime["origin"] != "local_cpu_retained_records":
        raise ValueError("unsupported runtime claim")
    rows = []
    with zipfile.ZipFile(io.BytesIO(ctx.input_bytes("data"))) as archive:
        names = archive.namelist()
        if (
            len(names) != 264
            or len(set(names)) != len(names)
            or sum(i.file_size for i in archive.infolist()) > 32 * 1024**2
        ):
            raise ValueError("unexpected campaign membership or size")
        for name in names:
            if (
                not name.startswith("trial-")
                or not name.endswith(".json")
                or Path(name).name != name
            ):
                raise ValueError("unexpected campaign member")
            row = decode(archive.read(name))
            rows.append(strict_trial(row, cases[row["case"]], protocol))
    expected = {
        (c, b, m, s)
        for c in cases
        for b in protocol["budgets_control_steps"]
        for m in protocol["methods"]
        for s in (protocol["random_seeds"] if m == "random" else [0])
    }
    actual = {(r["case"], r["budget"], r["method"], r["seed"]) for r in rows}
    if expected != actual or len(actual) != len(rows):
        raise ValueError("campaign assignment mismatch")
    return {"rows": rows, "new_simulation": False}


def score(ctx):
    definition = ctx.input("measurement")
    if definition != {
        "version": 1,
        "endpoint_tolerance_m": 0.01,
        "noninferiority_epsilon": 0,
        "population": "eight frozen diagnostic conditions",
    }:
        raise ValueError("unqualified measurement or acceptance semantics")
    rows = ctx.upstream("observe")["rows"]
    harmful = sum(r["harmful_admission"] for r in rows)
    return {
        "harmful_admissions": harmful,
        "valid_trials": len(rows),
        "scope": SCOPE,
        "outcome": "supported" if harmful == 0 else "contradicted",
    }


def confirm(ctx):
    rows, protocol = ctx.upstream("observe")["rows"], ctx.input("protocol")
    required = len(protocol["confirmation_tasks"])
    if any(r["decision"] == "supported" and r["confirmation_pairs"] != required for r in rows):
        raise ValueError("approval lacks separately executed confirmation")
    return {"all_approvals_confirmed": True, "new_simulation": False, "fresh_analysis_only": True}


def review(ctx):
    score, confirmation = ctx.upstream("score"), ctx.upstream("confirm")
    return {
        "verdict": score["outcome"] if confirmation["all_approvals_confirmed"] else "unresolved",
        "scope": SCOPE,
        "general_acquisition_advantage": "not_supported",
        "deployment_decision": "unresolved",
    }


def model(root: Path) -> DependencyModel:
    value = {
        "schema": "nisayon.qualification.dependencies.v1",
        "id": "edpi-finite-retained-review",
        "scope": SCOPE,
        "inputs": {
            key: {"kind": kind, "description": key}
            for key, kind in {
                "physical": "data",
                "protocol": "protocol",
                "population": "population",
                "runtime": "runtime",
                "measurement": "scoring",
                "data": "data",
                "procedure": "code",
            }.items()
        },
        "checks": {
            "observe": {
                "kind": "observation",
                "depends_on": [
                    "physical",
                    "protocol",
                    "population",
                    "runtime",
                    "data",
                    "procedure",
                ],
                "refresh": "on_change",
            },
            "score": {
                "kind": "analysis",
                "depends_on": ["observe", "measurement"],
                "refresh": "on_change",
            },
            "confirm": {
                "kind": "confirmation",
                "depends_on": ["observe", "protocol"],
                "refresh": "always",
            },
            "review": {
                "kind": "review",
                "depends_on": ["score", "confirm"],
                "refresh": "on_change",
            },
        },
        "decisions": {"retained_model_relation": {"depends_on": ["review"], "description": SCOPE}},
        "review": None,
    }
    first = DependencyModel.from_dict(value)
    reviewer = "development-context source and retained-record inspection"
    write_json(
        root / "model-review.json",
        {
            "schema": "nisayon.qualification.dependency_review.v1",
            "definition_sha256": first.definition_sha256,
            "reviewer": reviewer,
            "coverage": "reviewed_for_declared_scope",
            "statement": "Explicit finite inputs and current checker source. No independent human review, hidden-case benchmark, physical authenticity or complete dependency guarantee.",
        },
    )
    value["review"] = {
        "definition_sha256": first.definition_sha256,
        "reviewer": reviewer,
        "artifact": {
            "path": "model-review.json",
            "sha256": file_digest(root / "model-review.json"),
        },
    }
    return DependencyModel.from_dict(value)


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(root / "raw.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(args.source.glob("trial-*.json")):
            archive.write(path, path.name)
    values = {
        "physical": decode((HERE / "case-inputs.json").read_bytes()),
        "protocol": decode((HERE / "campaign-protocol.json").read_bytes()),
        "runtime": {
            "origin": "local_cpu_retained_records",
            "execution_authenticity": "not_authenticated",
        },
        "measurement": {
            "version": 1,
            "endpoint_tolerance_m": 0.01,
            "noninferiority_epsilon": 0,
            "population": "eight frozen diagnostic conditions",
        },
    }
    values["population"] = {key: values["protocol"][key] for key in ("tasks", "confirmation_tasks")}
    declaration, previous, results = model(root), None, []
    for name in (
        "baseline",
        "unchanged",
        "physical_changed",
        "physical_unknown",
        "measurement_changed",
        "corrupt_data",
    ):
        current = copy.deepcopy(values)
        if name == "physical_changed":
            current["physical"][0]["candidate"]["friction"] = 0.31
        if name == "measurement_changed":
            current["measurement"]["endpoint_tolerance_m"] = 0.02
        paths = {"data": root / "raw.zip"}
        for key, value in current.items():
            path = root / "declarations" / name / f"{key}.json"
            write_json(path, value)
            paths[key] = path
        if name == "physical_unknown":
            paths["physical"] = None
        if name == "corrupt_data":
            paths["data"] = root / "corrupt.zip"
            paths["data"].write_bytes(b"deliberately invalid archive")
        execution = execute_checks(
            declaration,
            inputs=paths,
            handlers={"observe": observe, "score": score, "confirm": confirm, "review": review},
            implementation_files=[
                HERE / p
                for p in (
                    "sdk_review.py",
                    "audit_hardening.py",
                    "audit_campaign.py",
                    "reference.py",
                )
            ],
            evidence_root=root,
            output=root / name,
            previous=previous,
            allow_partial=True,
        )
        inspected = inspect_checks(evidence_root=root, output=root / name)
        verdict = inspected["artifacts"].get("review", {}).get("verdict", "unresolved")
        expected = "supported" if name in ("baseline", "unchanged") else "unresolved"
        if verdict != expected:
            raise ValueError(f"SDK control {name}: {verdict}, expected {expected}")
        results.append(
            {
                "case": name,
                "execution_status": execution["status"],
                "review_status": inspected["status"],
                "verdict": verdict,
                "actions": {r["check"]: r["action"] for r in execution["attempts"]},
                "errors": execution["errors"],
            }
        )
        if name == "baseline":
            previous = EvidenceState.from_dict(execution["state"])
    exported = export_checks(evidence_root=root, execution=root / "unchanged", output=args.bundle)
    inspected = inspect_check_bundle(args.bundle)
    write_json(
        root / "summary.json",
        {
            "schema": "nisayon.edpi.sdk-controls.v1",
            "rows": results,
            "export": exported,
            "portable_review": inspected,
            "scope": SCOPE,
        },
    )
    print(json.dumps({"controls": len(results), "export": exported}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
