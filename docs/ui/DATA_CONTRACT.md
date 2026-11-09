# Instrument data contract

Version 1 · implementation contract for the two UI lanes

Phase one is static and recorded. A small generation is served by a local static
server. The browser has no execution credentials. The later live adapter serves the
same immutable objects and announces new generations; it does not change their meaning.

## Identity

```ts
type RunKey = { bundle_sha256: string; run_id: string };
type Moment = {
  generation_sha256: string;
  case_key: string;
  run: RunKey;
  row_index: number;
  phase: "before" | "after";
  clock: "simulation";
};
type Depth = "moment" | "fork" | "conditions" | "decision";
```

Run IDs are local to bundles. Row is a zero-based array locator, not a global time.
Explicitly preserve a source `step` that differs from array position. Prefix rows
keep their own run and coordinates. A comparison declares reset/time alignment and
maps each run to an actual row; no hidden interpolation or time stretching.

Depth, camera, panel layout and theme are view state. They do not change evidence.
The URL includes the pinned generation, case, full run key, row, phase and depth.
An invalid locator yields an explicit state; silently opening a different row is wrong.

## Files

`evidence.json` discovers the current approved generation. `integrity.json` records
the root manifest digest and byte length. These are static files initially, not
application endpoints. A generation manifest lists immutable content objects:

```text
manifest: schema, adapter, experiment identity, capabilities,
          source bindings, case object refs, file refs, limitations
file ref: path, sha256, byte_length, media_type, kind
case: case_key, case_id, experiment_id, arm, stage, predicates,
      run refs, decision refs, confirmation availability, findings
run: RunKey, role, process_status, measurement_status, task_outcome,
     sample ref, reconstruction ref, model ref, source refs
sample: row_index, step, action time, next-state time,
        consumed-observation time, original actions and readings,
        policy-state digests, reset event and availability
frame: row_index, phase, stored time, body/site/geom transforms,
       derivation identity, coordinate convention
```

The Codex lane owns the concrete JSON Schema and a checked real example. Publish the
first small example as the first integration commit, before broad exporter work.
Fable builds the shell and view state immediately and consumes that example when it
arrives. A labeled fixture may test loading/failure behavior; it cannot stand in for
the real scene or the completed milestone. Additive contract extensions are preferred;
both lanes must acknowledge breaking changes before either implements one.

Do not make a manifest contain its own byte digest. Use the manifest's exact bytes
as its content-addressed identity and pin that from discovery or a shared URL. Verify
that root before its children. Hash original fetched bytes before parsing; specify
whether a reference binds a compressed artifact or a decoded projection. Never hash
one serialization and display another while claiming byte identity.

Use bounded JSON/schema validation and explicit size limits. Reject malformed input,
non-finite numbers, duplicate identities, out-of-range locators, unknown required
schema versions and path traversal. Object paths stay within the generation's
allowlisted static origin. Digest knowledge is not authorization in a future private
deployment. The public projection excludes internal paths, secrets and reserved cases.

Expose generation G atomically once its required objects pass checks. Optional scene
assets can be unavailable without hiding a valid original reading. A new generation
never substitutes into an old inspector. Aborted loads cannot later overwrite a newer
selection. Digest checks establish byte integrity within the declared root of trust;
they do not independently attest the experiment or establish physical truth.

## Reconstruction

Use MuJoCo 3.2.7 for the initial export. Call `mj_kinematics` on admitted stored
`qpos` and any required recorded mocap state. There is no need for `mj_step`, policy
inference, contact reconstruction or new simulation. Validate dimensions, quaternion
conventions and model/source bindings before producing frames.

Keep world coordinates right-handed, Z-up, metres in the export. State quaternion
order (`wxyz`) and matrix layout explicitly. Convert once at the rendering boundary;
Three.js quaternion constructors use a different argument order. A reflected or
rotated robot is a failed data/rendering test even if it looks plausible.

For actual meshes, account for compiled mesh recentering, scaling and geometry-local
transforms. Prefer the pinned engine's compiled geometry plus its world transforms
over guessing how to attach a raw STL to a body origin. Bind every included asset's
bytes and redistribution terms. A link schematic using qualified frames is the
first fallback, with an explicit label and no claim about collision envelopes.

Retained configuration and cached original observations are separate series. The
D01 qualification found differences up to 0.558 mm in cube height and 0.499 mm in an
end-effector coordinate. Preserve both sources and the residual report. Do not widen
a tolerance after observing a disagreement or rewrite recorded `cube_height_m` from
new forward kinematics. The evaluator continues to own the original decision.

## Time and event findings

- Actions sit at `action_sim_time_s`; resulting stored state and original height
  sit at their respective recorded post-action times.
- Observation age uses the consumed observation's acquisition time, not the latest
  captured observation waiting in a queue.
- Host-monotonic duration stays on its own lane and invocation domain.
- First mismatch is a derived descriptive finding with its comparison definition,
  fields, threshold/tolerance and source locators. It is not automatic root cause.
- D01 first intended/executed gripper mismatch: step 0.
- D03 first age violation: step 1, 0.05 s against 1e-9 s; 0.10 s at step 2;
  approximately 0.15 s from step 3 in this retained diagnostic.

Findings do not replace evaluator reason codes. A finding without a sample locator
attaches to its condition or run, not to an invented timestamp.

## Memory

Carry initialization, availability, pre/post-state digest and reset events separately.
Before an initial inference, hidden state `None` with an observed initialization is
not D10's unavailable telemetry. Digest equality is exact byte equality for the
declared serialized state; inequality by itself neither explains nor condemns behavior.

Do not ship full recurrent tensors with the initial scene. A later frozen projection
must declare tensor slots, layer selection, flattening order, scaling, fit population,
method, transform digest and missingness. It cannot be called a confidence or causal
metric. A sample unavailable to the source remains unavailable in the picture.

## Status and decisions

Keep transport, publication, measurement and scientific decision distinct. Within a
case, also preserve trial status and task outcome. Concretely:

| Case | Required distinctions |
| --- | --- |
| D01 | Diagnostic correction completed; acceptance belongs to its separate confirmation decision |
| D03 | Task completed and timing obligation violated in the changed run |
| D05 | Confirmation rejected; condition 10423 progress gain 0.002936 m < 0.01 m |
| D06 | Trial unsupported / evaluator unresolved; not a failed supported intervention |
| D08 | Trial invalid, replay proposal rejected before execution / evaluator unresolved |
| D10 | Unavailable policy telemetry; valid reference and regression not established |

Import the reason's exact code, severity, detail and available locators. Do not rerun
acceptance logic in JavaScript. Public-friendly captions are derived from those
facts and expose the literal reason in inspection. Costs retain their parent/child
hierarchy and unknown categories. Do not add nested walls or treat missing cost as zero.

## Later live adapter

Read resources remain generation-addressed. A durable journal supplies event epoch,
sequence, deduplication, gap detection and snapshot recovery. Source freshness and
connection liveness are distinct. Sealed recorded runs arriving over a connection
are not per-step live robot telemetry.

Only a subsequent command slice introduces bounded typed requests, expected
generation/configuration, idempotency and worker-acknowledged cancellation. The
workspace MCP remains development infrastructure. The browser never receives an
arbitrary shell interface. The earlier API proposal is a reference for that phase,
updated to use bundle-scoped run identity; it is not the first slice's task list.
