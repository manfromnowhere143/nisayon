"""Use existing Nisayon evidence transport for a scoped retained-data review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_native import audit, read_payload

from nisayon.engine.io import file_digest, write_json
from nisayon.qualification import DependencyModel, execute_checks, inspect_checks
from nisayon.qualification.check_bundle import export_checks, inspect_check_bundle

HERE = Path(__file__).resolve().parent
SCOPE = "Retained native mechanism observations; no owner, task confirmation or deployment acceptance"


def review(ctx):
    protocol = ctx.input("protocol")
    if protocol != {"scope": SCOPE, "confirmation": "not_run", "owner_enrolled": False}:
        raise ValueError("Review scope changed")
    return audit(ctx.input("data"))


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    write_json(root / "raw.json", read_payload(args.records))
    write_json(root / "scope.json", {"scope": SCOPE, "confirmation": "not_run", "owner_enrolled": False})
    value = {"schema": "nisayon.qualification.dependencies.v1", "id": "edpi-phase2-mechanism-readback",
             "scope": SCOPE, "inputs": {
                 "data": {"kind": "data", "description": "Raw original failure and native mechanism records"},
                 "protocol": {"kind": "protocol", "description": "Scoped retained-data review only"},
                 "procedure": {"kind": "code", "description": "Exact producer and review source"}},
             "checks": {"review": {"kind": "review", "depends_on": ["data", "protocol", "procedure"],
                                      "refresh": "always"}},
             "decisions": {"mechanism_record": {"depends_on": ["review"], "description": SCOPE}},
             "review": None}
    initial = DependencyModel.from_dict(value)
    reviewer = "development-context source and arithmetic inspection"
    write_json(root / "model-review.json", {
        "schema": "nisayon.qualification.dependency_review.v1",
        "definition_sha256": initial.definition_sha256, "reviewer": reviewer,
        "coverage": "reviewed_for_declared_scope",
        "statement": "Declared bytes and arithmetic only; no independent human review, physical authenticity or complete dependency proof"})
    value["review"] = {"definition_sha256": initial.definition_sha256, "reviewer": reviewer,
                       "artifact": {"path": "model-review.json", "sha256": file_digest(root / "model-review.json")}}
    model = DependencyModel.from_dict(value)
    run = execute_checks(model, inputs={"data": root / "raw.json", "protocol": root / "scope.json"},
                         handlers={"review": review}, implementation_files=[HERE / n for n in
                         ("portable_review.py", "audit_native.py", "probe_drag.py", "probe_drag_v2.py",
                          "PROTOCOL.md", "AMENDMENT-01.md", "records/native-freeze.json",
                          "records/native-freeze-v2.json")],
                         evidence_root=root, output=root / "execution")
    inspected = inspect_checks(evidence_root=root, output=root / "execution")
    # The production authority requires full qualification obligations even for a
    # narrow decision label. Preserve and export its refusal; invent no confirmation.
    expected_errors = {
        "mechanism_record:fresh_confirmation_not_declared",
        "mechanism_record:uncovered_dependency_kind:population",
        "mechanism_record:uncovered_dependency_kind:runtime",
        "mechanism_record:uncovered_dependency_kind:scoring",
    }
    if run["status"] != "unresolved" or set(run["errors"]) != expected_errors or run["attempts"]:
        raise ValueError("Production refusal changed")
    artifact = audit(read_payload(args.records))
    write_json(root / "separate-arithmetic-review.json", artifact)
    exported = export_checks(evidence_root=root, execution=root / "execution", output=args.bundle)
    portable = inspect_check_bundle(args.bundle)
    write_json(root / "summary.json", {"execution": run["status"], "review": artifact,
                                      "export": exported, "portable_review": portable,
                                      "bundle_sha256": hashlib.sha256(args.bundle.read_bytes()).hexdigest()})
    print(json.dumps({"execution": run["status"], "portable": portable["review_status"],
                      "bundle_sha256": file_digest(args.bundle)}))


if __name__ == "__main__":
    main()
