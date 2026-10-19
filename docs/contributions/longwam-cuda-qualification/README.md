# Full-weight LongWAM lifecycle checks on a 40 GB A100

19 October 2026. This contribution follows the invited runtime-contract review
of [LeRobot PR 5008](https://github.com/huggingface/lerobot/pull/5008), at
`58e162e768edf374803e6b6bffc5c89680b967b8`. The port and its original tests are
the upstream author's work. Nisayon supplied the additional reset-sensitivity
check and the execution reported here.

All 14 original/candidate case bodies passed across released IDM and COD after
loading through CPU memory and transferring the policy to CUDA. The original
direct CUDA fixture exhausted GPU memory before every test body on this device.
Both outcomes are retained. This packet records full-weight software checks
with synthetic inputs; it contains no simulator or physical robot result.

## Results and loading boundary

| Model | Case set | CPU loading then CUDA | Original direct CUDA loading |
| --- | --- | --- | --- |
| IDM | Original | 3 passed, no skips | 3 setup errors, no bodies executed |
| IDM | Candidate | 4 passed, no skips | 4 setup errors, no bodies executed |
| COD | Original | 3 passed, no skips | 3 setup errors, no bodies executed |
| COD | Candidate | 4 passed, no skips | 4 setup errors, no bodies executed |

The original cases check streaming/full-window VAE equality, a genuinely
pending late handoff, and reset with pending work. The candidate adds a reset
with changed observations and checks the actual new inference's episode,
anchor, state, image and returned action. Numerically equal actions remain
legitimate if the fresh inference produces them. Passing the original
same-input reset comparison alone cannot establish that new inputs were used.

The loading adaptation changes neither production model source nor test bodies
or assertions. It calls the native `from_pretrained` with `config.device="cpu"`,
then `policy.to("cuda")`, and restores the runtime configuration device. Before
each run, its added weight check compares all 2,089 serialized tensors exactly,
including dtype, and checks all 3,298 shared aliases. Every parameter is on CUDA.
The four streaming VAE observations have maximum absolute error zero.

The original loader constructs the model on CUDA before loading its checkpoint
on CUDA. The retained tracebacks show OOM during safetensors deserialization.
Temporary double residency is the source-supported explanation. Successful
CPU staging does not qualify that direct-loading path or every 40 GB device.
Allocation immediately after loading was 24,837,432,832 bytes; this is not peak
inference memory. Test timing includes setup and is not an inference benchmark.

## Inspect without models or CUDA

From a checkout of this repository:

```sh
python3 docs/contributions/longwam-cuda-qualification/verify_results.py
```

The standard-library reader verifies file identities, the exact four-cell
matrix for each loading path, case names and counts, process exits, weight
records, and observed VAE errors. It distinguishes 14 passed case bodies from
14 setup errors. A successful readback is consistency of retained records,
not independent execution or proof of physical truth. All fixtures are exposed.

The [manifest](manifest.json) binds the public files. Original summaries,
weight records and execution logs are exact copies. JUnit files retain all
cases, times and failures; only the infrastructure hostname attribute is
removed. The [provenance record](provenance.json) gives both original and
published hashes for that transformation. Local source paths in dependency-lock
comments are generalized; all requirements and package hashes are unchanged.
No raw cloud-account or private correspondence record is needed to inspect
this result.

## Inspect the proposed test change

The [reset patch](reset-sensitivity.patch) applies to the pinned native test.
It is a proposed test improvement, not an upstream runtime fix. These files
retain the exact executed bytes, including upstream NVIDIA/Apache notices:

| File | Role |
| --- | --- |
| [Native](fixtures/native.py.txt) | Original three cases and direct loading |
| [Candidate](fixtures/candidate.py.txt) | Additional reset case, direct loading |
| [Native with CPU staging](fixtures/native-cpu-stage.py.txt) | Original bodies with the qualified loading and weight check |
| [Candidate with CPU staging](fixtures/candidate-cpu-stage.py.txt) | Additional reset case with the qualified loading and weight check |

The full-weight run establishes execution of the declared checks, not causal
use of every input by the learned model or all internal latent-state freshness.

## Run the qualified fixtures in a separate environment

Use the pinned upstream revision and a fresh, compatible Linux environment.
The execution used Python 3.12.13, Torch 2.10.0+cu128, CUDA runtime 12.8,
driver 580.178.04 and one A100-SXM4-40GB. The complete package observations
are in [environment.json](results/environment.json); the
[hashed dependency lock](linux-requirements.lock) records installation inputs.
Conversion completed with 85 GiB host RAM and 64 GiB swap. These are observed
resources, not a demonstrated minimum. Do not synchronize an existing research
environment to this lock.

[assets.json](assets.json) names the exact released model/backbone/tokenizer
revisions and the 12 allowed files, with sizes and SHA256 digests. The downloads
total 38.286 GB. Weights are not redistributed here. Follow their upstream
terms and use the pinned native conversion command:

```sh
python examples/longwam/convert_checkpoint.py \
  --bundle /absolute/path/to/released-idm-or-cod \
  --backbone /absolute/path/to/released-backbone \
  --tokenizer-model /absolute/path/to/released-tokenizer \
  --output /absolute/path/to/new-native-checkpoint
```

The retained [IDM](results/native-idm-manifest.json) and
[COD](results/native-cod-manifest.json) manifests identify the converted files.
Verify those identities before interpreting a run as this qualification.
In a disposable checkout of the pinned port, replace only
`tests/policies/longwam/test_longwam_gpu.py` with the exact selected `.py.txt`
fixture. Set `PYTHONPATH` to that checkout's `src` and root directories. For
each model, run the original and candidate CPU-staged fixtures in separate
processes, using fresh output paths:

```sh
LONGWAM_NATIVE_CHECKPOINT=/absolute/path/to/native-checkpoint \
N063_MODEL_LOAD_RECORD=/absolute/path/to/new-weights.json \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
python -m pytest tests/policies/longwam/test_longwam_gpu.py \
  -q -s -ra --junitxml=/absolute/path/to/new-result.xml
```

`N063_MODEL_LOAD_RECORD` is the exact historical fixture's output setting.
The direct-loading files do not use it. Missing CUDA or checkpoint prerequisites
cause skipped cases; exit zero with skips is not qualification. Require all
three original or four candidate nodes, no omissions or duplicates, exact
weights, and no failures or errors. Preserve unsuccessful runs separately.
The reader above checks this retained packet; it is not an acceptance tool for
arbitrary new executions. Restore the original file after an isolated run.

The port's broader reference-action, LIBERO and training results remain the
author's reported results. This contribution does not reproduce them. It also
does not establish owner savings, general reset correctness, physical task
confirmation, or separate reuse.
