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
const scene = vi.hoisted(() => ({ spatial: null as SpatialLayerState | null, pick: vi.fn(() => ({ kind: "body", body: 14 } as import("../src/scene/picking").ScenePick)), orbit: vi.fn(), zoom: vi.fn(), resetView: vi.fn(), setSetting: vi.fn(), setBounds: vi.fn() }));
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
      setWorkstation: vi.fn(), setContact: vi.fn(), setCollision: vi.fn(), setView: vi.fn(), setGround: vi.fn(), resize: vi.fn(), dispose: vi.fn(),
      setSpatial: (state: SpatialLayerState) => { scene.spatial = state; callbacks.onPartAnchor?.(state.selectedBody === null ? null : { bodyId: state.selectedBody, x: 590, y: 350, width: 1024, height: 768, visible: true, body: [{ left: 470, right: 610, top: 250, bottom: 500 }] }); },
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
  await waitFor(() => container.querySelector(".scene-playback") !== null);
  await workspace("Evidence");
}
async function click(element: Element) { await act(async () => { element.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); }
function opener(label: string): HTMLButtonElement {
  const selector = label === "Evidence" ? ".scene-evidence-control" : label === "Moment" ? ".scene-moment-control" : label === "Scene" ? ".scene-access button" : '.workspace-tools-list button[aria-label^="Generation"]';
  return container.querySelector<HTMLButtonElement>(selector)!;
}
async function workspace(label: string) {
  const close = container.querySelector('.scene-detail-heading > button');
  if (close) await click(close);
  if (label === "Sources") {
    await click(container.querySelector('.workspace-menu')!);
    await click(container.querySelector('[aria-label="Tools"]')!);
  }
  await click(opener(label));
  if (label === "Scene") await click([...container.querySelectorAll(".scene-framing-secondary button")].find(b => b.textContent === "Adjust view")!);
  if (label === "Evidence" && container.querySelector('.case-brief')) {
    await click(container.querySelector('.case-brief-sources button')!);
    await click([...container.querySelectorAll('.case-brief button')].find(button => button.textContent === 'Inspect readings')!);
  }
}
async function choosePart(label: string) {
  await workspace("Scene");

  await click(container.querySelector('[aria-label="Inspect model body"]')!);
  await click([...document.querySelectorAll('[role="option"]')].find((option) => option.textContent?.replace("✓", "") === label)!);
  await click(container.querySelector(".scene-detail-heading > button")!);
}
async function choose(label: string, option: string) {
  await click(container.querySelector(`[aria-label="${label}"]`)!);
  await click([...document.querySelectorAll('[role="option"]')].find(e => e.textContent?.replace("✓", "") === option)!);
}
afterEach(async () => { await act(async () => { root?.unmount(); }); root = null; container?.remove(); vi.restoreAllMocks(); });

// Native pointer events also reach light-dismiss listeners; click-only helpers
// miss the original bug where playback was immediately closed and paused.
async function pointerClick(element: Element, pointerType = "mouse") {
  await act(async () => {
    element.dispatchEvent(Object.assign(new MouseEvent("pointerdown", { bubbles: true, button: 0 }), { pointerId: 1, isPrimary: true, pointerType }));
    element.dispatchEvent(Object.assign(new MouseEvent("pointerup", { bubbles: true, button: 0 }), { pointerId: 1, isPrimary: true, pointerType }));
    element.dispatchEvent(new MouseEvent("click", { bubbles: true, detail: 1 }));
  });
}

it.each(["Moment", "Evidence", "Sources"])("keeps %s open while the persistent transport plays and scrubs", async label => {
  await mount();
  await workspace(label);
  const panel = container.querySelector('[data-scene-detail]');
  const play = container.querySelector<HTMLButtonElement>('.scene-play-control')!;
  await pointerClick(play);
  expect(store().getState().playing).toBe(true);
  expect(container.querySelector('[data-scene-detail]')).toBe(panel);
  await pointerClick(play, "touch");
  expect(store().getState().playing).toBe(false);
  const scrubber = container.querySelector<HTMLInputElement>('.scene-scrubber')!;
  await pointerClick(scrubber, "touch");
  await act(async () => { scrubber.value = "12"; scrubber.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(ready().moment.row_index).toBe(12);
  expect(container.querySelector('[data-scene-detail]')).toBe(panel);
  await pointerClick(play);
  await click(container.querySelector('.scene-detail-heading > button')!);
  expect(store().getState().playing).toBe(true);
  await act(async () => store().pause());
});

it("plays and steps from a non-modal Moment heading by keyboard", async () => {
  await mount();
  await workspace("Moment");
  const heading = container.querySelector<HTMLElement>('.scene-detail-heading h2')!;
  const row = ready().moment.row_index;
  await act(async () => { heading.focus(); heading.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true })); });
  expect(store().getState().playing).toBe(true);
  await act(async () => heading.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true })));
  expect(store().getState().playing).toBe(false);
  expect(ready().moment.row_index).toBe(row + 1);
  expect(container.querySelector('.moment-inspection')).not.toBeNull();
});

