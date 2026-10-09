"""Read-only integrity audit for the two actual integration inputs; no simulation."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from nisayon.engine.io import canonical_bytes, file_digest, write_json
from nisayon.evaluation.external import inventory_from_external_record

INPUTS = {
    "artifacts/retained-declarations-002/packet.json": (
        "fe3f81772490487d77288f15864fc19b5fac98822c290ce3dbb4e23b730f558a"
    ),
    "artifacts/robolab-import-006/external-record.json": (
        "089983905a37f02e65c66593106046a7007060749a01fd667917f39dc621a624"
    ),
}


def audit(root: Path) -> dict:
    for relative, expected in INPUTS.items():
        assert file_digest(root / relative) == expected, relative
    location = json.loads(
        (
            root / "docs/experiments/results/retained-declarations-002/retained-location.json"
        ).read_text()
    )
    packet_root = root / "artifacts/retained-declarations-002"
    for relative, expected in location["files"].items():
        path = packet_root / relative
        assert path.stat().st_size == expected["bytes"], relative
        assert file_digest(path) == expected["sha256"], relative

    external_path = root / "artifacts/robolab-import-006/external-record.json"
    document = json.loads(external_path.read_text())
    before = canonical_bytes(document)
    fields = []
    for episode in document["episodes"]:
        for name, field in episode["fields"].items():
            array = np.asarray(field["values"], dtype=field["dtype"])
            assert list(array.shape) == field["shape"], name
            metadata = {"dtype": field["dtype"], "shape": field["shape"]}
            actual = hashlib.sha256(
                canonical_bytes(metadata) + b"\n" + array.tobytes(order="C")
            ).hexdigest()
            assert actual == field["values_sha256"], name
            fields.append(
                {
                    "episode": episode["id"],
                    "field": name,
                    **metadata,
                    "values_sha256": actual,
                    "frame": field["mapping"]["frame"],
                    "alignment": field["mapping"]["alignment"],
                }
            )
    assert len(fields) == 43
    inventory = inventory_from_external_record(document)
    assert canonical_bytes(document) == before, "inventory conversion mutated the reader output"
    assert sum(len(e["fields"]) for e in inventory["episodes"]) == len(fields)

    source_root = root / "artifacts/robolab-reproduced-source-001"
    sources = document["source_packet"]["records"]
    for source in sources:
        path = source_root / source["path"]
        assert path.stat().st_size == source["bytes"], source["path"]
        assert file_digest(path) == source["sha256"], source["path"]
    for relative, expected in INPUTS.items():
        assert file_digest(root / relative) == expected, relative
    return {
        "schema": "nisayon.integration-input-audit.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "inputs": INPUTS,
        "native_packet_files_verified": len(location["files"]),
        "pinned_source_members_verified": len(sources),
        "numeric_fields_verified": len(fields),
        "numeric_fields": fields,
        "conversion_mutated_input": False,
        "scope": (
            "Retained original bytes and all numeric field digests verified after the actual "
            "workflows. The assessment is a projection; this companion preserves the field "
            "digests. No simulator, model, producer execution attestation or repair evidence."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(Path.cwd().resolve())
    write_json(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "numeric_fields"}, indent=2))
