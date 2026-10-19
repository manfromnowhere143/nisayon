"""Fetch only the pinned native files needed by the bounded resume checks."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory; existing paths are refused")
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("source-manifest.json").read_text())
    args.output.mkdir(parents=True, exist_ok=False)

    def fetch(item: dict) -> None:
        path = PurePosixPath(item["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Invalid source path: {path}")
        with urlopen(item["url"], timeout=60) as response:
            raw = response.read()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if (
            len(raw) != item["bytes"]
            or hashlib.sha256(raw).hexdigest() != item["sha256"]
            or blob != item["git_blob"]
        ):
            raise ValueError(f"Source identity mismatch: {path}")
        destination = args.output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(fetch, manifest["files"]))
    print(f"Verified {len(manifest['files'])} files at {manifest['head']}")


if __name__ == "__main__":
    main()
