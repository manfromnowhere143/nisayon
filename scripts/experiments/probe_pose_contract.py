"""Check a pinned XPolicyLab pose contract using its normally imported helpers."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--import-supplement", required=True, type=Path)
    parser.add_argument("--variant", choices=["baseline", "candidate"], required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(parents=True, exist_ok=False)
    source = args.source.absolute()
    protocol = json.loads(args.protocol.read_bytes())
    supplement = json.loads(args.import_supplement.read_bytes())
    expected_hashes = dict(protocol["source_sha256"])
    expected_hashes["client_server/tcp/model_server.py"] = supplement["source"]["sha256"]
    source_hashes = {p: digest(source / p) for p in expected_hashes}
    changes = [p for p, h in source_hashes.items() if h != expected_hashes[p]]
    assert changes == ([] if args.variant == "baseline" else ["utils/process_data.py"])
    sys.path.insert(0, str(source))
    import numpy as np
    from XPolicyLab.utils import process_data
    from XPolicyLab.utils.debug_env_client import validate_robot_state_dict

    assert Path(process_data.__file__).resolve() == source / "utils/process_data.py"
    receipt = {
        "schema": "nisayon.pose-contract.probe.v1",
        "started_at": datetime.now(UTC).isoformat(),
        "variant": args.variant,
        "source_revision": protocol["source_revision"],
        "source_sha256": source_hashes,
        "protocol_sha256": digest(args.protocol),
        "import_supplement_sha256": digest(args.import_supplement),
        "script_sha256": digest(Path(__file__)),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "scope": "Native CPU conversion/validation functions and constructed arrays; no policy run",
        "cases": [],
    }

    def save() -> None:
        (out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def state(layout: dict, mode: str, form: str, *, malformed: bool = False):
        prefix_shape = {"obs-vector": (), "obs-chunk": (3,), "dataset-prefix": (2, 3)}[form]
        suffix = "s" if form == "dataset-prefix" else ""
        fields, expected = {}, []
        for i, (joints, gripper) in enumerate(
            zip(layout["arm_dim"], layout["ee_dim"], strict=True)
        ):
            prefix = "" if len(layout["arm_dim"]) == 1 else ["left_", "right_"][i]
            if mode == "ee":
                # Position + unit quaternion; these do not depend on joint count.
                values = np.array([0.2 + i, 0.3 + i, 0.4 + i, 1, 0, 0, 0], dtype=np.float32)
                if malformed:
                    values = values[:6]
                key = prefix + "ee_pose" + suffix
            else:
                values = np.arange(joints, dtype=np.float32) / 10 + i
                key = prefix + "arm_joint_state" + suffix
            values = np.broadcast_to(values, prefix_shape + values.shape).copy()
            if prefix_shape:
                offsets = np.arange(np.prod(prefix_shape), dtype=np.float32).reshape(prefix_shape)
                values[..., 0] += offsets / 100
            fields[key] = values
            grip = np.arange(gripper, dtype=np.float32) / 10 + 0.25
            grip = np.broadcast_to(grip, prefix_shape + grip.shape).copy()
            fields[prefix + "ee_joint_state" + suffix] = grip
            expected.extend([values, grip])
        return fields, np.concatenate(expected, axis=-1)

    def native_oracle(fields: dict, layout: dict, form: str) -> None:
        # Validate individual records with the unmodified upstream debug oracle.
        singular = {
            (key[:-1] if form == "dataset-prefix" else key): value.reshape(-1, value.shape[-1])
            for key, value in fields.items()
        }
        for index in range(len(next(iter(singular.values())))):
            validate_robot_state_dict(
                {key: value[index] for key, value in singular.items()}, layout
            )

    def run_case(layout: dict, mode: str, form: str, *, malformed: bool = False) -> None:
        fields, expected = state(layout, mode, form, malformed=malformed)
        original = {key: value.copy() for key, value in fields.items()}
        source_type = "dataset" if form == "dataset-prefix" else "obs"
        row = {
            "id": f"{layout['id']}-{mode}-{form}" + ("-malformed" if malformed else ""),
            "layout": layout,
            "mode": mode,
            "form": form,
            "expected_shape": list(expected.shape),
            "native_oracle_accepts": None,
        }
        try:
            try:
                native_oracle(fields, layout, form)
                row["native_oracle_accepts"] = True
            except ValueError:
                row["native_oracle_accepts"] = False
            assert row["native_oracle_accepts"] is not malformed
            if malformed:
                rejected = []
                for operation in [
                    lambda: process_data.pack_robot_state(
                        {"state": fields}, mode, layout, source_type=source_type
                    ),
                    lambda: process_data.unpack_robot_state(
                        expected, mode, layout, source_type=source_type
                    ),
                ]:
                    try:
                        operation()
                        rejected.append(False)
                    except ValueError:
                        rejected.append(True)
                row["malformed_pack_unpack_rejected"] = rejected
                assert all(rejected), "helper accepted a pose rejected by native schema validator"
            else:
                packed = process_data.pack_robot_state(
                    {"state": fields}, mode, layout, source_type=source_type
                )
                np.testing.assert_array_equal(packed, expected)
                unpacked = process_data.unpack_robot_state(
                    packed, mode, layout, source_type=source_type
                )
                if isinstance(unpacked, list):
                    restored = {key: np.stack([row[key] for row in unpacked]) for key in fields}
                else:
                    restored = unpacked
                assert list(restored) == list(fields)
                for key in fields:
                    np.testing.assert_array_equal(restored[key], fields[key])
                native_oracle(restored, layout, form)
                row["packed_sha256"] = hashlib.sha256(packed.tobytes()).hexdigest()
            for key in fields:
                np.testing.assert_array_equal(fields[key], original[key])
            row["passed"] = True
        except Exception as exc:
            row.update(
                passed=False, error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()
            )
        row["inputs_unchanged"] = all(np.array_equal(fields[k], original[k]) for k in fields)
        row["passed"] = row["passed"] and row["inputs_unchanged"]
        receipt["cases"].append(row)
        save()

    for layout in protocol["ee_layouts"]:
        for form in protocol["array_layouts"]:
            run_case(layout, "ee", form)
    for layout in protocol["ee_layouts"]:
        if layout["id"] in protocol["joint_layouts"]:
            for form in protocol["array_layouts"]:
                run_case(layout, "joint", form)
    for label in protocol["invalid_cases"]:
        name, source_type = label.split("-")
        layout = next(x for x in protocol["ee_layouts"] if x["id"] == name)
        run_case(
            layout,
            "ee",
            "obs-vector" if source_type == "obs" else "dataset-prefix",
            malformed=True,
        )
    assert len(receipt["cases"]) == protocol["total_cases"]
    receipt["source_unchanged"] = source_hashes == {p: digest(source / p) for p in source_hashes}
    receipt["passed"] = sum(row["passed"] for row in receipt["cases"])
    receipt["failed"] = len(receipt["cases"]) - receipt["passed"]
    receipt["completed_at"] = datetime.now(UTC).isoformat()
    save()
    print(
        json.dumps(
            {key: receipt[key] for key in ["variant", "passed", "failed", "source_unchanged"]}
        )
    )
    return 0 if receipt["failed"] == 0 and receipt["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
