# Camera fixes require a declared input contract

28 October 2026. The unchanged SDK and ordinary native checks reach the same
five decisions on a public LeRobot camera-preprocessing incident. Both proposed
fixes satisfy a declared contract; they make different choices about absent
SmolVLA inputs. No diagnostic or complete-cost advantage is established.

[Issue #5118](https://github.com/huggingface/lerobot/issues/5118) reports that a
missing camera can shift another camera's image into the wrong slot.
[PR #5129](https://github.com/huggingface/lerobot/pull/5129), pinned at
`52d44203ed5bd5442dfd85d88ab78f7e91e54d77`, keeps SmolVLA's existing placeholder
budget and changes six policies. [PR #5120](https://github.com/huggingface/lerobot/pull/5120),
pinned at `8ff9599739e5607d5ccaeaacd3e12441dc24ae49`, retains every configured
SmolVLA slot and changes three policies. Their authors supplied these remedies;
this study qualifies their software behavior.

The six-policy incumbent is `9f45b7b37cc4b33f8ecdb503aa4d209370bd528d`.
The other proposal's base is `77710dee471d5cfb070fad1adc30c8f94dc14757`.
The six tested method ASTs agree between those bases; full source identities
remain distinct. Both bases were executed and retain their failures.

## What the checks decide

| Candidate and question | Matching native rows, both seeds | SDK software decision |
| --- | ---: | --- |
| Incumbent, six policies, preserve configured budget | 432 / 704 | reject |
| PR #5129, six policies, preserve configured budget | 704 / 704 | adopt |
| PR #5120, its three policies, preserve configured budget | 312 / 384 | reject |
| PR #5120, its three policies, retain every configured slot | 384 / 384 | adopt |
| PR #5129, six policies, retain every configured slot | 632 / 704 | reject |

All five SDK executions are valid, all five portable reviews agree with the
retained assessments, and all deployment decisions remain unresolved. The
reviews also succeed with the bound owner directories and native environment
temporarily unavailable. This checks portable evidence consistency, not
independent adjudication.

Each seed supplies 352 finite rows across PI0, PI05, PI0-FAST, SmolVLA, X-VLA
and EVO1. The matrix covers every three-camera subset, input dictionary order,
supported declared channel layouts, PI05 temporal masks, last-frame selection,
SmolVLA budgets 0/1/3, EVO1's absence budget, all-missing refusal and caller-input
preservation. Slot images are compared by exact shape, dtype and byte digest;
masks retain their originating camera. No resizing is requested in this matrix.
These rows share generated inputs and methods. They are not independent robot
trials or a population estimate.

The first copy attempt failed on upstream documentation symlinks. It was
retained; source export was corrected before any new matrix outcome. The native
code, contract and inputs stayed unchanged. The frozen runs then completed
2,816 native condition calls across four source variants and two seeds.
The SDK made 30 fresh-process reference/control/candidate attempts. Its explicit
same-shape camera-swap control is detected in every case.


A fresh acquisition and preparation reproduce all 2,545 declared owner-file
identities. PR #5129 seed 17 then reproduces all 352 rows and exact observation/
reference bytes in a project outside Git. An earlier relocation still lay under
the original Git root; that limitation and the additional outside-Git check are
retained in the measurements. These are repeated exposed checks, not fresh task
confirmation or independent replication.

## Cost and limit

The [measurements](measurements.json) retain source acquisition (5.97 s),
environment setup (14.31 s), cold native import qualification (43.12 s), the
eight ordinary native processes (85.39 s), and five SDK
plan/execute/assess/export/review workflows (416.63 s). Nested worker/CPU timers
are not added again. The native and SDK totals cover different assignments and
deliverables; they are not a matched complete-workflow timing comparison.
Research, implementation, active human effort, provider charges, review,
adoption and maintenance are not fully measured. Complete cost remains unknown.

The public descriptions and an ordinary configuration/source check already
expose the budget choice. The native comparator receives the same useful
contract and reaches the same decisions. This case therefore supplies no
incremental decision advantage or owner saving. It establishes that the
existing SDK can execute, retain and transport this scoped qualification.

No owner enrolled, no private data was used, no robot or policy weights ran,
and no upstream reply or patch was sent. No superiority, physical safety,
model-quality improvement, novel diagnosis or independent reuse follows.
The two seeds are declared exposed software conditions. This does not replace
the separate owner comparison or its untouched incident.

## Inspect or reproduce

The [runnable example](../../../../examples/qualification/camera_slots/README.md)
contains the frozen inputs, contract, pinned acquisition and environment,
native runner and existing SDK path. The
[evidence archive](evidence.tar.gz) contains 38 original members: raw native
observations/reference outputs and reports, five complete portable SDK bundles,
and their readback. [The manifest](evidence-manifest.json) binds every member.
The archive contains no policy weights or private owner records.

```sh
uv run --frozen python examples/qualification/camera_slots/verify_evidence.py \
  docs/experiments/results/camera-slot-qualification-2026-10-28
```

Native execution was qualified on the documented macOS CPU environment.
Repository CI and this read-only verifier do not reproduce policy inference or
the native matrix on another platform. This is a current-source example;
the tagged v0.2.0 wheel and its capabilities are unchanged.
