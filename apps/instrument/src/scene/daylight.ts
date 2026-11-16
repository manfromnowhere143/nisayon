import * as THREE from "three";

// Shared with the offline lighting bake. Metres, y up. These are authored
// presentation lights, never a calibrated room, sensor or physical result.
export const DAYLIGHT = { sun: [-8, 10, -6] as const, target: [0, 0, -2] as const, intensity: 3, colour: 0xffeed6 };

// An inexpensive, building-aligned reflection environment while the baked
// radiance loads, and a complete fallback when local media is unavailable.
export function daylightEnvironment() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xaec3c9).multiplyScalar(.8);
  const geometry = new THREE.PlaneGeometry(1, 1);
  const surfaces: THREE.MeshBasicMaterial[] = [];
  function panel(position: [number, number, number], scale: [number, number], rotation: [number, number, number], colour: number, intensity: number) {
    const material = new THREE.MeshBasicMaterial({ color: new THREE.Color(colour).multiplyScalar(intensity), side: THREE.DoubleSide });
    surfaces.push(material);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(...position); mesh.scale.set(...scale, 1); mesh.rotation.set(...rotation); scene.add(mesh);
  }
  panel([0, -.016, 0], [15, 24], [-Math.PI / 2, 0, 0], 0x858d87, .25);
  panel([5.9, 2.7, 0], [22, 5.4], [0, -Math.PI / 2, 0], 0xc3bcae, .55);
  panel([0, 6.6, 0], [12, 24], [Math.PI / 2, 0, 0], 0xb1a186, .75);
  panel([-6.1, 2.75, 0], [23, 5.5], [0, Math.PI / 2, 0], 0xe2ede4, 2.2);
  panel([0, 2.75, -10.3], [12.2, 5.5], [0, 0, 0], 0xd7e5e1, 1.7);
  panel([0, 6.55, 0], [1.6, 23], [Math.PI / 2, 0, 0], 0xe6f1ff, 3);
  return { scene, dispose() { geometry.dispose(); surfaces.forEach(m => m.dispose()); } };
}
