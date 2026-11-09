// Bounded validation of fetched JSON into the internal model. Every decoder
// rejects malformed input, non-finite numbers, duplicate identities, unknown
// required schema versions and paths that leave the generation root.

import { quatMultiply, quatRotate, type Quat, type Vec3 } from "./pose";
import {
  JOINT_MARK_NAMES,
  type CaseRecord,
  type CaseRef,
  type CostEntry,
  type DecisionRef,
  type ExportFinding,
  type FileRef,
  type FramePhase,
  type Frames,
  type Generation,
  type ModelGeom,
  type ModelRecord,
  type Observation,
  type PolicyFacts,
  type Predicates,
  type RunKey,
  type RunRecord,
  type SampleRow,
  type Samples,
  type SourceBinding,
  type SourceRef,
} from "./types";

export class DecodeError extends Error {
  readonly path: string;
  constructor(path: string, message: string) {
    super(`${path}: ${message}`);
    this.name = "DecodeError";
    this.path = path;
  }
}

export class UnsupportedSchemaError extends DecodeError {
  readonly schema: string;
  readonly supported: readonly string[];
  constructor(path: string, schema: string, supported: readonly string[]) {
    super(path, `unsupported schema "${schema}"; this instrument reads ${supported.join(", ")}`);
    this.name = "UnsupportedSchemaError";
    this.schema = schema;
    this.supported = supported;
  }
}

export const SUPPORTED = {
  evidence: ["nisayon.ui.evidence.v1"],
  generation: ["nisayon.ui.dev-generation.v1"],
  case: ["nisayon.ui.dev-case.v1"],
  samples: ["nisayon.ui.dev-samples.v1"],
  frames: ["nisayon.ui.dev-frames.v1"],
  model: ["nisayon.ui.dev-model.v1"],
} as const;

export const LIMITS = {
  rows: 100_000,
  bodies: 512,
  files: 4096,
  cases: 256,
  runs: 256,
  actionDimension: 64,
  findings: 256,
  stringLength: 8192,
  list: 100_000,
} as const;

export const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

export function rec(v: unknown, path: string): Record<string, unknown> {
  if (!isRecord(v)) throw new DecodeError(path, "expected an object");
  return v;
}

export function optRec(v: unknown, path: string): Record<string, unknown> | null {
  if (v === undefined || v === null) return null;
  return rec(v, path);
}

export function str(v: unknown, path: string): string {
  if (typeof v !== "string") throw new DecodeError(path, "expected a string");
  if (v.length > LIMITS.stringLength) throw new DecodeError(path, "string exceeds the length bound");
  return v;
}

export function optStr(v: unknown, path: string): string | null {
  if (v === undefined || v === null) return null;
  return str(v, path);
}

export function bool(v: unknown, path: string): boolean {
  if (typeof v !== "boolean") throw new DecodeError(path, "expected a boolean");
  return v;
}

export function num(v: unknown, path: string): number {
  if (typeof v !== "number" || !Number.isFinite(v)) throw new DecodeError(path, "expected a finite number");
  return v;
}

export function optNum(v: unknown, path: string): number | null {
  if (v === undefined || v === null) return null;
  return num(v, path);
}

export function int(v: unknown, path: string, min = 0): number {
  const n = num(v, path);
  if (!Number.isSafeInteger(n) || n < min) throw new DecodeError(path, `expected a safe integer ≥ ${min}`);
  return n;
}

export function optInt(v: unknown, path: string, min = 0): number | null {
  if (v === undefined || v === null) return null;
  return int(v, path, min);
}

export function arr(v: unknown, path: string, max: number): unknown[] {
  if (!Array.isArray(v)) throw new DecodeError(path, "expected an array");
  if (v.length > max) throw new DecodeError(path, `more than ${max} entries`);
  return v;
}

export function numArr(v: unknown, path: string, length?: number): number[] {
  const a = arr(v, path, LIMITS.list);
  if (length !== undefined && a.length !== length) {
    throw new DecodeError(path, `expected ${length} numbers, found ${a.length}`);
  }
  return a.map((x, i) => num(x, `${path}[${i}]`));
}

