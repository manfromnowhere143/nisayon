# Packet members the runtime assessor reads

The assessor (`src/nisayon/evaluation/a1_runtime_assessor.py`, CLI
`python -m nisayon.evaluation a1-runtime-assess STORE --contract runtime-contract.v1.json
--contract runtime-contract.v1.1.json --contract runtime-contract.v1.2.json
--contract runtime-contract.v1.3.json --dataset … --pilot-stats … --checkpoint …
--wheel …`) reads only members listed in `artifact-manifest.json`,
locates each by a filename substring, and rejects a needle that matches more than one
member. A seal that does not verify makes the whole assessment invalid; absent members
are reported as unresolved, never inferred.

| Member | Content |
|---|---|
| `seal.json`, `artifact-manifest.json`, `summary.json`, `invocation.json` | the pilot's seal layout |
| `dependency-gate*.json` | `route` (A), `wheel_url`, `wheel_sha256_expected`, `wheel_bytes_expected`, `downloaded_bytes`, `wheel_downloaded_bytes`, `other_downloaded_bytes`, `responses` {`consumed_before` 12, `used`, `cumulative_ceiling` 18}, `ledger` {`path` of a manifest-bound member, `sha256`}, `stopped`, `stop_mechanism` (one of response_ceiling, byte_allowance, storage_floor, storage_cap, digest_mismatch, size_mismatch, rights, transport_failure, other), `stop_reason` |
| the ledger member | the cumulative source ledger the gate names, inside the packet |
| `acquisition-receipt*.json` | `wheel_bytes`, `wheel_bytes_expected`, `wheel_sha256`, `wheel_sha256_expected`, `compared_against_retained_metadata`, `verified_before_installation`, `record` {`verified`, `members`, `bad`}, `license` {`member`, `sha256`, `declaration`, `covers_distribution`}; the assessor recomputes bytes, sha256, every RECORD member hash and the license text from the retained wheel (`--wheel`) and compares |
| `RECORD`, `LICENSE` (any subdirectory) | the extracted dist-info members, byte-identical to the archive's |
| `runtime-identity*.json` | `robosuite_version`; `historical` {`robosuite_version`, `lock_sha256_before/after`, `pyproject_sha256_before/after`, `venv_sha256_before/after`}; `packages` (name → {`version`, `sha256`}, including robosuite, mujoco, numpy, torch, robomimic and mink when installed); `installation` {`index_access_disabled`, `dependency_resolution_pinned`}; `mink_adaptation` {`reachable_from_lift_path`, `static_evidence`, `absent_from_sys_modules_after_construction`, `absent_from_sys_modules_after_episodes`} when mink is not installed; every digest lowercase 64-hex |
| `mink-selection*.json` | only when mink is installed: `version`, `artifact_sha256`, `rights` {`declaration`, `declared_before_artifact_get`}, the releases considered and the rule applied |
| `env-args*.json` | `consumed_env_args` (the exact attribute string) and `make_kwargs` (what `robosuite.make` received) |
| `controller*.json` | `right` with the effective OSC_POSE values read from the controller object, `gripper.type`, `action_dim`, `action_low`, `action_high` |
| `timing*.json` | `control_freq`, `control_timestep`, `model_timestep`, `opt_timestep` |
| `probe*.npz` | `gripper_close_qpos` (10, 2), `gripper_open_qpos` (10, 2), `sim_time` over the probe steps |
| `reset-determinism*.json` | `seed` 900, `state_sha256` [two digests], `obs_sha256` [two digests], `separate_processes` true |
| `replay-R-1*.npz`, `replay-R-2*.npz` | `states` (T+1, 32), `obs__<key>` (T+1, D) for every key, `obs__object-state` (T+1, 10), `cube_z`, `table_z`, `success`, `reward`, `sim_time` (T+1), `actions` (T, 7) as applied; row 0 is the state after `reset_to` |
| `replay-R-1*.json`, `replay-R-2*.json` | `attempt`, `completed`, `steps` (59), `failure`, seeds, thread count, wall and CPU |
| `episode-E-<seed>*.npz` | `actions` (n, 7) float32, `obs__<key>` (n, D) float64 raw, `success`, `reward`, `cube_z`, `table_z`, `inference_s`, `step_s` (n), `witness_steps` (k), `witness_raw__<key>` (k, D) float64, `witness_consumed__<key>` (k, D) float32 |
| `episode-E-<seed>*.json` | `seed`, `started`, `completed`, `termination` (`success`, `horizon` or `failed`), `steps`, `first_success_step`, `failure`, `parameter_sha256` of the parameters loaded for that episode |
| `inference-stats*.npz` | `<key>__mean` (float32) and `<key>__std` (float64) bound at inference, exactly the pilot packet's layout, dtypes and bytes |
| `policy-identity*.json` | `checkpoint_sha256` equal to the effective checkpoint digest, `parameter_sha256_before`, `parameter_sha256_after` (lowercase 64-hex, equal), rnn horizon and open-loop flag, threads |
| `costs*.json`, `failures*.json` | per-scope costs and every failure with partial output |
