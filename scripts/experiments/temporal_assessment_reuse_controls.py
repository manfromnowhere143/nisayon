"""Exercise saved-assessment reuse on the actual retained temporal example.

All mutations affect a new owned copy. Original packets and old assessments are
read-only. A fresh assessment reads existing software execution, never reruns it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.engine.temporal_store import _fresh_root
from nisayon.engine.temporal_workflow import (
    _packet_snapshot,
    assess_packet,
    assessment_identity,
    load_assessment,
)

REPO = Path(__file__).resolve().parents[2]
PACKET = REPO / (
    "artifacts/engine-integration-001/temporal-integration-001/complete-example-001/execution"
)
CAP = 16 * 1024**2


def size(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def expect_rejected(result, packet):
    try:
        load_assessment(result, packet)
    except (OSError, ValueError) as error:
        return {"status": "rejected", "type": type(error).__name__, "message": str(error)}
    raise AssertionError("Changed evidence unexpectedly reused a saved result")


def child_reader(source, result, packet):
    script = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from nisayon.engine.temporal_workflow import load_assessment
try:
    result = load_assessment(Path(sys.argv[2]), Path(sys.argv[3]))
    print(json.dumps({'status': 'verified', 'assignments': len(result['assignments']),
                      'original_costs': result['costs']}))
except (OSError, ValueError) as error:
    print(json.dumps({'status': 'rejected', 'type': type(error).__name__,
                      'message': str(error)}))
loaded = [name for name in sys.modules if name.split('.')[0] in
          {'torch', 'numpy', 'mujoco', 'robosuite', 'robomimic'}]
assert not loaded, loaded
"""
    start = time.perf_counter()
    child = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(source), str(result), str(packet)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    record = {
        "returncode": child.returncode,
        "wall_s": time.perf_counter() - start,
        "stdout": child.stdout,
        "stderr": child.stderr,
        "scope": "nested child wall; isolated Python with site packages disabled",
    }
    if child.returncode:
        raise AssertionError(record)
    record["readback"] = json.loads(child.stdout)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Commit the driver and source before the retained control")
    if size(PACKET) + size(REPO / "src/nisayon") + 6 * 1024**2 >= CAP:
        raise ValueError("Control's conservative preflight exceeds its 16 MiB allocation")
    out = _fresh_root(args.out)
    initial = _packet_snapshot(PACKET)
    identity = assessment_identity()
    start, cpu = time.perf_counter(), time.process_time()
    primary = assess_packet(PACKET, out / "current-assessment")
    copied = out / "moved-execution"
    shutil.copytree(PACKET, copied)
    moved = load_assessment(out / "current-assessment", copied)
    assert moved == primary
    fresh = child_reader(REPO / "src", out / "current-assessment", copied)
    assert fresh["readback"]["status"] == "verified"
    first = primary["assignments"][0]["assignment"]["id"]
    member = copied / "assignments" / first / "sources/uv.lock"
    member_bytes = member.read_bytes()
    original_sha = file_digest(member)
    member.unlink()
    missing = expect_rejected(out / "current-assessment", copied)
    member.write_bytes(member_bytes)
    assert file_digest(member) == original_sha
    assert load_assessment(out / "current-assessment", copied) == primary

    store = copied / "assignments" / first
    held = out / "held-assignment"
    store.rename(held)
    absent = assess_packet(copied, out / "missing-assessment")
    assert absent["assignments"][0]["integrity"] == "missing_store"
    assert load_assessment(out / "missing-assessment", copied) == absent
    held.rename(store)
    restored_stale = expect_rejected(out / "missing-assessment", copied)
    restored = assess_packet(copied, out / "restored-assessment")
    for earlier, later in zip(primary["assignments"], restored["assignments"], strict=True):
        assert earlier["attempt_id"] == later["attempt_id"]
        assert earlier["original_execution_costs"] == later["original_execution_costs"]
        assert earlier["temporal_contract"] == later["temporal_contract"]

    changed_source = out / "changed-reader-source"
    shutil.copytree(
        REPO / "src/nisayon",
        changed_source / "nisayon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    reference = changed_source / "nisayon/evaluation/temporal.py"
    with reference.open("a") as stream:
        stream.write("\n# Controlled source-byte change; no semantic replacement.\n")
    changed = child_reader(changed_source, out / "current-assessment", copied)
    assert changed["readback"]["status"] == "rejected"
    assert "reader, reference or interpreter changed" in changed["readback"]["message"]
    assert _packet_snapshot(PACKET) == initial
    assert _packet_snapshot(copied) == initial
    assert assessment_identity() == identity
    retained = size(out)
    if retained >= CAP:
        raise ValueError("Retained control exceeds the frozen 16 MiB allocation")
    result = {
        "schema": "nisayon.temporal-assessment-reuse-controls.v1",
        "source_commit": head,
        "driver_sha256": file_digest(Path(__file__)),
        "assessment_identity": identity,
        "original_packet": str(PACKET.relative_to(REPO)),
        "original_packet_snapshot": initial,
        "moved_packet_equal": moved == primary,
        "fresh_isolated_read": fresh,
        "missing_source_member": {
            "path": str(member.relative_to(copied)),
            "original_sha256": original_sha,
            "readback": missing,
            "restored_identically": True,
        },
        "missing_assignment_result": absent,
        "restored_input_rejects_old_missing_result": restored_stale,
        "restored_result": restored,
        "changed_reference_source": changed,
        "original_inputs_unchanged": True,
        "costs": {
            "controls_before_final_record_wall_s": time.perf_counter() - start,
            "parent_process_cpu_s": time.process_time() - cpu,
            "child_cpu_s": None,
            "retained_bytes_before_final_record": retained,
            "scope": "New verification and assessment work, nested in the enclosing command. Original execution and earlier read costs remain historical; no execution was retried.",
        },
        "boundary": "File mutation controls on an owned copy; no new scientific assignment or physical execution. Source hashes bind bytes, not external custody.",
    }
    write_json(out / "controls.json", result)
    print(
        json.dumps(
            {
                "controls": "passed",
                "assignments": len(primary["assignments"]),
                "costs": result["costs"],
            }
        )
    )


if __name__ == "__main__":
    main()
