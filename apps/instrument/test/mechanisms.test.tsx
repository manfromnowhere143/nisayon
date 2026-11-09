import { act } from "react";
import { createRoot } from "react-dom/client";
import { createHash } from "node:crypto";
import { expect, it } from "vitest";
import { discoverStudy, loadStudy, loadStudyReport, type Fields } from "../src/data/study";
import { clockGroups, clockLabel, temporalReport, processorReport, type Opportunity } from "../src/model/mechanisms";
import { initialStudyRoute, parseStudyRoute, studyRouteParams } from "../src/state/studyRoute";
import { ProcessorView, TemporalView } from "../src/ui/MechanismViews";
import { fetchFromDisk } from "./fixture";

const options = { fetch: fetchFromDisk(), digest: async (bytes: ArrayBuffer) => createHash("sha256").update(new Uint8Array(bytes)).digest("hex"), maxBytes: 16 * 1024 * 1024 };
async function report(name: string) {
  const study = await loadStudy(await discoverStudy(undefined, options), undefined, options);
  return (await loadStudyReport(study.reports[name]!, undefined, options)).record;
}

it("admits all 230 temporal assignments and keeps interrupted, temporal and usefulness decisions distinct", async () => {
  const d = temporalReport(await report("temporal"));
  expect(d.populations.reduce((n, p) => n + p.rows.length, 0)).toBe(230);
  expect(d.pairs).toHaveLength(35); expect(d.prefixes).toHaveLength(3);
  expect(d.prefixes.every(p => p.process_outcome === "unknown" && p.assigned_contract === "unresolved")).toBe(true);
  expect(d.prefixes.some(p => p.temporal_contract === "violated")).toBe(true);
  expect(d.populations.flatMap(p => p.rows).every(r => r.robot_task_outcome === "unmeasured")).toBe(true);
});

it("never overlays clocks and preserves single nanoseconds beyond Number's integer precision", () => {
  const opportunity = (value: string, clock = "controller"): Opportunity => ({ input_id: value, at: { value, clock, unit: "ns", exact_integer: true }, observed: [], attempts: [], refusal_reasons: [], counted: null, valid: null, acknowledged: null });
  const rows = [opportunity("9007199254740992"), opportunity("9007199254740993"), opportunity("9007199254740993", "sensor")];
  const groups = clockGroups(rows);
  expect(groups).toHaveLength(2); expect(groups[0]!.items.map(i => i.x)).toEqual([0, 1]); expect(groups[1]!.items[0]!.x).toBe(.5);
  expect(clockLabel(rows[1]!.at)).toBe("9007199254.740993 ms");
  expect(clockLabel(opportunity("-1234567").at)).toBe("−1.234567 ms");
  expect(clockLabel({ value: null, clock: "unknown", unit: "ns", exact_integer: false })).toBe("unrecorded");
});

it("exposes the supported processor mechanism with unresolved deployment and unexecuted re-migration, without model statistics", async () => {
  const record = await report("processor"), d = processorReport(record);
  expect(d.candidates.find(c => c.name === "explicit_override")!.decision.deployment_binding).toBe("unresolved");
  expect(d.candidates.find(c => c.name === "remigration")!.decision.outcome).toBe("unresolved_not_executed");
  expect(d.executions).toHaveLength(9); expect(d.comparison.comparative_value).toBe("not_established");
  const visit = (v: unknown) => { if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v === "object") for (const [k, x] of Object.entries(v)) { expect(["bound_stats", "stats", "mean", "std", "tensor_values"]).not.toContain(k); visit(x); } };
  visit(record);
});

it("fails closed on collapsed unknowns, missing assignments and a promoted authority", async () => {
  const source = await report("temporal");
  const missing = structuredClone(source); (missing.coverage as Fields).assignments = 229;
  expect(() => temporalReport(missing)).toThrow("coverage");
  expect(() => temporalReport({ ...source, execution_connected: true })).toThrow("authority");
  const erased = structuredClone(source) as { populations: { rows: { assigned_usefulness: { rows: Opportunity[] } }[] }[] };
  delete (erased.populations[0]!.rows[0]!.assigned_usefulness.rows[0] as unknown as Fields).valid;
  expect(() => temporalReport(erased)).toThrow("missing valid is not false");
});

it("pins the selected mechanism and opportunity in the same immutable investigation link", () => {
  const route = { ...initialStudyRoute(), view: "temporal" as const, item: "combined_deadline/Y03-fresh-value--selected_combined_deadline/2" };
  const problems: string[] = [];
  expect(parseStudyRoute(new URLSearchParams(studyRouteParams(route)), problems)).toEqual(route); expect(problems).toEqual([]);
});

it("renders recorded software outcomes with unknown robot outcome and no implied execution control", async () => {
  const element = document.createElement("div"); document.body.appendChild(element); const root = createRoot(element);
  try {
    const temporal = await report("temporal"), processor = await report("processor");
    await act(async () => root.render(<TemporalView record={temporal} item={null} onItem={() => {}} />));
    expect(element.textContent).toContain("Robot outcome: unmeasured"); expect(element.textContent).toContain("Execution disconnected");
    await act(async () => root.render(<ProcessorView record={processor} item="C3_remigration" onItem={() => {}} />));
    expect(element.textContent).toContain("This candidate was not executed"); expect(element.textContent).toContain("unresolved");
  } finally { await act(async () => root.unmount()); element.remove(); }
});
