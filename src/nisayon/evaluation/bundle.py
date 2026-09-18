"""A bundle directory holds one case, its runs, artifacts and confirmation.

Layout::

    bundle/
      case.json               nisayon.case.v1
      runs/<run-id>.json      nisayon.run.v1, one per run
      artifacts/...           trace files referenced by runs, relative to the artifact root
      confirmation.json       nisayon.confirmation.v1 (optional until a candidate is frozen)
      prior/*.json            earlier confirmations of the same case (optional)

The artifact root defaults to the bundle directory and must be explicit when it differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .schema import Malformed, load_json


@dataclass
class Bundle:
    root: Path
    artifact_root: Path
    case: object | None = None
    case_error: Malformed | None = None
    runs: dict[str, dict] = field(default_factory=dict)
    unparsed: list[dict] = field(default_factory=list)
    confirmation: object | None = None
    confirmation_error: Malformed | None = None
    prior: list[object] = field(default_factory=list)


def load_bundle(root: Path, artifact_root: Path | None = None) -> Bundle:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"bundle directory not found: {root}")
    bundle = Bundle(root=root, artifact_root=Path(artifact_root or root))
    case_path = root / "case.json"
    if case_path.is_file():
        try:
            bundle.case = load_json(case_path)
        except Malformed as error:
            bundle.case_error = error
    else:
        bundle.case_error = Malformed("case.json", "missing")
    for path in sorted((root / "runs").glob("*.json")):
        try:
            data = load_json(path)
        except Malformed as error:
            bundle.unparsed.append({"file": str(path.relative_to(root)), "error": str(error)})
            continue
        run_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(run_id, str) or not run_id.strip():
            bundle.unparsed.append(
                {"file": str(path.relative_to(root)), "error": "run.id: missing"}
            )
        elif run_id in bundle.runs:
            bundle.unparsed.append(
                {"file": str(path.relative_to(root)), "error": f"duplicate run id {run_id!r}"}
            )
        else:
            bundle.runs[run_id] = data
    confirmation_path = root / "confirmation.json"
    if confirmation_path.is_file():
        try:
            bundle.confirmation = load_json(confirmation_path)
        except Malformed as error:
            bundle.confirmation_error = error
    for path in sorted((root / "prior").glob("*.json")):
        try:
            bundle.prior.append(load_json(path))
        except Malformed as error:
            bundle.unparsed.append({"file": str(path.relative_to(root)), "error": str(error)})
    return bundle
