/** Bounded display projections, separate from the qualified native ZIP reader.
 * Shape and association checks do not authenticate these unsigned records.
 */
import { JsonNumber, array, object, parseRecord, string, type Json, type JsonObject } from "./json";

export const SUMMARY_SCHEMA = "nisayon.qualification.check_summary.v1";
export const MEASUREMENT_SCHEMA = "nisayon.qualification.check_measurement_review.v1";
export const EXPLANATION_SCHEMA = "nisayon.qualification.check_explanation.v1";
export const PROJECTION_BYTES = 2 * 1024 * 1024;
export const EXPLANATION_REFERENCES = 8192;
export class ProjectionError extends Error {
  constructor(readonly kind: "invalid" | "unsupported" | "capacity" | "association", message: string) { super(message); }
}
const invalid = (message: string): never => { throw new ProjectionError("invalid", message); };
const capacity = (message: string): never => { throw new ProjectionError("capacity", `${message} Use the compatible CLI to inspect this record.`); };
const exact = (value: Json | undefined, keys: string[], name: string) => {
  const record = object(value, name);
  if (Object.keys(record).sort().join() !== [...keys].sort().join()) invalid(`The ${name} has missing or unsupported fields.`);
  return record;
};
const text = (value: Json | undefined, max = 8192) => { const result = string(value); if (result.length > max) capacity("This text exceeds the browser's display limit."); return result; };
const one = <T extends string>(value: Json | undefined, values: readonly T[]): T => values.includes(value as T) ? value as T : invalid("The record contains an unsupported value.");
const fixed = <T extends Json>(value: Json | undefined, expected: T): T => value === expected ? expected : invalid("The record changes a required v1 meaning or authority.");
const id = (value: Json | undefined) => { const result = text(value, 80); return /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(result) ? result : invalid("Invalid recorded identifier."); };
const sha = (value: Json | undefined) => { const result = text(value, 64); return /^[a-f0-9]{64}$/.test(result) ? result : invalid("Expected a lowercase SHA-256 identity."); };
const nullable = <T>(value: Json | undefined, read: (v: Json | undefined) => T): T | null => value === null ? null : read(value);
const boolean = (value: Json | undefined) => typeof value === "boolean" ? value : invalid("Expected a boolean field.");
const list = <T>(value: Json | undefined, read: (v: Json) => T, max = 256): T[] => {
  const result = array(value); if (result.length > max) capacity(`This list exceeds the ${max}-entry browser limit.`); return result.map(read);
};
const unique = (values: string[]) => { if (new Set(values).size !== values.length) invalid("Duplicate recorded identifiers."); return values; };
const integer = (value: Json | undefined) => {
  if (!(value instanceof JsonNumber) || !/^(0|[1-9]\d*)$/.test(value.raw)) return invalid("Expected a nonnegative integer count.");
  if (!Number.isSafeInteger(Number(value.raw))) return capacity("This count exceeds the browser's integer capacity.");
  return Number(value.raw);
};
const seconds = (value: Json | undefined): string => {
  if (!(value instanceof JsonNumber) || !Number.isFinite(Number(value.raw)) || Number(value.raw) < 0) invalid("Recorded time must be finite, numeric and nonnegative.");
  return (value as JsonNumber).raw;
};
// Exact decimal comparison of display-clock metadata only. Measurement
// relations are never recomputed in JavaScript. Preserve the original spelling.
function decimal(raw: string): { n: bigint; scale: number } {
  const [mantissa = "0", exponent = "0"] = raw.toLowerCase().split("e");
  const [whole = "0", fraction = ""] = mantissa.split(".");
  const n = BigInt(whole + fraction), scale = fraction.length - Number(exponent);
  if (n < 0n) invalid("Recorded time must be nonnegative.");
  if (n === 0n) return { n, scale: 0 };
  if (!Number.isSafeInteger(scale) || Math.abs(scale) > 4096) capacity("The recorded clock precision exceeds the browser limit.");
  return { n, scale };
}
function checkClocks(workflow: string, attempts: (string | null)[]) {
  const w = decimal(workflow), times = attempts.filter((v): v is string => v !== null).map(decimal);
  const scale = Math.max(9, w.scale + 12, ...times.map(t => t.scale));
  if (scale > 4096) capacity("The recorded clock precision exceeds the browser limit.");
  const units = (t: ReturnType<typeof decimal>) => t.n * 10n ** BigInt(scale - t.scale);
  const wall = units(w), total = times.reduce((sum, t) => sum + units(t), 0n);
  const floor = 10n ** BigInt(scale - 9), relative = wall / 1_000_000_000_000n;
  if (total > wall + (floor > relative ? floor : relative)) invalid("Nested attempt times exceed their enclosing workflow time.");
}
const verdicts = ["supported", "rejected", "unresolved"] as const;
const statuses = ["completed", "unresolved"] as const;
const checkKinds = ["observation", "analysis", "confirmation", "review"] as const;
const inputKinds = ["code", "data", "runtime", "scoring", "population", "state", "protocol", "weights", "other"] as const;
const attemptStates = ["completed", "failed", "interrupted", "started", "not_attempted"] as const;
const actions = ["run", "reuse"] as const;
const commonSource = (r: JsonObject) => ({ bundle: sha(r.bundle_sha256), model: sha(r.model_sha256), checker: sha(r.checker_sha256) });

