from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from nisayon.engine.store import verify_manifest

SCRIPT = Path("scripts/experiments/seal_a1_training_packet.py")
SPEC = importlib.util.spec_from_file_location("seal_a1_training_packet", SCRIPT)
packet = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(packet)


def test_training_packet_seals_existing_outputs_without_dataset_duplication(tmp_path):
    output = tmp_path / "pilot"
    output.mkdir()
    (output / "model.pth").write_bytes(b"checkpoint")
    source = tmp_path / "input.json"
    source.write_text('{"input":true}\n')
    dataset = tmp_path / "dataset.hdf5"
    dataset.write_bytes(b"source body kept elsewhere")

    readback = packet.seal_in_place(
        output,
        [(source, "inputs/input.json")],
        adapters={"results/adapter.json": {"schema": "adapter", "passed": True}},
        invocation={"schema": "invocation"},
        summary={"schema": "summary"},
        source_commit="a" * 40,
        dataset_identity=packet._identity(dataset, display="private/dataset.hdf5"),
        durable_cap=4096,
    )

    seal = json.loads((output / "seal.json").read_text())
    members = verify_manifest(output, seal["artifact_manifest"])
    assert "model.pth" in members
    assert "inputs/input.json" in members
    assert "results/adapter.json" in members
    assert not (output / "private/dataset.hdf5").exists()
    assert seal["dataset_external_to_packet"]["sha256"] == packet.file_digest(dataset)
    assert readback["status"] == "executed_complete_pending_independent_assessment"


def test_training_packet_refuses_a_second_seal(tmp_path):
    output = tmp_path / "pilot"
    output.mkdir()
    (output / "raw.json").write_text("{}\n")
    kwargs = {
        "entries": [],
        "adapters": {},
        "invocation": {},
        "summary": {},
        "source_commit": "b" * 40,
        "dataset_identity": {"path": "elsewhere", "bytes": 0, "sha256": "0" * 64},
    }
    packet.seal_in_place(output, **kwargs)
    with pytest.raises(packet.SealError, match="already exists"):
        packet.seal_in_place(output, **kwargs)


def test_continuation_estimate_uses_median_maximum_and_fixed_remainder():
    report = {"costs": {"internal_total_wall_seconds": 13.0}}
    updates = [{"attributable_step_seconds": value} for value in (1.0, 2.0, 4.0, 6.0)]

    result = packet.continuation_estimate(report, updates)

    assert result["measured_non_update_remainder_seconds"] == 0.0
    assert result["observed_step_seconds"]["median"] == 3.0
    assert result["observed_step_seconds"]["maximum"] == 6.0
    assert result["bounded_examples"][0] == {
        "optimizer_updates": 100,
        "median_step_estimate_seconds": 300.0,
        "maximum_observed_step_estimate_seconds": 600.0,
    }
