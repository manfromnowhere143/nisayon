# Worker isolation must preserve processor links

**11 October 2026 · initial source-level finding.**

The later [native follow-through](../eval-copy-native-001/README.md) checks
installed pipelines and the full evaluator with scripted CPU policy/Gym
fixtures. This page preserves the earlier, narrower evidence. Learned-policy,
GPU and physical behavior remain untested.

LeRobot [PR #4450](https://github.com/huggingface/lerobot/pull/4450), at
`ca864ff1c7727d15ea4bc6c5f1e21b105633a473`, addresses shared policy state during
parallel evaluation. Its worker factory deep-copies the policy and each
processor separately. That splits a required connection: the absolute-action
step must read the state cached by the relative-action step in the same worker.

The [CPU source probe](probe.py) finds two consequences. Starting with an empty
cache, postprocessing raises even after preprocessing has run. Starting with a
previously cached joint state of `100`, it silently returns target `101` after
the worker observes state `10` and predicts delta `1`. The correct target is
`11`. An excluded gripper dimension stays at `0.25` in the controls.

## What ran

Five pinned source files supply unchanged definitions of the worker factory,
processor base and registry, relative/absolute steps, arithmetic and transition
keys. AST selection omits module-level dependency imports; class decorators and
the selected bodies execute. The callback, observations and policy token are
scripted. Processor steps are called directly, without pipeline converters,
`eval_policy_all`, an environment or learned inference. The result is a source
counterexample to this candidate, not a replay of the original issue's robot
success rates.

The controls were listed before execution. The conventional reference directly
uses the linked steps sequentially and returns `11`. The proposed correction
performs one `deepcopy` on the complete context tuple, retaining a single copy
memo within each worker. [Python's documented copying behavior](https://docs.python.org/3.12/library/copy.html)
explains this mechanism; no new copying algorithm is claimed.

| Control | PR's separate copies | Connected copy |
|---|---|---|
| Fresh relative-action state | Rejects missing cached state | Correct target |
| Previously cached state | Silent target `101` instead of `11` | Correct target |
| Relative processing disabled | Pass | Pass |
| Three tasks reusing one worker | Missing-state failures | Correct targets and context reuse |
| Two workers, two tasks each, barrier-controlled overlap | Missing-state failures | Correct targets, distinct contexts and reuse |
| Explicitly uncopyable policy | Clear rejection | Same clear rejection |

The [result](result.json) retains outputs and individual predicates. Both
variants preserve the original context. The candidate passes all six controls;
the PR version passes the two negative controls and fails four semantic
controls. These are software controls, not robot trials or a performance score.
The [candidate patch](candidate.patch) applies to the exact inspected PR head.

## Delivered and still unknown

The [technical review](https://github.com/huggingface/lerobot/pull/4450#pullrequestreview-5483662010)
was posted once and read back with the exact author, commit and body. It includes
a small reproducer and correction. The initial shared-state diagnosis and
worker-copy design belong to the upstream issue/PR authors. This work adds a
specific regression finding; no upstream acceptance is established.

One connected copy does not prove isolation for arbitrary closures, custom
`__deepcopy__` methods, compiled policies or GPU state. Weight-memory cost is
unchanged as an open trade-off. Native paired-pipeline and rollout checks are
now retained in the follow-through; changed source still needs a rebound
integration check before upstream merge. No customer savings, repeat use,
automatic defect detector or general deployment guarantee has been demonstrated.

The scientific lesson is concrete: an optimization must preserve required
relationships within an execution context while separating mutable state
between contexts. Testing only race absence misses the first obligation.

## Reproduce

The five source URLs, exact revision and hashes are in [sources.json](sources.json).
Local captures are under `artifacts/scientific-next-step-2026-10-11`. A clean
checkout can retrieve those five files into a separate capture directory; the
probe refuses different source bytes. Use an environment with Python 3.12 and
PyTorch. Do not synchronize either retained research environment.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B docs/experiments/results/eval-copy-graph-001/probe.py \
  --captures artifacts/scientific-next-step-2026-10-11 \
  --out artifacts/eval-copy-reproduction.json \
  --patch-out artifacts/eval-copy-reproduction.patch
```

The [review receipt](review.json) retains selection, source custody, known costs,
the initial lint failure, checks and communication readback. Full engineering
and adoption costs remain unmeasured.
