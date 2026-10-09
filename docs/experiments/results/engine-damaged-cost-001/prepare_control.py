"""Corrupt one cost record in an isolated copy of exposed development evidence."""

import json
import shutil
from pathlib import Path

from nisayon.engine.io import file_digest

root = Path.cwd()
source = root / "artifacts/retained-declarations-002"
output = root / "artifacts/engine-damaged-cost-001/packet-copy"
before = {str(p.relative_to(source)): file_digest(p) for p in source.rglob("*") if p.is_file()}
shutil.copytree(source, output)
packet = json.loads((output / "packet.json").read_text())
receipt = output / packet["rows"][0]["declaration"]["path"]
cost = sorted((receipt.parent / "attempts").glob("*.result.json"))[0]
original_cost = file_digest(cost)
cost.write_text("{ deliberately damaged cost record in a labelled copy\n")
after = {str(p.relative_to(source)): file_digest(p) for p in source.rglob("*") if p.is_file()}
assert before == after
record = {
    "schema": "nisayon.damaged-cost-control.v1",
    "scope": "Labelled corruption of a copied cost record; no scientific experiment",
    "source_root": str(source),
    "source_packet_sha256": file_digest(source / "packet.json"),
    "source_files_unchanged": len(before),
    "copied_cost_path": str(cost.relative_to(output)),
    "original_cost_sha256": original_cost,
    "damaged_cost_sha256": file_digest(cost),
    "original_declaration_sha256": file_digest(receipt),
    "new_simulator_executions": 0,
    "new_model_calls": 0,
}
(output.parent / "control.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
