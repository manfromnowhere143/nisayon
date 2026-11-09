// Camera framing from the complete retained trajectory, so a seek does not
// pump the lens. Source axes: metres, z up. Drawing radii are not collision data.
import type { Frames, ModelRecord } from "../model/types";
import { quatRotate, type Vec3 } from "../model/pose";
import type { VisualAsset } from "./visualCodec";

export type SceneView = "three-quarter" | "side" | "top";
export const SCENE_VIEWS: readonly SceneView[] = ["three-quarter", "side", "top"];
export const CAMERA_FOV = 30;
export const VIEW_ORIGIN: Vec3 = [-0.08, 0, 0.92];
export const VIEW_EYES: Record<SceneView, Vec3> = { "three-quarter": [1.6, -1.55, 1.55], side: [0, -2.35, 1.1], top: [-0.12, -0.45, 3.15] };
export interface SubjectBounds { min: Vec3; max: Vec3; fitPoints?: Vec3[] }
export const DEFAULT_BOUNDS: SubjectBounds = { min: [-0.63, -0.41, 0.76], max: [0.41, 0.41, 1.63] };
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a: Vec3): Vec3 => { const l = Math.hypot(...a); return [a[0] / l, a[1] / l, a[2] / l]; };

export function viewBasis(view: SceneView) {
  const eye = VIEW_EYES[view];
  const back = unit([eye[0] - VIEW_ORIGIN[0], eye[1] - VIEW_ORIGIN[1], eye[2] - VIEW_ORIGIN[2]]);
  const right = unit(cross([0, 0, 1], back));
  return { back, right, up: cross(back, right) };
}

export function corners(bounds: SubjectBounds): Vec3[] {
  const result: Vec3[] = [];
  for (const x of [bounds.min[0], bounds.max[0]]) for (const y of [bounds.min[1], bounds.max[1]]) for (const z of [bounds.min[2], bounds.max[2]]) result.push([x, y, z]);
  return result;
}

export function fitCamera(view: SceneView, aspect: number, bounds: SubjectBounds = DEFAULT_BOUNDS) {
  const basis = viewBasis(view);
  const points = bounds.fitPoints ?? corners(bounds);
  // Centre the actual projected subject. A world-aligned enclosing box has
  // empty corners far above the table; fitting those shrinks the robot.
  const low: Vec3 = [Infinity, Infinity, Infinity], high: Vec3 = [-Infinity, -Infinity, -Infinity];
  const axes = [basis.right, basis.up, basis.back];
  for (const p of points) for (let i = 0; i < 3; i++) {
    const value = dot(p, axes[i]!);
    low[i] = Math.min(low[i]!, value); high[i] = Math.max(high[i]!, value);
  }
  const target: Vec3 = [0, 0, 0];
  for (let axis = 0; axis < 3; axis++) for (let i = 0; i < 3; i++) target[i] = target[i]! + axes[axis]![i]! * (low[axis]! + high[axis]!) / 2;
  const tanV = Math.tan(CAMERA_FOV * Math.PI / 360) * 0.9;
  const tanH = tanV * Math.max(0.1, aspect);
  let distance = 0.2;
  for (const point of points) {
    const p: Vec3 = [point[0] - target[0], point[1] - target[1], point[2] - target[2]];
    const z = dot(p, basis.back);
    distance = Math.max(distance, z + Math.abs(dot(p, basis.right)) / tanH, z + Math.abs(dot(p, basis.up)) / tanV);
  }
  const position: Vec3 = [target[0] + basis.back[0] * distance, target[1] + basis.back[1] * distance, target[2] + basis.back[2] * distance];
  return { target, position, distance };
}

