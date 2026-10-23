# Reproduce the declared native software check

Portable bundle review only needs Nisayon. Native execution below targets the
qualified macOS ARM64 CPU environment and downloads its dependencies. The lock
was resolved for that platform; a different platform needs a separately resolved
and qualified environment. No checkpoint or model download is required.

Run from the Nisayon repository root. Choose new output directories: plans and
evidence stores are not overwritten. These are published development probes,
so their replay is not fresh confirmation or an untouched incident.

```sh
case_dir="$PWD/docs/experiments/results/groot-statistics-2026-10-23"
native_dir="$PWD/artifacts/groot-pr796-replay/source"
env_dir="$PWD/artifacts/groot-pr796-replay/venv"
mkdir -p artifacts/groot-pr796-replay
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/NVIDIA/Isaac-GR00T.git "$native_dir"
git -C "$native_dir" sparse-checkout init --cone
git -C "$native_dir" sparse-checkout set gr00t/data gr00t/configs gr00t/utils
git -C "$native_dir" fetch --depth 1 origin \
  944fe70c4fd54e3fcb80a7d7258a328f9c061176 \
  f6242731eb6fed8e1ec4250bb97cfae64a482843
git -C "$native_dir" checkout --detach 944fe70c4fd54e3fcb80a7d7258a328f9c061176
git -C "$native_dir" show \
  f6242731eb6fed8e1ec4250bb97cfae64a482843:gr00t/data/dataset/sharded_mixture_dataset.py \
  > "$native_dir/pr_mixture.py"
cp "$case_dir/qualification_adapter.py.txt" "$native_dir/qualification_adapter.py"
uv venv --python 3.12 "$env_dir"
uv pip sync --python "$env_dir/bin/python" --require-hashes "$case_dir/requirements.lock"
uv run --frozen nisayon-qualify plan "$case_dir/sdk-candidate-v2.json" \
  --project "$native_dir" --python "$env_dir/bin/python" \
  --out artifacts/groot-pr796-replay/candidate \
  --plan artifacts/groot-pr796-replay/candidate-plan.json \
  --timeout 60 --total-seconds 600
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --frozen nisayon-qualify run \
  artifacts/groot-pr796-replay/candidate-plan.json
uv run --frozen nisayon-qualify export artifacts/groot-pr796-replay/candidate \
  --out artifacts/groot-pr796-replay/review.zip
uv run --frozen nisayon-qualify review artifacts/groot-pr796-replay/review.zip
```

Expected software result: `adopt`, with `deployment_decision: unresolved`.
The plan records the new host environment; its hash will differ from the
historical plan. A path or hash difference does not itself establish a defect.

Repeat planning and execution with `sdk-original-v2.json`, `sdk-zero-all-v2.json`
and `sdk-ineffective-v2.json`, each with a distinct plan and store. Expected exit
codes are 1, 1 and 3. Do not use `set -e` to discard these expected nonzero
scientific outcomes. Their published bundles already retain the original runs.

The exact 18-case development and 32-case generation harness is retained as
`probe.py.txt`. Its fixed paths identify the original workspace layout;
`protocol.json`, the input records and outcomes expose all values for replay.
The native pipeline used generated parquet files, not the absent LIBERO demo
data. The four upstream test files are named in `native-tests.txt`; those tests
used the separate extended lock and candidate overlay described in the report.