it.each([["D01-gripper-sign", "command"], ["D03-observation-backlog", "capture"]])("takes %s to its retained finding and returns to Evidence", async (caseId, lens) => {
  await mount(`?evidence=fixtures/ui/recorded/${caseId}/evidence.json&i=30&p=before`);
  await click(container.querySelector('.scene-detail-heading > button')!);
  await click(opener("Evidence"));
  const initial = ready().moment;
  const row = ready().caseRecord.findings.find(f => f.run.run_id === initial.run.run_id && f.run.bundle_sha256 === initial.run.bundle_sha256)!.row_index;
  await pointerClick(container.querySelector('[data-see-moment]')!);
  expect(ready().moment.row_index).toBe(row);
  expect(ready().moment.run).toEqual(initial.run);
  expect(ready().moment.phase).toBe(initial.phase);
  expect(container.querySelector('.moment-inspection')?.getAttribute('data-step')).toBe(lens);
  expect(container.querySelectorAll('[data-scene-detail]')).toHaveLength(1);
  await click(container.querySelector('.scene-detail-heading > button')!);
  expect(container.querySelector('.scene-detail-heading h2')?.textContent).toBe('Evidence');
  expect(document.activeElement).toBe(container.querySelector('[data-see-moment]'));
  expect(ready().moment.row_index).toBe(row);
});

it("switches the shared reading position between Evidence and Moment without stacking or changing the recording", async () => {
  await mount();
  await click(container.querySelector(".scene-detail-heading > button")!);
  const moment = { ...ready().moment };
  await click(opener("Evidence"));
  expect(container.querySelectorAll("[data-scene-detail]")).toHaveLength(1);
  expect(container.querySelector(".case-brief")?.getAttribute("data-expanded")).toBe("false");
  expect(opener("Evidence").getAttribute("aria-expanded")).toBe("true");
  await click(opener("Moment"));
  expect(container.querySelectorAll("[data-scene-detail]")).toHaveLength(1);
  expect(container.querySelector(".scene-detail-heading h2")?.textContent).toBe("Moment");
  expect(opener("Evidence").getAttribute("aria-expanded")).toBe("false");
  expect(opener("Moment").getAttribute("aria-expanded")).toBe("true");
  await click(opener("Evidence"));
  expect(container.querySelectorAll("[data-scene-detail]")).toHaveLength(1);
  expect(container.querySelector(".moment-inspection")).toBeNull();
  expect(opener("Moment").getAttribute("aria-expanded")).toBe("false");
  await click(opener("Evidence"));
  expect(container.querySelector("[data-scene-detail]")).toBeNull();
  expect(ready().moment).toEqual(moment);
});

it.each(["Evidence", "Moment", "Sources"])("opens %s with pointer title focus and retains the exact recorded moment", async label => {
  await mount();
  await click(container.querySelector(".scene-detail-heading > button")!);
  const moment = { ...ready().moment };
  const trigger = opener(label);
  await act(async () => {
    trigger.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    trigger.focus();
    trigger.dispatchEvent(new MouseEvent("click", { detail: 1, bubbles: true }));
  });
  const title = document.activeElement as HTMLHeadingElement;
  expect(title.tagName).toMatch(/^H[1-6]$/);
  expect(container.querySelector("dialog")!.contains(title)).toBe(true);
  expect(title.dataset.pointerFocus).toBe("true");
  expect(ready().moment).toEqual(moment);
  await act(async () => title.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true })));
  expect(title.dataset.pointerFocus).toBeUndefined();
  await click(container.querySelector(".scene-detail-heading > button")!);
  expect(document.activeElement).toBe(label === "Sources" ? container.querySelector(".workspace-menu") : trigger);
  expect(ready().moment).toEqual(moment);
});

