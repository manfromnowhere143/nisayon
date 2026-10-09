"""Write the labelled clock-boundary diagnostic inputs beside this script.

Each input is a copy of the committed healthy trace T01 (unfenced remedy) with the
observation stamp moved to the `sensor` clock and one clock-declaration variant applied,
exactly as the coordinator's diagnostic did. They are API/CLI diagnostic inputs, never
executed producer assignments; the committed trace is not modified.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
SOURCE = (
    REPO
    / "docs/experiments/results/temporal-integration-001/execution-001/traces/T01-healthy--unfenced_queue_control.json"
)
FRESH = {"from": "sensor", "to": "controller", "offset": 0, "uncertainty": 0, "unit": "ns"}
STALE = {**FRESH, "offset": -100_000_000}


def variants(base: dict) -> dict[str, dict]:
    mapped = copy.deepcopy(base)
    for event in mapped["events"]:
        if event["kind"] == "observation_acquired":
            event["at"]["clock"] = "sensor"
    out = {"unchanged_healthy": copy.deepcopy(base)}
    for name, mappings in [
        ("single_fresh", [FRESH]),
        ("single_stale", [STALE]),
        ("conflict_fresh_first", [FRESH, STALE]),
        ("conflict_stale_first", [STALE, FRESH]),
        ("negative_uncertainty", [{**FRESH, "uncertainty": -1}]),
        ("mapping_container_scalar", 1),
        ("mapping_container_object", dict(FRESH)),
        ("non_object_member", [None, FRESH]),
        ("duplicate_declaration", [FRESH, dict(FRESH)]),
        (
            "reverse_direction_equivalent",
            [
                FRESH,
                {"from": "controller", "to": "sensor", "offset": 0, "uncertainty": 0, "unit": "ns"},
            ],
        ),
        ("unsupported_field", [{**FRESH, "rate": 1.0}]),
        ("boolean_offset", [{**FRESH, "offset": True}]),
        ("unit_mismatch", [{**FRESH, "unit": "ms"}]),
    ]:
        trace = copy.deepcopy(mapped)
        trace["clocks"]["declared_mappings"] = copy.deepcopy(mappings)
        out[name] = trace
    for name, names in [
        ("undeclared_acquisition_clock", ["controller"]),
        ("missing_clock_names", None),
    ]:
        trace = copy.deepcopy(mapped)
        trace["clocks"]["declared_mappings"] = [dict(FRESH)]
        if names is None:
            del trace["clocks"]["names"]
        else:
            trace["clocks"]["names"] = names
        out[name] = trace
    trace = copy.deepcopy(mapped)
    del trace["clocks"]
    out["no_clocks_object"] = trace
    return out


def main() -> int:
    raw = SOURCE.read_bytes()
    base = json.loads(raw)
    manifest = {
        "source_trace": str(SOURCE.relative_to(REPO)),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "role": "labelled diagnostic copies of one committed exposed trace; never executed producer assignments",
        "inputs": {},
    }
    for name, trace in variants(base).items():
        trace["case_id"] = f"diagnostic-{name}"
        path = HERE / "inputs" / f"{name}.json"
        path.write_text(json.dumps(trace, indent=1, sort_keys=True) + "\n")
        manifest["inputs"][name] = {
            "path": str(path.relative_to(REPO)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (HERE / "inputs" / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote {len(manifest['inputs'])} inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
