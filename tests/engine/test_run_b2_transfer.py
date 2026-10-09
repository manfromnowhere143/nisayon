import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "b2_test", Path("scripts/experiments/run_b2_transfer.py")
)
b2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b2)


def rows():
    return [
        {
            "seed": seed,
            "mode": mode,
            "outcome": "success" if mode == "corrected" else "task_failure",
            "initial_condition_sha256": str(seed),
        }
        for seed in b2.SEEDS
        for mode in ("unchanged", "corrected")
    ]


def test_fresh_paired_repairs_require_equal_captured_initial_conditions():
    records = rows()
    assert b2.paired_verdict(records)["supported"]
    records[-1]["initial_condition_sha256"] = "different"
    assert not b2.paired_verdict(records)["supported"]


def test_missing_or_failed_assignments_do_not_disappear_from_paired_verdict():
    records = rows()
    with pytest.raises(ValueError, match="twenty"):
        b2.paired_verdict(records[:-1])
    records[-1]["outcome"] = "execution_failure"
    assert not b2.paired_verdict(records)["supported"]


def test_seven_repairs_are_insufficient_and_regressions_are_rejected():
    records = rows()
    for index in [1, 3, 5]:
        records[index]["outcome"] = "task_failure"
    assert not b2.paired_verdict(records)["supported"]
    records = rows()
    records[0]["outcome"] = "success"
    records[1]["outcome"] = "task_failure"
    assert not b2.paired_verdict(records)["supported"]


@pytest.mark.parametrize("asset", ["policy", "dataset"])
def test_manifest_cannot_substitute_another_validly_hashed_asset(asset, monkeypatch):
    protocol = {
        "case": b2.CASE,
        "seeds": list(b2.SEEDS),
        "inputs": {
            "policy": {"sha256": b2.POLICY_SHA256},
            "dataset": {"sha256": b2.a1.DATASET_SHA256},
        },
    }
    protocol["inputs"][asset]["sha256"] = "0" * 64
    monkeypatch.setattr(
        b2.a1, "assert_file", lambda *_: pytest.fail("asset opened before identity gate")
    )
    with pytest.raises(ValueError, match=f"unqualified {asset} identity"):
        b2.validate_protocol(protocol)
