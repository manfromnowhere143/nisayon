import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("torch", reason="requires the locked simulation extra")
pytest.importorskip("robomimic", reason="requires the locked simulation extra")

SCRIPT = Path("scripts/experiments/freeze_a1_training_contract.py")
SPEC = importlib.util.spec_from_file_location("freeze_a1_training_contract", SCRIPT)
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


def test_assembled_contract_keeps_offline_claim_ceiling_and_exact_workload():
    config = freeze.driver.make_robomimic_config("dataset.hdf5", "artifacts/pilot")
    inventory = {
        "identity": {"sha256": "b" * 64},
        "membership": {
            "demos": [{"id": "demo_0"}, {"id": "demo_1"}],
            "demo_count": 2,
            "total_frames": 23,
            "sequence_starts_with_declared_padding": 23,
            "masks": {"train": ["demo_0"]},
        },
    }
    contract = freeze.assemble_contract(
        implementation_commit="a" * 40,
        dataset={
            "path": "dataset.hdf5",
            "bytes": 7,
            "sha256": "c" * 64,
            "custody_receipt_sha256": "d" * 64,
        },
        inventory=inventory,
        runtime={"driver_sha256": "e" * 64},
        config=config,
        model={
            "serialized_tensor_bytes": 8_000_000,
            "optimizer_updates": 0,
            "simulator_constructed": False,
        },
        output_root="artifacts/pilot",
        temporary_root="/private/tmp/pilot",
    )

    assert contract["workload"]["optimizer_updates_assigned_total"] == 100
    assert contract["workload"]["training_invocations_authorized"] == 1
    assert contract["dataset"]["training_demos"] == ["demo_0", "demo_1"]
    assert contract["robomimic_config"]["train"]["hdf5_normalize_obs"] is True
    assert contract["robomimic_config"]["experiment"]["rollout"]["enabled"] is False
    assert contract["limits"]["maximum_durable_output_bytes"] == 16 * 1024**2
    assert "policy competence" in contract["claim_ceiling"]["cannot_test"]
    assert "comparative advantage" in contract["claim_ceiling"]["cannot_test"]
