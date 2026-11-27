"""Bounded replay and scientific-view verification on preregistered cases."""

import argparse
import copy
import gzip
import json
import time
from pathlib import Path

from nisayon.engine.io import canonical_bytes

from .catalog import model_catalog
from .evidence import sha256, write_json
from .inspection import project, verify_projection

REPLAYS = (
    "nominal-00",
    "compound-none",
    "compound-candidate",
    "compound-shared-000ms",
    "compound-shared-660ms",
    "contact-m150-tc10-i40",
)
EXAMPLES = ("compound-candidate", "compound-shared-000ms")


def verify(root: Path, output: Path, examples: Path) -> None:
    from ricci_brain.replay import replay

    if output.exists() or examples.exists():
        raise FileExistsError("verification destinations must be new")
    examples.mkdir(parents=True)
    index = {r["id"]: r for r in json.loads((root / "index.json").read_text())}
    records = []
    for name in REPLAYS:
        started = time.perf_counter()
        result = replay(root / name)
        records.append(
            {
                "episode": name,
                "manifest_sha256": index[name]["manifest_sha256"],
                "replay": result,
                "wall_s": time.perf_counter() - started,
            }
        )
        write_json(output.with_suffix(".partial.json"), {"replays": records})
        print(json.dumps({"episode": name, "replayed": True}), flush=True)
    inspections = []
    for name in EXAMPLES:
        episode = root / name
        anchor = index[name]["manifest_sha256"]
        before = {str(p.relative_to(episode)): sha256(p) for p in episode.rglob("*") if p.is_file()}
        timings = []
        for _ in range(3):
            started = time.perf_counter()
            view = project(episode, anchor)
            timings.append(time.perf_counter() - started)
        verify_projection(view, episode, anchor)
        altered = copy.deepcopy(view)
        altered["samples"][0]["applied_command"]["torque_nm"][0] += 1.0
        try:
            verify_projection(altered, episode, anchor)
        except ValueError:
            altered_refused = True
        else:
            raise AssertionError("altered inspection accepted")
        catalog = model_catalog(episode, anchor)
        payload = canonical_bytes(view)
        path = examples / (name + ".inspection.json.gz")
        path.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
        catalog_path = examples / (name + ".model.json")
        write_json(catalog_path, catalog)
        after = {str(p.relative_to(episode)): sha256(p) for p in episode.rglob("*") if p.is_file()}
        if before != after:
            raise AssertionError("inspection altered source evidence")
        inspections.append(
            {
                "episode": name,
                "manifest_sha256": anchor,
                "rows": len(view["samples"]),
                "projection_wall_s": timings,
                "uncompressed_bytes": len(payload),
                "compressed_bytes": path.stat().st_size,
                "projection_sha256": sha256(path),
                "catalog_sha256": sha256(catalog_path),
                "source_unchanged": True,
                "altered_projection_refused": altered_refused,
                "native_entities": {
                    k: len(catalog[k])
                    for k in ("bodies", "joints", "actuators", "sensors", "geometries")
                },
            }
        )
    write_json(
        output,
        {
            "schema": "ricci.rb02.verification.v1",
            "replays": records,
            "inspections": inspections,
            "limits": [
                "Recorded-command replay is not a changed-action counterfactual.",
                "Offline projection adds no control-loop calls. Existing Brain 01 recording overhead is not isolated or hardware-qualified.",
                "No renderer or live telemetry transport was executed.",
                "Raw source audit and native computation checks do not establish execution authenticity or physical truth.",
            ],
        },
    )
    write_json(
        examples / "index.json",
        {
            "schema": "ricci.inspection-examples.v1",
            "contract": "ricci.scientific-inspection.v1",
            "examples": inspections,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    args = parser.parse_args()
    verify(args.root, args.out, args.examples)


if __name__ == "__main__":
    main()
