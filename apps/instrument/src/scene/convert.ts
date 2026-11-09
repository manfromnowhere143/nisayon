// One conversion from the exporter's frame convention (right-handed, z-up,
// metres, wxyz quaternions) to three.js (right-handed, y-up, xyzw quaternions).
// The scene root carries the axis rotation; body poses are used in MuJoCo
// coordinates inside that root. Tests pin both halves.

import { Quaternion, Vector3 } from "three";

// Rotation of −90° about X: MuJoCo (x, y, z) → three (x, z, −y).
export const MUJOCO_TO_THREE = new Quaternion(-Math.SQRT1_2, 0, 0, Math.SQRT1_2);

export function toThreeVector(x: number, y: number, z: number): Vector3 {
  return new Vector3(x, z, -y);
}

// MuJoCo stores quaternions as (w, x, y, z); three.js constructs (x, y, z, w).
export function quaternionFromWxyz(w: number, x: number, y: number, z: number, target = new Quaternion()): Quaternion {
  return target.set(x, y, z, w);
}

export function bodyPosition(xpos: Float64Array, bodyIndex: number, target = new Vector3()): Vector3 {
  const o = bodyIndex * 3;
  return target.set(xpos[o] as number, xpos[o + 1] as number, xpos[o + 2] as number);
}

export function bodyQuaternion(xquat: Float64Array, bodyIndex: number, target = new Quaternion()): Quaternion {
  const o = bodyIndex * 4;
  return quaternionFromWxyz(xquat[o] as number, xquat[o + 1] as number, xquat[o + 2] as number, xquat[o + 3] as number, target);
}
