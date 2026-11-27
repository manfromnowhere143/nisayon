"""Reseal invalid copies to distinguish integrity from scientific validity.

Original episodes are read only. Copies live in a temporary directory and are
never represented as executed physical trajectories or accepted evidence.
"""

import argparse
import copy
import json
import shutil
import tempfile
from pathlib import Path

from nisayon.engine.io import decode_json

from .catalog import model_catalog
from .evidence import sha256, write_json
from .inspection import project


def run(episode: Path, examples: Path) -> dict:
    anchor = sha256(episode / "manifest.json")
    initial = {str(p.relative_to(episode)): sha256(p) for p in episode.rglob("*") if p.is_file()}
    original_manifest = decode_json((episode / "manifest.json").read_bytes())
    raw = (episode / "policy.jsonl").read_bytes()
    rows = [decode_json(line) for line in raw.splitlines()]
    view = project(episode, anchor)
    catalog = model_catalog(episode, anchor)
    import gzip

    retained = decode_json(
        gzip.decompress((examples / f"{episode.name}.inspection.json.gz").read_bytes())
    )
    if view != retained or catalog != decode_json(
        (examples / f"{episode.name}.model.json").read_bytes()
    ):
        raise AssertionError("hardened reader changed the retained scientific view")
    findings = []
    with tempfile.TemporaryDirectory(prefix="ricci-invalid-copy-") as temp:
        target = Path(temp) / "episode"
        shutil.copytree(episode, target)
        for name in (
            "missing_row",
            "future_observation",
            "wrong_delivery",
            "probability_claim",
            "bool_torque",
            "duplicate_json_key",
            "unsupported_producer",
        ):
            changed = copy.deepcopy(rows)
            source = target / "source/model.py"
            source.write_bytes((episode / "source/model.py").read_bytes())
            if name == "missing_row":
                changed.pop(20)
            elif name == "future_observation":
                changed[20]["observation"]["delivered_s"] = changed[20]["t"] + 1
            elif name == "wrong_delivery":
                changed[20]["applied_command"]["torque_nm"][0] += 1
            elif name == "probability_claim":
                changed[20]["belief"]["calibrated_probabilities"] = True
            elif name == "bool_torque":
                changed[20]["command"]["torque_nm"][0] = True
            elif name == "unsupported_producer":
                source.write_bytes(source.read_bytes() + b"\n# changed producer\n")
            payload = (
                b"\n".join(json.dumps(row, allow_nan=False).encode() for row in changed) + b"\n"
            )
            if name == "duplicate_json_key":
                payload = b'{"tick":99,' + payload[1:]
            (target / "policy.jsonl").write_bytes(payload)
            manifest = copy.deepcopy(original_manifest)
            for entry in manifest["files"]:
                if entry["path"] in ("policy.jsonl", "source/model.py"):
                    path = target / entry["path"]
                    entry.update(bytes=path.stat().st_size, sha256=sha256(path))
            write_json(target / "manifest.json", manifest)
            try:
                project(target, sha256(target / "manifest.json"))
            except ValueError as error:
                findings.append({"control": name, "refused": True, "reason": str(error)})
            else:
                raise AssertionError(f"invalid resealed record accepted: {name}")
    after = {str(p.relative_to(episode)): sha256(p) for p in episode.rglob("*") if p.is_file()}
    if initial != after:
        raise AssertionError("original evidence changed")
    return {
        "schema": "ricci.rb02.inspection-controls.v1",
        "source_manifest_sha256": anchor,
        "source_unchanged": True,
        "retained_view_and_catalog_unchanged": True,
        "controls": findings,
        "scope": "Invalid copies were resealed, so refusal tests semantic checks beyond file hashes. This is not execution authenticity or hostile-code containment.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    write_json(args.out, run(args.episode, args.examples))


if __name__ == "__main__":
    main()
