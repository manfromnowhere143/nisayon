# Reuse observations when only scoring code changes

The check executor normally binds every handler into one shared procedure.
Changing a scoring source file therefore invalidates observations as well as
scores. `CheckImplementation` permits an explicit code input per handler, while
the SDK and shared dependencies remain common. Existing callers retain the
conservative behavior.

Every check must directly depend on its declared implementation input and
transitively depend on the shared procedure. Pass file paths only for the other
model inputs; the executor computes implementation inputs itself. A binding
automatically includes the handler's entire source file. Declare other source
dependencies in `files`, shared `implementation_files`, or explicit graph edges
to other bound implementation inputs. Handlers in the same file remain coupled.

```python
from nisayon.qualification import CheckImplementation, execute_checks

result = execute_checks(
    model,
    inputs=input_files,
    handlers=handlers,
    implementation_files=shared_dependencies,
    check_implementations={
        "observe": CheckImplementation(input_key="observe_code"),
        "score": CheckImplementation(input_key="score_code"),
        "confirm": CheckImplementation(input_key="confirm_code"),
    },
    evidence_root=evidence_root,
    output=evidence_root / "new-decision",
    previous=previous_state,
)
```

This is trusted, explicit dependency binding. It does not discover imports,
attest loaded Python state, support mutable closures or establish scientific
truth. A changed scorer cannot inherit its old verdict. A changed shared
dependency or SDK invalidates all affected evidence. Confirmation with
`refresh="always"` still executes; it does not become fresh physical evidence
merely because a handler ran again.

The runnable comparison uses the [already exposed camera matrix](../camera_slots/README.md).
Prepare that example's pinned sources and locked environment first. Then run:

```sh
uv run --frozen python examples/qualification/scoped_checks/run_example.py \
  --camera-root artifacts/camera-slot-qualification-2026-10-28 \
  --out artifacts/scoped-camera-checks
```

The output must be new. The script changes only copied scoring sources in that
output, comparing the configured-budget and all-configured-slot questions on
the same pinned PR #5129. It retains native attempts, fresh-process confirmation
at exposed seed 67, input/code bindings, original observations and four portable
check bundles. The ordinary camera reference already distinguishes these
contracts; neither repeated seed is an untouched robot condition.

The prospective expected counts are four native processes in conservative mode
versus three in scoped mode across the two questions, with identical decisions.
Both modes use the same SDK and dependency knowledge. This is an internal
invalidation comparison, not a comparison against a competent owner's native
workflow. Fixed execution order and one comparison do not support a timing
advantage estimate. Research, acquisition, implementation, human effort and
provider charges remain outside its complete-cost evidence.

`export_checks` and `inspect_check_bundle` retain their existing formats.
The built-in review reconstructs bindings and saved claims without executing
handlers; semantic outcomes still need their domain checker. This addition is
available from current source and does not change the tagged v0.2.0 wheel.
