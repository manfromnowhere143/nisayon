import { afterEach, expect, it, vi } from "vitest";
import { openProjection, readExampleBytes } from "../src/qualification/projectionClient";
import { PROJECTION_BYTES } from "../src/qualification/projection";
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
it("terminates an aborted import before a late file read can post bytes", async () => {
  const terminate = vi.fn(), postMessage = vi.fn();
  vi.stubGlobal("Worker", class { terminate = terminate; postMessage = postMessage; });
  let finish!: (value: ArrayBuffer) => void;
  const file = { size: 100, name: "record.json", arrayBuffer: () => new Promise<ArrayBuffer>(resolve => { finish = resolve; }) } as File;
  const controller = new AbortController(), task = openProjection(file, controller.signal);
  const rejected = expect(task).rejects.toMatchObject({ name: "AbortError" }); controller.abort(); await rejected;
  finish(new ArrayBuffer(100)); await Promise.resolve(); expect(terminate).toHaveBeenCalledOnce(); expect(postMessage).not.toHaveBeenCalled();
});
it("bounds a stalled reader and releases its worker", async () => {
  vi.useFakeTimers(); const terminate = vi.fn();
  vi.stubGlobal("Worker", class { terminate = terminate; postMessage = vi.fn(); });
  const file = { size: 10, name: "record.json", arrayBuffer: () => new Promise(() => {}) } as File;
  const task = openProjection(file, new AbortController().signal), rejected = expect(task).rejects.toMatchObject({ kind: "capacity" });
  await vi.advanceTimersByTimeAsync(8000); await rejected; expect(terminate).toHaveBeenCalledOnce();
});
it("refuses over-capacity files before allocating a worker", async () => {
  const worker = vi.fn(); vi.stubGlobal("Worker", worker);
  await expect(openProjection({ size: PROJECTION_BYTES + 1 } as File, new AbortController().signal)).rejects.toMatchObject({ kind: "capacity" });
  expect(worker).not.toHaveBeenCalled();
});
it("cancels a streaming example as soon as its bounded download overflows", async () => {
  const reader = { read: vi.fn().mockResolvedValueOnce({ done: false, value: new Uint8Array(PROJECTION_BYTES) }).mockResolvedValueOnce({ done: false, value: new Uint8Array(1) }), cancel: vi.fn(async () => {}), releaseLock: vi.fn() };
  await expect(readExampleBytes({ body: { getReader: () => reader } } as unknown as Response)).rejects.toMatchObject({ kind: "capacity" });
  expect(reader.read).toHaveBeenCalledTimes(2); expect(reader.cancel).toHaveBeenCalledOnce(); expect(reader.releaseLock).toHaveBeenCalledOnce();
});
