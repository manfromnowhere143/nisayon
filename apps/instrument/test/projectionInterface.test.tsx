import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ProjectionReview from "../src/qualification/ProjectionReview";
import { parseProjection, type CheckSummary, type MeasurementReview } from "../src/qualification/projection";
import type { Imported, ProjectionSelection } from "../src/qualification/projectionClient";
import { readResearchRoute } from "../src/research/navigation";
const open = vi.hoisted(() => vi.fn());
vi.mock("../src/qualification/projectionClient", () => ({ openProjection: open, readExampleBytes: async () => new Uint8Array([1]) }));
const projection = (name: string): Imported => ({ value: parseProjection(new Uint8Array(readFileSync(resolve("public/examples/check-records", name)))), sha256: "a".repeat(64), name });
const chosen = (id = "claim-disagreement"): ProjectionSelection => ({ summary: projection(`${id}.summary.json`) as Imported<CheckSummary>, measurement: id === "acquisition-failed" ? null : projection(`${id}.measurement.json`) as Imported<MeasurementReview>, explanation: null, example: id });
let root: Root | null = null, host: HTMLDivElement;
beforeEach(() => {
  open.mockReset(); open.mockImplementation(async (file: File) => projection(file.name));
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true })));
});
afterEach(async () => { await act(async () => root?.unmount()); root = null; host?.remove(); vi.unstubAllGlobals(); });
async function mount(initial: ProjectionSelection | null = null, hash = "#view=checks") {
  history.replaceState(null, "", `/${hash}`); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  function Harness() { const [selection, setSelection] = useState(initial); return <ProjectionReview selection={selection} setSelection={setSelection} archives={vi.fn()} />; }
  await act(async () => root!.render(<Harness />));
}
const button = (name: string) => [...host.querySelectorAll("button")].find(b => b.textContent?.includes(name))!;
const click = async (node: Element) => act(async () => node.dispatchEvent(new MouseEvent("click", { bubbles: true })));
const choose = async (value: string) => act(async () => { const select = host.querySelector("select")!; select.value = value; select.dispatchEvent(new Event("change", { bubbles: true })); });
const importFiles = async (...names: string[]) => act(async () => {
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { configurable: true, value: names.map(name => new File(["{}"], name)) }); input.dispatchEvent(new Event("change", { bubbles: true }));
});
it("deep-links to an actual mismatch without giving it a scene identity", async () => {
  expect(readResearchRoute("#view=checks", false).surface).toBe("checks");
  await mount(null, "#view=checks&record=claim-disagreement");
  expect(host.querySelector(".projection-verdict h2")?.textContent).toBe("The saved claim disagrees");
  expect(host.querySelector(".projection-claim")?.textContent).toContain("Saved supported");
  expect(host.querySelector(".projection-claim")?.textContent).toContain("Recomputed rejected");
  expect(host.textContent).toContain("not bound to the selected laboratory scene");
  expect(host.textContent).toContain("author description");
});
it("keeps a same-headline disagreement visible", async () => {
  const value = chosen(); value.measurement!.value.recorded = "rejected"; await mount(value);
  expect(host.textContent).toContain("Its headline verdict agrees"); expect(host.textContent).toContain("Disagrees");
});
it("shows absent prior receipts and absent semantic review separately", async () => {
  await mount(chosen("acquisition-failed"));
  expect(host.textContent).toContain("Measurement review not attached"); expect(host.textContent).toContain("0 / 4 complete");
  await click(button("Changes & inputs")); expect(host.querySelector("dialog")?.textContent).toContain("not a tested unchanged deployment");
  expect(host.querySelector("dialog")?.textContent).toContain("input acquisition failed");
});
it("refuses a conflicting local review while preserving the selected summary", async () => {
  await mount(chosen()); await importFiles("recorded-relation.measurement.json");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("does not match");
  expect(host.querySelector(".projection-verdict h2")?.textContent).toContain("saved claim disagrees");
});
it("replaces a summary without carrying forward an unrelated measured review", async () => {
  await mount(chosen()); await importFiles("acquisition-failed.summary.json");
  expect(host.querySelector(".projection-verdict h2")?.textContent).toBe("Measurement review not attached");
  expect(host.querySelector(".projection-claim")).toBeNull(); expect(location.hash).not.toContain("record=");
});
it("does not allow a late case A result to populate case B", async () => {
  let finish!: (value: Imported) => void;
  open.mockImplementation((file: File) => file.name === "claim-disagreement.summary.json" ? new Promise<Imported>(resolve => { finish = resolve; }) : Promise.resolve(projection(file.name)));
  await mount(); await choose("claim-disagreement"); await choose("recorded-relation");
  await act(async () => finish(projection("claim-disagreement.summary.json")));
  expect(host.querySelector(".projection-verdict h2")?.textContent).toBe("The recorded relation holds");
  expect(open.mock.calls[0]![1].aborted).toBe(true);
});
it("cancels an import and keeps the current result readable", async () => {
  await mount(chosen()); open.mockImplementation(() => new Promise(() => {}));
  await choose("recorded-relation"); await click(button("Cancel import"));
  expect(host.querySelector('[role="status"]')).toBeNull(); expect(host.textContent).toContain("The saved claim disagrees");
  expect(open.mock.calls[0]![1].aborted).toBe(true);
});
it("restores example selection on history navigation and rejects conflicting links", async () => {
  await mount(chosen()); history.replaceState(null, "", "/#view=checks&record=incomplete-execution");
  await act(async () => window.dispatchEvent(new PopStateEvent("popstate")));
  expect(host.textContent).toContain("No complete assessment");
  history.replaceState(null, "", "/#view=checks&record=a&record=b");
  await act(async () => window.dispatchEvent(new PopStateEvent("popstate")));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("conflicting example selections");
});
it("retains escaped producer text and source routes without executable markup", async () => {
  const value = chosen(); value.measurement!.value.assessment!.scope = '<img src=x onerror="alert(1)">'; await mount(value);
  await click(button("Measured conditions"));
  expect(host.querySelector("dialog")?.textContent).toContain("<img"); expect(host.querySelector("dialog img")).toBeNull();
});
it("aborts active readers when the view unmounts", async () => {
  open.mockImplementation(() => new Promise(() => {})); await mount(); await choose("claim-disagreement");
  const signal = open.mock.calls[0]![1] as AbortSignal; await act(async () => root!.unmount()); root = null; expect(signal.aborted).toBe(true);
});
it("closes the source dialog through native cancellation and restores its trigger", async () => {
  await mount(chosen()); const trigger = button("Source & CLI"); trigger.focus(); await click(trigger);
  const dialog = host.querySelector("dialog")!;
  expect(dialog.textContent).toContain("claim-disagreement.summary.json");
  expect(dialog.querySelector("input")?.getAttribute("maxlength")).toBe("2048");
  await act(async () => dialog.dispatchEvent(new Event("cancel", { cancelable: true })));
  expect(host.querySelector("dialog")).toBeNull(); expect(document.activeElement).toBe(trigger);
});
