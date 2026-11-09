// @vitest-environment node
// Node-side decode costs of the largest real objects. These are proxies for
// main-thread work, recorded to size the loading design; they are not browser
// measurements and are reported as such.
import { describe, expect, it } from "vitest";
import { strictParseJson } from "../src/data/strictJson";
import { createHash } from "node:crypto";
import { decodeCaseV1, decodeDiscoveryV1, decodeManifestV1, decodeModelV1, decodeReconstructionV1, decodeSamplesV1 } from "../src/model/decodeV1";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { REAL_DIR, readRealJson } from "./fixture";

describe("decode cost of the real regression run (node proxy)", () => {
  it("records hash, parse and decode wall times", () => {
    const evidence = decodeDiscoveryV1(readRealJson("evidence.json"));
    const manifest = decodeManifestV1(readRealJson(evidence.current.manifest_path), evidence.current.generation_sha256, "http://x/generations/m.json", "http://x/");
    const caseRecord = decodeCaseV1(readRealJson(manifest.cases[0]!.path), manifest);
    const regression = caseRecord.runs.find((r) => r.role === "regression")!;
    const model = decodeModelV1(readRealJson(regression.model!.path));
    const report: Record<string, number> = {};
    for (const [label, ref] of [
      ["samples", regression.samples],
      ["reconstruction", regression.frames!],
    ] as const) {
      const bytes = readFileSync(join(REAL_DIR, ref.path));
      let t = performance.now();
      createHash("sha256").update(bytes).digest("hex");
      report[`${label}_hash_ms`] = performance.now() - t;
      t = performance.now();
      const json = strictParseJson(bytes.toString("utf8"));
      report[`${label}_parse_ms`] = performance.now() - t;
      t = performance.now();
      if (label === "samples") decodeSamplesV1(json, { run: regression.run, rowCount: regression.row_count, actionDimension: 7 });
      else decodeReconstructionV1(json, { run: regression.run, rowCount: regression.row_count }, model);
      report[`${label}_decode_ms`] = performance.now() - t;
      report[`${label}_bytes`] = bytes.byteLength;
    }
    console.log(`[decode-cost] ${JSON.stringify(report)}`);
    expect(report.reconstruction_decode_ms).toBeLessThan(2000);
    expect(report.samples_decode_ms).toBeLessThan(2000);
  });
});