export function readSummary(record: JsonObject) {
  exact(record, ["schema", "source", "record_review", "execution", "context", "change", "inputs", "checks", "costs", "outcome", "decision", "deployment_decision", "limitations"], "summary");
  fixed(record.schema, SUMMARY_SCHEMA);
  const source = exact(record.source, ["bundle_sha256", "bundle_schema", "execution_schema", "model_sha256", "checker_sha256"], "source");
  fixed(source.bundle_schema, "nisayon.qualification.check_bundle.v1");
  const executionSchema = one(source.execution_schema, ["nisayon.qualification.check_execution.v1", "nisayon.qualification.check_execution.v2"]);
  const review = exact(record.record_review, ["integrity", "reconstruction", "independent_execution_attestation"], "record review");
  fixed(review.integrity, "verified"); fixed(review.independent_execution_attestation, false);
  const reconstruction = one(review.reconstruction, ["verified_execution_records", "unresolved"]);
  const execution = exact(record.execution, ["status", "error_count", "acquisition"], "execution"), status = one(execution.status, statuses), errors = integer(execution.error_count);
  const acq = exact(execution.acquisition, ["status", "resource", "reason_code"], "acquisition");
  const acquisition = { status: one(acq.status, ["completed", "failed", "interrupted", "not_recorded"]), resource: nullable(acq.resource, id), reason: nullable(acq.reason_code, v => one(v, ["input_acquisition_failed", "input_acquisition_interrupted"])) };
  if ((executionSchema.endsWith(".v1")) !== (acquisition.status === "not_recorded")) invalid("Acquisition history disagrees with the recorded execution version.");
  if (["completed", "not_recorded"].includes(acquisition.status) && (acquisition.resource !== null || acquisition.reason !== null)) invalid("Completed or absent acquisition history cannot carry a failure.");
  if (acquisition.status === "failed" && acquisition.reason !== "input_acquisition_failed" || acquisition.status === "interrupted" && acquisition.reason !== "input_acquisition_interrupted") invalid("Acquisition state and reason disagree.");
  const context = exact(record.context, ["question", "comparison_arms", "physical_or_simulation_provenance", "missing_reason"], "context");
  ["question", "comparison_arms", "physical_or_simulation_provenance"].forEach(k => fixed(context[k], null)); fixed(context.missing_reason, "not_bound_by_check_execution_schema");
  const change = exact(record.change, ["input_ids", "basis", "previous_check_count", "model_changed"], "change");
  fixed(change.basis, "recorded_previous_state");
  const changed = unique(list(change.input_ids, id)), previous = integer(change.previous_check_count), modelChanged = boolean(change.model_changed);
  const inputs = list(record.inputs, v => {
    const r = exact(v, ["id", "kind", "sha256", "status"], "input");
    const input = { id: id(r.id), kind: one(r.kind, inputKinds), sha: nullable(r.sha256, sha), status: one(r.status, ["bound", "unknown"]) };
    if ((input.status === "bound") !== (input.sha !== null)) invalid("Input binding and identity disagree."); return input;
  });
  const checks = list(record.checks, v => {
    const r = exact(v, ["id", "kind", "planned_action", "attempted_action", "execution_status", "elapsed_seconds", "artifact_sha256"], "check");
    const check = { id: id(r.id), kind: one(r.kind, checkKinds), planned: one(r.planned_action, actions), attempted: nullable(r.attempted_action, v => one(v, actions)), status: one(r.execution_status, attemptStates), seconds: nullable(r.elapsed_seconds, seconds), artifact: nullable(r.artifact_sha256, sha) };
    if ((check.status === "not_attempted") !== (check.attempted === null) || check.attempted !== null && check.attempted !== check.planned) invalid("A check attempt disagrees with its plan or state.");
    if (check.attempted === null && check.seconds !== null || check.status === "completed" && (check.artifact === null || check.seconds === null)) invalid("Check completion, timing and artifact identity disagree.");
    if (check.kind === "confirmation" && check.planned !== "run") invalid("A required confirmation cannot be planned as reuse.");
    return check;
  });
  unique([...inputs.map(i => i.id), ...checks.map(c => c.id)]);
  if (!inputs.length || !checks.length || changed.some(key => !inputs.some(i => i.id === key))) invalid("The summary has inconsistent input or check membership.");
  if (acquisition.resource && !inputs.some(i => i.id === acquisition.resource)) invalid("Acquisition names an unknown input.");
  if (["failed", "interrupted"].includes(acquisition.status) && (status !== "unresolved" || !errors || inputs.some(i => i.sha !== null) || checks.some(c => c.attempted !== null || c.artifact !== null))) invalid("Failed acquisition cannot retain executed checks or bound input bytes.");
  if ((status === "completed") !== (reconstruction === "verified_execution_records") || status === "completed" && (errors !== 0 || checks.some(c => c.status !== "completed"))) invalid("Execution and reconstruction states disagree.");
  const costs = exact(record.costs, ["workflow_wall_seconds", "human_engineering_seconds", "complete_cost", "basis", "boundary"], "costs");
  const workflow = seconds(costs.workflow_wall_seconds); fixed(costs.human_engineering_seconds, null); fixed(costs.complete_cost, null);
  fixed(costs.basis, "recorded_process_timing_not_independent_measurement"); fixed(costs.boundary, "Attempt times are nested; setup, review, retries and maintenance are incomplete.");
  checkClocks(workflow, checks.map(c => c.seconds));
  const outcome = exact(record.outcome, ["status", "reason"], "outcome"), decision = exact(record.decision, ["status", "automatic_acceptance"], "decision");
  fixed(outcome.status, "not_adjudicated"); fixed(outcome.reason, "handler_claims_require_a_semantic_checker"); fixed(decision.status, "unresolved"); fixed(decision.automatic_acceptance, false); fixed(record.deployment_decision, "unresolved");
  const limitations = list(record.limitations, v => text(v), 32);
  const expectedLimits = ["Reviewed declarations and trusted stateless handlers remain premises.", "Hashes bind bytes, not physical truth, permission or authenticity.", "A complete process does not establish scientific acceptance or complete cost.", "This projection does not classify hardware, simulation or historical provenance.", "IDs and digests remain visible; raw payloads, host paths and free text are omitted.", "Re-verify the pinned source archive; this saved summary is not signed authority."];
  if (limitations.length !== expectedLimits.length || limitations.some((v, i) => v !== expectedLimits[i])) invalid("The v1 summary must retain its fixed limitations.");
  return { kind: "summary" as const, source: commonSource(source), executionSchema, reconstruction, status, errors, acquisition, changed, previous, modelChanged, inputs, checks, workflow, limitations };
}
export type CheckSummary = ReturnType<typeof readSummary>;

