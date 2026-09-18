"""Openly labelled development examples for the reserved-screen checks.

``evidence_origin: synthetic_development``. No reserved answer exists; the answer digests
here are digests of labelled placeholder strings that are never written to a shared tree.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .reserved import DECLARED_FAMILIES

ORIGIN = "synthetic_development"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def case_bytes(case_id: str) -> bytes:
    return (
        json.dumps(
            {
                "schema": "nisayon.case.v1",
                "id": case_id,
                "evidence_origin": ORIGIN,
                "note": "development example of a sealed reserved case; not a real incident",
            },
            indent=2,
        )
        + "\n"
    ).encode()


def development_manifest(*, custody_separated: bool = True) -> dict:
    cases = []
    for family, count in DECLARED_FAMILIES.items():
        for index in range(count):
            case_id = f"R-{family}-{index + 1:02d}"
            cases.append(
                {
                    "id": case_id,
                    "family": family,
                    "sealed_sha256": hashlib.sha256(case_bytes(case_id)).hexdigest(),
                    "answer_sha256": _sha(f"placeholder answer for {case_id}; never written"),
                }
            )
    custody = (
        {
            "case_generation": "separate account",
            "solver_access": "none",
            "evaluator_access": "read-only",
            "statement": "development example of a separated custody statement; no such custody "
            "exists for this repository",
        }
        if custody_separated
        else {
            "case_generation": "shared",
            "solver_access": "filesystem",
            "evaluator_access": "shared",
            "statement": "shared development worktrees; both sessions can read everything",
        }
    )
    return {
        "schema": "nisayon.reserved_manifest.v1",
        "suite_id": "reserved-screen-development-example",
        "evidence_origin": ORIGIN,
        "sealed_at": "2026-09-20T09:00:00+00:00",
        "sealed_by_role": "case custodian (example)",
        "custody": custody,
        "protocol": {
            "obligation": "first-case-obligation-v0.2",
            "evaluator_commit": "example",
            "frozen_at": "2026-09-20T08:00:00+00:00",
            "retrieval_cutoff": {
                "at": "2026-09-20T08:30:00+00:00",
                "memory_tree_sha256": _sha("memory tree"),
            },
        },
        "families": dict(DECLARED_FAMILIES),
        "cases": cases,
        "arms": ["A", "B"],
    }


def development_ledger(manifest: dict) -> dict:
    return {
        "schema": "nisayon.comparison.v1",
        "evidence_origin": ORIGIN,
        "arms": [{"id": arm} for arm in manifest["arms"]],
        "trials": [
            {"arm": arm, "case_id": case["id"], "status": "not_attempted"}
            for arm in manifest["arms"]
            for case in manifest["cases"]
        ],
    }


def write_cases(manifest: dict, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        (folder / f"{case['id']}.json").write_bytes(case_bytes(case["id"]))
    return folder


@dataclass(frozen=True)
class ReservedScenario:
    name: str
    description: str
    expected_ready: bool
    expected_codes: tuple[str, ...]
    build: Callable[[], tuple[dict, dict | None]]


def _ready() -> tuple[dict, dict | None]:
    manifest = development_manifest()
    return manifest, development_ledger(manifest)


def _shared_worktrees() -> tuple[dict, dict | None]:
    manifest = development_manifest(custody_separated=False)
    return manifest, development_ledger(manifest)


def _order_broken() -> tuple[dict, dict | None]:
    manifest = development_manifest()
    manifest["sealed_at"] = "2026-09-20T07:00:00+00:00"
    return manifest, development_ledger(manifest)


def _family_counts() -> tuple[dict, dict | None]:
    manifest = development_manifest()
    manifest["cases"] = manifest["cases"][:-1]
    return manifest, development_ledger(manifest)


def _assignment_incomplete() -> tuple[dict, dict | None]:
    manifest = development_manifest()
    ledger = development_ledger(manifest)
    ledger["trials"] = [
        t for t in ledger["trials"] if not (t["arm"] == "B" and t["case_id"].endswith("-01"))
    ]
    return manifest, ledger


def _extra_case_in_ledger() -> tuple[dict, dict | None]:
    manifest = development_manifest()
    ledger = development_ledger(manifest)
    ledger["trials"].append({"arm": "A", "case_id": "D01-gripper-sign", "status": "confirmed"})
    return manifest, ledger


RESERVED_SCENARIOS: tuple[ReservedScenario, ...] = (
    ReservedScenario(
        "separated_custody_example",
        "A labelled example with a separated custody statement, complete assignments and consistent counts.",
        True,
        (),
        _ready,
    ),
    ReservedScenario(
        "shared_worktrees",
        "The custody statement gives the solver filesystem access; the reserved trial must stay unrun.",
        False,
        ("custody_not_separated",),
        _shared_worktrees,
    ),
    ReservedScenario(
        "sealed_before_freeze",
        "The manifest was sealed before the protocol was frozen.",
        False,
        ("protocol_not_frozen_before_seal",),
        _order_broken,
    ),
    ReservedScenario(
        "family_counts_differ",
        "One sealed case is missing from a family.",
        False,
        ("family_counts_differ",),
        _family_counts,
    ),
    ReservedScenario(
        "assignment_incomplete",
        "An arm has no trial for one reserved case.",
        False,
        ("assignment_incomplete",),
        _assignment_incomplete,
    ),
    ReservedScenario(
        "case_outside_manifest",
        "The ledger names a development case as if it were reserved.",
        False,
        ("assignment_incomplete",),
        _extra_case_in_ledger,
    ),
)


def scenario_files(item: ReservedScenario, folder: Path) -> tuple[Path, Path | None]:
    manifest, ledger = item.build()
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    ledger_path = None
    if ledger is not None:
        ledger_path = folder / "ledger.json"
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")
    return manifest_path, ledger_path


__all__ = [
    "RESERVED_SCENARIOS",
    "ReservedScenario",
    "case_bytes",
    "copy",
    "development_ledger",
    "development_manifest",
    "scenario_files",
    "write_cases",
]
