import { quatRotate, type Vec3 } from "../model/pose";

// A cutaway view of the retained room. A wall is hidden when the camera is
// outside its interior half-space, so zooming/orbiting cannot turn it into an
// opaque screen between the viewer and the task. This changes visibility only.
export function wallVisible(camera: Vec3, target: Vec3, position: Vec3, quaternion: [number, number, number, number], halfThickness: number): boolean {
  const [w, x, y, z] = quaternion;
  const inverse: [number, number, number, number] = [w, -x, -y, -z];
  const c = quatRotate(inverse, [camera[0] - position[0], camera[1] - position[1], camera[2] - position[2]]);
  const t = quatRotate(inverse, [target[0] - position[0], target[1] - position[1], target[2] - position[2]]);
  return Math.abs(c[2]) > halfThickness + 0.03 && c[2] * t[2] > 0;
}
