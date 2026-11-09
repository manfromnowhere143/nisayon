// @vitest-environment node
import { describe, expect, it } from "vitest";
import { decodeCase, decodeEvidence, decodeManifest, decodeSamples } from "../src/model/decode";
import { describeMismatch, firstActionMismatch, observationAgeViolations, pairedRun } from "../src/model/findings";
import { generationDir, readJson } from "./fixture";

const gen = generationDir();
const evidence = decodeEvidence(readJson("evidence.json"));
const manifest = decodeManifest(readJson(`${gen}/manifest.json`), evidence.current.generation_sha256, "http://fixture.test/m.json");
const caseRecord = decodeCase(readJson(`${gen}/${manifest.cases[0]!.path}`));

function samplesFor(role: string) {
  const run = caseRecord.runs.find((r) => r.role === role)!;
  return { run, samples: decodeSamples(readJson(`${gen}/${run.samples.path}`), { run: run.run, rowCount: run.row_count, actionDimension: 7 }) };
}

describe("D01 first mismatch is computed from data", () => {
  it("lands on step 0, gripper component, reversed sign in the regression run", () => {
    const { samples } = samplesFor("regression");
    const m = firstActionMismatch(samples.rows)!;
    expect(m.row_index).toBe(0);
    expect(m.step).toBe(0);
    expect(m.component).toBe(6);
    expect(m.intended).toBeCloseTo(-1.0001353025436401, 12);
    expect(m.executed).toBe(1.0);
    expect(describeMismatch(m, samples.rows.length).headline).toBe("Gripper command reversed at step 0.");
  });

  it("is a clip, not a reversal, in the reference run", () => {
    const { samples } = samplesFor("reference");
    const m = firstActionMismatch(samples.rows)!;
    expect(m.row_index).toBe(0);
    expect(m.component).toBe(6);
    expect(m.executed).toBe(-1.0);
    expect(describeMismatch(m, samples.rows.length).headline).toBe("Gripper command clipped at step 0.");
  });

  it("agrees with the export's own finding", () => {
    const { run, samples } = samplesFor("regression");
    const exported = caseRecord.findings.find((f) => f.run.run_id === run.run.run_id)!;
    const computed = firstActionMismatch(samples.rows)!;
    expect(exported.row_index).toBe(computed.row_index);
    expect(exported.component).toBe(computed.component);
    expect(exported.intended).toBe(computed.intended);
    expect(exported.executed).toBe(computed.executed);
  });

  it("finds no observation-age violation in D01 against 1e-9 s", () => {
    const { samples } = samplesFor("regression");
    expect(observationAgeViolations(samples.rows, caseRecord.predicates.max_observation_age_s)).toHaveLength(0);
  });

  it("pairs a regression with the reference and the reference with the regression", () => {
    const reference = caseRecord.runs.find((r) => r.role === "reference")!;
    const regression = caseRecord.runs.find((r) => r.role === "regression")!;
    expect(pairedRun(caseRecord, regression)?.run.run_id).toBe("reference-0");
    expect(pairedRun(caseRecord, reference)?.run.run_id).toBe("regression-0");
  });
});
