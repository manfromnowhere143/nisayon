"""Exercise the installed B2 reader outside Git, with copied and altered evidence.

Software qualification only. No simulator, learned inference or new conditions.
Run with the separate, locked records-only environment; retain command outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from importlib.metadata import distributions
from pathlib import Path

from nisayon.engine.io import write_json
from nisayon.engine.transfer_evidence import MANIFEST_SHA256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    packet, protocol, output = args.packet.resolve(), args.protocol.resolve(), args.out.resolve()
    if output.is_relative_to(packet) or output == protocol:
        raise ValueError("qualification output must stay outside the raw evidence")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    forbidden = ["torch", "mujoco", "robosuite", "robomimic"]
    absent = {name: importlib.util.find_spec(name) is None for name in forbidden}
    if not all(absent.values()):
        raise ValueError("qualification requires an environment without execution libraries")
    commands = []
    # Store the relocatable copy under retained qualification output. Child cwd
    # is outside Git, so no ancestor checkout can rescue a workspace dependency.
    relocated = output / "relocated-packet"
    shutil.copytree(packet, relocated)
    moved_protocol = output / "relocated-protocol.json"
    shutil.copyfile(protocol, moved_protocol)

    def invoke(label, source, contract, cwd):
        argv = [
            sys.executable,
            "-B",
            "-m",
            "nisayon.cli",
            "verify-lift-transfer",
            "--packet",
            str(source),
            "--protocol",
            str(contract),
        ]
        command_start = time.perf_counter()
        result = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=30, check=False
        )
        (output / f"{label}.stdout.json").write_text(result.stdout)
        (output / f"{label}.stderr.log").write_text(result.stderr)
        report = json.loads(result.stdout)
        commands.append(
            {
                "label": label,
                "argv": argv,
                "returncode": result.returncode,
                "wall_seconds": time.perf_counter() - command_start,
                "integrity": report["integrity"],
                "decision": report["decision"],
            }
        )
        return result, report

    with tempfile.TemporaryDirectory(prefix="nisayon-transfer-outside-git-") as directory:
        cwd = Path(directory)
        if any((parent / ".git").exists() for parent in [cwd, *cwd.parents]):
            raise ValueError("qualification cwd unexpectedly belongs to Git")
        original_process, original = invoke("original", packet, protocol, cwd)
        moved_process, moved = invoke("relocated", relocated, moved_protocol, cwd)
        if original_process.returncode != 0 or moved_process.returncode != 0 or original != moved:
            raise ValueError("original and relocated readbacks differ or fail")
        verdict = moved["recomputed"]["verdict"]
        if (verdict["unchanged_successes"], verdict["corrected_successes"]) != (0, 9):
            raise ValueError("retained task counts were not reproduced")
        member = relocated / "paired-execution/180100-corrected.npz"
        original_member = member.read_bytes()
        member.write_bytes(original_member[:-1] + bytes([original_member[-1] ^ 1]))
        process, report = invoke("altered", relocated, moved_protocol, cwd)
        if (
            process.returncode != 1
            or report["integrity"] != "invalid"
            or report["decision"] != "unresolved"
        ):
            raise ValueError("altered evidence was not rejected")
        member.unlink()
        process, report = invoke("missing", relocated, moved_protocol, cwd)
        if (
            process.returncode != 1
            or report["integrity"] != "incomplete"
            or report["decision"] != "unresolved"
        ):
            raise ValueError("missing evidence was not distinguished")
        member.write_bytes(original_member)
        process, restored = invoke("restored-copy", relocated, moved_protocol, cwd)
        if process.returncode != 0 or restored != original:
            raise ValueError("restored copy did not verify")
    if (
        hashlib.sha256((packet / "artifact-manifest.json").read_bytes()).hexdigest()
        != MANIFEST_SHA256
    ):
        raise ValueError("original manifest changed")
    write_json(
        output / "qualification.json",
        {
            "schema": "nisayon.transfer_evidence.qualification.v1",
            "scope": "Software portability and malformed-evidence controls, not additional task confirmation.",
            "passed": True,
            "python": sys.version,
            "packages": sorted(
                {f"{dist.metadata['Name']}=={dist.version}" for dist in distributions()}
            ),
            "execution_libraries_absent": absent,
            "verified_members": original["verified_members"],
            "network_input_array_witnesses_checked": original["recomputed"][
                "network_input_array_witnesses_checked"
            ],
            "commands": commands,
            "wall_seconds": time.perf_counter() - started,
            "cost_boundary": "Child command times are nested within this qualification; do not add them to its outer run cost. Engineering, installation and review are separate.",
        },
    )


if __name__ == "__main__":
    main()
