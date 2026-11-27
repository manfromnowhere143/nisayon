export type BrainRole = "baseline" | "candidate" | "privileged";
export interface BrainRow {
  tick: number; t_s: number; source_policy_line: number; after_truth_index: number;
  observation: null | { acquired_s: number; delivered_s: number; valid: boolean[]; joint_rad: number };
  estimate: null | { state_time_s: number; covariance_time_s: number; contact_reliable: boolean[]; pelvis_m: number[] };
  belief: { mode: string; calibrated_probabilities: false; scores: Record<string,number> | null };
  action: string; decision_time_s: number | null;
  controller: { status: string; ok: boolean; solve_wall_s: number | null; normalized_constraint_residual: number | null };
  guard: { mode: string; reasons: string[]; safe_stop_established: false; terminate_unqualified: boolean };
  issued_nm: number; applied_nm: number; applied_command_tick: number;
  after: { t_s: number; pelvis_m: number[]; torso_tilt_rad: number; tray_m: number[]; tray_supported: boolean; nonfoot_floor_contact: boolean };
}
export interface BrainTrace {
  role: BrainRole; episode: string; manifest_sha256: string; source_commit: string; model_sha256: string;
  projection_schema: "ricci.scientific-inspection.v1"; projection_sha256: string;
  artifacts: Record<string,string>; first_different_applied_s: number | null;
  outcome: { outcome: string; completed: boolean; fall: boolean; drop: boolean; protective_stop: boolean;
    constraint_violations: string[]; censored: boolean; scope: string; measurements: { duration_s: number; task_completion_s: number | null } };
  rows: BrainRow[];
}
export interface BrainInspection {
  schema: "nisayon.brain-inspection.v1"; scientific_contract: "ricci.scientific-inspection.v1"; effective_actuation_threshold_nm: .1; origin: "retained_simulation"; embodiment: string; case: string;
  control_period_s: .02; actuator: "right_knee_joint"; actuator_unit: "N m"; coordinate_frame: string;
  onset_s: number; comparison: string; replay: string; interpretation: string; traces: BrainTrace[];
}
function require(condition: unknown, reason: string): asserts condition { if (!condition) throw new Error(reason); }
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nullableNumber = (v: unknown) => v === null || finite(v);
const vector = (v: unknown) => Array.isArray(v) && v.length === 3 && v.every(finite);
const hash = (v: unknown) => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);

/** This is a bounded display reader. Source SHA verification precedes it;
 * the retained Brain 01 evaluator, never the frontend, owns outcomes. */
export function decodeBrainInspection(value: unknown): BrainInspection {
  require(!!value && typeof value === "object", "Missing Brain 01 evidence");
  const p = value as BrainInspection;
  require(p.schema === "nisayon.brain-inspection.v1" && p.origin === "retained_simulation"
    && p.control_period_s === .02 && p.actuator === "right_knee_joint" && p.actuator_unit === "N m"
    && finite(p.onset_s) && p.scientific_contract === "ricci.scientific-inspection.v1" && p.effective_actuation_threshold_nm === .1, "Unsupported scientific inspection contract");
  for (const key of ["embodiment","case","coordinate_frame","comparison","replay","interpretation"] as const)
    require(typeof p[key] === "string", "Missing interpretation boundary");
  require(Array.isArray(p.traces) && p.traces.length === 3, "Incomplete comparison");
  const roles = new Set<string>();
  for (const trace of p.traces) {
    require(["baseline","candidate","privileged"].includes(trace.role) && !roles.has(trace.role), "Duplicate or unsupported policy role"); roles.add(trace.role);
    require(trace.projection_schema === "ricci.scientific-inspection.v1" && hash(trace.projection_sha256), "Missing source-owned inspection identity");
    require(hash(trace.manifest_sha256) && hash(trace.model_sha256) && /^[a-f0-9]{40}$/.test(trace.source_commit), "Missing source identity");
    require(Array.isArray(trace.rows) && trace.rows.length > 0 && trace.rows.length <= 1000, "Scientific row budget exceeded");
    require(trace.outcome && typeof trace.outcome.outcome === "string" && typeof trace.outcome.scope === "string"
      && Array.isArray(trace.outcome.constraint_violations) && trace.outcome.constraint_violations.every(x=>typeof x === "string"), "Missing retained outcome");
    for (const key of ["completed","fall","drop","protective_stop","censored"] as const)
      require(typeof trace.outcome[key] === "boolean", "Unavailable outcome is not false");
    require(nullableNumber(trace.first_different_applied_s), "Missing action timing");
    for (let i=0; i<trace.rows.length; i++) {
      const r=trace.rows[i]!;
      require(r.source_policy_line === i+1 && r.after_truth_index === i+1, "Invalid original row binding");
      require(r.tick === i && finite(r.t_s) && Math.abs(r.t_s-i*.02)<1e-10, "Control clock discontinuity");
      require(r.applied_command_tick === i-1 && finite(r.issued_nm) && finite(r.applied_nm), "Unsupported actuation timing");
      if (i) require(r.applied_nm === trace.rows[i-1]!.issued_nm, "Applied command does not match delivery");
      require(r.after && finite(r.after.t_s) && Math.abs(r.after.t_s-r.t_s-.02)<1e-9
        && vector(r.after.pelvis_m) && vector(r.after.tray_m) && finite(r.after.torso_tilt_rad)
        && typeof r.after.tray_supported === "boolean" && typeof r.after.nonfoot_floor_contact === "boolean", "Invalid physical observation");
      if (r.observation !== null) {
        const o=r.observation;
        require(o && finite(o.acquired_s) && finite(o.delivered_s) && o.acquired_s>=0
          && o.acquired_s<=o.delivered_s && o.delivered_s<=r.t_s+1e-10 && finite(o.joint_rad)
          && Array.isArray(o.valid) && o.valid.length === 4 && o.valid.every(v=>typeof v === "boolean"), "Invalid sensor observation");
      }
      if (r.estimate !== null) require(r.estimate && finite(r.estimate.state_time_s) && finite(r.estimate.covariance_time_s)
        && vector(r.estimate.pelvis_m) && Array.isArray(r.estimate.contact_reliable)
        && r.estimate.contact_reliable.length === 2 && r.estimate.contact_reliable.every(v=>typeof v === "boolean"), "Invalid retained estimate");
      require(r.belief && typeof r.belief.mode === "string" && r.belief.calibrated_probabilities === false
        && (r.belief.scores === null || (typeof r.belief.scores === "object" && Object.values(r.belief.scores).every(finite))), "Compatibility scores are not probabilities");
      require(typeof r.action === "string" && nullableNumber(r.decision_time_s) && r.controller
        && typeof r.controller.status === "string" && typeof r.controller.ok === "boolean"
        && nullableNumber(r.controller.solve_wall_s) && nullableNumber(r.controller.normalized_constraint_residual), "Missing computational state");
      require(r.guard && r.guard.safe_stop_established === false && typeof r.guard.mode === "string"
        && typeof r.guard.terminate_unqualified === "boolean" && Array.isArray(r.guard.reasons)
        && r.guard.reasons.every(v=>typeof v === "string"), "Unsupported command admission");
    }
  }
  return p;
}

export function brainRow(trace: BrainTrace, index: number): BrainRow | null {
  // Ended executions remain unavailable. Never freeze the last pose over a
  // longer comparison trace and imply the failed robot kept operating.
  return Number.isInteger(index) && index >= 0 ? trace.rows[index] ?? null : null;
}
