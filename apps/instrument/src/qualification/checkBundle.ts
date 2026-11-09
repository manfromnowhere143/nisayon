/** Package bytes and saved record structure only. The browser does not run an SDK adjudicator. */
import { comparisonArchive, readRecord, verifyArchive, type QualificationBundle } from "./bundle";
import { array, object, string, JsonNumber, type Json, type JsonObject } from "./json";

export interface ExecutionCheck {
  id: string;
  declaration: JsonObject;
  selection: JsonObject;
  attempt: JsonObject | undefined;
  result: Json | undefined;
}
export interface CheckBundle {
  kind: "checks";
  sha256: string;
  modelSha256: string;
  fileName: string;
  files: Map<string, Uint8Array>;
  prefix: string;
  model: JsonObject;
  execution: JsonObject;
  applicability: JsonObject;
  assessment: JsonObject;
  checks: ExecutionCheck[];
  claims: { decision: string; check: string; value: string }[];
}
export type ReviewBundle = QualificationBundle | CheckBundle;
export const isCheckBundle = (bundle: ReviewBundle): bundle is CheckBundle => "kind" in bundle && bundle.kind === "checks";
const fail = (reason: string): never => { throw new Error(reason); };
// Object order is not semantic; numeric spelling remains lossless evidence.
function sameRecord(left: Json | undefined, right: Json | undefined): boolean {
  if (left === right) return true;
  if (left instanceof JsonNumber || right instanceof JsonNumber) return left instanceof JsonNumber && right instanceof JsonNumber && left.raw === right.raw;
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, i) => sameRecord(value, right[i]));
  if (left === null || right === null || typeof left !== "object" || typeof right !== "object") return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length && keys.every(key => Object.hasOwn(right, key) && sameRecord(left[key], right[key]));
}
const id = (value: unknown): string => typeof value === "string" && /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(value) ? value : fail("Unsupported check identity.");
const boundedMap = (value: Parameters<typeof object>[0], name: string, empty = false) => {
  const record = object(value, name), keys = Object.keys(record);
  if (keys.length > 256 || (!empty && keys.length === 0)) fail(`Unsupported ${name} size.`);
  keys.forEach(id); return record;
};

