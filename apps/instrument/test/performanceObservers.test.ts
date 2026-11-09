import { expect, it, vi, afterEach } from "vitest";
import { frameTiming } from "../src/perf/frameTiming";
import { Metrics } from "../src/perf/metrics";

afterEach(() => vi.unstubAllGlobals());
it("bounds pending GPU queries, never waits, discards disjoint results and releases each query", () => {
  let available = false, disjoint = false;
  const gl = { getExtension: vi.fn(() => ({ TIME_ELAPSED_EXT: 1, GPU_DISJOINT_EXT: 2 })), isContextLost: () => false, getParameter: () => disjoint, createQuery: vi.fn(() => ({})), beginQuery: vi.fn(), endQuery: vi.fn(), deleteQuery: vi.fn(), QUERY_RESULT_AVAILABLE: 3, QUERY_RESULT: 4, getQueryParameter: (_q: unknown, name: number) => name === 3 ? available : 4e6 };
  const timer = frameTiming(gl as unknown as WebGL2RenderingContext);
  for (let i = 0; i < 20; i++) timer.end(timer.begin());
  expect(gl.createQuery).toHaveBeenCalledTimes(8);
  available = true;
  expect(timer.summary().gpu).toMatchObject({ count: 8, p95: 4 });
  expect(gl.deleteQuery).toHaveBeenCalledTimes(8);
  available = false;
  timer.end(timer.begin()); disjoint = true;
  timer.end(timer.begin());
  expect(timer.summary().gpu.count).toBe(8);
  expect(gl.createQuery).toHaveBeenCalledTimes(9);
  expect(gl.deleteQuery).toHaveBeenCalledTimes(9);
  timer.dispose(); expect(gl.deleteQuery).toHaveBeenCalledTimes(9);
});

it("keeps API absence distinct from zero and records the maximum event per real interaction", () => {
  const missing = new Metrics();
  vi.stubGlobal("PerformanceObserver", undefined);
  missing.observeBrowser()();
  expect(missing.summary().browserEvents).toEqual({ supported: false, count: 0, p95: null, max: null });
  const callbacks: ((v: { getEntries: () => unknown[] }) => void)[] = [], stopped = vi.fn();
  vi.stubGlobal("PerformanceObserver", class {
    static supportedEntryTypes = ["event", "longtask"];
    constructor(callback: (v: { getEntries: () => unknown[] }) => void) { callbacks.push(callback); }
    observe() {} disconnect() { stopped(); }
  });
  const metrics = new Metrics(), stop = metrics.observeBrowser();
  callbacks[0]!({ getEntries: () => [{ interactionId: 0, duration: 900 }, { interactionId: 11, duration: 24 }, { interactionId: 11, duration: 48 }, { interactionId: 12, duration: 32 }] });
  callbacks[1]!({ getEntries: () => [{ duration: 82 }] });
  expect(metrics.summary().browserEvents).toMatchObject({ supported: true, count: 2, max: 48 });
  expect(metrics.summary().longTasks).toMatchObject({ supported: true, count: 1, totalMs: 82 });
  stop(); expect(stopped).toHaveBeenCalledTimes(2);
});
