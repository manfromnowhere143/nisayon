// @vitest-environment node
import { beforeAll, expect, it, vi } from "vitest";
import * as THREE from "three";
import { sha256Hex } from "../src/data/digest";
import { ResourceCache, openCase, openGeneration, openRun, type LoadedRun } from "../src/data/loader";
import { acquisitionGroups, axisEnds, bodyPose, configurationPath, observationPair, pathCount } from "../src/model/spatial";
import { createEvidenceLayer } from "../src/scene/evidenceLayer";
import { pickBody } from "../src/scene/picking";
import { decodeSamplesV1 } from "../src/model/decodeV1";
import { fetchFromDisk } from "./fixture";

const options = { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 16 * 1024 * 1024 };
async function load(id: string) {
  const cache = new ResourceCache();
  const { generation } = await openGeneration(`http://fixture.test/fixtures/ui/recorded/${id}/evidence.json`, undefined, options);
  const record = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = await openRun(generation, record, record.runs.find((r) => r.role === "regression")!.run, undefined, options, cache);
  return { generation, record, run, cache };
}
let d03: Awaited<ReturnType<typeof load>>;
beforeAll(async () => { d03 = await load("D03-observation-backlog"); });

it("retains the D03 step 27 acquisition consumed at step 30 and its 17.529 mm displacement", () => {
  const row = d03.run.samples.rows[30]!;
  const pair = observationPair(row, "eef");
  expect(row.observation_step).toBe(27);
  expect(row.consumed_acquisition?.oldest_sim_time_s).toBe(1.350000000000001);
  expect(row.latest_acquisition?.oldest_sim_time_s).toBe(1.500000000000001);
  expect(row.observation_age_s).toBe(0.15000000000000013);
  expect(pair.distance! * 1000).toBeCloseTo(17.52902764980821, 12);
  expect(pair.consumed!.position).toEqual([0.04622568585038902, 0.0007788527880133679, 0.8747216010331182]);
  expect(pair.acquired!.position).toEqual([0.05143933865905849, 0.0034656146546436337, 0.8582029465658072]);
  expect(acquisitionGroups(row.consumed_acquisition)).toMatchObject([{ time: 1.350000000000001, names: expect.arrayContaining(["robot0_eef_pos", "cube_pos"]) }]);
  expect(acquisitionGroups(row.consumed_acquisition)[0]!.names).toHaveLength(6);
  expect(observationPair(row, "cube").distance).toBeLessThan(0.00001);
});

it("agrees with each zero-age frame's own exported coordinate residual, without a new tolerance", async () => {
  const d01 = await load("D01-gripper-sign");
  let checked = 0;
  for (const data of [d01, d03]) for (const record of data.record.runs.filter((r) => data === d01 || r.role === "reference")) {
    const run = await openRun(data.generation, data.record, record.run, undefined, options, data.cache);
    for (const row of run.samples.rows) {
      if (row.observation_age_s !== 0) continue;
      const frame = run.frames!.rows[row.row_index]!.before;
      const consumed = observationPair(row, "eef").consumed!;
      const difference = Math.max(...consumed.position.map((value, axis) => Math.abs(value - frame.grip_site_xpos[axis]!)));
      expect(difference).toBe(frame.residual_eef_m);
      checked++;
    }
  }
  expect(checked).toBeGreaterThan(800);
});

it("converts observation xyzw once and never normalizes or invents an unavailable pose", () => {
  const row = d03.run.samples.rows[30]!;
  const pair = observationPair(row, "eef");
  const raw = row.observation!.robot0_eef_quat;
  expect(pair.consumed!.quaternion).toEqual([raw[3], raw[0], raw[1], raw[2]]);
  expect(axisEnds({ position: [1, 2, 3], quaternion: [Math.SQRT1_2, 0, 0, Math.SQRT1_2] })[0]![1]).toBeCloseTo(2.07, 14);
  expect(observationPair({ ...row, captured_observation: null }, "eef")).toMatchObject({ acquired: null, distance: null });
  expect(observationPair({ ...row, observation: { ...row.observation!, robot0_eef_quat: [0, 0, 0, 0] } }, "eef")).toMatchObject({ consumed: null, distance: null });
});

