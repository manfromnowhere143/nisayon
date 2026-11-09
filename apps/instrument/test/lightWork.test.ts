import { expect, it, vi } from "vitest";
import { lightWork } from "../src/scene/lightWork";

function device(timed = true) {
  const state = { done: false, ms: .25, disjoint: false, lost: false };
  const gl = {
    WAIT_FAILED: 1, TIMEOUT_EXPIRED: 2, CONDITION_SATISFIED: 3, SYNC_GPU_COMMANDS_COMPLETE: 4, QUERY_RESULT_AVAILABLE: 5, QUERY_RESULT: 6,
    getExtension: () => timed ? { TIME_ELAPSED_EXT: 7, GPU_DISJOINT_EXT: 8 } : null,
    getParameter: () => state.disjoint,
    createQuery: vi.fn(() => ({})), beginQuery: vi.fn(), endQuery: vi.fn(), deleteQuery: vi.fn(),
    getQueryParameter: vi.fn((_q, field) => field === 5 ? true : state.ms * 1e6),
    fenceSync: vi.fn(() => ({})), deleteSync: vi.fn(), flush: vi.fn(),
    clientWaitSync: vi.fn(() => state.done ? 3 : 2),
    isContextLost: () => state.lost,
  };
  return { state, gl, work: lightWork(gl as unknown as WebGL2RenderingContext) };
}

it("never queues a second batch behind unfinished work, and polls without blocking", () => {
  const { state, gl, work } = device();
  work.submit(() => 1);
  expect(work.ready()).toBe(false);
  const blocked = vi.fn(() => 1);
  expect(() => work.submit(blocked)).toThrow(/pending/);
  expect(blocked).not.toHaveBeenCalled();
  expect(gl.clientWaitSync).toHaveBeenLastCalledWith(expect.anything(), 0, 0);
  state.done = true;
  expect(work.ready()).toBe(true);
  expect(gl.deleteSync).toHaveBeenCalledTimes(1);
  expect(gl.deleteQuery).toHaveBeenCalledTimes(1);
  expect(work.limit()).toBe(2);
  work.dispose();
});

it("uses actual timer results to grow bounded batches and reduces them when the device slows", () => {
  const { state, work } = device(); state.done = true;
  for (let i = 0; i < 12; i++) { work.submit(() => work.limit()); work.ready(); }
  expect(work.limit()).toBe(8);
  state.ms = 64;
  work.submit(() => 8); work.ready();
  expect(work.limit()).toBe(1);
  expect(work.summary().measuredBatches).toBe(13);
  work.dispose();
});

it("does not invent GPU measurements without timer support or after a disjoint clock", () => {
  const fallback = device(false);
  fallback.work.submit(() => 2); fallback.work.ready();
  fallback.state.done = true; fallback.work.ready();
  expect(fallback.work.limit()).toBe(1);
  expect(fallback.work.summary()).toMatchObject({ timerSupported: false, measuredBatches: 0, p95BatchMs: null });
  fallback.work.dispose();
  const timed = device(); timed.state.done = true;
  timed.work.submit(() => 1); timed.work.ready();
  timed.state.disjoint = true;
  timed.work.submit(() => 2); timed.work.ready();
  expect(timed.work.summary().p95BatchMs).toBeNull();
  timed.work.dispose();
});

it("releases pending queries and fences on cancellation and ends a query after a failed submission", () => {
  const { gl, work } = device();
  expect(() => work.submit(() => { throw Error("shader failed"); })).toThrow("shader failed");
  expect(gl.endQuery).toHaveBeenCalledTimes(1);
  expect(gl.deleteQuery).toHaveBeenCalledTimes(1);
  work.submit(() => 1); work.dispose(); work.dispose();
  expect(gl.deleteQuery).toHaveBeenCalledTimes(2);
  expect(gl.deleteSync).toHaveBeenCalledTimes(1);
});
