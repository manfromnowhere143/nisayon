# Changed normalization data behind unchanged code

24 October 2026. A constructed native experiment exposed a limit in Nisayon's
declared dependency premise. With OpenPI's statistics JSON deliberately omitted,
the old SDK adopted the original software result and still reported its evidence
applicable after only that data changed. Fresh execution rejected the changed
result. This is a Nisayon completeness counterexample, not an OpenPI defect.

New plans require a bounded CPython witness of owner-file read attempts during
import and execution. An observed undeclared read prevents acceptance. Declaring
the statistics explicitly permits the valid result; changing their bytes makes
old evidence inapplicable. The current implementation confirms those outcomes
on both initial and fresh, exposed numerical inputs.

## Evidence

| SDK and declaration | Original result | Reuse after data changes | Fresh execution with changed data |
| --- | --- | --- | --- |
| Previous SDK, data omitted | Adopt | Applicable under the incomplete declaration | Reject |
| New SDK, data omitted; initial inputs | Unresolved | Unresolved | Unresolved |
| New SDK, data declared; initial inputs | Adopt | Inapplicable | Reject |
| New SDK, data omitted; fresh inputs | Unresolved | Unresolved | Unresolved |
| New SDK, data declared; fresh inputs | Adopt | Inapplicable | Reject |

The final implementation executed 24 native calls: four configurations, two
data states and three roles. Six calls establish the previous-SDK counterexample.
Each reference has an independent fixed numerical oracle; the deliberate control
reverses the first normalized value. The wrapper calls the real, unmodified
OpenPI loader. It does not execute an upstream robot policy or training system.
Every deployment decision remains unresolved.

The host was macOS 14.4 Apple Silicon, CPython 3.12.13. The minimal native
environment pins NumPy 1.26.4, numpydantic 1.6.9 and Pydantic 2.11.5 from the
upstream lock, with separately hash-locked transitive dependencies. OpenPI is
pinned to `215abfb217dbac7d5f1273282331b9b1866c0479`. The old SDK's 14 relevant
source files match public commit `54a45573389931254e5ad6b39cc1956072b94043`
byte-for-byte. [Source identities](source-identities.json) bind the final SDK
and probe; [the matrix](result.json) gives machine-readable outcomes.

The [prospective local protocol](PROTOCOL.md) preceded implementation. It was
not externally preregistered. Selection and both input sets were exposed to the
implementer; this is neither an independently selected incident nor untouched
reuse. The [research review](RESEARCH.md) explains the choice and its limits.

## Checks and retained failures

All **191 qualification regression tests** pass, including 26 new read-witness
controls. They exercise import-time and call-time reads, failed read attempts,
declared-data changes, write-only opens, descriptors, directory-relative opens,
aliases, another thread, registration refusal, event/path limits, altered
records, historical evidence and portable review. A missing or inconsistent
witness cannot supply acceptance for a new plan, even after an ordinary reseal.
Integrity checks still do not authenticate a wholesale rewritten store.

An additional adversarial check exposed a real defect in the first observer:
metadata collection could import an owner `platform.py` before observation
started. Its undeclared calibration read escaped the witness and the prototype
adopted the result. The correction takes library roots from the already frozen
plan, binds them into the request and starts observation before owner import.
The same case now records the omitted input and returns unresolved. The
[before](metadata-import/before/assessment.json),
[after](metadata-import/after/assessment.json), exact owner-source snapshots and
[patch restoring the failed prototype](restore-failed-prototype.patch) retain
the counterexample. The original metadata control had three native calls; the
corrected control adds three. These are separate from the 24-call final matrix.

The earlier 190-test focused suite and 1,516-pass local full suite had not exposed
that import boundary. Their logs are retained as pre-correction checks. The
191-test focused suite and the entire native matrix were rerun after correction;
the final implementation identity is recorded separately from the prototype.

The first test collection failed because the sparse checkout omitted two
existing example packages. After restoring them, two CLI tests exposed a test
invocation error: a relative `PYTHONPATH` selected the older installed SDK after
changing directories. An absolute source path corrected the invocation. Both
failures, the intermediate controls and the final suite are retained under
[commands](commands/). They are included in recorded command costs. The native
counterexample and final confirmation did not require altering the probes.

The [sealed run stores](runs/) retain plans, intents, observations, attempt costs,
manifests and seals. Inspection is read-only and needs no owner project or native
loader environment:

```sh
nisayon-qualify inspect docs/experiments/results/owner-read-witness-2026-10-24/runs/declared-fresh/original
nisayon-qualify inspect docs/experiments/results/owner-read-witness-2026-10-24/runs/omitted-fresh/original
```

The [runnable example](../../../../examples/qualification/owner_reads/README.md)
creates new owner copies and reproduces the declared/omitted controls. Historical
v1 evidence remains readable under its earlier scope; new v2 plans require the
read policy. See the [SDK migration and coverage](../../../NATIVE_QUALIFICATION.md).

[Portable review of the new native result](portable-review.json) verifies
integrity, assessment agreement and the required read policy. An
[actual historical v1 bundle](legacy-bundle-review.json) remains readable but
reports `assessment_mismatch` and an unresolved review decision because the
current assessment makes its premises and read scope explicit. Both assessments
are preserved. Inspecting its raw store still yields the original scoped result;
the reader does not silently promote the old bundle to new coverage.

## Boundary and next decision

The witness observes CPython `open` attempts, not bytes consumed or all program
dependencies. Reads outside the owner directory, native C I/O, environment
variables, remote state, child processes, device state and background activity
after the call remain outside its coverage. Before/after hashes do not prove an
atomic snapshot. Trusted native code, stable inputs and dependency completeness
remain premises. This is not a security sandbox or physical acceptance test.

Recorded command time includes retained setup, retries and native runs; it is
not complete engineering cost. The [cost record](costs.json) retains 22 command
durations and leaves unmeasured components unknown. Concurrent times overlap; attempt times
are nested within runner and command times. Human preparation/review, historical
research, provider charges and unrecorded operations remain unknown. The twofold
complete-cost target is unproven. The next value experiment still needs a live
owner decision, matched competent workflow, measured setup and review effort,
and a separately selected untouched reuse case.