export function readMeasurement(record: JsonObject) {
  exact(record, ["schema", "source", "selection", "integrity", "execution_status", "review_status", "reason", "assessment_matches", "recorded_verdict", "assessment", "confirmation", "task_outcome", "deployment_decision", "automatic_acceptance", "limit"], "measurement review");
  fixed(record.schema, MEASUREMENT_SCHEMA); fixed(record.integrity, "verified"); fixed(record.confirmation, "not_assessed"); fixed(record.task_outcome, "not_adjudicated"); fixed(record.deployment_decision, "unresolved"); fixed(record.automatic_acceptance, false);
  const s = exact(record.source, ["bundle_sha256", "model_sha256", "checker_sha256", "contract_input_sha256", "observation_sha256", "saved_assessment_sha256"], "measurement source");
  const source = { ...commonSource(s), contract: nullable(s.contract_input_sha256, sha), observation: nullable(s.observation_sha256, sha), saved: nullable(s.saved_assessment_sha256, sha) };
  const binding = exact(record.selection, ["contract_input", "observation_check", "assessment_check", "basis"], "measurement selection");
  fixed(binding.basis, "caller_selected_recorded_bindings_not_preregistration");
  const selection = { contract: id(binding.contract_input), observation: id(binding.observation_check), assessment: id(binding.assessment_check) }; unique(Object.values(selection));
  const execution = one(record.execution_status, statuses), status = one(record.review_status, ["verified", "unresolved", "claim_mismatch"]);
  const reason = one(record.reason, ["execution_incomplete", "saved_assessment_differs", "measurement_semantics_unresolved", "recorded_relation_recomputed"]);
  const matches = nullable(record.assessment_matches, boolean), recorded = nullable(record.recorded_verdict, v => one(v, verdicts)), limit = text(record.limit);
  const assessment = nullable(record.assessment, value => {
    const a = exact(value, ["schema", "contract_sha256", "verdict", "scope", "checks", "failures", "errors", "deployment_decision", "limit"], "assessment");
    fixed(a.schema, "nisayon.qualification.measurement_assessment.v1"); fixed(a.deployment_decision, "unresolved");
    const checks = list(a.checks, v => { const c = exact(v, ["metric", "condition", "holds"], "measured condition"); return { metric: id(c.metric), condition: id(c.condition), holds: boolean(c.holds) }; }, 2048);
    unique(checks.map(c => `${c.metric}:${c.condition}`));
    const result = { contract: sha(a.contract_sha256), verdict: one(a.verdict, verdicts), scope: text(a.scope), checks, failures: unique(list(a.failures, v => text(v, 240), 2048)), errors: list(a.errors, v => text(v), 2048), limit: text(a.limit) };
    const failedConditions = checks.filter(c => !c.holds).map(c => `${c.metric}:${c.condition}`).sort();
    if (failedConditions.join() !== [...result.failures].sort().join()) invalid("The retained failed conditions and failure list disagree.");
    if (result.verdict === "supported" && (result.failures.length || result.errors.length || checks.some(c => !c.holds)) || result.verdict === "rejected" && (!result.failures.length || result.errors.length) || result.verdict === "unresolved" && !result.errors.length) invalid("The measured verdict conflicts with its retained conditions.");
    return result;
  });
  if (!assessment) {
    if (execution !== "unresolved" || status !== "unresolved" || reason !== "execution_incomplete" || matches !== null || recorded !== null || source.observation !== null || source.saved !== null) invalid("An unfinished review cannot release a complete assessment.");
  } else {
    if (execution !== "completed" || source.contract === null || source.observation === null || source.saved === null || recorded === null || matches === null) invalid("A complete assessment is missing its source bindings.");
    if (status === "claim_mismatch") { if (matches !== false || reason !== "saved_assessment_differs") invalid("Saved-claim disagreement has inconsistent status."); }
    else if (matches !== true || recorded !== assessment.verdict || (status === "verified" ? assessment.verdict === "unresolved" || reason !== "recorded_relation_recomputed" : assessment.verdict !== "unresolved" || reason !== "measurement_semantics_unresolved")) invalid("The review status disagrees with its assessment.");
  }
  return { kind: "measurement" as const, source, selection, execution, status, reason, matches, recorded, assessment, limit };
}
export type MeasurementReview = ReturnType<typeof readMeasurement>;

