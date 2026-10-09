"""Measure the bounded conventional-baseline qualification and monitor one check."""

import argparse
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

from nisayon.engine.io import write_json

SPEC = importlib.util.spec_from_file_location(
    "external_resource_check",
    Path("docs/experiments/results/external-decision-001/resource_check.py"),
)
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
monitor = previous.monitor
previous_snapshot = previous.snapshot

PHASE_START = "2026-09-20T15:51:10.626540+00:00"
START_COMMIT = "34bda84fb79dd6b99eadb4f81306a9418ab237d8"
ARTIFACT_ROOT = Path("artifacts/baseline-qualification-001").resolve()
PHASE_OUTSIDE_FILE = Path(
    "/private/tmp/nisayon-baseline-qualification-start-resource.json"
).resolve()
INHERITED_OUTSIDE_FILES = (
    Path("/private/tmp/nisayon-interrupted-inspect.json").resolve(),
    Path("/private/tmp/nisayon-evaluation-identity-audit.txt").resolve(),
)
SOURCE_BYTES = 11_421
SOURCE_CAP = 256 * 1024
ARTIFACT_CAP = 16 * 1024**2
SHARED_TEMP_CAP = 512 * 1024**2
CLOSEOUT_RECORD_RESERVE = 1024**2


def _phase_commands() -> set[Path]:
    payload: set[Path] = set()
    for record_path in Path(".nisayon/runs").glob("*/run.json"):
        record = json.loads(record_path.read_text())
        if record["started_at"] >= PHASE_START and record["cwd"] == str(Path.cwd().resolve()):
            payload.update(monitor.files_under(record_path.parent))
    return payload


def _phase_changed() -> set[Path]:
    names = subprocess.check_output(
        ["git", "diff", "--name-only", f"{START_COMMIT}..HEAD"], text=True
    ).splitlines()
    names += subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], text=True
    ).splitlines()
    return {Path(name).resolve() for name in names if Path(name).is_file()}


def _declared_monitor_roots() -> set[Path]:
    roots: set[Path] = set()
    for intent in Path("artifacts/engine-integration-001/monitor-intents").glob("*.json"):
        roots.add(Path(json.loads(intent.read_text())["temporary_root"]).resolve())
    return roots


def _entry(path: Path, declared: set[Path]) -> dict:
    files = monitor.files_under(path)
    resolved = path.resolve()
    if resolved == PHASE_OUTSIDE_FILE:
        ownership = "phase_owned_retained_diagnostic"
    elif resolved in INHERITED_OUTSIDE_FILES:
        ownership = "inherited_retained_evidence"
    elif resolved in declared:
        ownership = "declared_monitor_root"
    else:
        ownership = "preexisting_unattributed_not_charged_to_phase"
    return {
        "path": str(resolved),
        "kind": "directory" if resolved.is_dir() else "file",
        "files": len(files),
        "logical_bytes": monitor.size(files),
        "ownership": ownership,
        "outside_monitor": resolved not in declared,
        "git_checkout": resolved.is_dir() and (resolved / ".git").exists(),
    }


def temporary_inventory() -> dict:
    declared = _declared_monitor_roots()
    parents = {Path("/private/tmp").resolve(), Path(tempfile.gettempdir()).resolve()}
    roots: set[Path] = set()
    for parent in parents:
        if not parent.exists():
            continue
        roots.update(path.resolve() for path in parent.glob("nisayon-*"))
        roots.update(path.resolve() for path in parent.glob("pytest-of-*"))
    entries = [_entry(path, declared) for path in sorted(roots)]
    outside = [item for item in entries if item["outside_monitor"]]
    return {
        "parents": [str(path) for path in sorted(parents)],
        "entries": entries,
        "entry_count": len(entries),
        "all_logical_bytes": sum(item["logical_bytes"] for item in entries),
        "outside_monitor_logical_bytes": sum(item["logical_bytes"] for item in outside),
        "declared_monitor_logical_bytes": sum(
            item["logical_bytes"] for item in entries if not item["outside_monitor"]
        ),
        "outside_monitor_fingerprint": [
            [item["path"], item["files"], item["logical_bytes"], item["ownership"]]
            for item in outside
        ],
        "scope": "Top-level nisayon-* and pytest-of-* roots under /private/tmp and the active platform temporary directory. Logical bytes exclude symlinks; no item is deleted.",
    }


