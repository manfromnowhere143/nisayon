"""Recalculate scoped outcomes from the separate request and effect journals.

This checks consistency and coverage, not the authenticity of a server journal.
"""

import hashlib
import json
import sys
from pathlib import Path


def audit(root):
    root = Path(root)
    results = json.loads((root / "results.json").read_text())
    rows = results["rows"]
    if len(rows) != 14:
        raise ValueError("Missing or duplicate assignments")
    seen = set()
    for row in rows:
        key = (row["serialized"], row["phase"], row["retry_budget"], row["deduplicate"])
        if key in seen:
            raise ValueError("Duplicate assignment")
        seen.add(key)
        folder = root / (f"{key[0]}-deduplicated" if key[3] else f"{key[0]}-{key[1]}-{key[2]}")
        observation = json.loads((folder / "observation.json").read_text())
        if observation != row:
            raise ValueError("Summary disagrees with observation")
        effects_bytes = (folder / "effects.jsonl").read_bytes()
        if hashlib.sha256(effects_bytes).hexdigest() != row["journal_sha256"]:
            raise ValueError("Effect journal digest mismatch")
        effects = [json.loads(line) for line in effects_bytes.splitlines()]
        requests = [
            json.loads(line) for line in (folder / "requests.jsonl").read_text().splitlines()
        ]
        if len(effects) != row["effects"] or len(requests) != row["requests"]:
            raise ValueError("Summary count disagrees with journals")
        if any(event["operation_key"] != "one-intent" for event in effects):
            raise ValueError("Wrong operation")
        if [event["effect_number"] for event in effects] != list(range(1, len(effects) + 1)):
            raise ValueError("Effect sequence mismatch")
        if [event["attempt"] for event in requests] != list(range(1, len(requests) + 1)):
            raise ValueError("Request sequence mismatch")
        expected_requests = 2 if key[2] == 1 and key[1] != "none" else 1
        expected_effects = (
            1
            if key[3] or key[1] == "none"
            else expected_requests - 1
            if key[1] == "before"
            else expected_requests
        )
        expected_status = "exception" if key[1] != "none" and key[2] == 0 else "acknowledged"
        if (len(requests), len(effects), row["status"]) != (
            expected_requests,
            expected_effects,
            expected_status,
        ):
            raise ValueError("Scoped outcome contract not met")
    expected = {
        (s, p, n, False) for s in (True, False) for p in ("none", "before", "after") for n in (0, 1)
    }
    expected |= {(s, "after", 1, True) for s in (True, False)}
    if seen != expected:
        raise ValueError("Assignment coverage differs from protocol")
    return {
        "status": "supported_scoped_transport_outcomes",
        "conditions": len(rows),
        "duplicate_effect_conditions": sum(r["effects"] == 2 for r in rows),
        "failed_call_with_committed_effect_conditions": sum(
            r["status"] == "exception" and r["effects"] == 1 for r in rows
        ),
        "independent_external_review": False,
        "complete_cost_advantage": None,
    }


if __name__ == "__main__":
    print(json.dumps(audit(sys.argv[1]), indent=2))
