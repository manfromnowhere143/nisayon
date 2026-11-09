import { ResourceCache, defaultOptions, openCase, openGeneration, type LoaderOptions } from "./loader";
import type { LibraryCase } from "./library";
import type { Fields, StudyTrial } from "./study";
import type { CaseRecord, Generation, RunRecord } from "../model/types";
import { formatLocator } from "../state/locator";

export interface StudyScenes { generation: Generation; caseRecord: CaseRecord; evidence: string }
export interface StudySceneLink { url: string; model: string; run: RunRecord }
const cache = new ResourceCache(8);
const fields = (v: unknown): Fields => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Fields : {};

export async function loadStudyScenes(key: string, library: LibraryCase[], signal: AbortSignal, options: LoaderOptions = defaultOptions()): Promise<StudyScenes | null> {
  const entry = library.find(c => c.caseKey === key);
  if (!entry) return null;
  const cached = cache.get<StudyScenes>(`${entry.evidence}:${entry.generation}`);
  if (cached) return cached;
  const { generation } = await openGeneration(entry.evidence, signal, options, entry.generation);
  const caseRecord = await openCase(generation, key, signal, options, cache);
  const value = { generation, caseRecord, evidence: entry.evidence };
  if (!signal.aborted) cache.set(`${entry.evidence}:${entry.generation}`, value);
  return value;
}

// A name is never sufficient. Join the full trial, verified original bundle,
// exact run, raw trace digest and execution/configuration identity. The normal
// scene loader subsequently admits the model, samples and frames together.
export function studySceneLink(scenes: StudyScenes | null, trial: StudyTrial, record: Fields): StudySceneLink | null {
  if (!scenes || !trial.confirmation) return null;
  const { caseRecord, generation, evidence } = scenes;
  if (caseRecord.case_key !== `${trial.comparison}/${trial.case_id}/${trial.arm}`) return null;
  const raw = trial.confirmation.raw_source;
  if (raw.status !== "verified" || typeof raw.bundle_sha256_expected !== "string" || raw.bundle_sha256_expected !== raw.bundle_sha256_observed) return null;
  const run = caseRecord.runs.find(r => r.stage === "confirmation" && r.run.bundle_sha256 === raw.bundle_sha256_observed && r.run.run_id === record.run_id);
  if (!run?.model || !run.frames || !run.raw_source_id || run.row_count < 1) return null;
  const trace = generation.source_bindings.find(s => s.id === run.raw_source_id);
  const artifacts = Array.isArray(record.artifacts) ? record.artifacts.map(fields) : [];
  if (!trace || !artifacts.some(a => a.sha256 === trace.sha256 && typeof a.path === "string" && a.path.endsWith(".jsonl.gz"))) return null;
  const identity = fields(run.evaluator?.identity);
  if (typeof record.configuration_sha256 !== "string" || identity.configuration_sha256 !== record.configuration_sha256 || typeof record.execution_identity_sha256 !== "string" || identity.execution_identity_sha256 !== record.execution_identity_sha256) return null;
  if (run.condition_id !== record.condition_id || run.seed !== record.seed || run.initial_state_sha256 !== fields(record.reset).initial_state_sha256 || run.started_at !== record.started_at) return null;
  return { run, model: run.model.sha256, url: formatLocator({ generation_sha256: generation.sha256, case_key: caseRecord.case_key, run: run.run, row_index: run.row_count - 1, phase: "after", clock: "simulation" }, "moment", evidence) };
}

export function diagnosticSceneLink(scenes: StudyScenes | null, trial: StudyTrial): string | null {
  if (!scenes || scenes.caseRecord.case_key !== `${trial.comparison}/${trial.case_id}/${trial.arm}`) return null;
  const bundle = fields(trial.diagnostic.bundle_source).sha256;
  const run = scenes.caseRecord.runs.find(r => r.stage === "diagnostic" && r.role === "regression" && r.run.bundle_sha256 === bundle);
  if (!run?.model || !run.frames) return null;
  const finding = scenes.caseRecord.findings.find(f => f.run.bundle_sha256 === bundle && f.run.run_id === run.run.run_id && f.row_index !== null);
  return formatLocator({ generation_sha256: scenes.generation.sha256, case_key: scenes.caseRecord.case_key, run: run.run, row_index: finding?.row_index ?? 0, phase: finding?.phase ?? "before", clock: "simulation" }, "moment", scenes.evidence);
}
