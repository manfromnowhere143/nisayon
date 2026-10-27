"""Explicit local condition consumption; no custody or independence claim."""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

from nisayon.engine.io import decode_json, digest, write_json

from .models import CaseSpec, fields


def _normalized(value: object, depth: int = 0) -> object:
    if depth > 64:
        raise ValueError("Condition input nesting exceeds 64 levels")
    if type(value) in (int, float):
        number = Fraction(value)
        # Conservatively treat 1 and 1.0, and signed zeros, as the same condition.
        # Never round large integers through float to obtain an identity.
        return ["number", str(number.numerator), str(number.denominator)]
    if isinstance(value, dict):
        return ["object", [[key, _normalized(value[key], depth + 1)] for key in sorted(value)]]
    if isinstance(value, list):
        return ["array", [_normalized(item, depth + 1) for item in value]]
    return [type(value).__name__, value]


def condition_ids(case: CaseSpec) -> list[str]:
    result = [digest(_normalized(probe["input"])) for probe in case.record()["probes"]]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate conditions do not provide additional confirmation")
    return result


def reserve_conditions(
    root: Path, investigation: list[str], confirmation: list[str], protocol_sha256: str
) -> dict:
    """Consume before execution; exclusive creation prevents duplicate reservations.

    A partial reservation remains spent. The caller explicitly chooses a shared
    store for this workload. Other stores, undisclosed experiments and independent
    clones are outside its coverage. Changing a case label does not reset it.
    """
    all_ids = investigation + confirmation + [protocol_sha256]
    if (
        len(investigation) > 64
        or not 1 <= len(confirmation) <= 32
        or any(
            not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key) for key in all_ids
        )
        or len(set(investigation)) != len(investigation)
        or len(set(confirmation)) != len(confirmation)
        or set(investigation) & set(confirmation)
    ):
        raise ValueError("Conditions require bounded distinct SHA-256 identities")
    if root.is_symlink():
        raise ValueError("Condition store must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    records = {}
    for purpose, values in (("investigation", investigation), ("confirmation", confirmation)):
        for key in values:
            path = root / f"{key}.json"
            record = {
                "schema": "nisayon.qualification.condition.v1",
                "condition_sha256": key,
                "first_protocol_sha256": protocol_sha256,
                "purpose": purpose,
            }
            try:
                write_json(path, record)
            except FileExistsError:
                if purpose == "confirmation":
                    raise ValueError(
                        "Confirmation condition already reserved or consumed"
                    ) from None
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Invalid retained condition record") from None
                with path.open("rb") as stream:
                    data = stream.read(8193)
                if len(data) > 8192:
                    raise ValueError("Condition record exceeds its bound") from None
                record = fields(decode_json(data), set(record))
                if (
                    record["schema"] != "nisayon.qualification.condition.v1"
                    or record["condition_sha256"] != key
                    or record["purpose"] not in {"investigation", "confirmation"}
                    or not isinstance(record["first_protocol_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", record["first_protocol_sha256"])
                ):
                    raise ValueError("Invalid retained condition identity") from None
            records[key] = record
    return {
        "schema": "nisayon.qualification.reservations.v1",
        "records": records,
        "scope": "Explicit local store only. Inputs outside this store may already be exposed; no blinding, independence or external freshness is established.",
    }