def snapshot() -> dict:
    result = previous_snapshot()
    counted_roots = [Path(path).resolve() for path in result["counted_roots"]]
    assert not any(
        ARTIFACT_ROOT == root
        or ARTIFACT_ROOT.is_relative_to(root)
        or root.is_relative_to(ARTIFACT_ROOT)
        for root in counted_roots
    )
    artifact_files = set(monitor.files_under(ARTIFACT_ROOT))
    result["counted_roots"].append(str(ARTIFACT_ROOT))
    result["retained_payload_bytes"] += monitor.size(list(artifact_files))

    outside_files = {
        path for path in (*INHERITED_OUTSIDE_FILES, PHASE_OUTSIDE_FILE) if path.is_file()
    }
    result["retained_payload_bytes"] += monitor.size(list(outside_files))
    result["retained_payload_bytes"] += CLOSEOUT_RECORD_RESERVE

    phase_payload = artifact_files | _phase_commands() | _phase_changed()
    if PHASE_OUTSIDE_FILE.is_file():
        phase_payload.add(PHASE_OUTSIDE_FILE)
    result["baseline_qualification_retained_bytes"] = monitor.size(list(phase_payload))
    result["baseline_qualification_artifact_cap_bytes"] = ARTIFACT_CAP
    result["baseline_qualification_source_bytes"] = SOURCE_BYTES
    result["baseline_qualification_source_cap_bytes"] = SOURCE_CAP
    result["cumulative_source_download_bytes"] = 4_374_474 + SOURCE_BYTES
    result["closeout_record_reserve_bytes"] = CLOSEOUT_RECORD_RESERVE
    result["temporary_inventory"] = temporary_inventory()
    result["scope"] += (
        " Baseline-qualification artifacts, commands and changed files are counted, as are "
        "the three retained /private/tmp evidence files and a 1 MiB closeout-record reserve."
    )
    return result


monitor.snapshot = snapshot


def validate(result: dict, *, full_check: bool) -> dict:
    phase = result["baseline"] if full_check else result
    assert phase["baseline_qualification_retained_bytes"] < ARTIFACT_CAP
    assert phase["baseline_qualification_source_bytes"] < SOURCE_CAP
    assert phase["cumulative_source_download_bytes"] < 64 * 1024**2
    assert phase["retained_payload_bytes"] < monitor.CAP - monitor.TEMP_LIMIT
    assert phase["free_disk_bytes"] > monitor.FREE_MINIMUM
    inventory = phase["temporary_inventory"]
    assert inventory["outside_monitor_logical_bytes"] + monitor.TEMP_LIMIT < SHARED_TEMP_CAP
    result["shared_temporary_cap_bytes"] = SHARED_TEMP_CAP
    result["temporary_suballocation_bytes"] = monitor.TEMP_LIMIT
    if full_check:
        post = snapshot()
        before = inventory["outside_monitor_fingerprint"]
        after = post["temporary_inventory"]["outside_monitor_fingerprint"]
        assert before == after
        result["outside_monitor_temporary_unchanged"] = True
        result["combined_existing_outside_temp_plus_sampled_peak_bytes"] = (
            inventory["outside_monitor_logical_bytes"] + result["sampled_peak_temporary_bytes"]
        )
        assert result["combined_existing_outside_temp_plus_sampled_peak_bytes"] < SHARED_TEMP_CAP
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full-check", action="store_true")
    parser.add_argument("--temporary-limit-mib", type=int, choices=range(1, 513), default=224)
    args = parser.parse_args()
    monitor.TEMP_LIMIT = args.temporary_limit_mib * 1024**2
    result = monitor.full_check() if args.full_check else snapshot()
    validate(result, full_check=args.full_check)
    write_json(args.out, result)
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}))
    raise SystemExit(result.get("returncode", 0))
