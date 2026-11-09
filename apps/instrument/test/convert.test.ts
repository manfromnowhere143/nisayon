// @vitest-environment node
import { describe, expect, it } from "vitest";
import { Quaternion, Vector3 } from "three";
import { MUJOCO_TO_THREE, bodyPosition, bodyQuaternion, quaternionFromWxyz, toThreeVector } from "../src/scene/convert";

describe("MuJoCo to three.js conversion", () => {
  it("maps z-up to y-up with the root rotation and with the vector helper identically", () => {
    for (const [v, expected] of [
      [[0, 0, 1], [0, 1, 0]],
      [[0, 1, 0], [0, 0, -1]],
      [[1, 0, 0], [1, 0, 0]],
    ] as const) {
      const rotated = new Vector3(v[0], v[1], v[2]).applyQuaternion(MUJOCO_TO_THREE);
      expect(rotated.x).toBeCloseTo(expected[0], 12);
      expect(rotated.y).toBeCloseTo(expected[1], 12);
      expect(rotated.z).toBeCloseTo(expected[2], 12);
      const helper = toThreeVector(v[0], v[1], v[2]);
      expect(helper.distanceTo(rotated)).toBeLessThan(1e-12);
    }
  });

  it("keeps a right-handed frame", () => {
    const x = toThreeVector(1, 0, 0);
    const y = toThreeVector(0, 1, 0);
    const z = toThreeVector(0, 0, 1);
    expect(new Vector3().crossVectors(x, y).distanceTo(z)).toBeLessThan(1e-12);
  });

  it("reorders wxyz to three's xyzw", () => {
    const q = quaternionFromWxyz(0.5, 0.1, 0.2, 0.3);
    expect([q.x, q.y, q.z, q.w]).toEqual([0.1, 0.2, 0.3, 0.5]);
  });

  it("applies a body quaternion so that a 90° yaw about MuJoCo z turns x into y", () => {
    const s = Math.SQRT1_2;
    const xquat = Float64Array.from([s, 0, 0, s]); // wxyz: 90° about z
    const q = bodyQuaternion(xquat, 0);
    const v = new Vector3(1, 0, 0).applyQuaternion(q);
    expect(v.x).toBeCloseTo(0, 12);
    expect(v.y).toBeCloseTo(1, 12);
    // Inside the rotated root, MuJoCo +y becomes three −z.
    const world = v.clone().applyQuaternion(MUJOCO_TO_THREE);
    expect(world.z).toBeCloseTo(-1, 12);
  });

  it("reads body positions by index", () => {
    const xpos = Float64Array.from([0, 0, 0, 1, 2, 3]);
    expect(bodyPosition(xpos, 1).toArray()).toEqual([1, 2, 3]);
    expect(new Quaternion().equals(bodyQuaternion(Float64Array.from([1, 0, 0, 0]), 0))).toBe(true);
  });
});
