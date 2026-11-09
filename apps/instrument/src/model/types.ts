// Internal model of one verified generation. The decoders are the only
// producers of these types; the rest of the instrument reads them.

export type RunKey = { bundle_sha256: string; run_id: string };
export type Phase = "before" | "after";
export type Depth = "moment" | "fork" | "conditions" | "decision";
export const DEPTHS: readonly Depth[] = ["moment", "fork", "conditions", "decision"];
export const PHASES: readonly Phase[] = ["before", "after"];

export interface Moment {
  generation_sha256: string;
  case_key: string;
  run: RunKey;
  row_index: number;
  phase: Phase;
  clock: "simulation";
}

export interface FileRef {
  path: string;
  sha256: string;
  byte_length: number;
  media_type: string | null;
  kind: string | null;
}

export interface CaseRef extends FileRef {
  case_key: string;
}

export interface SourceBinding {
  id?: string;
  canonical_json_sha256?: string | null;
  kind: string;
  path: string;
  sha256: string;
  byte_length: number | null;
  binding: string;
}

export interface Generation {
  sha256: string;
  manifestUrl: string;
  baseUrl: string;
  schema: string;
  label: string | null;
  adapter: Record<string, unknown>;
  experiment: { id: string; case_id: string; arm: string; stage: string };
  capabilities: Record<string, unknown>;
  source_bindings: SourceBinding[];
  bundle_sha256: string | null;
  cases: CaseRef[];
  files: FileRef[];
  residuals: Record<string, unknown> | null;
  limitations: string[];
}

export interface Predicates {
  min_cube_height_m: number;
  table_height_m: number | null;
  max_steps: number;
  control_period_s: number;
  max_observation_age_s: number;
  action_dimension: number;
  progress_minimum_gain_m: number;
  max_abs_executed_action: number | null;
  task: string | null;
  protocol_id: string | null;
  raw: Record<string, unknown>;
}

export interface CostEntry {
  category: string;
  value: number | null;
  unit: string | null;
  missing_reason: string | null;
}

export interface SourceRef {
  path: string;
  sha256: string;
  kind: string;
}

export interface RunRecord {
  plan?: Record<string, unknown> | null;
  run: RunKey;
  role: string;
  plan_id: string;
  stage: string | null;
  assignment_role: string | null;
  condition_id: string;
  seed: number | null;
  process_status: string;
  measurement_status: string;
  task_outcome: string;
  execution_mode: string;
  evidence_origin: string;
  candidate_sha256: string | null;
  configuration_sha256: string | null;
  reset_id: string | null;
  initial_state_sha256: string | null;
  started_at: string | null;
  ended_at: string | null;
  row_count: number;
  recording: { ends_at_row: number; last_next_sim_time_s: number | null };
  samples: FileRef;
  frames: FileRef | null;
  model: FileRef | null;
  sources: SourceRef[];
  source_locator?: { source_id: string; pointer: string };
  raw_source_id?: string | null;
  policy_reset: Record<string, unknown> | null;
  policy_state_reset: Record<string, unknown> | null;
  constraint_violations: unknown[];
  costs: CostEntry[];
  derivation_residuals: Record<string, unknown> | null;
  evaluator: Record<string, unknown> | null;
}

// The browser's own exact comparison of intended and executed actions.
export interface MismatchResult {
  row_index: number;
  step: number;
  component: number;
  intended: number;
  executed: number;
  action_sim_time_s: number;
}

// A descriptive finding published by the export. It never replaces a reason.
export interface ExportFinding {
  id: string | null;
  kind: string;
  code: string;
  definition: string;
  detail: string | null;
  run: RunKey;
  row_index: number | null;
  step: number | null;
  phase: Phase | null;
  threshold: number | null;
  component: number | null;
  intended: number | null;
  executed: number | null;
  action_sim_time_s: number | null;
  status: string | null;
}

export interface DecisionRef {
  path: string;
  sha256: string;
  byte_length: number;
  content: unknown;
  omitted_reason: string | null;
}

export interface CaseRecord {
  label: string | null;
  case_key: string;
  case_id: string;
  experiment_id: string;
  arm: string;
  stage: string;
  task: string | null;
  predicates: Predicates;
  deployments: Record<string, unknown>;
  plans: unknown[];
  runs: RunRecord[];
  alignment: Record<string, unknown>;
  comparison_alignment: string | null;
  findings: ExportFinding[];
  decisions: Record<string, DecisionRef | null>;
  decisionRefs: FileRef[];
  trial: Record<string, unknown> | null;
  confirmation: Record<string, unknown> | null;
  costs: Record<string, unknown> | null;
  telemetry_profile: string | null;
  qualification: Record<string, unknown> | null;
  limitations: string[];
}

export type MemoryState = "present" | "initialized_none" | "unavailable";

export interface PolicyFacts {
  availability: string;
  before: MemoryState;
  after: MemoryState;
  state_before_sha256: string | null;
  state_after_sha256: string | null;
  episode_reset: boolean | null;
  reset_before_inference: boolean;
  hidden_before_present: boolean;
  hidden_after_present: boolean;
  counter_before: number | null;
  counter_after: number | null;
}