export function vec3(v: unknown, path: string): [number, number, number] {
  const a = numArr(v, path, 3);
  return [a[0] as number, a[1] as number, a[2] as number];
}

export function vec4(v: unknown, path: string): [number, number, number, number] {
  const a = numArr(v, path, 4);
  return [a[0] as number, a[1] as number, a[2] as number, a[3] as number];
}

export function strArr(v: unknown, path: string, max: number = LIMITS.list): string[] {
  return arr(v, path, max).map((x, i) => str(x, `${path}[${i}]`));
}

const SHA = /^[0-9a-f]{64}$/;

export function sha(v: unknown, path: string): string {
  const s = str(v, path);
  if (!SHA.test(s)) throw new DecodeError(path, "expected a lowercase hex SHA-256");
  return s;
}

export function optSha(v: unknown, path: string): string | null {
  if (v === undefined || v === null) return null;
  return sha(v, path);
}

export function isSha256(v: string): boolean {
  return SHA.test(v);
}

// A path inside a generation: relative, no scheme, no traversal, no empty
// segments, no encoded traversal.
export function relativePath(v: unknown, path: string): string {
  const s = str(v, path);
  if (s.length === 0) throw new DecodeError(path, "empty path");
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(s) || s.startsWith("/") || s.includes("\\")) {
    throw new DecodeError(path, "must be a relative path within the generation");
  }
  let decoded: string;
  try {
    decoded = decodeURIComponent(s);
  } catch {
    throw new DecodeError(path, "malformed percent-encoding");
  }
  for (const segment of decoded.split("/")) {
    if (segment === "" || segment === "." || segment === "..") {
      throw new DecodeError(path, "path segments must be plain names");
    }
  }
  return s;
}

export function isSafeRelativePath(s: string): boolean {
  try {
    relativePath(s, "path");
    return true;
  } catch {
    return false;
  }
}

export function schemaOf(v: unknown, path: string, supported: readonly string[]): string {
  const s = str(v, path);
  if (!supported.includes(s)) throw new UnsupportedSchemaError(path, s, supported);
  return s;
}

export function fileRef(v: unknown, path: string): FileRef {
  const o = rec(v, path);
  return {
    path: relativePath(o.path, `${path}.path`),
    sha256: sha(o.sha256, `${path}.sha256`),
    byte_length: int(o.byte_length, `${path}.byte_length`),
    media_type: optStr(o.media_type, `${path}.media_type`),
    kind: optStr(o.kind, `${path}.kind`),
  };
}

export function optFileRef(v: unknown, path: string): FileRef | null {
  if (v === undefined || v === null) return null;
  return fileRef(v, path);
}

export function runKey(v: unknown, path: string): RunKey {
  const o = rec(v, path);
  return { bundle_sha256: sha(o.bundle_sha256, `${path}.bundle_sha256`), run_id: str(o.run_id, `${path}.run_id`) };
}

export interface Evidence {
  schema: string;
  label: string | null;
  current: { generation_sha256: string; manifest_path: string; byte_length: number };
}

export function decodeEvidence(json: unknown): Evidence {
  const o = rec(json, "evidence");
  const schema = schemaOf(o.schema, "evidence.schema", SUPPORTED.evidence);
  const current = rec(o.current, "evidence.current");
  return {
    schema,
    label: optStr(o.label, "evidence.label"),
    current: {
      generation_sha256: sha(current.generation_sha256, "evidence.current.generation_sha256"),
      manifest_path: relativePath(current.manifest_path, "evidence.current.manifest_path"),
      byte_length: int(current.byte_length, "evidence.current.byte_length", 1),
    },
  };
}

function sourceBinding(v: unknown, path: string): SourceBinding {
  const o = rec(v, path);
  return {
    kind: str(o.kind, `${path}.kind`),
    path: str(o.path, `${path}.path`),
    sha256: sha(o.sha256, `${path}.sha256`),
    byte_length: optInt(o.byte_length, `${path}.byte_length`),
    binding: str(o.binding, `${path}.binding`),
  };
}

