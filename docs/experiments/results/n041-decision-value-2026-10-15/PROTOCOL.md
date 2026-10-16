# N041: qualify a cheap score before relying on it

Frozen before executing the public records on 15 October 2026. The paper's
results have already been read. This is an exposed data readback, not a blinded
experiment, a new policy evaluation or evidence of Nisayon superiority.

Question: can low failure optimism by itself justify using a world model to
screen proposed robot actions? The scientific purpose is to test a proposed
shortcut before putting it into the owner workflow. A score that also rejects
successful actions can make that workflow worse.

Use CureWM revision `8a7ee5dfd71eab09020db57754e72a4dc23c825b`. Retrieve only
its published analysis scripts, scalar probe records and license/notice. Verify
every file against the pinned Git tree and record SHA256 identities. No model
weights, training, physics, hardware, paid model calls or new dependencies.

Run the unchanged upstream `analysis/check.py` once. Retain its full output,
return code and elapsed process time. Report all 20 checks, including failures;
do not edit expectations to obtain a pass.

Independently read all three arms in the four published LIBERO suites. Require
unique `(shard, name)` identities, complete matching keys and identical outcome,
family and severity fields across arms. Require explicit Boolean outcomes and
finite scores. Missing or conflicting rows invalidate the relevant comparison;
they are not dropped or converted to failures.

For each suite and arm, recompute failure and survivor counts, fraction of
failures scoring above 0.5, fraction of survivors scoring at or below 0.5, and
AUROC using direct failure versus survivor comparisons with half credit for
ties. Count source demonstration clusters separately from perturbation records.
The value threshold is the paper's diagnostic threshold, not a calibrated
probability or an owner acceptance rule. Compare rounded results to the native
table. Do not interpret the many perturbations as independent demonstrations.

Inspect the independent calculation with known ordering/tie cases and corrupted
record controls for duplicate identity, missing arms, mismatched labels and
nonfinite scores. These check the readback, not the physical validity of data.

Stop after this bounded readback. No new intervals or threshold optimization are
needed: upstream intervals retain their stated source cluster bootstrap premises.
The published records do not independently establish simulator replay fidelity,
task success, real robot transfer or economic value. Do not reuse exposed records
as a fresh owner confirmation or untouched reuse case.
