"""Explicit exact/numerical comparisons; return the first differing JSON path."""

from __future__ import annotations

import math

from nisayon.engine.io import canonical_bytes


def difference(reference: object, candidate: object, contract: dict, path: str = "") -> dict | None:
    """Compare observations, not physical adequacy or the truth of an oracle."""
    if (
        contract["kind"] == "numerical"
        and type(reference) in (int, float)
        and type(candidate) in (int, float)
    ):
        try:
            limit = contract.get("atol", 0) + contract.get("rtol", 0) * abs(reference)
            equal = math.isfinite(limit) and abs(candidate - reference) <= limit
        except OverflowError:
            equal = False
    elif type(reference) is dict and type(candidate) is dict:
        if set(reference) != set(candidate):
            return {
                "path": path,
                "reason": "object_keys",
                "reference": sorted(reference),
                "candidate": sorted(candidate),
            }
        for key in sorted(reference):
            escaped = key.replace("~", "~0").replace("/", "~1")
            result = difference(reference[key], candidate[key], contract, path + "/" + escaped)
            if result is not None:
                return result
        return None
    elif type(reference) is list and type(candidate) is list:
        if len(reference) != len(candidate):
            return {
                "path": path,
                "reason": "length",
                "reference": len(reference),
                "candidate": len(candidate),
            }
        for index, (left, right) in enumerate(zip(reference, candidate, strict=True)):
            result = difference(left, right, contract, path + f"/{index}")
            if result is not None:
                return result
        return None
    else:
        equal = canonical_bytes(reference) == canonical_bytes(candidate)
    return (
        None
        if equal
        else {"path": path, "reason": "value", "reference": reference, "candidate": candidate}
    )
