import { expect, it } from "vitest";
import * as THREE from "three";
import { createArchitecture } from "../src/scene/architecture";

it("keeps the presentation separate from body identity and batches the static hall", () => {
  const hall = createArchitecture();
  let drawables = 0;
  hall.root.updateMatrixWorld(true);
  hall.root.traverse(object => {
    expect(object.userData.body).toBeUndefined();
    if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
      drawables++;
      expect([...object.geometry.getAttribute("position").array].every(Number.isFinite)).toBe(true);
      if (object instanceof THREE.InstancedMesh) expect([...object.instanceMatrix.array].every(Number.isFinite)).toBe(true);
    }
  });
  expect(drawables).toBeLessThan(30);
  expect(hall.workstations.info.stations).toBe(1);
  expect(hall.workstations.screens).toHaveLength(1);
  const bounds = new THREE.Box3().setFromObject(hall.root);
  // The distant garden backing extends one metre below the visible floor.
  expect(bounds.min.y).toBeGreaterThanOrEqual(-1.01);
  expect(bounds.max.y).toBeGreaterThan(6);
  const scene = new THREE.Scene(); scene.add(hall.root); hall.dispose();
  expect(scene.children).toHaveLength(0);
});
