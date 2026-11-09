// Spatial readings stay in the recorded MuJoCo world: metres, z up. Observation
// quaternions arrive as xyzw; reconstructed poses use wxyz. No IK or smoothing.
import type { Acquisition, FramePhase, Frames, ModelRecord, Observation, Phase, SampleRow } from "./types";
import { quatRotate, type Quat, type Vec3 } from "./pose";

export type ObservationTarget = "eef" | "cube";
export interface SpatialOptions { observations: boolean; path: boolean; axes: boolean; goal?: boolean; collision?: boolean }
export interface SpatialPose { position: Vec3; quaternion: Quat }
export interface ObservationPair {
  consumed: SpatialPose | null;
  acquired: SpatialPose | null;
  distance: number | null;
}
export const AXIS_LENGTH = 0.07;
export const OBSERVATION_AXIS_LENGTH = AXIS_LENGTH * 0.65;

export function bodyLabel(name: string): string {
  const names: Record<string, string> = {
    world: "World", table: "Table", robot0_base: "Robot base", robot0_link0: "Base housing",
    robot0_right_hand: "Wrist flange", gripper0_right_gripper: "Gripper", gripper0_eef: "End effector",
    gripper0_leftfinger: "Left finger", gripper0_rightfinger: "Right finger",
    gripper0_finger_joint1_tip: "Left fingertip", gripper0_finger_joint2_tip: "Right fingertip", cube_main: "Cube",
  };
  const link = /^robot0_link(\d+)$/.exec(name);
  return names[name] ?? (link ? `Arm link ${link[1]}` : name.replace(/^mount0_/, "Mount · ").replaceAll("_", " "));
}

export function bodyPose(frame: FramePhase | null, body: number | null): SpatialPose | null {
  if (!frame || body === null || body < 0 || (body + 1) * 3 > frame.xpos.length) return null;
  return { position: Array.from(frame.xpos.slice(body * 3, body * 3 + 3)) as Vec3, quaternion: Array.from(frame.xquat.slice(body * 4, body * 4 + 4)) as Quat };
}

export function observationPose(observation: Observation | null, target: ObservationTarget): SpatialPose | null {
  if (!observation) return null;
  const pos = target === "eef" ? observation.robot0_eef_pos : observation.cube_pos;
  const q = target === "eef" ? observation.robot0_eef_quat : observation.cube_quat;
  // A malformed orientation must not produce a plausible-looking rotated frame.
  if (Math.abs(Math.hypot(...q) - 1) > 1e-4) return null;
  return { position: [...pos] as Vec3, quaternion: [q[3]!, q[0]!, q[1]!, q[2]!] };
}

export function observationPair(row: SampleRow | null, target: ObservationTarget): ObservationPair {
  const consumed = observationPose(row?.observation ?? null, target);
  const acquired = observationPose(row?.captured_observation ?? null, target);
  return { consumed, acquired, distance: consumed && acquired ? Math.hypot(...consumed.position.map((v, i) => v - acquired.position[i]!)) : null };
}

export function axisEnds(pose: SpatialPose, length = AXIS_LENGTH): Vec3[] {
  return ([[length, 0, 0], [0, length, 0], [0, 0, length]] as Vec3[]).map((axis) => {
    const v = quatRotate(pose.quaternion, axis);
    return v.map((n, i) => n + pose.position[i]!) as Vec3;
  });
}

// One reusable display buffer per recording and selected body. Vertices are
// retained samples; the line only connects them, and drawRange hides the future.
export function configurationPath(frames: Frames | null, body: number | null): Float32Array {
  if (!frames || body === null) return new Float32Array();
  const positions = new Float32Array(frames.rows.length * 2 * 3);
  for (const row of frames.rows) for (const [side, frame] of [row.before, row.after].entries()) {
    positions.set(frame.xpos.subarray(body * 3, body * 3 + 3), (row.row_index * 2 + side) * 3);
  }
  return positions;
}

export function pathCount(row: number, phase: Phase, path: Float32Array): number {
  return Math.max(0, Math.min(path.length / 3, row * 2 + (phase === "after" ? 2 : 1)));
}

export function pathStart(frames: Frames | null, row: number, phase: Phase, seconds: number | null): number {
  if (!frames || seconds === null) return 0;
  const now = frames.rows[row]?.[phase].sim_time_s;
  if (now === undefined) return 0;
  for (const candidate of frames.rows) {
    if (candidate.before.sim_time_s >= now - seconds) return candidate.row_index * 2;
    if (candidate.after.sim_time_s >= now - seconds) return candidate.row_index * 2 + 1;
  }
  return 0;
}

export function acquisitionGroups(capture: Acquisition | null): { time: number; names: string[] }[] {
  const groups = new Map<number, string[]>();
  for (const component of capture?.components ?? []) {
    const names = groups.get(component.sim_time_s) ?? [];
    names.push(component.name);
    groups.set(component.sim_time_s, names);
  }
  return Array.from(groups, ([time, names]) => ({ time, names })).sort((a, b) => a.time - b.time);
}

export function cubeHalfSize(model: ModelRecord): Vec3 | null {
  const body = model.bodies.find((b) => b.name === "cube_main");
  return model.geoms.find((g) => g.body === body?.index && g.type === "box")?.size ?? null;
}

export function bodyDepth(model: ModelRecord, index: number): number {
  let depth = 0, body = model.bodies[index];
  while (body && body.index !== 0 && depth < model.bodies.length) { depth++; body = model.bodies[body.parent]; }
  return depth;
}
