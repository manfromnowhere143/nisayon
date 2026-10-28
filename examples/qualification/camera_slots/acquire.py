"""Reacquire the exact retained public CPU source subset; no model weights."""

import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

if not __debug__:
    raise RuntimeError("Camera native qualification requires Python without optimization")

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
ART = ROOT / "artifacts/camera-slot-qualification-2026-10-28"


def main():
    for record in json.loads((PACKET / "source-downloads.json").read_text()):
        destination = ART / "sources" / record["name"]
        destination.mkdir(parents=True, exist_ok=False)
        with urllib.request.urlopen(record["url"], timeout=45) as response:
            data = response.read(134217729)
        assert len(data) <= 134217728, "Archive exceeds the frozen acquisition bound"
        assert hashlib.sha256(data).hexdigest() == record["archive_sha256"]
        (ART / f"{record['name']}.tar.gz").write_bytes(data)
        found = set()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                parts = member.name.split("/", 1)
                if len(parts) != 2 or parts[1] not in record["files"]:
                    continue
                name = parts[1]
                assert member.isfile() and name not in found
                source = archive.extractfile(member)
                assert source is not None
                content = source.read()
                assert hashlib.sha256(content).hexdigest() == record["files"][name]
                target = destination / name
                assert target.resolve().is_relative_to(destination.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                found.add(name)
        assert found == set(record["files"])
        print(json.dumps({"source": record["name"], "verified_files": len(found)}), flush=True)


if __name__ == "__main__":
    main()
