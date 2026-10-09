# Controller-target scope visibility (19 September 2026)

The execution lane's Lift deployment record can declare `controller_target`
(`restored` or `nominal`) since `62bb2da`; an omitted field keeps the restored-state
convention. The evaluator reads the repair a candidate carries from the deployment
fields where it differs from the changed deployment and rejects a candidate whose
components fall outside the declared repair scope (`candidate_outside_repair_scope`).
Before this correction the evaluator's field list did not contain `controller_target`,
so a candidate that changed the convention carried no component for it, and the scope
check could not see it.

## Before

[`smuggled-target-bundle/`](smuggled-target-bundle/) is a synthetic strict bundle in the
mini document's shape whose candidate inverts the repair gripper sign, as the declared
scope allows, and also sets `controller_target: nominal`, which the scope does not
allow. Every run carries its `configuration.deployment`, the confirmation and the frozen
protocol name the candidate consistently, and the candidate completes every assigned
condition. On the unfixed evaluator the public command accepts it
([`smuggled-target.before.decision.json`](smuggled-target.before.decision.json),
command `08f917fc`, 0.252997 s): decision `accepted`, no reasons, the candidate's
components name the gripper sign only. The four new tests fail on that source
(command `b5f340c2`, exit 1).

## Correction

`controller_target` joins the evaluator's deployment fields with the documented default
`restored`, and the component comparison takes a field's default when one side omits
it. An explicit `restored` on a candidate is therefore not an edit against a legacy
changed deployment, and an omitted field cannot hide a reversion. The deployment label
shows `controller_target=nominal` when declared.

## After

The same bundle is rejected ([`smuggled-target.after.decision.json`](smuggled-target.after.decision.json),
command `a5ea16f2`, 0.256922 s): every candidate run carries
`candidate_outside_repair_scope` for path `controller_target`. The tests pass
(command `ffba186c`): the smuggled change is rejected, an explicit `restored` equals the
omitted convention and the gripper repair is accepted, a target-only candidate is
admitted under a scope that names `controller_target`, and rejected under the gripper
scope. Full check at the corrected source: 582 tests, lint, format and 87 documents
(command `2ed485d8`, 236.864366 s). The historical decisions and both retained scores
reproduce unchanged: no retained record carries the field.

Five commands, 237.955254 s of command wall; no simulator execution, no model call, no
download.
