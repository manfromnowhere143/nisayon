import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { axisTicks } from "../src/ui/Lanes";
import { MomentInspection } from "../src/ui/MomentInspection";
import type { InstrumentStore } from "../src/state/store";
import { fetchFromDisk, REPO_ROOT } from "./fixture";
import type { SceneCallbacks } from "../src/scene/renderer";
import type { SpatialLayerState } from "../src/scene/evidenceLayer";
import { decodeVisualAsset } from "../src/scene/visualCodec";
import { VISUAL_ASSET } from "../src/scene/visualAssetPin";

// Exercise the detailed-scene interaction contract without claiming GPU paint.
// The old SVG substitution is intentionally unavailable in the application.
const scene = vi.hoisted(() => ({ spatial: null as SpatialLayerState | null, pick: vi.fn(() => 14), orbit: vi.fn(), zoom: vi.fn(), resetView: vi.fn(), setSetting: vi.fn(), setBounds: vi.fn() }));
const nativeAsset = decodeVisualAsset(JSON.parse(readFileSync(join(REPO_ROOT, VISUAL_ASSET.path), "utf8")), VISUAL_ASSET.sha256);
vi.mock("../src/scene/visualAssets", async (original) => ({
  ...(await original<typeof import("../src/scene/visualAssets")>()),
  loadVisualAsset: () => Promise.resolve(nativeAsset),
}));
vi.mock("../src/scene/renderer", async (original) => ({
  ...(await original<typeof import("../src/scene/renderer")>()),
  createSceneRenderer: (_canvas: unknown, _ground: unknown, callbacks: SceneCallbacks) => {
    let presented = false;
    return {
      setModel: vi.fn(), setPrimary: vi.fn(), setGhost: vi.fn(), setBounds: scene.setBounds, setSetting: scene.setSetting,
      setCollision: vi.fn(), setView: vi.fn(), setGround: vi.fn(), resize: vi.fn(), dispose: vi.fn(),
      setSpatial: (state: SpatialLayerState) => { scene.spatial = state; },
      pick: scene.pick, orbit: scene.orbit, zoom: scene.zoom, resetView: scene.resetView,
      present: () => { if (!presented) { presented = true; callbacks.onFirstFrame(); } },
    };
  },
}));

const options = { fetch: fetchFromDisk(), digest: async (bytes: ArrayBuffer) => createHash("sha256").update(Buffer.from(new Uint8Array(bytes))).digest("hex"), maxBytes: 16 * 1024 * 1024 };
let root: Root | null = null, container: HTMLDivElement;
const store = () => (window as unknown as { __nisayon: { store: InstrumentStore } }).__nisayon.store;
const ready = () => { const screen = store().getState().screen; if (screen.kind !== "ready") throw Error("not ready"); return screen; };
async function waitFor(test: () => boolean) { const start = Date.now(); while (!test()) { if (Date.now() - start > 5000) throw Error("DOM did not settle"); await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); }); } }
async function mount(search = "?evidence=fixtures/ui/recorded/D03-observation-backlog/evidence.json&i=30&p=before") {
  localStorage.clear();
  window.history.replaceState(null, "", search);
  container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
  await act(async () => { root!.render(<App loader={options} />); });
  await waitFor(() => container.querySelector(".transport") !== null);
  await workspace("Evidence");
}
async function click(element: Element) { await act(async () => { element.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); }
async function workspace(label: string) {
  const close = container.querySelector('.glass-card-close');
  if (close) await click(close);
  await click([...container.querySelectorAll('.workspace-actions button')].find(b => b.textContent?.startsWith(label))!);
}
async function choosePart(label: string) {
  await workspace("Scene");
  await click(container.querySelector('[aria-label="Inspect model body"]')!);
  await click([...document.querySelectorAll('[role="option"]')].find((option) => option.textContent?.replace("✓", "") === label)!);
  await click(container.querySelector(".glass-card-close")!);
}
async function choose(label: string, option: string) {
  await click(container.querySelector(`[aria-label="${label}"]`)!);
  await click([...document.querySelectorAll('[role="option"]')].find(e => e.textContent?.replace("✓", "") === option)!);
}
afterEach(async () => { await act(async () => { root?.unmount(); }); root = null; container?.remove(); vi.restoreAllMocks(); });

it.each(["Evidence", "Moment", "Scene", "Sources"])("opens %s with pointer title focus and retains the exact recorded moment", async label => {
  await mount();
  await click(container.querySelector(".glass-card-close")!);
  const moment = { ...ready().moment };
  const opener = [...container.querySelectorAll<HTMLButtonElement>(".workspace-actions button")].find(button => button.textContent?.startsWith(label))!;
  await act(async () => {
    opener.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    opener.focus();
    opener.dispatchEvent(new MouseEvent("click", { detail: 1, bubbles: true }));
  });
  const title = document.activeElement as HTMLHeadingElement;
  expect(title.tagName).toMatch(/^H[1-6]$/);
  expect(container.querySelector("dialog")!.contains(title)).toBe(true);
  expect(title.dataset.pointerFocus).toBe("true");
  expect(ready().moment).toEqual(moment);
  await act(async () => title.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true })));
  expect(title.dataset.pointerFocus).toBeUndefined();
  await click(container.querySelector(".glass-card-close")!);
  expect(document.activeElement).toBe(opener);
  expect(ready().moment).toEqual(moment);
});

