import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { associate, parseProjection, PROJECTION_BYTES, ProjectionError, readbackCommands, type CheckSummary, type MeasurementReview } from "../src/qualification/projection";
const packet = resolve("../../work/research/ui-engine-integration-2026-11-16");
const index = JSON.parse(readFileSync(resolve(packet, "fixtures-index.json"), "utf8")) as { rows: { id: string; summary: string; summary_sha256: string; measurement_review?: string; measurement_review_sha256?: string; expected_execution: string; expected_review_status?: string; expected_measurement_verdict?: string | null }[] };
const bytes = (name: string, kind = "summary") => new Uint8Array(readFileSync(resolve(packet, `fixtures/${name}.${kind}.json`)));
const record = (name = "software_claim_mismatch", kind = "summary") => JSON.parse(new TextDecoder().decode(bytes(name, kind)));
const encode = (value: unknown) => new TextEncoder().encode(JSON.stringify(value));
const read = (value: unknown) => parseProjection(encode(value));
const summary = () => read(record()) as CheckSummary;
const measurement = () => read(record("software_claim_mismatch", "measurement")) as MeasurementReview;
const rejects = (value: unknown, kind = "invalid") => { try { read(value); throw new Error("accepted invalid control"); } catch (e) { expect(e).toBeInstanceOf(ProjectionError); expect((e as ProjectionError).kind).toBe(kind); } };

describe("retained source-pinned projections, original bytes", () => {
  it.each(index.rows)("reads $id without promoting execution to acceptance", row => {
    const raw = new Uint8Array(readFileSync(resolve(packet, row.summary)));
    expect(createHash("sha256").update(raw).digest("hex")).toBe(row.summary_sha256);
    const s = parseProjection(raw) as CheckSummary;
    expect(s.kind).toBe("summary"); expect(s.status).toBe(row.expected_execution);
    if (row.measurement_review) {
      const b = new Uint8Array(readFileSync(resolve(packet, row.measurement_review)));
      expect(createHash("sha256").update(b).digest("hex")).toBe(row.measurement_review_sha256);
      const m = parseProjection(b) as MeasurementReview;
      expect(m.status).toBe(row.expected_review_status); expect(m.assessment?.verdict ?? null).toBe(row.expected_measurement_verdict);
      expect(() => associate(s, m)).not.toThrow();
    }
  });
});
it("keeps same-headline assessment disagreement distinct", () => {
  const r = record("software_claim_mismatch", "measurement"); r.recorded_verdict = r.assessment.verdict;
  const m = read(r) as MeasurementReview;
  expect(m.status).toBe("claim_mismatch"); expect(m.matches).toBe(false); expect(m.recorded).toBe(m.assessment?.verdict);
});
it("does not count an unattempted planned reuse as consumed evidence", () => {
  const r = record("software_partial");
  const c = r.checks.find((c: { execution_status: string; kind: string }) => c.execution_status === "not_attempted" && c.kind === "review"); c.planned_action = "reuse";
  const s = read(r) as CheckSummary; const planned = s.checks.find(check => check.id === c.id)!;
  expect(planned.planned).toBe("reuse"); expect(planned.attempted).toBeNull(); expect(planned.status).toBe("not_attempted");
});
it("preserves exact represented clock text above 2^53", () => {
  const source = new TextDecoder().decode(bytes("software_claim_mismatch")).replace(/"workflow_wall_seconds": [^,]+/, '"workflow_wall_seconds": 9007199254740993');
  expect((parseProjection(new TextEncoder().encode(source)) as CheckSummary).workflow).toBe("9007199254740993");
});
it.each([
  ["unknown schema", (r: any) => { r.schema += ".future"; }, "unsupported"],
  ["missing field", (r: any) => { delete r.context; }],
  ["bad digest", (r: any) => { r.source.bundle_sha256 = "A".repeat(64); }],
  ["duplicate check", (r: any) => { r.checks.push(r.checks[0]); }],
  ["unknown changed input", (r: any) => { r.change.input_ids = ["absent"]; }],
  ["bound unknown input", (r: any) => { r.inputs[0].status = "unknown"; }],
  ["false acceptance", (r: any) => { r.decision.automatic_acceptance = true; }],
  ["invented authority", (r: any) => { r.accepted = true; }],
  ["invented complete cost", (r: any) => { r.costs.complete_cost = 0; }],
  ["numeric string clock", (r: any) => { r.costs.workflow_wall_seconds = "1"; }],
  ["negative clock", (r: any) => { r.costs.workflow_wall_seconds = -1; }],
  ["nested costs counted twice", (r: any) => { r.costs.workflow_wall_seconds = .00001; }],
  ["false acquisition success", (r: any) => { r.execution.acquisition.reason_code = "input_acquisition_failed"; }],
  ["false completion", (r: any) => { r.checks[0].execution_status = "failed"; }],
  ["action disagreement", (r: any) => { r.checks[1].attempted_action = "reuse"; }],
  ["prototype key", (r: any) => { Object.defineProperty(r, "__proto__", { value: {}, enumerable: true }); }],
  ["text capacity", (r: any) => { r.limitations[0] = "x".repeat(8193); }, "capacity"],
  ["row capacity", (r: any) => { r.inputs = Array.from({ length: 257 }, (_, i) => ({ ...r.inputs[0], id: `item${i}` })); }, "capacity"],
] as const)("refuses deliberate invalid control: %s", (_, mutate, kind: string = "invalid") => { const r = record(); mutate(r); rejects(r, kind); });
it.each(["bundle", "model", "checker", "contract", "observation", "saved"] as const)("refuses a measurement join with differing %s bytes", field => {
  const m = measurement(); m.source[field] = "0".repeat(64); expect(() => associate(summary(), m)).toThrow(/does not match/);
});
it("refuses differing execution state and selected check identities", () => {
  const m = measurement(); m.execution = "unresolved"; expect(() => associate(summary(), m)).toThrow();
  const n = measurement(); n.selection.observation = "confirm"; expect(() => associate(summary(), n)).toThrow();
});
it.each([
  (r: any) => { r.assessment_matches = true; },
  (r: any) => { r.automatic_acceptance = true; },
  (r: any) => { r.assessment.extra_acceptance = true; },
  (r: any) => { r.assessment.checks.push(r.assessment.checks[0]); },
  (r: any) => { r.assessment.verdict = "supported"; },
  (r: any) => { r.assessment = null; },
])("refuses inconsistent or invented measured authority %#", mutate => { const r = record("software_claim_mismatch", "measurement"); mutate(r); rejects(r); });
it("refuses duplicate keys, malformed UTF-8, overflow and oversized JSON", () => {
  expect(() => parseProjection(new TextEncoder().encode('{"schema":"x","schema":"y"}'))).toThrow(/duplicate/);
  expect(() => parseProjection(new Uint8Array([0xff]))).toThrow();
  const raw = new TextDecoder().decode(bytes("software_claim_mismatch")).replace(/"workflow_wall_seconds": [^,]+/, '"workflow_wall_seconds": 1e9999');
  expect(() => parseProjection(new TextEncoder().encode(raw))).toThrow(/finite/);
  expect(() => parseProjection(new Uint8Array(PROJECTION_BYTES + 1))).toThrow(/2 MiB/);
});
it("quotes a user path without executing or interpolating it", () => {
  const path = "/tmp/a'b $(touch nope);`whoami`.zip";
  const command = readbackCommands(summary(), measurement(), path)[1]!;
  expect(command).toContain("'/tmp/a'\"'\"'b $(touch nope);`whoami`.zip'");
  expect(command).toContain("--observation-check 'observe'");
});
