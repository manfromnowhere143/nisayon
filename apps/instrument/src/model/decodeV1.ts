// Decoders for the data lane's concrete wire schema (schemas/ui/generation-v1).
// Every object is checked against the declared shape; identities, paths and
// counts are bounded; the internal model is produced without invention.

import {
  DecodeError,
  LIMITS,
  UnsupportedSchemaError,
  arr,
  bool,
  fileRef,
  int,
  isRecord,
  num,
  numArr,
  optInt,
  optNum,
  optRec,
  optSha,
  optStr,
  predicates,
  rec,
  runKey,
  sha,
  str,
  strArr,
  vec3,
} from "./decode";
import type { Evidence } from "./decode";
import type { Acquisition } from "./types";
import {
  JOINT_MARK_NAMES,
  linkStrokesFromBodies,
  type CaseRecord,
  type CaseRef,
  type CostEntry,
  type ExportFinding,
  type FileRef,
  type FramePhase,
  type Frames,
  type Generation,
  type MemoryState,
  type ModelGeom,
  type ModelRecord,
  type Observation,
  type PolicyFacts,
  type RunRecord,
  type SampleRow,
  type Samples,
  type SourceBinding,
} from "./types";

export const V1 = {
  discovery: "nisayon.ui-discovery.v1",
  integrity: "nisayon.ui-integrity.v1",
  generation: "nisayon.ui-generation.v1",
  case: "nisayon.ui-case.v1",
  samples: "nisayon.ui-samples.v1",
  reconstruction: "nisayon.ui-reconstruction.v1",
  model: "nisayon.ui-model.v1",
  decision: "nisayon.ui-decision.v1",
} as const;

const OBJECT_PATH = /^(objects|generations)\/[0-9a-f]{64}\.json$/;

function objectRef(v: unknown, path: string, kind?: string): FileRef {
  const ref = fileRef(v, path);
  if (!OBJECT_PATH.test(ref.path)) throw new DecodeError(`${path}.path`, "expected objects/<sha256>.json or generations/<sha256>.json");
  if (!ref.path.includes(ref.sha256)) throw new DecodeError(`${path}.path`, "the object's path must carry its own digest");
  if (kind !== undefined && ref.kind !== kind) throw new DecodeError(`${path}.kind`, `expected kind "${kind}", found "${ref.kind ?? "none"}"`);
  return ref;
}

function sameObject(a: FileRef, b: FileRef): boolean {
  return a.path === b.path && a.sha256 === b.sha256 && a.byte_length === b.byte_length && a.kind === b.kind && a.media_type === b.media_type;
}
function registered(ref: FileRef, files: readonly FileRef[], path: string): void {
  const entry = files.find((file) => file.path === ref.path);
  if (!entry || !sameObject(entry, ref)) throw new DecodeError(path, `${ref.path} disagrees with the manifest registry`);
}

function expectSchema(v: unknown, path: string, expected: string): void {
  const s = str(v, path);
  if (s !== expected) throw new UnsupportedSchemaError(path, s, [expected]);
}

export function decodeDiscoveryV1(json: unknown): Evidence {
  const o = rec(json, "evidence");
  expectSchema(o.schema, "evidence.schema", V1.discovery);
  const manifest = objectRef(o.manifest, "evidence.manifest", "manifest");
  return { schema: V1.discovery, label: null, current: { generation_sha256: manifest.sha256, manifest_path: manifest.path, byte_length: manifest.byte_length } };
}

interface SourceV1 {
  id: string;
  label: string;
  sha256: string;
  byte_length: number;
  encoding: string;
  canonical_json_sha256: string | null;
}

function sourceV1(v: unknown, path: string): SourceV1 {
  const o = rec(v, path);
  return {
    id: str(o.id, `${path}.id`),
    label: str(o.label, `${path}.label`),
    sha256: sha(o.sha256, `${path}.sha256`),
    byte_length: int(o.byte_length, `${path}.byte_length`, 1),
    encoding: str(o.encoding, `${path}.encoding`),
    canonical_json_sha256: optSha(o.canonical_json_sha256, `${path}.canonical_json_sha256`),
  };
}

