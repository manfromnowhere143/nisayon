"""Fetch only the pinned public sample packet, verifying size and every digest.

Recordings stay in the selected local artifact directory; this does not install
a simulator or establish that asset-specific terms permit redistribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from pathlib import Path

from nisayon.engine.io import write_json

MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs/experiments/results/robolab-record-001/sample-manifest.json"
)


def fetch(output: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text())
    output = output.resolve()
    if shutil.disk_usage(output.parent).free < 5 * 1024**3:
        raise RuntimeError("Less than 5 GiB free; do not grow artifacts")
    if sum(r["bytes"] for r in manifest["records"]) > 1024**2:
        raise ValueError("Pinned sample packet unexpectedly exceeds 1 MiB")
    output.mkdir(parents=True, exist_ok=False)
    write_json(
        output / "fetch-intent.json",
        {"schema": "nisayon.source-fetch.v1", "manifest": manifest, "status": "started"},
    )
    received, records = 0, []
    started = time.perf_counter()
    try:
        for item in manifest["records"]:
            name = item["path"]
            if Path(name).name != name or not item["source_url"].startswith(
                (
                    "https://raw.githubusercontent.com/NVlabs/RoboLab/",
                    "https://media.githubusercontent.com/media/NVlabs/RoboLab/",
                )
            ):
                raise ValueError("Unexpected source path or origin")
            partial = output / (name + ".partial")
            with urllib.request.urlopen(item["source_url"], timeout=30) as response:
                raw = response.read(item["bytes"] + 1)
            received += len(raw)
            with partial.open("xb") as stream:
                stream.write(raw)
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("Pinned source bytes differ: " + name)
            partial.rename(output / name)
            records.append(name)
        write_json(output / "manifest.json", manifest)
    finally:
        write_json(
            output / "fetch-result.json",
            {
                "schema": "nisayon.source-fetch-result.v1",
                "received_bytes": received,
                "verified_files": records,
                "complete": len(records) == len(manifest["records"]),
                "wall_s": time.perf_counter() - started,
            },
        )
    return {"received_bytes": received, "verified_files": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(fetch(args.output), indent=2))


if __name__ == "__main__":
    main()
