# Phase II intake and native mechanism check

26 November 2026. Research proxy; no owner enrollment or deployment decision.

## Decision before implementation

The existing production qualification kernel already has dependency applicability,
portable evidence, finite decision probes and complete-cost accounting. Preserve it.
The original finite acquisition campaign remains a permanent negative control.
Its proof has been read and its 16,331 checks and retained choices reproduced.

No candidate owner has supplied acceptance, a working physical reference, or a
complete cost ledger. The twofold complete-cost target is therefore unresolved.
No new acquisition mechanism is justified by that target. This bounded check
addresses a different question: whether a publicly reported integration mechanism
can be reproduced with existing local assets, and whether alternative changes have
different mechanical consequences. It cannot pass the owner-value gate.

## Selected public incident and alternatives

Source: https://github.com/ARISE-Initiative/robosuite/issues/853 (open; reporter
Mugi-Studing; no maintainer response at intake). Reported robosuite 1.5.1,
MuJoCo 3.3.5. Available local stack: robosuite 1.5.1, MuJoCo 3.2.7, NumPy
1.26.4, Python 3.12.13, CPU. This is a cross-version mechanism reproduction,
not an exact reproduction of the reporter's environment.

The source supplies unusually large fingertip inertia and enabled fluid forces.
MuJoCo's documented inertia-box fluid model couples inertia to drag. Compare
stock parameters, zero fluid density/viscosity, the reporter's diagnostic
inertia of 1e-6 kg m², and their combination. The 1e-6 value is an intervention
for diagnosis, NOT a calibrated physical replacement or an accepted correction.
No force threshold or task-acceptance label is inferred from it.

## Frozen measurement procedure

- One stock Panda Lift environment, initialization noise disabled; NumPy seed
  20261126. Save initial qpos and compiled XML. No camera or learned-policy load.
- Recompile each variant from the same XML; change only the two fingertip inertia
  elements and/or fluid options. Fresh data for each query; same qpos and controls.
- Joint 7 velocities: 0, +0.45, -0.45, +0.9, -0.9 rad/s; all others zero.
- At each state record native passive force, the fluid-only difference against
  zero-fluid at the same state, joint-space mass matrix, and contact count.
- At +0.9 rad/s run 20 actual native integration steps for each variant under
  zero actuator commands, retaining all qpos/qvel. These are free-response probes,
  not task executions or a successful repair. Do not replay a stock future.
- Independently check the documented isotropic inertia-box drag formula on a
  single hinge, for both inertias and all five velocities. Absolute tolerance
  1e-10 N m plus relative tolerance 1e-9 covers floating-point arithmetic, not
  physical error. Analytical comparison uses no native fluid-force output.
- Retain identity control (stock recompile), both intervention mechanisms,
  equivalent zero-fluid comparison and every failure. No missing observation
  counts as a pass. No estimated statistical confidence.

Record the source digest before execution, raw arrays, versions, source assets,
subprocess runtime, peak memory and commands. Limit native subprocess to 300 s,
one process, 100 MiB new artifacts, minimum 5 GiB free disk; no downloads.

## Explicit gate and stopping rule

Different torques or trajectories do not supply D(h), the set of corrections
meeting owner task and operational constraints. True inertia, admissible fluid
approximation, task tolerances and maintenance/confirmation costs remain unknown.
If those premises cannot be established, stop before constructing a comparative
selector or claiming a decision-discriminability witness. Do not invent labels,
priors or weights to bridge the gap. The native check is discovery, not hidden
confirmation or an untouched validation case.

Fresh 32-pair task confirmation remains required for a later applicable deployment
claim; this static/free-response check neither performs nor waives it. Software
qualification, simulation task qualification and deployment acceptance remain
separate. No hardware execution or outreach is authorized here.