it("keeps recording selection available inside Workspace controls", async () => {
  await mount();
  await click(container.querySelector(".glass-card-close")!);
  const moment = { ...ready().moment };
  await waitFor(() => !!container.querySelector('.identity > .case-select button'));
  const current = container.querySelector('.identity > .case-select button')!.textContent;
  await click(container.querySelector('.workspace-menu')!);
  const choice = container.querySelector<HTMLButtonElement>('dialog .workspace-recording .choice-trigger')!;
  expect(choice).not.toBeNull();
  expect(choice.textContent).toBe(current);
  await click(choice);
  expect(document.querySelectorAll('[role="option"]').length).toBeGreaterThan(0);
  expect(ready().moment).toEqual(moment);
});

it("changes architecture and camera by keyboard without changing the recorded source or moment, and honours reduced motion", async () => {
  await mount();
  await click(container.querySelector(".glass-card-close")!);
  const moment = { ...ready().moment }, record = ready().run.record;
  await act(async () => store().setReducedMotion(true));
  const controls = [...container.querySelectorAll<HTMLButtonElement>(".view-controls button")];
  await click(controls.find(button => button.textContent === "Hall")!);
  expect(scene.setSetting).toHaveBeenLastCalledWith("architecture", "lab");
  expect(scene.setBounds.mock.calls.at(-1)?.[1]).toBe(false);
  await click(controls.find(button => button.textContent === "Source room")!);
  expect(scene.setSetting).toHaveBeenLastCalledWith("source", "lab");
  const stage = container.querySelector<HTMLElement>(".scene-box")!;
  expect(stage.tabIndex).toBe(0);
  await act(async () => {
    stage.focus();
    for (const key of ["ArrowRight", "+", "Home"]) stage.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
  });
  expect(scene.orbit).toHaveBeenLastCalledWith(.12, 0);
  expect(scene.zoom).toHaveBeenLastCalledWith(.88);
  expect(scene.resetView).toHaveBeenCalled();
  expect(ready().moment).toEqual(moment);
  expect(ready().run.record).toBe(record);
});

