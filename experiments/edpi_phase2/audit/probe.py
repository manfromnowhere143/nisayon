"""Reproduce assigned-input counterexamples without native policy execution."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


def module(path: Path):
    spec = importlib.util.spec_from_file_location("serving_reader_v1", path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def mutations(old):
    state = "row0_input_observation.state"

    def nan(r, a, f, s):
        a[state] = a["row51_input_observation.state"].copy()

    def camera(r, a, f, s):
        key = "row0_input_observation.images.image"
        a[key] = np.zeros_like(a[key])
        a["row0_image0"] = np.full_like(a["row0_image0"], -1)
        r[0]["images"][0]["sha256"] = old.sha(a["row0_image0"])

    return {
        "native_rejected_nan_state": nan,
        "wrong_state_shape": lambda r, a, f, s: a.update({state: np.arange(9, dtype=np.float32)}),
        "wrong_state_dtype": lambda r, a, f, s: a.update({state: a[state].astype(np.float64)}),
        "unassigned_finite_state": lambda r, a, f, s: a.update({state: np.full(8, 42, dtype=np.float32)}),
        "coordinated_unassigned_camera": camera,
        "boolean_row_index": lambda r, a, f, s: r[0].update(index=False),
        "integer_mask_readback": lambda r, a, f, s: r[0]["masks"][0].update(values=[1]),
    }


def load(packet):
    old = module(packet / "verify.py")
    run = packet / "records/native-02"
    rows = [json.loads(line) for line in (run / "rows.jsonl").read_text().splitlines()]
    with np.load(run / "arrays.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    return old, rows, arrays, json.loads((packet / "records/freeze-v2.json").read_text()), json.loads((run / "summary.json").read_text())


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    old, rows, arrays, freeze, summary = load(args.packet)
    result = {"original": old.audit(rows, arrays, freeze, summary), "mutations": {}}
    state = "observation.state"
    old.require(rows[0]["accepted"] is True and rows[51]["accepted"] is False, "witness decisions")
    old.require(rows[51]["stage"] == "request" and rows[51]["case"] == "request_nan", "witness refusal")
    for name in (old.A, old.B):
        old.require(np.array_equal(arrays[f"row0_input_{name}"], arrays[f"row51_input_{name}"]), "witness camera mismatch")
    old.require(np.isnan(arrays[f"row51_input_{state}"][0]), "witness NaN absent")
    result["native_witness"] = {"accepted_row": rows[0], "refused_row": rows[51], "camera_inputs_identical": True}
    for name, mutate in mutations(old).items():
        rr, ff, ss = copy.deepcopy(rows), copy.deepcopy(freeze), copy.deepcopy(summary)
        aa = dict(arrays)
        mutate(rr, aa, ff, ss)
        try:
            old.audit(rr, aa, ff, ss)
            result["mutations"][name] = {"accepted": True}
        except (ValueError, KeyError, TypeError) as exc:
            result["mutations"][name] = {"accepted": False, "error": str(exc)}
        if name == "native_rejected_nan_state":
            destination = args.out / "misleading-packet"
            for relative in (*freeze["files"], "records/freeze-v2.json", "verify.py"):
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(args.packet / relative, target)
            run = destination / "records/native-02"
            run.mkdir(parents=True)
            shutil.copyfile(args.packet / "records/native-02/rows.jsonl", run / "rows.jsonl")
            np.savez_compressed(run / "arrays.npz", **aa)
            ss["arrays_sha256"] = hashlib.sha256((run / "arrays.npz").read_bytes()).hexdigest()
            (run / "summary.json").write_text(json.dumps(ss, indent=2) + "\n")
            command = [sys.executable, str(destination / "verify.py"), str(destination)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
            (args.out / "old-cli.stdout").write_text(completed.stdout)
            (args.out / "old-cli.stderr").write_text(completed.stderr)
            result["full_cli"] = {"argv": command, "returncode": completed.returncode, "mutated_arrays_sha256": ss["arrays_sha256"], "original_arrays_sha256": summary["arrays_sha256"]}
    (args.out / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"mutations": result["mutations"], "full_cli": result["full_cli"]}, indent=2))


if __name__ == "__main__":
    main()
