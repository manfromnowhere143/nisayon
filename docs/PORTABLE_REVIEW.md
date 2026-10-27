# Review a qualification without its native environment

An engineer can run a native check locally and pass its evidence to a reviewer
who has neither the owner project nor its robotics dependencies. The local SDK
now exports that store into one file and recomputes its assessment from a
private copy. It preserves failed and incomplete results as well as successful
software checks. The [qualification guide](NATIVE_QUALIFICATION.md) defines the
underlying experimental scope.

```sh
nisayon-qualify export /path/to/run --out /path/to/new-review.nisayon.zip
nisayon-qualify review /path/to/new-review.nisayon.zip
```

`export` returns exit 0 when it creates the file, including when the stored
experiment is invalid or incomplete. `review` returns 0 for software adoption,
1 for rejection and 3 for unresolved. Unreadable or invalid transport returns
2 with a diagnostic on stderr. Read the JSON result: container integrity,
agreement with the saved assessment and scientific acceptance are separate.

Both commands are local and read only with respect to the source store. They
do not execute native code, retrieve a model, contact a service or publish a
result. Packages contain original inputs, logs and absolute paths. Export does
not redact or anonymize them. A new output is required, outside the source
store; existing files are never replaced.

Upgrading the SDK changes its exact tool identity. Stored runs remain readable;
new execution requires a plan bound to the installed tool. The prior local
installation is retained for previously frozen plans.

The Python interface uses the same implementation:

```python
from nisayon.qualification import export_run, inspect_bundle

receipt = export_run("/path/to/run", "/path/to/new-review.nisayon.zip")
review = inspect_bundle(receipt["bundle"])
print(review["review_status"], review["software_decision"])
```

## What the reviewer receives

The versioned package is a deterministic, uncompressed ZIP with three kinds of
member. It preserves source-store files byte for byte.

| Member | Content |
| --- | --- |
| `bundle.json` | `nisayon.qualification.bundle.v1`, the canonical plan digest and exact file membership with raw SHA-256 and byte length |
| `assessment.json` | The exporter's saved assessment, including the implementation identity |
| `evidence/…` | Every file in the source store: plan, attempts, observations, logs, completion, manifest and seal when present |

The plan and raw records remain sufficient for the Python assessor. The reader
checks the transport index, rebuilds a private evidence directory, runs the
existing read-only assessment and compares every saved assessment field except
`assessment_tool`. Both implementation identities remain visible. Snapshot paths
in assessor-generated `invalid_evidence` diagnostics are normalized to
`evidence/`; original native records and error messages are unchanged.

The returned `nisayon.qualification.review.v1` record includes:

| Field | Meaning |
| --- | --- |
| `bundle_sha256`, `plan_sha256` | Identity of the exact file and declared plan |
| `integrity` | `verified` after bounded container and member checks; malformed transport raises an error instead |
| `review_status`, `assessment_agrees` | `verified`/true when saved and current assessment content agrees; otherwise `assessment_mismatch`/false |
| `assessor_identity_matches` | Whether saved and current implementation identities match; differing identities are preserved |
| `software_decision` | The current software decision when assessment content agrees; otherwise `unresolved` |
| `deployment_decision` | Remains `unresolved` in the current adapter |
| `recorded_assessment`, `assessment` | The saved record and the freshly recomputed record, including their own validity, scope, obligations and costs |

`review_status: verified` can describe an invalid or incomplete experiment.
It means the package accurately carries that result. A rewritten success label,
even with updated transport hashes, cannot override reassessment. Hashes do not
authenticate an author or establish that fabricated observations describe a
physical event. The original trusted-code, declared-dependency and oracle
premises still apply.

## Bounds and interrupted work

Version 1 accepts at most 4,096 ZIP members, 16 MiB per payload file, 64 MiB of
payload and a 1 MiB index. The archive read is capped at 68 MiB including ZIP
structure. Source scanning also caps files and directories together at 4,096
entries. Names use portable ASCII path components and reject traversal,
case aliases, reserved device names and file/directory collisions. Compression,
encryption, symlinks, special files, ZIP comments and hidden wrappers are not
supported by this transport version. These are explicit format bounds, not
general ZIP compatibility.

The writer copies a bounded snapshot, assesses the copy and checks another
source read for changes. The source must be quiescent; these checks are not a
transactional filesystem snapshot against a concurrent adversary. It then
publishes the complete archive with an exclusive same-filesystem hard link.
Interruption leaves an existing destination intact. A hard kill may leave a
temporary directory; it does not promote it to the requested output. Platform
qualification is limited to the recorded environment.

## Connect the instrument

The UI can open `bundle.json`, verify each member's bytes and read the case from
`evidence/plan.json`. Plan assignments identify the role, probe and attempt
directory. The assessment comparisons identify the first differing JSON path.
Open the corresponding request, observation and native call witnesses using
those assignments. The [qualification guide](NATIVE_QUALIFICATION.md) describes the underlying
case, plan and assessment fields.

Browser display of `assessment.json` must identify it as a saved assessment.
Only a Python `review` recomputes this contract. Preserve original numeric bytes
for inspection; ordinary JavaScript number conversion can erase distinctions
between large integers or signed zero. Keep annotations and layout outside the
sealed evidence. Treat imported values and logs as text, never active code.

The UI application, its import adapter and device/browser acceptance remain
separately owned. There is no new HTTP server or native execution service.
The [implementation record](experiments/results/native-sdk-2026-10-23/README.md)
describes the checked scope and retained limitations.

## Executable check records

Current source adds `export-checks EXECUTION --evidence-root ROOT --out FILE`
and `review-check-bundle FILE` for reviewed dependency models and check outputs.
The export includes the required prior evidence and frozen inputs; review
reconstructs their relationships without running native handlers. The exact
SDK source and distribution identity remain part of the contract. A completed
check may report a rejected or unresolved relation.

`review-native-task FILE` adds semantic reassessment of the included original
N100-format task records. A consistent task comparison leaves measurement
adequacy and deployment authority unresolved. See the
[native task guide](NATIVE_TASK_OUTCOMES.md) and
[executable examples](../examples/qualification/executable_checks/README.md).
These commands require current source, not the tagged v0.2.0 wheel. Retained
paths and logs are not automatically redacted; inspect a package before sharing.