it.each([
  ["Gripper command lane", ".lane-executed", "before"],
  ["Cube height lane", ".lane-executed", "after"],
  ["Observation age lane", ".lane-executed", "before"],
  ["Policy memory lane", ".mem-cell", "after"],
] as const)("selects the drawn sample and phase on %s, including a CSS-scaled plot", async (label, mark, phase) => {
  await mount();
  await act(async () => store().toggleLanes());
  const svg = container.querySelector<SVGSVGElement>(`svg[aria-label^="${label}"]`)!;
  const width = Number(svg.getAttribute("width"));
  vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({ left: 11, top: 0, width: width * 2, height: 100, right: 11 + width * 2, bottom: 100, x: 11, y: 0, toJSON() {} });
  let localX: number;
  if (mark === ".mem-cell") { const cell = svg.querySelectorAll(mark)[29]!; localX = Number(cell.getAttribute("x")) + Number(cell.getAttribute("width")) / 2; }
  else localX = Number(svg.querySelector(mark)!.getAttribute("d")!.match(/[ML]([^,]+),[\d.-]+/g)![29]!.slice(1).split(",")[0]);
  await act(async () => { store().play(); svg.dispatchEvent(new MouseEvent("pointerdown", { clientX: 11 + 2 * localX, bubbles: true })); });
  expect(ready().moment).toMatchObject({ row_index: 29, phase });
  expect(store().getState().playing).toBe(false);
  expect(new URLSearchParams(location.search).get("p")).toBe(phase);
  expect(svg.getAttribute("role")).toBe("slider");
  await act(async () => svg.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true })));
  expect(ready().moment).toMatchObject({ row_index: 30, phase });
  expect(svg.getAttribute("aria-valuenow")).toBe("30");
});

it("exposes exact D03 observations, groups six matching stamps and keeps scene paths in the past", async () => {
  await mount();
  const spatialButton = Array.from(container.querySelectorAll(".section-tab")).find((button) => button.textContent === "Spatial")!;
  await click(spatialButton);
  expect(container.querySelector(".spatial-metrics")!.textContent).toContain("17.529 mm");
  expect(container.querySelector(".spatial-metrics")!.textContent).toContain("150.000 ms");
  expect(scene.spatial?.options.observations).toBe(true);
  expect(scene.spatial?.row?.row_index).toBe(30);
  await workspace("Scene");
  const pathButton = Array.from(container.querySelectorAll(".overlay-tools button")).find((button) => button.textContent === "Path")!;
  await click(pathButton);
  await workspace("Evidence");
  expect(scene.spatial!.count - scene.spatial!.start).toBeLessThanOrEqual(42);
  await choose("Configuration path history", "Full recorded history");
  expect(scene.spatial!.count - scene.spatial!.start).toBe(61);
  await choose("Spatial detail", "Acquisition");
  expect(container.querySelectorAll(".capture-intervals [data-capture]")).toHaveLength(1);
  expect(container.querySelector(".capture-intervals [data-capture]")?.getAttribute("data-capture")).toBe("1.350000000000001");
  expect(container.querySelector(".acquisition-components")!.textContent).toContain("6 components");
  await choose("Spatial detail", "Comparison");
  await click(Array.from(container.querySelectorAll(".spatial-actions button")).find((button) => button.textContent?.startsWith("Go to consumed"))!);
  expect(ready().moment).toMatchObject({ row_index: 27, phase: "before" });
});

it("pins a part to its model, restores it from history and retains the camera and moment across run switches", async () => {
  await mount();
  const moment = ready().moment, view = store().getState().view;
  await choosePart("Left finger");
  const partUrl = store().currentUrl();
  expect(new URL(partUrl).searchParams.get("part")).toBe("gripper0_leftfinger");
  expect(new URL(partUrl).searchParams.get("pm")).toBe(ready().run.record.model!.sha256);
  expect(ready().moment).toEqual(moment);
  expect(store().getState().view).toBe(view);
  expect(scene.spatial?.selectedBody).toBe(14);
  await act(async () => store().selectRun(ready().caseRecord.runs.find((run) => run.role === "reference")!.run));
  await waitFor(() => ready().pendingRun === null);
  expect(store().getState().part?.name).toBe("gripper0_leftfinger");
  await choosePart("Cube");
  await act(async () => { window.history.replaceState(null, "", partUrl); store().handlePopState(); });
  await waitFor(() => ready().pendingRun === null);
  expect(store().getState().part?.name).toBe("gripper0_leftfinger");
  expect(ready().moment).toEqual(moment);
  expect(store().getState().view).toBe(view);
});

