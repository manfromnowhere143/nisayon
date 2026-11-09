// Orthographic projection of MuJoCo world points for the SVG fallback. The
// same frames as the WebGL scene, drawn without a GPU.

import { viewBasis, type SceneView } from "./framing";

export interface Projected {
  x: number;
  y: number;
  depth: number;
}

export function projectPoint(x: number, y: number, z: number, view: SceneView): Projected {
  const { right, up, back } = viewBasis(view);
  return { x: x * right[0] + y * right[1] + z * right[2], y: x * up[0] + y * up[1] + z * up[2], depth: x * back[0] + y * back[1] + z * back[2] };
}
