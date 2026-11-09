// @vitest-environment node
// Camera framing without a browser: the named views must keep the table, the
// cube and the arm's reach inside the frustum with a margin, at phone and
// desktop aspect ratios. This is geometry, not a visual acceptance.
import { describe, expect, it } from "vitest";
import { PerspectiveCamera, Vector3 } from "three";
import { toThreeVector } from "../src/scene/convert";
import { SCENE_VIEWS, CAMERA_FOV } from "../src/scene/renderer";
import { DEFAULT_BOUNDS, corners, fitCamera, viewBasis } from "../src/scene/framing";
import { projectPoint } from "../src/scene/project";

const POINTS: [string, [number, number, number]][] = [
  ["table corner +x+y", [0.4, 0.4, 0.8]],
  ["table corner -x-y", [-0.4, -0.4, 0.8]],
  ["table corner +x-y", [0.4, -0.4, 0.8]],
  ["table corner -x+y", [-0.4, 0.4, 0.8]],
  ["cube at reset", [0.0267, 0.0013, 0.8316]],
  ["gripper at reset", [-0.11, 0.023, 1.008]],
  ["robot base", [-0.56, 0, 0.912]],
  ["arm shoulder", [-0.56, 0, 1.245]],
  ["arm raised reach", [-0.3, 0.1, 1.45]],
  ["retained D01 link3 row 0 before", [-0.49949155271254025, 0.0013081687721355484, 1.555149990329396]],
];

describe("named camera views frame the workspace", () => {
  for (const view of SCENE_VIEWS) {
    for (const [label, aspect] of [
      ["phone 390×359", 390 / 359],
      ["desktop 1440 scene 840×640", 840 / 640],
      ["narrow inspector scene", 0.6],
    ] as const) {
      it(`${view} keeps the scene inside the frame at ${label}`, () => {
        const camera = new PerspectiveCamera(CAMERA_FOV, aspect, 0.05, 30);
        const fit = fitCamera(view, aspect);
        camera.position.copy(toThreeVector(...fit.position));
        camera.lookAt(toThreeVector(...fit.target));
        camera.updateMatrixWorld();
        camera.updateProjectionMatrix();
        for (const [name, p] of [...POINTS, ...corners(DEFAULT_BOUNDS).map((p): [string, typeof p] => ["subject envelope", p])]) {
          const ndc = toThreeVector(p[0], p[1], p[2]).project(camera);
          expect(Math.abs(ndc.x), `${name} x`).toBeLessThan(0.92);
          expect(Math.abs(ndc.y), `${name} y`).toBeLessThan(0.92);
          expect(ndc.z, `${name} in front`).toBeLessThan(1);
        }
        // The cube should occupy a meaningful part of the frame, not a speck:
        // its 4 cm edge must span at least 1.2% of the frame width.
        const a = toThreeVector(0.0067, 0.0013, 0.8316).project(camera);
        const b = toThreeVector(0.0467, 0.0013, 0.8316).project(camera);
        expect(new Vector3().subVectors(b, a).length()).toBeGreaterThan(0.024);
        const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
        const { right: expected } = viewBasis(view);
        expect(right.distanceTo(toThreeVector(...expected))).toBeLessThan(1e-12);
        [projectPoint(1, 0, 0, view).x, projectPoint(0, 1, 0, view).x, projectPoint(0, 0, 1, view).x].forEach((v, i) => expect(v).toBeCloseTo(expected[i]!, 14));
      });
    }
  }
});
