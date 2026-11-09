import { arr, DecodeError, fileRef, int, rec, sha, str } from "../model/decode";
import type { FileRef } from "../model/types";
import { defaultOptions, fetchVerified, readDiscovery, type LoaderOptions } from "./loader";
import { processorReport, temporalReport } from "../model/mechanisms";

const base = () => new URL("/fixtures/ui/study/", location.href).href;
export type Fields = Record<string, unknown>;
export interface StudyEntry { key: string; comparison: string; case_id: string; arm: string; historical_status: string; state: string; original_incident_id: string; repetition_id: string | null; pairs: number; records: number; object: FileRef }
export interface Study { sha: string; source: { engine_commit: string; metadata_commit: string; view_sha256: string }; verified_at: string; scope: string; trials: StudyEntry[]; counts: { trials: number; pairs: number; records: number; unscheduled: number }; costs: Fields; reports: Record<string, FileRef> }
export interface StudyPair { id: string; identity: Fields; state: string; issues: unknown[]; reference: { record_indices: number[]; run_id: string }; candidate: { record_indices: number[]; run_id: string } }
export interface StudyTrial { schema: string; case_id: string; arm: string; comparison: string; historical_status: string; state: string; issues: unknown[]; historical_decision: Fields | null; diagnostic: Fields; declaration: Fields; costs: Fields; retries: unknown; retrospective_declarations: Fields[]; confirmation: { pairs: StudyPair[]; observations: Fields[]; protocol: Fields; raw_source: Fields } | null }
export const studyUrl = (ref: Pick<FileRef, "path">) => new URL(ref.path, base()).href;

function boundRef(value: unknown, kind: "objects" | "generations"): FileRef {
  const ref = fileRef(value, "study.reference");
  if (ref.path !== `${kind}/${ref.sha256}.json`) throw new DecodeError("study.reference", "path does not bind its bytes");
  return ref;
}

export async function discoverStudy(signal?: AbortSignal, options: LoaderOptions = defaultOptions()): Promise<FileRef> {
  const doc = rec(await readDiscovery(new URL("evidence.json", base()).href, signal, options), "study.discovery");
  if (doc.schema !== "nisayon.ui-study-discovery.v1") throw new DecodeError("study.discovery", "unsupported schema");
  return boundRef(doc.generation, "generations");
}

export async function loadStudy(ref: FileRef, signal?: AbortSignal, options: LoaderOptions = defaultOptions()): Promise<Study> {
  const doc = rec((await fetchVerified(studyUrl(ref), ref, "manifest", signal, options)).json, "study");
  if (doc.schema !== "nisayon.ui-study.v1" || doc.execution_connected !== false || doc.scientific_acceptance !== "none") throw new DecodeError("study", "unsupported authority or schema");
  const source = rec(doc.source, "study.source"), counts = rec(doc.counts, "study.counts");
  const trials = arr(doc.trials, "study.trials", 1024).map((value): StudyEntry => {
    const t = rec(value, "study.trial"), key = str(t.key, "study.trial.key");
    for (const name of ["comparison", "case_id", "arm", "historical_status", "state", "original_incident_id"]) str(t[name], `study.trial.${name}`);
    if (key !== `${t.comparison}/${t.case_id}/${t.arm}`) throw new DecodeError("study.trial", "identity disagrees");
    return { ...t, pairs: int(t.pairs, "study.trial.pairs"), records: int(t.records, "study.trial.records"), object: boundRef(t.object, "objects") } as unknown as StudyEntry;
  });
  if (!trials.length || new Set(trials.map(t => t.key)).size !== trials.length || counts.trials !== trials.length || counts.pairs !== trials.reduce((n, t) => n + t.pairs, 0) || counts.records !== trials.reduce((n, t) => n + t.records, 0) || counts.unscheduled !== trials.filter(t => t.state === "confirmation_not_scheduled").length) throw new DecodeError("study", "membership or totals disagree");
  const commit = (v: unknown) => { const s = str(v, "study.commit"); if (!/^[0-9a-f]{40}$/.test(s)) throw new DecodeError("study.commit", "invalid source commit"); return s; };
  const reports = Object.fromEntries(Object.entries(rec(doc.reports ?? {}, "study.reports")).map(([key, value]) => [key, boundRef(value, "objects")]));
  return { sha: ref.sha256, source: { engine_commit: commit(source.engine_commit), metadata_commit: commit(source.metadata_commit), view_sha256: sha(source.view_sha256, "study.source.view_sha256") }, verified_at: str(doc.verified_at, "study.verified_at"), scope: str(doc.scope, "study.scope"), trials, counts: { trials: trials.length, pairs: int(counts.pairs, "study.pairs"), records: int(counts.records, "study.records"), unscheduled: int(counts.unscheduled, "study.unscheduled") }, costs: rec(doc.costs, "study.costs"), reports };
}

