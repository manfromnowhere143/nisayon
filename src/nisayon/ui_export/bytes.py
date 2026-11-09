"""Bounded bytes, exact-byte identities and strict JSON for the static boundary."""

import gzip
import hashlib
import io
import json
import math
from pathlib import Path

MAX_OBJECT_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 128 * 1024 * 1024


class ExportError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    # Same documented serialization as the retained producer/evaluator digest.
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def finite(value: object, depth: int = 0) -> None:
    if depth > 64:
        raise ExportError("JSON nesting exceeds 64")
    if isinstance(value, float) and not math.isfinite(value):
        raise ExportError("non-finite number")
    if type(value) is int and abs(value) > 2**53 - 1:
        raise ExportError("integer outside exact JavaScript range")
    if isinstance(value, dict):
        for child in value.values():
            finite(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            finite(child, depth + 1)


def _pairs(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise ExportError(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def parse(data: bytes, limit: int = MAX_OBJECT_BYTES):
    if len(data) > limit:
        raise ExportError("JSON byte limit exceeded")
    try:
        value = json.loads(data, object_pairs_hook=_pairs)
        finite(value)
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ExportError(f"invalid JSON: {error}") from error


def read(path: Path, limit: int = MAX_OBJECT_BYTES) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ExportError(f"byte limit exceeded: {path.name}")
    return data


def decompress(data: bytes, limit: int = MAX_BUNDLE_BYTES) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        decoded = stream.read(limit + 1)
    if len(decoded) > limit:
        raise ExportError("decoded byte limit exceeded")
    return decoded


def inside(root: Path, relative: str) -> Path:
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or "%" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise ExportError("unsafe relative path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ExportError("path escapes the source root")
    return path


def check_bytes(data: bytes, digest: str, length: int | None = None) -> None:
    if length is not None and len(data) != length:
        raise ExportError("byte length mismatch")
    if sha256(data) != digest:
        raise ExportError("byte digest mismatch")