export function decodeManifest(json: unknown, sha256: string, manifestUrl: string): Generation {
  const o = rec(json, "manifest");
  const schema = schemaOf(o.schema, "manifest.schema", SUPPORTED.generation);
  const experiment = rec(o.experiment, "manifest.experiment");
  const files = arr(o.files, "manifest.files", LIMITS.files).map((f, i) => fileRef(f, `manifest.files[${i}]`));
  const seenPaths = new Set<string>();
  for (const f of files) {
    if (seenPaths.has(f.path)) throw new DecodeError("manifest.files", `duplicate path "${f.path}"`);
    seenPaths.add(f.path);
  }
  const cases: CaseRef[] = arr(o.cases, "manifest.cases", LIMITS.cases).map((c, i) => {
    const path = `manifest.cases[${i}]`;
    const ref = fileRef(c, path);
    return { ...ref, case_key: str(rec(c, path).case_key, `${path}.case_key`) };
  });
  const seenCases = new Set<string>();
  for (const c of cases) {
    if (seenCases.has(c.case_key)) throw new DecodeError("manifest.cases", `duplicate case_key "${c.case_key}"`);
    seenCases.add(c.case_key);
  }
  if (cases.length === 0) throw new DecodeError("manifest.cases", "a generation needs at least one case");
  const slash = manifestUrl.lastIndexOf("/");
  return {
    sha256,
    manifestUrl,
    baseUrl: slash >= 0 ? manifestUrl.slice(0, slash + 1) : manifestUrl,
    schema,
    label: optStr(o.label, "manifest.label"),
    adapter: rec(o.adapter, "manifest.adapter"),
    experiment: {
      id: str(experiment.id, "manifest.experiment.id"),
      case_id: str(experiment.case_id, "manifest.experiment.case_id"),
      arm: str(experiment.arm, "manifest.experiment.arm"),
      stage: str(experiment.stage, "manifest.experiment.stage"),
    },
    capabilities: rec(o.capabilities, "manifest.capabilities"),
    source_bindings: arr(o.source_bindings, "manifest.source_bindings", LIMITS.files).map((b, i) =>
      sourceBinding(b, `manifest.source_bindings[${i}]`),
    ),
    bundle_sha256: optSha(o.bundle_sha256, "manifest.bundle_sha256"),
    cases,
    files,
    residuals: optRec(o.residuals, "manifest.residuals"),
    limitations: strArr(o.limitations, "manifest.limitations", 256),
  };
}

export function predicates(v: unknown, path: string): Predicates {
  const o = rec(v, path);
  const action_dimension = int(o.action_dimension, `${path}.action_dimension`, 1);
  if (action_dimension > LIMITS.actionDimension) throw new DecodeError(`${path}.action_dimension`, "exceeds the bound");
  return {
    min_cube_height_m: num(o.min_cube_height_m, `${path}.min_cube_height_m`),
    table_height_m: optNum(o.table_height_m, `${path}.table_height_m`),
    max_steps: int(o.max_steps, `${path}.max_steps`, 1),
    control_period_s: num(o.control_period_s, `${path}.control_period_s`),
    max_observation_age_s: num(o.max_observation_age_s, `${path}.max_observation_age_s`),
    action_dimension,
    progress_minimum_gain_m: num(o.progress_minimum_gain_m, `${path}.progress_minimum_gain_m`),
    max_abs_executed_action: optNum(o.max_abs_executed_action, `${path}.max_abs_executed_action`),
    task: optStr(o.task, `${path}.task`),
    protocol_id: optStr(o.protocol_id, `${path}.protocol_id`),
    raw: o,
  };
}

export function costEntry(v: unknown, path: string): CostEntry {
  const o = rec(v, path);
  return {
    category: str(o.category, `${path}.category`),
    value: optNum(o.value, `${path}.value`),
    unit: optStr(o.unit, `${path}.unit`),
    missing_reason: optStr(o.missing_reason, `${path}.missing_reason`),
  };
}

function sourceRef(v: unknown, path: string): SourceRef {
  const o = rec(v, path);
  return { path: str(o.path, `${path}.path`), sha256: sha(o.sha256, `${path}.sha256`), kind: str(o.kind, `${path}.kind`) };
}

