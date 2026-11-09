import { beforeEach, expect, it, vi } from "vitest";
import { createProgressClient, decodeProgress, mergeProgress, PROGRESS_URL, REFRESH_MS, SAVED_PROGRESS } from "../src/research/progress";

const at = "2026-10-22T21:00:00Z";
function item(number = 5062) {
  const repo = "huggingface/lerobot", url = `https://github.com/${repo}/pull/${number}`;
  return { number, html_url: url, repository_url: `https://api.github.com/repos/${repo}`, user: { login: "manfromnowhere143" }, title: "Preserve checkpoint recovery", state: "open", draft: false, updated_at: at, pull_request: { url: `https://api.github.com/repos/${repo}/pulls/${number}`, html_url: url, merged_at: null as string | null } };
}
const envelope = (items = [item()]) => ({ total_count: items.length, incomplete_results: false, items });
beforeEach(() => sessionStorage.clear());

it("requires merge evidence and keeps closed, draft and open states distinct", () => {
  const open = item(1), draft = { ...item(2), draft: true }, closed = { ...item(3), state: "closed" }, merged = { ...item(4), state: "closed" };
  merged.pull_request.merged_at = at;
  expect(decodeProgress(envelope([open, draft, closed, merged]), at).records.map(r => r.status)).toEqual(["open", "draft", "closed", "merged"]);
  expect(() => decodeProgress(envelope([{ ...merged, state: "open" }]), at)).toThrow("Conflicting merge");
  const missing = item(); delete (missing.pull_request as { merged_at?: string | null }).merged_at;
  expect(() => decodeProgress(envelope([missing]), at)).toThrow("date");
});

it("discovers a new public contribution only within the registered author and repository scope", () => {
  const next = item(6000), foreign = { ...item(6001), user: { login: "someone-else" } }, outside = { ...item(6002), repository_url: "https://api.github.com/repos/unknown/private" };
  const result = decodeProgress(envelope([next, foreign, outside]), at);
  expect(result.records.map(r => r.url)).toEqual([next.html_url]);
  expect(mergeProgress(SAVED_PROGRESS, result).records).toHaveLength(13);
});

it("rejects substituted links, duplicated identities and unknown metadata", () => {
  expect(() => decodeProgress(envelope([{ ...item(), html_url: "javascript:alert(1)" }]), at)).toThrow("identity");
  expect(() => decodeProgress(envelope([item(), item()]), at)).toThrow("identity");
  expect(() => decodeProgress(envelope([{ ...item(), draft: undefined } as never]), at)).toThrow("metadata");
  expect(() => decodeProgress({ ...envelope(), incomplete_results: undefined }, at)).toThrow("envelope");
});

it("retains omitted records and their observation dates when search is empty or partial", () => {
  const partial = decodeProgress({ ...envelope([]), total_count: 110, incomplete_results: true }, at);
  const result = mergeProgress(SAVED_PROGRESS, partial);
  expect(result.records).toEqual(SAVED_PROGRESS.records);
  expect(result.partial).toBe(true);
  expect(result.records[0]!.observedAt).toBe(SAVED_PROGRESS.records[0]!.observedAt);
});

it("uses one bounded credential-free GET and conditional refreshes without repeating on remount", async () => {
  let now = Date.parse(at);
  const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify(envelope()), { headers: { ETag: '"public-progress"' } })).mockResolvedValueOnce(new Response(null, { status: 304 }));
  const client = createProgressClient(fetcher, () => now);
  const [first, repeated] = await Promise.all([client.refresh(), client.refresh()]);
  expect(first).toBe(repeated); expect(first.connection).toBe("current"); expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0]![0]).toBe(PROGRESS_URL);
  expect(fetcher.mock.calls[0]![1]).toMatchObject({ method: "GET", credentials: "omit", referrerPolicy: "no-referrer", redirect: "error" });
  await createProgressClient(fetcher, () => now).refresh(); expect(fetcher).toHaveBeenCalledTimes(1);
  now += REFRESH_MS; await client.refresh(); expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls[1]![1]?.headers).toMatchObject({ "If-None-Match": '"public-progress"' });
  expect(client.current().connection).toBe("current");
});

it("retains saved results through rate limits and honors the server retry time", async () => {
  let now = Date.parse(at);
  const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response("rate limited", { status: 429, headers: { "Retry-After": "3600" } }));
  const client = createProgressClient(fetcher, () => now);
  expect((await client.refresh()).connection).toBe("unavailable");
  expect(client.current().records).toEqual(SAVED_PROGRESS.records);
  now += REFRESH_MS; await client.refresh(); expect(fetcher).toHaveBeenCalledTimes(1);
  now += 3600_000; await client.refresh(); expect(fetcher).toHaveBeenCalledTimes(2);
});

it("rejects oversized and conflicting responses without replacing saved evidence", async () => {
  for (const body of [" ".repeat(512_001), '{"total_count":0,"total_count":1,"items":[],"incomplete_results":false}']) {
    const client = createProgressClient(vi.fn<typeof fetch>().mockResolvedValue(new Response(body)), () => Date.parse(at));
    const value = await client.refresh(); expect(value.connection).toBe("unavailable"); expect(value.records).toEqual(SAVED_PROGRESS.records);
  }
});
