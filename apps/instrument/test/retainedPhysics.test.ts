// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";
import * as THREE from "three";
import { beforeAll, expect, it, vi } from "vitest";
import { ResourceCache, openCase, openGeneration, openRun } from "../src/data/loader";
import { sha256Hex } from "../src/data/digest";
import { decodeFrameBytes, frameBuffers } from "../src/data/frameDecode";
import { controllerFrame, observedFingerPads } from "../src/model/physicalDisplay";
import { poseAt } from "../src/model/pose";
import { nearestPhysicalSample, physicalSamples } from "../src/ui/PhysicalHistory";
import { decodeCollisionView } from "../src/scene/collisionAssets";
import { COLLISION_ASSET } from "../src/scene/collisionAssetPin";
import { createCollisionLayer } from "../src/scene/collisionLayer";
import { fetchFromDisk, REPO_ROOT } from "./fixture";
import type { FramePhase } from "../src/model/types";

const options = { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 16 * 1024 * 1024 };
async function load() {
  const cache = new ResourceCache(), { generation } = await openGeneration("http://fixture.test/fixtures/ui/recorded/D03-observation-backlog/evidence.json", undefined, options);
  const record = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = await openRun(generation, record, record.runs.find(r => r.role === "regression" && r.stage === "diagnostic")!.run, undefined, options, cache);
  return { generation, run };
}
let data: Awaited<ReturnType<typeof load>>;
beforeAll(async () => { data = await load(); });

it("draws the retained controller rotation columns and position, leaving invalid orientation absent", () => {
  const frame = data.run.frames!.rows[30]!.after, target = controllerFrame(frame)!;
  expect(target.position).toEqual(frame.physical!.goal_pos);
  expect(target.grip).toEqual(frame.grip_site_xpos);
  for (let axis = 0; axis < 3; axis++) expect(target.ends[axis]).toEqual(frame.physical!.goal_pos!.map((v, i) => v + .045 * frame.physical!.goal_ori![i]![axis]!));
  expect(controllerFrame({ ...frame, physical: { ...frame.physical!, goal_ori: [[0, 0, 0], [0, 0, 0], [0, 0, 0]] } })!.ends).toEqual([]);
  expect(controllerFrame({ ...frame, physical: { ...frame.physical!, goal_pos: null } })).toBeNull();
});

it("derives only two native finger pads, agrees with current acquisition, and preserves the lagged observation", () => {
  const { run } = data, row = run.samples.rows[30]!, before = run.frames!.rows[30]!.before;
  const pads = observedFingerPads(run.model!, before, row, row.captured_observation);
  expect(pads).toHaveLength(2);
  for (const pad of pads) {
    const geom = run.model!.geoms.find(g => g.name === pad.name)!;
    const native = poseAt(before.geoms, geom.index);
    expect(pad.half).toEqual(geom.size);
    // Numerical composition check, not a physical acceptance tolerance.
    pad.pose.position.forEach((v, i) => expect(v).toBeCloseTo(native.pos[i]!, 7));
  }
  const lagged = observedFingerPads(run.model!, before, row, row.observation);
  expect(lagged).toHaveLength(2);
  expect(Math.hypot(...lagged[0]!.pose.position.map((v, i) => v - pads[0]!.pose.position[i]!))).toBeGreaterThan(.01);
  expect(observedFingerPads(run.model!, before, { ...row, captured_observation: null }, row.observation)).toEqual([]);
});

it.each(["before", "after"] as const)("picks joint and actuator histories on their own %s frame clock", phase => {
  const { run } = data;
  for (const read of [(f: FramePhase) => f.physical?.qpos[3], (f: FramePhase) => f.physical?.ctrl[3]]) {
    const samples = physicalSamples(run.frames, phase, read);
    expect(samples[29]!.time).toBe(run.frames!.rows[29]![phase].sim_time_s);
    expect(nearestPhysicalSample(samples, samples[29]!.time)?.row).toBe(29);
    expect(nearestPhysicalSample(samples, -Infinity)?.row).toBe(0);
  }
});

it("transfers full precision reconstruction buffers without changing retained values or accepting duplicate JSON", async () => {
  const { run, generation } = data;
  const bytes = await options.fetch(new URL(run.record.frames!.path, generation.baseUrl).href).then(r => r.arrayBuffer());
  const request = { bytes, expectation: { run: run.record.run, rowCount: run.record.row_count, record: run.record }, model: run.model! };
  const decoded = decodeFrameBytes(request);
  const buffers = frameBuffers(decoded);
  const transferred = structuredClone(decoded, { transfer: buffers });
  expect(buffers.every(b => b.byteLength === 0)).toBe(true);
  expect(transferred).toEqual(run.frames);
  expect(() => decodeFrameBytes({ ...request, bytes: new TextEncoder().encode('{"schema":"x","schema":"y"}').buffer })).toThrow(/duplicate/i);
});

it("binds collision hulls, refuses altered model/assets, reuses buffers and releases them once", async () => {
  const { run, generation } = data, bytes = readFileSync(join(REPO_ROOT, COLLISION_ASSET.path));
  expect(bytes.byteLength).toBe(COLLISION_ASSET.byte_length);
  expect(await sha256Hex(new Uint8Array(bytes).buffer)).toBe(COLLISION_ASSET.sha256);
  const raw = JSON.parse(bytes.toString()), view = decodeCollisionView(raw, run.model!, run.record.model!.sha256, generation);
  expect(view.parts).toHaveLength(18);
  expect(view.meshes.size).toBe(10);
  expect(view.parts.some(p => p.name === "floor")).toBe(false);
  expect(() => decodeCollisionView(raw, run.model!, "0".repeat(64), generation)).toThrow(/not qualified/);
  expect(() => decodeCollisionView(raw, run.model!, run.record.model!.sha256, { ...generation, source_bindings: generation.source_bindings.filter(s => s.kind !== "asset") })).toThrow(/not bound/);
  const layer = createCollisionLayer(view), geometry = new Set<THREE.BufferGeometry>();
  layer.root.traverse(o => { if (o instanceof THREE.LineSegments) geometry.add(o.geometry); });
  const spies = [...geometry].map(g => vi.spyOn(g, "dispose"));
  for (const row of run.frames!.rows) { layer.pose(row.before, true); layer.pose(row.after, true); }
  expect(spies.every(s => s.mock.calls.length === 0)).toBe(true);
  layer.dispose(); expect(spies.every(s => s.mock.calls.length === 1)).toBe(true);
});
