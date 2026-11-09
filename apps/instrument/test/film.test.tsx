import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Film, filmSource } from "../src/research/Film";

const mocks = vi.hoisted(() => ({ supported: true, instances: [] as Array<{ startLoad: ReturnType<typeof vi.fn>; stopLoad: ReturnType<typeof vi.fn>; destroy: ReturnType<typeof vi.fn>; handlers: Record<string, (...args: unknown[]) => void> }> }));
vi.mock("hls.js", () => ({ default: class {
  static isSupported() { return mocks.supported; }
  static Events = { MEDIA_ATTACHED: "attached", MANIFEST_PARSED: "manifest", ERROR: "error" };
  handlers: Record<string, (...args: unknown[]) => void> = {};
  startLoad = vi.fn(); stopLoad = vi.fn(); destroy = vi.fn();
  constructor() { mocks.instances.push(this); }
  on(event: string, handler: (...args: unknown[]) => void) { this.handlers[event] = handler; }
  attachMedia() { this.handlers.attached?.(); }
  loadSource() { this.handlers.manifest?.(); }
} }));
const urls = { hls: "https://stream.mux.com/fixture.m3u8?token=test", mp4: "https://stream.mux.com/fixture/highest.mp4?token=test" };
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  mocks.instances.length = 0; mocks.supported = true;
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("");
});
it("uses adaptive MSE even when a Chromium-like browser advertises native HLS", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("maybe");
  vi.spyOn(document, "hidden", "get").mockReturnValue(false);
  await act(async () => root.render(<Film poster="/poster.webp" playRequested={true} onClose={() => {}} source={async () => urls} />));
  expect(mocks.instances).toHaveLength(1);
  expect(mocks.instances[0]!.startLoad).toHaveBeenCalledWith(-1);
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();
  expect(host.querySelector("video")!.getAttribute("src")).toBeNull();
});
it("falls back to native HLS or MP4 when adaptive MSE is unavailable", async () => {
  mocks.supported = false;
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("probably");
  const source = async () => urls;
  await act(async () => root.render(<Film poster="/poster.webp" playRequested={false} onClose={() => {}} source={source} />));
  expect(host.querySelector("video")!.src).toBe(urls.hls);
  await act(async () => root.render(null));
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("");
  await act(async () => root.render(<Film poster="/poster.webp" playRequested={false} onClose={() => {}} source={source} />));
  expect(host.querySelector("video")!.src).toBe(urls.mp4);
  expect(mocks.instances).toHaveLength(0);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it("starts adaptive segments only on play, pauses when hidden and destroys the stream on close", async () => {
  const source = vi.fn(async () => urls);
  await act(async () => root.render(<Film poster="/poster.webp" playRequested={false} onClose={() => {}} source={source} />));
  const hls = mocks.instances[0]!; expect(hls).toBeDefined(); expect(hls.startLoad).not.toHaveBeenCalled();
  await act(async () => host.querySelector("video")!.dispatchEvent(new Event("play")));
  expect(hls.startLoad).toHaveBeenCalledWith(-1);
  const visibility = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
  await act(async () => document.dispatchEvent(new Event("visibilitychange")));
  expect(hls.stopLoad).toHaveBeenCalledOnce(); expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
  visibility.mockReturnValue(false);
  await act(async () => document.dispatchEvent(new Event("visibilitychange")));
  expect(hls.startLoad).toHaveBeenCalledOnce();
  await act(async () => root.render(null)); expect(hls.destroy).toHaveBeenCalledOnce();
});
it("refuses late media initialization after navigation closes the film", async () => {
  let resolve!: (value: typeof urls) => void, signal!: AbortSignal;
  const source = (current: AbortSignal) => { signal = current; return new Promise<typeof urls>(done => { resolve = done; }); };
  await act(async () => root.render(<Film poster="/poster.webp" playRequested={false} onClose={() => {}} source={source} />));
  await act(async () => root.render(null)); expect(signal.aborted).toBe(true);
  await act(async () => resolve(urls)); expect(mocks.instances).toHaveLength(0);
});
it("keeps close and retry available after a fatal streaming error", async () => {
  const source = vi.fn(async () => urls), closed = vi.fn();
  await act(async () => root.render(<Film poster="/poster.webp" playRequested={false} onClose={closed} source={source} />));
  await act(async () => mocks.instances[0]!.handlers.error!("error", { fatal: true }));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("could not load");
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Close film"]')!.click()); expect(closed).toHaveBeenCalledOnce();
});
it("does not accept a film endpoint redirecting playback to an unrelated origin", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ hls: "https://unrelated.example/video", mp4: urls.mp4 }))));
  await expect(filmSource(new AbortController().signal)).rejects.toThrow("Invalid film origin");
});
