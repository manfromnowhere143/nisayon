import { expect, it } from "vitest";
import { BoxGeometry, Group, Mesh, MeshBasicMaterial, PerspectiveCamera, Vector3 } from "three";
import { projectBodyAnnotation } from "../src/scene/bodyAnnotation";
import { partInspectionPlacement } from "../src/ui/partInspectionPlacement";

it("anchors to transformed visible body geometry and excludes room geometry from the robot silhouette", () => {
  const root = new Group(), geometry = new BoxGeometry(1, 1, 1), material = new MeshBasicMaterial();
  const selected = new Mesh(geometry, material); selected.userData.body = 4; selected.position.x = 1;
  const robot = new Mesh(geometry, material); robot.userData.body = 3;
  const room = new Mesh(geometry, material); room.userData.body = 0; room.scale.setScalar(100);
  const hidden = new Mesh(geometry, material); hidden.userData.body = 4; hidden.position.x = 50; hidden.visible = false;
  root.add(selected, robot, room, hidden); root.position.y = 1; root.updateMatrixWorld(true);
  const camera = new PerspectiveCamera(50, 2, .1, 30); camera.position.z = 6; camera.updateMatrixWorld(true);
  const before = selected.matrixWorld.clone();
  const result = projectBodyAnnotation([root], 4, new Vector3(0, 0, 0), camera, 1000, 500, new Set([3, 4]));
  const projected = new Vector3(1, 1, 0).project(camera);
  expect(result.x).toBe(Math.round((projected.x + 1) * 500));
  expect(result.y).toBe(Math.round((1 - projected.y) * 250));
  expect(result.visible).toBe(true); expect(result.body).toHaveLength(2);
  expect(selected.matrixWorld.equals(before)).toBe(true);
  root.position.x = 100; root.updateMatrixWorld(true);
  expect(projectBodyAnnotation([root], 4, new Vector3(), camera, 1000, 500, new Set([3, 4])).visible).toBe(false);
  geometry.dispose(); material.dispose();
});

it("uses the retained body origin when a body has no visible mesh", () => {
  const camera = new PerspectiveCamera(50, 1, .1, 30); camera.position.z = 6; camera.updateMatrixWorld(true);
  const result = projectBodyAnnotation([], 4, new Vector3(0, 0, 0), camera, 390, 390, new Set());
  expect(result).toMatchObject({ bodyId: 4, x: 195, y: 195, visible: true, body: [] });
});

it.each([[320, 568], [390, 844], [852, 393], [1280, 800]])("keeps compact and expanded details inside header, transport and cutout clearance at %s × %s", (width, height) => {
  const safe = { left: 28, right: width - 28, top: 84, bottom: height - 104 };
  const anchor = { x: width * .6, y: height * .5, width, height, visible: true, body: [{ left: width * .4, right: width * .6, top: 110, bottom: height * .65 }] };
  for (const expanded of [false, true]) {
    const result = partInspectionPlacement(anchor, { width: expanded ? 300 : 248, height: expanded ? 460 : 158 }, safe);
    expect(result.left).toBeGreaterThanOrEqual(safe.left + 10);
    expect(result.top).toBeGreaterThanOrEqual(safe.top + 10);
    expect(result.left + result.width).toBeLessThanOrEqual(safe.right - 10);
    expect(result.top + result.height).toBeLessThanOrEqual(safe.bottom - 10);
    expect(Number.isFinite(result.end.x + result.end.y + result.bend.x + result.bend.y)).toBe(true);
  }
});

it("places detail off the Panda silhouette when the safe area has space", () => {
  const anchor = { x: 640, y: 400, width: 1280, height: 800, visible: true, body: [{ left: 520, right: 700, top: 210, bottom: 580 }] };
  const placed = partInspectionPlacement(anchor, { width: 300, height: 380 }, { left: 20, right: 1260, top: 84, bottom: 696 });
  expect(placed.left >= 700 || placed.left + placed.width <= 520).toBe(true);
});
