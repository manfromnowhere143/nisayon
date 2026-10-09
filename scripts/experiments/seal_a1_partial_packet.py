"""Seal the A1 rights-stop evidence as a private, content-bound packet."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.store import create_manifest, verify_manifest

CASE = "a1-pilot-001"
SCHEMA = "nisayon.a1-partial-execution-seal.v1"
DURABLE_CAP = 16 * 1024**2
EVALUATION_ROOT = Path("/Users/danielwahnich/workspace/nisayon-fable5")

COMMAND_IDS = (
    "49d9e1a2848448bb8c1126c6109c70ad",
    "1156c2e13abd443197111cbce8755fb6",
    "75c174ddc04c4785a6defa6f2f8ccc2d",
    "0e7d7712506e4079b0efa8e7f5e75de8",
    "9fcad3d864b145aea47025c8664f3d3a",
    "1ccbf3ef78fc4bf59f20b16a332d49fd",
    "ccb40bc631f24928a3e21ea0bb20cff1",
    "bcdb8e8505af40f6812e644dcd0e3f99",
    "81b00b6264834bae9aea1f7e402035ea",
    "2b0cffceb6c947fdb26d6500f65d1f93",
    "ee09a9d9c584414f930bb881143cbc19",
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _identity(path: Path, *, display: str | None = None) -> dict[str, Any]:
    return {
        "path": display or str(path),
        "bytes": path.stat().st_size,
        "sha256": file_digest(path),
    }


def _copy_entries(output: Path, entries: list[tuple[Path, str]]) -> None:
    destinations = [destination for _, destination in entries]
    if len(destinations) != len(set(destinations)):
        raise ValueError("Packet destinations must be unique")
    for source, destination in entries:
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Packet input must be a regular file: {source}")
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)


def seal_packet(
    output: Path,
    entries: list[tuple[Path, str]],
    *,
    invocation: dict[str, Any],
    summary: dict[str, Any],
    durable_cap: int = DURABLE_CAP,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    _copy_entries(output, entries)
    write_json(output / "invocation.json", invocation)
    write_json(output / "summary.json", summary)
    members = [path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()]
    manifest = create_manifest(output, members)
    before_seal = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    if before_seal > durable_cap:
        raise ValueError("A1 partial packet exceeds the durable-output cap")
    seal = {
        "schema": SCHEMA,
        "case": CASE,
        "sealed_at": datetime.now(UTC).isoformat(),
        "source_commit": invocation["source"]["execution_commit"],
        "status": "partial_execution_stopped_before_dataset_get",
        "summary": _identity(output / "summary.json", display="summary.json"),
        "invocation": _identity(output / "invocation.json", display="invocation.json"),
        "artifact_manifest": manifest,
        "retained_logical_bytes_before_seal": before_seal,
        "durable_cap_bytes": durable_cap,
        "absent_by_design": [
            "dataset body",
            "training configuration",
            "normalization statistics",
            "model checkpoint",
            "optimizer state",
            "rollout or task outcome",
        ],
        "premise": "Integrity binds retained bytes; independent assessment decides correctness.",
    }
    write_json(output / "seal.json", seal)
    members_readback = verify_manifest(output, manifest)
    if set(members_readback) != set(members):
        raise ValueError("Manifest readback changed member identity")
    retained = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    if retained > durable_cap:
        raise ValueError("A1 partial packet exceeds the durable-output cap after sealing")
    return {
        "schema": "nisayon.a1-partial-execution-readback.v1",
        "store": str(output.resolve()),
        "seal_sha256": file_digest(output / "seal.json"),
        "manifest_sha256": manifest["sha256"],
        "summary_sha256": file_digest(output / "summary.json"),
        "manifest_files": len(members_readback),
        "retained_bytes": retained,
        "status": seal["status"],
    }


def build_packet(output: Path) -> dict[str, Any]:
    root = Path.cwd().resolve()
    if _git(root, "status", "--porcelain=v1"):
        raise ValueError("Execution worktree must be clean before sealing")
    evaluation_head = _git(EVALUATION_ROOT, "rev-parse", "HEAD")
    if _git(EVALUATION_ROOT, "status", "--porcelain=v1"):
        raise ValueError("Evaluation worktree must be clean before copying its freeze")

    result_root = root / "docs/experiments/results/a1-feasibility-001"
    artifact_root = root / "artifacts/a1-feasibility-001"
    evaluation_result = EVALUATION_ROOT / "docs/evaluation/results/a1-pilot-001"
    entries: list[tuple[Path, str]] = []
    for name in (
        "phase-start.json",
        "authorization.v1.json",
        "acquisition-protocol.v1.json",
        "source-ledger.v1.json",
        "pilot-readiness-001.json",
        "execution-delivery-001.json",
        "README.md",
    ):
        entries.append((result_root / name, f"inputs/execution/{name}"))
    for name in ("PILOT_ACCEPTANCE.md", "pilot-acceptance.v1.json"):
        entries.append((evaluation_result / name, f"inputs/evaluation/{name}"))
    for path in sorted((artifact_root / "sources").iterdir()):
        entries.append((path, f"inputs/rights/{path.name}"))
    for name in (
        "acquisition-assessment-001.json",
        "resource-preflight-001.json",
        "resource-after-delivery-001.json",
    ):
        entries.append((artifact_root / name, f"results/{name}"))
    for command_id in COMMAND_IDS:
        command_root = root / ".nisayon/runs" / command_id
        for name in ("run.json", "stdout.log", "stderr.log"):
            entries.append((command_root / name, f"commands/{command_id}/{name}"))
    for name in (
        "scripts/experiments/assess_a1_acquisition.py",
        "scripts/experiments/seal_a1_partial_packet.py",
        "tests/engine/test_a1_acquisition.py",
        "pyproject.toml",
        "uv.lock",
    ):
        entries.append((root / name, f"source/{name}"))

    delivery = json.loads((result_root / "execution-delivery-001.json").read_text())
    assessment = json.loads((artifact_root / "acquisition-assessment-001.json").read_text())
    execution_head = _git(root, "rev-parse", "HEAD")
    invocation = {
        "schema": "nisayon.a1-partial-execution-invocation.v1",
        "declared_at": datetime.now(UTC).isoformat(),
        "source": {
            "execution_commit": execution_head,
            "execution_branch": _git(root, "branch", "--show-current"),
            "evaluation_freeze_commit": evaluation_head,
            "dependency_lock_sha256": file_digest(root / "uv.lock"),
            "gate_script_sha256": file_digest(
                root / "scripts/experiments/assess_a1_acquisition.py"
            ),
            "sealer_script_sha256": file_digest(
                root / "scripts/experiments/seal_a1_partial_packet.py"
            ),
        },
        "network_during_seal": 0,
        "dataset_body_requests_during_seal": 0,
        "policy_or_simulator_execution_during_seal": False,
        "command_record_id": os.environ.get("NISAYON_COMMAND_RECORD_ID"),
        "command_record_root": os.environ.get("NISAYON_COMMAND_RECORD_ROOT"),
    }
    summary = {
        "schema": "nisayon.a1-partial-execution-summary.v1",
        "case": CASE,
        "status": "stopped_before_dataset_get",
        "decision": delivery["decision"],
        "named_missing_requirement": delivery["named_missing_requirement"],
        "gate_result": assessment["decision"],
        "dataset_get_authorized_by_gate": assessment["dataset_get_authorized_by_gate"],
        "official_object": assessment["official_repository"],
        "pinned_object": assessment["pinned_stanford_object"],
        "checks": assessment["checks"],
        "workload": delivery["workload"],
        "claim_levels": delivery["claim_levels"],
        "known_costs": delivery["known_costs"],
        "unknown_costs": delivery["unknown_costs"],
        "failures": delivery["failures"],
        "resource_preflight": delivery["resource_preflight"],
        "ready_to_execute": False,
        "executed": False,
        "independent_assessment": "pending",
        "producer_authority": "Execution evidence for independent evaluation; not acceptance.",
    }
    readback = seal_packet(output, entries, invocation=invocation, summary=summary)
    if _git(EVALUATION_ROOT, "rev-parse", "HEAD") != evaluation_head or _git(
        EVALUATION_ROOT, "status", "--porcelain=v1"
    ):
        raise ValueError("Evaluation freeze changed while the packet was copied")
    return readback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_packet(args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
