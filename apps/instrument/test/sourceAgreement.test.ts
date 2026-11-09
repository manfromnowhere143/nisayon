// @vitest-environment node
// Corruptions have valid byte hashes: the loader must also bind their meaning.
import { createHash } from "node:crypto";
import { expect, it } from "vitest";
import { ResourceCache, openCase, openGeneration, openRun, type LoaderOptions } from "../src/data/loader";
import { sha256Hex } from "../src/data/digest";
import { fetchFromDisk, readRealJson } from "./fixture";

const options: LoaderOptions = { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 16 * 1024 * 1024 };
async function prepare() {
  const cache = new ResourceCache();
  const { generation } = await openGeneration("http://fixture.test/fixtures/ui/d01/evidence.json", undefined, options);
  const caseRecord = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = caseRecord.runs.find((r) => r.role === "reference")!;
  return { generation, caseRecord, run, cache };
}
type RawFrames = { model: { path: string; sha256: string }; raw_source_id: string; frames: { stored_time_s: number; state_sha256: string }[] };
it.each(["clock", "state", "model", "raw source"] as const)("keeps readings but removes a reconstruction with a mismatched %s", async (fault) => {
  const { generation, caseRecord, run, cache } = await prepare();
  const raw = readRealJson(run.frames!.path) as RawFrames;
  if (fault === "clock") raw.frames[0]!.stored_time_s += 0.01;
  if (fault === "state") raw.frames[0]!.state_sha256 = "0".repeat(64);
  if (fault === "raw source") raw.raw_source_id = "raw:another-recording";
  if (fault === "model") raw.model = { ...raw.model, sha256: "0".repeat(64), path: `objects/${"0".repeat(64)}.json` };
  const bytes = new TextEncoder().encode(JSON.stringify(raw));
  const digest = createHash("sha256").update(bytes).digest("hex");
  run.frames = { ...run.frames!, path: `objects/${digest}.json`, sha256: digest, byte_length: bytes.byteLength };
  generation.files.push(run.frames);
  const opts = { ...options, fetch: async (url: string) => url.endsWith(run.frames!.path) ? new Response(bytes) : options.fetch(url) };
  const loaded = await openRun(generation, caseRecord, run.run, undefined, opts, cache);
  expect(loaded.samples.rows).toHaveLength(44);
  expect(loaded.samples.rows[0]!.next_sim_time_s).toBe(0.05000000000000003);
  expect(loaded.frames).toBeNull();
  expect(loaded.framesIssue?.kind).toBe("decode");
});
it("removes cached reconstruction if its model is unavailable on reopening", async () => {
  const { generation, caseRecord, run, cache } = await prepare();
  const first = await openRun(generation, caseRecord, run.run, undefined, options, cache);
  expect(first.frames).not.toBeNull();
  const broken = { ...caseRecord, runs: [{ ...run, model: null }] };
  const loaded = await openRun(generation, broken, run.run, undefined, options, cache);
  expect(loaded.samples.rows).toHaveLength(44);
  expect(loaded.frames).toBeNull();
  expect(loaded.framesIssue).not.toBeNull();
});
it("rechecks frame state binding when an unchanged frame object comes from cache", async () => {
  const { generation, caseRecord, run, cache } = await prepare();
  await openRun(generation, caseRecord, run.run, undefined, options, cache);
  const raw = readRealJson(run.samples.path) as { rows: { original: { state_before_sha256: string } }[] };
  raw.rows[0]!.original.state_before_sha256 = "0".repeat(64);
  const bytes = new TextEncoder().encode(JSON.stringify(raw));
  const digest = createHash("sha256").update(bytes).digest("hex");
  run.samples = { ...run.samples, path: `objects/${digest}.json`, sha256: digest, byte_length: bytes.byteLength };
  generation.files.push(run.samples);
  const opts = { ...options, fetch: async (url: string) => url.endsWith(run.samples.path) ? new Response(bytes) : options.fetch(url) };
  const loaded = await openRun(generation, caseRecord, run.run, undefined, opts, cache);
  expect(loaded.samples.rows).toHaveLength(44);
  expect(loaded.frames).toBeNull();
  expect(loaded.framesIssue?.message).toContain("state digest");
});
