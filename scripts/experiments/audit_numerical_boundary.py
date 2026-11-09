"""Verify retained pilot bytes and replay every decision without executing owner code."""

import argparse
import hashlib
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from nisayon.engine.io import decode_json, file_digest, write_json
from nisayon.qualification import inspect_run

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--packet", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
packet = args.packet.resolve()
spec = decode_json((packet / "spec.json").read_bytes())
archives = decode_json((packet / "archives.json").read_bytes())["archives"]
checked, decisions = [], []
with tempfile.TemporaryDirectory(prefix="nisayon-numeric-audit-") as temporary:
    for archive in archives:
        path = packet / archive["path"]
        if file_digest(path) != archive["sha256"]:
            raise ValueError("Archive identity changed")
        root = Path(temporary) / path.stem
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or set(names) != set(archive["files"]):
                raise ValueError("Archive membership changed")
            if len(names) > 4096 or sum(i.file_size for i in bundle.infolist()) > 64 * 1024**2:
                raise ValueError("Unexpected pilot size")
            for name in names:
                relative = PurePosixPath(name)
                if relative.is_absolute() or ".." in relative.parts or str(relative) != name:
                    raise ValueError("Invalid retained path")
                raw = bundle.read(name)
                if hashlib.sha256(raw).hexdigest() != archive["files"][name]:
                    raise ValueError("Retained member changed")
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        if file_digest(root / "result.json") != file_digest(packet / f"{path.stem}-result.json"):
            raise ValueError("Summary differs from retained evidence")
        intent = decode_json((root / "intent.json").read_bytes())
        if intent["spec_sha256"] != file_digest(packet / "spec.json"):
            raise ValueError("Pilot changed the frozen specification")
        if path.stem in {"before", "after"}:
            for row in spec["cases"]:
                assessment = inspect_run(root / row["id"]).record()
                if assessment["software_decision"] != row["expected"]:
                    raise ValueError(f"Current scorer disagrees on {path.stem}/{row['id']}")
                if assessment["deployment_decision"] != "unresolved":
                    raise ValueError("Software evidence cannot grant deployment acceptance")
                decisions.append(
                    {
                        "source": path.stem,
                        "case": row["id"],
                        "decision": assessment["software_decision"],
                    }
                )
        checked.append({"archive": archive["path"], "files": len(names)})
result = {
    "status": "supported",
    "scope": "Archive integrity and current-scoring replay; not independent truth or original-scorer reproduction",
    "archives": checked,
    "reassessed_decisions": decisions,
    "owner_code_executed": False,
}
write_json(args.out, result)
print({"archives": len(checked), "reassessed_decisions": len(decisions), "status": "supported"})
