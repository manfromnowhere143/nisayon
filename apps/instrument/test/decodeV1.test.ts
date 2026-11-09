// @vitest-environment node
import { describe, expect, it } from "vitest";
import { DecodeError } from "../src/model/decode";
import { decodeCaseV1, decodeDecisionV1, decodeDiscoveryV1, decodeManifestV1, decodeModelV1, decodeReconstructionV1, decodeSamplesV1 } from "../src/model/decodeV1";
import { firstActionMismatch } from "../src/model/findings";
import { readRealJson } from "./fixture";

const evidence = decodeDiscoveryV1(readRealJson("evidence.json"));
const manifest = decodeManifestV1(readRealJson(evidence.current.manifest_path), evidence.current.generation_sha256, `http://fixture.test/fixtures/ui/d01/${evidence.current.manifest_path}`, "http://fixture.test/fixtures/ui/d01/");
const caseRef = manifest.cases[0]!;
const caseRecord = decodeCaseV1(readRealJson(caseRef.path), manifest);
const regression = caseRecord.runs.find((r) => r.role === "regression")!;
const expectation = { run: regression.run, rowCount: regression.row_count, actionDimension: caseRecord.predicates.action_dimension };

describe("the data lane's D01 generation decodes", () => {
  it("discovers the manifest by its own digest and lists one case", () => {
    expect(evidence.current.generation_sha256).toBe("0ee415adfbca09e60a090a2f545c4e9d1193cc8a057a7648b1486148207e93c7");
    expect(manifest.cases.length).toBe(1);
    expect(caseRef.case_key).toBe("development-ablation-001/D01-gripper-sign/B");
    expect(manifest.bundle_sha256).toBe("373e33e88bd43538a56ce7cf111e5db10519a0afe4f9bc5ae46340e4502d856a");
    expect(manifest.source_bindings.length).toBeGreaterThan(10);
  });

  it("carries three diagnostic runs with separate statuses and a required decision object", () => {
    expect(caseRecord.runs.map((r) => `${r.role}:${r.task_outcome}`).sort()).toEqual(["candidate:completed", "reference:completed", "regression:failed"]);
    expect(regression.row_count).toBe(400);
    expect(regression.evaluator?.progress).toBe("lost");
    expect(caseRecord.decisionRefs.length).toBe(1);
    expect(caseRecord.confirmation?.availability).toBe("not_in_this_generation");
    expect(caseRecord.findings[0]?.code).toBe("gripper_transport_mismatch");
    expect(caseRecord.findings[0]?.row_index).toBe(0);
  });

  it("decodes samples with memory states and the computed mismatch still lands on step 0", () => {
    const samples = decodeSamplesV1(readRealJson(regression.samples.path), expectation);
    expect(samples.rows.length).toBe(400);
    expect(samples.rows[0]!.policy.before).toBe("initialized_none");
    expect(samples.rows[0]!.policy.after).toBe("present");
    expect(samples.rows[0]!.policy.hidden_before_present).toBe(false);
    expect(samples.rows[0]!.locators.pointer).toBe("/runs/1/trace/0");
    const m = firstActionMismatch(samples.rows)!;
    expect(m.row_index).toBe(0);
    expect(m.component).toBe(6);
    expect(m.executed).toBe(1);
  });

  it("decodes the model into strokes and drawable primitives", () => {
    const model = decodeModelV1(readRealJson(regression.model!.path));
    expect(model.bodies.length).toBe(24);
    expect(model.sites.find((s) => s.name === "gripper0_grip_site")?.index).toBe(2);
    expect(model.schematic.links.length).toBe(13);
    const drawn = model.schematic.drawable_geoms.map((i) => model.geoms[i]!.name);
    expect(drawn).toContain("table_visual");
    expect(drawn).toContain("cube_g0_vis");
    expect(drawn).not.toContain("table_collision");
    expect(drawn).not.toContain("cube_g0");
    expect(drawn.some((n) => n.startsWith("wall_"))).toBe(false);
    expect(model.meshes.available).toBe(false);
  });

  it("decodes reconstruction frames in the model's order with residuals", () => {
    const model = decodeModelV1(readRealJson(regression.model!.path));
    const reference = caseRecord.runs.find((r) => r.role === "reference")!;
    const frames = decodeReconstructionV1(readRealJson(reference.frames!.path), { run: reference.run, rowCount: reference.row_count }, model);
    expect(frames.rows.length).toBe(44);
    expect(frames.body_count).toBe(24);
    expect(frames.geom_count).toBe(21);
    const after0 = frames.rows[0]!.after;
    expect(after0.residual_cube_height_m).toBeCloseTo(0.0005579657636821667, 12);
    expect(frames.rows[0]!.before.residual_cube_height_m).toBeNull();
    expect(after0.grip_site_xpos[2]).toBeGreaterThan(0.9);
    expect(frames.maximum_residuals.cube_height_difference_m).toBeCloseTo(0.0005579657636821667, 12);
    expect(after0.derived_cube_z_m).not.toBeNull();
  });

  it("rejects frames whose count or convention disagree", () => {
    const model = decodeModelV1(readRealJson(regression.model!.path));
    const raw = readRealJson(regression.frames!.path) as { frames: unknown[]; convention: Record<string, string> };
    expect(() => decodeReconstructionV1({ ...raw, frames: raw.frames.slice(0, 10) }, expectation, model)).toThrow(/expected 800 frames/);
    expect(() => decodeReconstructionV1({ ...raw, convention: { ...raw.convention, up: "Y" } }, expectation, model)).toThrow(DecodeError);
  });

  it("rejects an object path that does not carry its digest", () => {
    const raw = readRealJson(evidence.current.manifest_path) as { files: { path: string; sha256: string }[] };
    const files = raw.files.map((f, i) => (i === 0 ? { ...f, path: "objects/" + "0".repeat(64) + ".json" } : f));
    expect(() => decodeManifestV1({ ...raw, files }, "0".repeat(64), "http://x/generations/x.json", "http://x/")).toThrow(/carry its own digest/);
  });
});

