import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ProjectionReview from "../src/qualification/ProjectionReview";
import { parseProjection, type CheckSummary, type DependencyExplanation, type MeasurementReview } from "../src/qualification/projection";
import type { Imported, ProjectionSelection } from "../src/qualification/projectionClient";
const open = vi.hoisted(() => vi.fn());
vi.mock("../src/qualification/projectionClient", () => ({ openProjection: open, readExampleBytes: async () => new Uint8Array([1]) }));
const record = (name: string, folder = "public/examples/check-records"): Imported => ({ value: parseProjection(new Uint8Array(readFileSync(resolve(folder, name)))), sha256: name, name });
const chosen = (name = "literal-zero", measurement = true): ProjectionSelection => ({ summary: record(`${name}.summary.json`) as Imported<CheckSummary>, explanation: record(`${name}.explanation.json`) as Imported<DependencyExplanation>, measurement: measurement ? record(`${name}.measurement.json`) as Imported<MeasurementReview> : null, example: null });
let root: Root | null = null, host: HTMLDivElement;
beforeEach(() => { open.mockReset(); open.mockImplementation(async (file: File) => record(file.name)); vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true }))); });
afterEach(async () => { await act(async () => root?.unmount()); root = null; host?.remove(); vi.unstubAllGlobals(); });
async function mount(initial: ProjectionSelection | null = null, hash = "#view=checks") {
  history.replaceState(null, "", `/${hash}`); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  function Harness() { const [selection, setSelection] = useState(initial); return <ProjectionReview selection={selection} setSelection={setSelection} archives={vi.fn()} />; }
  await act(async () => root!.render(<Harness />));
}
const button = (text: string) => [...host.querySelectorAll("button")].find(b => b.textContent?.includes(text))!;
const click = async (node: Element) => act(async () => node.dispatchEvent(new MouseEvent("click", { bubbles: true })));
const select = async (selector: string, value: string) => act(async () => { const node = host.querySelector<HTMLSelectElement>(selector)!; node.value = value; node.dispatchEvent(new Event("change", { bubbles: true })); });
const importFiles = async (...names: string[]) => act(async () => { const input = host.querySelector<HTMLInputElement>('input[type="file"]')!; Object.defineProperty(input, "files", { configurable: true, value: names.map(name => new File(["{}"], name)) }); input.dispatchEvent(new Event("change", { bubbles: true })); });
it("traces a scoring change through keyboard-accessible native nodes", async () => {
  await mount(null, "#view=checks&record=scoring-change");
  expect(host.querySelector(".dependency-selected strong")?.textContent).toBe("score");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("No reason codes were recorded");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("Changed in the recorded comparison");
  await click(host.querySelector('button[aria-label="Inspect check observe"]')!);
  expect(host.querySelector(".dependency-selected strong")?.textContent).toBe("observe");
  expect(host.querySelector(".dependency-actions")?.textContent).toContain("Reused · completed");
  expect(document.activeElement).toBe(host.querySelector(".dependency-selector select"));
  expect(host.querySelector("canvas")).toBeNull();
});
it("shows unattempted planned reuse without presenting consumed evidence", async () => {
  await mount(null, "#view=checks&record=unattempted-reuse");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("Reuse was planned, but never attempted");
  expect(host.textContent).toContain("0 / 4 complete");
  expect(host.querySelector(".projection-verdict")?.textContent).toContain("Measurement review not attached");
});
it("keeps historical completed requirements separate from a new run instruction", async () => {
  const s = chosen(); await mount(s); await select(".dependency-selector select", s.explanation!.value.decisions[0]!.id);
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("does not request another run");
  expect(host.querySelector(".dependency-requirement")?.textContent).toContain("completed");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("Deployment: unresolved");
});
it("shows an old unknown now bound without calling the current input missing", async () => {
  const folder = "../../work/experiments/check-explanation-2026-11-16/examples", name = "calibration_rebound_pin";
  const s: ProjectionSelection = { summary: record(`${name}.summary.json`, folder) as Imported<CheckSummary>, explanation: record(`${name}.explanation.json`, folder) as Imported<DependencyExplanation>, measurement: null, example: null };
  await mount(s); await select(".dependency-selector select", "confirm");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("The current input is bound");
  await select(".dependency-selector select", "confirmation");
  expect(host.querySelector(".dependency-actions")?.textContent).toContain("Previously unknown");
  expect(host.querySelector(".dependency-actions")?.textContent).toContain("Bound to bytes");
});
it("separates absent prior declaration and model changes from byte equivalence", async () => {
  const s = chosen(), input = s.explanation!.value.inputs[0]!; input.previousPresent = false; input.previousSha = null; s.explanation!.value.modelChanged = true;
  await mount(s); await select(".dependency-selector select", input.id);
  expect(host.textContent).toContain("Equal input hashes do not establish equivalent meaning");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("Not previously declared");
});
it("preserves deliberately withheld diagnostics in a locally imported record", async () => {
  await mount(chosen("missing-history", false)); await select(".dependency-selector select", "observe");
  expect(host.querySelector(".dependency-reading")?.textContent).toContain("Diagnostic detail withheld");
  expect(host.textContent).not.toContain("removed historical observation artifact");
  expect(host.textContent).not.toContain("/Users/"); expect(host.querySelector(".projection-author")).toBeNull();
});
it.each(["literal-zero", "nonzero-refused"])("imports all three %s records in any file order", async name => {
  await mount(); await importFiles(`${name}.measurement.json`, `${name}.explanation.json`, `${name}.summary.json`);
  expect(host.querySelector(".dependency-inspector")).not.toBeNull();
  expect(host.querySelector(".projection-verdict h2")?.textContent).toBe(name === "literal-zero" ? "The recorded relation holds" : "No complete assessment");
  if (name === "nonzero-refused") { expect(host.textContent).toContain("not attempted"); expect(host.textContent).not.toContain("1e-400"); }
  expect(host.querySelector(".projection-verdict dl")?.textContent).toContain("DeploymentUnresolved");
});
it.each(["measurement", "explanation"])("attaches %s first and preserves it when adding the other companion", async first => {
  await mount(); await importFiles("literal-zero.summary.json", `literal-zero.${first}.json`);
  await importFiles(`literal-zero.${first === "measurement" ? "explanation" : "measurement"}.json`);
  expect(host.querySelector(".dependency-inspector")).not.toBeNull(); expect(host.querySelector(".projection-verdict h2")?.textContent).toBe("The recorded relation holds");
});
it("detaches an explanation without losing the measured relation, then clears both for a new summary", async () => {
  await mount(chosen()); await click(button("Detach explanation"));
  expect(host.querySelector(".dependency-inspector")).toBeNull(); expect(host.textContent).toContain("The recorded relation holds");
  expect(document.activeElement).toBe(host.querySelector("h1"));
  await importFiles("nonzero-refused.summary.json");
  expect(host.textContent).toContain("Measurement review not attached"); expect(host.querySelector(".dependency-inspector")).toBeNull();
});
it("refuses a mismatched explanation while preserving both current companions", async () => {
  await mount(chosen()); await importFiles("scoring-change.explanation.json");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("does not match");
  expect(host.textContent).toContain("The recorded relation holds"); expect(host.querySelector(".dependency-inspector")).not.toBeNull();
});
it("preserves a valid new summary when its malformed companion fails", async () => {
  await mount(chosen()); open.mockImplementation(async (file: File) => { if (file.name === "bad.json") throw new Error("The declared graph contains a cycle."); return record(file.name); });
  await importFiles("nonzero-refused.summary.json", "bad.json");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("cycle"); expect(host.textContent).toContain("Measurement review not attached");
  expect(host.querySelector(".dependency-inspector")).toBeNull(); expect(host.querySelector(".projection-verdict dl")?.textContent).toContain("Executionunresolved");
});
it("refuses duplicate companion roles without altering selection", async () => {
  await mount(chosen()); await importFiles("literal-zero.explanation.json", "nonzero-refused.explanation.json");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("duplicate roles"); expect(host.textContent).toContain("The recorded relation holds");
});
it("prevents a late explanation from populating a newer example", async () => {
  let finish!: (value: Imported) => void;
  open.mockImplementation((file: File) => file.name === "scoring-change.explanation.json" ? new Promise<Imported>(resolve => { finish = resolve; }) : Promise.resolve(record(file.name)));
  await mount(); await select(".projection-load select", "scoring-change"); await select(".projection-load select", "nonzero-refused");
  await act(async () => finish(record("scoring-change.explanation.json")));
  expect(host.querySelector(".projection-verdict h2")?.textContent).toBe("No complete assessment"); expect(host.querySelector(".dependency-selected")?.textContent).toContain("Not attempted");
});
it("cancels pending companion work when the user detaches", async () => {
  await mount(chosen()); let finish!: (value: Imported) => void;
  open.mockImplementation(() => new Promise<Imported>(resolve => { finish = resolve; }));
  await importFiles("literal-zero.explanation.json"); const signal = open.mock.calls[0]![1] as AbortSignal;
  await click(button("Detach explanation")); await act(async () => finish(record("literal-zero.explanation.json")));
  expect(signal.aborted).toBe(true); expect(host.querySelector(".dependency-inspector")).toBeNull(); expect(host.textContent).toContain("The recorded relation holds");
});
it("restores a dependency example on back navigation and provides all three readback commands", async () => {
  await mount(chosen()); await click(button("Source & CLI"));
  expect(host.querySelectorAll(".projection-command")).toHaveLength(3); expect(host.querySelector("dialog")?.textContent).toContain("explain-check-bundle");
  const dialog = host.querySelector("dialog")!; await act(async () => dialog.dispatchEvent(new Event("cancel", { cancelable: true })));
  history.replaceState(null, "", "/#view=checks&record=scoring-change"); await act(async () => window.dispatchEvent(new PopStateEvent("popstate")));
  expect(host.querySelector(".dependency-inspector")).not.toBeNull(); expect(host.textContent).toContain("Measurement review not attached");
});
it("keeps valid long identifiers readable through native node selection", async () => {
  const s = chosen(), name = "a".repeat(80), old = s.explanation!.value.inputs[0]!.id;
  const rename = (value: any): any => typeof value === "string" ? value === old ? name : value : Array.isArray(value) ? value.map(rename) : value && typeof value === "object" ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, rename(item)])) : value;
  // Deliberate display control, never shipped as an experimental outcome.
  s.explanation!.value = rename(s.explanation!.value); await mount(s);
  await select(".dependency-selector select", name);
  expect(host.querySelector(".dependency-selected strong")?.textContent).toBe(name);
  expect(host.querySelector(".dependency-selector select")?.getAttribute("disabled")).toBeNull();
});
it("keeps local triple imports out of network requests", async () => {
  await mount(); await importFiles("literal-zero.summary.json", "literal-zero.explanation.json", "literal-zero.measurement.json");
  expect(fetch).not.toHaveBeenCalled(); expect(host.querySelector(".projection-author")).toBeNull();
});
it("retries an unavailable example without silently selecting a substitute", async () => {
  vi.mocked(fetch).mockRejectedValueOnce(new Error("Recorded example unavailable"));
  await mount(null, "#view=checks&record=literal-zero");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("unavailable");
  expect(host.querySelector(".projection-verdict")).toBeNull();
  await click(button("Retry"));
  expect(host.querySelector(".projection-verdict h2")?.textContent).toBe("The recorded relation holds");
  expect(host.querySelector(".dependency-inspector")).not.toBeNull();
});
