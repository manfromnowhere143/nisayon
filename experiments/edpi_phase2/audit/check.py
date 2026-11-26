"""Adversarial regression against the frozen reader and retained native witness."""

from __future__ import annotations

import argparse
import copy
import io
import json
import platform
import resource
import tempfile
import time
import warnings
import zipfile
from functools import partial
from pathlib import Path
from unittest.mock import patch

import legacy_reader as old
import numpy as np
import probe
import verify_v2 as new
from strict_json import decode_json


def refused(name, operation, records):
    try:
        operation()
    except (ValueError, KeyError, TypeError, EOFError, zipfile.BadZipFile) as exc:
        records.append({"case": name, "error": str(exc)})
        return
    raise RuntimeError("Counterexample escaped: " + name)


def altered_npz(data, mode):
    target = "row0_input_observation.state.npy"
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as dest,
    ):
        for info in source.infolist():
            payload = source.read(info)
            if info.filename == target:
                if mode == "huge_header":
                    header = io.BytesIO()
                    np.lib.format.write_array_header_1_0(
                        header, {"descr": "<f4", "fortran_order": False, "shape": (10**9,)}
                    )
                    payload = header.getvalue() + bytes(32)
                elif mode == "truncated_payload":
                    payload = payload[:-1]
            dest.writestr(info.filename, payload)
        if mode == "duplicate_member":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                dest.writestr(target, source.read(target))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("before", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    _, rows, arrays, freeze, summary = probe.load(args.packet)
    result = {"positive": new.verify(args.packet)}
    with patch.object(old, "audit", new.audit):
        result["original_controls_refused"] = old.controls(rows, arrays, freeze, summary)
    records = []
    for name, mutate in probe.mutations(old).items():
        rr, ff, ss, aa = (
            copy.deepcopy(rows),
            copy.deepcopy(freeze),
            copy.deepcopy(summary),
            dict(arrays),
        )
        mutate(rr, aa, ff, ss)
        refused(name, partial(new.audit, rr, aa, ff, ss), records)
    rr, aa = copy.deepcopy(rows), dict(arrays)
    aa["row51_input_observation.state"] = arrays["row0_input_observation.state"]
    refused("removed_declared_nan_fault", lambda: new.audit(rr, aa, freeze, summary), records)
    refused(
        "saved_misleading_packet", lambda: new.verify(args.before / "misleading-packet"), records
    )
    for name, text in {
        "duplicate_json": '{"accepted": false, "accepted": true}',
        "nonfinite_json": '{"seconds": NaN}',
        "overflow_json": '{"seconds": 1e999}',
        "underflow_json": '{"seconds": 1e-999}',
    }.items():
        refused(name, partial(decode_json, text), records)
    # The real packet path must use that decoder, not just its unit primitive.
    with tempfile.TemporaryDirectory(prefix="nisayon-serving-json-") as directory:
        root = Path(directory)
        for relative in (*freeze["files"], "records/freeze-v2.json"):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((args.packet / relative).read_bytes())
        run = root / "records/native-02"
        run.mkdir(parents=True)
        (run / "summary.json").write_text('{"rows": 0, "rows": 324}')
        refused("duplicate_json_packet", lambda: new.verify(root), records)
    data = (args.packet / "records/native-02/arrays.npz").read_bytes()
    for mode in ("duplicate_member", "huge_header", "truncated_payload"):
        changed = altered_npz(data, mode)
        refused(mode, partial(new.read_arrays, changed), records)
    result.update(
        {
            "new_controls_refused": records,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "seconds": time.perf_counter() - started,
            "peak_rss_platform_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "rss_units": "bytes on macOS; KiB on Linux",
            "platform": platform.platform(),
        }
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
