# Cartesian pose width is independent of joint count

**12 October 2026 · N026 · bounded software correction delivered; adoption unknown.**

XPolicyLab's shared helpers use the robot's joint count to size Cartesian pose
fields. Its documented pose is seven values: position and quaternion. At
[`f6e309e`](https://github.com/XPolicyLab/XPolicyLab/commit/f6e309e8ece20bfa33c0e5d7b05a5f3287522757),
a valid pose on a six-joint arm is rejected, while a malformed six-value pose
passes both helpers. Packing and unpacking agree with each other while violating
the declared format. A seven-joint arm hides the discrepancy.

The [frozen decision packet](DECISION.md) compares current primary research and
chooses this check before another integration layer. The source-derived
hypothesis is supported by normal imports, the unchanged native validator and
explicit expected values. A [four-line patch](cartesian-width.patch) fixes the
declared controls. One [upstream report](https://github.com/XPolicyLab/XPolicyLab/issues/167)
contains the correction and an executed reproduction; exact title, body and
author were [read back](issue.json). Maintainer acceptance remains unknown.

## What ran

| Declared controls | Original | Corrected |
|---|---:|---:|
| Valid Cartesian poses: single/dual six-joint and mixed six/seven-joint arms, three array layouts | 0/9 | 9/9 |
| Valid Cartesian poses: seven-joint arm, three array layouts | 3/3 | 3/3 |
| Existing dual/mixed joint-space behavior, three array layouts | 6/6 | 6/6 |
| Reject malformed six-value Cartesian poses, single/dual arms and observation/dataset inputs | 0/4 | 4/4 |
| **Total** | **9/22** | **22/22** |

Array layouts cover a single observation, a three-step chunk and two sequences
of three dataset records. Values are nonzero and distinguishable. The unchanged
`validate_robot_state_dict` accepts every valid input and rejects the malformed
poses. Explicit concatenation checks ordering; unpacking restores values and
keys. All checked input arrays and source files remain unchanged by execution.
The six joint-space packed outputs are byte-identical across variants.

The patch changes only Cartesian field widths in `_validate_config`. The
[patch identity check](patch-identity.json) applies it to the original file and
reproduces the tested candidate exactly. Removing its one guarded assignment
restores the original AST. For the documented string `action_type="joint"`, the
new branch is not entered; prior validation and the remaining code are identical.
This supports preservation of that code path, including its errors. The executed
joint controls cover valid inputs; they are not an exhaustive error-input test.

The first attempt failed during import before executing a case: the selected
source download omitted `tcp/model_server.py`. That invalid attempt, its original
probe and its cost are retained. The [import supplement](import-supplement.json)
fetches the unchanged module from the same revision. The frozen decision and all
22 controls stayed unchanged. The subsequent baseline and candidate use the
same probe and new locked environment, with no import stubs or extracted bodies.

Results: [original](baseline-result.json), [candidate](candidate-result.json),
[evidence and costs](evidence.json), [source receipts](sources.json),
[validation](validation.json). The seven recorded commands sum to **32.568969
command-seconds**, including the failed import. Some commands overlap. This is
not complete engineering time: acquisition, research, preparation, review,
adoption and maintenance remain unmeasured. No cost advantage follows.

## Reproduce

The [compact reproduction](reproduce.py) was executed on both variants. It fails
on the original helper and passes after the patch. The complete probe is
[probe_pose_contract.py](../../../../scripts/experiments/probe_pose_contract.py).
Use a new checkout and environment; preserve existing experiment artifacts.
Run from the Nisayon root:

```sh
git clone --no-checkout https://github.com/XPolicyLab/XPolicyLab.git artifacts/pose-contract-replay-source
git -C artifacts/pose-contract-replay-source checkout --detach f6e309e8ece20bfa33c0e5d7b05a5f3287522757
uv venv --python 3.12.13 artifacts/pose-contract-replay-venv
uv pip sync docs/experiments/results/pose-contract-001/requirements.lock --python artifacts/pose-contract-replay-venv/bin/python --require-hashes
artifacts/pose-contract-replay-venv/bin/python -B scripts/experiments/probe_pose_contract.py \
  --source artifacts/pose-contract-replay-source \
  --protocol docs/experiments/results/pose-contract-001/protocol.json \
  --import-supplement docs/experiments/results/pose-contract-001/import-supplement.json \
  --variant baseline --out artifacts/pose-contract-replay-original
```

The original probe intentionally exits 1 with 13 failed controls. Apply the
retained patch and run the candidate into a separate output directory:

```sh
patch -d artifacts/pose-contract-replay-source -p1 < docs/experiments/results/pose-contract-001/cartesian-width.patch
artifacts/pose-contract-replay-venv/bin/python -B scripts/experiments/probe_pose_contract.py \
  --source artifacts/pose-contract-replay-source \
  --protocol docs/experiments/results/pose-contract-001/protocol.json \
  --import-supplement docs/experiments/results/pose-contract-001/import-supplement.json \
  --variant candidate --out artifacts/pose-contract-replay-corrected
```

Expected: 22 passes, exit 0. These commands describe a fresh reproduction route;
the [retained command records](evidence.json) identify the actual paths used here.
XPolicyLab source and required credit are covered by [NOTICE](NOTICE.txt) and its
[Apache 2.0 license](XPolicyLab-LICENSE.txt).

## What this changes

The [primary-source comparison](DECISION.md) strengthens the case for qualifying
the meaning of an interface within established workflows. XPolicyLab already
supplies native validation and adapter auditing; an appropriate six-joint
Cartesian check can expose this defect without Nisayon. Its integration study
is a competent alternative to account for, not evidence of our advantage.

This result adds specific coverage and a usable correction. It does not establish
novel testing, general diagnosis, physical performance or lower complete cost.
The controls were derived after source inspection, not held out. The native
validator and helper share an upstream codebase; this is not an independent
audit. No full upstream adapter audit, learned-policy rollout, physics or
hardware run was executed. Other action-dimension callers and the separately
noticed single-arm joint-key discrepancy remain outside this allocation.

No Nisayon production backend or general checker was added. N015 still needs
an owner with a consequential deployment choice and measurable review,
integration and maintenance costs. Resume this incident on maintainer evidence
or changed source, then bind qualification to that revision. Do not rerun these
exposed controls as independent confirmation or treat another simple bug as
proof of the broader commercial thesis.