export interface Observation {
  robot0_eef_pos: number[];
  robot0_eef_quat: number[];
  robot0_gripper_qpos: number[];
  cube_pos: number[];
  cube_quat: number[];
  gripper_to_cube_pos: number[];
}

export interface Acquisition {
  step: number;
  oldest_sim_time_s: number;
  components: { name: string; sequence: number; sim_time_s: number }[];
}

export interface SampleRow {
  row_index: number;
  step: number;
  observation_step: number | null;
  action_sim_time_s: number;
  next_sim_time_s: number;
  observation_sim_time_s: number | null;
  consumed_observation_capture_sim_time_s: number | null;
  observation_age_s: number | null;
  intended_action: number[];
  executed_action: number[];
  cube_height_m: number;
  task_success: boolean;
  inference_wall_host_s: number | null;
  policy: PolicyFacts;
  observation: Observation | null;
  captured_observation: Observation | null;
  consumed_acquisition: Acquisition | null;
  latest_acquisition: Acquisition | null;
  next_observation: Observation | null;
  digests: Record<string, string | null>;
  locators: Record<string, string | number | null>;
}

export interface Samples {
  run: RunKey;
  clock: string;
  rows: SampleRow[];
}

export interface FramePhase {
  physical?: PhysicalState | null;
  sim_time_s: number;
  xpos: Float64Array;
  xquat: Float64Array;
  sites: Float64Array;
  geoms: Float64Array;
  grip_site_xpos: [number, number, number];
  derived_cube_z_m: number | null;
  residual_cube_height_m: number | null;
  residual_eef_m: number | null;
  state_sha256: string | null;
}

export interface PhysicalState {
  qpos: number[];
  qvel: number[];
  ctrl: number[];
  goal_pos: [number, number, number] | null;
  goal_ori: number[][] | null;
}
export interface ModelJoint {
  id: number; name: string; body: number; type: "free" | "ball" | "slide" | "hinge";
  axis: [number, number, number]; qposAddress: number; dofAddress: number; range: [number, number] | null;
}
export interface ModelActuator {
  id: number; name: string; joint: number | null; kind: string; unit: string;
  controlRange: [number, number] | null; forceRange: [number, number] | null;
}

export interface FrameRow {
  row_index: number;
  step: number | null;
  before: FramePhase;
  after: FramePhase;
}

export interface Frames {
  run: RunKey;
  derivation: Record<string, unknown>;
  body_count: number;
  site_count: number;
  geom_count: number;
  maximum_residuals: Record<string, number>;
  rows: FrameRow[];
}

export interface ModelBody {
  index: number;
  name: string;
  parent: number;
}

export interface ModelSite {
  index: number;
  name: string;
  body: number;
}

export interface ModelGeom {
  index: number;
  name: string;
  body: number;
  type: string;
  size: [number, number, number];
  local_pos: [number, number, number] | null;
  local_quat: [number, number, number, number] | null;
}

export interface ModelRecord {
  joints?: ModelJoint[];
  actuators?: ModelActuator[];
  label: string | null;
  representation: string;
  bodies: ModelBody[];
  sites: ModelSite[];
  geoms: ModelGeom[];
  schematic: {
    links: [string, string, number][];
    joint_marks: string[];
    drawable_geoms: number[];
    floor_z_m: number;
  };
  meshes: Record<string, unknown>;
  counts: Record<string, number>;
  limitations: string[];
}

export function sameRun(a: RunKey, b: RunKey): boolean {
  return a.bundle_sha256 === b.bundle_sha256 && a.run_id === b.run_id;
}

export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 8) : "—";
}

export function bodyIndexByName(model: ModelRecord): Map<string, number> {
  return new Map(model.bodies.map((b) => [b.name, b.index]));
}

// Link strokes for the articulated schematic, from the body tree. Radii are
// drawing widths, not collision envelopes.
export function linkStrokesFromBodies(bodies: ModelBody[]): [string, string, number][] {
  const byIndex = new Map(bodies.map((b) => [b.index, b]));
  const strokes: [string, string, number][] = [];
  for (const body of bodies) {
    const parent = byIndex.get(body.parent);
    if (!parent || parent.index === body.index) continue;
    const child = body.name;
    if (!/^(robot0_link[1-7]|robot0_right_hand|gripper0_(right_gripper|leftfinger|rightfinger|finger_joint[12]_tip))$/.test(child)) continue;
    strokes.push([parent.name, child, strokeRadius(child)]);
  }
  return strokes;
}

export function strokeRadius(name: string): number {
  if (/robot0_link[12]$/.test(name)) return 0.05;
  if (/robot0_link[34]$/.test(name)) return 0.045;
  if (/robot0_link5$/.test(name)) return 0.04;
  if (/robot0_link6$/.test(name)) return 0.038;
  if (/robot0_link7$/.test(name)) return 0.034;
  if (name === "robot0_right_hand" || name === "gripper0_right_gripper") return 0.028;
  if (/finger_joint/.test(name)) return 0.008;
  return 0.012;
}

export const JOINT_MARK_NAMES = ["robot0_link1", "robot0_link2", "robot0_link3", "robot0_link4", "robot0_link5", "robot0_link6", "robot0_link7"];
