## Arisole Robot Reliability Gate (`INSUFFICIENT_DATA`)

- Suite: `arisole-eval-lerobot-v0.1` v`0.1.2`
- Gate engine: `deployment-gate-v1`
- Config: `arisole-reliability-ci-v1`
- Suite status: `partial`

### Reasons
- **INSUFFICIENT_DATA** · `min_comparable_episodes` — paired_episodes=0 < min_comparable_episodes=20; statistically weak comparison cannot produce PASS/BLOCK.

### Transitions
- Paired: 0
- P2F: 0 · F2P: 0 · F2F: 0 · P2P: 0

### Honesty
- Missing success labels or weak n never become PASS.
- Trajectory metrics remain `insufficient_data` when channels are absent.
- Secrets must never appear in this summary.

### Reproducibility
```json
{
  "suite_id": "arisole-eval-lerobot-v0.1",
  "suite_version": "0.1.2",
  "gate_engine_version": "deployment-gate-v1",
  "config_version": "arisole-reliability-ci-v1",
  "evaluator_pinned": true,
  "artifact_hashes": {
    "baseline": {},
    "candidate": {}
  }
}
```
