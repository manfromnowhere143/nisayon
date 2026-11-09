// @vitest-environment node
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { VISUAL_ASSET } from "../src/scene/visualAssetPin";
import { decodeVisualAsset } from "../src/scene/visualCodec";
import {
  defaultOptions,
  openCase,
  openGeneration,
  openRun,
  ResourceCache,
} from "../src/data/loader";
import { fetchFromDisk, REPO_ROOT } from "./fixture";

const geometry = decodeVisualAsset(
  JSON.parse(readFileSync(join(REPO_ROOT, VISUAL_ASSET.path), "utf8")),
  VISUAL_ASSET.sha256,
);
class WorkerStandIn {
  static instance: WorkerStandIn;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessageerror: (() => void) | null = null;
  terminate = vi.fn();
  postMessage = vi.fn();
  constructor() {
    WorkerStandIn.instance = this;
  }
}
beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("keeps the geometry worker alive during a real-progress sequence over 30 seconds", async () => {
  // The worker stand-in tests its lifecycle. Real emitted workers and production
  // bytes are exercised separately by the release probe, without a GPU claim.
  vi.useRealTimers();
  const options = { ...defaultOptions(), fetch: fetchFromDisk() };
  const { generation } = await openGeneration(
    "http://fixture.test/fixtures/ui/recorded/D01-gripper-sign/evidence.json",
    undefined,
    options,
  );
  const cache = new ResourceCache();
  const record = await openCase(
    generation,
    generation.cases[0]!.case_key,
    undefined,
    options,
    cache,
  );
  const run = await openRun(
    generation,
    record,
    record.runs.find((r) => r.role === "regression")!.run,
    undefined,
    options,
    cache,
  );
  vi.useFakeTimers();
  vi.stubGlobal("Worker", WorkerStandIn);
  vi.stubGlobal("location", { href: "http://fixture.test/" });
  const { loadVisualAsset } = await import("../src/scene/visualAssets");
  const progress = vi.fn();
  const loading = loadVisualAsset(
    run.model!,
    run.record.model!.sha256,
    generation,
    { ...options, onProgress: progress },
  );
  const worker = WorkerStandIn.instance;
  for (let i = 1; i <= 5; i++) {
    await vi.advanceTimersByTimeAsync(10_000);
    worker.onmessage!({
      data: {
        progress: { stage: "run", url: VISUAL_ASSET.path, loaded: i, total: 5 },
      },
    });
    expect(worker.terminate).not.toHaveBeenCalled();
  }
  worker.onmessage!({ data: { asset: geometry } });
  expect(await loading).toBe(geometry);
  expect(progress).toHaveBeenCalledTimes(5);
  expect(worker.terminate).toHaveBeenCalledOnce();
  expect(vi.getTimerCount()).toBe(0);
});
