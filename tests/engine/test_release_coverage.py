import copy
import importlib
from pathlib import Path

import pytest

from nisayon.engine.io import file_digest, write_json


@pytest.fixture
def release_audit(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/experiments"))
    return importlib.import_module("audit_release_comparisons")


def fixture_bundle():
    assignments = [
        {
            "run_id": f"{mode}-{seed}",
            "seed": seed,
            "mode": mode,
            "candidate_sha256": mode,
            "role": "fresh_development_confirmation",
        }
        for seed in (60000, 60001)
        for mode in ("reference", "correction")
    ]
    return {
        "assignments": assignments,
        "runs": [
            {
                "id": a["run_id"],
                "plan_id": a["mode"],
                "seed": a["seed"],
                "condition_id": f"seed-{a['seed']}",
                "candidate_sha256": a["candidate_sha256"],
            }
            for a in assignments
        ],
    }


@pytest.mark.parametrize("corruption", ["missing", "duplicate", "mismatched", "unassigned"])
def test_condition_counts_cannot_hide_wrong_observation_identities(
    release_audit, tmp_path, corruption
):
    bundle = fixture_bundle()
    if corruption == "missing":
        bundle["runs"].pop()
    elif corruption == "duplicate":
        bundle["runs"][-1] = copy.deepcopy(bundle["runs"][0])
    elif corruption == "mismatched":
        bundle["runs"][-1]["seed"] = 60002
    else:
        bundle["runs"][-1]["seed"] = 60002
        bundle["assignments"][-1]["seed"] = 60002
    write_json(tmp_path / "bundle.json", bundle)
    write_json(tmp_path / "frozen-protocol.json", {"condition_ids": ["seed-60000", "seed-60001"]})
    record = {"bundle_path": "bundle.json", "bundle_sha256": file_digest(tmp_path / "bundle.json")}
    with pytest.raises(ValueError):
        release_audit.confirmation_coverage(tmp_path, record, [60000, 60001])


def test_each_frozen_manifest_has_its_own_expected_identity_set(release_audit, tmp_path):
    write_json(tmp_path / "bundle.json", fixture_bundle())
    write_json(tmp_path / "frozen-protocol.json", {"condition_ids": ["seed-60000", "seed-60001"]})
    record = {"bundle_path": "bundle.json", "bundle_sha256": file_digest(tmp_path / "bundle.json")}
    assert release_audit.confirmation_coverage(tmp_path, record, [60000, 60001])[
        "observed_seeds"
    ] == [60000, 60001]
    with pytest.raises(ValueError, match="condition identity"):
        release_audit.confirmation_coverage(tmp_path, record, [10500, 10501])
