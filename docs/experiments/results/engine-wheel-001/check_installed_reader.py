"""Local package portability check; imports only the installed private test wheel."""

import importlib.metadata
import importlib.util
import json
import os
import sys
from pathlib import Path

from nisayon.engine import robolab_record
from nisayon.engine.io import file_digest

root = Path(sys.argv[1]).resolve(strict=True)
environment = Path(sys.prefix).resolve(strict=True)
module = Path(robolab_record.__file__).resolve(strict=True)
assert module.is_relative_to(environment), module
absent = {name: importlib.util.find_spec(name) is None for name in ("torch", "robosuite", "mujoco")}
assert all(absent.values()), absent
outside = environment.parent / "nisayon-wheel-reader-cwd-20260919"
outside.mkdir(exist_ok=False)
os.chdir(outside)
output = root / "artifacts/robolab-wheel-import-001"
sys.argv = [
    "nisayon.engine.robolab_record",
    "--source",
    str(root / "artifacts/robolab-reproduced-source-001"),
    "--output",
    str(output),
]
robolab_record.main()
actual = output / "external-record.json"
expected = root / "artifacts/robolab-import-006/external-record.json"
assert actual.read_bytes() == expected.read_bytes()
result = {
    "schema": "nisayon.installed-reader-check.v1",
    "scope": "Private local wheel check, not a release or cross-platform qualification",
    "source_commit": "28e29a8c6e9d38a30a21c36893da9382e04b88ee",
    "wheel_sha256": file_digest(
        root / "artifacts/engine-wheel-001/nisayon_workspace-0.1.0-py3-none-any.whl"
    ),
    "requirements_sha256": file_digest(root / "artifacts/engine-wheel-001/requirements.txt"),
    "python": sys.version,
    "module": str(module),
    "module_sha256": file_digest(module),
    "working_directory": str(Path.cwd()),
    "isolated_python": bool(sys.flags.isolated),
    "simulator_and_torch_absent": absent,
    "import_equals_checkout_bytes": True,
    "full_import_sha256": file_digest(actual),
    "installed_distributions": {
        item.metadata["Name"]: item.version for item in importlib.metadata.distributions()
    },
}
(root / "artifacts/engine-wheel-001/check.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
