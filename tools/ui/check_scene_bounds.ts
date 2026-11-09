// Geometric framing check against every retained configuration, without a GPU.
// Declared scene sizes come from CSS arithmetic; browser layout remains unverified.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { decodeModelV1, decodeReconstructionV1 } from "../../apps/instrument/src/model/decodeV1";
import { CAMERA_FOV, SCENE_VIEWS, VIEW_POSITIONS, VIEW_TARGET } from "../../apps/instrument/src/scene/renderer";
import { corners, fitCamera, trajectoryBounds } from "../../apps/instrument/src/scene/framing";
import { VISUAL_ASSET } from "../../apps/instrument/src/scene/visualAssetPin";
import { decodeVisualAsset } from "../../apps/instrument/src/scene/visualCodec";
import { toThreeVector } from "../../apps/instrument/src/scene/convert";
import { projectPoint } from "../../apps/instrument/src/scene/project";
import { PerspectiveCamera, Vector3, Quaternion } from "../../apps/instrument/node_modules/three/build/three.module.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const json = (path: string) => JSON.parse(readFileSync(path, "utf8"));
const library = json(resolve(root, "fixtures/ui/recorded/library.json"));
const visualBytes = readFileSync(resolve(root, "." + VISUAL_ASSET.path));
assert.equal(hash(visualBytes), VISUAL_ASSET.sha256);
const visual = decodeVisualAsset(JSON.parse(visualBytes.toString("utf8")), VISUAL_ASSET.sha256);
const visualMeshes = new Map(visual.meshes.map((m) => [m.name, m]));
const sizes = [
  { id: "phone-390x844", viewport: [390, 844], width: 358, height: 358 * 0.92 },
  { id: "short-phone-390x660", viewport: [390, 660], width: 358, height: 358 * 0.92 },
  { id: "phone-320x660", viewport: [320, 660], width: 288, height: 288 * 0.92 },
  { id: "desktop-1440x900", viewport: [1440, 900], width: (1440 - 56 - 32) * 1.35 / 2.35, height: 900 - 126 - 90 },
  { id: "inspector-1440x900", viewport: [1440, 900], width: (1440 - 56 - 64 - 380) * 1.15 / 2.1, height: 900 - 126 - 90 },
];
const scenarios = sizes.flatMap((size) => SCENE_VIEWS.flatMap((view) => (["workspace", "lab", "grasp"] as const).map((focus) => {
  const camera = new PerspectiveCamera(CAMERA_FOV, size.width / size.height, 0.05, 30);
  camera.position.copy(VIEW_POSITIONS[view]);
  camera.lookAt(VIEW_TARGET);
  camera.updateMatrixWorld();
  camera.updateProjectionMatrix();
  return { ...size, view, focus, camera, frames: 0, clipped_frames: 0, maximum_abs_x: 0, maximum_abs_y: 0,
    subject_clipped_frames: 0, subject_maximum_abs_x: 0, subject_maximum_abs_y: 0,
    first_clip: null as any, first_subject_clip: null as any,
    minimum_cube_width_px: Infinity, minimum_cube_height_px: Infinity };
})));
const report: Record<string, any> = {
  schema: "nisayon.ui-scene-bounds.v1",
  interface_base_commit: "92389b3880935cab879e892d3d7a0795400679f4",
  state: "working tree identified by source hashes below",
  source_hashes: Object.fromEntries([
    "apps/instrument/src/scene/renderer.ts", "apps/instrument/src/styles/app.css",
    "apps/instrument/src/scene/framing.ts", "apps/instrument/src/scene/visualAssetPin.ts", "apps/instrument/src/scene/nativeSurface.ts", "apps/instrument/src/styles/tokens.css", "apps/instrument/src/scene/project.ts", "tools/ui/check_scene_bounds.ts",
  ].map((path) => [path, hash(readFileSync(resolve(root, path)))])),
  node: process.version,
  scope: "Every recorded frame: enclosing corners of each native visual mesh transformed by its compiled local pose and retained body pose, drawn non-robot box/cylinder vertices and gripper site. No browser layout, rasterization, material, occlusion, antialiasing or interaction check.",
  scene_size_assumptions: "CSS pixel arithmetic at 100% text and zero desktop safe-area inset. Phone width minus 32; desktop width minus 56; inspector third track 380. Actual browser bounds still need measurement.",
  limits: ["Native mesh bounds enclose every source vertex. Shadow rasterization and comparison occlusion remain unverified.", "Bounding boxes are not collision envelopes or contact evidence.", "Same geometry in both grounds; no color/contrast acceptance follows."],
  cases: [],
};
report.view_basis = SCENE_VIEWS.map((view) => {
  const camera = scenarios.find((s) => s.view === view)!.camera;
  const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const webglRight = new Vector3(right.x, -right.z, right.y).normalize();
  const svgRight = new Vector3(projectPoint(1, 0, 0, view).x,
    projectPoint(0, 1, 0, view).x, projectPoint(0, 0, 1, view).x).normalize();
  return { view, webgl_screen_right_in_source_axes: webglRight.toArray(),
    svg_screen_right_in_source_axes: svgRight.toArray(),
    horizontal_axis_difference_degrees: Math.acos(Math.max(-1, Math.min(1, webglRight.dot(svgRight)))) * 180 / Math.PI };
});
const started = performance.now();
const temp = new Vector3();
const q = new Quaternion();
let frameCount = 0;
for (const entry of library.cases) {
  const folder = resolve(root, "fixtures/ui/recorded", entry.directory);
  const read = (ref: any) => {
    const bytes = readFileSync(resolve(folder, ref.path));
    assert.equal(bytes.byteLength, ref.byte_length);
    assert.equal(hash(bytes), ref.sha256);
    return JSON.parse(bytes.toString("utf8"));
  };
  const manifest = read(entry.manifest);
  const caseRecord = read(manifest.cases[0].object);
  let checked = 0;
  for (const run of caseRecord.runs) {
    const model = decodeModelV1(read(run.model));
    const frames = read(run.reconstruction);
    const decodedFrames = decodeReconstructionV1(frames, { run: run.key, rowCount: run.sample_count }, model);
    assert.equal(visual.modelBindings[model.meshes.source_id as string], run.model.sha256);
    const bounds = Object.fromEntries((["workspace", "lab", "grasp"] as const).map((focus) => [focus, trajectoryBounds(model, [decodedFrames], focus, visual)]));
    for (const scenario of scenarios) {
      const fit = fitCamera(scenario.view, scenario.width / scenario.height, bounds[scenario.focus]);
      scenario.camera.position.copy(toThreeVector(...fit.position));
      scenario.camera.lookAt(toThreeVector(...fit.target));
      scenario.camera.updateMatrixWorld();
    }
    const gripperSite = model.sites.find((s) => s.name === "gripper0_grip_site")!;
    for (const frame of frames.frames) {
      const points: { label: string; xyz: number[]; cube: boolean }[] = [];
      for (const part of visual.parts) {
        const body = frame.bodies[part.body];
        const local = new Quaternion(part.quaternion_wxyz[1], part.quaternion_wxyz[2], part.quaternion_wxyz[3], part.quaternion_wxyz[0]);
        const world = new Quaternion(body[4], body[5], body[6], body[3]);
        for (const corner of corners(visualMeshes.get(part.mesh)!.bounds)) {
          temp.fromArray(corner).applyQuaternion(local).add(new Vector3(...part.position)).applyQuaternion(world);
          points.push({ label: part.name, xyz: [temp.x + body[0], temp.y + body[1], temp.z + body[2]], cube: false });
        }
      }
      points.push({ label: gripperSite.name, xyz: frame.sites[gripperSite.index].slice(0, 3), cube: false });
      for (const index of model.schematic.drawable_geoms) {
        const geom = model.geoms[index]!;
        if (/^(robot0_|gripper0_)/.test(model.bodies[geom.body]!.name)) continue;
        const pose = frame.geoms[index];
        q.set(pose[4], pose[5], pose[6], pose[3]);
        const local: number[][] = [];
        if (geom.type === "box") {
          for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
            local.push([x * geom.size[0], y * geom.size[1], z * geom.size[2]]);
          }
        } else if (geom.type === "cylinder") {
          for (const sign of [-1, 1]) for (let i = 0; i < 20; i += 1) {
            const angle = i * Math.PI * 2 / 20;
            local.push([Math.sin(angle) * geom.size[0], -Math.cos(angle) * geom.size[0], sign * geom.size[1]]);
          }
        }
        for (const vertex of local) {
          temp.fromArray(vertex).applyQuaternion(q);
          points.push({ label: geom.name, xyz: [temp.x + pose[0], temp.y + pose[1], temp.z + pose[2]],
            cube: model.bodies[geom.body]!.name.startsWith("cube") });
        }
      }
      const locator = { generation_sha256: entry.manifest.sha256, case_key: entry.case_key,
        run: run.key, row_index: frame.row_index, phase: frame.phase, clock: "simulation" };
      for (const scenario of scenarios) {
        let clipped = false;
        let subjectClipped = false;
        const cube = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
        for (const point of points) {
          // The selected task's subject: arm/gripper, cube and table top. Mount
          // cabinets and table supports may intentionally extend beyond a crop.
          const subject = scenario.focus === "lab" ? !/^(floor|wall_)/.test(point.label) : scenario.focus === "grasp" ? /^(gripper0_|cube)/.test(point.label) : /^(robot0_|gripper0_|cube)/.test(point.label) || point.label === "table_visual";
          const p = toThreeVector(point.xyz[0]!, point.xyz[1]!, point.xyz[2]!).project(scenario.camera);
          scenario.maximum_abs_x = Math.max(scenario.maximum_abs_x, Math.abs(p.x));
          scenario.maximum_abs_y = Math.max(scenario.maximum_abs_y, Math.abs(p.y));
          if (subject) {
            scenario.subject_maximum_abs_x = Math.max(scenario.subject_maximum_abs_x, Math.abs(p.x));
            scenario.subject_maximum_abs_y = Math.max(scenario.subject_maximum_abs_y, Math.abs(p.y));
          }
          if (Math.abs(p.x) > 1 || Math.abs(p.y) > 1 || Math.abs(p.z) > 1) {
            clipped = true;
            scenario.first_clip ??= { locator, point: point.label, world_xyz: point.xyz, ndc_xyz: p.toArray() };
            if (subject) {
              subjectClipped = true;
              scenario.first_subject_clip ??= { locator, point: point.label, world_xyz: point.xyz, ndc_xyz: p.toArray() };
            }
          }
          if (point.cube) {
            cube.minX = Math.min(cube.minX, p.x); cube.maxX = Math.max(cube.maxX, p.x);
            cube.minY = Math.min(cube.minY, p.y); cube.maxY = Math.max(cube.maxY, p.y);
          }
        }
        scenario.minimum_cube_width_px = Math.min(scenario.minimum_cube_width_px, (cube.maxX - cube.minX) * scenario.width / 2);
        scenario.minimum_cube_height_px = Math.min(scenario.minimum_cube_height_px, (cube.maxY - cube.minY) * scenario.height / 2);
        scenario.frames += 1;
        if (clipped) scenario.clipped_frames += 1;
        if (subjectClipped) scenario.subject_clipped_frames += 1;
      }
      checked += 1;
    }
  }
  report.cases.push({ case_id: entry.case_id, frames: checked, generation_sha256: entry.manifest.sha256 });
  frameCount += checked;
  console.log(JSON.stringify({ case_id: entry.case_id, frames: checked }));
}
report.frames = frameCount;
report.scenarios = scenarios.map(({ camera, ...scenario }) => scenario);
report.command_wall_seconds = (performance.now() - started) / 1000;
writeFileSync(resolve(root, process.argv[2] ?? "docs/ui/qualification/scene-bounds-native-lab.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify({ frames: frameCount, view_basis: report.view_basis,
  scenarios: report.scenarios.map(({ id, view, subject_clipped_frames, subject_maximum_abs_x, subject_maximum_abs_y }: any) => ({ id, view, subject_clipped_frames, subject_maximum_abs_x, subject_maximum_abs_y })), command_wall_seconds: report.command_wall_seconds }, null, 2));
