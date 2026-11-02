# Recovery must preserve the intended state

2 November 2026. Two exposed software probes distinguish successful execution
from the state that an engineer intended to preserve. They support bounded
contract clarifications, not an agent, robotics or cost-superiority claim.

* **Habitat:** the proposed bad-gradient patch passes its five supplied tests
  and keeps weights finite in nine warm-Adam fault conditions. Every one of those
  conditions changes parameters, optimizer state and the next valid update
  relative to skipping the failed step. Seventeen local controls qualify a
  conservative refusal, with distributed recovery explicitly unsupported.
* **OpenAI Agents SDK:** fourteen native MCP conditions reproduce across three
  fresh processes. An HTTP 503 substituted after a committed effect leaves one
  effect despite client failure. One configured retry produces two effects.
  Ordinary operation-key deduplication preserves one effect. The default retry
  budget is zero; no at-most-once guarantee or new algorithm is claimed.

[RESULTS.md](RESULTS.md) distinguishes the source-extracted Habitat boundary
from the real local MCP transport. [PROTOCOL.md](PROTOCOL.md) records the selected
questions and resource caps. [TARGET_REGISTER.md](TARGET_REGISTER.md) reconciles
OpenAI, NVIDIA, Cognition, Mobileye, SpaceX and adjacent targets with existing
fixes and access limits. [SOURCES.md](SOURCES.md) supplies exact primary sources.

Mobileye's Meteor work already covers hypothesis-driven failure discovery and
targeted data selection; Cognition already provides a reusable memory format.
Nisayon's useful candidate distinction is a cheaper independently correct change
decision using existing tools. That advantage remains unproved. These ordinary
probes must also be available to a competent comparison baseline.

[costs.json](costs.json) includes the recorded command subtotal and explicit
unknowns; it is not a full cost measurement. [evidence.zip](evidence.zip) retains
the original observations, separate request/effect journals, command receipts,
failed no-op assertion and successful controls. [manifest.json](manifest.json)
binds the included bytes; integrity does not authenticate experimental truth.
All cases are investigator-selected development cases, excluded from a future
untouched evaluation. No independent external scoring, owner enrollment, physical
execution, paid infrastructure or model API call is represented by these tests.

## Review retained observations

From the repository root, using a new output directory:

```sh
NISAYON_PACKET=docs/experiments/results/recovery-boundaries-2026-11-02
python3 -m zipfile -e "$NISAYON_PACKET/evidence.zip" artifacts/recovery-evidence
python3 "$NISAYON_PACKET/audit_mcp.py" artifacts/recovery-evidence/mcp-final
```

The audit independently recalculates journal counts and assignment coverage.
It does not perform fresh native execution. Six audit controls include five
altered/missing-record rejections. To run them, use a Python environment containing
pytest and set `NISAYON_EVIDENCE_ROOT=artifacts/recovery-evidence`.

## Fresh Habitat method experiment

```sh
uv venv --python 3.12 artifacts/recovery-torch
uv pip install --python artifacts/recovery-torch/bin/python -r "$NISAYON_PACKET/torch-requirements.lock"
cp "$NISAYON_PACKET/records/habitat-4.py.txt" artifacts/habitat-original-tests.py
artifacts/recovery-torch/bin/python -m pytest -v artifacts/habitat-original-tests.py
artifacts/recovery-torch/bin/python -m pytest -v "$NISAYON_PACKET/habitat_controls.py"
artifacts/recovery-torch/bin/python -m pytest -v "$NISAYON_PACKET/habitat_noop_red.py"
```

The final command **must fail**: it is the retained false-no-op assertion.
The original five tests and the seventeen scoped controls must pass. Source files
are hash checked before extracting two unmodified methods. This does not install
or qualify the full Habitat trainer. The upstream code/tests retain Meta's MIT
license in [HABITAT-LICENSE.txt](records/HABITAT-LICENSE.txt).

## Fresh native MCP experiment

```sh
git init artifacts/recovery-agents
git -C artifacts/recovery-agents remote add origin https://github.com/openai/openai-agents-python.git
git -C artifacts/recovery-agents fetch --depth 1 origin e355d69152d4f4730dfb03b63dbce53e8d9f5d8c
git -C artifacts/recovery-agents checkout --detach FETCH_HEAD
uv venv --python 3.12 artifacts/recovery-mcp
uv pip install --python artifacts/recovery-mcp/bin/python -r "$NISAYON_PACKET/mcp-requirements.lock" -e artifacts/recovery-agents
artifacts/recovery-mcp/bin/python "$NISAYON_PACKET/mcp_effect_probe.py" artifacts/recovery-mcp-fresh
python3 "$NISAYON_PACKET/audit_mcp.py" artifacts/recovery-mcp-fresh
NISAYON_EVIDENCE_ROOT=artifacts/recovery-evidence artifacts/recovery-mcp/bin/python -m pytest -v "$NISAYON_PACKET/audit_controls.py"
```

No API key is needed. The server binds loopback only, writes synthetic local
journals and is shut down in cleanup. The command refuses an existing result
directory. This experiment uses MCP 2.3.0; it is not compatible with MCP 1.x.
Observed dependency versions are locked, but wheel hashes and cross-platform
dependency resolution are not qualified. The environment measured was macOS
14.4 ARM64, Python 3.12.13. The local server lifecycle follows the SDK's native
HTTP test pattern; OpenAI's MIT license is retained in
[OPENAI-LICENSE.txt](records/OPENAI-LICENSE.txt).

Broader agent comparisons, durable distributed transactions, real training quality,
CUDA behavior and deployment acceptance require their own experiments. The next
product proof remains one consequential owner decision and a genuinely untouched
transfer with independent scoring and complete accounting.
