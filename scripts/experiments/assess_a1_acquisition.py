"""Assess the frozen A1 dataset gate from retained, offline response bytes."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path
from typing import Any

from nisayon.engine.io import file_digest, write_json

OFFICIAL_REPOSITORY = "robomimic/robomimic_datasets"
OFFICIAL_PATH = "v1.5/lift/ph/low_dim_v15.hdf5"
HISTORICAL_PATH = "v1.5/lift/ph/low_dim_v141.hdf5"


def _read_headers(path: Path) -> tuple[int, dict[str, str]]:
    text = path.read_text()
    status = re.search(r"^HTTP/\S+\s+(\d{3})\b", text, flags=re.MULTILINE)
    if status is None:
        raise ValueError(f"no HTTP status in {path}")
    first_block = text.split("\n\n", 1)[0]
    header_lines = first_block.splitlines()[1:]
    message = Parser().parsestr("\n".join(header_lines))
    return int(status.group(1)), {key.lower(): value for key, value in message.items()}


def _identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": file_digest(path),
    }


def assess(
    *,
    protocol_path: Path,
    metadata_path: Path,
    metadata_headers_path: Path,
    rename_path: Path,
    rename_headers_path: Path,
    stanford_headers_path: Path,
) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text())
    metadata = json.loads(metadata_path.read_text())
    metadata_status, metadata_headers = _read_headers(metadata_headers_path)
    rename_status, rename_headers = _read_headers(rename_headers_path)
    stanford_status, stanford_headers = _read_headers(stanford_headers_path)
    rename_html = rename_path.read_text()

    official_matches = [
        sibling
        for sibling in metadata.get("siblings", [])
        if sibling.get("rfilename") == OFFICIAL_PATH
    ]
    official = official_matches[0] if len(official_matches) == 1 else {}
    lfs = official.get("lfs", {})
    official_bytes = lfs.get("size")
    official_sha256 = lfs.get("sha256")
    stanford_bytes = int(stanford_headers["content-length"])

    license_declared = (
        metadata.get("id") == OFFICIAL_REPOSITORY
        and metadata.get("cardData", {}).get("license") == "mit"
        and "license:mit" in metadata.get("tags", [])
    )
    rename_confirmed = all(
        marker in rename_html
        for marker in (
            f"Rename {HISTORICAL_PATH} to {OFFICIAL_PATH}",
            "d2h-icon d2h-moved",
            'd2h-lines-added">+0',
            'd2h-lines-deleted">-0',
        )
    )
    official_identity_present = (
        len(official_matches) == 1
        and isinstance(official_bytes, int)
        and isinstance(official_sha256, str)
        and len(official_sha256) == 64
    )

    limits = protocol["shared_limits"]
    declared_download_cap = protocol["retained_network_plan"]["dataset_body_cap_bytes"]
    within_dependency_cap = stanford_bytes <= min(
        declared_download_cap,
        limits["new_dependency_bytes"],
    )
    projected_cumulative = limits["known_cumulative_source_bytes_before_dataset"] + stanford_bytes
    within_cumulative_cap = projected_cumulative <= limits["cumulative_source_bytes"]
    byte_identity_possible = official_identity_present and stanford_bytes == official_bytes

    transport_evidence_valid = (
        metadata_status == 200
        and rename_status == 200
        and stanford_status == 200
        and int(metadata_headers["content-length"]) == metadata_path.stat().st_size
        and int(rename_headers["content-length"]) == rename_path.stat().st_size
    )
    if not transport_evidence_valid:
        decision = "unresolved_invalid_retained_transport_evidence"
    elif not license_declared or not rename_confirmed or not official_identity_present:
        decision = "unresolved_official_rights_identity_missing"
    elif not within_dependency_cap or not within_cumulative_cap:
        decision = "infeasible_under_acquisition_limits"
    elif not byte_identity_possible:
        decision = "unresolved_exact_bytes_not_bound_to_retained_license"
    else:
        decision = "eligible_for_single_dataset_get_and_digest_check"

    return {
        "schema": "nisayon.a1-acquisition-assessment.v1",
        "case": "a1-feasibility-001",
        "recorded_at": datetime.now(UTC).isoformat(),
        "protocol": _identity(protocol_path),
        "inputs": {
            "official_metadata": _identity(metadata_path),
            "official_metadata_headers": _identity(metadata_headers_path),
            "rename_history": _identity(rename_path),
            "rename_history_headers": _identity(rename_headers_path),
            "stanford_head_headers": _identity(stanford_headers_path),
        },
        "official_repository": {
            "id": metadata.get("id"),
            "revision": metadata.get("sha"),
            "license": metadata.get("cardData", {}).get("license"),
            "license_declared": license_declared,
            "path": official.get("rfilename"),
            "bytes": official_bytes,
            "sha256": official_sha256,
            "rename_commit": "33d08702ad61296b55a74c4f810ab54462f319e9",
            "historical_path": HISTORICAL_PATH,
            "rename_confirmed_with_zero_line_changes": rename_confirmed,
        },
        "pinned_stanford_object": {
            "url": protocol["target"]["pinned_url"],
            "http_status": stanford_status,
            "content_type": stanford_headers.get("content-type"),
            "content_length": stanford_bytes,
            "etag": stanford_headers.get("etag"),
            "last_modified": stanford_headers.get("last-modified"),
            "body_requests": 0,
            "body_bytes": 0,
            "sha256": None,
        },
        "checks": {
            "transport_evidence_valid": transport_evidence_valid,
            "official_license_declared": license_declared,
            "official_identity_present": official_identity_present,
            "rename_confirmed": rename_confirmed,
            "within_new_dependency_cap": within_dependency_cap,
            "projected_cumulative_source_bytes": projected_cumulative,
            "within_cumulative_source_cap": within_cumulative_cap,
            "official_bytes": official_bytes,
            "stanford_bytes": stanford_bytes,
            "byte_count_difference": stanford_bytes - official_bytes,
            "byte_identity_possible": byte_identity_possible,
        },
        "decision": decision,
        "dataset_get_authorized_by_gate": decision
        == "eligible_for_single_dataset_get_and_digest_check",
        "rights_conclusion": (
            "The MIT declaration is retained for the official repository object. The pinned "
            "Stanford object has a different byte length, so it cannot have the official "
            "object's SHA-256. The retained terms therefore are not bound to the pinned bytes."
        ),
        "scientific_conclusion": (
            "No dataset body, training membership, normalization population, optimizer update, "
            "checkpoint or task outcome may be inferred from this acquisition assessment."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--metadata-headers", type=Path, required=True)
    parser.add_argument("--rename-history", type=Path, required=True)
    parser.add_argument("--rename-headers", type=Path, required=True)
    parser.add_argument("--stanford-headers", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(
        protocol_path=args.protocol,
        metadata_path=args.metadata,
        metadata_headers_path=args.metadata_headers,
        rename_path=args.rename_history,
        rename_headers_path=args.rename_headers,
        stanford_headers_path=args.stanford_headers,
    )
    write_json(args.out, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
