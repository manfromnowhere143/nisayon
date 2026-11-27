import { Box3, Ray, Vector3 } from "three";

// Presentation-space clearances, in metres. The perimeter garden, glazing,
// columns and workbench stay outside the camera's navigable aisle. This does
// not change the source robot, recorded pose or task collision geometry.
const consoleClearance = new Box3(new Vector3(3.1, -.1, -.2), new Vector3(5.3, 2.02, 2.2));
const ray = new Ray(), direction = new Vector3(), candidate = new Vector3(), hit = new Vector3();

export function confineLabCamera(eye: Vector3, target: Vector3, overhead = false): void {
  direction.subVectors(eye, target);
  const distance = direction.length();
  if (distance < 1e-6) return;
  direction.divideScalar(distance);
  const clear = (t: number) => {
    candidate.copy(target).addScaledVector(direction, t);
    if (Math.abs(candidate.x) > 4.7 || candidate.z < -9.2 || candidate.z > 9.2 || candidate.y < .3) return false;
    // Stay below the inner vault except in the explicit sectioned top view.
    const rise = Math.max(0, candidate.y - 2.2);
    return overhead || (candidate.x / 5.0) ** 2 + (rise / 3.85) ** 2 < 1;
  };
  let length = distance;
  if (!clear(distance)) {
    let low = 0, high = distance;
    for (let i = 0; i < 24; i++) {
      const mid = (low + high) / 2;
      if (clear(mid)) low = mid; else high = mid;
    }
    length = low;
  }
  // Avoid settling behind the console when orbiting at monitor height. The
  // radial request stays intact so returning to an open aisle restores it.
  ray.set(target, direction);
  if (!consoleClearance.containsPoint(target) && ray.intersectBox(consoleClearance, hit)) {
    length = Math.min(length, Math.max(.3, hit.distanceTo(target) - .15));
  }
  eye.copy(target).addScaledVector(direction, length);
}