it("keeps recording selection available inside Workspace controls", async () => {
  await mount();
  await click(container.querySelector(".scene-detail-heading > button")!);
  const moment = { ...ready().moment };
  await waitFor(() => !!container.querySelector('.identity > .case-select button'));
  const current = container.querySelector('.identity > .case-select button')!.textContent;
  await click(container.querySelector('.workspace-menu')!);
  const choice = container.querySelector<HTMLSelectElement>('.workspace-popover .workspace-recording select')!;
  expect(choice).not.toBeNull();
  expect(choice.selectedOptions[0]?.textContent).toBe(current);
  expect(choice.options.length).toBeGreaterThan(0);
  expect(ready().moment).toEqual(moment);
});

it("changes architecture and camera by keyboard without changing the recorded source or moment, and honours reduced motion", async () => {
  await mount();
  await click(container.querySelector(".scene-detail-heading > button")!);
  const moment = { ...ready().moment }, record = ready().run.record;
  await act(async () => store().setReducedMotion(true));
  await click(opener("Scene"));
  const current = container.querySelector<HTMLButtonElement>(".scene-framing-current")!;
  if (current.textContent !== "Hall") {
    await click([...container.querySelectorAll(".scene-framing-options button")].find(b => b.textContent === "Hall")!);
    await click(current);
  }
  expect(scene.setSetting).toHaveBeenLastCalledWith("architecture", "lab");
  expect(scene.setBounds.mock.calls.at(-1)?.[1]).toBe(false);
  await click([...container.querySelectorAll(".scene-framing-secondary button")].find(button => button.textContent?.startsWith("Source room"))!);
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
  await click(container.querySelector(".scene-detail-heading > button")!);
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
  await click(container.querySelector(".scene-detail-heading > button")!);
  const open = container.querySelector<HTMLButtonElement>(".scene-moment-control")!;
  open.focus();
  const moment = ready().moment, view = store().getState().view, focus = store().getState().sceneFocus;
  await act(async () => store().play());
  await click(open);
  expect(store().getState().playing).toBe(true);
  await act(async () => store().pause());
  const panel = container.querySelector(".moment-inspection")!;
  expect(panel.querySelector('.inspection-details')?.hasAttribute('hidden')).toBe(true);
  expect(panel.querySelector('.inspection-measures')?.textContent).toContain("150.0 ms");
  expect(panel.querySelector('.inspection-measures')?.textContent).toContain("17.5 mm");
  await click(panel.querySelector('.inspection-detail-toggle')!);
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
  await act(async () => container.querySelector(".scene-detail-heading h2")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
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
  await click(container.querySelector('[aria-label="Close Moment"]')!);
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("evidence");
  expect(document.activeElement === opener).toBe(true);
});

it("opens a phone part's recorded details beside the robot, preserves sources, and returns focus without moving the camera", async () => {
  const original = window.matchMedia;
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({ ...original(query), matches: query.includes("max-width") }));
  await mount();
  const moment = ready().moment, view = store().getState().view;
  await choosePart("Arm link 4");
  expect(container.querySelector(".scene-part-cue")).toBeNull();
  const callout = container.querySelector(".panda-part-callout")!;
  expect(callout.querySelector("h2")?.textContent).toBe("Arm link 4");
  expect(document.activeElement).toBe(callout.querySelector("h2"));
  const body = ready().run.model!.bodies.find(b => b.name === "robot0_link4")!.index;
  const position = Array.from(ready().run.frames!.rows[moment.row_index]![moment.phase]!.xpos.slice(body * 3, body * 3 + 3));
  for (const value of position) expect(callout.textContent).toContain(value.toFixed(6));
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("scene");
  const details = container.querySelector<HTMLButtonElement>('[aria-label="Show selected part details"]')!;
  expect(details.closest(".scene-box")).toBeNull();
  details.focus();
  const canvas = container.querySelector(".scene-box");
  await click(details);
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("scene");
  expect(container.querySelector(".scene-detail")).toBeNull();
  expect(container.querySelector(".spatial-heading h2")?.textContent).toBe("Arm link 4");
  expect(container.querySelector('[aria-label="Spatial detail"]')?.textContent).toBe("Coordinates");
  expect(document.activeElement).toBe(details);
  expect(callout.textContent).toContain(`position: ${JSON.stringify(position)}`);
  expect(ready().moment).toEqual(moment); expect(store().getState().view).toBe(view);
  await choose("Spatial detail", "Sources");
  const links = [...callout.querySelectorAll<HTMLAnchorElement>("a")];
  for (const record of [ready().run.record.samples, ready().run.record.frames!, ready().run.record.model!]) {
    expect(links.some(a => a.href === new URL(record.path, ready().generation.baseUrl).href)).toBe(true);
  }
  expect(callout.textContent).toContain("robot0_link4");
  await act(async () => callout.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })));
  expect(container.querySelector(".panda-part-callout")).toBeNull();
  expect(store().getState().part).toBeNull();
  expect(document.activeElement).toBe(canvas);
  expect(container.querySelector(".scene-box")).toBe(canvas);
  expect(ready().moment).toEqual(moment); expect(store().getState().view).toBe(view);
});

