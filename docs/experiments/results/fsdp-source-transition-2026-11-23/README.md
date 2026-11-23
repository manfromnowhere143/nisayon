# An ownership correction meets a changed FSDP loader

23 November 2026. A passing result for an old loader cannot qualify a newer
implementation with different managed-parameter, ignored-parameter and buffer
paths. This packet tests that boundary using the existing Accelerate #4447
ownership correction and real native CPU execution.

| Identity | Exact revision |
| --- | --- |
| Current upstream | `bd0703e3390ebb2b4eb1db5a0f1283f8edbc6091` |
| Previously published fork candidate | `8023c5ff621e07a3f8e8a25baf496de728f89e8e` |
| Closed PR's retained head metadata | `8c5efdca48fe03796171004c07a9c03461bfdbd2` |
| Local candidate file SHA-256 | `5d1d652939fbdb1f6c3b2bdf1aeef33f506049b35fe5b12510950d6db5e38bae` |

The [one-file candidate](../../../../work/experiments/fsdp-source-transition-2026-11-23/candidate.patch)
adds explicit optional consumption for an internally owned source dictionary,
clears it before actual assignment, and opts in at the owning preparation call.
The borrowed-source default and current distribution logic remain intact. The
proposed ownership contract does not authorize consuming arbitrary caller data.

## Native result and controls

Two local CPU/Gloo ranks executed the reviewed loader function with installed
Torch 2.11.0. Broadcast, DTensor distribution and `load_state_dict(assign=True)`
were real operations. The probe observed the dictionary at the actual assignment
boundary and used separate tensor arithmetic to check expected values.

| Run | Conditions per rank | Total rank observations | Outcome |
| --- | ---: | ---: | --- |
| Current base, development | 20 | 40 | 16 owned-source failures; all value checks pass |
| Candidate, development | 20 | 40 | All pass |
| Current base, fresh confirmation | 8 | 16 | 8 owned-source failures |
| Candidate, fresh confirmation | 8 | 16 | All pass |
| Clear only after assignment | 20 | 40 | 16 ownership failures, despite an empty final dictionary |
| Old published loader, mixed state | 1 | 2 | Native buffer errors; unresolved |

The probe/scorer and new confirmation shape/value offset were frozen before the
candidate. Controls cover borrowed inputs, target dtype, float/integer buffers,
managed/ignored state, uneven/empty shards and non-main input forms. These are
finite conditions, not independent deployments. Clearing one dictionary does
not prove that all shared storage has been released.

An initial IPv6 rendezvous attempt produced no rank observation and was stopped.
It remains unresolved in the record. Seven native invocations consumed 45.369
seconds including that 27.488-second failure. Completed runs took 2.76–3.16
seconds each. Resource sampling is a guard, not a comparative memory benchmark.

**Not run:** full `fsdp2_prepare_model`, CUDA offload/pinned transfers, GPU memory,
training, forward/backward/optimizer steps, Linux, hosted CI or an independent
owner trial. The older combined GPU RSS result does not apply to this candidate.
Only the reviewed function AST was executed; upstream package initialization,
remote scripts, checkpoints and builds were not run.

## Applicability receipt

The existing Nisayon dependency API and competent native manifest selector
produce the same prospective choices at equal source and evidence identities:

| Transition | Observation | Score | Confirmation | Review |
| --- | --- | --- | --- | --- |
| Unchanged source | Reuse | Reuse | Run | Run |
| Changed loader | Run | Run | Run | Run |
| Description-only change | Reuse | Reuse | Run | Run |

Unknown source stays unresolved; altered observation bytes require rechecks.
These are plans, not executed new decisions. Fresh confirmation is still
required. Planner and offline-reader timings do not establish reduced owner
work or human review time.

## Inspect without executing Torch

The public source contains an exact-byte evidence archive and its member hashes.
Choose a fresh extraction directory. From the repository root:

```sh
mkdir -p artifacts/fsdp-source-transition
tar -xzf work/experiments/fsdp-source-transition-2026-11-23/evidence.tar.gz \
  -C artifacts/fsdp-source-transition
python3 artifacts/fsdp-source-transition/verify.py
```

The [offline verifier](../../../../work/experiments/fsdp-source-transition-2026-11-23/verify.py)
checks frozen identities, exact Git blobs, producer digests and recomputed scores,
including missing-rank and wrong-source controls. It imports no Torch and runs
no native experiment. The [protocol](../../../../work/experiments/fsdp-source-transition-2026-11-23/protocol.json),
[result](../../../../work/experiments/fsdp-source-transition-2026-11-23/RESULTS.txt),
[source ledger](../../../../work/experiments/fsdp-source-transition-2026-11-23/SOURCES.json)
and [local PR description](../../../../work/experiments/fsdp-source-transition-2026-11-23/PR_DESCRIPTION.txt)
retain the full scope. The description has not been posted. Full integration is
the next gate for the existing PR, not a reason to open a duplicate.