const reasonCodes = ["dependency_model_changed", "dependency_model_review_unavailable", "missing_receipt", "unavailable_upstream_evidence", "receipt_dependency_mismatch", "artifact_bytes_changed", "fresh_check_required", "upstream_requires_check", "recorded_reason_detail_withheld"] as const;
const ids = (value: Json | undefined) => unique(list(value, id));
const sameIds = (a: string[], b: string[]) => [...a].sort().join() === [...b].sort().join();

export function readExplanation(record: JsonObject) {
  exact(record, ["schema", "source", "record_review", "execution_status", "planning", "change", "inputs", "checks", "decisions", "outcome", "deployment_decision", "automatic_acceptance", "limitations"], "dependency explanation");
  fixed(record.schema, EXPLANATION_SCHEMA); fixed(record.outcome, "not_adjudicated"); fixed(record.deployment_decision, "unresolved"); fixed(record.automatic_acceptance, false);
  const s = exact(record.source, ["bundle_sha256", "bundle_schema", "execution_schema", "model_sha256", "checker_sha256", "applicability_record_sha256", "previous_record_sha256"], "explanation source");
  fixed(s.bundle_schema, "nisayon.qualification.check_bundle.v1");
  const source = { ...commonSource(s), applicability: sha(s.applicability_record_sha256), previousRecord: sha(s.previous_record_sha256) };
  const executionSchema = one(s.execution_schema, ["nisayon.qualification.check_execution.v1", "nisayon.qualification.check_execution.v2"]);
  const rr = exact(record.record_review, ["integrity", "reconstruction", "independent_execution_attestation"], "explanation record review");
  fixed(rr.integrity, "verified"); fixed(rr.independent_execution_attestation, false);
  const reconstruction = one(rr.reconstruction, ["verified_execution_records", "unresolved"]), status = one(record.execution_status, statuses);
  if ((status === "completed") !== (reconstruction === "verified_execution_records")) invalid("Explanation execution and reconstruction disagree.");
  const p = exact(record.planning, ["status", "obligation_count", "basis"], "planning");
  fixed(p.basis, "recorded_previous_state_not_a_new_experiment");
  const planning = { status: one(p.status, ["planned", "unresolved"]), obligations: integer(p.obligation_count) };
  if ((planning.status === "planned") !== (planning.obligations === 0)) invalid("Recorded planning status and obligation count disagree.");
  const change = exact(record.change, ["input_ids", "previous_model_sha256", "model_changed", "previous_check_count"], "explanation change");
  const changed = ids(change.input_ids), previousModel = sha(change.previous_model_sha256), modelChanged = boolean(change.model_changed), previous = integer(change.previous_check_count);
  if (modelChanged !== (previousModel !== source.model)) invalid("The previous model identity and change flag disagree.");
  const inputs = list(record.inputs, v => {
    const r = exact(v, ["id", "kind", "sha256", "status", "previous_present", "previous_sha256"], "explanation input");
    const input = { id: id(r.id), kind: one(r.kind, inputKinds), sha: nullable(r.sha256, sha), status: one(r.status, ["bound", "unknown"]), previousPresent: boolean(r.previous_present), previousSha: nullable(r.previous_sha256, sha) };
    if ((input.status === "bound") !== (input.sha !== null) || !input.previousPresent && input.previousSha !== null) invalid("Current or previous input identity is inconsistent.");
    return input;
  });
  const checks = list(record.checks, v => {
    const r = exact(v, ["id", "kind", "refresh", "depends_on", "planned_action", "attempted_action", "execution_status", "artifact_sha256", "previous_receipt_present", "previous_artifact_sha256", "reasons", "affected_inputs"], "explanation check");
    const check = { id: id(r.id), kind: one(r.kind, checkKinds), refresh: one(r.refresh, ["on_change", "always"]), depends: ids(r.depends_on), planned: one(r.planned_action, actions), attempted: nullable(r.attempted_action, v => one(v, actions)), status: one(r.execution_status, attemptStates), artifact: nullable(r.artifact_sha256, sha), previousReceipt: boolean(r.previous_receipt_present), previousArtifact: nullable(r.previous_artifact_sha256, sha),
      reasons: list(r.reasons, v => { const reason = exact(v, ["code", "check"], "selection reason"); return { code: one(reason.code, reasonCodes), check: nullable(reason.check, id) }; }),
      affected: list(r.affected_inputs, v => { const item = exact(v, ["input", "reason", "via"], "affected input"); return { input: id(item.input), reason: one(item.reason, ["changed", "unknown"]), via: id(item.via) }; }) };
    if (!check.depends.length) invalid("A check must declare at least one dependency.");
    if ((check.status === "not_attempted") !== (check.attempted === null) || check.attempted !== null && check.attempted !== check.planned || check.status === "completed" && check.artifact === null) invalid("Explanation attempt, plan and artifact disagree.");
    if (check.previousReceipt !== (check.previousArtifact !== null)) invalid("Previous receipt presence and its recorded artifact disagree.");
    if (check.refresh === "always" && check.planned !== "run" || check.kind === "confirmation" && check.refresh !== "always") invalid("Always-refresh checks cannot be planned as reuse.");
    return check;
  });
  const decisions = list(record.decisions, v => {
    const r = exact(v, ["id", "depends_on", "applicability", "required_checks", "reusable_checks", "obligations"], "historical decision requirements");
    return { id: id(r.id), depends: ids(r.depends_on), applicability: one(r.applicability, ["requires_checks", "unresolved"]), required: ids(r.required_checks), reusable: ids(r.reusable_checks), obligations: unique(list(r.obligations, v => text(v, 160))) };
  });
  unique([...inputs.map(i => i.id), ...checks.map(c => c.id), ...decisions.map(d => d.id)]);
  const inputMap = new Map(inputs.map(i => [i.id, i])), checkMap = new Map(checks.map(c => [c.id, c]));
  if (!inputs.length || !checks.length || !decisions.length || changed.some(key => !inputMap.has(key))) invalid("The explanation has inconsistent node membership.");
  const references = checks.reduce((n, c) => n + c.depends.length + c.reasons.length + 2 * c.affected.length, 0) + decisions.reduce((n, d) => n + d.depends.length + d.required.length + d.reusable.length + d.obligations.length, 0);
  if (references > EXPLANATION_REFERENCES) capacity("The dependency explanation exceeds the 8192-reference browser budget.");
  // Structural graph checks only. No planner, handler or scientific relation runs here.
  const visited = new Set<string>(), active = new Set<string>(), ancestors = new Map<string, Set<string>>();
  function visit(key: string): Set<string> {
    if (inputMap.has(key)) return new Set([key]);
    if (active.has(key)) return invalid("The declared check graph contains a cycle.");
    const check = checkMap.get(key); if (!check) return invalid("A dependency names an unknown input or check.");
    if (visited.has(key)) return ancestors.get(key)!;
    active.add(key); const reachable = new Set<string>();
    for (const dependency of check.depends) { reachable.add(dependency); visit(dependency).forEach(node => reachable.add(node)); }
    active.delete(key); visited.add(key); ancestors.set(key, reachable); return reachable;
  }
  checks.forEach(c => visit(c.id));
  for (const check of checks) {
    for (const reason of check.reasons) {
      if (reason.code === "upstream_requires_check" ? !reason.check || !check.depends.includes(reason.check) || !checkMap.has(reason.check) : reason.check !== null) invalid("A selection reason names an invalid upstream check.");
    }
    for (const item of check.affected) {
      if (!inputMap.has(item.input) || !check.depends.includes(item.via) || !visit(item.via).has(item.input)) invalid("An affected input does not resolve through its declared dependency.");
    }
  }
  for (const decision of decisions) {
    if (!decision.depends.length || decision.depends.some(key => !checkMap.has(key))) invalid("A decision dependency must name a declared check.");
    unique([...decision.required, ...decision.reusable]);
    const reachable = new Set(decision.depends.flatMap(key => [key, ...visit(key)]));
    if ([...decision.required, ...decision.reusable].some(key => !checkMap.has(key) || !reachable.has(key))) invalid("A decision requirement names a check outside its declared dependencies.");
    if (!sameIds([...decision.required, ...decision.reusable], [...reachable].filter(key => checkMap.has(key))) || decision.required.some(key => checkMap.get(key)!.planned !== "run") || decision.reusable.some(key => checkMap.get(key)!.planned !== "reuse")) invalid("Historical decision requirements disagree with the recorded check selections.");
    if ((decision.applicability === "unresolved") !== (decision.obligations.length > 0)) invalid("Decision applicability and its obligations disagree.");
    for (const obligation of decision.obligations) {
      if (["fresh_confirmation_not_declared", "dependency_model_review_unavailable"].includes(obligation)) continue;
      const [code, value, extra] = obligation.split(":");
      if (extra !== undefined || (code === "unknown_input" ? !value || !inputMap.has(value) || !reachable.has(value) : code === "uncovered_dependency_kind" ? !inputKinds.includes(value as typeof inputKinds[number]) : true)) invalid("A decision obligation has an unsupported code or reference.");
    }
  }
  if (status === "completed" && checks.some(c => c.status !== "completed") || checks.filter(c => c.previousReceipt).length > previous) invalid("Explanation completion or previous-receipt count is inconsistent.");
  const limitations = list(record.limitations, v => text(v), 32);
  const expected = ["Explains the recorded declared graph, not physical causation or an optimal experiment.", "Previous receipt presence or equal hashes do not establish valid reusable evidence.", "Planned reuse is not attempted reuse; required checks are historical plan obligations.", "Always-refresh confirmation is a program obligation, not proof of fresh physical data.", "IDs and digests may be sensitive; omitted diagnostics remain available in local source records.", "Re-verify the pinned archive with its recorded checker; unsigned JSON is not authenticated evidence."];
  if (limitations.length !== expected.length || limitations.some((v, i) => v !== expected[i])) invalid("The v1 explanation must retain its fixed limitations.");
  return { kind: "explanation" as const, source, executionSchema, reconstruction, status, planning, changed, previousModel, modelChanged, previous, inputs, checks, decisions, limitations };
}
export type DependencyExplanation = ReturnType<typeof readExplanation>;
export type Projection = CheckSummary | MeasurementReview | DependencyExplanation;

