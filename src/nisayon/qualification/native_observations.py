"""Bounded typed observation trees with content-addressed numeric array bytes.

No pickle, owner code, lazy external paths or lossy JSON numeric conversion.
These records bind returned bytes, not their accuracy as observations.
"""

import math
import re

from .models import fields
from .native_measurements import _int, _require, _sha

ARRAY_ELEMENTS = 1_000_000
ARRAY_BYTES = 8 * 1024**2
TOTAL_BYTES = 512 * 1024**2
FILE_COUNT = 16_384


def _scalar(value):
    _require(value is None or type(value) in (bool, int, float, str), "observation_type")
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite_observation")


class ObservationWriter:
    def __init__(self, root, np):
        self.root, self.np = root, np
        self.root.mkdir(exist_ok=False)
        self.identities, self.size = set(), 0

    def encode(self, value, depth=0):
        np = self.np
        _require(depth <= 16, "observation_depth")
        if isinstance(value, np.ndarray):
            _require(
                value.dtype.kind in "biuf"
                and value.dtype.itemsize <= 8
                and value.ndim <= 16
                and value.size <= ARRAY_ELEMENTS,
                "observation_array",
            )
            _require(bool(np.isfinite(value).all()), "nonfinite_observation")
            raw = value.tobytes(order="C")
            _require(len(raw) <= ARRAY_BYTES, "observation_array_bound")
            identity = _sha(raw)
            if identity not in self.identities:
                _require(
                    len(self.identities) < FILE_COUNT and self.size + len(raw) <= TOTAL_BYTES,
                    "observation_store_bound",
                )
                with (self.root / (identity + ".bin")).open("xb") as stream:
                    stream.write(raw)
                self.identities.add(identity)
                self.size += len(raw)
            return {
                "array": {
                    "dtype": value.dtype.str,
                    "shape": list(value.shape),
                    "sha256": identity,
                    "bytes": len(raw),
                }
            }
        if isinstance(value, np.generic):
            return self.encode(value.item(), depth + 1)
        if isinstance(value, dict):
            _require(all(type(k) is str for k in value) and len(value) <= 1024, "observation_keys")
            return {"mapping": {k: self.encode(v, depth + 1) for k, v in value.items()}}
        if isinstance(value, (list, tuple)):
            _require(len(value) <= 1024, "observation_sequence")
            return {
                "tuple" if isinstance(value, tuple) else "list": [
                    self.encode(v, depth + 1) for v in value
                ]
            }
        _scalar(value)
        return {"scalar": value}


class ObservationReader:
    def __init__(self, root, np):
        self.root, self.np = root, np
        _require(root.is_dir() and not root.is_symlink(), "observation_directory")
        self.names = set()
        size = 0
        for path in root.iterdir():
            _require(
                path.is_file()
                and not path.is_symlink()
                and re.fullmatch(r"[0-9a-f]{64}\.bin", path.name),
                "observation_regular_file",
            )
            count = path.stat().st_size
            _require(count <= ARRAY_BYTES, "observation_array_bound")
            self.names.add(path.name)
            size += count
            _require(
                len(self.names) <= FILE_COUNT and size <= TOTAL_BYTES, "observation_store_bound"
            )
        self.seen, self.checked = set(), set()

    def check(self, value, depth=0):
        _require(depth <= 16, "observation_depth")
        _require(type(value) is dict and len(value) == 1, "observation_node")
        key, content = next(iter(value.items()))
        if key == "array":
            fields(content, {"dtype", "shape", "sha256", "bytes"})
            _require(type(content["dtype"]) is str, "observation_dtype")
            dtype = self.np.dtype(content["dtype"])
            _require(
                dtype.str == content["dtype"] and dtype.kind in "biuf" and dtype.itemsize <= 8,
                "observation_dtype",
            )
            shape = content["shape"]
            _require(type(shape) is list and len(shape) <= 16, "observation_shape")
            for dimension in shape:
                _int(dimension, "observation_dimension", ARRAY_ELEMENTS)
            elements = math.prod(shape)
            count = _int(content["bytes"], "observation_bytes", ARRAY_BYTES)
            _require(
                elements <= ARRAY_ELEMENTS and count == elements * dtype.itemsize,
                "observation_shape_bytes",
            )
            identity = content["sha256"]
            _require(
                type(identity) is str and re.fullmatch(r"[0-9a-f]{64}", identity),
                "observation_identity",
            )
            name = identity + ".bin"
            _require(name in self.names, "observation_array_missing")
            self.seen.add(name)
            signature = (identity, dtype.str, count)
            if signature not in self.checked:
                with (self.root / name).open("rb") as stream:
                    raw = stream.read(ARRAY_BYTES + 1)
                _require(len(raw) == count and _sha(raw) == identity, "observation_array_integrity")
                _require(
                    bool(self.np.isfinite(self.np.frombuffer(raw, dtype=dtype)).all()),
                    "nonfinite_observation",
                )
                self.checked.add(signature)
        elif key == "mapping":
            _require(
                type(content) is dict
                and len(content) <= 1024
                and all(type(k) is str for k in content),
                "observation_keys",
            )
            for child in content.values():
                self.check(child, depth + 1)
        elif key in ("list", "tuple"):
            _require(type(content) is list and len(content) <= 1024, "observation_sequence")
            for child in content:
                self.check(child, depth + 1)
        elif key == "scalar":
            _scalar(content)
        else:
            raise ValueError("observation_node")

    def finish(self):
        _require(self.seen == self.names, "unreferenced_observation_array")
