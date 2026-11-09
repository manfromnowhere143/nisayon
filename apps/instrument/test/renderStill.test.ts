import { afterEach, expect, it, vi } from "vitest";
import { renderStill } from "../src/scene/renderStill";
import { REFINEMENT_LIMITS as LIMITS } from "../src/scene/refinement";

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

function harness(calibrating = false) {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
  const state = { samples: 0, ready: true, compiling: false };
  const controller = new AbortController(), reveal = vi.fn(), compose = vi.fn(), update = vi.fn();
  const calibration = vi.fn((_millisecondsPerSample: number) => { state.samples = 0; });
  const promise = renderStill({
    signal: controller.signal, started: performance.now(),
    work: { ready: () => state.ready, limit: () => 8, submit: draw => { draw(); state.ready = false; } },
    samples: () => state.samples,
    renderTile: () => { if (!state.compiling) state.samples += 1 / 16; },
    compose, reveal, update, check: () => {}, compiling: () => state.compiling,
    ...(calibrating ? { calibrate: calibration } : {}),
  });
  const frame = (ready = true) => { state.ready = ready; vi.advanceTimersToNextTimer(); };
  return { state, controller, reveal, compose, update, promise, frame, calibration };
}

it("finishes independently of display frames and waits for GPU completion before revealing", async () => {
  const h = harness();
  const raf = vi.spyOn(window, "requestAnimationFrame");
  h.frame();
  const submitted = h.state.samples;
  h.frame(false); h.frame(false);
  expect(h.state.samples).toBe(submitted); // An unfinished GPU batch cannot be overtaken.
  while (h.state.samples < 8) h.frame();
  expect(h.compose).not.toHaveBeenCalled(); expect(h.reveal).not.toHaveBeenCalled();
  while (h.state.samples < LIMITS.samples) h.frame();
  h.frame(false); expect(h.compose).not.toHaveBeenCalled(); // Submitted is not completed.
  h.frame(); expect(h.compose).toHaveBeenCalledTimes(1);
  h.frame(false); expect(h.reveal).not.toHaveBeenCalled(); // The filtered image also needs a fence.
  h.frame(); await h.promise;
  expect(h.reveal).toHaveBeenCalledTimes(1);
  expect(h.update).toHaveBeenLastCalledWith("complete", LIMITS.samples);
  expect(raf).not.toHaveBeenCalled(); expect(vi.getTimerCount()).toBe(0);
});

it("times out with no animation frames or GPU completion and never exposes a partial still", async () => {
  const h = harness(); const outcome = expect(h.promise).rejects.toThrow(/20 s/);
  while (h.state.samples < 12) h.frame();
  h.state.ready = false;
  await vi.advanceTimersByTimeAsync(LIMITS.milliseconds); await outcome;
  expect(h.reveal).not.toHaveBeenCalled(); expect(h.compose).not.toHaveBeenCalled();
  expect(vi.getTimerCount()).toBe(0);
});

it("cancels a finished but not yet presented still when the user changes the moment", async () => {
  const h = harness(); h.state.samples = LIMITS.samples; h.frame();
  expect(h.compose).toHaveBeenCalledTimes(1);
  h.controller.abort(); h.frame(); await h.promise;
  expect(h.reveal).not.toHaveBeenCalled();
  expect(h.update).not.toHaveBeenCalledWith("complete", expect.anything());
  expect(vi.getTimerCount()).toBe(0);
});

it("distinguishes shader compilation from completed samples and keeps final progress monotonic", async () => {
  const h = harness(); h.state.compiling = true; h.frame();
  expect(h.update).toHaveBeenLastCalledWith("compiling", 0);
  h.state.compiling = false;
  while (h.state.samples < LIMITS.samples) h.frame();
  h.frame(); h.state.ready = false; vi.advanceTimersByTime(600);
  expect(h.update).toHaveBeenLastCalledWith("finishing", LIMITS.samples);
  h.frame(); await h.promise;
  const counts = h.update.mock.calls.map(call => call[1] as number);
  expect(counts).toEqual([...counts].sort((a, b) => a - b));
});

it("measures completed work once before progress starts and then completes all 65 samples at the chosen resolution", async () => {
  const h = harness(true);
  while (!h.calibration.mock.calls.length) h.frame();
  expect(h.calibration).toHaveBeenCalledTimes(1);
  expect(h.calibration.mock.calls[0]![0]).toBeGreaterThan(0);
  expect(h.state.samples).toBe(0);
  expect(h.reveal).not.toHaveBeenCalled();
  while (h.state.samples < LIMITS.samples) h.frame();
  h.frame(); h.frame(); await h.promise;
  expect(h.calibration).toHaveBeenCalledTimes(1);
  expect(h.reveal).toHaveBeenCalledTimes(1);
  const changes = h.update.mock.calls;
  const start = changes.findIndex(call => call[0] === "sampling");
  expect(changes.slice(start).every(call => ["sampling", "finishing", "complete"].includes(call[0]))).toBe(true);
  const counts = changes.slice(start).map(call => call[1] as number);
  expect(counts).toEqual([...counts].sort((a, b) => a - b));
  expect(h.update).toHaveBeenLastCalledWith("complete", LIMITS.samples);
  expect(vi.getTimerCount()).toBe(0);
});