// Object paths are relative to the export root (where evidence.json lives), not
// to the generations/ directory that holds the manifest.
export function decodeManifestV1(json: unknown, sha256: string, manifestUrl: string, rootUrl: string): Generation {
  const o = rec(json, "manifest");
  expectSchema(o.schema, "manifest.schema", V1.generation);
  const sources = arr(o.sources, "manifest.sources", LIMITS.files).map((s, i) => sourceV1(s, `manifest.sources[${i}]`));
  const seenSources = new Set<string>();
  for (const s of sources) {
    if (seenSources.has(s.id)) throw new DecodeError("manifest.sources", `duplicate source id "${s.id}"`);
    seenSources.add(s.id);
  }
  const files = arr(o.files, "manifest.files", LIMITS.files).map((f, i) => objectRef(f, `manifest.files[${i}]`));
  const seenFiles = new Set<string>();
  for (const f of files) {
    if (seenFiles.has(f.path)) throw new DecodeError("manifest.files", `duplicate file path "${f.path}"`);
    seenFiles.add(f.path);
  }
  const cases: CaseRef[] = arr(o.cases, "manifest.cases", LIMITS.cases).map((c, i) => {
    const path = `manifest.cases[${i}]`;
    const entry = rec(c, path);
    const object = objectRef(entry.object, `${path}.object`, "case");
    registered(object, files, `${path}.object`);
    return { ...object, case_key: str(entry.case_key, `${path}.case_key`) };
  });
  const seenCases = new Set<string>();
  for (const c of cases) {
    if (seenCases.has(c.case_key)) throw new DecodeError("manifest.cases", `duplicate case_key "${c.case_key}"`);
    seenCases.add(c.case_key);
  }
  if (cases.length === 0) throw new DecodeError("manifest.cases", "a generation needs at least one case");
  const bundle = sources.find((s) => s.id.startsWith("bundle:"));
  const firstCase = rec(arr(o.cases, "manifest.cases", LIMITS.cases)[0], "manifest.cases[0]");
  return {
    sha256,
    manifestUrl,
    baseUrl: rootUrl,
    schema: V1.generation,
    label: null,
    adapter: { name: str(o.adapter, "manifest.adapter") },
    experiment: { id: str(o.experiment_id, "manifest.experiment_id"), case_id: str(firstCase.case_id, "manifest.cases[0].case_id"), arm: "", stage: "" },
    capabilities: { list: strArr(o.capabilities, "manifest.capabilities", 64) },
    source_bindings: sources.map(
      (s): SourceBinding => ({
        id: s.id,
        canonical_json_sha256: s.canonical_json_sha256,
        kind: s.encoding,
        path: s.label,
        sha256: s.sha256,
        byte_length: s.byte_length,
        binding: s.canonical_json_sha256 ? `${s.id} · canonical JSON ${s.canonical_json_sha256.slice(0, 8)}` : s.id,
      }),
    ),
    bundle_sha256: bundle ? bundle.sha256 : null,
    cases,
    files,
    residuals: null,
    limitations: strArr(o.limitations, "manifest.limitations", 256),
  };
}

function locator(v: unknown, path: string): Record<string, string | number | null> {
  const o = rec(v, path);
  return { source_id: str(o.source_id, `${path}.source_id`), pointer: optStr(o.pointer, `${path}.pointer`), line: optInt(o.line, `${path}.line`, 1) };
}

function costEntryV1(v: unknown, path: string): CostEntry {
  const o = rec(v, path);
  return {
    category: str(o.category ?? "unknown", `${path}.category`),
    value: optNum(o.value, `${path}.value`),
    unit: optStr(o.unit, `${path}.unit`),
    missing_reason: optStr(o.missing_reason, `${path}.missing_reason`),
  };
}

function runV1(v: unknown, path: string, sources: Map<string, SourceBinding>): RunRecord {
  const o = rec(v, path);
  const key = runKey(o.key, `${path}.key`);
  const sample_count = int(o.sample_count, `${path}.sample_count`, 1);
  if (sample_count > LIMITS.rows) throw new DecodeError(`${path}.sample_count`, "exceeds the row bound");
  const source = locator(o.source, `${path}.source`);
  const raw_source_id = optStr(o.raw_source_id, `${path}.raw_source_id`);
  const evaluator = optRec(o.evaluator, `${path}.evaluator`);
  const candidate = evaluator && isRecord(evaluator.candidate) ? evaluator.candidate : null;
  const identity = evaluator && isRecord(evaluator.identity) ? evaluator.identity : null;
  const reset = optRec(o.reset, `${path}.reset`) ?? {};
  const sourceRefs = [];
  const bundleSource = sources.get(String(source.source_id));
  if (!bundleSource || bundleSource.kind !== "json" || bundleSource.sha256 !== key.bundle_sha256) throw new DecodeError(`${path}.source`, "run source binding does not match the claimed bundle");
  if (typeof source.pointer !== "string" || !/^\/runs\/(0|[1-9][0-9]*)$/.test(source.pointer)) throw new DecodeError(`${path}.source.pointer`, "invalid run source pointer");
  sourceRefs.push({ path: `${bundleSource.path} ${source.pointer ?? ""}`.trim(), sha256: bundleSource.sha256, kind: "bundle" });
  if (raw_source_id) {
    const raw = sources.get(raw_source_id);
    if (!raw) throw new DecodeError(`${path}.raw_source_id`, "unknown raw source");
    sourceRefs.push({ path: raw.path, sha256: raw.sha256, kind: raw.kind });
  }
  const model = o.model === null || o.model === undefined ? null : objectRef(o.model, `${path}.model`, "model");
  const reconstruction = o.reconstruction === null || o.reconstruction === undefined ? null : objectRef(o.reconstruction, `${path}.reconstruction`, "reconstruction");
  const plan = optRec(o.plan, `${path}.plan`);
  const execution = optRec(o.execution, `${path}.execution`);
  if (plan && (plan.id !== o.plan_id || plan.role !== o.role)) throw new DecodeError(`${path}.plan`, "plan identity or role differs from the run");
  return {
    run: key,
    role: str(o.role, `${path}.role`),
    plan_id: plan ? `${key.bundle_sha256}:${str(o.plan_id, `${path}.plan_id`)}` : str(o.role, `${path}.role`),
    plan,
    stage: str(o.stage, `${path}.stage`),
    assignment_role: null,
    condition_id: str(o.condition_id, `${path}.condition_id`),
    seed: execution ? optInt(execution.seed, `${path}.execution.seed`) : null,
    process_status: str(o.process_status, `${path}.process_status`),
    measurement_status: str(o.measurement_status, `${path}.measurement_status`),
    task_outcome: str(o.task_outcome, `${path}.task_outcome`),
    execution_mode: optStr(execution?.execution_mode, `${path}.execution.execution_mode`) ?? optStr(plan?.execution_mode, `${path}.plan.execution_mode`) ?? "",
    evidence_origin: optStr(execution?.evidence_origin, `${path}.execution.evidence_origin`) ?? (evaluator && typeof evaluator.evidence_origin === "string" ? evaluator.evidence_origin : ""),
    candidate_sha256: candidate && typeof candidate.digest === "string" && /^[0-9a-f]{64}$/.test(candidate.digest) ? candidate.digest : null,
    configuration_sha256: identity && typeof identity.configuration_sha256 === "string" && /^[0-9a-f]{64}$/.test(identity.configuration_sha256) ? identity.configuration_sha256 : null,
    reset_id: optStr(execution?.reset_id, `${path}.execution.reset_id`),
    initial_state_sha256: optSha(execution?.initial_state_sha256, `${path}.execution.initial_state_sha256`),
    started_at: optStr(execution?.started_at, `${path}.execution.started_at`),
    ended_at: optStr(execution?.ended_at, `${path}.execution.ended_at`),
    row_count: sample_count,
    recording: { ends_at_row: sample_count - 1, last_next_sim_time_s: optNum(o.last_next_sim_time_s, `${path}.last_next_sim_time_s`) },
    samples: objectRef(o.samples, `${path}.samples`, "samples"),
    frames: reconstruction,
    model,
    sources: sourceRefs,
    source_locator: { source_id: String(source.source_id), pointer: source.pointer },
    raw_source_id,
    policy_reset: isRecord(reset.policy_reset) ? reset.policy_reset : null,
    policy_state_reset: isRecord(reset.policy_state_reset) ? reset.policy_state_reset : null,
    constraint_violations: [],
    costs: arr(o.costs ?? [], `${path}.costs`, 4096).map((c, i) => costEntryV1(c, `${path}.costs[${i}]`)),
    derivation_residuals: null,
    evaluator,
  };
}

