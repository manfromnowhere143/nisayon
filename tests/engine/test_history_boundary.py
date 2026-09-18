import gzip
import json

import pytest

from nisayon.engine.history import retain_history, retained_confirmation_sources, verify_history


def test_required_missing_or_corrupted_history_is_not_an_empty_consumed_set(tmp_path):
    source = tmp_path / "earlier.json"
    destination = tmp_path / "store"
    with pytest.raises(FileNotFoundError):
        retain_history([source], destination)
    source.write_text("not valid JSON")
    with pytest.raises(ValueError):
        retain_history([source], destination)
    source.write_text(
        json.dumps(
            {
                "schema": "nisayon.first_case.v1",
                "case": {"id": "same-case"},
                "confirmation": {"condition_ids": ["seed-2000"]},
            }
        )
    )
    references = retain_history([source], destination)
    assert len(verify_history(destination, references)) == 1
    (destination / references[0]["path"]).unlink()
    with pytest.raises(FileNotFoundError):
        verify_history(destination, references)


def test_latest_confirmation_is_discovered_without_a_version_allowlist(tmp_path):
    folder = tmp_path / "docs/experiments/results/newly-published-version"
    folder.mkdir(parents=True)
    path = folder / "bundle.json.gz"
    path.write_bytes(
        gzip.compress(
            json.dumps(
                {
                    "schema": "nisayon.first_case.v1",
                    "case": {"id": "synthetic-history"},
                    "confirmation": {"condition_ids": ["seed-9876"]},
                    "decision": "invalid",
                }
            ).encode()
        )
    )
    calibration = folder / "calibration-bundle.json.gz"
    calibration.write_bytes(
        gzip.compress(
            json.dumps({"schema": "nisayon.family_calibration.v1", "confirmation": None}).encode()
        )
    )
    assert retained_confirmation_sources(tmp_path) == [path]
    # Being invalid does not make an observed confirmation condition unused.
    path.write_bytes(b"broken retained archive")
    with pytest.raises(OSError):
        retained_confirmation_sources(tmp_path)
