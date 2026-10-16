# Reproduce the recorded analysis

Run from the Nisayon repository root, in a fresh checkout or with the named
artifact directory absent. Do not overwrite the original retained run. These
commands download public evidence and execute CPU analysis, with no simulator
or model-weight installation.

The acquisition script verifies every selected file against the frozen source
tree before writing it:

```sh
python3 -B docs/experiments/results/decision-endpoint-001/acquire.py \
  --out artifacts/decision-evidence-2026-10-12/source
```

Fetch the small pinned predicate and checkpoint-metadata files and restore their
retained identity manifests. The source URLs and expected hashes are committed;
the manifest timestamps describe our original retrieval, not this rerun:

```python
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

evidence = Path("docs/experiments/results/decision-endpoint-001")
artifacts = Path("artifacts/decision-evidence-2026-10-12")
for name in [
    "native-predicate-sources.json",
    "native-predicate-config.json",
    "checkpoint-metadata-sources.json",
]:
    manifest = json.loads((evidence / name).read_text())
    for row in manifest if isinstance(manifest, list) else [manifest]:
        with urllib.request.urlopen(row["url"], timeout=45) as response:
            data = response.read()
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        path = Path(row["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    shutil.copyfile(evidence / name, artifacts / name)
packet = artifacts / "source/reviews/2026-09-24_ras_strengthening/confirmatory"
shutil.copytree(packet, artifacts / "upstream-replay/confirmatory")
```

Mutable HTTP metadata formatting may change even at a pinned revision. A hash
failure must be investigated, with the previous receipt preserved. Do not loosen
the check or silently replace the manifest.

Install a **separate Python 3.11.16** environment, then the two locked packages.
The current protocol deliberately pins the CPU reference environment rather than
the original Windows/GPU simulation stack:

```sh
uv venv --python 3.11.16 artifacts/decision-evidence-2026-10-12/venv
uv pip sync docs/experiments/results/decision-endpoint-001/requirements.lock \
  --python artifacts/decision-evidence-2026-10-12/venv/bin/python \
  --require-hashes --link-mode copy
```

Our local uv catalog did not contain that Python release. On macOS arm64 we used
the official standalone archive in [python-runtime.json](python-runtime.json),
checking its full SHA-256 before extraction. The exact executed
[bootstrap script](bootstrap_python.py.txt) expects
[release metadata](python-build-20260901.json) beside it under the artifact root.
Its receipt confirms that no global installation changed. On other platforms,
use the corresponding verified Python build; the archived runtime hash is only
for the original macOS arm64 execution.

Run the unchanged upstream analyzer **on its copy**, then Nisayon's fixed reader:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/nisayon run \
  --label decision-endpoint-upstream-rerun --timeout 120 -- \
  artifacts/decision-evidence-2026-10-12/venv/bin/python -B \
  artifacts/decision-evidence-2026-10-12/upstream-replay/confirmatory/analyze_portable.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/nisayon run \
  --label decision-endpoint-readback-rerun --timeout 120 -- \
  artifacts/decision-evidence-2026-10-12/venv/bin/python -B \
  scripts/experiments/verify_decision_endpoints.py \
  --artifacts artifacts/decision-evidence-2026-10-12 \
  --protocol docs/experiments/results/decision-endpoint-001/protocol.json \
  --out artifacts/decision-evidence-2026-10-12/readback-rerun
```

Require `status == "reproduced_recorded_analysis"`, all 20 primary contrasts,
40,960 state-derived labels with zero disagreements, and unchanged source files.
The interval tolerance is `1e-10`; exact counts are required. Preserve any
`invalid_readback` result and script before changing an implementation. A second
read of these exposed trajectories is still reproduction, not fresh confirmation.