function runRecord(v: unknown, path: string): RunRecord {
  const o = rec(v, path);
  const row_count = int(o.row_count, `${path}.row_count`, 1);
  if (row_count > LIMITS.rows) throw new DecodeError(`${path}.row_count`, "exceeds the row bound");
  const recording = rec(o.recording, `${path}.recording`);
  const ends_at_row = int(recording.ends_at_row, `${path}.recording.ends_at_row`);
  if (ends_at_row !== row_count - 1) {
    throw new DecodeError(`${path}.recording.ends_at_row`, `must equal row_count - 1 (${row_count - 1})`);
  }
  return {
    run: runKey(o.run, `${path}.run`),
    role: str(o.role, `${path}.role`),
    plan_id: str(o.plan_id, `${path}.plan_id`),
    assignment_role: optStr(o.assignment_role, `${path}.assignment_role`),
    condition_id: str(o.condition_id, `${path}.condition_id`),
    seed: optInt(o.seed, `${path}.seed`, Number.MIN_SAFE_INTEGER),
    process_status: str(o.process_status, `${path}.process_status`),
    measurement_status: str(o.measurement_status, `${path}.measurement_status`),
    task_outcome: str(o.task_outcome, `${path}.task_outcome`),
    execution_mode: str(o.execution_mode, `${path}.execution_mode`),
    evidence_origin: str(o.evidence_origin, `${path}.evidence_origin`),
    candidate_sha256: optSha(o.candidate_sha256, `${path}.candidate_sha256`),
    configuration_sha256: optSha(o.configuration_sha256, `${path}.configuration_sha256`),
    reset_id: optStr(o.reset_id, `${path}.reset_id`),
    initial_state_sha256: optSha(o.initial_state_sha256, `${path}.initial_state_sha256`),
    started_at: optStr(o.started_at, `${path}.started_at`),
    ended_at: optStr(o.ended_at, `${path}.ended_at`),
    row_count,
    stage: null,
    recording: { ends_at_row, last_next_sim_time_s: num(recording.last_next_sim_time_s, `${path}.recording.last_next_sim_time_s`) },
    samples: fileRef(o.samples, `${path}.samples`),
    frames: optFileRef(o.frames, `${path}.frames`),
    model: optFileRef(o.model, `${path}.model`),
    sources: arr(o.sources ?? [], `${path}.sources`, 64).map((s, i) => sourceRef(s, `${path}.sources[${i}]`)),
    policy_reset: optRec(o.policy_reset, `${path}.policy_reset`),
    policy_state_reset: optRec(o.policy_state_reset, `${path}.policy_state_reset`),
    constraint_violations: arr(o.constraint_violations ?? [], `${path}.constraint_violations`, 4096),
    costs: arr(o.costs ?? [], `${path}.costs`, 4096).map((c, i) => costEntry(c, `${path}.costs[${i}]`)),
    derivation_residuals: optRec(o.derivation_residuals, `${path}.derivation_residuals`),
    evaluator: null,
  };
}

export function finding(v: unknown, path: string): ExportFinding | null {
  const o = rec(v, path);
  const kind = str(o.kind, `${path}.kind`);
  if (kind !== "first_action_mismatch") return null;
  const result = o.result === null || o.result === undefined ? null : rec(o.result, `${path}.result`);
  return {
    id: null,
    kind,
    code: kind,
    definition: str(o.definition, `${path}.definition`),
    detail: null,
    run: runKey(o.run, `${path}.run`),
    status: str(o.status, `${path}.status`),
    row_index: result ? int(result.row_index, `${path}.result.row_index`) : null,
    step: result ? int(result.step, `${path}.result.step`) : null,
    phase: null,
    threshold: 0,
    component: result ? int(result.component, `${path}.result.component`) : null,
    intended: result ? num(result.intended, `${path}.result.intended`) : null,
    executed: result ? num(result.executed, `${path}.result.executed`) : null,
    action_sim_time_s: result ? num(result.action_sim_time_s, `${path}.result.action_sim_time_s`) : null,
  };
}

