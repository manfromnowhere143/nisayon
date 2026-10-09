"""Freeze the dataset-derived wheel members before any A1 package response."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import xml.etree.ElementTree as ET
from pathlib import Path

import h5py

ASSET_MARKER = "/robosuite/models/assets/"
ASSET_PREFIX = "robosuite/models/assets/"


class AssetManifestError(RuntimeError):
    """The held dataset does not satisfy the prospectively declared asset contract."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def model_file_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise AssetManifestError(f"model_file has unsupported type {type(value).__name__}")


def referenced_asset_members(model_file: str) -> tuple[str, ...]:
    """Map compiled XML file attributes to normalized wheel member names."""

    try:
        root = ET.fromstring(model_file)
    except ET.ParseError as error:
        raise AssetManifestError(f"model_file is not XML: {error}") from error
    raw_paths = [element.attrib["file"] for element in root.iter() if "file" in element.attrib]
    members: list[str] = []
    for raw_path in raw_paths:
        if raw_path.count(ASSET_MARKER) != 1:
            raise AssetManifestError(f"file path is outside the unique asset root: {raw_path}")
        relative = posixpath.normpath(raw_path.split(ASSET_MARKER, 1)[1])
        if relative in {"", ".", ".."} or relative.startswith("../") or relative.startswith("/"):
            raise AssetManifestError(f"file path escapes the asset root: {raw_path}")
        member = f"{ASSET_PREFIX}{relative}"
        if "\\" in member or any(part in {"", ".", ".."} for part in member.split("/")):
            raise AssetManifestError(f"normalized member is unsafe: {member}")
        members.append(member)
    if len(set(raw_paths)) != len(raw_paths):
        raise AssetManifestError("model_file repeats a raw file path")
    if len(set(members)) != len(members):
        raise AssetManifestError("distinct raw paths collapse to one normalized member")
    return tuple(sorted(members))


def canonical_members_sha256(members: tuple[str, ...]) -> str:
    payload = json.dumps(members, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_manifest(
    *,
    dataset: Path,
    expected_dataset_bytes: int,
    expected_dataset_sha256: str,
    demo: str,
    expected_model_file_sha256: str,
    expected_file_count: int,
    recorded_at: str,
    source_commit: str,
) -> dict:
    if dataset.is_symlink() or not dataset.is_file():
        raise AssetManifestError("dataset is absent, non-regular, or a symlink")
    dataset_bytes = dataset.stat().st_size
    if dataset_bytes != expected_dataset_bytes:
        raise AssetManifestError(
            f"dataset bytes differ: {dataset_bytes} != {expected_dataset_bytes}"
        )
    dataset_sha256 = file_sha256(dataset)
    if dataset_sha256 != expected_dataset_sha256:
        raise AssetManifestError(
            f"dataset sha256 differs: {dataset_sha256} != {expected_dataset_sha256}"
        )
    with h5py.File(dataset, "r") as handle:
        group_path = f"data/{demo}"
        if group_path not in handle:
            raise AssetManifestError(f"dataset group is absent: {group_path}")
        group = handle[group_path]
        if "model_file" not in group.attrs:
            raise AssetManifestError(f"model_file attribute is absent: {group_path}")
        model_file = model_file_text(group.attrs["model_file"])
    model_bytes = model_file.encode("utf-8")
    model_sha256 = hashlib.sha256(model_bytes).hexdigest()
    if model_sha256 != expected_model_file_sha256:
        raise AssetManifestError(
            f"model_file sha256 differs: {model_sha256} != {expected_model_file_sha256}"
        )
    members = referenced_asset_members(model_file)
    if len(members) != expected_file_count:
        raise AssetManifestError(
            f"referenced member count differs: {len(members)} != {expected_file_count}"
        )
    return {
        "schema": "nisayon.a1-runtime-referenced-assets.v1",
        "case": "a1-runtime-001",
        "recorded_at": recorded_at,
        "source_commit": source_commit,
        "dataset": {
            "path": str(dataset),
            "bytes": dataset_bytes,
            "sha256": dataset_sha256,
        },
        "model_file": {
            "demo": demo,
            "bytes": len(model_bytes),
            "sha256": model_sha256,
            "file_attribute_count": len(members),
        },
        "derivation": {
            "rule": (
                "parse every XML element file attribute; require exactly one "
                f"{ASSET_MARKER!r} marker; normalize the suffix with POSIX semantics; "
                f"prefix {ASSET_PREFIX!r}; reject escapes, duplicates and unsafe names"
            ),
            "ordering": "ascending Unicode code-point order",
            "canonical_encoding": "compact UTF-8 JSON array with ensure_ascii=false",
            "members_sha256": canonical_members_sha256(members),
        },
        "members": list(members),
        "operations": {
            "network_responses": 0,
            "package_bytes": 0,
            "environment_constructions": 0,
            "physics_steps": 0,
            "policy_actions": 0,
            "attempt_slots_consumed": 0,
        },
        "claim_boundary": (
            "this freezes package-member selection input only; it does not establish that "
            "the members exist in robosuite 1.5.1 or that the resulting runtime works"
        ),
        "publication": "private; no push or publication",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-dataset-bytes", type=int, required=True)
    parser.add_argument("--expected-dataset-sha256", required=True)
    parser.add_argument("--demo", required=True)
    parser.add_argument("--expected-model-file-sha256", required=True)
    parser.add_argument("--expected-file-count", type=int, required=True)
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError(f"refusing to overwrite asset manifest {args.output}")
    manifest = build_manifest(
        dataset=args.dataset,
        expected_dataset_bytes=args.expected_dataset_bytes,
        expected_dataset_sha256=args.expected_dataset_sha256,
        demo=args.demo,
        expected_model_file_sha256=args.expected_model_file_sha256,
        expected_file_count=args.expected_file_count,
        recorded_at=args.recorded_at,
        source_commit=args.source_commit,
    )
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "members": len(manifest["members"]),
                "members_sha256": manifest["derivation"]["members_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
