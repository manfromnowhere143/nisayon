import * as THREE from "three";

// Raycaster does not exclude an invisible ancestor. Only visible primary
// meshes participate; the nearest opaque environment mesh also blocks a pick.
export function pickBody(ray: THREE.Raycaster, roots: THREE.Object3D[]): number | null {
  const meshes: THREE.Mesh[] = [];
  for (const root of roots) root.traverseVisible((object) => {
    if (object instanceof THREE.Mesh) meshes.push(object);
  });
  const hit = ray.intersectObjects(meshes, false)[0];
  const body: unknown = hit?.object.userData.body;
  return typeof body === "number" && body > 0 ? body : null;
}
