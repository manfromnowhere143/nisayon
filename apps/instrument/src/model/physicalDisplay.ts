import type { FramePhase, ModelRecord, Observation, SampleRow } from "./types";
import { observationPose, bodyPose, type SpatialPose } from "./spatial";
import { poseAt, quatMultiply, quatRotate, type Quat, type Vec3 } from "./pose";

export function controllerFrame(frame: FramePhase | null): { position: Vec3; ends: Vec3[]; grip: Vec3 } | null {
  const p = frame?.physical?.goal_pos, m = frame?.physical?.goal_ori;
  if (!frame || !p) return null;
  let ends: Vec3[] = [];
  if (m) {
    const orthogonal = m.every((r, i) => m.every((s, j) => Math.abs(r.reduce((n, v, k) => n + v * s[k]!, 0) - (i === j ? 1 : 0)) < 1e-6));
    const determinant = m[0]![0]! * (m[1]![1]! * m[2]![2]! - m[1]![2]! * m[2]![1]!) - m[0]![1]! * (m[1]![0]! * m[2]![2]! - m[1]![2]! * m[2]![0]!) + m[0]![2]! * (m[1]![0]! * m[2]![1]! - m[1]![1]! * m[2]![0]!);
    if (orthogonal && Math.abs(determinant - 1) < 1e-6) ends = [0, 1, 2].map(axis => p.map((v, i) => v + .045 * m[i]![axis]!) as Vec3);
  }
  return { position: p, ends, grip: frame.grip_site_xpos };
}

const inverse = ([w, x, y, z]: Quat): Quat => [w, -x, -y, -z];
export interface FingerPad { name: string; pose: SpatialPose; half: Vec3 }

// The recorded observation supplies two slide coordinates and an end-effector
// pose, never an arm configuration. Derive only the two native finger pads by
// rigid composition and the declared slide axes. No inverse kinematics.
export function observedFingerPads(model: ModelRecord, before: FramePhase | null, row: SampleRow | null, observation: Observation | null): FingerPad[] {
  const acquired = observationPose(row?.captured_observation ?? null, "eef"), observed = observationPose(observation, "eef");
  if (!before?.physical || !acquired || !observed || observation?.robot0_gripper_qpos.length !== 2) return [];
  const result: FingerPad[] = [];
  for (const finger of [1, 2]) {
    const joint = model.joints?.find(j => j.name === `gripper0_finger_joint${finger}` && j.type === "slide");
    const pad = model.geoms.find(g => g.name === `gripper0_finger${finger}_pad_collision` && g.type === "box");
    if (!joint || !pad) return [];
    // The pad must belong to that finger's fixed subtree.
    let owner = pad.body;
    while (owner !== joint.body && owner > 0) owner = model.bodies[owner]!.parent;
    if (owner !== joint.body) return [];
    const body = bodyPose(before, joint.body), geom = poseAt(before.geoms, pad.index);
    const q = before.physical.qpos[joint.qposAddress];
    if (!body || q === undefined) return [];
    const axis = quatRotate(body.quaternion, joint.axis);
    const delta = observation.robot0_gripper_qpos[finger - 1]! - q;
    const relative = quatRotate(inverse(acquired.quaternion), geom.pos.map((v, i) => v + delta * axis[i]! - acquired.position[i]!) as Vec3);
    const rotated = quatRotate(observed.quaternion, relative);
    result.push({ name: pad.name, half: pad.size, pose: { position: observed.position.map((v, i) => v + rotated[i]!) as Vec3, quaternion: quatMultiply(observed.quaternion, quatMultiply(inverse(acquired.quaternion), geom.quat)) } });
  }
  return result;
}