export function trajectoryBounds(model: ModelRecord, recordings: readonly Frames[], focus: "workspace" | "grasp" | "lab" = "workspace", visual: VisualAsset | null = null): SubjectBounds {
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  const fitPoints: Vec3[] = [];
  const include = (p: Vec3, radius = 0) => {
    for (let i = 0; i < 3; i++) { min[i] = Math.min(min[i]!, p[i]! - radius); max[i] = Math.max(max[i]!, p[i]! + radius); }
    if (radius) for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) fitPoints.push([p[0] + x * radius, p[1] + y * radius, p[2] + z * radius]);
    else fitPoints.push(p);
  };
  const nativeBounds = new Map<number, SubjectBounds>();
  if (visual) {
    const meshes = new Map(visual.meshes.map((m) => [m.name, m]));
    for (const part of visual.parts) {
      if (focus === "workspace" && model.bodies[part.body]?.name.startsWith("mount0_")) continue;
      if (focus === "grasp" && !model.bodies[part.body]?.name.startsWith("gripper0_")) continue;
      let box = nativeBounds.get(part.body);
      if (!box) { box = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] }; nativeBounds.set(part.body, box); }
      for (const corner of corners(meshes.get(part.mesh)!.bounds)) {
        const point = quatRotate(part.quaternion_wxyz, corner);
        for (let i = 0; i < 3; i++) { const v = point[i]! + part.position[i]!; box.min[i] = Math.min(box.min[i]!, v); box.max[i] = Math.max(box.max[i]!, v); }
      }
    }
  }
  const indices = new Map(model.bodies.map((b) => [b.name, b.index]));
  const bodies = new Map<number, number>();
  for (const [a, b, r] of model.schematic.links) for (const name of [a, b]) {
    if (focus === "grasp" && !name.startsWith("gripper0_")) continue;
    const index = indices.get(name); if (index !== undefined) bodies.set(index, Math.max(r, bodies.get(index) ?? 0.03));
  }
  const primitives = model.geoms.filter((g) => model.schematic.drawable_geoms.includes(g.index) && (focus === "lab" || (focus === "grasp" ? /^(gripper0_|cube)/.test(model.bodies[g.body]?.name ?? "") : /^(robot0_|gripper0_|cube)/.test(model.bodies[g.body]?.name ?? "") || g.name === "table_visual")));
  for (const frames of recordings) for (const row of frames.rows) for (const f of [row.before, row.after]) {
    if (!visual) for (const [i, r] of bodies) include([f.xpos[i * 3]!, f.xpos[i * 3 + 1]!, f.xpos[i * 3 + 2]!], r);
    for (const [i, box] of nativeBounds) {
      const q = i * 4;
      for (const corner of corners(box)) {
        const point = quatRotate([f.xquat[q]!, f.xquat[q + 1]!, f.xquat[q + 2]!, f.xquat[q + 3]!], corner);
        include([point[0] + f.xpos[i * 3]!, point[1] + f.xpos[i * 3 + 1]!, point[2] + f.xpos[i * 3 + 2]!]);
      }
    }
    include(f.grip_site_xpos, 0.0075);
    for (const g of primitives) {
      if (visual && /^(robot0_|gripper0_|mount0_)/.test(model.bodies[g.body]?.name ?? "")) continue;
      const o = g.index * 7;
      const p: Vec3 = [f.geoms[o]!, f.geoms[o + 1]!, f.geoms[o + 2]!];
      const q: [number, number, number, number] = [f.geoms[o + 3]!, f.geoms[o + 4]!, f.geoms[o + 5]!, f.geoms[o + 6]!];
      if (g.type === "box") {
        for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
          const v = quatRotate(q, [x * g.size[0], y * g.size[1], z * g.size[2]]);
          include([p[0] + v[0], p[1] + v[1], p[2] + v[2]]);
        }
      } else if (g.type === "cylinder") {
        const axis = quatRotate(q, [0, 0, 1]);
        const e = axis.map((v) => Math.abs(v) * g.size[1] + g.size[0] * Math.sqrt(Math.max(0, 1 - v * v))) as Vec3;
        for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) include([p[0] + x * e[0], p[1] + y * e[1], p[2] + z * e[2]]);
      }
    }
  }
  return min.every(Number.isFinite) && max.every(Number.isFinite) ? { min, max, fitPoints } : DEFAULT_BOUNDS;
}