describe("source agreement beyond byte hashes", () => {
  it("rejects a case reference that disagrees with the manifest registry", () => {
    const raw = readRealJson(evidence.current.manifest_path) as { cases: { object: { byte_length: number } }[] };
    raw.cases[0]!.object.byte_length += 1;
    expect(() => decodeManifestV1(raw, manifest.sha256, manifest.manifestUrl, manifest.baseUrl)).toThrow(/manifest registry/);
  });
  it("rejects run objects whose length disagrees with the manifest registry", () => {
    const raw = readRealJson(caseRef.path) as { runs: { samples: { byte_length: number } }[] };
    raw.runs[0]!.samples.byte_length += 1;
    expect(() => decodeCaseV1(raw, manifest)).toThrow(/manifest registry/);
  });
  it("rejects a run whose claimed bundle is not the bound source", () => {
    const raw = readRealJson(caseRef.path) as { runs: { key: { bundle_sha256: string } }[] };
    raw.runs[0]!.key.bundle_sha256 = "1".repeat(64);
    expect(() => decodeCaseV1(raw, manifest)).toThrow(/run source binding/);
  });
  it("rejects invalid model ancestry without silently remapping bodies", () => {
    const raw = readRealJson(regression.model!.path) as { bodies: { parent_id: number }[] };
    raw.bodies[1]!.parent_id = 23;
    expect(() => decodeModelV1(raw)).toThrow(/ancestry/);
  });
  it("rejects a non-unit retained rotation rather than correcting it", () => {
    const raw = readRealJson(regression.frames!.path) as { frames: { bodies: number[][] }[] };
    raw.frames[0]!.bodies[1]![3] = 2;
    const model = decodeModelV1(readRealJson(regression.model!.path));
    expect(() => decodeReconstructionV1(raw, expectation, model)).toThrow(/unit quaternion/);
  });
  it("rejects a projected time that differs from its original reading", () => {
    const raw = readRealJson(regression.samples.path) as { rows: { next_sim_time_s: number }[] };
    raw.rows[0]!.next_sim_time_s += 0.01;
    expect(() => decodeSamplesV1(raw, expectation)).toThrow(/original reading/);
  });
  it("does not treat missing memory as initialized state", () => {
    const raw = readRealJson(regression.samples.path) as { rows: { memory: { before_sha256: string | null } }[] };
    raw.rows[0]!.memory.before_sha256 = null;
    expect(() => decodeSamplesV1(raw, expectation)).toThrow(/memory digest|memory availability/);
  });
});


it.each(["bundle_sha256", "source_canonical_bundle_sha256"])("rejects an evaluator result with the wrong %s", (field) => {
  const raw = readRealJson(caseRecord.decisionRefs[0]!.path) as Record<string, unknown>;
  raw[field] = "0".repeat(64);
  expect(() => decodeDecisionV1(raw, manifest)).toThrow(/decision source or bundle binding/);
});