export async function loadStudyReport(ref: FileRef, signal?: AbortSignal, options: LoaderOptions = defaultOptions()): Promise<{ record: Fields; source: Fields; scope: string }> {
  boundRef(ref, "objects");
  const doc = rec((await fetchVerified(studyUrl(ref), ref, "case", signal, options)).json, "report");
  if (doc.schema !== "nisayon.ui-retained-report.v1") throw new DecodeError("report", "unsupported schema");
  const record = rec(doc.record, "report.record");
  if (record.schema === "nisayon.ui-temporal-contracts.v1") temporalReport(record);
  if (record.schema === "nisayon.ui-processor-decision.v1") processorReport(record);
  return { record: rec(doc.record, "report.record"), source: rec(doc.source, "report.source"), scope: str(doc.scope, "report.scope") };
}

export async function loadStudyTrial(entry: StudyEntry, signal?: AbortSignal, options: LoaderOptions = defaultOptions()): Promise<StudyTrial> {
  boundRef(entry.object, "objects");
  const doc = rec((await fetchVerified(studyUrl(entry.object), entry.object, "case", signal, options)).json, "trial");
  if (doc.schema !== "nisayon.ui-study-trial.v1" || doc.case_id !== entry.case_id || doc.arm !== entry.arm || doc.comparison !== entry.comparison || doc.historical_status !== entry.historical_status || doc.state !== entry.state) throw new DecodeError("trial", "identity disagrees with study");
  for (const name of ["diagnostic", "declaration", "costs"]) rec(doc[name], `trial.${name}`);
  arr(doc.issues, "trial.issues", 10000);
  arr(doc.retrospective_declarations, "trial.retrospective_declarations", 1000).forEach(v => rec(v, "trial.declaration"));
  if (doc.historical_decision !== null) rec(doc.historical_decision, "trial.historical_decision");
  if (doc.confirmation !== null) {
    const confirmation = rec(doc.confirmation, "trial.confirmation");
    rec(confirmation.protocol, "trial.protocol"); rec(confirmation.raw_source, "trial.raw_source");
    const observations = arr(confirmation.observations, "trial.records", 10000), pairs = arr(confirmation.pairs, "trial.pairs", 5000);
    if (observations.length !== entry.records || pairs.length !== entry.pairs) throw new DecodeError("trial", "record counts disagree");
    const ids = new Set<string>();
    for (const value of pairs) {
      const pair = rec(value, "trial.pair"), id = str(pair.id, "trial.pair.id");
      rec(pair.identity, "trial.pair.identity"); str(pair.state, "trial.pair.state"); arr(pair.issues, "trial.pair.issues", 1000);
      if (ids.has(id)) throw new DecodeError("trial.pair", "duplicate identity"); ids.add(id);
      for (const side of ["reference", "candidate"]) {
        const role = rec(pair[side], "trial.pair.role");
        for (const index of arr(role.record_indices, "trial.pair.indices", 100)) {
          const i = int(index, "trial.pair.index");
          if (i >= observations.length || rec(observations[i], "trial.record").run_id !== role.run_id) throw new DecodeError("trial.pair", "record identity disagrees");
        }
      }
    }
  } else if (entry.pairs || entry.records) throw new DecodeError("trial", "missing declared confirmation");
  return doc as unknown as StudyTrial;
}
