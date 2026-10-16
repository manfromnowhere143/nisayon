"""Fetch only the pinned public confirmation packet described by protocol.json."""

import argparse
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
protocol_path = Path(__file__).with_name("protocol.json")
protocol = json.loads(protocol_path.read_text())
base = protocol["source_repository"].replace("github.com", "raw.githubusercontent.com")
base += "/" + protocol["source_revision"] + "/"


def fetch(row):
    rel = Path(row["path"])
    assert not rel.is_absolute() and ".." not in rel.parts
    target = args.out / rel
    reused = target.exists()
    if reused:
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(base + rel.as_posix(), timeout=45) as response:
            data = response.read(row["bytes"] + 1)
    assert len(data) == row["bytes"], rel
    git_blob = b"blob " + str(len(data)).encode() + b"\0" + data
    assert hashlib.sha1(git_blob).hexdigest() == row["git_blob_sha1"], rel
    if not reused:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {
        "url": base + rel.as_posix(),
        "path": str(target),
        "bytes": len(data),
        "git_blob_sha1": row["git_blob_sha1"],
        "sha256": hashlib.sha256(data).hexdigest(),
        "verified_at": datetime.now(UTC).isoformat(),
        "reused_local_download": reused,
    }


with ThreadPoolExecutor(max_workers=4) as pool:
    receipts = list(pool.map(fetch, protocol["source_files"]))
manifest = args.out.parent / "packet-sources.json"
manifest.write_text(json.dumps(receipts, indent=2) + "\n")
print(json.dumps({"files": len(receipts), "bytes": sum(r["bytes"] for r in receipts)}))
