"""Exposed lexical-value control; run unchanged before and after the correction."""

import json
import sys
from decimal import Decimal

from nisayon.engine.io import decode_json
from nisayon.qualification import MeasurementContract, assess_measurements
from nisayon.qualification.compare import difference

TOKENS = [
    "1e-400",
    "-1e-400",
    "1e-324",
    "2e-324",
    "-2.4E-324",
    "3e-324",
    "5e-324",
    "0e-400",
    "-0.00e9999",
    "0.1",
]
rows = []
for token in TOKENS:
    row = {"token": token, "exact_decimal_nonzero": not Decimal(token).is_zero()}
    try:
        value = decode_json(token)
    except ValueError as error:
        row.update(status="refused", error=str(error))
    else:
        row.update(
            status="decoded",
            decoded_hex=value.hex(),
            numerically_equal_zero=difference(0, value, {"kind": "numerical", "atol": 0, "rtol": 0})
            is None,
        )
    rows.append(row)

contract = MeasurementContract.from_dict(
    {
        "schema": "nisayon.qualification.measurement_contract.v1",
        "id": "raw-underflow",
        "scope": "Exposed JSON ingestion control; no physical measurement",
        "metrics": {
            "error": {
                "unit": "m",
                "boundary": "constructed scalar",
                "conditions": ["one"],
                "relation": "equal",
                "aggregation": "all",
            }
        },
    }
)
reference = {
    "schema": "nisayon.qualification.measurements.v1",
    "origin": "exposed_control",
    "complete": True,
    "metrics": {
        "error": {
            "unit": "m",
            "boundary": "constructed scalar",
            "values": {"one": 0},
        }
    },
}
candidate_bytes = json.dumps(reference).replace('"one": 0', '"one": 1e-400')
try:
    candidate = decode_json(candidate_bytes)
except ValueError as error:
    measurement = {"ingestion": "refused", "assessment": None, "error": str(error)}
else:
    measurement = {
        "ingestion": "decoded",
        "assessment": assess_measurements(contract, reference, candidate),
    }
print(json.dumps({"python": sys.version, "rows": rows, "measurement": measurement}, indent=2))