export function decisionRef(v: unknown, path: string): DecisionRef | null {
  if (v === null || v === undefined) return null;
  const o = rec(v, path);
  return {
    path: str(o.path, `${path}.path`),
    sha256: sha(o.sha256, `${path}.sha256`),
    byte_length: int(o.byte_length, `${path}.byte_length`),
    content: o.content ?? null,
    omitted_reason: optStr(o.omitted_reason, `${path}.omitted_reason`),
  };
}

export function decodeCase(json: unknown): CaseRecord {
  const o = rec(json, "case");
  schemaOf(o.schema, "case.schema", SUPPORTED.case);
  const runs = arr(o.runs, "case.runs", LIMITS.runs).map((r, i) => runRecord(r, `case.runs[${i}]`));
  const seen = new Set<string>();
  for (const r of runs) {
    const key = `${r.run.bundle_sha256}:${r.run.run_id}`;
    if (seen.has(key)) throw new DecodeError("case.runs", `duplicate run identity ${r.run.run_id} in bundle ${r.run.bundle_sha256.slice(0, 8)}`);
    seen.add(key);
  }
  if (runs.length === 0) throw new DecodeError("case.runs", "a case needs at least one run");
  const decisionsRaw = optRec(o.decisions, "case.decisions") ?? {};
  const decisions: Record<string, DecisionRef | null> = {};
  for (const [k, v] of Object.entries(decisionsRaw)) decisions[k] = decisionRef(v, `case.decisions.${k}`);
  const findings = arr(o.findings ?? [], "case.findings", LIMITS.findings)
    .map((f, i) => finding(f, `case.findings[${i}]`))
    .filter((f): f is ExportFinding => f !== null);
  return {
    label: optStr(o.label, "case.label"),
    case_key: str(o.case_key, "case.case_key"),
    case_id: str(o.case_id, "case.case_id"),
    experiment_id: str(o.experiment_id, "case.experiment_id"),
    arm: str(o.arm, "case.arm"),
    stage: str(o.stage, "case.stage"),
    task: optStr(o.task, "case.task"),
    predicates: predicates(o.predicates, "case.predicates"),
    deployments: optRec(o.deployments, "case.deployments") ?? {},
    plans: arr(o.plans ?? [], "case.plans", 256),
    runs,
    alignment: optRec(o.alignment, "case.alignment") ?? {},
    comparison_alignment: typeof (optRec(o.alignment, "case.alignment") ?? {}).declared === "string" ? String((optRec(o.alignment, "case.alignment") ?? {}).declared) : null,
    findings,
    decisions,
    decisionRefs: [],
    trial: null,
    confirmation: optRec(o.confirmation, "case.confirmation"),
    costs: optRec(o.costs, "case.costs"),
    telemetry_profile: optStr(o.telemetry_profile, "case.telemetry_profile"),
    qualification: optRec(o.qualification, "case.qualification"),
    limitations: [],
  };
}

function observation(v: unknown, path: string): Observation | null {
  if (v === null || v === undefined) return null;
  const o = rec(v, path);
  return {
    robot0_eef_pos: numArr(o.robot0_eef_pos, `${path}.robot0_eef_pos`, 3),
    robot0_eef_quat: numArr(o.robot0_eef_quat, `${path}.robot0_eef_quat`, 4),
    robot0_gripper_qpos: numArr(o.robot0_gripper_qpos, `${path}.robot0_gripper_qpos`, 2),
    cube_pos: numArr(o.cube_pos, `${path}.cube_pos`, 3),
    cube_quat: numArr(o.cube_quat, `${path}.cube_quat`, 4),
    gripper_to_cube_pos: numArr(o.gripper_to_cube_pos, `${path}.gripper_to_cube_pos`, 3),
  };
}