it("bounds past-only configuration paths and updates buffers in place across every retained row", () => {
  const run = d03.run, model = run.model!, frames = run.frames!;
  const body = model.bodies.find((b) => b.name === "gripper0_eef")!.index;
  const path = configurationPath(frames, body);
  expect(pathCount(30, "before", path)).toBe(61);
  expect(pathCount(30, "after", path)).toBe(62);
  expect(pathCount(900, "after", path)).toBe(frames.rows.length * 2);
  const layer = createEvidenceLayer();
  const update = (i: number) => layer.update(model, run.samples.rows[i]!, bodyPose(frames.rows[i]!.before, body), path, pathCount(i, "before", path), { observations: true, axes: true, path: true }, true, i % 2 === 0);
  update(0);
  const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>();
  layer.root.traverse((object) => {
    if (object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points) {
      geometries.add(object.geometry);
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
    }
  });
  const buffers = [...geometries].map((geometry) => Object.entries(geometry.attributes));
  const disposals = [...geometries, ...materials].map((value) => vi.spyOn(value, "dispose"));
  for (let i = 1; i < frames.rows.length; i++) update(i);
  [...geometries].forEach((geometry, i) => { for (const [name, attribute] of buffers[i]!) expect(geometry.getAttribute(name)).toBe(attribute); });
  expect(disposals.every((spy) => spy.mock.calls.length === 0)).toBe(true);
  layer.dispose();
  expect(disposals.every((spy) => spy.mock.calls.length === 1)).toBe(true);
});

it("picks a visible primary body, respects opaque occlusion and ignores hidden ancestors", () => {
  const root = new THREE.Group(), hidden = new THREE.Group();
  const material = new THREE.MeshBasicMaterial(), geometry = new THREE.SphereGeometry(0.5);
  const body = new THREE.Mesh(geometry, material); body.userData.body = 12; root.add(body);
  const occluder = new THREE.Mesh(geometry, material); occluder.userData.body = 0; occluder.position.z = 2; hidden.add(occluder); root.add(hidden);
  const ray = new THREE.Raycaster(new THREE.Vector3(0, 0, 4), new THREE.Vector3(0, 0, -1));
  root.updateMatrixWorld(true);
  expect(pickBody(ray, [root])).toBeNull();
  hidden.visible = false;
  expect(pickBody(ray, [root])).toBe(12);
  root.visible = false;
  expect(pickBody(ray, [root])).toBeNull();
  geometry.dispose(); material.dispose();
});

it("rejects malformed acquisition fields and preserves absence in historical objects", async () => {
  const run: LoadedRun = d03.run;
  const response = await options.fetch(new URL(run.record.samples.path, d03.generation.baseUrl).href);
  const raw = await response.json();
  const expectation = { run: run.record.run, rowCount: run.record.row_count, actionDimension: 7, record: run.record };
  const original = raw.rows[30].original;
  original.captured_observation_capture.step = 999;
  expect(() => decodeSamplesV1(raw, expectation)).toThrow(/acquisition step differs/);
  original.captured_observation_capture.step = original.captured_observation_step;
  original.observation_capture.components.robot0_eef_pos.simulation_s = "1.35";
  expect(() => decodeSamplesV1(raw, expectation)).toThrow(/finite number/);
  delete original.observation_capture;
  delete original.captured_observation_capture;
  delete raw.rows[30].observations.captured_observation;
  const decoded = decodeSamplesV1(raw, expectation).rows[30]!;
  expect(decoded.consumed_acquisition).toBeNull();
  expect(decoded.latest_acquisition).toBeNull();
  expect(observationPair(decoded, "eef").acquired).toBeNull();
});
