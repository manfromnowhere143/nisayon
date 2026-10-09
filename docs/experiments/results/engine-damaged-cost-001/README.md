# Recovery with one damaged cost record

The actual recovery CLI preserves all twenty declarations and terminal records
when one attempt's cost JSON cannot be read. It reports one affected row and
one unknown attempt cost. The original claim and receipt remain unchanged.
This is a labelled corruption control on a copy of exposed development evidence,
not a scientific experiment or a new adjudication.

The control ran against clean source
`51ac4d451ac5679d7f53dd33588a9905526ead26`. The
[preparation script](prepare_control.py) copied
`artifacts/retained-declarations-002` to
`artifacts/engine-damaged-cost-001/packet-copy`, damaged one completion-cost file,
and verified all 283 original files remained unchanged. The
[control record](control.json) retains original and damaged digests. The
[recovery output](recovery.json) keeps the finding beside the original statement.

Recorded commands:

```sh
.venv/bin/nisayon run --label prepare-damaged-cost-copy-control --timeout 120 -- \
  .venv/bin/python artifacts/engine-damaged-cost-001/prepare_control.py
.venv/bin/nisayon run --label inspect-damaged-cost-copy-control --timeout 120 -- \
  .venv/bin/python -m nisayon.engine.retained_declarations \
  --inspect artifacts/engine-damaged-cost-001/packet-copy \
  --output artifacts/engine-damaged-cost-001/recovery.json
```

The exact commands, logs and source state are retained in command records
[`0428792a4607433fab0ee164646c4b72`](../engine-continuation-checks-001/0428792a4607433fab0ee164646c4b72/run.json)
and [`186a60c9e3dc46fb80f01002dd041d84`](../engine-continuation-checks-001/186a60c9e3dc46fb80f01002dd041d84/run.json).
Their outer walls are 0.210369 s and 0.208676 s. The twenty original workflow
cost histories remain nested evidence; they are not charged as fresh work.
No simulator execution or model call occurred.

Thirty-one focused writer, native confirmation, workflow and comparison-recovery
checks pass at the same clean source revision; record
[`1d2cf1659f5f41bdb7470fd82b859296`](../engine-continuation-checks-001/1d2cf1659f5f41bdb7470fd82b859296/run.json).
These checks cover malformed/non-object JSON and unsupported completion schema.
They do not resolve the separately retained evaluation-owned date fixture failure
or supply the missing prospective scoring semantics.
