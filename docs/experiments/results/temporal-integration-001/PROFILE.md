# Temporal capture and read costs

The frozen 24-assignment profile completed on `a6fbe77eff8b7783287e9b2aca62b35e99c7456a`.
Capture and evidence verification dominate this small local path. These results
do not justify weakening verification or claiming a complete-workflow saving.

[Plan](profile-plan.v1.json), [all measurements](profile-001.json), driver
[`profile_temporal_workflow.py`](../../../../scripts/experiments/profile_temporal_workflow.py).
The command record is `e175e1739524426fa348d63b15a40424` (1.300895 s).
Raw captures and serialized inspections remain in
`artifacts/engine-integration-001/temporal-integration-001/profile-001/`.

Four exposed cases—healthy operation, overlapping chunks, a missing dispatch
acknowledgement and no response—each ran under the conventional and identical
selected remedy in three fixed passes. Each capture has a distinct attempt ID.
The first pass starts in a fresh process; it is not a cold filesystem-cache
measurement. Later passes reverse and then restore the remedy order. The
reference checker is the separately implemented version named in the record;
its pending semantic corrections limit interpretation of its verdicts.

| Phase | Total wall seconds | Total CPU seconds | Median wall seconds per assignment |
| --- | ---: | ---: | ---: |
| Capture, including seal | 0.507034 | 0.469689 | 0.018723 |
| Verify and inspect | 0.411394 | 0.410291 | 0.015307 |
| Separate reference | 0.001516 | 0.001518 | 0.000063 |
| Serialize inspection to bytes | 0.003024 | 0.003027 | 0.000107 |

The measured envelope is 1.164936 wall seconds and 1.112944 CPU seconds. Total
process CPU before writing the final profile record is 1.174928 seconds. That
includes imports and preparation, excludes child Git CPU, and spends part of
the original 600-second research allowance; the profile's 30-second allocation
does not reset that allowance. Phase costs are nested in the envelope and the
recorded command, so they must not be added again to the command ledger.

Retained bytes before the final record: 8,949,190, below the frozen 16 MiB cap.
Cumulative process high-water resident memory ranged from 29,786,112 to
35,176,448 bytes; it is not incremental memory per case. Serialized inspection
sizes ranged from 14,499 to 32,909 bytes. Virtual schedule time, scripted
test-double operations and actual CPU time remain separate quantities. Robot
task progress, learned inference, charges, energy and active engineering effort
are unmeasured. No new physical experiment or reserved allocation was used.

No optimization is adopted from this profile. It establishes the cost of this
named capture/read implementation on these inputs, with all repetitions and
outcomes retained. Future source changes require their own measurements before
any performance claim can be transferred to them.