function policyFacts(v: unknown, path: string): PolicyFacts {
  const o = rec(v, path);
  const availability = str(o.availability, `${path}.availability`);
  const hidden_before_present = bool(o.hidden_before_present, `${path}.hidden_before_present`);
  const hidden_after_present = bool(o.hidden_after_present, `${path}.hidden_after_present`);
  return {
    availability,
    before: availability !== "available" ? "unavailable" : hidden_before_present ? "present" : "initialized_none",
    after: availability !== "available" ? "unavailable" : hidden_after_present ? "present" : "initialized_none",
    state_before_sha256: optSha(o.state_before_sha256, `${path}.state_before_sha256`),
    state_after_sha256: optSha(o.state_after_sha256, `${path}.state_after_sha256`),
    episode_reset: null,
    reset_before_inference: bool(o.reset_before_inference, `${path}.reset_before_inference`),
    hidden_before_present,
    hidden_after_present,
    counter_before: optInt(o.counter_before, `${path}.counter_before`),
    counter_after: optInt(o.counter_after, `${path}.counter_after`),
  };
}

export interface SamplesExpectation {
  run: RunKey;
  rowCount: number;
  actionDimension: number;
}

export function decodeSamples(json: unknown, expected: SamplesExpectation): Samples {
  const o = rec(json, "samples");
  schemaOf(o.schema, "samples.schema", SUPPORTED.samples);
  const run = runKey(o.run, "samples.run");
  if (run.bundle_sha256 !== expected.run.bundle_sha256 || run.run_id !== expected.run.run_id) {
    throw new DecodeError("samples.run", `file belongs to run ${run.run_id} of bundle ${run.bundle_sha256.slice(0, 8)}, not the selected run`);
  }
  const rowsRaw = arr(o.rows, "samples.rows", LIMITS.rows);
  if (rowsRaw.length !== expected.rowCount) {
    throw new DecodeError("samples.rows", `expected ${expected.rowCount} rows, found ${rowsRaw.length}`);
  }
  const rows: SampleRow[] = rowsRaw.map((r, i) => {
    const path = `samples.rows[${i}]`;
    const row = rec(r, path);
    const row_index = int(row.row_index, `${path}.row_index`);
    if (row_index !== i) throw new DecodeError(`${path}.row_index`, `expected ${i}`);
    const digestsRaw = optRec(row.digests, `${path}.digests`) ?? {};
    const digests: Record<string, string | null> = {};
    for (const [k, v] of Object.entries(digestsRaw)) digests[k] = optSha(v, `${path}.digests.${k}`);
    return {
      row_index,
      step: int(row.step, `${path}.step`),
      observation_step: optInt(row.observation_step, `${path}.observation_step`),
      action_sim_time_s: num(row.action_sim_time_s, `${path}.action_sim_time_s`),
      next_sim_time_s: num(row.next_sim_time_s, `${path}.next_sim_time_s`),
      observation_sim_time_s: optNum(row.observation_sim_time_s, `${path}.observation_sim_time_s`),
      consumed_observation_capture_sim_time_s: optNum(
        row.consumed_observation_capture_sim_time_s,
        `${path}.consumed_observation_capture_sim_time_s`,
      ),
      observation_age_s: optNum(row.observation_age_s, `${path}.observation_age_s`),
      intended_action: numArr(row.intended_action, `${path}.intended_action`, expected.actionDimension),
      executed_action: numArr(row.executed_action, `${path}.executed_action`, expected.actionDimension),
      cube_height_m: num(row.cube_height_m, `${path}.cube_height_m`),
      task_success: bool(row.task_success, `${path}.task_success`),
      inference_wall_host_s: optNum(row.inference_wall_host_s, `${path}.inference_wall_host_s`),
      policy: policyFacts(row.policy, `${path}.policy`),
      observation: observation(row.observation, `${path}.observation`),
      captured_observation: null,
      consumed_acquisition: null,
      latest_acquisition: null,
      next_observation: observation(row.next_observation, `${path}.next_observation`),
      digests,
      locators: {},
    };
  });
  return { run, clock: str(o.clock, "samples.clock"), rows };
}

