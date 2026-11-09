// @vitest-environment node
import { describe, expect, it } from "vitest";
import { LoadError, ResourceCache, openCase, openGeneration, openRun, resolveWithin, type LoaderOptions } from "../src/data/loader";
import { sha256Hex } from "../src/data/digest";
import { fetchFromDisk } from "./fixture";

const BASE = "http://fixture.test/";

function options(): LoaderOptions {
  return { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 64 * 1024 * 1024 };
}

async function openAll(evidence: string) {
  const opts = options();
  const cache = new ResourceCache();
  const { generation } = await openGeneration(`${BASE}${evidence}`, undefined, opts);
  const caseRecord = await openCase(generation, generation.cases[0]!.case_key, undefined, opts, cache);
  const reference = caseRecord.runs.find((r) => r.role === "reference")!;
  const run = await openRun(generation, caseRecord, reference.run, undefined, opts, cache);
  return { generation, caseRecord, run, cache };
}

describe("verified loading", () => {
  it("starts all three bound run-object transfers before any completes, then checks their agreement", async () => {
    const opts = options(), cache = new ResourceCache();
    const { generation } = await openGeneration(`${BASE}dev-fixture/evidence.json`, undefined, opts);
    const caseRecord = await openCase(generation, generation.cases[0]!.case_key, undefined, opts, cache);
    const record = caseRecord.runs.find((run) => run.role === "regression")!;
    const started: string[] = [];
    let release = () => {};
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const loading = openRun(generation, caseRecord, record.run, undefined, { ...opts, fetch: async (url, init) => { started.push(url); await gate; return opts.fetch(url, init); } }, cache);
    await Promise.resolve();
    expect(started).toHaveLength(3);
    expect(started.some((url) => url.endsWith(record.samples.path))).toBe(true);
    expect(started.some((url) => url.endsWith(record.model!.path))).toBe(true);
    expect(started.some((url) => url.endsWith(record.frames!.path))).toBe(true);
    release();
    const run = await loading;
    expect(run.frames?.rows.length).toBe(record.row_count);
    expect(run.framesIssue).toBeNull();
  });
  it("opens the generation, case and run with byte verification", async () => {
    const { generation, run, cache } = await openAll("dev-fixture/evidence.json");
    expect(generation.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(run.samples.rows.length).toBe(44);
    expect(run.frames?.rows.length).toBe(44);
    expect(run.framesIssue).toBeNull();
    expect(run.model?.bodies.length).toBe(24);
    expect(cache.size).toBeGreaterThan(0);
  });

  it("reports a changed child byte as an integrity failure with both digests", async () => {
    await expect(openAll("dev-fixture-corrupt-child/evidence.json")).rejects.toMatchObject({
      name: "LoadError",
      stage: "run",
      issue: { kind: "integrity", expected: expect.stringMatching(/^[0-9a-f]{64}$/), actual: expect.stringMatching(/^[0-9a-f]{64}$/) },
    });
  });

  it("refuses a root whose digest does not match the evidence", async () => {
    await expect(openAll("dev-fixture-wrong-root/evidence.json")).rejects.toMatchObject({ stage: "manifest", issue: { kind: "integrity" } });
  });

  it("keeps original readings when optional frames are missing", async () => {
    const { run } = await openAll("dev-fixture-missing-frames/evidence.json");
    expect(run.samples.rows.length).toBe(44);
    expect(run.frames).toBeNull();
    expect(run.framesIssue?.kind).toBe("absent");
  });

  it("names an unsupported schema version", async () => {
    await expect(openAll("dev-fixture-unknown-schema/evidence.json")).rejects.toMatchObject({ stage: "manifest", issue: { kind: "unsupported-schema", actual: "nisayon.ui.dev-generation.v9" } });
  });

  it("reports absent evidence", async () => {
    await expect(openAll("dev-fixture-absent/evidence.json")).rejects.toMatchObject({ stage: "evidence", issue: { kind: "absent" } });
  });

  it("drops a superseded load instead of resolving it", async () => {
    const controller = new AbortController();
    const opts = options();
    const slowFetch: LoaderOptions["fetch"] = async (input, init) => {
      const response = await opts.fetch(input, init);
      controller.abort();
      return response;
    };
    await expect(openGeneration(`${BASE}dev-fixture/evidence.json`, controller.signal, { ...opts, fetch: slowFetch })).rejects.toMatchObject({ issue: { kind: "aborted" } });
  });

  it("refuses paths that escape the generation root", () => {
    expect(() => resolveWithin("http://fixture.test/dev-fixture/generations/abc/", "../../evidence.json", "run")).toThrow(LoadError);
    expect(resolveWithin("http://fixture.test/dev-fixture/generations/abc/", "runs/x.json", "run")).toBe("http://fixture.test/dev-fixture/generations/abc/runs/x.json");
  });

  it("rejects a run that is not in the case", async () => {
    const { generation, caseRecord } = await openAll("dev-fixture/evidence.json");
    await expect(openRun(generation, caseRecord, { bundle_sha256: "0".repeat(64), run_id: "reference-0" }, undefined, options(), new ResourceCache())).rejects.toMatchObject({ issue: { kind: "absent" } });
  });
});