function findingV1(v: unknown, path: string): ExportFinding {
  const o = rec(v, path);
  const phaseRaw = optStr(o.phase, `${path}.phase`);
  return {
    id: optStr(o.id, `${path}.id`),
    kind: optStr(o.kind, `${path}.kind`) ?? "descriptive",
    code: str(o.code, `${path}.code`),
    definition: str(o.definition, `${path}.definition`),
    detail: optStr(o.detail, `${path}.detail`),
    run: runKey(o.run, `${path}.run`),
    row_index: optInt(o.row_index, `${path}.row_index`),
    step: optInt(o.step, `${path}.step`),
    phase: phaseRaw === "before" || phaseRaw === "after" ? phaseRaw : null,
    threshold: optNum(o.threshold, `${path}.threshold`),
    component: null,
    intended: null,
    executed: null,
    action_sim_time_s: null,
    status: "export descriptive finding; not an evaluator decision",
  };
}

export function decodeCaseV1(json: unknown, generation: Generation): CaseRecord {
  const o = rec(json, "case");
  expectSchema(o.schema, "case.schema", V1.case);
  const sources = new Map(generation.source_bindings.map((s) => [s.id ?? s.binding.split(" · ")[0] as string, s]));
  const runs = arr(o.runs, "case.runs", LIMITS.runs).map((r, i) => runV1(r, `case.runs[${i}]`, sources));
  const seen = new Set<string>();
  for (const r of runs) {
    const key = `${r.run.bundle_sha256}:${r.run.run_id}`;
    if (seen.has(key)) throw new DecodeError("case.runs", `duplicate run identity ${r.run.run_id} in bundle ${r.run.bundle_sha256.slice(0, 8)}`);
    seen.add(key);
  }
  if (runs.length === 0) throw new DecodeError("case.runs", "a case needs at least one run");
  const plans = new Map<string, Record<string, unknown>>();
  for (const run of runs) {
    if (!run.plan) continue;
    const prior = plans.get(run.plan_id);
    if (prior && JSON.stringify(prior) !== JSON.stringify(run.plan)) throw new DecodeError("case.plans", "one plan identity has conflicting declarations");
    plans.set(run.plan_id, run.plan);
  }
  for (const r of runs) {
    for (const ref of [r.samples, r.frames, r.model]) {
      if (ref) registered(ref, generation.files, "case.runs");
    }
  }
  const decisionRefs = arr(o.decisions, "case.decisions", 64).map((d, i) => objectRef(d, `case.decisions[${i}]`, "decision"));
  for (const ref of decisionRefs) {
    registered(ref, generation.files, "case.decisions");
  }
  const findings = arr(o.findings, "case.findings", LIMITS.findings).map((f, i) => findingV1(f, `case.findings[${i}]`));
  const runIds = new Set(runs.map((r) => `${r.run.bundle_sha256}:${r.run.run_id}`));
  for (const f of findings) {
    if (!runIds.has(`${f.run.bundle_sha256}:${f.run.run_id}`)) throw new DecodeError("case.findings", `finding ${f.code} names a run that is not in this case`);
  }
  const trial = optRec(o.trial, "case.trial");
  const trialSource = trial ? sources.get(str(rec(trial.source, "case.trial.source").source_id, "case.trial.source.source_id")) : null;
  if (trial && !trialSource) throw new DecodeError("case.trial.source", "trial source is not bound by this generation");
  return {
    label: null,
    case_key: str(o.case_key, "case.case_key"),
    case_id: str(o.case_id, "case.case_id"),
    experiment_id: str(o.experiment_id, "case.experiment_id"),
    arm: str(o.arm, "case.arm"),
    stage: runs[0]?.stage ?? "",
    task: optStr(o.task, "case.task"),
    predicates: predicates(o.predicates, "case.predicates"),
    deployments: {},
    plans: Array.from(plans, ([id, plan]) => ({ ...plan, id })),
    runs,
    alignment: { declared: str(o.comparison_alignment, "case.comparison_alignment") },
    comparison_alignment: str(o.comparison_alignment, "case.comparison_alignment"),
    findings,
    decisions: trial && trialSource ? { trial: { path: trialSource.path, sha256: trialSource.sha256, byte_length: trialSource.byte_length!, content: trial, omitted_reason: null } } : {},
    decisionRefs,
    trial,
    confirmation: rec(o.confirmation, "case.confirmation"),
    costs: null,
    telemetry_profile: null,
    qualification: null,
    limitations: strArr(o.limitations, "case.limitations", 64),
  };
}

