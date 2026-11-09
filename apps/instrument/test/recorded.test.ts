// @vitest-environment node
import { describe, expect, it } from "vitest";
import { sha256Hex } from "../src/data/digest";
import { openLibrary } from "../src/data/library";
import { ResourceCache, openCase, openGeneration, openRun, type LoaderOptions } from "../src/data/loader";
import { contextualFinding, evaluatorForRun, pairedRun } from "../src/model/findings";
import { fetchFromDisk } from "./fixture";

const options: LoaderOptions = { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 16 * 1024 * 1024 };
const root = "http://fixture.test/fixtures/ui/recorded/";
async function load(id: string, cache = new ResourceCache()) {
  const { generation } = await openGeneration(`${root}${id}/evidence.json`, undefined, options);
  const record = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = await openRun(generation, record, record.runs.find((r) => r.role === "regression")!.run, undefined, options, cache);
  return { generation, record, run, cache };
}

describe("recorded library integration", () => {
  it("reopens a historical pin even when discovery disappears, without fetching it", async () => {
    const pin = "0ee415adfbca09e60a090a2f545c4e9d1193cc8a057a7648b1486148207e93c7";
    const requests: string[] = [];
    const opts = { ...options, fetch: async (url: string) => { requests.push(url); return url.endsWith("evidence.json") ? new Response("gone", { status: 404 }) : options.fetch(url); } };
    const opened = await openGeneration("http://fixture.test/fixtures/ui/d01/evidence.json", undefined, opts, pin);
    expect(opened.generation.sha256).toBe(pin);
    expect(requests).toEqual([`http://fixture.test/fixtures/ui/d01/generations/${pin}.json`]);
    await expect(openGeneration("http://fixture.test/fixtures/ui/d01/evidence.json", undefined, opts, "0".repeat(64))).rejects.toMatchObject({ stage: "manifest", issue: { kind: "absent" } });
  });

  it("uses the D03 age finding and retains task completion", async () => {
    const { record, run } = await load("D03-observation-backlog");
    const finding = contextualFinding(record, run.record, run.samples.rows);
    expect(finding.row).toBe(1);
    expect(finding.headline).toContain("Observation arrives late at step 1");
    expect(finding.detail).toContain("50 ms");
    expect(run.record.task_outcome).toBe("completed");
    expect(run.samples.rows.slice(0, 4).map((r) => r.observation_age_s)).toEqual([0, 0.05000000000000003, 0.10000000000000007, expect.closeTo(0.15, 12)]);
  });

  it("binds D05 condition 10423 to its frozen pair, rejection and real trial bytes", async () => {
    const { generation, record, cache } = await load("D05-recurrent-carry");
    const candidate = record.runs.find((r) => r.run.run_id === "confirmation-correction-10423")!;
    const reference = pairedRun(record, candidate)!;
    expect(reference.run.run_id).toBe("confirmation-reference-10423");
    expect(reference.condition_id).toBe(candidate.condition_id);
    expect(reference.run.bundle_sha256).toBe(candidate.run.bundle_sha256);
    expect(pairedRun(record, reference)?.run).toEqual(candidate.run);
    const entry = evaluatorForRun(record, candidate)!;
    expect(entry.progress).toBe("lost");
    const decision = record.decisions.confirmation_decision!.content as Record<string, unknown>;
    expect(decision.decision).toBe("rejected");
    expect(decision.reasons).toContainEqual({ code: "progress_lost", detail: "lift.cube_raised: gain 0.002936 m is below the minimum 0.01", run_id: candidate.run.run_id, severity: "rejected" });
    expect(record.decisions.trial).toMatchObject({ sha256: "d90039d8a88a1a7996f52642fcc8c21395fd1a572bc650b69ad842383ce726fb", byte_length: 3522 });
    const run = await openRun(generation, record, candidate.run, undefined, options, cache);
    expect(contextualFinding(record, candidate, run.samples.rows).row).toBeNull();
  });

  it("keeps unsupported, invalid and unavailable separate", async () => {
    const d06 = await load("D06-stateless-inference");
    const d08 = await load("D08-old-future-replay");
    const d10 = await load("D10-opaque-policy-state");
    expect(d06.record.trial?.status).toBe("unsupported");
    expect(d08.record.trial?.status).toBe("invalid");
    for (const item of [d06, d08, d10]) expect((item.record.decisions.diagnostic_decision!.content as Record<string, unknown>).decision).toBe("unresolved");
    expect(d08.record.runs.some((r) => r.run.run_id === "invalid-replay-control")).toBe(false);
    expect(d10.run.samples.rows.every((r) => r.policy.before === "unavailable")).toBe(true);
    expect(contextualFinding(d10.record, d10.run.record, d10.run.samples.rows).headline).toBe("Policy state was not recorded.");
  });

  it("loads the six-case discovery and bounds the cache over 20 switches (Node only)", async () => {
    const library = await openLibrary(options, undefined, `${root}library.json`);
    expect(library).toHaveLength(6);
    const cache = new ResourceCache(16);
    for (let i = 0; i < 20; i += 1) {
      const entry = library[i % library.length]!;
      const loaded = await load(entry.caseId, cache);
      expect(loaded.generation.sha256).toBe(entry.generation);
      expect(cache.size).toBeLessThanOrEqual(16);
    }
  });
});
