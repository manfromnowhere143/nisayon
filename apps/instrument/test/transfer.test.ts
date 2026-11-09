// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { transferBytes } from "../src/data/transfer";
import { defaultOptions, fetchVerified } from "../src/data/loader";
import { sha256Hex } from "../src/data/digest";

afterEach(() => vi.useRealTimers());

it("finishes a progressing download beyond the former 30-second geometry cutoff", async () => {
  vi.useFakeTimers();
  const received: number[] = [];
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 1; i <= 5; i++)
        setTimeout(() => {
          controller.enqueue(Uint8Array.of(i));
          if (i === 5) controller.close();
        }, i * 10_000);
    },
  });
  const loading = transferBytes(
    "https://test/geometry",
    async () => new Response(body),
    {
      maxBytes: 5,
      expectedBytes: 5,
      onProgress: (p) => received.push(p.loaded),
    },
  );
  await vi.advanceTimersByTimeAsync(50_000);
  expect([...new Uint8Array(await loading)]).toEqual([1, 2, 3, 4, 5]);
  expect(received).toEqual([0, 1, 2, 3, 4, 5]);
  expect(vi.getTimerCount()).toBe(0);
});

it("cancels a stalled response even when the fetch adapter ignores abort", async () => {
  vi.useFakeTimers();
  let signal: AbortSignal;
  const loading = transferBytes(
    "https://test/stall",
    async (_url, init) => {
      signal = init.signal;
      return new Promise<Response>(() => {});
    },
    { maxBytes: 10 },
  );
  const rejected = expect(loading).rejects.toMatchObject({
    kind: "network",
    message: expect.stringMatching(/stopped making progress/),
  });
  await vi.advanceTimersByTimeAsync(20_000);
  await rejected;
  expect(signal!.aborted).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});

it("cancels a body that stops after headers and preserves selection cancellation", async () => {
  vi.useFakeTimers();
  const cancel = vi.fn();
  const selection = new AbortController();
  const loading = transferBytes(
    "https://test/body",
    async () => new Response(new ReadableStream({ cancel })),
    {
      maxBytes: 10,
      signal: selection.signal,
    },
  );
  const rejected = expect(loading).rejects.toMatchObject({ kind: "aborted" });
  await vi.advanceTimersByTimeAsync(1);
  selection.abort();
  await rejected;
  expect(cancel).toHaveBeenCalledOnce();
  expect(vi.getTimerCount()).toBe(0);
});

it("retries one broken connection and verifies the fresh bytes", async () => {
  const bytes = new TextEncoder().encode('{"verified":true}');
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("connection reset"))
    .mockResolvedValueOnce(new Response(bytes));
  const result = await fetchVerified(
    "https://test/object",
    { byte_length: bytes.length, sha256: await sha256Hex(bytes.buffer) },
    "run",
    undefined,
    { ...defaultOptions(), fetch },
  );
  expect(result.json).toEqual({ verified: true });
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("never retries or accepts an integrity mismatch", async () => {
  const fetch = vi.fn(async () => new Response("{}"));
  await expect(
    fetchVerified(
      "https://test/object",
      { sha256: "0".repeat(64) },
      "run",
      undefined,
      { ...defaultOptions(), fetch },
    ),
  ).rejects.toMatchObject({ issue: { kind: "integrity" } });
  expect(fetch).toHaveBeenCalledOnce();
});

it("uses declared uncompressed bytes for progress, keeping the byte bound", async () => {
  const progress = vi.fn();
  const options = { maxBytes: 4, expectedBytes: 4, onProgress: progress };
  await transferBytes(
    "https://test/compressed",
    async () =>
      new Response("1234", {
        headers: { "content-encoding": "br", "content-length": "2" },
      }),
    options,
  );
  expect(progress).toHaveBeenLastCalledWith({ loaded: 4, total: 4 });
  await expect(
    transferBytes(
      "https://test/oversize",
      async () => new Response("12345"),
      options,
    ),
  ).rejects.toMatchObject({ kind: "decode" });
});