function memoryState(v: unknown, path: string): MemoryState {
  const s = str(v, path);
  if (s === "present" || s === "initialized_none" || s === "unavailable") return s;
  throw new DecodeError(path, `unknown memory state "${s}"`);
}

function acquisition(v: unknown, path: string, step: unknown): Acquisition | null {
  if (v === undefined || v === null) return null;
  const o = rec(v, path);
  const capturedStep = int(o.step, `${path}.step`);
  if (step !== undefined && step !== null && capturedStep !== step) throw new DecodeError(path, "acquisition step differs from its observation step");
  const components = Object.entries(rec(o.components, `${path}.components`));
  if (components.length > 64) throw new DecodeError(path, "too many acquisition components");
  return {
    step: capturedStep,
    oldest_sim_time_s: num(o.oldest_capture_sim_time_s, `${path}.oldest_capture_sim_time_s`),
    components: components.map(([name, value]) => {
      const component = rec(value, `${path}.components.${name}`);
      return { name, sequence: int(component.sequence, `${path}.components.${name}.sequence`), sim_time_s: num(component.simulation_s, `${path}.components.${name}.simulation_s`) };
    }),
  };
}

function observationV1(v: unknown, path: string): Observation | null {
  if (v === null || v === undefined) return null;
  const o = rec(v, path);
  const object = numArr(o.object, `${path}.object`, 10);
  return {
    robot0_eef_pos: numArr(o.robot0_eef_pos, `${path}.robot0_eef_pos`, 3),
    robot0_eef_quat: numArr(o.robot0_eef_quat, `${path}.robot0_eef_quat`, 4),
    robot0_gripper_qpos: numArr(o.robot0_gripper_qpos, `${path}.robot0_gripper_qpos`, 2),
    cube_pos: object.slice(0, 3),
    cube_quat: object.slice(3, 7),
    gripper_to_cube_pos: object.slice(7, 10),
  };
}