it("restores a selected body from a shared link and clears a mismatched model pin with a note", async () => {
  await mount("?evidence=fixtures/ui/recorded/D03-observation-backlog/evidence.json&i=30&p=before&part=robot0_link4");
  expect(store().getState().part?.name).toBe("robot0_link4");
  expect(container.querySelector(".spatial-heading h2")?.textContent).toBe("Arm link 4");
  expect(container.querySelector('[aria-label="Coordinate source"]')?.textContent).toBe("Body origin");
  const url = new URL(store().currentUrl()); url.searchParams.set("pm", "0".repeat(64));
  await act(async () => { window.history.replaceState(null, "", url); store().handlePopState(); });
  expect(store().getState().part).toBeNull();
  expect(container.querySelector(".selection-note")?.textContent).toContain("not bound to this model");
  expect(ready().moment.row_index).toBe(30);
});

it("selects a body through the detailed scene picker but never picks after an orbit gesture", async () => {
  await mount();
  await click(container.querySelector(".glass-card-close")!);
  const box = container.querySelector<HTMLElement>(".scene-box")!;
  box.setPointerCapture = vi.fn();
  vi.spyOn(box, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, width: 320, height: 320, right: 320, bottom: 320, x: 0, y: 0, toJSON() {} });
  const body = container.querySelector('.scene-canvas')!;
  const pointer = (name: string, x: number) => new MouseEvent(name, { bubbles: true, clientX: x, clientY: 10, button: 0 });
  await act(async () => { body.dispatchEvent(pointer("pointerdown", 10)); box.dispatchEvent(pointer("pointerup", 10)); });
  expect(store().getState().part?.name).toBe("gripper0_leftfinger");
  await act(async () => { store().selectPart(null); body.dispatchEvent(pointer("pointerdown", 10)); box.dispatchEvent(pointer("pointermove", 30)); box.dispatchEvent(pointer("pointerup", 30)); });
  expect(store().getState().part).toBeNull();
});


it("keeps temporal tick labels apart at phone and desktop widths without hiding recording endpoints", () => {
  for (const width of [240, 390, 900]) for (const end of [0.05, 2.23, 20]) {
    const ticks = axisTicks(end, width);
    expect(ticks[0]).toBe(0); expect(ticks.at(-1)).toBe(end);
    for (let i = 1; i < ticks.length; i++) expect((ticks[i]! - ticks[i - 1]!) / end * (width - 20)).toBeGreaterThanOrEqual(47.99);
  }
});

