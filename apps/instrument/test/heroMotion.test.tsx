import { StrictMode, act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Opening } from "../src/research/Opening";
import { HERO_MEDIA } from "../src/research/heroMotion";

let host: HTMLDivElement, root: Root, reduced: boolean, narrow: boolean, visibility: DocumentVisibilityState;
let network: EventTarget & { saveData: boolean; effectiveType: string };
let preferenceListeners: Set<EventListenerOrEventListenerObject>;
let intersect: IntersectionObserverCallback;
const originalConnection = Object.getOwnPropertyDescriptor(navigator, "connection");
beforeEach(() => {
  vi.useFakeTimers(); localStorage.clear(); history.replaceState(null, "", "/");
  reduced = false; narrow = false; visibility = "visible"; preferenceListeners = new Set();
  network = Object.assign(new EventTarget(), { saveData: false, effectiveType: "4g" });
  Object.defineProperty(navigator, "connection", { configurable: true, value: network });
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
  vi.spyOn(window, "matchMedia").mockImplementation(query => ({
    get matches() { return query.includes("reduced-motion") ? reduced : query.includes("700px") && narrow; },
    media: query, onchange: null, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
    addEventListener: (_: string, listener: EventListenerOrEventListenerObject) => { preferenceListeners.add(listener); },
    removeEventListener: (_: string, listener: EventListenerOrEventListenerObject) => { preferenceListeners.delete(listener); },
  } as MediaQueryList));
  vi.stubGlobal("IntersectionObserver", class {
    constructor(callback: IntersectionObserverCallback) { intersect = callback; }
    observe() {} disconnect() {}
  });
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("probably");
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ hls: "https://stream.mux.com/test.m3u8?token=test", mp4: "https://stream.mux.com/test/highest.mp4?token=test" }))));
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove();
  if (originalConnection) Object.defineProperty(navigator, "connection", originalConnection);
  else Reflect.deleteProperty(navigator, "connection");
  vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
});
async function mount(key = "first") {
  await act(async () => root.render(<StrictMode><Opening key={key} navigate={() => {}} inspectExample={() => {}} /></StrictMode>));
}
const background = () => host.querySelector<HTMLVideoElement>(".opening-motion")!;
const control = () => host.querySelector<HTMLButtonElement>(".opening-motion-control")!;
async function posterLoaded() {
  await act(async () => host.querySelector("img")!.dispatchEvent(new Event("load")));
  await act(async () => vi.advanceTimersByTimeAsync(40));
}
async function changeVisibility(value: DocumentVisibilityState) {
  visibility = value;
  await act(async () => document.dispatchEvent(new Event("visibilitychange")));
}

it("paints the poster before requesting a silent native sequence and reveals only a playing frame", async () => {
  await mount();
  expect(background().getAttribute("src")).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
  await posterLoaded();
  expect(background().getAttribute("src")).toBe(HERO_MEDIA.wide);
  expect(background().muted).toBe(true); expect(background().playsInline).toBe(true);
  expect(background().controls).toBe(false); expect(background().loop).toBe(true);
  expect(background().dataset.visible).toBe("false");
  await act(async () => background().dispatchEvent(new Event("playing")));
  expect(background().dataset.visible).toBe("true");
  expect(host.querySelectorAll("video")).toHaveLength(1);
  expect(fetch).not.toHaveBeenCalled();
});

it.each(["reduced motion", "data saver", "slow network"])("defaults to a usable still for %s but allows deliberate playback", async preference => {
  reduced = preference === "reduced motion"; network.saveData = preference === "data saver";
  if (preference === "slow network") network.effectiveType = "2g";
  await mount(); await posterLoaded();
  expect(background().getAttribute("src")).toBeNull();
  expect(control().getAttribute("aria-label")).toBe("Play background motion");
  expect(host.querySelector('[aria-label="Open Nisayon"]')).not.toBeNull();
  await act(async () => control().click());
  expect(background().getAttribute("src")).toBe(HERO_MEDIA.wide);
});

it("selects the smaller derivative on narrow screens", async () => {
  narrow = true; await mount(); await posterLoaded();
  expect(background().getAttribute("src")).toBe(HERO_MEDIA.small);
});

it("keeps a manual pause across hidden tabs and a return to the opening", async () => {
  await mount(); await posterLoaded();
  await act(async () => background().dispatchEvent(new Event("playing")));
  await act(async () => control().click());
  expect(background().dataset.visible).toBe("true");
  await changeVisibility("hidden"); expect(background().getAttribute("src")).toBeNull();
  await changeVisibility("visible"); expect(background().getAttribute("src")).toBeNull();
  await mount("return"); await posterLoaded();
  expect(background().getAttribute("src")).toBeNull();
  expect(control().getAttribute("aria-label")).toBe("Play background motion");
});

it("releases hidden/offscreen playback and suspends it behind the full-film dialog", async () => {
  await mount(); await posterLoaded();
  await act(async () => intersect([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver));
  expect(background().getAttribute("src")).toBeNull();
  await act(async () => intersect([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver));
  expect(background().getAttribute("src")).toBe(HERO_MEDIA.wide);
  await changeVisibility("hidden"); expect(background().getAttribute("src")).toBeNull();
  await changeVisibility("visible"); expect(background().getAttribute("src")).toBe(HERO_MEDIA.wide);
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Watch Nisayon intro"]')!.click());
  expect(host.querySelector("dialog")).not.toBeNull();
  expect(background().getAttribute("src")).toBeNull();
});

it("falls back cleanly when autoplay or the media request fails, with a deliberate retry", async () => {
  vi.mocked(HTMLMediaElement.prototype.play).mockRejectedValueOnce(new DOMException("Autoplay denied", "NotAllowedError"));
  await mount(); await posterLoaded();
  expect(background().dataset.visible).toBe("false");
  expect(control().getAttribute("aria-label")).toBe("Play background motion");
  await act(async () => control().click());
  await act(async () => background().dispatchEvent(new Event("playing")));
  expect(background().dataset.visible).toBe("true");
  await act(async () => background().dispatchEvent(new Event("error")));
  expect(background().dataset.visible).toBe("false");
  expect(control().getAttribute("aria-label")).toBe("Play background motion");
  expect(host.querySelector("img")).not.toBeNull();
});

it("stops for a new reduced-motion preference and ignores an old rejected play request", async () => {
  let reject!: (reason: Error) => void;
  vi.mocked(HTMLMediaElement.prototype.play).mockImplementationOnce(() => new Promise((_, failure) => { reject = failure; }));
  await mount(); await posterLoaded();
  await act(async () => {
    reduced = true;
    for (const listener of preferenceListeners) if (typeof listener === "function") listener(new Event("change"));
  });
  expect(background().getAttribute("src")).toBeNull();
  await act(async () => control().click());
  await act(async () => reject(new Error("Obsolete playback failed")));
  expect(control().getAttribute("aria-label")).toBe("Pause background motion");
  expect(background().getAttribute("src")).toBe(HERO_MEDIA.wide);
});
