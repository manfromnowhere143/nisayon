# Portable readback of the confirmed Lift repair

**9 October 2026 · software qualification complete.**

The new `nisayon verify-lift-transfer` command makes the retained B2 result
checkable without its simulator environments, policy weights or original
workspace paths. It is scoped to that exact sealed experiment. See the
[interface and reproduction command](../../TRANSFER_EVIDENCE.md).

The first retained invocation verified all 114 packet members and recomputed
0/10 unchanged versus 9/10 corrected, including 19,244 network-input array
witnesses. It consumed no new experiment condition. Its output is retained at
`artifacts/transfer-evidence-001/b2-inspection.json`; command
`1e01496db2544eef8fe1b2ea6a68467d` measured 0.245671 seconds wall time.
This excludes engineering effort and the original B2 execution, and omits the
historical readback's runtime-tree and resource-monitor checks. It is not a
comparative efficiency result.

The final [inspection](inspection.json) verifies **114 members / 4,074,252 bytes**,
all **19,244** network-input array witnesses and all ten paired outcomes. It
preserves seed 180104 as a corrected task failure. The earlier one-off readback
and its unchanged raw packet remain the historical evidence.

The [portability qualification](portability.json) used a new, non-editable
installation from the existing lockfile and the `records` extra. PyTorch,
MuJoCo, robosuite and robomimic were absent. The installed command returned
identical inspection JSON from the original packet, a relocated copy, and the
restored copy after two negative controls, with its working directory outside
Git. An altered trace returned `invalid`; a missing trace returned `incomplete`.
Both kept the decision unresolved. Only the copy was modified.

All **1,165 tests** pass, including **35 new controls**, plus lint, formatting and
147 local documentation checks. The new controls include rehashed contradictory
arrays, false producer summaries, incomplete outcomes, mismatched initial states,
seven repairs below the required eight, object-array rejection, path boundaries
and output preservation. Their arrays are labelled software fixtures, not
additional robot trials or confirmation conditions.

The [preservation readback](preservation.json) checks both original runtime
trees, all fifteen original input/source pins and the B2 packet after validation.
The [command ledger](validation.json) includes the initial controls, first
readback, clean installation, relocation controls, full checks and preservation.
Child command times remain nested; engineering, review, uninstrumented discovery
and provider costs are not measured. The separate clean reader environment is
retained locally and does not replace either experiment environment.

The implementation is restricted to B2's pinned seals. It does not add generic
repair dispatch, an OpenPI bridge adapter or an adaptive planner. The next value
experiment still needs a consequential incident with enough source and trace
evidence for the competent conventional workflow to run the same checks.
