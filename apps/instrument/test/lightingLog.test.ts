import { expect, it } from "vitest";
import { lightingEvent } from "../dev/lightingLog";

it("retains bounded rendering diagnostics and discards unrelated client fields", () => {
  const event = { page: "00000000-0000-0000-0000-000000000001", at: "2026-09-20T18:00:00.000Z", attempt: 1, phase: "sampling", samples: 12, elapsedMs: 2500, gpu: { timerSupported: false, batches: 60, measuredBatches: 0, p95BatchMs: null } };
  expect(lightingEvent({ ...event, url: "private query", source: "private evidence", arbitrary: new Array(1000) })).toEqual(event);
  expect(lightingEvent({ ...event, samples: NaN })).toBeNull();
  expect(lightingEvent({ ...event, phase: "made-up" })).toBeNull();
  expect(lightingEvent({ ...event, page: "../../path" })).toBeNull();
  expect(lightingEvent({ ...event, reason: "x".repeat(513), gpu: { timerSupported: true, p95BatchMs: Infinity } })).toEqual({ ...event, gpu: undefined });
});
