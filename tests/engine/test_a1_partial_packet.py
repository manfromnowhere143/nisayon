from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from nisayon.engine.store import verify_manifest

SCRIPT = Path("scripts/experiments/seal_a1_partial_packet.py")
SPEC = importlib.util.spec_from_file_location("seal_a1_partial_packet", SCRIPT)
packet = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(packet)


def test_partial_packet_is_content_bound_and_explicitly_absent(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"result":"unresolved"}\n')
    output = tmp_path / "packet"

    readback = packet.seal_packet(
        output,
        [(source, "inputs/source.json")],
        invocation={"source": {"execution_commit": "a" * 40}},
        summary={"status": "stopped_before_dataset_get"},
        durable_cap=4096,
    )

    seal = json.loads((output / "seal.json").read_text())
    members = verify_manifest(output, seal["artifact_manifest"])
    assert set(members) == {"inputs/source.json", "invocation.json", "summary.json"}
    assert "dataset body" in seal["absent_by_design"]
    assert readback["status"] == "partial_execution_stopped_before_dataset_get"


def test_partial_packet_refuses_overwrite(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("{}\n")
    output = tmp_path / "packet"
    packet.seal_packet(
        output,
        [(source, "source.json")],
        invocation={"source": {"execution_commit": "b" * 40}},
        summary={},
    )

    with pytest.raises(FileExistsError):
        packet.seal_packet(
            output,
            [(source, "source.json")],
            invocation={"source": {"execution_commit": "b" * 40}},
            summary={},
        )