function framePhase(v: unknown, path: string, bodyCount: number, model: ModelRecord | null): FramePhase {
  const o = rec(v, path);
  const xpos = Float64Array.from(numArr(o.xpos, `${path}.xpos`, bodyCount * 3));
  const xquat = Float64Array.from(numArr(o.xquat, `${path}.xquat`, bodyCount * 4));
  const grip = vec3(o.grip_site_xpos, `${path}.grip_site_xpos`);
  // Geometry world poses composed from the body pose and the declared local pose.
  const geoms = new Float64Array(model ? model.geoms.length * 7 : 0);
  if (model) {
    model.geoms.forEach((g, i) => {
      const local_pos: Vec3 = g.local_pos ?? [0, 0, 0];
      const local_quat: Quat = g.local_quat ?? [1, 0, 0, 0];
      const bq: Quat = [xquat[g.body * 4] as number, xquat[g.body * 4 + 1] as number, xquat[g.body * 4 + 2] as number, xquat[g.body * 4 + 3] as number];
      const r = quatRotate(bq, local_pos);
      const q = quatMultiply(bq, local_quat);
      geoms.set([(xpos[g.body * 3] as number) + r[0], (xpos[g.body * 3 + 1] as number) + r[1], (xpos[g.body * 3 + 2] as number) + r[2], q[0], q[1], q[2], q[3]], i * 7);
    });
  }
  const sites = Float64Array.from([grip[0], grip[1], grip[2], 1, 0, 0, 0]);
  return {
    sim_time_s: num(o.sim_time_s, `${path}.sim_time_s`),
    xpos,
    xquat,
    sites,
    geoms,
    grip_site_xpos: grip,
    derived_cube_z_m: num(o.derived_cube_z_m, `${path}.derived_cube_z_m`),
    residual_cube_height_m: num(o.cube_z_difference_m, `${path}.cube_z_difference_m`),
    residual_eef_m: num(o.eef_coordinate_difference_m, `${path}.eef_coordinate_difference_m`),
    state_sha256: null,
  };
}

export function decodeFrames(json: unknown, expected: { run: RunKey; rowCount: number }, model: ModelRecord | null = null): Frames {
  const o = rec(json, "frames");
  schemaOf(o.schema, "frames.schema", SUPPORTED.frames);
  const run = runKey(o.run, "frames.run");
  if (run.bundle_sha256 !== expected.run.bundle_sha256 || run.run_id !== expected.run.run_id) {
    throw new DecodeError("frames.run", `file belongs to run ${run.run_id}, not the selected run`);
  }
  const convention = rec(o.coordinate_convention, "frames.coordinate_convention");
  if (convention.up !== "z" || convention.handedness !== "right" || convention.quaternion_order !== "wxyz" || convention.units !== "m") {
    throw new DecodeError("frames.coordinate_convention", "expected right-handed, z-up, metres, wxyz quaternions");
  }
  const body_count = int(o.body_count, "frames.body_count", 1);
  if (body_count > LIMITS.bodies) throw new DecodeError("frames.body_count", "exceeds the body bound");
  if (model && model.bodies.length !== body_count) throw new DecodeError("frames.body_count", `frames carry ${body_count} bodies; the model declares ${model.bodies.length}`);
  const rowsRaw = arr(o.rows, "frames.rows", LIMITS.rows);
  if (rowsRaw.length !== expected.rowCount) {
    throw new DecodeError("frames.rows", `expected ${expected.rowCount} rows, found ${rowsRaw.length}`);
  }
  let maxCube = 0;
  let maxEef = 0;
  const rows = rowsRaw.map((r, i) => {
    const path = `frames.rows[${i}]`;
    const row = rec(r, path);
    const row_index = int(row.row_index, `${path}.row_index`);
    if (row_index !== i) throw new DecodeError(`${path}.row_index`, `expected ${i}`);
    const before = framePhase(row.before, `${path}.before`, body_count, model);
    const after = framePhase(row.after, `${path}.after`, body_count, model);
    for (const phase of [before, after]) {
      maxCube = Math.max(maxCube, phase.residual_cube_height_m ?? 0);
      maxEef = Math.max(maxEef, phase.residual_eef_m ?? 0);
    }
    return { row_index, step: int(row.step, `${path}.step`), before, after };
  });
  return {
    run,
    derivation: rec(o.derivation, "frames.derivation"),
    body_count,
    site_count: 1,
    geom_count: model ? model.geoms.length : 0,
    maximum_residuals: { cube_height_difference_m: maxCube, eef_coordinate_difference_m: maxEef },
    rows,
  };
}

