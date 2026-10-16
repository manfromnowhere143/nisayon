"""Verify retained routing evidence without compiling or executing it."""

import hashlib
import json
import tarfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "raw-manifest.json").read_text())
    archive = root / manifest["archive"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["sha256"]
    expected = {entry["path"]: entry for entry in manifest["members"]}
    assert len(expected) == len(manifest["members"])
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        assert len(members) == len(expected)
        assert {member.name for member in members} == set(expected)
        data = {}
        for member in members:
            assert member.isfile()
            content = source.extractfile(member).read()
            entry = expected[member.name]
            assert len(content) == entry["bytes"]
            assert hashlib.sha256(content).hexdigest() == entry["sha256"]
            data[member.name] = content
    final = json.loads(data["run-002/report.json"])
    first = json.loads(data["run-001/report.json"])
    assert first["variants"] == final["variants"]
    assert (root / "result.json").read_bytes() == data["run-002/report.json"]
    assert (root / "PROTOCOL.md").read_bytes() == data["ROUTING_PROTOCOL.md"]
    assert (root / "envelope-key.patch").read_bytes() == data["run-002/envelope-key.patch"]
    for run, driver in (
        ("run-001", "driver-first-executed.py"),
        ("run-002", "driver-final-executed.py"),
    ):
        result = json.loads(data[f"{run}/report.json"])
        assert hashlib.sha256(data[driver]).hexdigest() == result["driver_sha256"]
        assert hashlib.sha256(data["harness-executed.cpp"]).hexdigest() == result["harness_sha256"]
        for name, digest in result["source_sha256"].items():
            assert hashlib.sha256(data[f"source/{name}"]).hexdigest() == digest
        for variant, entry in result["variants"].items():
            assert json.loads(data[f"{run}/{variant}.stdout.log"]) == {
                key: value
                for key, value in entry.items()
                if key not in ("process_exit_code", "extracted_source_sha256")
            }
            extracted = data[f"{run}/{variant}/routing_functions.inc"]
            assert hashlib.sha256(extracted).hexdigest() == entry["extracted_source_sha256"]
    source = data["source/VinRobotics/vla.cpp/src/serving/server.cpp"].decode()
    original = data["run-002/original/routing_functions.inc"].decode()
    for signature, metadata in final["extractions"].items():
        start = source.index(signature)
        function = source[start : source.index("\n}", start) + 2]
        assert function in original
        assert hashlib.sha256(function.encode()).hexdigest() == metadata["sha256"]
    print(
        f"Verified {len(expected)} archived members, both runs, exact source extractions and reports."
    )


if __name__ == "__main__":
    main()
