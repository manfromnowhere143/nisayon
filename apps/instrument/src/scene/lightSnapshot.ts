import * as THREE from "three";
import { REFINEMENT_LIMITS } from "./refinement";

// Freeze the currently visible world matrices. No IK, easing, mesh replacement,
// simulator step or transform interpolation. Annotations stay out of the BVH.
export function lightSnapshot(source: THREE.Scene, camera: THREE.PerspectiveCamera) {
  source.updateMatrixWorld(true); camera.updateMatrixWorld(true);
  const physical = new THREE.Scene(), overlays = new THREE.Scene();
  const geometries = new Map<THREE.BufferGeometry, THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  let bytes = 0, triangles = 0;
  const dispose = () => { for (const geometry of geometries.values()) geometry.dispose(); for (const material of materials) material.dispose(); physical.clear(); overlays.clear(); };
  try {
    source.traverseVisible(object => {
      if (object instanceof THREE.DirectionalLight) {
        const light = object.clone();
        light.position.setFromMatrixPosition(object.matrixWorld);
        light.target.position.setFromMatrixPosition(object.target.matrixWorld);
        physical.add(light, light.target); return;
      }
      if (!(object instanceof THREE.Mesh || object instanceof THREE.Line || object instanceof THREE.Points)) return;
      const sourceGeometry: THREE.BufferGeometry = object.geometry;
      let geometry: THREE.BufferGeometry | undefined = geometries.get(sourceGeometry);
      if (!geometry) {
        bytes += Object.values(sourceGeometry.attributes).reduce((n, a) => n + a.array.byteLength, sourceGeometry.index?.array.byteLength ?? 0);
        if (bytes > REFINEMENT_LIMITS.geometryBytes) throw Error("Still geometry exceeds the retained buffer budget");
        geometry = sourceGeometry.clone(); geometries.set(sourceGeometry, geometry);
      }
      let annotation = !(object instanceof THREE.Mesh);
      for (let node: THREE.Object3D | null = object; node; node = node.parent) annotation ||= node.userData.recordingOverlay === true;
      const original = Array.isArray(object.material) ? object.material : [object.material];
      annotation ||= original.some(m => !(m instanceof THREE.MeshStandardMaterial));
      const copies = original.map(m => {
        let copy = m.clone();
        if (annotation && m instanceof THREE.MeshStandardMaterial) {
          copy.dispose();
          copy = new THREE.MeshBasicMaterial({ color: m.color, opacity: m.opacity, transparent: m.transparent, depthWrite: m.depthWrite, depthTest: m.depthTest, side: m.side });
        } else if (copy instanceof THREE.MeshStandardMaterial) {
          // The selected link's UI luminance must not illuminate nearby parts.
          copy.emissive.set(0);
          // The tracer reads a material flag, not Mesh.castShadow. In
          // particular, the cutaway walls must not become light blockers.
          Object.assign(copy, { castShadow: object.castShadow });
        }
        materials.add(copy); return copy;
      });
      const clone = object.clone(false) as THREE.Mesh;
      clone.geometry = geometry; clone.material = Array.isArray(object.material) ? copies : copies[0]!;
      clone.matrixAutoUpdate = false; clone.matrix.copy(object.matrixWorld); clone.matrixWorld.copy(object.matrixWorld);
      if (!annotation) {
        triangles += (geometry.index?.count ?? geometry.getAttribute("position").count) / 3;
        if (triangles > REFINEMENT_LIMITS.triangles) throw Error("Still geometry exceeds the triangle budget");
      }
      (annotation ? overlays : physical).add(clone);
    });
    const view = camera.clone(); view.position.setFromMatrixPosition(camera.matrixWorld); view.quaternion.setFromRotationMatrix(camera.matrixWorld); view.updateMatrixWorld(true);
    physical.environmentIntensity = source.environmentIntensity;
    return { physical, overlays, camera: view, bytes, triangles, dispose };
  } catch (error) { dispose(); throw error; }
}