export function parseProjection(bytes: Uint8Array): Projection {
  if (bytes.byteLength > PROJECTION_BYTES) capacity("This JSON exceeds the 2 MiB browser limit.");
  try {
    const record = object(parseRecord(new TextDecoder("utf-8", { fatal: true }).decode(bytes)));
    if (record.schema === SUMMARY_SCHEMA) return readSummary(record);
    if (record.schema === MEASUREMENT_SCHEMA) return readMeasurement(record);
    if (record.schema === EXPLANATION_SCHEMA) return readExplanation(record);
    throw new ProjectionError("unsupported", "This JSON schema or version is not supported by the projection reader.");
  } catch (error) {
    if (error instanceof ProjectionError) throw error;
    const message = error instanceof Error ? error.message : "Invalid JSON record.";
    throw new ProjectionError(message.includes("supported inspection") ? "capacity" : "invalid", message);
  }
}
export function associate(summary: CheckSummary, review: MeasurementReview): void {
  const refuse = (): never => { throw new ProjectionError("association", "This review does not match the selected summary. Its results have not been attached."); };
  if (["bundle", "model", "checker"].some(k => summary.source[k as keyof CheckSummary["source"]] !== review.source[k as keyof CheckSummary["source"]]) || summary.status !== review.execution) refuse();
  const input = summary.inputs.find(i => i.id === review.selection.contract), observation = summary.checks.find(c => c.id === review.selection.observation), assessment = summary.checks.find(c => c.id === review.selection.assessment);
  if (!input || input.kind !== "scoring" || input.sha !== review.source.contract || observation?.kind !== "observation" || assessment?.kind !== "analysis") refuse();
  if (review.assessment && (observation?.status !== "completed" || assessment?.status !== "completed" || observation.artifact !== review.source.observation || assessment.artifact !== review.source.saved)) refuse();
}
export const quoteShell = (value: string) => `'${value.replaceAll("'", `'"'"'`)}'`;
export function associateExplanation(summary: CheckSummary, explanation: DependencyExplanation, review: MeasurementReview | null = null): void {
  const refuse = (): never => { throw new ProjectionError("association", "The explanation does not match the selected records. Its dependencies have not been attached."); };
  if (["bundle", "model", "checker"].some(k => summary.source[k as keyof CheckSummary["source"]] !== explanation.source[k as keyof CheckSummary["source"]]) || summary.executionSchema !== explanation.executionSchema || summary.status !== explanation.status || summary.reconstruction !== explanation.reconstruction || summary.previous !== explanation.previous || summary.modelChanged !== explanation.modelChanged || !sameIds(summary.changed, explanation.changed)) refuse();
  if (summary.inputs.length !== explanation.inputs.length || summary.checks.length !== explanation.checks.length) refuse();
  for (const input of summary.inputs) {
    const row = explanation.inputs.find(i => i.id === input.id);
    if (!row || row.kind !== input.kind || row.sha !== input.sha || row.status !== input.status) refuse();
  }
  for (const check of summary.checks) {
    const row = explanation.checks.find(c => c.id === check.id);
    if (!row || row.kind !== check.kind || row.planned !== check.planned || row.attempted !== check.attempted || row.status !== check.status || row.artifact !== check.artifact) refuse();
  }
  if (review) {
    associate(summary, review);
    const analysis = explanation.checks.find(c => c.id === review.selection.assessment);
    if (!analysis?.depends.includes(review.selection.contract) || !analysis.depends.includes(review.selection.observation)) refuse();
  }
}
export function readbackCommands(summary: CheckSummary, review: MeasurementReview | null, path: string, explanation: DependencyExplanation | null = null): string[] {
  const archive = quoteShell(path), pin = quoteShell(summary.source.bundle);
  return [`nisayon-qualify summarize-check-bundle ${archive} --sha256 ${pin}`, ...(explanation ? [`nisayon-qualify explain-check-bundle ${archive} --sha256 ${pin}`] : []), ...(review ? [`nisayon-qualify review-check-measurements ${archive} --sha256 ${pin} --contract-input ${quoteShell(review.selection.contract)} --observation-check ${quoteShell(review.selection.observation)} --assessment-check ${quoteShell(review.selection.assessment)}`] : [])];
}