export function decodeSamplesV1(json: unknown, expected: { run: { bundle_sha256: string; run_id: string }; rowCount: number; actionDimension: number; record?: RunRecord }): Samples {
  const o = rec(json, "samples");
  expectSchema(o.schema, "samples.schema", V1.samples);
  const run = runKey(o.run, "samples.run");
  if (run.bundle_sha256 !== expected.run.bundle_sha256 || run.run_id !== expected.run.run_id) {
    throw new DecodeError("samples.run", `file belongs to run ${run.run_id} of bundle ${run.bundle_sha256.slice(0, 8)}, not the selected run`);
  }
  const rowsRaw = arr(o.rows, "samples.rows", LIMITS.rows);
  if (rowsRaw.length !== expected.rowCount) throw new DecodeError("samples.rows", `expected ${expected.rowCount} rows, found ${rowsRaw.length}`);
  const rows: SampleRow[] = rowsRaw.map((r, i) => {
    const path = `samples.rows[${i}]`;
    const row = rec(r, path);
    const row_index = int(row.row_index, `${path}.row_index`);
    if (row_index !== i) throw new DecodeError(`${path}.row_index`, `expected ${i}`);
    const original = rec(row.original, `${path}.original`);
    const memory = rec(row.memory, `${path}.memory`);
    const observations = optRec(row.observations, `${path}.observations`);
    const before = memoryState(memory.before, `${path}.memory.before`);
    const after = memoryState(memory.after, `${path}.memory.after`);
    const capture = optRec(original.observation_capture, `${path}.original.observation_capture`);
    const digests: Record<string, string | null> = {};
    for (const k of ["observation_sha256", "next_observation_sha256", "captured_observation_sha256", "state_before_sha256", "state_after_sha256"]) {
      digests[k] = optSha(original[k], `${path}.original.${k}`);
    }
    const policy: PolicyFacts = {
      availability: before === "unavailable" || after === "unavailable" ? "unavailable" : "available",
      before,
      after,
      state_before_sha256: optSha(memory.before_sha256, `${path}.memory.before_sha256`),
      state_after_sha256: optSha(memory.after_sha256, `${path}.memory.after_sha256`),
      episode_reset: memory.episode_reset === null || memory.episode_reset === undefined ? null : bool(memory.episode_reset, `${path}.memory.episode_reset`),
      reset_before_inference: memory.reset_before_inference === null || memory.reset_before_inference === undefined ? false : bool(memory.reset_before_inference, `${path}.memory.reset_before_inference`),
      hidden_before_present: before === "present",
      hidden_after_present: after === "present",
      counter_before: null,
      counter_after: null,
    };
    for (const field of ["step", "action_sim_time_s", "next_sim_time_s", "observation_sim_time_s"]) {
      if (num(row[field], `${path}.${field}`) !== num(original[field], `${path}.original.${field}`)) throw new DecodeError(`${path}.${field}`, "projection differs from its original reading");
    }
    const actionTime = num(row.action_sim_time_s, `${path}.action_sim_time_s`);
    const nextTime = num(row.next_sim_time_s, `${path}.next_sim_time_s`);
    const observedTime = num(row.observation_sim_time_s, `${path}.observation_sim_time_s`);
    if (nextTime < actionTime || observedTime > actionTime || num(row.observation_age_s, `${path}.observation_age_s`) !== actionTime - observedTime) throw new DecodeError(path, "sample clock or observation age disagrees");
    for (const [side, field, state] of [["before", "policy_state_sha256", before], ["after", "policy_state_after_sha256", after]] as const) {
      if (memory[`${side}_sha256`] !== original[field]) throw new DecodeError(`${path}.memory`, "memory digest differs from original reading");
      if ((state === "unavailable") !== (memory[`${side}_sha256`] === null)) throw new DecodeError(`${path}.memory`, "memory availability disagrees with recorded digest");
    }
    if (bool(memory.reset_before_inference, `${path}.memory.reset_before_inference`) !== bool(original.policy_reset_before_inference, `${path}.original.policy_reset_before_inference`)) throw new DecodeError(`${path}.memory`, "reset flag differs from original reading");
    const source = locator(row.source, `${path}.source`);
    const raw = row.raw_source === null || row.raw_source === undefined ? null : locator(row.raw_source, `${path}.raw_source`);
    const record = expected.record;
    if (record?.source_locator && (source.source_id !== record.source_locator.source_id || source.pointer !== `${record.source_locator.pointer}/trace/${i}` || source.line !== null)) throw new DecodeError(`${path}.source`, "sample source locator differs from selected run");
    if (record?.raw_source_id !== undefined && (record.raw_source_id === null ? raw !== null : !raw || raw.source_id !== record.raw_source_id || raw.line !== i + 2 || raw.pointer !== null)) throw new DecodeError(`${path}.raw_source`, "raw line binding differs from selected run");
    if (record && policy.episode_reset !== (i === 0 ? record.policy_reset?.episode_reset_applied ?? null : null)) throw new DecodeError(`${path}.memory.episode_reset`, "episode reset marker differs from selected run");
    return {
      row_index,
      step: int(row.step, `${path}.step`),
      observation_step: optInt(original.observation_step, `${path}.original.observation_step`),
      action_sim_time_s: num(row.action_sim_time_s, `${path}.action_sim_time_s`),
      next_sim_time_s: num(row.next_sim_time_s, `${path}.next_sim_time_s`),
      observation_sim_time_s: optNum(row.observation_sim_time_s, `${path}.observation_sim_time_s`),
      consumed_observation_capture_sim_time_s: capture ? optNum(capture.oldest_capture_sim_time_s, `${path}.original.observation_capture.oldest_capture_sim_time_s`) : null,
      observation_age_s: optNum(row.observation_age_s, `${path}.observation_age_s`),
      intended_action: numArr(original.intended_action, `${path}.original.intended_action`, expected.actionDimension),
      executed_action: numArr(original.executed_action, `${path}.original.executed_action`, expected.actionDimension),
      cube_height_m: num(original.cube_height_m, `${path}.original.cube_height_m`),
      task_success: bool(original.task_success, `${path}.original.task_success`),
      inference_wall_host_s: optNum(original.inference_wall_s, `${path}.original.inference_wall_s`),
      policy,
      observation: observations ? observationV1(observations.observation, `${path}.observations.observation`) : null,
      captured_observation: observations ? observationV1(observations.captured_observation, `${path}.observations.captured_observation`) : null,
      consumed_acquisition: acquisition(original.observation_capture, `${path}.original.observation_capture`, original.observation_step),
      latest_acquisition: acquisition(original.captured_observation_capture, `${path}.original.captured_observation_capture`, original.captured_observation_step),
      next_observation: observations ? observationV1(observations.next_observation, `${path}.observations.next_observation`) : null,
      digests,
      locators: {
        source_id: source.source_id ?? null,
        pointer: source.pointer ?? null,
        raw_source_id: raw ? (raw.source_id ?? null) : null,
        raw_line: raw ? (raw.line ?? null) : null,
      },
    };
  });
  const steps = new Set<number>();
  for (const row of rows) {
    if (steps.has(row.step)) throw new DecodeError("samples.rows", "duplicate sample step");
    steps.add(row.step);
    if (row.row_index > 0 && row.action_sim_time_s < rows[row.row_index - 1]!.next_sim_time_s) throw new DecodeError("samples.rows", "recorded state time overlaps or reverses");
  }
  if (expected.record?.recording.last_next_sim_time_s != null && rows.at(-1)?.next_sim_time_s !== expected.record.recording.last_next_sim_time_s) throw new DecodeError("samples.rows", "recording end time differs from selected run");
  return { run, clock: "simulation", rows };
}

