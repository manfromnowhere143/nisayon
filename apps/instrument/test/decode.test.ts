// @vitest-environment node
import { describe, expect, it } from "vitest";
import { DecodeError, UnsupportedSchemaError, decodeCase, decodeEvidence, decodeFrames, decodeManifest, decodeModel, decodeSamples, relativePath } from "../src/model/decode";
import { generationDir, readJson } from "./fixture";

const gen = generationDir();
const evidence = decodeEvidence(readJson("evidence.json"));
const manifestJson = readJson(`${gen}/manifest.json`);
const manifest = decodeManifest(manifestJson, evidence.current.generation_sha256, `http://fixture.test/dev-fixture/${gen}/manifest.json`);
const caseRef = manifest.cases[0]!;
const caseRecord = decodeCase(readJson(`${gen}/${caseRef.path}`));
const regression = caseRecord.runs.find((r) => r.role === "regression")!;
const expectation = { run: regression.run, rowCount: regression.row_count, actionDimension: caseRecord.predicates.action_dimension };

describe("fixture decodes", () => {
  it("reads evidence, manifest, case, samples, frames and model", () => {
    expect(manifest.cases.length).toBe(1);
    expect(caseRecord.runs.map((r) => r.role).sort()).toEqual(["correction", "reference", "regression"]);
    expect(regression.row_count).toBe(400);
    const samples = decodeSamples(readJson(`${gen}/${regression.samples.path}`), expectation);
    expect(samples.rows.length).toBe(400);
    expect(samples.rows[0]!.intended_action.length).toBe(7);
    const frames = decodeFrames(readJson(`${gen}/${regression.frames!.path}`), expectation);
    expect(frames.rows.length).toBe(400);
    expect(frames.body_count).toBe(24);
    expect(frames.rows[0]!.before.xpos.length).toBe(24 * 3);
    const model = decodeModel(readJson(`${gen}/${regression.model!.path}`));
    expect(model.bodies.length).toBe(24);
    expect(model.schematic.links.length).toBeGreaterThan(8);
    expect(model.meshes.available).toBe(false);
  });

  it("keeps the retained residual maxima on the manifest", () => {
    expect(manifest.residuals?.qualification_max_cube_height_difference_m).toBeCloseTo(0.0005579657636821667, 12);
    expect(manifest.residuals?.qualification_max_eef_coordinate_difference_m).toBeCloseTo(0.0004987299592940087, 12);
  });
});

describe("decode rejects", () => {
  it("unknown schema versions", () => {
    expect(() => decodeManifest({ ...(manifestJson as object), schema: "nisayon.ui.dev-generation.v9" }, "0".repeat(64), "http://x/m.json")).toThrow(UnsupportedSchemaError);
  });

  it("duplicate run identities", () => {
    const raw = readJson(`${gen}/${caseRef.path}`) as { runs: unknown[] };
    expect(() => decodeCase({ ...raw, runs: [raw.runs[0], raw.runs[0]] })).toThrow(/duplicate run identity/);
  });

  it("non-finite numbers", () => {
    const raw = readJson(`${gen}/${regression.samples.path}`) as { rows: { cube_height_m: number }[] };
    const rows = raw.rows.map((r, i) => (i === 3 ? { ...r, cube_height_m: Number.POSITIVE_INFINITY } : r));
    expect(() => decodeSamples({ ...raw, rows }, expectation)).toThrow(/finite/);
  });

  it("a samples file that belongs to another run", () => {
    const raw = readJson(`${gen}/${regression.samples.path}`);
    const other = caseRecord.runs.find((r) => r.role === "reference")!;
    expect(() => decodeSamples(raw, { ...expectation, run: other.run, rowCount: other.row_count })).toThrow(/not the selected run/);
  });

  it("row counts that differ from the run record", () => {
    const raw = readJson(`${gen}/${regression.samples.path}`) as { rows: unknown[] };
    expect(() => decodeSamples({ ...raw, rows: raw.rows.slice(0, 10) }, expectation)).toThrow(/expected 400 rows/);
  });

  it("path traversal and absolute paths", () => {
    expect(() => relativePath("../secret.json", "p")).toThrow(DecodeError);
    expect(() => relativePath("/etc/passwd", "p")).toThrow(DecodeError);
    expect(() => relativePath("https://example.org/x.json", "p")).toThrow(DecodeError);
    expect(() => relativePath("a/%2e%2e/b.json", "p")).toThrow(DecodeError);
    expect(relativePath("runs/reference-0.samples.json", "p")).toBe("runs/reference-0.samples.json");
  });

  it("an unexpected coordinate convention", () => {
    const raw = readJson(`${gen}/${regression.frames!.path}`) as { coordinate_convention: Record<string, string> };
    expect(() => decodeFrames({ ...raw, coordinate_convention: { ...raw.coordinate_convention, up: "y" } }, expectation)).toThrow(/z-up/);
  });

  it("a wrong action dimension", () => {
    const raw = readJson(`${gen}/${regression.samples.path}`);
    expect(() => decodeSamples(raw, { ...expectation, actionDimension: 6 })).toThrow(/expected 6 numbers/);
  });
});
