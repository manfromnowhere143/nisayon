"""Retain one exposed native comparison and its unchanged-SDK qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
ART = ROOT / "artifacts/camera-slot-qualification-2026-10-28"
PYTHON = ART / "env/bin/python"
ARMS = ("base", "pr5129", "pr5120", "pr5120_base")


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(path):
    return {str(p.relative_to(path)): digest(p) for p in sorted(path.rglob("*")) if p.is_file()}


def verify():
    freeze = json.loads((PACKET / "freeze.json").read_text())
    for name, expected in freeze["study_files"].items():
        assert digest(PACKET / name) == expected, f"Study file changed: {name}"
    for name, expected in freeze["owner_files"].items():
        assert files(ART / "owners" / name) == expected, f"Owner source changed: {name}"


def prepare():
    native = json.loads((PACKET / "source-downloads.json").read_text())
    manifest = {}
    for arm in ARMS:
        source = ART / "sources" / arm
        retained = next(x for x in native if x["name"] == arm)["files"]
        assert files(source) == retained, f"Downloaded source changed: {arm}"
        owner = ART / "owners" / arm
        owner.mkdir(parents=True, exist_ok=False)
        # Upstream src contains documentation symlinks into the unexported docs
        # tree. They are outside this source subset and not runtime inputs.
        for link in source.rglob("*"):
            if link.is_symlink():
                assert link.suffix in (".md", ".mdx"), f"Unreviewed source symlink: {link}"
        for filename in retained:
            original = source / filename
            assert not original.is_symlink(), f"Unexpected declared symlink: {filename}"
            target = owner / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
        for filename in ("entry.py", "camera_contract.py"):
            shutil.copyfile(PACKET / filename, owner / filename)
        manifest[arm] = files(owner)
        assert len(manifest[arm]) <= 1024
    names = (
        "intake.json",
        "protocol.json",
        "constraints.in",
        "requirements.lock",
        "source-downloads.json",
        "camera_contract.py",
        "entry.py",
        "native_run.py",
        "run_study.py",
    )
    write(
        PACKET / "freeze.json",
        {
            "created_at": datetime.now(UTC).isoformat(),
            "study_files": {name: digest(PACKET / name) for name in names},
            "owner_files": manifest,
            "scope": "Public remedies and author tests are exposed; no unseen-owner claim.",
        },
    )
    print(json.dumps({"prepared": {arm: len(v) for arm, v in manifest.items()}}))


def native():
    verify()
    destination = PACKET / "native-01"
    destination.mkdir(exist_ok=False)
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        CUDA_VISIBLE_DEVICES="",
        OMP_NUM_THREADS="1",
    )
    records = []
    for arm in ARMS:
        for seed in (17, 67):
            identifier = f"{arm}-{seed}"
            command = [
                str(PYTHON),
                "-B",
                str(PACKET / "native_run.py"),
                str(ART / "owners" / arm),
                str(seed),
                str(destination / identifier),
            ]
            row = {
                "arm": arm,
                "seed": seed,
                "command": command,
                "started_at": datetime.now(UTC).isoformat(),
                "status": "running",
            }
            records.append(row)
            write(destination / "commands.json", records)
            start = time.perf_counter()
            with (destination / f"{identifier}.log").open("w") as out:
                try:
                    result = subprocess.run(
                        command, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=120
                    )
                    row.update(returncode=result.returncode, status="completed")
                except subprocess.TimeoutExpired:
                    row.update(returncode=None, status="timed_out")
            row["whole_process_seconds"] = time.perf_counter() - start
            write(destination / "commands.json", records)
            print(
                json.dumps(
                    {
                        k: row[k]
                        for k in ("arm", "seed", "status", "returncode", "whole_process_seconds")
                    }
                ),
                flush=True,
            )
            if row["returncode"] != 0:
                raise SystemExit("Invalid native attempt retained; inspect before an amendment")
    verify()


def sdk():
    from nisayon.qualification import (
        CaseSpec,
        ExecutionContext,
        assess_change,
        export_run,
        inspect_bundle,
        plan_change,
        run_plan,
    )

    verify()
    destination = PACKET / "sdk-01"
    destination.mkdir(exist_ok=False)
    # All labels are recomputed from retained executions. These are distinct
    # contract questions, never a pooled winner across incompatible semantics.
    assignments = (
        ("base", "configured_budget", "all"),
        ("pr5129", "configured_budget", "all"),
        ("pr5120", "configured_budget", "changed_three"),
        ("pr5120", "all_configured_slots", "changed_three"),
        ("pr5129", "all_configured_slots", "all"),
    )
    records = []
    for arm, mode, scope in assignments:
        identifier = f"{arm}-{mode}-{scope}"
        owner = ART / "owners" / arm
        expected_probes = []
        for seed in (17, 67):
            expected = json.loads(
                (PACKET / "native-01" / f"{arm}-{seed}" / f"expected-{mode}.json").read_text()
            )
            if scope == "changed_three":
                expected["conditions"] = [
                    row
                    for row in expected["conditions"]
                    if row["id"].split("-", 1)[0] in ("pi0", "pi05", "smolvla")
                ]
            expected_probes.append(
                {
                    "id": f"seed-{seed}",
                    "input": {"seed": seed, "mode": mode, "scope": scope},
                    "expected": expected,
                }
            )
        required = ["pi0_method", "pi05_method", "smol_method"]
        if scope == "all":
            required += ["fast_method", "xvla_method", "evo_method"]
        case = CaseSpec.from_dict(
            {
                "schema": "nisayon.qualification.case.v1",
                "id": identifier,
                "question": f"Does {arm} satisfy {mode} for the declared {scope} camera methods?",
                "contract": {"kind": "exact"},
                "source_files": sorted(files(owner)),
                "targets": {
                    "reference": {"path": "entry.py", "callable": "reference"},
                    "negative_control": {"path": "entry.py", "callable": "negative_control"},
                    "candidate": {
                        "path": "entry.py",
                        "callable": "candidate",
                        "required_calls": required,
                    },
                },
                "premises": {
                    "population": "Finite exposed CPU camera preprocessing matrix, two declared seeds; no robot task inference.",
                    "state": "fresh_process",
                    "environment": "Locked Python 3.12 / Torch 2.7.1 macOS arm64 CPU environment; imported unchanged native methods on a declared configuration shim, no model construction.",
                    "oracle": "Frozen independent software contract; no physical or owner acceptance authority.",
                },
                "probes": expected_probes,
            }
        )
        (destination / f"{identifier}-case.json").write_text(
            json.dumps(case.record(), indent=2) + "\n"
        )
        context = ExecutionContext.from_project(
            owner,
            output_dir=ART / "sdk-runs" / identifier,
            python=PYTHON,
            timeout_seconds=120,
            total_seconds=1200,
        )
        started = time.perf_counter()
        plan = plan_change(case, context=context)
        (destination / f"{identifier}-plan.json").write_text(
            json.dumps(plan.record(), indent=2) + "\n"
        )
        evidence = run_plan(plan, context=context)
        assessment = assess_change(case, evidence)
        assessment.write(destination / f"{identifier}-assessment.json")
        bundle = ART / f"{identifier}.zip"
        export_receipt = export_run(context.output_dir, bundle)
        review = inspect_bundle(bundle)
        write(destination / f"{identifier}-export.json", export_receipt)
        write(destination / f"{identifier}-review.json", review)
        row = {
            "arm": arm,
            "mode": mode,
            "scope": scope,
            "plan_execute_assess_export_review_seconds": time.perf_counter() - started,
            "assessment": assessment.record(),
            "bundle_sha256": digest(bundle),
        }
        records.append(row)
        write(destination / "summary.json", records)
        print(
            json.dumps(
                {
                    "arm": arm,
                    "mode": mode,
                    "scope": scope,
                    "seconds": row["plan_execute_assess_export_review_seconds"],
                    "assessment": row["assessment"],
                }
            ),
            flush=True,
        )
    verify()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "native", "sdk"))
    args = parser.parse_args()
    {"prepare": prepare, "native": native, "sdk": sdk}[args.phase]()
