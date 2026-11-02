import json
import os
import shutil
from pathlib import Path

import pytest
from audit_mcp import audit

HERE = Path(os.environ.get("NISAYON_EVIDENCE_ROOT", Path(__file__).resolve().parent))


def test_readback_matches_in_both_processes():
    assert audit(HERE / "mcp-first") == audit(HERE / "mcp-repeat")


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "changed_effect", "missing_requests", "false_zero"]
)
def test_altered_or_missing_evidence_rejected(tmp_path, mutation):
    root = tmp_path / "copied"
    shutil.copytree(HERE / "mcp-first", root)
    path = root / "results.json"
    result = json.loads(path.read_text())
    if mutation == "missing":
        result["rows"].pop()
    elif mutation == "duplicate":
        result["rows"][-1] = result["rows"][0]
    elif mutation == "changed_effect":
        (root / "True-after-0/effects.jsonl").write_text("")
    elif mutation == "missing_requests":
        (root / "True-after-0/requests.jsonl").unlink()
    elif mutation == "false_zero":
        result["rows"][4]["effects"] = 0
    path.write_text(json.dumps(result))
    with pytest.raises((ValueError, FileNotFoundError)):
        audit(root)