export async function inspectReview(buffer: ArrayBuffer, fileName: string, progress?: (done: number, total: number) => void): Promise<ReviewBundle> {
  const archive = await verifyArchive(buffer, progress);
  const { files, index, sha256 } = archive;
  if (index.schema === "nisayon.qualification.bundle.v1") return comparisonArchive(archive, fileName);
  if (index.schema !== "nisayon.qualification.check_bundle.v1" || Object.keys(index).sort().join() !== "files,model_sha256,schema") fail("This check package format is not supported yet.");
  const modelSha256 = string(index.model_sha256);
  if (!/^[a-f0-9]{64}$/.test(modelSha256)) fail("Invalid check model identity.");
  const assessment = object(readRecord(files, "assessment.json"));
  if (assessment.schema !== "nisayon.qualification.check_review.v1" || assessment.model_sha256 !== modelSha256 || assessment.deployment_decision !== "unresolved") fail("The saved reconstruction has inconsistent identity or authority.");
  const path = string(assessment.execution_path);
  if (path.length > 512 || !path.split("/").every(part => /^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,159}$/.test(part) && !part.endsWith("."))) fail("Invalid execution path.");
  const prefix = `evidence/${path}`;
  const read = (name: string) => object(readRecord(files, `${prefix}/${name}.json`), name);
  const model = read("model"), execution = read("execution"), applicability = read("applicability"), state = read("state");
  if (model.schema !== "nisayon.qualification.dependencies.v1" || execution.schema !== "nisayon.qualification.check_execution.v1" || applicability.schema !== "nisayon.qualification.applicability.v1" || state.schema !== "nisayon.qualification.evidence_state.v1") fail("Unsupported execution record version.");
  id(model.id); string(model.scope);
  if (state.model_sha256 !== modelSha256 || applicability.model_sha256 !== modelSha256 || !sameRecord(execution.state, state)) fail("The execution and dependency identities disagree.");
  if (execution.automatic_acceptance !== false || execution.deployment_decision !== "unresolved" || !["completed", "unresolved"].includes(string(execution.status))) fail("Unsupported execution authority or status.");
  const errors = array(execution.errors);
  errors.forEach(error => string(error, "execution error"));
  if (execution.status === "completed" && errors.length) fail("A completed execution contains execution errors.");
  const inputs = boundedMap(model.inputs, "inputs"), declarations = boundedMap(model.checks, "checks"), decisions = boundedMap(model.decisions, "decisions");
  const selections = boundedMap(applicability.checks, "check selections");
  const keys = Object.keys(declarations);
  if (keys.sort().join() !== Object.keys(selections).sort().join() || keys.some(key => Object.hasOwn(inputs, key))) fail("The planned check membership is inconsistent.");
  for (const [key, value] of Object.entries(declarations)) {
    const check = object(value), deps = array(check.depends_on);
    if (!deps.length || deps.length > 256 || new Set(deps).size !== deps.length || deps.some(dep => !Object.hasOwn(inputs, id(dep)) && !Object.hasOwn(declarations, id(dep)))) fail(`Invalid dependencies for ${key}.`);
    if (!["observation", "analysis", "confirmation", "review"].includes(string(check.kind)) || !["always", "on_change"].includes(string(check.refresh)) || (check.kind === "confirmation" && check.refresh !== "always")) fail("Unsupported check execution rule.");
  }
  const known = new Set(Object.keys(inputs)), remaining = new Set(keys);
  while (remaining.size) {
    const ready = [...remaining].filter(key => array(object(declarations[key]).depends_on).every(dep => known.has(string(dep))));
    if (!ready.length) fail("Cyclic check dependencies are unsupported.");
    ready.forEach(key => { known.add(key); remaining.delete(key); });
  }
  const attempts = array(execution.attempts).map(value => object(value));
  if (attempts.length > keys.length || new Set(attempts.map(a => a.check)).size !== attempts.length || attempts.some(a => !keys.includes(id(a.check)))) fail("Invalid execution attempt membership.");
  const review = object(assessment.review);
  if (!["verified_execution_records", "unresolved"].includes(string(review.status)) || review.automatic_acceptance !== false || (review.deployment_decision !== undefined && review.deployment_decision !== "unresolved")) fail("Unsupported saved reconstruction status.");
  if ((execution.status === "completed") !== (review.status === "verified_execution_records")) fail("Execution and saved reconstruction disagree.");
  const artifacts = boundedMap(review.artifacts, "saved results", true);
  if (Object.keys(artifacts).some(key => !keys.includes(key))) fail("Undeclared saved check result.");
  const checks: ExecutionCheck[] = Object.entries(selections).map(([key, value]) => {
    const declaration = object(declarations[key]), selection = object(value), attempt = attempts.find(row => row.check === key);
    if (!["run", "reuse"].includes(string(selection.action))) fail("Unknown check selection.");
    if (selection.kind !== declaration.kind) fail("A selected check differs from its declared kind.");
    if (selection.action === "reuse" && declaration.refresh === "always") fail("A required fresh check is marked as reused.");
    array(selection.reasons); array(selection.affected_inputs);
    if (attempt && (attempt.action !== selection.action || !["started", "completed", "failed", "interrupted"].includes(string(attempt.status)))) fail("Attempt differs from its selection.");
    if (execution.status === "completed" && (attempt?.status !== "completed" || artifacts[key] === undefined)) fail("A completed execution omitted a check.");
    if (artifacts[key] !== undefined && !sameRecord(readRecord(files, `${prefix}/checks/${key}/result.json`), artifacts[key])) fail("Saved check output differs from its original result.");
    const result = artifacts[key];
    return { id: key, declaration, selection, attempt, result };
  });
  const claims: CheckBundle["claims"] = [];
  for (const [decision, value] of Object.entries(decisions)) {
    const deps = array(object(value).depends_on);
    if (!deps.length || deps.length > 256 || new Set(deps).size !== deps.length) fail("Invalid decision dependencies.");
    for (const dep of deps) {
      const key = id(dep), check = checks.find(row => row.id === key);
      if (!check) throw new Error("Decision refers to an unknown check.");
      const result = check.result && typeof check.result === "object" && !Array.isArray(check.result) && !(check.result instanceof JsonNumber) ? check.result : {};
      const saved = result.verdict ?? result.software_decision ?? result.decision;
      if (typeof saved === "string" && ["supported", "rejected", "adopt", "reject", "unresolved"].includes(saved)) claims.push({ decision, check: key, value: saved });
    }
  }
  return { kind: "checks", sha256, modelSha256, fileName, files, prefix, model, execution, applicability, assessment, checks, claims };
}
