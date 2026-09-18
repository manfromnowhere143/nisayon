"""Local development-condition reservations, not an evaluation isolation boundary."""

from __future__ import annotations

import gzip
import json
import subprocess
from pathlib import Path

from .io import digest, file_digest, write_json
from .store import resolve_member

HISTORY_PATH = "work/development/consumed-conditions.json"


def evidence_conditions(source: Path) -> dict:
    """Read condition identities from retained execution or assignment bytes.

    Invalid/partial runs and assigned-but-unused conditions stay consumed. A
    human-maintained list is an index, not evidence that its listed seeds agree
    with the artifact it names. This adapter covers the current Panda Lift lane.
    """
    raw = source.read_bytes()
    document = json.loads(gzip.decompress(raw) if source.suffix == ".gz" else raw)
    schema = document.get("schema")
    if schema in {"nisayon.first_case.v1", "nisayon.family_calibration.v1"}:
        namespace = "panda-lift:" + document["case"]["policy"]["sha256"]
        values = [r["seed"] for r in document.get("runs", [])]
        values += [a["seed"] for a in document.get("assignments", [])]
    elif schema == "nisayon.development.frozen-suite.v1":
        namespace = "panda-lift:" + document["asset"]["sha256"]
        values = [seed for seeds in document["condition_seeds"].values() for seed in seeds]
    elif schema == "nisayon.development-condition.v1":
        namespace = document["namespace"]
        values = [document["seed"]]
    else:
        raise ValueError(f"Unknown consumed-condition evidence schema: {source.name}")
    if not values or any(type(s) is not int or not 0 <= s <= 2**32 - 1 for s in values):
        raise ValueError("Retained condition evidence has missing or invalid seeds")
    return {"namespace": namespace, "seeds": sorted(set(values)), "schema": schema}


def consumed_history(root: Path, namespace: str, *, required: bool = True) -> dict:
    """Read portable committed consumption evidence, regardless of case labels."""
    path = root / HISTORY_PATH
    if not path.is_file():
        if required:
            raise ValueError("Committed condition history is missing; freshness cannot be checked")
        document = {"schema": "nisayon.consumed-conditions.v1", "entries": []}
    else:
        document = json.loads(path.read_text())
    if document.get("schema") != "nisayon.consumed-conditions.v1":
        raise ValueError("Unknown consumed-condition history schema")
    seeds, evidence = set(), []
    indexed_paths = set()
    for item in document["entries"]:
        if item["namespace"] != namespace:
            continue
        values = item["seeds"]
        if len(values) != len(set(values)) or any(
            type(s) is not int or not 0 <= s <= 2**32 - 1 for s in values
        ):
            raise ValueError("Invalid committed condition values")
        reference = item["evidence"]
        source = resolve_member(root, reference["path"])
        if file_digest(source) != reference["sha256"]:
            raise ValueError("Committed consumed-condition evidence digest mismatch")
        observed = evidence_conditions(source)
        if observed["namespace"] != namespace:
            raise ValueError("Consumed-condition evidence belongs to another policy namespace")
        if not set(values) <= set(observed["seeds"]):
            raise ValueError("Indexed consumed seeds are absent from their bound evidence")
        seeds.update(observed["seeds"])
        evidence.append(reference)
        indexed_paths.add(source)
    discovered = []
    results = root / "docs/experiments/results"
    sources = sorted({*results.rglob("*bundle.json.gz"), *results.rglob("frozen-suite.json")})
    for path in sources:
        source = resolve_member(root, str(path.relative_to(root)))
        if source in indexed_paths:
            continue
        observed = evidence_conditions(source)
        if observed["namespace"] != namespace:
            continue
        seeds.update(observed["seeds"])
        reference = {
            "path": str(path.relative_to(root)),
            "sha256": file_digest(source),
            "schema": observed["schema"],
        }
        discovered.append(reference)
        evidence.append(reference)
    return {
        "path": HISTORY_PATH if path.is_file() else None,
        "sha256": file_digest(path) if path.is_file() else None,
        "seeds": sorted(seeds),
        "evidence": evidence,
        "discovered_unindexed_evidence": discovered,
        "scope": "Seeds derived from bound and discovered retained execution/assignment artifacts, independent of case labels. Invalid and unused assignments stay consumed. The registry is a checked index, not the sole source of condition identities.",
    }


def _reservation_directory(root: Path, namespace: str) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        # Git worktrees share repository metadata; cloned repositories instead rely
        # on the committed history. This is coordination, never evaluation custody.
        return Path(result.stdout.strip()) / "nisayon/conditions" / digest(namespace)
    return root / ".nisayon/conditions" / digest(namespace)


def reserve_fresh(
    root: Path,
    namespace: str,
    seeds: list[int],
    protocol_sha256: str,
    invocation_id: str,
    *,
    history_required: bool = True,
) -> dict:
    if len(set(seeds)) != len(seeds) or any(
        type(seed) is not int or not 0 <= seed <= 2**32 - 1 for seed in seeds
    ):
        raise ValueError("Fresh conditions must be distinct uint32 integer seeds")
    history = consumed_history(root, namespace, required=history_required)
    consumed = sorted(set(seeds) & set(history["seeds"]))
    if consumed:
        raise ValueError(
            f"Conditions already consumed in committed evidence: {consumed}; use new seeds"
        )
    folder = _reservation_directory(root, namespace)
    legacy = root / ".nisayon/conditions" / digest(namespace)
    collisions = [
        seed
        for seed in seeds
        if (folder / f"seed-{seed}.json").exists() or (legacy / f"seed-{seed}.json").exists()
    ]
    if collisions:
        raise ValueError(f"Conditions already reserved or consumed: {collisions}; use new seeds")
    for seed in seeds:
        # Exclusive file creation also prevents two concurrent invocations from
        # both claiming the same condition. A partial failed reservation stays spent.
        write_json(
            folder / f"seed-{seed}.json",
            {
                "schema": "nisayon.development-condition.v1",
                "namespace": namespace,
                "seed": seed,
                "protocol_sha256": protocol_sha256,
                "invocation_id": invocation_id,
                "status": "reserved_before_observation",
            },
        )
    return {
        "namespace": namespace,
        "seeds": seeds,
        "protocol_sha256": protocol_sha256,
        "consumed_history": history,
        "reservation_store_locator": str(folder),
        "scope": "Exclusive reservations shared by Git worktrees, plus committed consumed-condition evidence for other clones. Independent clones must exchange committed results before reuse. No custody or blinding claim.",
    }


def verify_reservation(
    root: Path, namespace: str, seeds: list[int], protocol_sha256: str, invocation_id: str
) -> dict:
    """Confirm the caller owns these pre-observation assignments; never reassign them."""
    folder = _reservation_directory(root, namespace)
    records = []
    if len(seeds) != len(set(seeds)):
        raise ValueError("Duplicate condition reservation request")
    for seed in seeds:
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("Invalid condition reservation seed")
        path = folder / f"seed-{seed}.json"
        if not path.is_file():
            raise ValueError("Assigned condition has no pre-execution reservation")
        record = json.loads(path.read_text())
        if any(
            record.get(key) != value
            for key, value in {
                "namespace": namespace,
                "seed": seed,
                "protocol_sha256": protocol_sha256,
                "invocation_id": invocation_id,
            }.items()
        ):
            raise ValueError("Assigned condition belongs to a different protocol or invocation")
        records.append({"record": record, "sha256": file_digest(path)})
    return {
        "namespace": namespace,
        "records": records,
        "scope": "Local shared-Git reservation ownership, not evaluator custody",
    }
