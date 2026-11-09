"""Read-only source inventory and public/retained evidence coverage audit.

This does not execute the simulator, read reserved answers, evaluate a candidate,
or claim a line-by-line correctness review. Pass the canonical and UI worktrees.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import subprocess
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def inventory(root):
    entries = []
    for row in subprocess.check_output(["git", "ls-tree", "-rlz", "HEAD"], cwd=root).split(b"\0"):
        if not row:
            continue
        header, name = row.decode().split("\t", 1)
        mode, kind, oid, size = header.split()
        entries.append(
            {
                "path": name,
                "git_object": oid,
                "kind": kind,
                "bytes": int(size) if size != "-" else None,
            }
        )
    return entries


def modules(root, paths):
    result = []
    for name in paths:
        raw = (root / name).read_bytes()
        tree = ast.parse(raw)
        entries = []
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                entries.append(
                    {"name": node.name, "line": node.lineno, "kind": type(node).__name__}
                )
        result.append(
            {
                "path": name,
                "sha256": sha(raw),
                "bytes": len(raw),
                "lines": len(raw.splitlines()),
                "purpose": (ast.get_docstring(tree) or "").split("\n")[0],
                "entries": entries,
                "review_scope": "AST inventory; targeted interface and data-flow review described in README",
            }
        )
    return result


def public(url, expected=None):
    with urllib.request.urlopen(url, timeout=45) as response:
        raw = response.read(16_777_217)
    assert len(raw) <= 16_777_216
    if expected:
        assert sha(raw) == expected["sha256"] and len(raw) == expected["byte_length"]
    return json.loads(raw), {"url": url, "sha256": sha(raw), "bytes": len(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--ui", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    trees = {"canonical": inventory(args.canonical), "ui": inventory(args.ui)}
    indexed = modules(
        args.canonical,
        [
            e["path"]
            for e in trees["canonical"]
            if e["path"].startswith("src/") and e["path"].endswith(".py")
        ],
    )
    ui_export = modules(
        args.ui,
        [
            e["path"]
            for e in trees["ui"]
            if e["path"].startswith("src/nisayon/ui_export/") and e["path"].endswith(".py")
        ],
    )
    catalog, catalog_read = public("https://nisayon.danielwahnich.dev/api/engine.json")
    library, library_read = public(
        "https://nisayon.danielwahnich.dev/fixtures/ui/recorded/library.json"
    )
    flow_paths = [
        "apps/instrument/src/App.tsx",
        "apps/instrument/src/state/store.ts",
        "apps/instrument/src/ui/Identity.tsx",
        "apps/instrument/src/ui/EnginePanel.tsx",
        "apps/instrument/src/ui/DepthSurface.tsx",
        "apps/instrument/src/ui/RecordPages.tsx",
        "apps/instrument/src/model/decodeV1.ts",
        "apps/instrument/src/data/library.ts",
        "tools/ui/build_system_catalog.py",
        "tools/ui/package_site.py",
    ]
    flow_sources = [
        {"path": path, "sha256": sha((args.ui / path).read_bytes())} for path in flow_paths
    ]
    current = {entry["path"]: entry for entry in indexed}
    live = {entry["source"]["path"]: entry for entry in catalog["modules"]}
    eligible = [
        p
        for p in current
        if p.startswith(("src/nisayon/engine/", "src/nisayon/evaluation/"))
        and not Path(p).name.startswith("__")
        and "fixture" not in p
    ]

    def case(entry):
        base = "https://nisayon.danielwahnich.dev/fixtures/ui/recorded/" + entry["directory"] + "/"
        manifest, manifest_read = public(base + entry["manifest"]["path"], entry["manifest"])
        ref = manifest["cases"][0]["object"]
        value, case_read = public(base + ref["path"], ref)
        return {
            "case_id": value["case_id"],
            "arm": value["arm"],
            "trial_status": value["trial"]["status"],
            "run_records": len(value["runs"]),
            "stages": dict(Counter(r["stage"] for r in value["runs"])),
            "roles": dict(Counter(r["role"] for r in value["runs"])),
            "condition_pairs": len(value["confirmation"].get("pairs", [])),
            "configuration_differences": value["trial"]["diagnosis_record"]
            .get("selection", {})
            .get("configuration_differences"),
            "manifest": manifest_read,
            "case_object": case_read,
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        cases = list(pool.map(case, library["cases"]))
    retained = args.canonical / "docs/experiments/results/confirmation-engine-001"
    manifest = json.loads((retained / "retained-output-manifest.json").read_text())
    item = next(e for e in manifest["outputs"] if e["path"] == "view.json.gz")
    packed = (retained / item["path"]).read_bytes()
    raw = gzip.decompress(packed)
    assert sha(packed) == item["sha256"] and sha(raw) == item["uncompressed_sha256"]
    assert len(raw) == item["uncompressed_bytes"]
    view = json.loads(raw)
    confirmations = [t["confirmation"] for t in view["trials"] if t["confirmation"]]
    native = {
        "source": str(retained.relative_to(args.canonical)) + "/view.json.gz",
        "sha256": sha(packed),
        "uncompressed_sha256": sha(raw),
        "trial_assignments": len(view["trials"]),
        "pairs": sum(len(c["pairs"]) for c in confirmations),
        "confirmation_observations": sum(len(c["observations"]) for c in confirmations),
        "unscheduled_trials": sum(t["confirmation"] is None for t in view["trials"]),
        "trial_states": dict(Counter(t["state"] for t in view["trials"])),
        "scientific_acceptance": view["scientific_acceptance"],
        "raw_stores_reverified_this_audit": False,
    }
    result = {
        "schema": "nisayon.ui-exposure-audit.v1",
        "checked_at": datetime.now(UTC).isoformat(),
        "canonical_commit": git(args.canonical, "rev-parse", "HEAD"),
        "ui_commit": git(args.ui, "rev-parse", "HEAD"),
        "tracked_counts": {name: len(entries) for name, entries in trees.items()},
        "canonical_python_files": len(indexed),
        "canonical_python_lines": sum(e["lines"] for e in indexed),
        "published_catalog": {
            "source": catalog_read,
            "modules": len(live),
            "interfaces": len(catalog["interfaces"]),
            "execution_connected": catalog["execution_connected"],
            "missing_canonical_modules": [p for p in eligible if p not in live],
            "different_canonical_modules": [
                p
                for p in live
                if p in current and live[p]["source"]["sha256"] != current[p]["sha256"]
            ],
            "ui_only_modules": [p for p in live if p not in current],
        },
        "library": {
            "source": library_read,
            "case_count": len(cases),
            "run_records": sum(c["run_records"] for c in cases),
            "condition_pairs": sum(c["condition_pairs"] for c in cases),
            "cases": cases,
        },
        "retained_confirmation_view": native,
        "browser_rendered": False,
        "reserved_answers_read": False,
        "new_simulator_executions": 0,
        "new_model_experiments": 0,
        "limits": [
            "Git inventory accounts for paths; it does not mean each line or artifact was manually reviewed.",
            "AST inventory describes source structure, not correctness or measured product performance.",
            "The retained view bytes were checked against its output manifest; authoritative raw stores were not reverified or executed.",
            "Public manifest/case hashes verify transmitted bytes, not physical truth.",
            "No browser was available; visual, phone and assistive-technology acceptance remains unmeasured.",
        ],
    }
    result["reviewed_ui_sources"] = flow_sources
    (args.out / "findings.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.out / "source-modules.json").write_text(
        json.dumps({"canonical": indexed, "ui_export": ui_export}, indent=2) + "\n"
    )
    (args.out / "tracked-files.json.gz").write_bytes(
        gzip.compress(json.dumps(trees, separators=(",", ":")).encode(), mtime=0)
    )
    print(
        json.dumps(
            {
                "canonical_python_files": len(indexed),
                "missing_catalog_modules": len(
                    result["published_catalog"]["missing_canonical_modules"]
                ),
                "different_catalog_modules": len(
                    result["published_catalog"]["different_canonical_modules"]
                ),
                "public_run_records": result["library"]["run_records"],
                "public_pairs": result["library"]["condition_pairs"],
                "retained": native,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
