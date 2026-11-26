"""Check the complete assigned inputs of the retained serving experiment.

Only Python and NumPy are required. Copied readers are fixed local source,
never code imported from the packet being checked. No native policy executes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from collections.abc import Iterator, Mapping
from pathlib import Path

import legacy_reader as legacy
import numpy as np
from strict_json import canonical_bytes, decode_json

FROZEN_SHA256 = "a93855a8d14aac085bac0c68d8b621ec2c8628d1a4cdd4fc8b143c4c39db3575"
LEGACY_AUDIT = legacy.audit
require = legacy.require
A, B, STATE = legacy.A, legacy.B, legacy.STATE


def assignment() -> list[dict]:
    return [
        {
            "resolution": [h, w],
            "empty_cameras": n,
            "case": c,
            "variant": v,
            "expected_accept": legacy.expected(c, n, v),
        }
        for h, w in ((8, 10), (256, 256))
        for n in (0, 1, 2)
        for c in legacy.CASES
        for v in legacy.VARIANTS
    ]


def same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def assigned_inputs(row: dict) -> dict[str, np.ndarray]:
    """Independent index formula for the frozen deterministic input recipe.

    Invalid requests are assigned experiments too. Their defects must remain
    present rather than being repaired by this reader.
    """
    h, w = row["resolution"]
    # HWC flat index expressed through separate pixel/channel coordinates.
    pixel = np.indices((h, w), dtype=np.int64)
    index = (pixel[0] * w + pixel[1])[..., None] * 3 + np.array([0, 1, 2])
    values = {
        A: np.remainder(index, 256).astype(np.uint8),
        B: np.remainder(index * 7 + 31, 256).astype(np.uint8),
        STATE: np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.float32),
    }
    rh, rw = (224, 224) if (h, w) == (256, 256) else (h, w)
    if row["case"] != "omit_synthetic":
        for j in range(row["empty_cameras"]):
            values[f"observation.images.empty_camera_{j}"] = np.zeros((rh, rw, 3), np.uint8)
    case = row["case"]
    if case in ("missing_first_real", "request_missing"):
        del values[A]
    if case == "missing_last_real":
        del values[B]
    if case == "missing_state":
        del values[STATE]
    if case == "no_visual":
        values = {STATE: values[STATE]}
    if case == "black_real":
        values[A] = np.zeros((h, w, 3), np.uint8)
    if case == "request_extra":
        values["unknown"] = np.zeros(1, np.float32)
    if case == "request_dtype":
        values[A] = values[A].astype(np.float32)
    if case == "request_shape":
        values[A] = values[A][:-1]
    if case == "request_nan":
        values[STATE][0] = np.nan
    # Negotiation faults change feature declarations, not these request arrays.
    return values


def input_references() -> Iterator[tuple[str, np.ndarray]]:
    for i, row in enumerate(assignment()):
        for name, value in assigned_inputs(row).items():
            yield f"row{i}_input_{name}", value


def array_layout() -> dict[str, tuple[tuple[int, ...], np.dtype]]:
    layout = {key: (value.shape, value.dtype) for key, value in input_references()}
    for i, row in enumerate(assignment()):
        if not row["expected_accept"]:
            continue
        h, w = row["resolution"]
        h, w = (224, 224) if (h, w) == (256, 256) else (h, w)
        for j in range(2 + row["empty_cameras"]):
            layout[f"row{i}_image{j}"] = ((1, 3, h, w), np.dtype("float32"))
            layout[f"row{i}_mask{j}"] = ((1,), np.dtype("bool"))
    return layout


def audit(rows: list, arrays: Mapping[str, np.ndarray], frozen: dict, summary: dict) -> dict:
    expected = assignment()
    require(same(frozen["assignment"], expected), "Typed frozen assignment differs")
    require(len(rows) == len(expected), "Incomplete or duplicated rows")
    for i, (row, declared) in enumerate(zip(rows, expected, strict=True)):
        require(same(row["index"], i), "Typed row index differs")
        require(
            all(same(row[key], value) for key, value in declared.items()),
            "Typed assignment differs",
        )
        for kind in ("images", "masks"):
            for j, metadata in enumerate(row.get(kind, [])):
                value = arrays[f"row{i}_{kind[:-1]}{j}"]
                reference = {
                    "sha256": legacy.sha(value),
                    "shape": list(value.shape),
                    "dtype": value.dtype.name,
                    "values": value.tolist() if value.size <= 16 else None,
                }
                require(same(metadata, reference), "Typed tensor metadata differs")
    checked = 0
    for key, reference in input_references():
        require(key in arrays, "Missing assigned input: " + key)
        value = arrays[key]
        require(
            value.shape == reference.shape and value.dtype.str == reference.dtype.str,
            "Assigned input shape/dtype differs: " + key,
        )
        require(
            np.array_equal(value, reference, equal_nan=True), "Assigned input values differ: " + key
        )
        checked += 1
    for key, value in {
        "rows": 324,
        "accepted": 80,
        "unexpected": 0,
        "direct_mismatches": 0,
    }.items():
        require(same(summary[key], value), "Typed summary differs: " + key)
    result = LEGACY_AUDIT(rows, arrays, frozen, summary)
    return {
        **result,
        "reader": "assigned-input-supplement-v2",
        "assigned_input_arrays_checked": checked,
        "input_nan_semantics": "only the declared request_nan state element; NaN payload bits unspecified",
    }


def bounded_file(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, "File exceeds reader limit: " + path.name)
    return data


def read_arrays(data: bytes) -> dict[str, np.ndarray]:
    """Bound members before allocation; never trust an NPY header for dimensions."""
    layout = array_layout()
    expected_names = {key + ".npy" for key in layout}
    require(len(data) <= 64 * 1024**2, "NPZ container exceeds 64 MiB")
    arrays = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(
            len(names) == len(expected_names) and set(names) == expected_names,
            "NPZ inventory or duplicates",
        )
        for entry in entries:
            key = entry.filename[:-4]
            shape, dtype = layout[key]
            size = math.prod(shape) * dtype.itemsize
            require(
                entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                "NPZ compression unsupported",
            )
            require(0 <= entry.file_size - size <= 1036, "NPY member size differs")
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                require(version in ((1, 0), (2, 0)), "NPY version unsupported")
                read_header = (
                    np.lib.format.read_array_header_1_0
                    if version == (1, 0)
                    else np.lib.format.read_array_header_2_0
                )
                actual_shape, fortran, actual_dtype = read_header(stream, max_header_size=1024)
                require(
                    actual_shape == shape and actual_dtype.str == dtype.str and fortran is False,
                    "NPY declared layout differs: " + key,
                )
                data = stream.read(size + 1)
                require(len(data) == size, "NPY payload length differs")
                arrays[key] = np.frombuffer(data, dtype=dtype).reshape(shape)
    return arrays


def verify(packet: Path) -> dict:
    root = packet.resolve()
    frozen_data = bounded_file(root / "records/freeze-v2.json", 512 * 1024)
    require(hashlib.sha256(frozen_data).hexdigest() == FROZEN_SHA256, "Unsupported protocol freeze")
    frozen = decode_json(frozen_data)
    for relative, digest in frozen["files"].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root), "Frozen file escapes packet")
        require(
            hashlib.sha256(bounded_file(path, 4 * 1024**2)).hexdigest() == digest,
            "Frozen source differs: " + relative,
        )
    run = root / "records/native-02"
    summary = decode_json(bounded_file(run / "summary.json", 64 * 1024))
    rows_data = bounded_file(run / "rows.jsonl", 1024**2)
    arrays_data = bounded_file(run / "arrays.npz", 64 * 1024**2)
    require(hashlib.sha256(rows_data).hexdigest() == summary["rows_sha256"], "Rows digest differs")
    require(
        hashlib.sha256(arrays_data).hexdigest() == summary["arrays_sha256"], "Arrays digest differs"
    )
    require(summary["freeze_sha256"] == FROZEN_SHA256, "Summary freeze differs")
    rows = [decode_json(line) for line in rows_data.splitlines()]
    return audit(rows, read_arrays(arrays_data), frozen, summary)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.packet)
    except (ValueError, KeyError, TypeError, OSError, EOFError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Invalid serving evidence: {exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
