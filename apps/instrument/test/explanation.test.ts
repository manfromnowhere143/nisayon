import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { associate, associateExplanation, parseProjection, ProjectionError, readbackCommands, type CheckSummary, type DependencyExplanation, type MeasurementReview } from "../src/qualification/projection";
const old = resolve("../../work/experiments/check-explanation-2026-11-16/examples"), current = resolve("../../work/experiments/json-underflow-2026-11-16/examples");
const bytes = (name: string, role = "explanation", folder = old) => new Uint8Array(readFileSync(resolve(folder, `${name}.${role}.json`)));
const raw = (name = "scoring_change", role = "explanation", folder = old): any => JSON.parse(new TextDecoder().decode(bytes(name, role, folder)));
const encode = (value: unknown) => new TextEncoder().encode(JSON.stringify(value));
const parse = (value: unknown) => parseProjection(encode(value));
const explain = (name = "scoring_change", folder = old) => parseProjection(bytes(name, "explanation", folder)) as DependencyExplanation;
const summary = (name = "scoring_change", folder = old) => parseProjection(bytes(name, "summary", folder)) as CheckSummary;
const review = (name = "literal_zero") => parseProjection(bytes(name, "measurement", current)) as MeasurementReview;
const invalid = (value: unknown, kind = "invalid") => { expect(() => parse(value)).toThrow(ProjectionError); try { parse(value); } catch (error) { expect((error as ProjectionError).kind).toBe(kind); } };
const fixtures = [
  ...JSON.parse(readFileSync(resolve(old, "index.json"), "utf8")).rows.map((row: any) => ({ id: row.id, folder: old, status: row.execution_status, files: [{ path: row.summary, sha256: row.summary_sha256 }, { path: row.explanation, sha256: row.explanation_sha256 }], measurement: false, checker: "0651a9d55fc2626d20a42c73a234fc57dc105254fc64bb2d9a4afa0781961a69" })),
  ...JSON.parse(readFileSync(resolve(current, "index.json"), "utf8")).examples.map((row: any) => ({ id: row.id, folder: current, status: row.execution_status, files: Object.values(row.projection_files) as { path: string; sha256: string }[], measurement: true, checker: "cd211f77a0abdd170212d1f46d9e018f3c1d82e0f749f1457903f94dc37ecb99" })),
];
it.each(fixtures)("reads and associates exact source bytes for $id", fixture => {
  for (const f of fixture.files) expect(createHash("sha256").update(readFileSync(resolve(fixture.folder, f.path))).digest("hex")).toBe(f.sha256);
  const s = summary(fixture.id, fixture.folder), e = explain(fixture.id, fixture.folder);
  expect(e.kind).toBe("explanation"); expect(e.status).toBe(fixture.status); expect(e.source.checker).toBe(fixture.checker);
  const m = fixture.measurement ? review(fixture.id) : null;
  expect(() => associateExplanation(s, e, m)).not.toThrow();
  if (m) expect(() => associate(s, m)).not.toThrow();
});
it("keeps the failed numeric observation distinct from a supported literal zero", () => {
  const refused = explain("nonzero_refused", current), m = review("nonzero_refused");
  expect(refused.checks.find(c => c.id === "observe")?.status).toBe("failed");
  expect(refused.checks.find(c => c.id === "score")?.status).toBe("not_attempted");
  expect(m.assessment).toBeNull(); expect(m.matches).toBeNull(); expect(m.status).toBe("unresolved");
  expect(review().assessment?.verdict).toBe("supported"); expect(review().matches).toBe(true);
});
it("compares keyed records independently of source array order", () => {
  const e = explain(); e.inputs.reverse(); e.checks.reverse(); e.changed.reverse();
  expect(() => associateExplanation(summary(), e)).not.toThrow();
});
it("preserves previous unknowns now bound and missing prior declarations", () => {
  const e = explain("calibration_rebound_pin"), input = e.inputs.find(i => i.id === "confirmation")!;
  expect(input.previousPresent).toBe(true); expect(input.previousSha).toBeNull(); expect(input.status).toBe("bound");
  expect(e.checks.find(c => c.id === "confirm")?.affected).toContainEqual({ input: "confirmation", reason: "unknown", via: "confirmation" });
  const r = raw("first_execution"); r.inputs[0].previous_present = false; r.inputs[0].previous_sha256 = null;
  expect((parse(r) as DependencyExplanation).inputs[0]!.previousPresent).toBe(false);
});
it("retains withheld diagnostics and unattempted reusable evidence without guessing", () => {
  expect(explain("missing_history").checks.find(c => c.id === "observe")?.reasons).toContainEqual({ code: "recorded_reason_detail_withheld", check: null });
  const e = explain("unattempted_reuse"), c = e.checks.find(c => c.id === "observe")!;
  expect(c.planned).toBe("reuse"); expect(c.attempted).toBeNull(); expect(c.status).toBe("not_attempted");
  expect(e.decisions[0]!.reusable).toContain("observe");
});
it("keeps completed requirements historical and accepts affected inputs without reason codes", () => {
  const e = explain(), score = e.checks.find(c => c.id === "score")!;
  expect(score.reasons).toEqual([]); expect(score.affected).toContainEqual({ input: "scoring", reason: "changed", via: "scoring" });
  expect(e.decisions[0]!.required).toContain("score"); expect(score.status).toBe("completed");
});
it.each([
  ["future schema", (r: any) => { r.schema += ".v2"; }, "unsupported"],
  ["missing source", (r: any) => { delete r.source; }],
  ["wrong record digest", (r: any) => { r.source.previous_record_sha256 = "z".repeat(64); }],
  ["duplicate node", (r: any) => { r.inputs.push(r.inputs[0]); }],
  ["cross-role node", (r: any) => { r.decisions[0].id = r.inputs[0].id; }],
  ["unknown node", (r: any) => { r.checks[0].depends_on.push("absent"); }],
  ["cycle", (r: any) => { r.checks.find((c: any) => c.id === "observe").depends_on.push("score"); }],
  ["self cycle", (r: any) => { r.checks[0].depends_on.push(r.checks[0].id); }],
  ["empty dependencies", (r: any) => { r.checks[0].depends_on = []; }],
  ["decision used as dependency", (r: any) => { r.checks[0].depends_on.push(r.decisions[0].id); }],
  ["duplicate edge", (r: any) => { r.checks[0].depends_on.push(r.checks[0].depends_on[0]); }],
  ["decision references input", (r: any) => { r.decisions[0].depends_on = ["data"]; }],
  ["wrong requirement role", (r: any) => { r.decisions[0].required_checks.push("scoring"); }],
  ["overlapping requirements", (r: any) => { r.decisions[0].reusable_checks.push(r.decisions[0].required_checks[0]); }],
  ["missing required check", (r: any) => { r.decisions[0].required_checks.pop(); }],
  ["unknown reason", (r: any) => { r.checks[0].reasons[0].code = "looks_safe"; }],
  ["private diagnostic injection", (r: any) => { r.checks[0].reasons[0].detail = "/private/owner/path"; }],
  ["invalid upstream reason", (r: any) => { r.checks[0].reasons = [{ code: "upstream_requires_check", check: "data" }]; }],
  ["non-upstream reason with a check", (r: any) => { r.checks[0].reasons[0].check = "observe"; }],
  ["unknown affected input", (r: any) => { r.checks[0].affected_inputs[0].input = "absent"; }],
  ["invalid via", (r: any) => { r.checks[0].affected_inputs[0].via = "review"; }],
  ["unreachable input via declared check", (r: any) => { r.checks.find((c: any) => c.id === "score").affected_inputs[0].via = "observe"; }],
  ["previous declaration disagreement", (r: any) => { r.inputs[0].previous_present = false; }],
  ["unknown current identity disagreement", (r: any) => { r.inputs[0].status = "unknown"; }],
  ["previous receipt disagreement", (r: any) => { r.checks[0].previous_receipt_present = false; }],
  ["previous model disagreement", (r: any) => { r.change.model_changed = true; }],
  ["record review disagreement", (r: any) => { r.record_review.reconstruction = "unresolved"; }],
  ["execution disagreement", (r: any) => { r.checks[0].execution_status = "failed"; }],
  ["unattempted action disagreement", (r: any) => { r.checks[0].attempted_action = null; }],
  ["freshness disagreement", (r: any) => { r.checks[0].refresh = "on_change"; }],
  ["unknown obligation code", (r: any) => { r.decisions[0].obligations = ["private:/owner/path"]; r.decisions[0].applicability = "unresolved"; }],
  ["unknown obligation input", (r: any) => { r.decisions[0].obligations = ["unknown_input:missing"]; r.decisions[0].applicability = "unresolved"; }],
  ["wrong planning count", (r: any) => { r.planning.obligation_count = 1; }],
  ["false attestation", (r: any) => { r.record_review.independent_execution_attestation = true; }],
  ["false acceptance", (r: any) => { r.automatic_acceptance = true; }],
  ["unknown authority field", (r: any) => { r.safe_to_deploy = true; }],
  ["removed limitations", (r: any) => { r.limitations = []; }],
  ["hostile identifier", (r: any) => { r.inputs[0].id = '<img src=x onerror="alert(1)">'; }],
  ["overlong identifier", (r: any) => { r.inputs[0].id = "a".repeat(81); }, "capacity"],
  ["node capacity", (r: any) => { r.inputs = Array.from({ length: 257 }, (_, i) => ({ ...r.inputs[0], id: `node${i}` })); }, "capacity"],
] as const)("refuses deliberate malformed explanation: %s", (_, mutate, kind: string = "invalid") => { const r = raw(); mutate(r); invalid(r, kind); });
it("bounds a dense graph before traversal without calling the science invalid", () => {
  const r = raw("first_execution"), input = r.inputs[0], check = r.checks.find((c: any) => c.id === "observe");
  r.inputs = Array.from({ length: 256 }, (_, i) => ({ ...input, id: `input${i}` }));
  r.checks = Array.from({ length: 34 }, (_, i) => ({ ...check, id: `check${i}`, depends_on: r.inputs.map((i: any) => i.id) }));
  r.decisions[0].depends_on = r.checks.map((c: any) => c.id); r.decisions[0].required_checks = [...r.decisions[0].depends_on];
  invalid(r, "capacity");
});
it.each(["bundle", "model", "checker"] as const)("refuses cross-record %s identity joins", key => {
  const e = explain(); e.source[key] = "0".repeat(64); expect(() => associateExplanation(summary(), e)).toThrow(/does not match/);
});
it.each([
  (e: DependencyExplanation) => { e.executionSchema = "nisayon.qualification.check_execution.v1"; },
  (e: DependencyExplanation) => { e.reconstruction = "unresolved"; },
  (e: DependencyExplanation) => { e.status = "unresolved"; },
  (e: DependencyExplanation) => { e.changed = []; },
  (e: DependencyExplanation) => { e.previous++; },
  (e: DependencyExplanation) => { e.modelChanged = true; },
  (e: DependencyExplanation) => { e.inputs[0]!.sha = "0".repeat(64); },
  (e: DependencyExplanation) => { e.inputs[0]!.kind = "other"; },
  (e: DependencyExplanation) => { e.inputs[0]!.status = "unknown"; },
  (e: DependencyExplanation) => { e.checks[0]!.planned = "reuse"; },
  (e: DependencyExplanation) => { e.checks[0]!.attempted = null; },
  (e: DependencyExplanation) => { e.checks[0]!.artifact = null; },
  (e: DependencyExplanation) => { e.checks[0]!.kind = "analysis"; },
  (e: DependencyExplanation) => { e.checks.pop(); },
])("refuses inconsistent explanation association %#", mutate => { const e = explain(); mutate(e); expect(() => associateExplanation(summary(), e)).toThrow(/does not match/); });
it("checks selected measurement direct edges when all three records are present", () => {
  const e = explain("literal_zero", current); e.checks.find(c => c.id === "score")!.depends = ["scoring"];
  expect(() => associateExplanation(summary("literal_zero", current), e, review())).toThrow(/does not match/);
});
it("refuses cross-generation companions even when graphs resemble one another", () => {
  expect(() => associateExplanation(summary(), explain("literal_zero", current))).toThrow(/does not match/);
});
it("preserves tiny clock tokens without doing scientific arithmetic", () => {
  const r = raw("nonzero_refused", "summary", current);
  for (const check of r.checks) if (check.elapsed_seconds !== null) check.elapsed_seconds = 0;
  const source = JSON.stringify(r).replace(/"workflow_wall_seconds":[^,]+/, '"workflow_wall_seconds":1e-400');
  expect((parseProjection(new TextEncoder().encode(source)) as CheckSummary).workflow).toBe("1e-400");
  expect(() => parseProjection(new TextEncoder().encode(source.replace('"workflow_wall_seconds":1e-400', '"workflow_wall_seconds":-1e-400')))).toThrow(/nonnegative/);
});
it("quotes explanation commands for the same archive pin", () => {
  const commands = readbackCommands(summary(), null, "/tmp/a'b $(touch nope).zip", explain());
  expect(commands).toHaveLength(2); expect(commands[1]).toContain("explain-check-bundle '/tmp/a'\"'\"'b $(touch nope).zip'");
  expect(commands[1]).toContain(summary().source.bundle);
});
