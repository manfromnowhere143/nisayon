"""Retain explicitly supplied development history instead of ignoring missing inputs."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from .io import file_digest
from .store import resolve_member


def retained_confirmation_sources(root: Path) -> list[Path]:
    """Discover all retained confirmations, including failed/invalid ones.

    A fixed list of v1/v2 paths previously omitted the latest v3 record. New
    result versions must not require a source edit to become freshness history.
    """
    sources = []
    for path in sorted((root / "docs/experiments/results").rglob("*bundle.json.gz")):
        document = json.loads(gzip.decompress(path.read_bytes()))
        schema = document.get("schema")
        if schema not in {"nisayon.first_case.v1", "nisayon.family_calibration.v1"}:
            raise ValueError(f"Unknown retained bundle schema: {path}")
        if schema == "nisayon.first_case.v1" and document.get("confirmation") is not None:
            sources.append(path)
    sources.extend(
        sorted((root / "docs/evaluation/results/audit-2026-09-18").glob("*.decision.json"))
    )
    for source in sources:
        read_history(source)  # An unreadable required history fails before execution.
    return sources


def read_history(path: Path) -> dict:
    raw = path.read_bytes()
    data = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if not isinstance(data, dict) or data.get("schema") not in {
        "nisayon.first_case.v1",
        "nisayon.decision.v1",
        "nisayon.confirmation.v1",
    }:
        raise ValueError(f"Unsupported retained confirmation history: {path.name}")
    return data


def retain_history(sources: list[Path], destination: Path) -> list[dict]:
    references = []
    for index, source in enumerate(sources):
        document = read_history(source)
        name = f"history/{index:02d}-{source.name}"
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
        references.append(
            {
                "path": name,
                "sha256": file_digest(target),
                "schema": document["schema"],
                "case_id": (document.get("case") or {}).get("id") or document.get("case_id"),
            }
        )
    return references


def verify_history(root: Path, references: list[dict]) -> list[Path]:
    paths = []
    for reference in references:
        path = resolve_member(root, reference["path"])
        if file_digest(path) != reference["sha256"]:
            raise ValueError(f"Retained history digest mismatch: {reference['path']}")
        document = read_history(path)
        case_id = (document.get("case") or {}).get("id") or document.get("case_id")
        if document["schema"] != reference["schema"] or case_id != reference["case_id"]:
            raise ValueError("Retained history identity mismatch")
        paths.append(path)
    return paths
