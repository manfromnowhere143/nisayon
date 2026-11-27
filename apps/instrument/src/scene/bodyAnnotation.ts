import { Box3, Camera, Mesh, Object3D, Vector3 } from "three";
import type { AnnotationAnchor, ScreenRect } from "../concepts/annotationPlacement";

export interface BodyAnnotation extends AnnotationAnchor { bodyId: number }

export function sameBodyAnnotation(a: BodyAnnotation | null, b: BodyAnnotation | null) {
  return a === b || (!!a && !!b && a.bodyId === b.bodyId && a.width === b.width && a.height === b.height &&
    a.x === b.x && a.y === b.y && a.visible === b.visible && a.body.length === b.body.length &&
    a.body.every((rect, index) => { const other = b.body[index]!; return rect.left === other.left && rect.right === other.right && rect.top === other.top && rect.bottom === other.bottom; }));
}

/** Project visible presentation meshes. These bounds never enter the recorded
 * model, collision system or numerical readings. Called by the existing draw. */
export function projectBodyAnnotation(roots: Object3D[], bodyId: number, origin: Vector3,
  camera: Camera, width: number, height: number, subjectBodies: ReadonlySet<number>): BodyAnnotation {
  const selected = new Box3(), bounds = new Box3(), point = new Vector3();
  const body: ScreenRect[] = [];
  for (const root of roots) root.traverseVisible(object => {
    if (!(object instanceof Mesh) || typeof object.userData.body !== "number") return;
    const id = object.userData.body as number;
    if (id !== bodyId && !subjectBodies.has(id)) return;
    if (!object.geometry.boundingBox) object.geometry.computeBoundingBox();
    if (!object.geometry.boundingBox) return;
    bounds.copy(object.geometry.boundingBox).applyMatrix4(object.matrixWorld);
    if (id === bodyId) selected.union(bounds);
    const rect = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity };
    for (const x of [bounds.min.x, bounds.max.x]) for (const y of [bounds.min.y, bounds.max.y]) for (const z of [bounds.min.z, bounds.max.z]) {
      point.set(x, y, z).project(camera);
      if (point.z < -1 || point.z > 1) continue;
      const sx = (point.x + 1) * width / 2, sy = (1 - point.y) * height / 2;
      rect.left = Math.min(rect.left, sx); rect.right = Math.max(rect.right, sx);
      rect.top = Math.min(rect.top, sy); rect.bottom = Math.max(rect.bottom, sy);
    }
    if (Number.isFinite(rect.left)) body.push(rect);
  });
  if (selected.isEmpty()) point.copy(origin); else selected.getCenter(point);
  point.project(camera);
  return { bodyId, width, height, x: Math.round((point.x + 1) * width / 2), y: Math.round((1 - point.y) * height / 2),
    visible: point.z >= -1 && point.z <= 1 && Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1, body };
}