it("inspects capture, command and result at one unchanged moment, then opens the real comparison", async () => {
  await mount();
  await click(container.querySelector(".glass-card-close")!);
  const open = container.querySelector<HTMLButtonElement>(".scene-inspect-action")!;
  open.focus();
  const moment = ready().moment, view = store().getState().view, focus = store().getState().sceneFocus;
  await act(async () => store().play());
  await click(open);
  expect(store().getState().playing).toBe(false);
  const panel = container.querySelector(".moment-inspection")!;
  expect(panel.textContent).toContain("150.000 ms");
  expect(panel.textContent).toContain("17.529 mm");
  expect(panel.textContent).toContain("6 components share the capture stamp");
  expect(panel.querySelectorAll("[data-capture]")).toHaveLength(1);
  expect(panel.querySelector(".moment-clock svg")?.getAttribute("aria-label")).toContain("1.350000000000001 s");
  expect(scene.spatial?.options.observations).toBe(true);
  await click(Array.from(panel.querySelectorAll(".inspection-steps button")).find((b) => b.textContent?.includes("Command"))!);
  expect(panel.textContent).toContain("Intended");
  expect(panel.textContent).toContain("Executed");
  expect(scene.spatial?.options.observations).toBe(false);
  await click(Array.from(panel.querySelectorAll(".inspection-steps button")).find((b) => b.textContent?.includes("Result"))!);
  expect(panel.textContent).toContain("Whole-run task outcome: completed");
  expect(panel.textContent).toContain("height condition does not hold at this sample");
  expect(ready().moment).toEqual(moment);
  expect(store().getState().view).toBe(view); expect(store().getState().sceneFocus).toBe(focus);
  const source = panel.querySelector<HTMLAnchorElement>(".inspection-source a")!;
  expect(source.href).toContain(ready().run.record.samples.sha256);
  await click(Array.from(panel.querySelectorAll(".inspection-actions button")).find((b) => b.textContent === "Compare recordings")!);
  expect(ready().depth).toBe("fork"); expect(ready().moment).toEqual(moment);
  expect(container.querySelector(".moment-inspection")).toBeNull();
  await click(open);
  await act(async () => container.querySelector(".moment-inspection h2")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  expect(container.querySelector(".moment-inspection")).toBeNull();
  expect(document.activeElement === open).toBe(true);
});

it("returns a phone inspection to its evidence pane and opening control", async () => {
  const original = window.matchMedia;
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({ ...original(query), matches: query.includes("max-width") }));
  await mount();
  // The centered evidence surface is already open through its workspace control.
  const opener = Array.from(container.querySelectorAll<HTMLButtonElement>(".finding button")).find((button) => button.textContent === "Inspect this moment")!;
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("evidence");
  await click(opener);
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("evidence");
  await click(container.querySelector('[aria-label="Close moment inspection"]')!);
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("evidence");
  expect(document.activeElement === opener).toBe(true);
});

it("makes a phone part selection visible on the scene and opens its actual details without moving the camera", async () => {
  const original = window.matchMedia;
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({ ...original(query), matches: query.includes("max-width") }));
  await mount();
  const moment = ready().moment, view = store().getState().view;
  await choosePart("Arm link 4");
  expect(container.querySelector(".scene-part-cue")).toBeNull();
  expect(container.querySelector(".selected-part-control")?.textContent).toContain("Arm link 4");
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("scene");
  const details = container.querySelector<HTMLButtonElement>('[aria-label="Show selected part details"]')!;
  expect(details.closest(".scene-box")).toBeNull();
  details.focus();
  const canvas = container.querySelector(".scene-box");
  await click(details);
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("evidence");
  expect(container.querySelector(".spatial-heading h2")?.textContent).toBe("Arm link 4");
  expect(container.querySelector('[aria-label="Spatial detail"]')?.textContent).toBe("Coordinates");
  expect(document.activeElement).toBe(container.querySelector(".spatial-heading h2"));
  expect(ready().moment).toEqual(moment); expect(store().getState().view).toBe(view);
  await click(container.querySelector(".glass-card-close")!);
  expect(document.activeElement).toBe(details);
  expect(container.querySelector(".scene-box")).toBe(canvas);
  expect(ready().moment).toEqual(moment); expect(store().getState().view).toBe(view);
});

it("shows missing capture data as unavailable rather than a zero-age or zero-distance observation", async () => {
  await mount();
  const { run, generation, caseRecord, moment } = ready();
  const rows = [...run.samples.rows];
  rows[moment.row_index] = { ...rows[moment.row_index]!, observation_age_s: null, consumed_observation_capture_sim_time_s: null, consumed_acquisition: null, observation: null, captured_observation: null };
  await act(async () => root!.render(<MomentInspection run={{ ...run, samples: { ...run.samples, rows } }} generation={generation} caseRecord={caseRecord} moment={moment} step="capture" onStep={vi.fn()} target="eef" onTarget={vi.fn()} onClose={vi.fn()} onCompare={vi.fn()} onDecision={vi.fn()} />));
  expect(container.querySelector(".inspection-measures")!.textContent).not.toContain("0.000");
  expect(container.querySelector(".inspection-measures")!.textContent).toContain("Not recorded");
  expect(container.querySelector(".moment-clock svg")!.getAttribute("aria-label")).toContain("capture unavailable");
  expect(container.querySelector(".inspection-explanation")!.textContent).toContain("observation pair is unavailable");
});
