// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { BufferGeometry, Mesh } from "three";
import { sha256Hex } from "../src/data/digest";
import { ResourceCache, openCase, openGeneration, openRun } from "../src/data/loader";
import { VISUAL_ASSET } from "../src/scene/visualAssetPin";
import { checkVisualBinding, decodeVisualAsset, type VisualAsset } from "../src/scene/visualAssets";
import { buildNativeSurfaces } from "../src/scene/nativeSurface";
import { fetchFromDisk, REPO_ROOT } from "./fixture";

const options = { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 16 * 1024 * 1024 };
const bytes = readFileSync(join(REPO_ROOT, VISUAL_ASSET.path));
const raw = JSON.parse(bytes.toString()) as Record<string, unknown>;
let asset: VisualAsset;
beforeAll(() => {
  const start = performance.now();
  asset = decodeVisualAsset(raw, VISUAL_ASSET.sha256);
  console.log("[visual-decode-node-only]", JSON.stringify({ bytes: bytes.length, decode_ms: performance.now() - start }));
});
async function retained() {
  const { generation } = await openGeneration("http://fixture.test/fixtures/ui/d01/evidence.json", undefined, options);
  const cache = new ResourceCache();
  const record = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = await openRun(generation, record, record.runs.find((r) => r.role === "regression")!.run, undefined, options, cache);
  return { generation, run };
}

describe("optional native visual geometry", () => {
  it("pins the exact package bytes and the original D01 model and assets", async () => {
    expect(bytes.length).toBe(VISUAL_ASSET.byte_length);
    expect(await sha256Hex(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))).toBe(VISUAL_ASSET.sha256);
    const { generation, run } = await retained();
    expect(() => checkVisualBinding(asset, run.model!, run.record.model!.sha256, generation)).not.toThrow();
    expect(asset.parts).toHaveLength(54);
    expect(asset.meshes).toHaveLength(53);
  });

  it("refuses an unqualified model or a generation missing a source mesh", async () => {
    const { generation, run } = await retained();
    expect(() => checkVisualBinding(asset, run.model!, "0".repeat(64), generation)).toThrow(/not qualified/);
    const missing = { ...generation, source_bindings: generation.source_bindings.filter((s) => s.sha256 !== asset.meshes[0]!.source_sha256) };
    expect(() => checkVisualBinding(asset, run.model!, run.record.model!.sha256, missing)).toThrow(/source asset/);
    const changed = { ...run.model!, bodies: run.model!.bodies.map((b) => b.index === 3 ? { ...b, name: "different_robot" } : b) };
    expect(() => checkVisualBinding(asset, changed, run.record.model!.sha256, generation)).toThrow(/body order/);
  });

  it("rejects triangle indices outside the published surface", () => {
    const meshes = (raw.meshes as Record<string, unknown>[]).slice();
    const first = { ...meshes[0]! };
    const encoded = Buffer.from(first.indices_u32_le as string, "base64");
    encoded.writeUInt32LE(first.vertex_count as number, 0);
    first.indices_u32_le = encoded.toString("base64");
    meshes[0] = first;
    expect(() => decodeVisualAsset({ ...raw, meshes }, VISUAL_ASSET.sha256)).toThrow(/absent vertex/);
  });

  it("seeks without reallocating geometry and disposes shared surfaces once", async () => {
    const { run } = await retained();
    const surfaces = buildNativeSurfaces(asset);
    const geometries = new Set<BufferGeometry>();
    surfaces.primary.root.traverse((o) => { if (o instanceof Mesh) geometries.add(o.geometry); });
    expect(geometries.size).toBe(53);
    const spies = [...geometries].map((g) => vi.spyOn(g, "dispose"));
    const sources = [...geometries].map((g) => g.getAttribute("position").array);
    for (let i = 0; i < 20; i++) {
      surfaces.primary.pose(run.frames!.rows[i * 10]!.before);
      surfaces.ghost.pose(run.frames!.rows[i * 10]!.after);
      surfaces.primary.palette(i % 2 ? "black" : "paper", false);
    }
    expect([...geometries].every((g, i) => g.getAttribute("position").array === sources[i])).toBe(true);
    expect(spies.every((spy) => spy.mock.calls.length === 0)).toBe(true);
    surfaces.ghost.root.traverse((o) => { if (o instanceof Mesh) expect(geometries.has(o.geometry)).toBe(true); });
    surfaces.dispose();
    expect(spies.every((spy) => spy.mock.calls.length === 1)).toBe(true);
  });
});
