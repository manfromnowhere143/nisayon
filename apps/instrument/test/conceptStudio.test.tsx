import { act, createRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { INITIAL_LOAD, staticShoulderStudy } from "../src/concepts/ricci";
import { ConceptStudio } from "../src/concepts/ConceptStudio";
import { readResearchRoute } from "../src/research/navigation";
import { createRicciRenderer } from "../src/concepts/ricciRenderer";

vi.mock("../src/concepts/ricciRenderer", () => ({ createRicciRenderer: vi.fn((_canvas, callbacks) => {
  callbacks.ready();
  return { trace: vi.fn(), camera: vi.fn(), laboratory: vi.fn(), select: vi.fn(), view: vi.fn(), orbit: vi.fn(), zoom: vi.fn(), reset: vi.fn(), dispose: vi.fn() };
}) }));

it("conserves the tray load under asymmetric sharing and recovers the retained one-arm case", () => {
  for (const share of [0, .1, .5, .9, 1]) {
    const result = staticShoulderStudy({ ...INITIAL_LOAD, share });
    expect(result.leftReactionN + result.rightReactionN).toBeCloseTo(19.62, 10);
    expect(result.leftNm + result.rightNm).toBeCloseTo(30.411, 10);
  }
  expect(staticShoulderStudy({ ...INITIAL_LOAD, share: 1 }).leftNm).toBeCloseTo(20.601, 10);
  expect(staticShoulderStudy(INITIAL_LOAD).leftNm).toBeCloseTo(15.2055, 10);
  expect(staticShoulderStudy({ ...INITIAL_LOAD, payloadKg: 0 }).leftNm).toBeCloseTo(9.81, 10);
});
it("increases only the payload contribution with reach, and rejects undefined physical inputs", () => {
  const near = staticShoulderStudy({ ...INITIAL_LOAD, reachM: .3 });
  const far = staticShoulderStudy({ ...INITIAL_LOAD, reachM: .6 });
  expect(far.leftNm - far.armMoment).toBeCloseTo(2 * (near.leftNm - near.armMoment), 10);
  for (const patch of [{ payloadKg: -1 }, { reachM: NaN }, { armKg: Infinity }, { share: 1.1 }]) {
    expect(() => staticShoulderStudy({ ...INITIAL_LOAD, ...patch })).toThrow();
  }
});

let root: Root | null = null, host: HTMLDivElement;
afterEach(async () => { await act(async () => root?.unmount()); root = null; host?.remove(); vi.restoreAllMocks(); });
async function mount(hash = "#view=concepts") {
  history.replaceState(null, "", `/${hash}`);
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  await act(async () => root!.render(<ConceptStudio heading={createRef()} laboratory={vi.fn()} />));
  const deadline = Date.now() + 1000;
  while (host.querySelector('.ricci-render')?.getAttribute('data-renderer') === 'loading') {
    if (Date.now() > deadline) throw Error('Ricci initialization did not settle');
    await act(async () => new Promise(resolve => setTimeout(resolve, 20)));
  }
}
const button = (name: string) => [...host.querySelectorAll("button")].find(b => b.textContent?.includes(name))!;
const click = async (node: Element) => act(async () => node.dispatchEvent(new MouseEvent("click", { bubbles: true })));

it("keeps the legacy conditional load study inspectable in isolation", async () => {
  const { LoadStudy } = await import("../src/concepts/LoadStudy");
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  await act(async () => root!.render(<LoadStudy />));
  expect(host.querySelector(".load-results")?.textContent).toContain("15.21");
  expect(host.textContent).toContain("does not establish an actuator rating");
  await click(button("Inspect the calculation"));
  expect(host.querySelector(".load-derivation")?.textContent).toContain("not solved from tray contact geometry");
});

const ids = ["head_visor", "torso_spine", "waist_pelvis", "arm_upper", "arm_distal", "leg_upper", "leg_shank", "ankle_foot", "outer_shell", "power_pack", "compute_thermal", "service_safety"];
it("opens the same route with geometry and no media substitute or initial focus theft", async () => {
  expect(readResearchRoute("#view=concepts", false).surface).toBe("concepts"); await mount();
  expect(host.querySelector("canvas")).not.toBeNull(); expect(host.querySelectorAll("img,video,audio,iframe,svg image")).toHaveLength(0);
  expect(host.querySelector("dialog[open]")).toBeNull(); expect(document.activeElement).not.toBe(host.querySelector("h1"));
});
it("opens every R01 section in one expandable card and fully dismisses it on close", async () => {
  await mount();
  for (const id of ids) {
    await click(button("Parts")); expect(host.querySelectorAll('[data-list-part]')).toHaveLength(12);
    await click(host.querySelector(`[data-list-part="${id}"]`)!);
    expect(host.querySelector(".ricci-annotation")?.getAttribute("data-part")).toBe(id);

    expect(host.querySelector(".ricci-part-copy")).toBeNull();
    await click(host.querySelector(".ricci-callout footer button")!);
    expect(host.querySelectorAll(".ricci-part-copy dt")).toHaveLength(5);
    expect(host.querySelector(".ricci-part-copy")?.textContent).toContain("Proposed materials");
    expect(host.querySelectorAll(".ricci-callout")).toHaveLength(1);
    expect(host.querySelector(".ricci-callout h2")).not.toBeNull();
    expect(host.querySelector(".ricci-modal[open]")).toBeNull();
    // Direct-link close avoids depending on jsdom's history timer in this test.
    history.replaceState(null,"",location.href);
    await click(host.querySelector('[aria-label="Close part inspection"]')!);
    expect(location.hash).not.toContain("part="); expect(host.querySelector(".ricci-callout, .ricci-part-label")).toBeNull();
  }
});
it("retains camera ownership, selection and scene node across lab and inspector changes", async () => {
  await mount(); const canvas=host.querySelector("canvas"),renderer=vi.mocked(createRicciRenderer).mock.results.at(-1)!.value;
  expect(host.querySelector("main")?.dataset.stage).toBe("black");
  await click(button("Enter the Lab")); expect(location.hash).toContain("stage=lab");
  await click(button("Black stage")); expect(location.hash).not.toContain("stage=");
  await click(button("Enter the Lab")); expect(host.querySelector("main")?.dataset.stage).toBe("lab");
  const callback=vi.mocked(createRicciRenderer).mock.calls.at(-1)![1];
  await act(async()=>callback.pick({id:"ankle_foot",instance:"ankle_foot_right",detail:"sole"}));
  expect(location.hash).toContain("instance=ankle_foot_right"); expect(host.querySelector(".ricci-callout")?.textContent).toContain("Right");
  history.replaceState(null,"",location.href); await click(host.querySelector('[aria-label="Close part inspection"]')!);
  expect(host.querySelector("canvas")).toBe(canvas); expect(renderer.reset).not.toHaveBeenCalled(); expect(renderer.dispose).not.toHaveBeenCalled();
  expect(location.hash).not.toContain("part="); expect(host.querySelector("main")?.dataset.stage).toBe("lab");
});
it("keeps repeatable camera controls beside Motion Study without recreating the renderer", async () => {
  await mount();
  const canvas = host.querySelector("canvas"), renderer = vi.mocked(createRicciRenderer).mock.results.at(-1)!.value;
  const camera = host.querySelector('.ricci-stage-actions .ricci-camera-access')!;
  expect(camera.querySelector('[aria-label="View"]')).not.toBeNull();
  expect(host.querySelector('.ricci-stage .ricci-view-controls')).toBeNull();
  for (let turn = 0; turn < 3; turn++) await click(camera.querySelector('[aria-label="Turn right"]')!);
  expect(renderer.orbit.mock.calls).toEqual([[.18], [.18], [.18]]);
  await click(camera.querySelector('[aria-label="Zoom in on Ricci"]')!);
  expect(renderer.zoom).toHaveBeenCalledWith(.06);
  await click(button("Motion Study"));
  expect(host.querySelector("canvas")).toBe(canvas);
  expect(renderer.dispose).not.toHaveBeenCalled();
  expect(renderer.reset).not.toHaveBeenCalled();
});
it("ends authored motion before opening retained Brain inspection and preserves the scene", async () => {
  await mount();
  const canvas = host.querySelector("canvas"), renderer = vi.mocked(createRicciRenderer).mock.results.at(-1)!.value;
  await click(button("Motion Study"));
  await click(host.querySelector('[aria-label="Play preview"]')!);
  expect(renderer.trace.mock.calls.at(-1)?.[2]).toBe(true);
  expect(host.querySelector(".ricci-trace-caption")).not.toBeNull();
  await click(button("Brain 01"));
  expect(host.querySelector(".brain-inspection")).not.toBeNull();
  expect(host.querySelector(".ricci-trace-caption, .ricci-transport")).toBeNull();
  expect(renderer.trace.mock.calls.at(-1)?.[2]).toBe(false);
  const stopped = renderer.trace.mock.calls.length;
  await act(async () => new Promise(resolve => setTimeout(resolve, 80)));
  expect(renderer.trace).toHaveBeenCalledTimes(stopped);
  await click(button("Brain 01"));
  expect(host.querySelector(".brain-inspection")).toBeNull();
  expect(host.querySelector(".ricci-trace-caption, .ricci-transport")).toBeNull();
  expect(host.querySelector("canvas")).toBe(canvas);
  expect(renderer.dispose).not.toHaveBeenCalled();
});
it("keeps accessible descriptions usable when graphics fails and retries with a fresh canvas", async () => {
  vi.mocked(createRicciRenderer).mockImplementationOnce(()=>{throw new Error("No GPU");}); await mount();
  const canvas=host.querySelector("canvas"); await click(host.querySelector('[data-part="ankle_foot"]')!);
  expect(host.querySelector(".ricci-callout h2")?.textContent).toBe("Ankle / sole");
  history.replaceState(null,"",location.href);await click(host.querySelector('[aria-label="Close part inspection"]')!);
  await click(button("Retry 3D view"));expect(host.querySelector("canvas")).not.toBe(canvas);expect(location.hash).not.toContain("part=");
});
it("never scrolls the page for a tap, inspector, or stage transition", async()=>{
  const scroll=vi.spyOn(window,"scrollBy").mockImplementation(()=>{});await mount();await click(button("Parts"));await click(host.querySelector('[data-list-part="head_visor"]')!);
  history.replaceState(null,"",location.href);await click(host.querySelector('.ricci-close')!);await click(button("Enter the Lab"));expect(scroll).not.toHaveBeenCalled();
});
it("reads Back selection/stage/inspector states and removes route listeners on cleanup", async()=>{
  const add=vi.spyOn(window,"addEventListener"),remove=vi.spyOn(window,"removeEventListener");await mount("#view=concepts&stage=lab&part=ankle_foot&inspect=part");
  history.replaceState(null,"","/#view=concepts&stage=lab&part=ankle_foot");await act(async()=>window.dispatchEvent(new PopStateEvent("popstate")));
  expect(host.querySelector(".ricci-callout h2")).not.toBeNull();expect(host.querySelector(".ricci-annotation")?.getAttribute("data-part")).toBe("ankle_foot");
  history.replaceState(null,"","/#view=concepts");await act(async()=>window.dispatchEvent(new PopStateEvent("popstate")));
  expect(host.querySelector(".ricci-callout")).toBeNull();expect(host.querySelector("main")?.dataset.stage).toBe("black");
  await act(async()=>root!.unmount());root=null;for(const event of ["popstate","hashchange"]){expect(remove).toHaveBeenCalledWith(event,add.mock.calls.find(c=>c[0]===event)?.[1]);}
});
it.each(["missing","ankle_foot&part=head_visor","","%3Cscript%3E"])("refuses invalid part %s without substitution",async part=>{
  await mount(`#view=concepts&part=${part}`);expect(host.querySelector('[role="status"]')?.textContent).toContain("This link");await click(button("Reset selection"));expect(location.hash).toBe("#view=concepts");
});

it("opens motion controls without changing the camera or authored clock; selection, expansion and Escape preserve them", async () => {
  await mount();
  const canvas = host.querySelector("canvas"), renderer = vi.mocked(createRicciRenderer).mock.results.at(-1)!.value;
  await click(button("Motion Study"));
  expect(renderer.trace.mock.calls.at(-1)).toEqual([0, "load", true]);
  const trace = renderer.trace.mock.calls.at(-1);
  expect(host.querySelector(".ricci-transport output")?.textContent).toBe("0.0 s");
  const callback = vi.mocked(createRicciRenderer).mock.calls.at(-1)![1];
  await act(async () => callback.pick({ id: "head_visor", instance: "head_visor", detail: "shell" }));
  await click(host.querySelector(".ricci-callout footer button")!);
  expect(host.querySelectorAll(".ricci-callout")).toHaveLength(1);
  await act(async () => host.querySelector(".ricci-callout h2")!.dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true, cancelable:true})));
  expect(host.querySelector(".ricci-callout,.ricci-part-label")).toBeNull();
  expect(location.hash).not.toContain("part=");
  expect(host.querySelector("canvas")).toBe(canvas);
  expect(renderer.reset).not.toHaveBeenCalled();
  expect(renderer.trace.mock.calls.at(-1)).toEqual(trace);
  await click(button("Motion Study"));
  expect(renderer.trace.mock.calls.at(-1)).toEqual([0, "load", false]);
  expect(host.querySelector(".ricci-transport")).toBeNull();
  await click(button("Motion Study"));
  expect(renderer.trace.mock.calls.at(-1)).toEqual([0, "load", true]);
  await act(async () => host.querySelector("main")!.dispatchEvent(new KeyboardEvent("keydown", {key:"Escape", bubbles:true, cancelable:true})));
  expect(renderer.trace.mock.calls.at(-1)).toEqual([0, "load", false]);
});
it("replaces the selected part and clears one card on a qualified scene miss", async () => {
  await mount();
  const callback = vi.mocked(createRicciRenderer).mock.calls.at(-1)![1];
  await act(async () => callback.pick({ id: "head_visor", instance: "head_visor", detail: "shell" }));
  await act(async () => callback.pick({ id: "ankle_foot", instance: "ankle_foot_right", detail: "sole" }));
  expect(host.querySelectorAll(".ricci-callout")).toHaveLength(1);
  expect(host.querySelector(".ricci-callout h2")?.textContent).toContain("Ankle / sole");
  await act(async () => callback.miss?.());
  expect(host.querySelector(".ricci-callout,.ricci-part-label")).toBeNull();
  expect(location.hash).not.toContain("part=");
});
it("cancels deferred GPU work on an immediate route exit", async () => {
  history.replaceState(null, "", "/#view=concepts");
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  const before = vi.mocked(createRicciRenderer).mock.calls.length;
  await act(async () => { root!.render(<ConceptStudio heading={createRef()} laboratory={vi.fn()} />); });
  await act(async () => { root!.unmount(); }); root = null;
  await act(async () => new Promise(resolve => setTimeout(resolve, 40)));
  expect(vi.mocked(createRicciRenderer).mock.calls.length).toBe(before);
});
