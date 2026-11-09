"""Qualify additive model metadata against an already qualified geometry object."""

import json
import re
from pathlib import Path

from project_engine import digest, encoded

ROOT = Path(__file__).resolve().parents[2]
ADDITIVE = {"nv", "nu", "joints", "actuators"}


def geometry_record(value):
    return {k: v for k, v in value.items() if k not in ADDITIVE}


def main():
    pin_path = ROOT / "apps/instrument/src/scene/visualAssetPin.ts"
    pin = json.loads(re.search(r"VISUAL_ASSET = (\{.*?\}) as const", pin_path.read_text(), re.S)[1])
    raw = (ROOT / pin["path"].lstrip("/")).read_bytes()
    if digest(raw) != pin["sha256"] or len(raw) != pin["byte_length"]:
        raise ValueError("Unverified visual package")
    asset = json.loads(raw)
    library = ROOT / "fixtures/ui/recorded"
    aliases = {(a["source_id"], a["sha256"]) for a in asset.get("model_binding_aliases", [])}
    for case in json.loads((library / "library.json").read_bytes())["cases"]:
        root = library / case["directory"]
        manifest = json.loads((root / case["manifest"]["path"]).read_bytes())
        record = json.loads((root / manifest["cases"][0]["object"]["path"]).read_bytes())
        for run in record["runs"]:
            ref = run["model"]
            raw = (root / ref["path"]).read_bytes()
            if digest(raw) != ref["sha256"]:
                raise ValueError("Model digest mismatch")
            model = json.loads(raw)
            original_sha = asset["model_bindings"][model["source_id"]]
            old = root / "objects" / (original_sha + ".json")
            old_raw = old.read_bytes()
            if digest(old_raw) != original_sha or geometry_record(
                json.loads(old_raw)
            ) != geometry_record(model):
                raise ValueError("Geometry changed: full visual qualification is required")
            if ref["sha256"] != original_sha:
                aliases.add((model["source_id"], ref["sha256"]))
    asset["model_binding_aliases"] = [{"source_id": s, "sha256": h} for s, h in sorted(aliases)]
    data = encoded(asset) + b"\n"
    sha = digest(data)
    path = f"/fixtures/ui/visual/objects/{sha}.json"
    (ROOT / path.lstrip("/")).write_bytes(data)
    ref = {"path": path, "sha256": sha, "byte_length": len(data)}
    pin_path.write_text(
        "// Qualified source geometry with additive model bindings.\nexport const VISUAL_ASSET = "
        + json.dumps(ref, indent=2)
        + " as const;\n"
    )
    print(
        json.dumps(
            {"package": ref, "qualified_additive_models": len(aliases), "geometry_changed": False}
        )
    )


if __name__ == "__main__":
    main()
