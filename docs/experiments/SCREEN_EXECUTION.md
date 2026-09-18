# Public execution harness for the next screen

The shared callable `nisayon.engine.development.run_assigned_case` executes
one assigned public incident through both scripted arms. The ten-case runner
uses this same path. It checks frozen inputs and reservation ownership,
finishes both diagnoses, freezes both selected candidates, prepares both
confirmation stores, and only then starts confirmation. Each selected arm
pays for its own full reruns and final Fable check. Completed trial files
survive a later partner interruption.

The callable accepts typed finite Lift deployments. It is not a general robot
or agent interface. Its inputs contain no reserved answers. The current
diagnostic procedure is scripted and shares development knowledge; a future
screen controller must establish actual custody before supplying reserved
assignments.

The first completed development ledger is now bound in the
[public package](results/development-screen-package-001/package.json), frozen
at `f0f1f57`. Its [Fable check](results/development-screen-package-001/evaluator-check.json)
finds all 20 evaluator sources bound without a changed or missing file. The
remaining blockers are unset token/monetary ceilings and unavailable isolated
agent and custody interfaces. The development-comparison gap is resolved;
reserved cases and answers remain unopened. Preparation and checking cost
0.187347 s and 0.077234 s respectively; the check's exit code 1 records the
expected not-ready result.

To freeze another exact public package after a relevant implementation change:

```sh
.venv/bin/python -m nisayon.engine.screen prepare \
  --development-ledger artifacts/development-ablation-001/comparison-ledger.json \
  --output artifacts/screen-package-NEXT.json
```

The package binds engine/evaluator sources, baseline and confirmation-service
hashes, installed dependency identities, policy bytes, predicates, equal
64-rollout/1,800-second/one-candidate diagnostic limits and 32-pair confirmation.
It names executable reservation, diagnosis, freeze, confirmation, ledger,
cost, recovery and final-check entry points. No case or answer is generated.
Without a completed ledger, a package can describe the current interface but
cannot claim completed development qualification.

`screen request-reserved --package PACKAGE --manifest MANIFEST --output REPORT`
currently returns an **unrun** result before reading the manifest. The actual
runtime lacks both restricted case custody and a matched isolated agent
provider. A package's contrary assertion cannot bypass those missing
capabilities. Agent token and monetary ceilings also remain unset until such
an interface can be measured. No false-ready manifest, separate branch or
hash substitutes for access separation. Fable's
[manifest checks](../evaluation/RESERVED_SCREEN.md) remain necessary record
checks after a real boundary exists.

For continuation after an interrupted comparison:

```sh
.venv/bin/python -m nisayon.engine.comparison_recovery \
  --root artifacts/development-ablation-001 \
  --output artifacts/development-ablation-001-recovery.json
```

This reads every assigned case/arm, verifies retained trial/decision bytes,
and inspects incomplete phase stores. Unknown outcomes and costs remain
unknown. It changes no record or reservation and does not resume physics.
Tests with labelled fixtures check the cross-arm freeze order, lossless
partial recovery, altered-decision rejection, reservation ownership, and
refusal to open even a named manifest before custody exists.

The remaining step for an actual reserved agent screen is concrete: supply
and qualify an external solver/custodian boundary, set equal measured
model/token/monetary budgets, then freeze a new package before independently
authored reserved cases are sealed and retrieved. Until then the reserved
twenty-case and total-cost target remain untested.
