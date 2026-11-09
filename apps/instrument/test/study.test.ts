import { describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { discoverStudy, loadStudy, loadStudyReport, loadStudyTrial } from "../src/data/study";
import { ResourceCache, openCase, openGeneration, openRun, type LoaderOptions } from "../src/data/loader";
import { decodeModelV1, decodeReconstructionV1 } from "../src/model/decodeV1";
import { fetchFromDisk, REPO_ROOT } from "./fixture";

const options: LoaderOptions = { fetch: fetchFromDisk(), digest: async bytes => createHash("sha256").update(new Uint8Array(bytes)).digest("hex"), maxBytes: 16 * 1024 * 1024 };

describe("current engine study admission", () => {
  it("admits all assignments and preserves D05's rejected progress obligation", async () => {
    const study = await loadStudy(await discoverStudy(undefined, options), undefined, options);
    expect(study.counts).toEqual({ trials: 26, pairs: 660, records: 1474, unscheduled: 6 });
    const trials = await Promise.all(study.trials.map(e => loadStudyTrial(e, undefined, options)));
    const d05 = trials.find(t => t.case_id === "D05-recurrent-carry" && t.arm === "A")!;
    expect(d05.historical_decision?.decision).toBe("rejected");
    expect(d05.historical_decision?.reasons).toEqual(expect.arrayContaining([expect.objectContaining({ code: "progress_lost" })]));
    expect(trials.filter(t => !t.confirmation)).toHaveLength(6);
    for (const ref of Object.values(study.reports)) await expect(loadStudyReport(ref, undefined, options)).resolves.toHaveProperty("record");
  });

  it("rejects corrupted bytes, conflicting membership, and an invalid object identity", async () => {
    const ref = await discoverStudy(undefined, options);
    const study = await loadStudy(ref, undefined, options);
    const bad = { ...options, fetch: async () => new Response("{}") };
    await expect(loadStudy(ref, undefined, bad)).rejects.toThrow();
    await expect(loadStudyTrial({ ...study.trials[0]!, arm: "invented" }, undefined, options)).rejects.toThrow(/identity/);
    const raw = JSON.parse(readFileSync(join(REPO_ROOT, "fixtures/ui/study", ref.path), "utf8"));
    raw.counts.pairs++;
    const bytes = JSON.stringify(raw), sha256 = createHash("sha256").update(bytes).digest("hex");
    await expect(loadStudy({ ...ref, path: `generations/${sha256}.json`, sha256, byte_length: Buffer.byteLength(bytes) }, undefined, { ...options, fetch: async () => new Response(bytes) })).rejects.toThrow(/totals/);
    await expect(loadStudyTrial({ ...study.trials[0]!, object: { ...study.trials[0]!.object, path: "../../private.json" } }, undefined, options)).rejects.toThrow();
  });
});

describe("retained physical state and configuration", () => {
  it("uses native actuator dimensions and real plan configurations; rejects malformed state", async () => {
    const base = "http://fixture.test/fixtures/ui/recorded/D03-observation-backlog/";
    const { generation } = await openGeneration(base + "evidence.json", undefined, options);
    const cache = new ResourceCache();
    const record = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
    const r = record.runs.find(r => r.role === "regression" && r.stage === "diagnostic")!;
    const run = await openRun(generation, record, r.run, undefined, options, cache);
    expect(r.plan?.deployment).toMatchObject({ observation_delay_steps: 3 });
    expect(record.plans.length).toBeGreaterThan(0);
    expect(run.model?.joints?.find(j => j.name === "robot0_joint4")?.range).toEqual([-3.0718, -0.0698]);
    expect(run.model?.actuators?.map(a => [a.unit, a.controlRange])).toEqual([
      ...Array.from({ length: 5 }, () => ["N m", [-80, 80]]), ...Array.from({ length: 2 }, () => ["N m", [-12, 12]]), ["m", [0, .04]], ["m", [-.04, 0]]
    ]);
    expect(run.frames?.rows[30]?.before.physical?.qpos).toHaveLength(16);
    expect(run.frames?.rows[30]?.before.physical?.qvel).toHaveLength(15);
    expect(run.frames?.rows[30]?.after.physical?.ctrl).toHaveLength(9);
    const rawModel = await options.fetch(base + r.model!.path).then(r => r.json());
    const model = decodeModelV1(rawModel);
    const raw = await options.fetch(base + r.frames!.path).then(r => r.json());
    raw.frames[0].physical.qpos.pop();
    expect(() => decodeReconstructionV1(raw, { run: r.run, rowCount: r.row_count }, model)).toThrow();
  });
});
