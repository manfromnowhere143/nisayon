"""JSON-lines acquisition worker. Physical parameters and reference truth are absent."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finite import choose  # noqa: E402

if len(sys.argv) == 3 and sys.argv[1] == "--isolation-probe":
    try:
        Path(sys.argv[2]).read_bytes()
    except PermissionError:
        print("protected_input_refused")
        raise SystemExit(0) from None
    raise SystemExit("protected input was readable")

for line in sys.stdin:
    if len(line) > 131072:
        raise ValueError("oversized selector input")
    request = json.loads(line)
    if set(request) != {"probes", "observations", "method", "remaining", "seed"}:
        raise ValueError("unexpected selector field")
    if any(set(p) != {"id", "weight", "cost"} for p in request["probes"]):
        raise ValueError("unexpected probe field")
    print(json.dumps(choose(**request)), flush=True)
