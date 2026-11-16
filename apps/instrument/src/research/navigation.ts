import { CATALOG_SHA } from "./catalogPin";
import { CASE_IDS, type CaseId } from "./catalog";

export interface ResearchRoute {
  surface: "home" | "system" | "research" | "lab" | "qualify" | "develop" | "concepts" | "checks";
  caseId: CaseId;
  variant: "original" | "corrected";
  sample: number;
  contextCost: number;
  otherCost: number;
  catalog: string;
  issue: string | null;
}
export function readResearchRoute(
  hash: string,
  hasLabSelection: boolean,
): ResearchRoute {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const route: ResearchRoute = {
    surface: hasLabSelection ? "lab" : "home",
    caseId: "transfer",
    variant: "corrected",
    sample: 0,
    contextCost: 0,
    otherCost: 0,
    catalog: CATALOG_SHA,
    issue: null,
  };
  for (const key of [
    "view",
    "case",
    "variant",
    "sample",
    "catalog",
    "context",
    "work",
  ]) {
    if (p.getAll(key).length > 1)
      return {
        ...route,
        issue: "This link contains conflicting selection parameters.",
      };
  }
  if (!p.has("view")) return route;
  const view = p.get("view");
  if (view !== "home" && view !== "system" && view !== "research" && view !== "lab" && view !== "qualify" && view !== "develop" && view !== "concepts" && view !== "checks")
    route.issue = "This link names an unknown instrument view.";
  else route.surface = view;
  const id = p.get("case");
  if (id !== null) {
    if (CASE_IDS.includes(id as CaseId)) route.caseId = id as CaseId;
    else
      route.issue = "This investigation is not available in this instrument.";
  }
  const variant = p.get("variant");
  if (variant !== null) {
    if (variant === "original" || variant === "corrected")
      route.variant = variant;
    else route.issue = "This source variant is not available.";
  }
  const sample = p.get("sample");
  if (sample !== null) {
    if (/^\d{1,4}$/.test(sample)) route.sample = Number(sample);
    else route.issue = "This link has an invalid sample.";
  }
  const catalog = p.get("catalog");
  if (catalog !== null) {
    if (/^[a-f0-9]{64}$/.test(catalog)) route.catalog = catalog;
    else route.issue = "This link has an invalid evidence identity.";
  }
  for (const [key, field, max, step] of [
    ["context", "contextCost", 0.5, 0.01],
    ["work", "otherCost", 6, 0.1],
  ] as const) {
    const raw = p.get(key);
    if (raw !== null) {
      const value = Number(raw);
      if (
        /^\d+(\.\d{1,2})?$/.test(raw) &&
        value >= 0 &&
        value <= max &&
        Math.abs(value / step - Math.round(value / step)) < 1e-8
      )
        route[field] = value;
      else route.issue = "This link has an invalid hypothetical cost.";
    }
  }
  return route;
}
export function researchHash(route: ResearchRoute): string {
  const p = new URLSearchParams({
    view: route.surface,
    catalog: route.catalog,
  });
  if (route.surface === "research" || route.surface === "lab") {
    p.set("case", route.caseId);
    p.set("variant", route.variant);
    p.set("sample", String(route.sample));
  }
  if (route.caseId === "cost" && (route.surface === "research" || route.surface === "lab")) {
    p.set("context", String(route.contextCost));
    p.set("work", String(route.otherCost));
  }
  return `#${p}`;
}
export function openResearch(surface: ResearchRoute["surface"] = "research"): void {
  window.dispatchEvent(
    new CustomEvent("nisayon:navigate", { detail: surface }),
  );
}
