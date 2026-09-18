"""Retain compact bound results without copying simulator assets or history stores."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from explain_development_parity import read, require

from nisayon.engine.io import file_digest, write_json
from nisayon.evaluation.scoring import score_comparison


def retain(root: Path, analysis: Path, audit: Path, output: Path) -> dict:
    require(not output.exists() and not output.is_relative_to(root), "Use a new archive directory")
    output.mkdir(parents=True)
    bindings = []

    def keep(source: Path, relative: Path | str, *, compressed: bool = False):
        target = output / relative
        if compressed:
            target = target.with_name(target.name + ".gz")
        raw = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(gzip.compress(raw, mtime=0) if compressed else raw)
        restored = gzip.decompress(target.read_bytes()) if compressed else target.read_bytes()
        require(restored == raw, "Archive bytes changed")
        bindings.append(
            {
                "source_locator": str(source),
                "source_sha256": file_digest(source),
                "path": str(target.relative_to(output)),
                "sha256": file_digest(target),
                "compression": "gzip" if compressed else None,
            }
        )

    for name in (
        "frozen-suite.json",
        "condition-reservation.json",
        "preparation-costs.json",
        "comparison-ledger.json",
        "comparison-score.json",
    ):
        keep(root / name, name)
    ledger = read(root / "comparison-ledger.json")
    parents = set()
    for case in ledger["cases"]:
        keep(root / case["id"] / "joint-freeze.json", Path(case["id"]) / "joint-freeze.json")
    for trial in ledger["trials"]:
        folder = root / trial["case_id"] / trial["arm"]
        keep(folder / "trial.json", folder.relative_to(root) / "trial.json")
        for phase in ("diagnostic", "confirmation"):
            stage = folder / phase
            if not stage.exists():
                continue
            for source in sorted(stage.glob("*.json")):
                keep(source, source.relative_to(root))
            store = stage / "execution"
            for name in (
                "bundle.json",
                "bundle-header.json",
                "artifact-manifest.json",
                "invocation.json",
                "integrity.json",
                "frozen-protocol.json",
                "joint-freeze.json",
            ):
                source = store / name
                if source.is_file():
                    keep(source, source.relative_to(root), compressed=source.name == "bundle.json")
        diagnostic = folder / "diagnostic"
        for source in sorted((diagnostic / "calls").rglob("*.json")):
            keep(source, source.relative_to(root))
        for source in sorted((diagnostic / "packets").rglob("*.json")):
            keep(source, source.relative_to(root), compressed=source.name != "packet.json")
        for source in sorted((diagnostic / "calls").glob("*/result.json")):
            result = read(source)
            log = Path(result["events_reference"]["locator"])
            parents.add((log.parent.parent, result["command_record"]["parent_command_record_id"]))
            for name in ("run.json", "stdout.log", "stderr.log"):
                keep(log.parent / name, Path("command-records") / log.parent.name / name)
    for directory, identity in parents:
        for name in ("run.json", "stdout.log", "stderr.log"):
            keep(directory / identity / name, Path("command-records") / identity / name)
    for source in (analysis / "analysis.json", analysis / "table.md"):
        keep(source, Path("analysis") / source.name, compressed=source.suffix == ".json")
    for source in (
        audit / "audit.json",
        audit / "scoring-controls.json",
        *sorted(audit.glob("E*/*-decision.json")),
    ):
        keep(source, Path("evidence-audit") / source.relative_to(audit))
    # Scoring must still bind every decision to the named execution after compression.
    score = score_comparison(ledger, output)
    require(score == read(root / "comparison-score.json"), "Compact score differs")
    manifest = {
        "schema": "nisayon.compact-result-bindings.v1",
        "raw_root_locator": str(root),
        "files": bindings,
        "portable_score_matches": True,
        "retained_bytes": sum((output / b["path"]).stat().st_size for b in bindings),
        "boundary": "Exact records and deterministically compressed bundles/solver traces. Full simulator stores, array artifacts and duplicated history remain at raw locators; full evidence re-evaluation needs those stores. Portable scoring and file binding checks work from this compact archive. No source record rewritten.",
    }
    write_json(output / "bindings.json", manifest)
    return {k: manifest[k] for k in ("portable_score_matches", "retained_bytes", "boundary")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "analysis", "audit", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            retain(
                args.root.resolve(strict=True),
                args.analysis.resolve(strict=True),
                args.audit.resolve(strict=True),
                args.output.resolve(),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
