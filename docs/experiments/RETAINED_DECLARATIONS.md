# Declarations on retained native evidence

This workflow records explicit development claims and refusals for the twenty
case–arm assignments in `development-ablation-001`. Both arms use the same
[declaration plan](../../work/development/retained-declaration-plan-v1.json) and
the original `first-case-obligation-v0.2` terminal rule. Every statement freezes
before this invocation begins consuming terminal decisions. The historical
ledger already exposes those decisions; this ordering is a software property,
not prospective experimental evidence or independent custody.

The actual run at `3bd1a060826a1b859cc6eb86042cef80fb3a0a62` completed in
1.209089 s. Its [complete table](results/retained-declarations-001/records.tsv)
and [retained byte inventory](results/retained-declarations-001/retained-location.json)
locate all receipt and evidence files. Raw-store verification separately retained
the native [D01 positive](results/engine-continuation-checks-001/D01-positive.json)
and [D05 rejection](results/engine-continuation-checks-001/D05-rejection.json), with
identical historical outcomes and all corruption controls rejected. This is
reassessment of existing data, not fresh confirmation.

The corrected run at `97110995f59da1009ff9bf722f7b68ab7893cfe4` completed in
0.513159 s. Its [decision table](results/retained-declarations-002/records.tsv),
[full cost export](results/retained-declarations-002/costs.tsv) and
[byte inventory](results/retained-declarations-002/retained-location.json) retain
the local preparation ledger and all twenty assignments. All 163 engine and
application tests passed on that clean implementation revision. The evaluation
endpoint remains a separate dependency; this is not an effectiveness report.

```sh
.venv/bin/nisayon run --label retained-declaration-workflow --timeout 180 -- \
  .venv/bin/python -m nisayon.engine.retained_declarations \
  --source docs/experiments/results/development-ablation-001 \
  --plan work/development/retained-declaration-plan-v1.json \
  --output artifacts/retained-declarations-new
```

Use a new output directory. The output includes the frozen plan and assignment
list, original diagnosis bytes, a declaration receipt for every assigned arm,
separate terminal-start/result receipts, exact historical decision bytes, the
complete packet and a tab-separated table. Original records are read only.
An interruption retains the declarations, partial receipt state and completed
rows. `inspect_declaration(root, evidence_root=...)` reads that state without
resuming an execution. No simulator or model is called.

For one report over all frozen assignments, including statements that were never
written, use the read-only recovery command. Its output must be outside the
original demonstration:

```sh
.venv/bin/python -m nisayon.engine.retained_declarations \
  --inspect artifacts/retained-declarations-new \
  --output artifacts/retained-declarations-recovery-new.json
```

Recovery reads the bound freeze, historical inputs and each receipt. It reports
missing declarations, declarations awaiting terminal work, interrupted terminal
work, retained terminal evidence, binding findings and writer cost gaps. It does
not resume an execution or turn a missing statement into abstention. The report
is a read-only observation of the retained files; active writers may continue
after inspection, and local integrity is not external custody. Locate the
original command record for its outer cost; individual writer walls are nested
components. Claim correctness still belongs to the prospective evaluator.

A malformed observed-clock field or terminal-evidence reference is retained as
a finding on that assignment. Recovery continues through the other assignments;
it never repairs the source bytes. Damaged attempt-cost JSON similarly leaves
the original declaration visible and that attempt's cost unknown. The
[actual damaged-cost control](results/engine-damaged-cost-001/README.md) demonstrates
this behavior on a copy of the retained native packet.

The plan deliberately claims the seven retained diagnostic candidates per arm,
including D05. D05's terminal rejection therefore remains beside its declaration.
D06 and D08 receive explicit development refusals; D10 remains unresolved.
These statements were authored for the demonstration and must not be attributed
retroactively to the historical arms. No new correction or effectiveness estimate
is asserted. In particular, the new declaration must never be copied into an old
v1 ledger's `arm_claimed_acceptance` field.

Each packet row retains the entire historical trial and its cost categories.
The source preparation ledger is copied and verified once at packet level.
`costs.tsv` exports every historical trial quantity, shared preparation cost,
new processing measurement and missing category. A missing preparation ledger
is explicitly unknown. Old diagnostic,
confirmation and simulator walls overlap as declared in the original record;
new terminal-read and writer walls are nested in the new command wall. None of
these is an engineer-effort measurement. Missing effort, provider charges,
energy and unrecorded processing remain explicit unknowns.

The first packet, `retained-declarations-001`, incorrectly left its preparation
reference relative to the original suite rather than the packet output root.
The original ledger and its 2534.406124 s recorded command total were intact,
but that reference was not portable. A subsequent workflow run retains the
verified copy under `sources/preparation-costs.json`. The first packet and its
command remain unchanged as evidence of this defect.

The engine packet is `nisayon.retained-declaration-packet.v1`. Its `freeze`
reference locates the assignment manifest, and each row binds `declaration`,
`terminal_start`, `terminal_result` and `terminal_evidence`. References resolve
against the output directory. The historical terminal checker decisions are
preserved without translating them into prospective claim classifications.
That translation and the external-record field assessment are evaluation-owned
integration dependencies. The current table names them as such.

The three focused tests use real committed native metadata. They verify all
twenty assignments, the declaration-before-terminal ordering across both arms,
D05's retained claim/rejection, missing-cost preservation and recovery from an
injected terminal read failure. They neither create physical observations nor
alter the source suite. The first run's recovery assertion used the wrong state
name (`declared_terminal_not_started`); it is retained as a failed check and was
corrected to the writer's actual `declared_awaiting_terminal` state.
