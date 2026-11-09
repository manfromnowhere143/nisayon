import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Develop } from "../src/qualification/Develop";

let host: HTMLDivElement, root: Root, width = 1100, height = 80;
const copied = vi.fn(async (_text: string) => {});
const observers = new Set<() => void>();
beforeEach(() => {
  width = 1100; height = 80;
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  vi.stubGlobal("ResizeObserver", class {
    constructor(private notify: () => void) { observers.add(notify); }
    observe() {} disconnect() { observers.delete(this.notify); }
  });
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    return { width: this.classList.contains("command-measure") ? 80 : width, height } as DOMRect;
  });
  vi.stubGlobal("getComputedStyle", () => ({ lineHeight: "24px" }));
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: copied } });
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); copied.mockClear(); });
async function click(label: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.getAttribute("aria-label") === label || button.textContent?.endsWith(label));
  expect(button).toBeDefined(); await act(async () => button!.click());
}
it("shows and copies the actual command in the 80px body that triggered the overflow warning", async () => {
  await act(async () => root.render(<Develop review={() => {}} />));
  await click("Example");
  const expected = ".venv/bin/nisayon-qualify example owner-project";
  expect(host.querySelector('pre[aria-label="SDK command"]')?.textContent).toBe(expected);
  expect(host.textContent).not.toContain("This view needs more room");
  expect(host.querySelector(".command-pages")).toBeNull();
  await click("Copy SDK command"); expect(copied).toHaveBeenCalledWith(expected);
});
it("keeps every character reachable on a narrow screen and copies both complete review commands", async () => {
  width = 180; height = 100;
  await act(async () => root.render(<Develop review={() => {}} />));
  await click("Review");
  const expected = ".venv/bin/nisayon-qualify export run-001 --out review-001.nisayon.zip\n.venv/bin/nisayon-qualify review review-001.nisayon.zip";
  let complete = host.querySelector("pre")!.textContent;
  while (!host.querySelector<HTMLButtonElement>('[aria-label="Next command page"]')!.disabled) {
    await click("Next command page"); complete += host.querySelector("pre")!.textContent;
  }
  expect(complete).toBe(expected);
  await click("Copy SDK command"); expect(copied).toHaveBeenCalledWith(expected);
  width = 1200; height = 120;
  await act(async () => { for (const notify of observers) notify(); });
  expect(host.querySelector("pre")!.textContent).toBe(expected);
  expect(host.querySelector(".command-pages")).toBeNull();
  await click("Run"); expect(host.querySelector("pre")!.textContent).toContain(".venv/bin/nisayon-qualify run plan-001.json");
});
