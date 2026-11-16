import { act, createRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { INITIAL_LOAD, staticShoulderStudy } from "../src/concepts/ricci";
import { ConceptStudio } from "../src/concepts/ConceptStudio";
import { readResearchRoute } from "../src/research/navigation";

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
afterEach(async () => { await act(async () => root?.unmount()); root = null; host?.remove(); });
async function mount(hash = "#view=concepts") {
  history.replaceState(null, "", `/${hash}`);
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  await act(async () => root!.render(<ConceptStudio heading={createRef()} laboratory={vi.fn()} />));
}
const button = (name: string) => [...host.querySelectorAll("button")].find(b => b.textContent?.includes(name))!;
const click = async (node: Element) => act(async () => node.dispatchEvent(new MouseEvent("click", { bubbles: true })));

it("opens a physics deep link without a research catalog, with an explicit calculation boundary", async () => {
  const hash = "#view=concepts&chapter=physics";
  expect(readResearchRoute(hash, false).surface).toBe("concepts");
  expect(readResearchRoute(hash, false).issue).toBeNull();
  await mount(hash);
  expect(host.querySelector(".load-results")?.textContent).toContain("15.21");
  expect(host.textContent).toContain("does not establish an actuator rating");
  await click(button("Inspect the calculation"));
  expect(host.querySelector(".load-derivation")?.textContent).toContain("not solved from tray contact geometry");
});
it("updates conditional moments through the actual range input and resets to the source study", async () => {
  await mount("#view=concepts&chapter=physics");
  const slider = [...host.querySelectorAll<HTMLInputElement>("input")].find(input => input.getAttribute("aria-label") === "Tray + payload")!;
  expect(slider, host.innerHTML).toBeInstanceOf(HTMLInputElement);
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(slider, "4");
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    slider.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(host.querySelector(".load-results")?.textContent).toContain("20.60");
  await click(button("Reset study inputs"));
  expect(slider.value).toBe("2");
  expect(host.querySelector(".load-results")?.textContent).toContain("15.21");
});
it("preserves a useful reading and navigation when source media fails", async () => {
  await mount();
  await act(async () => host.querySelector("img")!.dispatchEvent(new Event("error")));
  expect(host.querySelector('[role="status"]')?.textContent).toContain("Reference image unavailable");
  await click(button("Ankle & sole"));
  expect(host.querySelector(".concept-inspection")?.textContent).toContain("Bearing support");
  await click(button("Evidence"));
  expect(location.hash).toContain("chapter=evidence");
  expect(host.querySelector(".concept-document")?.textContent).toContain("component fit, mass and actuation are not closed");
});
it("restores the selected chapter on browser history navigation", async () => {
  await mount();
  await click(button("Build"));
  history.replaceState(null, "", "/#view=concepts&chapter=motion");
  await act(async () => window.dispatchEvent(new PopStateEvent("popstate")));
  expect(host.querySelector("main")?.dataset.chapter).toBe("motion");
  expect(host.textContent).toContain("No Ricci dynamics are solved here");
  expect(host.querySelector("img")?.getAttribute("src")).toContain("carry-reference");
});
