// @vitest-environment node
import { describe, expect, it } from "vitest";
import { ResourceCache, openCase, openGeneration, openRun, type LoaderOptions } from "../src/data/loader";
import { sha256Hex } from "../src/data/digest";
import { firstActionMismatch } from "../src/model/findings";
import { fetchFromDisk } from "./fixture";

const BASE = "http://fixture.test/";

function options(): LoaderOptions {
  return { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 64 * 1024 * 1024 };
}

describe("the real D01 generation through the verified loader", () => {
  it("opens the generation, the case with its decision object, and every run", async () => {
    const opts = options();
    const cache = new ResourceCache(32);
    const { generation } = await openGeneration(`${BASE}fixtures/ui/d01/evidence.json`, undefined, opts);
    expect(generation.sha256).toBe("0ee415adfbca09e60a090a2f545c4e9d1193cc8a057a7648b1486148207e93c7");
    const caseRecord = await openCase(generation, generation.cases[0]!.case_key, undefined, opts, cache);
    expect(Object.keys(caseRecord.decisions)).toEqual(["diagnostic_decision"]);
    const decision = caseRecord.decisions.diagnostic_decision!.content as Record<string, unknown>;
    expect(decision.decision).toBe("unresolved");
    for (const record of caseRecord.runs) {
      const run = await openRun(generation, caseRecord, record.run, undefined, opts, cache);
      expect(run.samples.rows.length).toBe(record.row_count);
      expect(run.frames?.rows.length).toBe(record.row_count);
      expect(run.model?.bodies.length).toBe(24);
      expect(run.framesIssue).toBeNull();
      expect(run.record.recording.last_next_sim_time_s).not.toBeNull();
      const mismatch = firstActionMismatch(run.samples.rows);
      expect(mismatch?.row_index).toBe(0);
    }
  });
});
