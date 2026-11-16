"""Strict, portable evidence serialization without a simulator dependency."""

import hashlib
import json
import math
from pathlib import Path


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        _reject_constant(value)
    if number == 0.0 and any(digit in "123456789" for digit in value.lower().split("e", 1)[0]):
        # A nonzero token must not become zero before a measured relation is
        # assessed. Exponent digits do not change a literal zero's value.
        raise ValueError("Nonzero JSON number underflows to zero")
    return number


def decode_json(data: str | bytes | bytearray) -> object:
    """Decode evidence without duplicate declarations or silent numeric range loss.

    Exponent overflow needs its own check: ``parse_constant`` does not see
    otherwise valid numeric tokens such as ``1e999``. Nonzero tokens that round
    to zero are refused too; literal signed zeros and nonzero subnormals remain
    supported. Other finite tokens retain Python's binary-float rounding.
    Explicit nulls remain null.
    This is a decoding boundary, not schema validation or an authenticity check.
    """
    try:
        return json.loads(
            data,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except RecursionError as exc:
        # Evidence readers handle ValueError as invalid input. A maliciously
        # deep JSON record must take that path instead of crashing assessment.
        raise ValueError("JSON nesting exceeds the decoder's supported depth") from exc


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Refuse overwrite: prior failed attempts are evidence too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
