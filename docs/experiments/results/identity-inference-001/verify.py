"""Verify retained software evidence without rerunning any experiment."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "raw-manifest.json").read_text())
    raw = (root / manifest["path"]).read_bytes()
    assert digest(raw) == manifest["sha256"] and len(raw) == manifest["bytes"]
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        assert len({m.name for m in members}) == len(members)
        assert all(m.isfile() for m in members)
        files = {m.name: archive.extractfile(m).read() for m in members}
    assert files.keys() == manifest["members"].keys()
    for name, expected in manifest["members"].items():
        assert digest(files[name]) == expected["sha256"], name
        assert len(files[name]) == expected["bytes"], name

    variants = ["baseline", "baseline-v2", "candidate-run", "baseline-v3", "final"]
    runs = {n: json.loads(files[f"runs/{n}/result.json"]) for n in variants}
    assert [(runs[n]["passed"], runs[n]["failed"]) for n in variants] == [
        (18, 30),
        (28, 20),
        (48, 0),
        (34, 22),
        (56, 0),
    ]
    for name, run in runs.items():
        assert run["cli_agreement"] and len(run["cli"]) == 5
        assert all(row["matches_library"] for row in run["cli"])
        for path, expected in run["input_sha256"].items():
            assert digest(files[f"runs/{name}/{path}"]) == expected
            assert runs["final"]["input_sha256"][path] == expected
    assert runs["baseline-v3"]["input_sha256"] == runs["final"]["input_sha256"]
    assert len(runs["final"]["cases"]) == 56
    for row in runs["final"]["cases"]:
        assert row["passed"] and row["observed_identity"] == row["expected_identity"]
        assert row["gate"] == row["expected_gate"]
        assert (
            row["gate_exit"]
            == {"REVIEW": 0, "BLOCK": 1, "INSUFFICIENT_DATA": 2}[row["expected_gate"]]
        )
        if row["gate"] == "BLOCK":
            assert row["comparison_status"] == "cannot_compare" and row["comparable"] == 0
        if row["id"].startswith("multi_explicit_complete"):
            assert row["origin"] == "eval_info.per_task[].task"
    old = {r["id"]: r for r in runs["baseline-v3"]["cases"]}
    for row in runs["final"]["cases"]:
        before = old[row["id"]]
        if not before["passed"]:
            assert (before["gate"], before["gate_exit"], before["comparable"]) == (
                "REVIEW",
                0,
                30,
            )
            assert row["gate"] == "BLOCK"
    for command in (
        "native-original-command",
        "native-candidate-command",
        "native-final-command",
    ):
        record = json.loads(files[f"commands/{command}.json"])
        assert record["returncode"] == 0
        for stream, expected in record["logs"].items():
            data = files[f"command-logs/{record['id']}/{stream}"]
            assert digest(data) == expected["sha256"] and len(data) == expected["bytes"]
        assert b"38 passed" in files[f"command-logs/{record['id']}/stdout.log"]

    for freeze, key, protocol in (
        ("protocol-freeze.json", "protocol_sha256", "PROTOCOL.md"),
        ("candidate-freeze.json", "protocol_v2_sha256", "PROTOCOL-v2.md"),
        ("expanded-freeze.json", "protocol_sha256", "PROTOCOL-v3.md"),
    ):
        record = json.loads((root / freeze).read_text())
        assert record[key] == digest((root / protocol).read_bytes())
    for variant, probe in (
        ("baseline", "probe-initial.py"),
        ("baseline-v2", "probe-v2.py"),
        ("final", "probe.py"),
    ):
        assert runs[variant]["probe_sha256"] == digest((root / probe).read_bytes())

    with tempfile.TemporaryDirectory(prefix="nisayon-identity-readback-") as directory:
        destination = Path(directory)
        wheel = files["packages/arisole_eval-0.1.5-py3-none-any.whl"]
        with zipfile.ZipFile(io.BytesIO(wheel)) as package:
            # Only the source module is needed to verify patch applicability.
            source = package.read("arisole_eval/lerobot/meta.py")
        module = destination / "arisole_eval/lerobot/meta.py"
        module.parent.mkdir(parents=True)
        module.write_bytes(source)
        assert digest(source) == runs["baseline-v3"]["module_sha256"]
        assert source == (root / "upstream-meta.py.txt").read_bytes()
        subprocess.run(
            ["patch", "--batch", "-p1", "-i", str(root / "identity-coverage.patch")],
            cwd=destination,
            check=True,
            capture_output=True,
            timeout=10,
        )
        assert digest(module.read_bytes()) == runs["final"]["module_sha256"]
    print(
        json.dumps(
            {
                "status": "verified_retained_bytes",
                "archive_members": len(files),
                "original_controls_passed": 34,
                "final_controls_passed": 56,
                "native_tests_passed_per_variant": 38,
                "scope": "Readback and patch applicability; no new experiment or physical claim",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
