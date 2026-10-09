from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path("scripts/experiments/assess_a1_acquisition.py")
SPEC = importlib.util.spec_from_file_location("assess_a1_acquisition", SCRIPT)
acquisition = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(acquisition)


def _write_fixture(tmp_path: Path, *, official_bytes: int, stanford_bytes: int) -> dict[str, Path]:
    paths = {
        "protocol": tmp_path / "protocol.json",
        "metadata": tmp_path / "metadata.json",
        "metadata_headers": tmp_path / "metadata.headers",
        "rename_history": tmp_path / "rename.html",
        "rename_headers": tmp_path / "rename.headers",
        "stanford_headers": tmp_path / "stanford.headers",
    }
    paths["protocol"].write_text(
        json.dumps(
            {
                "target": {"pinned_url": "http://example.test/low_dim_v141.hdf5"},
                "retained_network_plan": {"dataset_body_cap_bytes": 32 * 1024**2},
                "shared_limits": {
                    "new_dependency_bytes": 32 * 1024**2,
                    "known_cumulative_source_bytes_before_dataset": 21_495_048,
                    "cumulative_source_bytes": 64 * 1024**2,
                },
            }
        )
    )
    paths["metadata"].write_text(
        json.dumps(
            {
                "id": acquisition.OFFICIAL_REPOSITORY,
                "sha": "revision",
                "tags": ["license:mit"],
                "cardData": {"license": "mit"},
                "siblings": [
                    {
                        "rfilename": acquisition.OFFICIAL_PATH,
                        "lfs": {"size": official_bytes, "sha256": "a" * 64},
                    }
                ],
            }
        )
    )
    paths["rename_history"].write_text(
        f"Rename {acquisition.HISTORICAL_PATH} to {acquisition.OFFICIAL_PATH}\n"
        '<svg class="d2h-icon d2h-moved"></svg>\n'
        '<span class="d2h-lines-added">+0</span>\n'
        '<span class="d2h-lines-deleted">-0</span>\n'
    )
    paths["metadata_headers"].write_text(
        f"HTTP/2 200\nContent-Length: {paths['metadata'].stat().st_size}\n\n"
    )
    paths["rename_headers"].write_text(
        f"HTTP/2 200\nContent-Length: {paths['rename_history'].stat().st_size}\n\n"
    )
    paths["stanford_headers"].write_text(
        "HTTP/1.1 200 OK\n"
        "Content-Type: application/octet-stream\n"
        f"Content-Length: {stanford_bytes}\n"
        'ETag: "fixture"\n\n'
    )
    return paths


def _assess(paths: dict[str, Path]) -> dict:
    return acquisition.assess(
        protocol_path=paths["protocol"],
        metadata_path=paths["metadata"],
        metadata_headers_path=paths["metadata_headers"],
        rename_path=paths["rename_history"],
        rename_headers_path=paths["rename_headers"],
        stanford_headers_path=paths["stanford_headers"],
    )


def test_different_lengths_stop_before_dataset_get(tmp_path):
    result = _assess(_write_fixture(tmp_path, official_bytes=21_084_088, stanford_bytes=21_693_920))

    assert result["decision"] == "unresolved_exact_bytes_not_bound_to_retained_license"
    assert result["checks"]["byte_count_difference"] == 609_832
    assert result["checks"]["within_new_dependency_cap"] is True
    assert result["dataset_get_authorized_by_gate"] is False


def test_equal_lengths_only_authorize_digest_check(tmp_path):
    result = _assess(_write_fixture(tmp_path, official_bytes=21_084_088, stanford_bytes=21_084_088))

    assert result["decision"] == "eligible_for_single_dataset_get_and_digest_check"
    assert result["checks"]["byte_identity_possible"] is True
    assert result["pinned_stanford_object"]["sha256"] is None
    assert result["dataset_get_authorized_by_gate"] is True


def test_missing_license_stops_before_dataset_get(tmp_path):
    paths = _write_fixture(tmp_path, official_bytes=21_084_088, stanford_bytes=21_084_088)
    metadata = json.loads(paths["metadata"].read_text())
    metadata["cardData"]["license"] = None
    paths["metadata"].write_text(json.dumps(metadata))
    paths["metadata_headers"].write_text(
        f"HTTP/2 200\nContent-Length: {paths['metadata'].stat().st_size}\n\n"
    )

    result = _assess(paths)

    assert result["decision"] == "unresolved_official_rights_identity_missing"
    assert result["dataset_get_authorized_by_gate"] is False


def test_size_limit_failure_is_infeasible(tmp_path):
    too_large = 33 * 1024**2
    result = _assess(_write_fixture(tmp_path, official_bytes=too_large, stanford_bytes=too_large))

    assert result["decision"] == "infeasible_under_acquisition_limits"
    assert result["checks"]["within_new_dependency_cap"] is False
    assert result["dataset_get_authorized_by_gate"] is False
