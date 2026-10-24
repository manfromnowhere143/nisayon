"""Export exact upstream trees and compose two disjoint author patches."""

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKET = Path(__file__).resolve().parent
SOURCE = ROOT / "artifacts/openpi/source"
DEST = ROOT / "artifacts/openpi/arms"
REVISIONS = {
    "base": "215abfb217dbac7d5f1273282331b9b1866c0479",
    "pr1016": "3b3b21d8fc971eca008a0b6f07c86605fb57133f",
    "pr1050": "525cdf07b33a74a99c037ba565d5d6cb4aa93022",
}


def git(*args):
    return subprocess.check_output(["git", "-C", str(SOURCE), *args])


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    for name, revision in REVISIONS.items():
        directory = DEST / name
        directory.mkdir()
        data = git("archive", revision, "src", "LICENSE", "pyproject.toml")
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(directory, filter="data")

    combined = DEST / "combined"
    shutil.copytree(DEST / "base", combined)
    touched = set()
    for name in ("pr1016", "pr1050"):
        names = (
            git("diff", "--name-only", REVISIONS["base"], REVISIONS[name], "--", "src")
            .decode()
            .splitlines()
        )
        assert not touched.intersection(names), "Upstream patches overlap; inspect before composing"
        touched.update(names)
        for filename in names:
            target = combined / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git("show", f"{REVISIONS[name]}:{filename}"))
        (PACKET / f"{name}.patch").write_bytes(
            git(
                "diff", "--binary", "--no-ext-diff", REVISIONS["base"], REVISIONS[name], "--", "src"
            )
        )

    bad = DEST / "bad_reshape"
    shutil.copytree(combined, bad)
    path = bad / "src/openpi/models_pytorch/preprocessing_pytorch.py"
    original = path.read_text()
    before = "        image = image.permute(0, 3, 1, 2)  # [B, H, W, C] -> [B, C, H, W]"
    after = "        image = image.reshape(image.shape[0], image.shape[3], image.shape[1], image.shape[2])"
    assert original.count(before) == 1
    path.write_text(original.replace(before, after))

    manifests = {}
    for directory in sorted(DEST.iterdir()):
        manifests[directory.name] = {
            str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        }
    result = {
        "revisions": REVISIONS,
        "composed_paths": sorted(touched),
        "source_files_sha256": manifests,
        "mutant": {
            "path": "src/openpi/models_pytorch/preprocessing_pytorch.py",
            "before": before,
            "after": after,
        },
    }
    (PACKET / "source-identities.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "arms": list(manifests),
                "files_per_arm": {k: len(v) for k, v in manifests.items()},
                "composed_paths": sorted(touched),
            }
        )
    )


if __name__ == "__main__":
    main()
