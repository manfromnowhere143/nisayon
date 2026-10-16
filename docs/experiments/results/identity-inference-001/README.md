# Require complete evidence before inferring run identity

**15 October 2026 · N038 · local software correction; adoption unproved.**

Arisole Eval 0.1.5 can infer a run-wide task or suite from partially labelled
records. Its native comparison then reports 30 comparable pairs and its default
gate returns `REVIEW`/0. The missing labels have disappeared from the inference,
although they should prevent a claim of unanimous identity.

The [one-module patch](identity-coverage.patch) requires every original relevant
entry to supply the same nonblank string. It also reads original entries that
the parser could not turn into episodes. Explicit metadata and overrides retain
their precedence and attribution. Complete multi-task names remain supported,
with their provenance correctly named `eval_info.per_task[].task`.

## Executed result

| Check | Released 0.1.5 | Local correction |
|---|---|---|
| Identical final software controls | 34 pass, 22 fail | 56 pass, zero fail |
| Each of the 22 exposed incomplete-identity cases | `REVIEW`/0; 30 comparable records | `cannot_compare`, `BLOCK`/1; zero comparable records |
| Original sdist tests | 38 pass, zero skips | 38 pass, zero skips |
| Five native CLI evaluate/gate checks per probe run | Agree with library results | Agree with library results |

The 56 controls are 28 source-derived families in two entry orders. They cover
missing, null, blank, whitespace, conflicting and malformed identity, complete
inference, explicit declarations and seedless input. Each uses constructed
records; the 30 seed labels are not independent physical trials. This check
does not redesign pairing or validate the truth of an operator declaration.

The [protocol](PROTOCOL.md) was frozen before execution. The first run had
18 passes and 30 failures: ten failures came from my mistaken expectation that
positive cases should return `PASS`. Missing trajectory information correctly
makes them `REVIEW`. [Amendment v2](PROTOCOL-v2.md) corrects that expectation
without changing inputs; released behavior then passes 28/48.

The first correction passes all 48 controls. Further source inspection showed
that its single-task fallback would discard valid complete explicit multi-task
names. [Amendment v3](PROTOCOL-v3.md) adds eight controls before the final
candidate run. The final patch preserves that behavior. Both candidates, all
five probe runs, input hashes and original test logs remain retained. The first
and intermediate native test runs also retain a harmless cache-path warning;
the final run uses an absolute cache path and has no warning.

## Reproduction and retained bytes

[result.json](result.json) binds the wheel, sdist, environment, attempts, clocks
and limits. [raw.tar.gz](raw.tar.gz) retains all inputs/outputs, CLI logs, command
records and the published package archives; [raw-manifest.json](raw-manifest.json)
binds all 1,261 members. The three protocol freezes and three probe revisions
preserve the changes to the check. No earlier experiment packet was modified.

Read back every retained member and verify that the patch produces the executed
module, without installing a package or rerunning experiments:

```sh
python3 docs/experiments/results/identity-inference-001/verify.py
```

To repeat the native check, use a new disposable Python 3.12 environment with
[requirements.txt](requirements.txt), the retained 0.1.5 wheel and no Nisayon
runtime dependencies. Run [probe.py](probe.py) with that interpreter and a new
`--out` directory. The unchanged wheel should return exit 1 for its 22 failed
controls. Extract the wheel into a separate directory, apply
`patch --batch -p1 -i /absolute/path/to/identity-coverage.patch` there, and select
that directory with `PYTHONPATH`. The corrected probe should return exit 0.
The output records the actual imported module and its SHA-256.

For the original tests, unpack the retained sdist and run its `tests` directory
with the same interpreter, `-m pytest -q -c /dev/null --override-ini pythonpath=`
and an **absolute** `--override-ini cache_dir=...`. Use no `PYTHONPATH` for the
installed wheel, then the corrected directory for the candidate. Exact executed
commands and logs are in the archive. Preserve existing Nisayon environments.

## Cost and meaning

The final probes take 4.341 seconds for released behavior and 10.920 seconds for
the correction, including ten nested CLI subprocesses each. Their command
records take 4.885 and 11.679 seconds. These single diagnostic timings are not a
performance comparison. Native tests take 1.150 and 1.827 command seconds.
Earlier attempts remain charged separately in the result. Nested clocks must
not be added to their enclosing command clocks.

The isolated install reuses 13 pinned dependencies and the previously retained
wheel; the newly downloaded sdist is 69,113 bytes. Complete source acquisition,
human effort, agent charges, owner integration and maintenance are unmeasured.
Costs remain partial. There is no demonstrated saving.

This result supports rejecting inferred identity from the affected unpatched
path and using the local correction for these declared software cases. It
establishes no robot outcome, fresh confirmation, general statistical validity
or product advantage. No patch was sent and no release was made during N038.
The broader decision and owner dependency remain in the
[reassessment](../../../FRONTIER_DECISION_2026-10-14.md).

Arisole Eval is upstream work. Its source and package are retained under the
[Apache 2.0 license](UPSTREAM_LICENSE.txt); [upstream-meta.py.txt](upstream-meta.py.txt)
preserves the original module. The correction does not imply maintainer
endorsement or adoption.
