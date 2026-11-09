import { isSha256 } from "../model/decode";
import type { FileRef } from "../model/types";

export const STUDY_VIEWS = ["trials", "temporal", "processor", "external", "decision_case", "declaration_score", "recovery"] as const;
export const STUDY_SECTIONS = ["decision", "pairs", "executions", "diagnostics", "declaration", "costs", "recovery"] as const;
export interface StudyRoute {
  open: boolean;
  pin: FileRef | null;
  trial: string;
  view: typeof STUDY_VIEWS[number];
  section: typeof STUDY_SECTIONS[number];
  pair: string | null;
  execution: string | null;
  item: string | null;
}
export const initialStudyRoute = (trial = ""): StudyRoute => ({ open: true, pin: null, trial, view: "trials", section: "decision", pair: null, execution: null, item: null });

export function parseStudyRoute(params: URLSearchParams, problems: string[]): StudyRoute | null {
  if (!["study", "study_bytes", "trial", "study_view", "study_section", "pair", "execution", "study_open", "study_item"].some(k => params.has(k))) return null;
  const route = initialStudyRoute(params.get("trial") ?? "");
  const sha = params.get("study"), length = params.get("study_bytes");
  if (sha !== null || length !== null) {
    if (!sha || !isSha256(sha) || !length || !/^[1-9]\d{0,7}$/.test(length) || Number(length) > 16 * 1024 * 1024) problems.push("Study link needs its generation SHA-256 and valid byte length.");
    else route.pin = { path: `generations/${sha}.json`, sha256: sha, byte_length: Number(length), media_type: null, kind: null };
  }
  if (route.trial && !/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/[AB]$/.test(route.trial)) problems.push("Study trial must identify comparison, case and arm.");
  const view = params.get("study_view"), section = params.get("study_section"), open = params.get("study_open");
  if (view !== null && !(STUDY_VIEWS as readonly string[]).includes(view)) problems.push("Unknown Study view.");
  else if (view !== null) route.view = view as StudyRoute["view"];
  if (section !== null && !(STUDY_SECTIONS as readonly string[]).includes(section)) problems.push("Unknown Study section.");
  else if (section !== null) route.section = section as StudyRoute["section"];
  if (open !== null && open !== "0" && open !== "1") problems.push("Study open state must be 0 or 1.");
  route.open = open !== "0";
  route.pair = params.get("pair"); route.execution = params.get("execution");
  route.item = params.get("study_item");
  if (route.item !== null && !/^[A-Za-z0-9._/-]{1,300}$/.test(route.item)) problems.push("Invalid retained mechanism selection.");
  if (route.pair !== null && !isSha256(route.pair)) problems.push("Study pair must use its complete identity digest.");
  if (route.execution !== null && !/^[A-Za-z0-9._-]{1,180}$/.test(route.execution)) problems.push("Invalid retained execution identifier.");
  return route;
}

export function studyRouteParams(route: StudyRoute | null): Record<string, string> {
  if (!route) return {};
  return {
    ...(route.pin ? { study: route.pin.sha256, study_bytes: String(route.pin.byte_length) } : {}),
    trial: route.trial, study_view: route.view, study_section: route.section, study_open: route.open ? "1" : "0",
    ...(route.pair ? { pair: route.pair } : {}), ...(route.execution ? { execution: route.execution } : {}),
    ...(route.item ? { study_item: route.item } : {}),
  };
}
