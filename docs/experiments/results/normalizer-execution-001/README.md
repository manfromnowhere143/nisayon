# normalizer-execution-001

This case makes one concrete preprocessing decision inspectable from pinned source and
configuration through executed float32 arrays, selected statistics, persistence and an
independent decision.

## Result

At NVIDIA/Isaac-GR00T revision
`1a1837f20538b7d7e21f977a11a5aee14f99803c`, `libero_sim` selects min/max
normalization for every retained state and action group. It selects neither mean/std nor
sin/cos encoding and has no relative-action override. The nested
`StateActionProcessor` owns the statistics used by the numerical operation. With
`override=False`, it keeps the constructor's parent statistics while the outer mirror
takes the later five-episode candidate; serialization writes the nested active values.
With `override=True`, the nested state takes the candidate.

The sealed `producer-004` executes the unchanged numerical utilities, complete nested
processor and exact outer selection/save/load methods through a documented model-free
constructor. It does not import or run the VLM, tokenizer, image pipeline, model,
policy, simulator or robot.

On 43 deterministic retained rows:

- keeping the shipped parent statistics is `supported`;
- replacing them with moments recomputed from the five exposed episodes is `rejected`
  because the effective map changes; and
- save/reload preserves the selected nested statistics and every output exactly.

The independent assessment reconstructs all real outputs and thirteen executed control
runs at 0 ULP. It reports 12 useful acceptances, no false acceptance or refusal and no
unjustified reuse or replacement. All 1,406 exposed rows lie within the parent min/max
ranges, while 539 coordinate values lie outside the parent q01/q99 ranges.

## Comparison and scope

The separately authored conventional float64 diagnostic reaches the same two real-case
decisions and every other control decision. It falsely accepts one constructed control,
NX5d: `std=1e-40` produces `-Infinity` in the executed float32 state path while the
float64 transcription remains finite. That is a scoped dtype-boundary diagnostic
advantage. It is not evidence that Nisayon obtains more valid, confirmed robot repairs.

Software correctness is supported for the retained reduced-execution boundary.
Deployment applicability is unresolved because no historical checkpoint statistics,
`override_pretraining_statistics` value or inference invocation was retained. No
normalizer defect or task-level correction is established, and robot-task outcome is
unmeasured.

For an engineer, the result provides an executable way to bind a proposed normalizer
change to the pinned configuration, active nested statistics, actual float32 arrays and
saved/reloaded state before accepting a keep or replacement. It also prevents a
float64-only transcription from hiding a non-finite deployed result.

## Next investment

Stop this metadata line. The next value experiment should be selected separately from
a non-reserved, observable policy-integration failure. Freeze a working deployment and
a changed deployment that differ only in normalizer/statistics selection; require the
candidate to change at least one task-relevant action; let Nisayon and a competent
conventional workflow choose independently from the same evidence; then run the full
policy/controller/environment path and fresh predeclared confirmation conditions. Stop
and return unresolved if the deployment selector cannot be bound, the candidate changes
no action, or the task outcome cannot be measured. Further metadata work is justified
only by a specific unresolved deployment decision it can change.

[Integrated readback](integration-readback-001.json),
[validation](validation-001.json), and
[independent assessment](../../../evaluation/results/normalizer-execution-001/assessment-readback-001.json).

