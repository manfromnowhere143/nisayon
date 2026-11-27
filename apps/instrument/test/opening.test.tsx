import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Opening } from "../src/research/Opening";
import { Experience } from "../src/research/Experience";
import evidence from "../src/research/opening-evidence.json";
import { inspectBundle } from "../src/qualification/bundle";
import { preview } from "../src/qualification/RecordExplorer";
import { object } from "../src/qualification/json";
import { PUBLIC_DIR } from "./fixture";

let host: HTMLDivElement, root: Root;
const navigate = vi.fn(), inspectExample = vi.fn(), catalogLoader = vi.fn();
beforeEach(() => {
  history.replaceState(null, "", "/");
  localStorage.clear();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("probably");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ hls: "https://stream.mux.com/test.m3u8?token=test", mp4: "https://stream.mux.com/test/highest.mp4?token=test" }))));
  vi.stubGlobal("crypto", { subtle: { digest: async (_algorithm: string, bytes: Uint8Array) => new Uint8Array(createHash("sha256").update(new Uint8Array(bytes)).digest()).buffer } });
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove();
  vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.clearAllMocks();
});
async function mount() {
  await act(async () => root.render(<StrictMode><Opening navigate={navigate} inspectExample={inspectExample} /></StrictMode>));
}
function button(text: string) { return [...host.querySelectorAll("button")].find(node => node.textContent?.includes(text))!; }

it("opens a cold visit without requesting a catalog, film or hidden lab", async () => {
  await act(async () => root.render(<StrictMode><Experience catalogLoader={catalogLoader} /></StrictMode>));
  expect(host.querySelector(".opening h1")?.textContent).toBe("Nisayon");
  expect(catalogLoader).not.toHaveBeenCalled();
  expect(host.querySelector(".app,video[src],source")).toBeNull();
  expect(host.querySelector(".research-workspace")?.hasAttribute("inert")).toBe(true);
  expect(host.querySelector(".opening-image img")?.getAttribute("fetchpriority")).toBe("high");
  expect(fetch).not.toHaveBeenCalled();
});

it("keeps a usable still and direct instrument entry when the poster fails", async () => {
  await mount();
  await act(async () => host.querySelector("img")!.dispatchEvent(new Event("error")));
  expect(host.textContent).toContain("Scene unavailable");
  expect(host.querySelector(".opening-image img")).toBeNull();
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Open Nisayon"]')!.click());
  expect(navigate).toHaveBeenCalledWith("lab");
});

it("opens one deliberate film dialog on repeated clicks and restores focus on Escape", async () => {
  await mount();
  const play = host.querySelector<HTMLButtonElement>('[aria-label="Watch Nisayon intro"]')!, push = vi.spyOn(history, "pushState"), back = vi.spyOn(history, "back").mockImplementation(() => {});
  play.focus();
  await act(async () => { play.click(); play.click(); });
  expect(push).toHaveBeenCalledOnce();
  const video = host.querySelector(".film-picture video") as HTMLVideoElement;
  expect(video.autoplay).toBe(false); expect(video.loop).toBe(false); expect(video.controls).toBe(true);
  expect(video.preload).toBe("none");
  await act(async () => host.querySelector("dialog")!.dispatchEvent(new Event("cancel", { cancelable: true })));
  expect(host.querySelector("dialog")).toBeNull(); expect(document.activeElement).toBe(play);
  expect(back).toHaveBeenCalledOnce();
});

it("handles film failure, retry and browser Back without hiding the next action", async () => {
  await mount();
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Watch Nisayon intro"]')!.click());
  await act(async () => host.querySelector(".film-picture video")!.dispatchEvent(new Event("error")));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("film could not load");
  await act(async () => button("Try again").click());
  expect(host.querySelector('[role="alert"]')).toBeNull();
  await act(async () => { history.replaceState(null, "", "/#view=home"); window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(host.querySelector("dialog")).toBeNull();
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Open Nisayon"]')!.click());
  expect(navigate).toHaveBeenCalledWith("lab");
  expect(host.querySelector(".opening-evidence")).toBeNull();
});

it("binds the opening example to the exact retained public package", async () => {
  const bytes = readFileSync(join(PUBLIC_DIR, "examples/qualification/rejected.nisayon.zip"));
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(evidence.package_sha256);
  const bundle = await inspectBundle(new Uint8Array(bytes).buffer, "rejected.nisayon.zip");
  expect(bundle.assessment.software_decision).toBe(evidence.software_decision);
  expect(bundle.assessment.execution_validity).toBe(evidence.execution_validity);
  expect(bundle.comparisons).toHaveLength(evidence.comparisons.length);
  for (let i = 0; i < bundle.comparisons.length; i++) {
    const difference = object(bundle.comparisons[i]!.candidate_difference);
    const displayed = evidence.comparisons[i]!.candidate_difference;
    expect(difference.path).toBe(displayed.path);
    expect(Number(preview(difference.reference!))).toBe(displayed.reference);
    expect(Number(preview(difference.candidate!))).toBe(displayed.candidate);
  }
});
