"""Verify a pinned research archive without executing archived source."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--sha256", required=True, help="Expected digest from a trusted separate receipt"
    )
    parser.add_argument(
        "--extract", type=Path, help="Optional NEW directory; verification precedes writes"
    )
    args = parser.parse_args()
    if args.archive.stat().st_size > 128 * 1024**2:
        raise ValueError("archive too large")
    raw = args.archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        raise ValueError("archive does not match supplied identity")
    with zipfile.ZipFile(args.archive) as archive:
        infos, names = archive.infolist(), archive.namelist()
        if (
            len(names) > 4096
            or len(names) != len(set(names))
            or sum(i.file_size for i in infos) > 128 * 1024**2
        ):
            raise ValueError("unexpected archive membership or expansion")
        for info in infos:
            name = info.filename
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or str(path) != name
                or info.is_dir()
                or info.file_size > 32 * 1024**2
            ):
                raise ValueError("unsafe member")
            if any(str(parent) in names for parent in path.parents if str(parent) != "."):
                raise ValueError("member/file prefix collision")
        manifest = json.loads(archive.read("manifest.json"))
        if set(names) != {"manifest.json", *manifest["files"]}:
            raise ValueError("manifest membership differs")
        contents = {}
        for name, entry in manifest["files"].items():
            payload = archive.read(name)
            if (
                len(payload) != entry["bytes"]
                or hashlib.sha256(payload).hexdigest() != entry["sha256"]
            ):
                raise ValueError(f"member differs: {name}")
            contents[name] = payload
        if args.extract:
            root = args.extract.absolute()
            if root.resolve() != root:
                raise ValueError("extraction path must have no symlink aliases")
            root.mkdir(parents=True, exist_ok=False)
            for name, payload in contents.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(payload)
            (root / "manifest.json").write_bytes(archive.read("manifest.json"))
    print(
        json.dumps(
            {
                "integrity": "verified",
                "members": len(contents),
                "archive_sha256": args.sha256,
                "extracted": str(args.extract) if args.extract else None,
                "executed_archived_code": False,
                "authenticity": "not_established",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
