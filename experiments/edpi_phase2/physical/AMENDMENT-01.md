# Native identity correction

The first frozen mechanism check completed and failed its nominal identity
control. Preserve PROTOCOL.md, probe_drag.py, native-freeze.json and native-run-01
unchanged. Passive/fluid force differences were about 5.33e-15, but the mass
matrix differed by 3.3333342e-6 after XML export/recompilation. The ten independent
single-hinge analytical checks passed. This is an engineering failure of this
research harness, not an accepted model-equivalence result.

The smallest alternative is a native compiled-model copy. The second procedure
will use copy.copy(MjModel), verify its stock measurements at the original frozen
tolerance, and retain the XML round-trip field differences for diagnosis. Change
body_inertia only on candidate copies; call mj_setConst after that change to
recompute derived constants. Use fresh MjData and the same initial qpos for each
measurement and free-response trajectory. Preserve all other conditions, sample
counts, absolute/relative tolerances and the unresolved owner/confirmation gate.

The copy, XML round trip and parameter modification are separate operations.
Do not label passing torque alone as physical identity. Neither a successful
copy nor a failed round trip proves general snapshot restoration for policies,
controllers, random state, observation history or other MuJoCo versions.

The second run is an exposed engineering correction, not independent confirmation.
The source and this amendment are frozen before its execution. The first run's
failure is a required part of the final packet.
