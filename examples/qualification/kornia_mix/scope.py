"""Applicability checks for this one CPU mixing contract; no native imports."""

import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON field: {key}")
            result[key] = value
        return result

    value = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)
    canonical(value)  # Reject NaN, Infinity and exponent overflow, recursively.
    return value


def write(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_files(root):
    root = Path(root).resolve()
    package = root / "kornia"
    if not (package / "__init__.py").is_file() or package.is_symlink():
        raise ValueError("Expected a complete ordinary Kornia package")
    files = {}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlinks are outside this source snapshot contract")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files[str(path.relative_to(root))] = file_digest(path)
    return files


def environment():
    distributions = list(importlib.metadata.distributions())
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python_sha256": file_digest(sys.executable),
        "distributions": {dist.metadata["Name"]: dist.version for dist in distributions},
        "distribution_records": {
            dist.metadata["Name"]: hashlib.sha256(
                (dist.read_text("RECORD") or "").encode()
            ).hexdigest()
            for dist in distributions
        },
    }


def check_environment(actual, expected):
    if actual != expected:
        raise ValueError("Environment changed: requalify the contract before reuse")


def validate_conditions(rows):
    if not isinstance(rows, list) or not 12 <= len(rows) <= 64:
        raise ValueError("Require 12–64 conditions covering every family and dtype")
    seen = set()
    coverage = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("A condition must be an object")
        required = {"id", "kind", "dtype", "beta", "shape", "seed"}
        allowed = required | {
            "same_on_batch",
            "move",
            "patch_size",
            "num_mix",
            "cut_size",
            "labels",
        }
        if not required <= row.keys() or row.keys() - allowed:
            raise ValueError("Missing or unknown contract fields")
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in seen:
            raise ValueError("Condition identities must be nonempty and unique")
        seen.add(row["id"])
        if row["kind"] not in ("cutmix", "patchmix", "module"):
            raise ValueError("Operator outside the qualified family")
        if row["dtype"] not in ("float16", "bfloat16", "float32", "float64"):
            raise ValueError("Dtype outside the qualified family")
        beta = row["beta"]
        if type(beta) not in (int, float) or not math.isfinite(beta) or not 1e-8 <= beta <= 1e5:
            raise ValueError("Require a finite positive Python scalar in [1e-8, 1e5]")
        shape = row["shape"]
        if (
            not isinstance(shape, list)
            or len(shape) != 4
            or any(type(x) is not int or not 1 <= x <= 64 for x in shape)
            or math.prod(shape) > 32768
        ):
            raise ValueError("Require bounded nonempty BCHW input, at most 32768 elements")
        if type(row["seed"]) is not int or not 0 <= row["seed"] < 2**32:
            raise ValueError("Seed outside the bounded integer domain")
        if type(row.get("same_on_batch", False)) is not bool:
            raise ValueError("same_on_batch must be Boolean")
        if row.get("move", "to") not in ("to", "parent", "set_rng"):
            raise ValueError("Unknown device/dtype transition")
        if row["kind"] == "patchmix":
            if any(key in row for key in ("num_mix", "cut_size", "labels")):
                raise ValueError("CutMix-only fields supplied to PatchMix")
            size = row.get("patch_size")
            if type(size) is not int or not 1 <= size <= min(shape[2:]):
                raise ValueError("Invalid patch size")
        else:
            if "patch_size" in row:
                raise ValueError("PatchMix-only field supplied to CutMix")
            mixes = row.get("num_mix", 1)
            if type(mixes) is not int or not 1 <= mixes <= 4:
                raise ValueError("Require 1–4 mixes")
            cut = row.get("cut_size", [0, 1])
            if (
                not isinstance(cut, list)
                or len(cut) != 2
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in cut)
                or not 0 <= cut[0] <= cut[1] <= 1
            ):
                raise ValueError("Invalid cut range")
        if "labels" in row:
            labels = row["labels"]
            if (
                row["kind"] != "module"
                or not isinstance(labels, list)
                or len(labels) != shape[0]
                or any(type(x) is not int or not -(2**24) <= x <= 2**24 for x in labels)
            ):
                raise ValueError("Labels must be exactly representable bounded class IDs")
        coverage.add((row["kind"], row["dtype"]))
    expected = {
        (kind, dtype)
        for kind in ("cutmix", "patchmix", "module")
        for dtype in ("float16", "bfloat16", "float32", "float64")
    }
    if coverage != expected:
        raise ValueError("Missing family/dtype coverage; no qualification possible")


if __name__ == "__main__":
    print(json.dumps(environment(), allow_nan=False))
