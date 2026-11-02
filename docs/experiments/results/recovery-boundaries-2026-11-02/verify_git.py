"""Verify the published Git objects, including manifest coverage, without caches."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def verify(revision="HEAD"):
    folder = Path(__file__).resolve().parent
    repo = Path(
        subprocess.check_output(
            ["git", "-C", str(folder), "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    prefix = folder.relative_to(repo).as_posix() + "/"
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--verify", revision + "^{commit}"], text=True
    ).strip()

    def read(path):
        return subprocess.check_output(
            ["git", "-C", str(repo), "show", commit + ":" + prefix + path],
            stderr=subprocess.DEVNULL,
        )

    manifest = json.loads(read("manifest.json"))
    tracked = subprocess.check_output(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", commit, "--", prefix], text=True
    ).splitlines()
    members = {path.removeprefix(prefix) for path in tracked} - {"manifest.json"}
    failures = []
    if members != manifest["files"].keys():
        failures.append(
            {
                "inventory": {
                    "unpublished": sorted(manifest["files"].keys() - members),
                    "unbound": sorted(members - manifest["files"].keys()),
                }
            }
        )
    for name in sorted(members & manifest["files"].keys()):
        if hashlib.sha256(read(name)).hexdigest() != manifest["files"][name]:
            failures.append({"digest_mismatch": name})
    return {
        "commit": commit,
        "files_checked": len(members),
        "valid": not failures,
        "failures": failures,
        "limit": "Git object integrity and coverage, not experimental authenticity",
    }


if __name__ == "__main__":
    result = verify(sys.argv[1] if len(sys.argv) > 1 else "HEAD")
    print(json.dumps(result, indent=2))
    raise SystemExit(not result["valid"])
