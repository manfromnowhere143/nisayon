import * as THREE from "three";
import type { FramePhase } from "../model/types";
import type { CollisionView } from "./collisionAssets";

export function createCollisionLayer(view: CollisionView) {
  const root = new THREE.Group(), bodies = new Map<number, THREE.Group>();
  const geometries = new Map<string, THREE.BufferGeometry>();
  const material = new THREE.LineBasicMaterial({ color: 0x96aab9, transparent: true, opacity: .85, depthTest: false, depthWrite: false });
  for (const part of view.parts) {
    let body = bodies.get(part.body);
    if (!body) { body = new THREE.Group(); bodies.set(part.body, body); root.add(body); }
    const key = part.mesh ?? `${part.type}:${part.size.join(",")}`;
    let edges = geometries.get(key);
    if (!edges) {
      let geometry: THREE.BufferGeometry;
      if (part.mesh) {
        const mesh = view.meshes.get(part.mesh)!;
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.BufferAttribute(mesh.positions, 3));
        geometry.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
      } else if (part.type === "box") geometry = new THREE.BoxGeometry(...part.size.map(n => n * 2) as [number, number, number]);
      else { geometry = new THREE.CylinderGeometry(part.size[0], part.size[0], part.size[1] * 2, 24, 1); geometry.rotateX(Math.PI / 2); }
      edges = part.mesh ? new THREE.WireframeGeometry(geometry) : new THREE.EdgesGeometry(geometry, 25);
      geometry.dispose(); geometries.set(key, edges);
    }
    const line = new THREE.LineSegments(edges, material);
    line.position.set(...part.position);
    const [w, x, y, z] = part.quaternion; line.quaternion.set(x, y, z, w);
    line.name = part.name; line.renderOrder = 12; line.raycast = () => {};
    body.add(line);
  }
  return {
    root,
    pose(frame: FramePhase | null, visible: boolean) {
      root.visible = visible && frame !== null;
      if (!root.visible || !frame) return;
      for (const [i, body] of bodies) {
        body.position.fromArray(frame.xpos, i * 3);
        const k = i * 4; body.quaternion.set(frame.xquat[k + 1]!, frame.xquat[k + 2]!, frame.xquat[k + 3]!, frame.xquat[k]!);
      }
    },
    palette(ground: "black" | "paper") { material.color.set(ground === "black" ? 0x9fb8c9 : 0x3b5362); },
    dispose() { root.removeFromParent(); for (const geometry of geometries.values()) geometry.dispose(); material.dispose(); },
  };
}
