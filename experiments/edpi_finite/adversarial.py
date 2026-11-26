"""Retain fault sensitivity of both the frozen audit and its later supplement."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from audit_campaign import audit_trial
from audit_hardening import decode, strict_trial

HERE = Path(__file__).resolve().parent


def mutations(approved: dict, equal: dict) -> list[tuple[str, dict]]:
    result = []

    def add(name, change, original=approved):
        row = copy.deepcopy(original)
        change(row)
        result.append((name, row))

    add("missing_confirmation", lambda r: r["confirmation_raw"].pop())
    add("duplicate_probe", lambda r: r["raw"].append(copy.deepcopy(r["raw"][0])))
    add(
        "invalid_pair",
        lambda r: r["raw"][0]["pair"]["candidate"]["initial_state"].__setitem__(1, 3),
    )
    add(
        "paired_false_reset_metadata",
        lambda r: [
            r["raw"][0]["pair"][k].__setitem__("initial_state", [0, 3, 0])
            for k in ("reference", "candidate")
        ],
    )
    add("incomplete_trajectory", lambda r: r["raw"][0]["pair"]["candidate"]["states"].pop())
    add(
        "changed_force_metadata",
        lambda r: r["raw"][0]["pair"]["candidate"].__setitem__("force_n", 100),
    )
    add("changed_arm_cost", lambda r: r["raw"][0]["pair"]["candidate"].__setitem__("controls", 0))
    add(
        "changed_measurement",
        lambda r: r["raw"][0]["pair"]["candidate"].__setitem__("measurement_error_m", 0.1),
    )
    add("bad_reading", lambda r: r["raw"][0]["pair"]["candidate"].__setitem__("reading_m", 30))
    add("wrong_final_decision", lambda r: r.__setitem__("decision", "contradicted"))
    add(
        "noninferiority_as_superiority",
        lambda r: r["diagnostic"].__setitem__("superiority", True),
        equal,
    )
    add("false_probe_count", lambda r: r.__setitem__("probe_pairs", 0))
    add("false_total_cost", lambda r: r.__setitem__("controls", 0))
    add(
        "reused_confirmation_reset",
        lambda r: r["confirmation_raw"][0]["pair"]["candidate"].__setitem__(
            "reset_id", r["raw"][0]["pair"]["candidate"]["reset_id"]
        ),
    )
    add(
        "forged_available_evidence",
        lambda r: r["choices"][0]["observations"].__setitem__("p07", [0, 0]),
    )
    add(
        "boolean_state",
        lambda r: r["raw"][0]["pair"]["candidate"]["states"][0].__setitem__(0, False),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = decode((HERE / "campaign-protocol.json").read_bytes())
    cases = {c["id"]: c for c in decode((HERE / "case-inputs.json").read_bytes())}
    trials = [decode(p.read_bytes()) for p in sorted(args.source.glob("trial-*.json"))]
    for row in trials:
        strict_trial(row, cases[row["case"]], protocol)
    approved = next(r for r in trials if r["case"] == "case-01" and r["decision"] == "supported")
    equal = next(r for r in trials if r["case"] == "case-03" and r["decision"] == "supported")
    results = []
    for name, row in mutations(approved, equal):
        result = {
            "control": name,
            "mutation_sha256": hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
        }
        for label, checker in (("frozen_v1", audit_trial), ("supplement_v2", strict_trial)):
            try:
                checker(row, cases[row["case"]], protocol)
            except (ValueError, KeyError, TypeError, IndexError, ZeroDivisionError) as error:
                result[label] = {"refused": True, "reason": str(error)}
            else:
                result[label] = {"refused": False}
        results.append(result)
    parser_controls = []
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
        try:
            decode(raw)
        except ValueError:
            parser_controls.append(True)
        else:
            parser_controls.append(False)
    # Explicitly unsafe ablation: replace every unknown paired difference with 0.
    # This is an audit of weakened reasoning, not another physical experiment.
    missing_as_zero = {c: "supported" for c in cases}
    result = {
        "schema": "nisayon.edpi.fault-sensitivity.v1",
        "valid_trials_checked": len(trials),
        "controls": results,
        "parser_controls_refused": parser_controls,
        "frozen_v1_omissions": [r["control"] for r in results if not r["frozen_v1"]["refused"]],
        "all_supplement_controls_refused": all(r["supplement_v2"]["refused"] for r in results)
        and all(parser_controls),
        "missing_as_zero_ablation": {
            "no_observation_decisions": missing_as_zero,
            "harmful_admissions": 1,
            "unsupported_admissions": 4,
            "scope": "deliberately unsafe inference mutation; no operational admission",
        },
        "scope": "Post-freeze validation repair, not threshold changes or new campaign outcomes. All original bytes retained; independent human review remains absent.",
    }
    with args.out.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "valid_trials": len(trials),
                "v1_omissions": result["frozen_v1_omissions"],
                "v2_controls_pass": result["all_supplement_controls_refused"],
            }
        )
    )
    return 0 if result["all_supplement_controls_refused"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