export function decodeModelV1(json: unknown): ModelRecord {
  const o = rec(json, "model");
  expectSchema(o.schema, "model.schema", V1.model);
  const representation = str(o.representation, "model.representation");
  const nq = int(o.nq, "model.nq"), nv = optInt(o.nv, "model.nv"), nu = optInt(o.nu, "model.nu");
  if (representation !== "articulated_schematic") throw new DecodeError("model.representation", `unknown representation "${representation}"`);
  const bodies = arr(o.bodies, "model.bodies", LIMITS.bodies).map((b, i) => {
    const path = `model.bodies[${i}]`;
    const body = rec(b, path);
    const index = int(body.id, `${path}.id`);
    if (index !== i) throw new DecodeError(`${path}.id`, `expected ${i}`);
    return { index, name: str(body.name, `${path}.name`), parent: int(body.parent_id, `${path}.parent_id`) };
  });
  if (bodies.length === 0) throw new DecodeError("model.bodies", "model has no world body");
  for (const body of bodies) if (body.index === 0 ? body.parent !== 0 : body.parent >= body.index) throw new DecodeError(`model.bodies[${body.index}].parent_id`, "invalid body ancestry");
  if (new Set(bodies.map((body) => body.name)).size !== bodies.length) throw new DecodeError("model.bodies", "duplicate body name");
  const sites = arr(o.sites, "model.sites", 256).map((s, i) => {
    const path = `model.sites[${i}]`;
    const site = rec(s, path);
    const index = int(site.id, `${path}.id`);
    if (index !== i) throw new DecodeError(`${path}.id`, `expected ${i}`);
    return { index, name: str(site.name, `${path}.name`), body: int(site.body_id, `${path}.body_id`) };
  });
  const geoms: ModelGeom[] = arr(o.geoms, "model.geoms", 4096).map((g, i) => {
    const path = `model.geoms[${i}]`;
    const geom = rec(g, path);
    return {
      index: i,
      name: str(geom.name, `${path}.name`),
      body: int(geom.body_id, `${path}.body_id`),
      type: str(geom.type, `${path}.type`),
      size: vec3(geom.size, `${path}.size`),
      local_pos: null,
      local_quat: null,
    };
  });
  for (const g of geoms) {
    if (g.body >= bodies.length) throw new DecodeError(`model.geoms[${g.index}].body_id`, "names a body outside the model");
  }
  for (const site of sites) if (site.body >= bodies.length) throw new DecodeError(`model.sites[${site.index}].body_id`, "names a body outside the model");
  for (const geom of geoms) if (geom.size.some((size) => size < 0)) throw new DecodeError(`model.geoms[${geom.index}].size`, "negative geometry size");
  // Drawn primitives: boxes and cylinders that are not room walls, with one
  // of each collision/visual twin.
  const names = new Set(geoms.map((g) => g.name));
  const drawable = geoms
    .filter((g) => (g.type === "box" || g.type === "cylinder") && !g.name.startsWith("wall_"))
    .filter((g) => !(g.name.endsWith("_collision") && names.has(g.name.replace(/_collision$/, "_visual"))))
    .filter((g) => !(/_g\d+$/.test(g.name) && names.has(`${g.name}_vis`)))
    .map((g) => g.index);
  const range = (v: unknown, path: string): [number, number] | null => {
    if (v == null) return null;
    const values = numArr(v, path, 2);
    if (values[0]! > values[1]!) throw new DecodeError(path, "reversed range");
    return values as [number, number];
  };
  const joints = arr(o.joints ?? [], "model.joints", 512).map((v, i) => {
    const p = `model.joints[${i}]`, j = rec(v, p), type = str(j.type, `${p}.type`);
    if (!["free", "ball", "slide", "hinge"].includes(type)) throw new DecodeError(p, "unsupported joint type");
    const body = int(j.body_id, `${p}.body_id`), qposAddress = int(j.qpos_address, `${p}.qpos_address`), dofAddress = int(j.dof_address, `${p}.dof_address`);
    if (j.id !== i || body >= bodies.length || qposAddress + (type === "free" ? 7 : type === "ball" ? 4 : 1) > nq || nv === null || dofAddress + (type === "free" ? 6 : type === "ball" ? 3 : 1) > nv) throw new DecodeError(p, "joint address outside declared model");
    return { id: i, name: str(j.name, `${p}.name`), body, type: type as "free" | "ball" | "slide" | "hinge", axis: vec3(j.axis, `${p}.axis`), qposAddress, dofAddress, range: range(j.range, `${p}.range`) };
  });
  const actuators = arr(o.actuators ?? [], "model.actuators", 512).map((v, i) => {
    const p = `model.actuators[${i}]`, a = rec(v, p), joint = optInt(a.joint_id, `${p}.joint_id`);
    if (a.id !== i || (joint !== null && joint >= joints.length)) throw new DecodeError(p, "actuator identity outside declared model");
    return { id: i, name: str(a.name, `${p}.name`), joint, kind: str(a.kind, `${p}.kind`), unit: str(a.unit, `${p}.unit`), controlRange: range(a.control_range, `${p}.control_range`), forceRange: range(a.force_range, `${p}.force_range`) };
  });
  if (nu !== null && actuators.length !== nu) throw new DecodeError("model.actuators", "actuator count disagrees");
  return {
    label: null,
    representation,
    bodies,
    sites,
    geoms,
    joints, actuators,
    schematic: { links: linkStrokesFromBodies(bodies), joint_marks: JOINT_MARK_NAMES.filter((n) => bodies.some((b) => b.name === n)), drawable_geoms: drawable, floor_z_m: 0 },
    meshes: { available: false, omitted_mesh_count: int(o.omitted_mesh_count, "model.omitted_mesh_count"), source_id: str(o.source_id, "model.source_id") },
    counts: { nq, ...(nv !== null ? { nv } : {}), ...(nu !== null ? { nu } : {}), nmocap: int(o.nmocap, "model.nmocap"), nbody: bodies.length, ngeom: geoms.length, nsite: sites.length },
    limitations: strArr(o.limitations, "model.limitations", 64),
  };
}

