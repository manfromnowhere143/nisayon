import * as THREE from "three";

// Shared by both viewers. Metres, y up. These are authored
// presentation lights, never a calibrated room, sensor or physical result.
export const DAYLIGHT = { sun: [-8, 10, -6] as const, target: [0, 0, -2] as const, intensity: 2.4, colour: 0xf3f5ff };

// Building-aligned procedural radiance: no image dependency or stale bake from
// the earlier material palette. The floor separately reflects scene geometry.
export function daylightEnvironment() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xa0a7af).multiplyScalar(.8);
  const geometry = new THREE.PlaneGeometry(1, 1);
  const surfaces: THREE.MeshBasicMaterial[] = [];
  function panel(position: [number, number, number], scale: [number, number], rotation: [number, number, number], colour: number, intensity: number) {
    const material = new THREE.MeshBasicMaterial({ color: new THREE.Color(colour).multiplyScalar(intensity), side: THREE.DoubleSide });
    surfaces.push(material);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(...position); mesh.scale.set(...scale, 1); mesh.rotation.set(...rotation); scene.add(mesh);
  }
  panel([0, -.016, 0], [15, 24], [-Math.PI / 2, 0, 0], 0x171b20, .18);
  panel([5.9, 2.7, 0], [22, 5.4], [0, -Math.PI / 2, 0], 0xb9babc, .55);
  panel([0, 6.6, 0], [12, 24], [Math.PI / 2, 0, 0], 0xb4b5b8, .75);
  panel([-6.1, 2.75, 0], [23, 5.5], [0, Math.PI / 2, 0], 0xe6eaf0, 2.2);
  panel([0, 2.75, -10.3], [12.2, 5.5], [0, 0, 0], 0xdfe6ee, 1.7);
  panel([0, 6.55, 0], [1.6, 23], [Math.PI / 2, 0, 0], 0xe6f1ff, 3);
  return { scene, dispose() { geometry.dispose(); surfaces.forEach(m => m.dispose()); } };
}
