import * as THREE from "three";

export type ScenePick = { kind: "body"; body: number } | { kind: "workstation"; id: "recording" } | { kind: "instrument"; id: "contact" };

export function pickScene(ray: THREE.Raycaster, roots: THREE.Object3D[]): ScenePick | null {
  const meshes: THREE.Mesh[] = [];
  for (const root of roots) root.traverseVisible(object => {
    if (!(object instanceof THREE.Mesh) || object.userData.ignorePick) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    // Glazing and display annotations do not intercept a ray. Opaque furniture
    // does, even when it is unselectable. Hidden parents never participate.
    if (materials.every(m => !m.visible || (m.transparent && m.opacity < .2))) return;
    meshes.push(object);
  });
  const hit = ray.intersectObjects(meshes, false).find(intersection => {
    const mesh = intersection.object as THREE.Mesh;
    const material = Array.isArray(mesh.material) ? mesh.material[intersection.face?.materialIndex ?? 0] : mesh.material;
    if (!material?.visible || (material.transparent && material.opacity < .2)) return false;
    // Raycaster does not apply the shader's local clipping. The overhead roof
    // cutaway must expose the same surfaces to input that it exposes to sight.
    const planes = material.clippingPlanes;
    if (!planes?.length) return true;
    const clipped = (plane: THREE.Plane) => plane.distanceToPoint(intersection.point) < 0;
    return material.clipIntersection ? !planes.every(clipped) : !planes.some(clipped);
  });
  if (hit?.object.userData.workstation === "recording") return { kind: "workstation", id: "recording" };
  if (hit?.object.userData.instrument === "contact") return { kind: "instrument", id: "contact" };
  const body: unknown = hit?.object.userData.body;
  return typeof body === "number" && body > 0 ? { kind: "body", body } : null;
}

// Raycaster does not exclude an invisible ancestor. Only visible primary
// meshes participate; the nearest opaque environment mesh also blocks a pick.
export function pickBody(ray: THREE.Raycaster, roots: THREE.Object3D[]): number | null {
  const hit = pickScene(ray, roots);
  return hit?.kind === "body" ? hit.body : null;
}