function poseBuffer(v: unknown, path: string, count: number): Float64Array {
  const a = arr(v, path, LIMITS.list);
  if (a.length !== count) throw new DecodeError(path, `expected ${count} poses, found ${a.length}`);
  const out = new Float64Array(count * 7);
  a.forEach((p, i) => {
    const pose = numArr(p, `${path}[${i}]`, 7);
    if (Math.abs(pose.slice(3).reduce((sum, q) => sum + q * q, 0) - 1) >= 1e-9) throw new DecodeError(`${path}[${i}]`, "expected a unit quaternion");
    out.set(pose, i * 7);
  });
  return out;
}

export function decodeReconstructionV1(json: unknown, expected: { run: { bundle_sha256: string; run_id: string }; rowCount: number; record?: RunRecord }, model: ModelRecord | null): Frames {
  const o = rec(json, "reconstruction");
  expectSchema(o.schema, "reconstruction.schema", V1.reconstruction);
  const run = runKey(o.run, "reconstruction.run");
  if (run.bundle_sha256 !== expected.run.bundle_sha256 || run.run_id !== expected.run.run_id) {
    throw new DecodeError("reconstruction.run", `file belongs to run ${run.run_id}, not the selected run`);
  }
  const convention = rec(o.convention, "reconstruction.convention");
  if (convention.up !== "Z" || convention.handedness !== "right" || convention.quaternion_order !== "wxyz" || convention.length_unit !== "m" || convention.pose_layout !== "x,y,z,qw,qx,qy,qz") {
    throw new DecodeError("reconstruction.convention", "expected right-handed, Z-up, metres, wxyz quaternions in x,y,z,qw,qx,qy,qz layout");
  }
  if (str(o.method, "reconstruction.method") !== "mj_kinematics") throw new DecodeError("reconstruction.method", "expected mj_kinematics");
  const modelRef = objectRef(o.model, "reconstruction.model", "model");
  if (expected.record && (!expected.record.model || !sameObject(modelRef, expected.record.model))) throw new DecodeError("reconstruction.model", "reconstruction model differs from selected run");
  if (expected.record?.raw_source_id !== undefined && o.raw_source_id !== expected.record.raw_source_id) throw new DecodeError("reconstruction.raw_source_id", "reconstruction raw source differs from selected run");
  const framesRaw = arr(o.frames, "reconstruction.frames", LIMITS.rows * 2);
  if (framesRaw.length !== expected.rowCount * 2) throw new DecodeError("reconstruction.frames", `expected ${expected.rowCount * 2} frames (before and after per row), found ${framesRaw.length}`);
  const bodyCount = model ? model.bodies.length : rec(framesRaw[0], "reconstruction.frames[0]").bodies instanceof Array ? (rec(framesRaw[0], "reconstruction.frames[0]").bodies as unknown[]).length : 0;
  const siteCount = model ? model.sites.length : 0;
  const geomCount = model ? model.geoms.length : 0;
  const gripSite = model ? model.sites.find((s) => s.name === "gripper0_grip_site") : undefined;
  const cubeBody = model ? model.bodies.find((b) => b.name === "cube_main") : undefined;
  const maximum = rec(o.maximum_residuals, "reconstruction.maximum_residuals");
  const maximum_residuals: Record<string, number> = {};
  for (const [k, v] of Object.entries(maximum)) maximum_residuals[k] = num(v, `reconstruction.maximum_residuals.${k}`);

  const phaseOf = (v: unknown, index: number, rowIndex: number, phase: "before" | "after"): FramePhase => {
    const path = `reconstruction.frames[${index}]`;
    const f = rec(v, path);
    if (int(f.row_index, `${path}.row_index`) !== rowIndex) throw new DecodeError(`${path}.row_index`, `expected ${rowIndex}`);
    if (str(f.phase, `${path}.phase`) !== phase) throw new DecodeError(`${path}.phase`, `expected ${phase}`);
    const bodies = poseBuffer(f.bodies, `${path}.bodies`, bodyCount);
    const sites = poseBuffer(f.sites, `${path}.sites`, siteCount);
    const geoms = poseBuffer(f.geoms, `${path}.geoms`, geomCount);
    const xpos = new Float64Array(bodyCount * 3);
    const xquat = new Float64Array(bodyCount * 4);
    for (let b = 0; b < bodyCount; b += 1) {
      xpos[b * 3] = bodies[b * 7] as number;
      xpos[b * 3 + 1] = bodies[b * 7 + 1] as number;
      xpos[b * 3 + 2] = bodies[b * 7 + 2] as number;
      xquat[b * 4] = bodies[b * 7 + 3] as number;
      xquat[b * 4 + 1] = bodies[b * 7 + 4] as number;
      xquat[b * 4 + 2] = bodies[b * 7 + 5] as number;
      xquat[b * 4 + 3] = bodies[b * 7 + 6] as number;
    }
    const residuals = rec(f.residuals, `${path}.residuals`);
    const grip: [number, number, number] = gripSite ? [sites[gripSite.index * 7] as number, sites[gripSite.index * 7 + 1] as number, sites[gripSite.index * 7 + 2] as number] : [Number.NaN, Number.NaN, Number.NaN];
    const rawPhysical = optRec(f.physical, `${path}.physical`);
    if (rawPhysical && (!model || model.counts.nv === undefined || model.counts.nu === undefined)) throw new DecodeError(path, "physical state requires declared dimensions");
    const physical = rawPhysical ? {
      qpos: numArr(rawPhysical.qpos, `${path}.physical.qpos`, model!.counts.nq),
      qvel: numArr(rawPhysical.qvel, `${path}.physical.qvel`, model!.counts.nv),
      ctrl: numArr(rawPhysical.ctrl, `${path}.physical.ctrl`, model!.counts.nu),
      goal_pos: rawPhysical.goal_pos == null ? null : vec3(rawPhysical.goal_pos, `${path}.physical.goal_pos`),
      goal_ori: rawPhysical.goal_ori == null ? null : arr(rawPhysical.goal_ori, `${path}.physical.goal_ori`, 3).map((r, i) => numArr(r, `${path}.physical.goal_ori[${i}]`, 3)),
    } : null;
    if (physical?.goal_ori && physical.goal_ori.length !== 3) throw new DecodeError(path, "controller orientation must have three rows");
    return {
      physical,
      sim_time_s: num(f.stored_time_s, `${path}.stored_time_s`),
      xpos,
      xquat,
      sites,
      geoms,
      grip_site_xpos: grip,
      derived_cube_z_m: cubeBody ? (xpos[cubeBody.index * 3 + 2] as number) : null,
      residual_cube_height_m: optNum(residuals.cube_height_difference_m, `${path}.residuals.cube_height_difference_m`),
      residual_eef_m: optNum(residuals.eef_coordinate_difference_m, `${path}.residuals.eef_coordinate_difference_m`),
      state_sha256: optSha(f.state_sha256, `${path}.state_sha256`),
    };
  };
  const rows = [];
  for (let i = 0; i < expected.rowCount; i += 1) {
    rows.push({ row_index: i, step: null, before: phaseOf(framesRaw[2 * i], 2 * i, i, "before"), after: phaseOf(framesRaw[2 * i + 1], 2 * i + 1, i, "after") });
  }
  return {
    run,
    derivation: {
      method: "mj_kinematics",
      mujoco_version: str(o.mujoco_version, "reconstruction.mujoco_version"),
      numpy_version: str(o.numpy_version, "reconstruction.numpy_version"),
      raw_source_id: str(o.raw_source_id, "reconstruction.raw_source_id"),
      model_sha256: modelRef.sha256,
    },
    body_count: bodyCount,
    site_count: siteCount,
    geom_count: geomCount,
    maximum_residuals,
    rows,
  };
}

export interface DecisionV1 {
  stage: string;
  decision: string;
  scope: string;
  raw: Record<string, unknown>;
}

export function decodeDecisionV1(json: unknown, generation?: Generation): DecisionV1 {
  const o = rec(json, "decision");
  expectSchema(o.schema, "decision.schema", V1.decision);
  const bundle = sha(o.bundle_sha256, "decision.bundle_sha256");
  if (generation) {
    const location = locator(o.source, "decision.source");
    const source = generation.source_bindings.find((entry) => entry.id === location.source_id && entry.kind === "json");
    const bundles = generation.source_bindings.filter((entry) => entry.sha256 === bundle && entry.kind === "json");
    if (!source || bundles.length !== 1 || bundles[0]!.canonical_json_sha256 !== sha(o.source_canonical_bundle_sha256, "decision.source_canonical_bundle_sha256")) throw new DecodeError("decision.source", "decision source or bundle binding differs from the generation");
  }
  arr(o.reasons, "decision.reasons", 4096).forEach((r, i) => rec(r, `decision.reasons[${i}]`));
  rec(o.runs, "decision.runs");
  return { stage: str(o.stage, "decision.stage"), decision: str(o.decision, "decision.decision"), scope: str(o.scope, "decision.scope"), raw: o };
}
