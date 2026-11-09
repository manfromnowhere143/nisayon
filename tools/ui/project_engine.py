"""Publish a bounded read-only projection of admitted engine evidence.

Verification runs in the engine's pinned interpreter. No simulation or evaluator
is executed. Immutable objects are written before the discovery pointer moves.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from project_mechanisms import mechanism_reports

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nisayon.ui_export.source import project_private_paths  # noqa: E402

REPORTS = {
    "external": "docs/experiments/results/decision-case-001/combined-foreign.json",
    "recovery": "docs/experiments/results/confirmation-engine-001/recovery.json",
    "decision_case": "docs/experiments/results/decision-case-001/post-scope-pair-scores.json",
    "declaration_score": "docs/experiments/results/decision-case-001/combined-native.json",
}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def public(value):
    value = project_private_paths(value, [])
    text = encoded(value).decode()
    if re.search(r"/(?:Users|home|private|var/folders)/", text):
        raise ValueError("Projection contains a private filesystem locator")
    return value


def atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def put(root: Path, value, kind="objects"):
    data = encoded(public(value)) + b"\n"
    if len(data) > 16_777_216:
        raise ValueError("Projected object exceeds the admission limit")
    sha = digest(data)
    path = f"{kind}/{sha}.json"
    target = root / path
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError("Immutable object was changed")
    else:
        atomic(target, data)
    return {"path": path, "sha256": sha, "byte_length": len(data)}


def verify(engine: Path, directory: Path, interpreter: Path):
    # Separate import graph: the UI worktree intentionally has older engine
    # modules. Never validate current evidence with those modules by accident.
    code = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1] + '/src')
from nisayon.engine.confirmation_view import load_export
view, status = load_export(Path(sys.argv[2]), Path(sys.argv[1]))
print(json.dumps(status))
sys.exit(0 if status['status'] == 'current' else 2)
"""
    process = subprocess.run(
        [str(interpreter), "-c", code, str(engine), str(directory)],
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if process.returncode:
        # Keep detailed source diagnostics in the local receipt, never in a feed.
        raise ValueError(
            "Engine export failed current-source verification: " + process.stdout[:2000]
        )
    status = json.loads(process.stdout)
    if status != {"status": "current", "issues": []}:
        raise ValueError("Engine verification did not admit this export")
    return status


def retained_declarations(engine: Path):
    location = engine / "docs/experiments/results/retained-declarations-001/retained-location.json"
    if not location.exists():
        return {}
    manifest = json.loads(location.read_bytes())
    source = Path(manifest["root_locator"]).resolve()
    output = {}
    for entry in manifest["records"]:
        if not entry["path"].endswith(
            (
                "/declaration/declaration.json",
                "/declaration/terminal-start.json",
                "/declaration/terminal-result.json",
                "/demonstration-row.json",
            )
        ):
            continue
        path = (source / entry["path"]).resolve()
        if not path.is_relative_to(source) or path.is_symlink():
            raise ValueError("Declaration path leaves its retained root")
        data = path.read_bytes()
        if digest(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise ValueError("Retained declaration bytes changed")
        case, arm, *rest = entry["path"].split("/")
        output.setdefault((case, arm), []).append(
            {
                "kind": "/".join(rest),
                "source_sha256": entry["sha256"],
                "scope": manifest["evidence_scope"],
                "record": json.loads(data),
            }
        )
    return output


def trial_projection(trial, source_sha, index, declarations):
    confirmation = trial["confirmation"]
    if confirmation:
        confirmation = {key: value for key, value in confirmation.items() if key != "raw_source"}
        raw = trial["confirmation"]["raw_source"]
        confirmation["raw_source"] = {
            key: raw.get(key)
            for key in (
                "status",
                "bundle_sha256_expected",
                "bundle_sha256_observed",
                "verification",
            )
        }
    return {
        "schema": "nisayon.ui-study-trial.v1",
        **trial,
        "confirmation": confirmation,
        "retrospective_declarations": declarations.get((trial["case_id"], trial["arm"]), []),
        "source": {"sha256": source_sha, "pointer": f"/trials/{index}"},
    }


def project(engine: Path, directory: Path, interpreter: Path, output: Path):
    engine = engine.resolve()
    # A dirty producer implementation cannot be presented as a committed source.
    if git(engine, "diff", "HEAD", "--", "src", "uv.lock", "pyproject.toml"):
        raise ValueError("Engine implementation has uncommitted changes")
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    verify(engine, directory, interpreter)
    raw = (directory / "view.json").read_bytes()
    if (
        digest(raw) != manifest["view_sha256"]
        or (directory / "manifest.json").read_bytes() != manifest_raw
    ):
        raise ValueError("Export changed during verification")
    view = json.loads(raw)
    if view["scientific_acceptance"] != "none":
        raise ValueError("Unexpected confirmation-view authority")
    declarations = retained_declarations(engine)
    reports = {}
    for name, path in REPORTS.items():
        data = (engine / path).read_bytes()
        committed = subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=engine)
        if data != committed:
            raise ValueError("Uncommitted retained report: " + path)
        reports[name] = put(
            output,
            {
                "schema": "nisayon.ui-retained-report.v1",
                "source": {
                    "path": path,
                    "sha256": digest(data),
                    "engine_commit": git(engine, "rev-parse", "HEAD"),
                },
                "scope": "Retained report; not a new evaluation or independent revalidation of its scientific premises.",
                "record": json.loads(data),
            },
        )
    entries = []
    reports.update(mechanism_reports(engine, output, put))
    for index, trial in enumerate(view["trials"]):
        obj = trial_projection(trial, digest(raw), index, declarations)
        ref = put(output, obj)
        confirmation = trial["confirmation"]
        entries.append(
            {
                **{
                    key: trial[key]
                    for key in (
                        "comparison",
                        "case_id",
                        "arm",
                        "historical_status",
                        "state",
                        "original_incident_id",
                        "repetition_id",
                    )
                },
                "key": f"{trial['comparison']}/{trial['case_id']}/{trial['arm']}",
                "pairs": len(confirmation["pairs"]) if confirmation else 0,
                "records": len(confirmation["observations"]) if confirmation else 0,
                "object": ref,
            }
        )
    generation = {
        "schema": "nisayon.ui-study.v1",
        "source": {
            "engine_commit": git(engine, "rev-parse", "HEAD"),
            "metadata_commit": view["source_commit"],
            "view_sha256": digest(raw),
            "manifest_sha256": digest(manifest_raw),
        },
        "verified_at": datetime.now(UTC).isoformat(),
        "verification": "current dependencies, metadata and retained raw artifact digests",
        "execution_connected": False,
        "scientific_acceptance": "none",
        "scope": "Retained development evidence; repetitions and paired conditions are not independent incidents.",
        "trials": entries,
        "reports": reports,
        "costs": view["costs"],
        "limitations": view.get("limitations", []),
        "counts": {
            "trials": len(entries),
            "pairs": sum(e["pairs"] for e in entries),
            "records": sum(e["records"] for e in entries),
            "unscheduled": sum(e["state"] == "confirmation_not_scheduled" for e in entries),
        },
    }
    ref = put(output, generation, "generations")
    atomic(
        output / "evidence.json",
        encoded({"schema": "nisayon.ui-study-discovery.v1", "generation": ref}) + b"\n",
    )
    return {"generation": ref, "counts": generation["counts"], "source": generation["source"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, default=ROOT.parent / "nisayon")
    parser.add_argument("--export", type=Path, required=True, dest="directory")
    parser.add_argument(
        "--python",
        type=Path,
        default=ROOT.parent / "nisayon-codex/.venv/bin/python",
        dest="interpreter",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures/ui/study")
    args = parser.parse_args()
    print(json.dumps(project(args.engine, args.directory, args.interpreter, args.output), indent=2))


if __name__ == "__main__":
    main()