export function decodeModel(json: unknown): ModelRecord {
  const o = rec(json, "model");
  schemaOf(o.schema, "model.schema", SUPPORTED.model);
  const convention = rec(o.coordinate_convention, "model.coordinate_convention");
  if (convention.up !== "z" || convention.handedness !== "right" || convention.quaternion_order !== "wxyz") {
    throw new DecodeError("model.coordinate_convention", "expected right-handed, z-up, wxyz quaternions");
  }
  const bodies = arr(o.bodies, "model.bodies", LIMITS.bodies).map((b, i) => {
    const path = `model.bodies[${i}]`;
    const body = rec(b, path);
    const index = int(body.index, `${path}.index`);
    if (index !== i) throw new DecodeError(`${path}.index`, `expected ${i}`);
    return { index, name: str(body.name, `${path}.name`), parent: int(body.parent, `${path}.parent`) };
  });
  const byName = new Map(bodies.map((b) => [b.name, b.index]));
  const schematic = rec(o.schematic, "model.schematic");
  const links = arr(schematic.links, "model.schematic.links", 256).map((l, i): [string, string, number] => {
    const path = `model.schematic.links[${i}]`;
    const a = arr(l, path, 3);
    const from = str(a[0], `${path}[0]`);
    const to = str(a[1], `${path}[1]`);
    if (!byName.has(from) || !byName.has(to)) throw new DecodeError(path, "link names a body that is not in the model");
    return [from, to, num(a[2], `${path}[2]`)];
  });
  const geoms: ModelGeom[] = [];
  for (const [i, b] of arr(schematic.boxes ?? [], "model.schematic.boxes", 64).entries()) {
    const path = `model.schematic.boxes[${i}]`;
    const box = rec(b, path);
    const body = byName.get(str(box.body, `${path}.body`));
    if (body === undefined) throw new DecodeError(`${path}.body`, "unknown body");
    geoms.push({ index: geoms.length, name: str(box.name, `${path}.name`), body, type: "box", size: vec3(box.half_size, `${path}.half_size`), local_pos: vec3(box.pos, `${path}.pos`), local_quat: vec4(box.quat, `${path}.quat`) });
  }
  for (const [i, c] of arr(schematic.cylinders ?? [], "model.schematic.cylinders", 64).entries()) {
    const path = `model.schematic.cylinders[${i}]`;
    const cyl = rec(c, path);
    const body = byName.get(str(cyl.body, `${path}.body`));
    if (body === undefined) throw new DecodeError(`${path}.body`, "unknown body");
    geoms.push({ index: geoms.length, name: str(cyl.name, `${path}.name`), body, type: "cylinder", size: [num(cyl.radius, `${path}.radius`), num(cyl.half_length, `${path}.half_length`), 0], local_pos: vec3(cyl.pos, `${path}.pos`), local_quat: vec4(cyl.quat, `${path}.quat`) });
  }
  const countsRaw = optRec(o.counts, "model.counts") ?? {};
  const counts: Record<string, number> = {};
  for (const [k, v] of Object.entries(countsRaw)) counts[k] = num(v, `model.counts.${k}`);
  return {
    label: optStr(o.label, "model.label"),
    representation: "articulated_schematic",
    bodies,
    sites: [{ index: 0, name: "gripper0_grip_site", body: byName.get("gripper0_eef") ?? -1 }],
    geoms,
    schematic: {
      links,
      joint_marks: strArr(schematic.joint_marks ?? JOINT_MARK_NAMES, "model.schematic.joint_marks", 64),
      drawable_geoms: geoms.map((g) => g.index),
      floor_z_m: num(schematic.floor_z_m ?? 0, "model.schematic.floor_z_m"),
    },
    meshes: optRec(o.meshes, "model.meshes") ?? {},
    counts,
    limitations: [],
  };
}
