"""Strict parsing helpers for exchange records.

Records are plain JSON. Numbers must be finite; unknown values use explicit
missingness; timestamps carry a clock domain and unit. Anything else is
``Malformed`` with the path that failed, so a producer can find it.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

WALL_CLOCK = "wall_utc"
DURATION_UNITS = {"s": 1.0, "ms": 0.001}


class Malformed(ValueError):
    """A record violates the exchange contract at ``path``."""

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


def _reject_constant(name: str) -> None:
    raise Malformed("$", f"non-finite JSON constant {name}")


def load_json(path: Path) -> object:
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                text = stream.read()
        else:
            text = path.read_text()
    except (OSError, EOFError) as error:
        detail = getattr(error, "strerror", None) or str(error)
        raise Malformed(str(path), f"unreadable: {detail}") from error
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as error:
        raise Malformed(str(path), f"invalid JSON: {error.msg} at line {error.lineno}") from error


def canonical_json(obj: object) -> str:
    """Deterministic serialization used for digests: sorted keys, no spaces, no NaN."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest_of(obj: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def mapping(obj: object, path: str) -> dict:
    if not isinstance(obj, dict):
        raise Malformed(path, f"expected an object, found {type(obj).__name__}")
    return obj


def sequence(obj: object, path: str) -> list:
    if not isinstance(obj, list):
        raise Malformed(path, f"expected a list, found {type(obj).__name__}")
    return obj


def require(obj: dict, key: str, path: str) -> object:
    if key not in obj:
        raise Malformed(f"{path}.{key}", "missing")
    return obj[key]


def string(obj: dict, key: str, path: str, *, allowed: set[str] | None = None) -> str:
    value = require(obj, key, path)
    if not isinstance(value, str) or not value.strip():
        raise Malformed(f"{path}.{key}", "expected a nonempty string")
    if allowed is not None and value not in allowed:
        raise Malformed(f"{path}.{key}", f"expected one of {sorted(allowed)}, found {value!r}")
    return value


def optional_string(
    obj: dict, key: str, path: str, *, allowed: set[str] | None = None
) -> str | None:
    if obj.get(key) is None:
        return None
    return string(obj, key, path, allowed=allowed)


def finite(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise Malformed(path, f"expected a finite number, found {type(value).__name__}")
    if not math.isfinite(value):
        raise Malformed(path, "expected a finite number")
    return float(value)


def integer(value: object, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Malformed(path, f"expected an integer, found {type(value).__name__}")
    if minimum is not None and value < minimum:
        raise Malformed(path, f"expected an integer >= {minimum}, found {value}")
    return value


def boolean(obj: dict, key: str, path: str) -> bool:
    value = require(obj, key, path)
    if not isinstance(value, bool):
        raise Malformed(f"{path}.{key}", "expected true or false")
    return value


def string_list(obj: dict, key: str, path: str) -> list[str]:
    items = sequence(obj.get(key, []), f"{path}.{key}")
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise Malformed(f"{path}.{key}[{index}]", "expected a nonempty string")
    return list(items)


def number_list(value: object, path: str) -> list[float]:
    return [finite(item, f"{path}[{index}]") for index, item in enumerate(sequence(value, path))]


@dataclass(frozen=True)
class Quantity:
    """A measured or declared number with a unit, or an explicit missing value."""

    value: float | None
    unit: str
    missing: str | None = None

    def to_dict(self) -> dict:
        data: dict = {"value": self.value, "unit": self.unit}
        if self.missing is not None:
            data["missing"] = self.missing
        return data


def parse_quantity(
    obj: object, path: str, *, unit: str | None = None, units: set[str] | None = None
) -> Quantity:
    data = mapping(obj, path)
    found_unit = string(data, "unit", path)
    if unit is not None and found_unit != unit:
        raise Malformed(f"{path}.unit", f"expected unit {unit!r}, found {found_unit!r}")
    if units is not None and found_unit not in units:
        raise Malformed(f"{path}.unit", f"expected one of {sorted(units)}, found {found_unit!r}")
    value = require(data, "value", path)
    if value is None:
        missing = data.get("missing")
        if not isinstance(missing, str) or not missing.strip():
            raise Malformed(f"{path}.missing", "a null value needs a missingness reason")
        return Quantity(None, found_unit, missing)
    return Quantity(finite(value, f"{path}.value"), found_unit)


def parse_duration(obj: object, path: str) -> float:
    """A duration or simulator time as seconds. Accepts ``s`` or ``ms`` explicitly."""
    quantity = parse_quantity(obj, path, units=set(DURATION_UNITS))
    if quantity.value is None:
        raise Malformed(path, f"missing duration ({quantity.missing})")
    return quantity.value * DURATION_UNITS[quantity.unit]


def parse_sim_time(obj: object, path: str, clock: str) -> float:
    data = mapping(obj, path)
    found = string(data, "clock", path)
    if found != clock:
        raise Malformed(
            f"{path}.clock", f"clock domain {found!r} does not match declared {clock!r}"
        )
    return parse_duration(data, path)


def parse_wall_time(obj: object, path: str) -> datetime:
    data = mapping(obj, path)
    string(data, "clock", path, allowed={WALL_CLOCK})
    raw = string(data, "value", path)
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError as error:
        raise Malformed(f"{path}.value", f"invalid ISO 8601 timestamp {raw!r}") from error
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise Malformed(f"{path}.value", "timestamp needs an explicit UTC offset")
    return stamp
