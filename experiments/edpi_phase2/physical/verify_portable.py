"""Exercise actual relocation, pinned import and two forms of bundle corruption."""

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from nisayon.qualification.check_bundle import import_check_bundle, inspect_check_bundle


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    original = args.bundle.read_bytes()
    identity = hashlib.sha256(original).hexdigest()
    controls = []
    with tempfile.TemporaryDirectory(prefix="nisayon-edpi-portable-") as temp:
        root = Path(temp)
        relocated = root / "renamed.nisayon.zip"
        shutil.copyfile(args.bundle, relocated)
        inspected = inspect_check_bundle(relocated)
        if inspected["review_status"] != "verified" or inspected["integrity"] != "verified":
            raise ValueError("relocated evidence did not verify")
        controls.append({"control": "relocation", "passed": True})
        imported = import_check_bundle(
            relocated, expected_sha256=identity, output=root / "imported"
        )
        controls.append({"control": "pinned_import", "passed": True, "result": imported})
        try:
            import_check_bundle(relocated, expected_sha256="0" * 64, output=root / "wrong-pin")
        except ValueError as error:
            controls.append({"control": "wrong_pin", "passed": True, "reason": str(error)})
        else:
            raise ValueError("incorrect pin accepted")
        with zipfile.ZipFile(relocated) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        changed = "evidence/execution/inputs/data"
        if changed not in files:
            raise ValueError("expected captured input absent")
        for rehash in (False, True):
            mutated = files | {changed: b"{}\n"}
            if rehash:
                index = json.loads(mutated["bundle.json"])
                index["files"][changed] = {
                    "sha256": hashlib.sha256(mutated[changed]).hexdigest(),
                    "bytes": len(mutated[changed]),
                }
                mutated["bundle.json"] = json.dumps(index, sort_keys=True).encode()
            path = root / f"tampered-{rehash}.zip"
            with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, raw in mutated.items():
                    archive.writestr(name, raw)
            try:
                inspect_check_bundle(path)
            except ValueError as error:
                controls.append(
                    {
                        "control": f"altered_input_rehash_{rehash}",
                        "passed": True,
                        "reason": str(error),
                    }
                )
            else:
                raise ValueError("corrupted review accepted")
    if args.bundle.read_bytes() != original:
        raise ValueError("original archive changed")
    with args.out.open("x") as stream:
        json.dump(
            {
                "schema": "nisayon.edpi.transport-controls.v1",
                "bundle_sha256": identity,
                "controls": controls,
                "original_preserved": True,
                "scope": "Portable artifact integrity and pinned import; no execution authenticity or independent physical approval.",
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(json.dumps({"controls_passed": len(controls), "original_preserved": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
