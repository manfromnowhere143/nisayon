"""Exercise the installed SDK with normally imported, source-pinned XPolicyLab helpers.

This uses exposed development cases. It is not an untouched reuse or owner-cost trial.
The retained upstream checkout and native environment are read, never modified.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import (
    CaseSpec,
    ExecutionContext,
    assess_change,
    assess_reuse,
    inspect_run,
    plan_change,
    run_plan,
)

ADAPTER = '''"""Development replay adapter; upstream functions run through normal imports."""
import numpy as np
from XPolicyLab.utils import process_data as native
import negative_process_data as negative


def exercise(value, implementation):
    fields = {key: np.asarray(item, dtype=np.float32) for key, item in value["fields"].items()}
    before = {key: item.copy() for key, item in fields.items()}
    expected = np.asarray(value["packed_input"], dtype=np.float32)
    try:
        packed = implementation.pack_robot_state(
            {"state": fields}, value["mode"], value["layout"], source_type=value["source_type"]
        )
        accepted, output = True, packed.tolist()
    except ValueError:
        accepted, output = False, None
    # Exercise unpack independently, including when packing rejected the input.
    try:
        restored = implementation.unpack_robot_state(
            expected, value["mode"], value["layout"], source_type=value["source_type"]
        )
        if isinstance(restored, list):
            restored = {key: np.stack([row[key] for row in restored]) for key in fields}
        unpack_accepted = True
        roundtrip = bool(set(restored) == set(fields) and all(
            np.array_equal(restored[key], fields[key]) for key in fields
        )) if accepted else None
    except ValueError:
        unpack_accepted, roundtrip = False, None
    return {
        "accepted": accepted, "packed": output, "unpack_accepted": unpack_accepted,
        "roundtrip_equal": roundtrip,
        "input_unchanged": all(np.array_equal(fields[key], before[key]) for key in fields),
    }


def reference(value):
    return exercise(value, native)


def candidate(value):
    return exercise(value, native)


def old_defect(value):
    return exercise(value, negative)
'''


def prepare(source: Path, readback: Path, owner: Path) -> dict:
    identities = json.loads(readback.read_text())
    expected = {item["path"]: item["sha256"] for item in identities["files"]}
    names = ["XPolicyLab.py", "utils/process_data.py", "utils/load_file.py", "LICENSE"]
    owner.mkdir()
    for name in names:
        assert file_digest(source / name) == expected[name], f"Retained source changed: {name}"
        target = owner / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    corrected = (owner / "utils/process_data.py").read_text()
    correction = '    if action_type == "ee":\n        arm_dims = [7] * len(arm_dims)\n'
    assert corrected.count(correction) == 1
    # Restore the known joint-width error, retaining the rest of the merged implementation.
    (owner / "negative_process_data.py").write_text(corrected.replace(correction, ""))
    (owner / "adapter.py").write_text(ADAPTER)
    (owner / "NOTICE.txt").write_text(
        "XPolicyLab source is attributable to its upstream authors under Apache-2.0.\n"
        "Repository: https://github.com/XPolicyLab/XPolicyLab\n"
        f"Revision: {identities['revision']}\n"
        "The native helpers are copied unchanged. negative_process_data.py deliberately\n"
        "removes the Cartesian-width correction for an exposed development control.\n"
        "Modification dated 22 October 2026. No upstream endorsement is implied.\n"
    )
    return {
        "repository": identities["repository"],
        "revision": identities["revision"],
        "upstream_files": {name: expected[name] for name in names},
        "negative_control": "Merged implementation with only the seven-value width override removed",
        "source_readback_sha256": file_digest(readback),
    }


def probe(layout: dict, mode: str, form: str, *, malformed: bool = False) -> dict:
    prefix_shape = {"obs-vector": (), "obs-chunk": (3,), "dataset-prefix": (2, 3)}[form]
    suffix = "s" if form == "dataset-prefix" else ""
    fields = {}

    # Dyadic values are exactly representable in float32. No NumPy is needed by the SDK host.
    def expand(values: list, shape: tuple, index: int = 0):
        if not shape:
            result = values.copy()
            result[0] += index / 16
            return result
        stride = 1 if len(shape) == 1 else shape[1]
        return [expand(values, shape[1:], index + i * stride) for i in range(shape[0])]

    for i, (joints, gripper) in enumerate(zip(layout["arm_dim"], layout["ee_dim"], strict=True)):
        prefix = "" if len(layout["arm_dim"]) == 1 else ["left_", "right_"][i]
        if mode == "ee":
            values = [0.25 + i, 0.5 + i, 0.75 + i, 1.0, 0.0, 0.0, 0.0]
            if malformed:
                values = values[:6]
            key = prefix + "ee_pose" + suffix
        else:
            values = [j / 8 + i for j in range(joints)]
            key = prefix + "arm_joint_state" + suffix
        fields[key] = expand(values, prefix_shape)
        fields[prefix + "ee_joint_state" + suffix] = expand(
            [0.25 + j / 8 for j in range(gripper)], prefix_shape
        )

    def concatenate(items: list, depth: int):
        if depth == 0:
            return [number for item in items for number in item]
        return [concatenate([item[i] for item in items], depth - 1) for i in range(len(items[0]))]

    packed = concatenate(list(fields.values()), len(prefix_shape))
    return {
        "id": f"{layout['id']}-{mode}-{form}" + ("-malformed" if malformed else ""),
        "input": {
            "fields": fields,
            "packed_input": packed,
            "layout": layout,
            "mode": mode,
            "source_type": "dataset" if form == "dataset-prefix" else "obs",
        },
        "expected": {
            "accepted": not malformed,
            "packed": None if malformed else packed,
            "unpack_accepted": not malformed,
            "roundtrip_equal": None if malformed else True,
            "input_unchanged": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--readback", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--native-python", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    provenance = prepare(args.source.resolve(), args.readback.resolve(), out / "owner")
    protocol = json.loads(args.protocol.read_text())
    layouts = protocol["ee_layouts"]
    probes = [probe(layout, "ee", form) for layout in layouts for form in protocol["array_layouts"]]
    probes += [
        probe(layout, "joint", form)
        for layout in layouts
        if layout["id"] in protocol["joint_layouts"]
        for form in protocol["array_layouts"]
    ]
    probes += [
        probe(layout, "ee", form, malformed=True)
        for layout in layouts
        if layout["id"] in {"single6", "dual6"}
        for form in ["obs-vector", "dataset-prefix"]
    ]
    assert len(probes) == protocol["total_cases"] == 22
    value = {
        "schema": "nisayon.qualification.case.v1",
        "id": "xpolicylab-cartesian-width",
        "question": "Does the merged helper satisfy declared Cartesian width and preserve joint packing?",
        "contract": {"kind": "exact"},
        "source_files": sorted(
            str(p.relative_to(out / "owner")) for p in (out / "owner").rglob("*") if p.is_file()
        ),
        "targets": {
            role: {
                "path": "adapter.py",
                "callable": symbol,
                "required_calls": [f"{module}.pack_robot_state", f"{module}.unpack_robot_state"],
            }
            for role, symbol, module in [
                ("reference", "reference", "native"),
                ("negative_control", "old_defect", "negative"),
                ("candidate", "candidate", "native"),
            ]
        },
        "premises": {
            "population": "22 exposed development layouts with constructed dyadic arrays; no learned policy",
            "state": "fresh_process",
            "environment": "Retained CPU environment; source-bound normal imports, no simulation or hardware",
            "oracle": "Seven Cartesian values from the upstream schema; explicit array concatenation and round trip",
        },
        "probes": probes,
    }
    write_json(out / "case.json", value)
    assessments = {}
    evidence = None
    for name, candidate in [("merged", "candidate"), ("restored-defect", "old_defect")]:
        case_value = json.loads(json.dumps(value))
        if candidate == "old_defect":
            case_value["targets"]["candidate"] = dict(case_value["targets"]["negative_control"])
        case = CaseSpec.from_dict(case_value)
        context = ExecutionContext.from_project(
            out / "owner",
            output_dir=out / name,
            python=args.native_python,
            timeout_seconds=20,
            total_seconds=300,
        )
        plan = plan_change(case, context=context)
        write_json(out / f"{name}-plan.json", plan.record())
        current = run_plan(plan, context=context)
        assessment = assess_change(case, current)
        assessment.write(out / f"{name}-assessment.json")
        assessments[name] = assessment.record()
        assert assessment.decision == ("adopt" if name == "merged" else "reject"), (
            assessment.record()
        )
        if name == "merged":
            evidence = current
    changed = json.loads(json.dumps(value))
    changed["premises"]["population"] = "A new owner and camera population, not yet executed"
    proposed = plan_change(
        CaseSpec.from_dict(changed),
        context=ExecutionContext.from_project(
            out / "owner", output_dir=out / "unexecuted", python=args.native_python
        ),
    )
    reuse = assess_reuse(evidence, proposed)
    write_json(out / "changed-population-reuse.json", reuse)
    assert reuse["verdict_applicability"] == "inapplicable" and not reuse["automatic_acceptance"]
    # Confirm the observations remain inspectable without the copied native source present.
    (out / "owner").rename(out / "owner-retained")
    assert inspect_run(out / "merged").decision == "adopt"
    receipt = {
        "schema": "nisayon.native-qualification.development-replay.v1",
        "provenance": provenance,
        "probes_per_role": len(probes),
        "native_calls": sum(len(item["attempts"]) for item in assessments.values()),
        "decisions": {key: item["software_decision"] for key, item in assessments.items()},
        "deployment_decisions": {
            key: item["deployment_decision"] for key, item in assessments.items()
        },
        "first_candidate_difference": next(
            row["candidate_difference"]
            for row in assessments["restored-defect"]["comparisons"]
            if row["candidate_difference"]
        ),
        "changed_population_reuse": reuse["verdict_applicability"],
        "inspect_after_source_relocation": "passed",
        "total_driver_wall_seconds": time.perf_counter() - started,
        "cost_boundary": "Driver setup, planning, all executions and assessments; excludes earlier engineering, installation, human/provider/compute costs",
        "scope": "Exposed native software regression; no new owner, untouched reuse, task success or comparative cost claim",
    }
    write_json(out / "result.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
