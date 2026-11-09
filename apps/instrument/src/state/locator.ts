// The URL is the selection: pinned generation, case, full run key, row, phase
// and depth. Theme, camera and panel layout are view state and stay out of it.

import { isSafeRelativePath, isSha256 } from "../model/decode";
import { DEPTHS, PHASES, type Depth, type Moment, type Phase, type RunKey } from "../model/types";
import { parseStudyRoute, type StudyRoute } from "./studyRoute";

// Early shared URLs omitted this root. Keep that interpretation forever.
export const DEFAULT_EVIDENCE = "fixtures/ui/d01/evidence.json";
export const INITIAL_EVIDENCE = "fixtures/ui/recorded/D01-gripper-sign/evidence.json";
export const DEV_EVIDENCE = "dev-fixture/evidence.json";

export interface Locator {
  generation: string | null;
  caseKey: string | null;
  run: RunKey | null;
  row: number | null;
  phase: Phase | null;
  depth: Depth | null;
  evidence: string | null;
  condition: string | null;
  part: string | null;
  partModel: string | null;
  study: StudyRoute | null;
  problems: string[];
}

export function parseLocator(search: string): Locator {
  const params = new URLSearchParams(search);
  const problems: string[] = [];
  const g = params.get("g");
  let generation: string | null = null;
  if (g !== null) {
    if (isSha256(g)) generation = g;
    else problems.push(`g must be a lowercase hex SHA-256; found "${truncate(g)}"`);
  }
  const caseKey = params.get("c");
  const b = params.get("b");
  const r = params.get("r");
  let run: RunKey | null = null;
  if (b !== null || r !== null) {
    if (b === null || r === null) problems.push("a run locator needs both b (bundle SHA-256) and r (run id)");
    else if (!isSha256(b)) problems.push(`b must be a lowercase hex SHA-256; found "${truncate(b)}"`);
    else if (r.length === 0) problems.push("r (run id) is empty");
    else run = { bundle_sha256: b, run_id: r };
  }
  const i = params.get("i");
  let row: number | null = null;
  if (i !== null) {
    if (/^\d{1,9}$/.test(i)) row = Number(i);
    else problems.push(`i (row) must be a non-negative integer; found "${truncate(i)}"`);
  }
  const p = params.get("p");
  let phase: Phase | null = null;
  if (p !== null) {
    if ((PHASES as readonly string[]).includes(p)) phase = p as Phase;
    else problems.push(`p (phase) must be before or after; found "${truncate(p)}"`);
  }
  const d = params.get("d");
  let depth: Depth | null = null;
  if (d !== null) {
    if ((DEPTHS as readonly string[]).includes(d)) depth = d as Depth;
    else problems.push(`d (depth) must be one of ${DEPTHS.join(", ")}; found "${truncate(d)}"`);
  }
  const e = params.get("evidence");
  let evidence: string | null = null;
  if (e !== null) {
    if (isSafeRelativePath(e)) evidence = e;
    else problems.push("evidence must be a relative path on this origin");
  }
  const k = params.get("k");
  let condition: string | null = null;
  if (k !== null) {
    if (/^[A-Za-z0-9._-]{1,128}$/.test(k)) condition = k;
    else problems.push(`k (condition) must be a plain identifier; found "${truncate(k)}"`);
  }
  const part = params.get("part");
  const partModel = params.get("pm");
  if (part !== null && !/^[A-Za-z0-9_.-]{1,128}$/.test(part)) problems.push("part must be a model body name");
  if (partModel !== null && (!isSha256(partModel) || part === null)) problems.push("pm needs a part and its model SHA-256");
  const study = parseStudyRoute(params, problems);
  return { generation, caseKey, run, row, phase, depth, evidence, condition, part, partModel, study, problems };
}

export function formatLocator(moment: Moment, depth: Depth, evidence: string | null, extra: Record<string, string> = {}, condition: string | null = null): string {
  const params = new URLSearchParams();
  if (evidence !== null && evidence !== DEFAULT_EVIDENCE) params.set("evidence", evidence);
  params.set("g", moment.generation_sha256);
  params.set("c", moment.case_key);
  params.set("b", moment.run.bundle_sha256);
  params.set("r", moment.run.run_id);
  params.set("i", String(moment.row_index));
  params.set("p", moment.phase);
  params.set("d", depth);
  if (condition !== null) params.set("k", condition);
  for (const [k, v] of Object.entries(extra)) params.set(k, v);
  return `?${params.toString()}`;
}

function truncate(s: string): string {
  return s.length > 24 ? `${s.slice(0, 24)}…` : s;
}
