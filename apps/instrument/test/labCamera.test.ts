import { expect, it } from "vitest";
import { Box3, Vector3 } from "three";
import { confineLabCamera } from "../src/scene/labCamera";

it("keeps the camera inside the vaulted aisle and in front of the console throughout an orbit and zoom sweep", () => {
  const target = new Vector3(0, 1, 0), console = new Box3(new Vector3(3.1, -.1, -.2), new Vector3(5.3, 2.02, 2.2));
  for (const radius of [2, 5, 12, 30]) for (let yaw = 0; yaw < 360; yaw += 10) for (const pitch of [5, 25, 55, 85]) {
    const a = yaw * Math.PI / 180, p = pitch * Math.PI / 180;
    const direction = new Vector3(Math.cos(a) * Math.cos(p), Math.sin(p), Math.sin(a) * Math.cos(p));
    const eye = target.clone().addScaledVector(direction, radius);
    confineLabCamera(eye, target);
    expect(Math.abs(eye.x)).toBeLessThanOrEqual(4.700001);
    expect(Math.abs(eye.z)).toBeLessThanOrEqual(9.200001);
    expect(eye.y).toBeGreaterThanOrEqual(.3);
    expect((eye.x / 5) ** 2 + (Math.max(0, eye.y - 2.2) / 3.85) ** 2).toBeLessThanOrEqual(1.000001);
    expect(console.containsPoint(eye)).toBe(false);
    expect(eye.clone().sub(target).cross(direction).length()).toBeLessThan(1e-10);
  }
  expect(target.toArray()).toEqual([0, 1, 0]);
});
