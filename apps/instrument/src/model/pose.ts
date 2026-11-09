// Quaternion arithmetic in the exporter's wxyz convention, used where the
// browser composes a body pose with a geometry's local pose.

export type Quat = [number, number, number, number];
export type Vec3 = [number, number, number];

export function quatRotate(q: Quat, v: Vec3): Vec3 {
  const [w, x, y, z] = q;
  const [vx, vy, vz] = v;
  const cx = y * vz - z * vy;
  const cy = z * vx - x * vz;
  const cz = x * vy - y * vx;
  const ccx = y * cz - z * cy;
  const ccy = z * cx - x * cz;
  const ccz = x * cy - y * cx;
  return [vx + 2 * (w * cx + ccx), vy + 2 * (w * cy + ccy), vz + 2 * (w * cz + ccz)];
}

export function quatMultiply(a: Quat, b: Quat): Quat {
  const [aw, ax, ay, az] = a;
  const [bw, bx, by, bz] = b;
  return [
    aw * bw - ax * bx - ay * by - az * bz,
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
  ];
}

export function poseAt(buffer: Float64Array, index: number): { pos: Vec3; quat: Quat } {
  const o = index * 7;
  return {
    pos: [buffer[o] as number, buffer[o + 1] as number, buffer[o + 2] as number],
    quat: [buffer[o + 3] as number, buffer[o + 4] as number, buffer[o + 5] as number, buffer[o + 6] as number],
  };
}
