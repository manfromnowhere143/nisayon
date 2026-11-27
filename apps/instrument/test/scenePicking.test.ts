// @vitest-environment node
import { expect, it } from "vitest";
import { BoxGeometry, Group, Mesh, MeshBasicMaterial, Plane, Raycaster, Vector3 } from "three";
import { createArchitecture } from "../src/scene/architecture";
import { pickScene } from "../src/scene/picking";

it("selects the visible robot through the real overhead cutaway while retaining the closed roof's occlusion", () => {
  const hall = createArchitecture(), root = new Group(), geometry = new BoxGeometry(.5, .5, .5), material = new MeshBasicMaterial();
  const body = new Mesh(geometry, material); body.position.y = 1; body.userData.body = 12;
  root.add(hall.root, body); root.updateMatrixWorld(true);
  // Cross the solid shell beside the narrow central skylight.
  const ray = new Raycaster(new Vector3(3, 9, 0), new Vector3(-3, -8, 0).normalize());
  expect(pickScene(ray, [root])).toBeNull();
  hall.cutaway(true);
  expect(pickScene(ray, [root])).toEqual({ kind: "body", body: 12 });
  hall.cutaway(false);
  expect(pickScene(ray, [root])).toBeNull();
  hall.dispose(); geometry.dispose(); material.dispose();
});

it("matches intersection clipping and keeps the visible desk distinct from a body", () => {
  const root = new Group(), geometry = new BoxGeometry(1, 1, 1), material = new MeshBasicMaterial();
  const desk = new Mesh(geometry, material); desk.userData.workstation = "recording";
  root.add(desk); root.updateMatrixWorld(true);
  const ray = new Raycaster(new Vector3(0, 0, 4), new Vector3(0, 0, -1));
  expect(pickScene(ray, [root])).toEqual({ kind: "workstation", id: "recording" });
  material.clippingPlanes = [new Plane(new Vector3(1, 0, 0), -1), new Plane(new Vector3(0, 1, 0), 1)];
  expect(pickScene(ray, [root])).toBeNull();
  material.clipIntersection = true;
  expect(pickScene(ray, [root])).toEqual({ kind: "workstation", id: "recording" });
  material.visible = false;
  expect(pickScene(ray, [root])).toBeNull();
  geometry.dispose(); material.dispose();
});
