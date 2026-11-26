"""Supplement: reexecute the frozen matrix using the proposed actual native patch."""
import hashlib
import importlib.util
import json
from pathlib import Path

import matrix_v2 as study  # Uses its frozen arguments; does not execute main.

path = Path("artifacts/edpi-serving-intake-2026-11-26/modeling_pi05_candidate.py")
record = json.loads((study.HERE / "records/patch-freeze.json").read_text())
if hashlib.sha256(path.read_bytes()).hexdigest() != record["candidate_sha256"]:
    raise ValueError("Patched source changed")
spec = importlib.util.spec_from_file_location(
    "lerobot.policies.pi05.modeling_pi05_nisayon_intake", path
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
study.Narrow = module.PI05Policy
study.main()