it("keeps the part inspection bound to the current row and resets disclosure for a new part", async () => {
  await mount();
  await choosePart("Left finger");
  await click(container.querySelector('[aria-label="Show selected part details"]')!);
  await act(async () => store().setRow(12));
  const body = ready().run.model!.bodies.find(b => b.name === "gripper0_leftfinger")!.index;
  const position = Array.from(ready().run.frames!.rows[12]!.before!.xpos.slice(body * 3, body * 3 + 3));
  expect(container.querySelector(".panda-part-callout")?.textContent).toContain(`position: ${JSON.stringify(position)}`);
  await click(container.querySelector('[aria-label="Show fewer part details"]')!);
  expect(container.querySelector(".panda-part-callout")?.textContent).toContain(position[0]!.toFixed(6));
  await click(container.querySelector('[aria-label="Show selected part details"]')!);
  await act(async () => store().selectPart("robot0_link2"));
  expect(container.querySelector(".panda-part-callout h2")?.textContent).toBe("Arm link 2");
  expect(container.querySelector(".panda-part-callout")?.getAttribute("data-expanded")).toBe("false");
  expect(container.querySelector(".spatial-panel")).toBeNull();
  await click(opener("Evidence"));
  expect(container.querySelector(".panda-part-callout")).toBeNull();
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

it("restarts playback from the final recorded row through the persistent play control", async () => {
  await mount();
  await click(container.querySelector(".scene-detail-heading > button")!);
  await act(async () => store().setRow(ready().run.record.row_count - 1));
  const play = container.querySelector<HTMLButtonElement>(".scene-play-control")!;
  expect(play.disabled).toBe(false);
  await click(play);
  expect(store().getState().playing).toBe(true);
  expect(ready().moment.row_index).toBe(0);
  await act(async () => store().pause());
});


it.each(["screen", "keyboard", "control"])("opens the console and selected signal through %s, retaining row, camera, playback and return focus", async entrance => {
  await mount();
  await click(container.querySelector(".scene-detail-heading > button")!);
  const box = container.querySelector<HTMLElement>(".scene-box")!;
  const moment = ready().moment, view = store().getState().view, focus = store().getState().sceneFocus;
  let origin: HTMLElement = box;
  if (entrance === "screen") {
    box.setPointerCapture = vi.fn();
    vi.spyOn(box, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, width: 320, height: 320, right: 320, bottom: 320, x: 0, y: 0, toJSON() {} });
    scene.pick.mockReturnValueOnce({ kind: "workstation", id: "recording" });
    await act(async () => {
      container.querySelector(".scene-canvas")!.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10, button: 0 }));
      box.dispatchEvent(new MouseEvent("pointerup", { bubbles: true, clientX: 10, clientY: 10, button: 0 }));
    });
  } else if (entrance === "keyboard") {
    await act(async () => box.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })));
  } else {
    origin = opener("Scene");
    await click(origin);
    await click([...container.querySelectorAll(".scene-framing-secondary button")].find(button => button.textContent === "Experiment console")!);
  }
  expect(container.querySelector(".lab-console.scene-detail-floating")).not.toBeNull();
  expect(container.querySelector(".moment-inspection")).toBeNull();
  expect(ready().moment).toEqual(moment);
  await click([...container.querySelectorAll(".lab-console nav button")].find(button => button.textContent?.startsWith("Inspect current recording"))!);
  expect(container.querySelector(".moment-inspection .inspection-measures")?.textContent).toContain("150.0 ms");
  expect(container.querySelector(".case-brief")).toBeNull();
  expect(ready().moment).toEqual(moment);
  expect(store().getState().view).toBe(view); expect(store().getState().sceneFocus).toBe(focus);
  const play = container.querySelector<HTMLButtonElement>(".scene-play-control")!;
  await pointerClick(play); expect(store().getState().playing).toBe(true);
  await act(async () => store().pause());
  await click(container.querySelector('[aria-label="Close Moment"]')!);
  expect(container.querySelector(".moment-inspection")).toBeNull();
  expect(container.querySelector(".app")?.getAttribute("data-mobile-pane")).toBe("scene");
  expect(document.activeElement).toBe(origin);
  expect(store().getState().view).toBe(view); expect(store().getState().sceneFocus).toBe(focus);
});
