import * as THREE from "three";
import type { FramePhase } from "../model/types";
import type { VisualAsset } from "./visualAssets";

// Buffers are created once per model view, shared by its two figures, and
// explicitly released when that view is replaced. Seeking changes transforms.
export function buildNativeSurfaces(asset: VisualAsset) {
  const geometries = new Map(asset.meshes.map((mesh) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(mesh.positions, 3));
    geometry.setAttribute("normal", new THREE.BufferAttribute(mesh.normals, 3));
    geometry.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
    geometry.computeBoundingSphere();
    return [mesh.name, geometry] as const;
  }));
  const ownedMaterials: THREE.MeshStandardMaterial[] = [];
  const contours = new Map<string, THREE.EdgesGeometry>();
  const contourMaterial = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: .8, depthWrite: false });

  function figure(ghost: boolean) {
    const root = new THREE.Group();
    root.userData.recordingOverlay = ghost;
    const bodies = new Map<number, THREE.Group>();
    const materials: { source: THREE.Color; material: THREE.MeshStandardMaterial; body: number }[] = [];
    const surfaces: { mesh: THREE.Mesh; name: string; body: number; contour?: THREE.LineSegments }[] = [];
    for (const part of asset.parts) {
      let body = bodies.get(part.body);
      if (!body) { body = new THREE.Group(); bodies.set(part.body, body); root.add(body); }
      const source = new THREE.Color(part.rgba[0], part.rgba[1], part.rgba[2]).convertSRGBToLinear();
      const dark = Math.max(...part.rgba.slice(0, 3)) < 0.4;
      const material = new THREE.MeshStandardMaterial({
        color: source, roughness: dark ? 0.48 : 0.32, metalness: dark ? 0.25 : 0.12,
        transparent: ghost, opacity: ghost ? 0.23 : part.rgba[3], depthWrite: !ghost,
      });
      materials.push({ source, material, body: part.body });
      ownedMaterials.push(material);
      const mesh = new THREE.Mesh(geometries.get(part.mesh), material);
      mesh.name = part.name;
      mesh.userData.body = part.body;
      mesh.position.set(...part.position);
      const [w, x, y, z] = part.quaternion_wxyz;
      mesh.quaternion.set(x, y, z, w);
      mesh.castShadow = !ghost;
      mesh.receiveShadow = !ghost;
      body.add(mesh);
      surfaces.push({ mesh, name: part.mesh, body: part.body });
    }
    return {
      root,
      select(body: number | null) {
        for (const entry of materials) {
          entry.material.emissive.set(!ghost && entry.body === body ? 0xffffff : 0x000000);
          entry.material.emissiveIntensity = 0.15;
        }
        if (!ghost) for (const surface of surfaces) {
          const selected = surface.body === body;
          if (selected && !surface.contour) {
            let edges = contours.get(surface.name);
            if (!edges) { edges = new THREE.EdgesGeometry(surface.mesh.geometry, 28); contours.set(surface.name, edges); }
            surface.contour = new THREE.LineSegments(edges, contourMaterial);
            surface.contour.raycast = () => {};
            surface.mesh.add(surface.contour);
          }
          if (surface.contour) surface.contour.visible = selected;
        }
      },
      pose(frame: FramePhase | null) {
        root.visible = frame !== null;
        if (!frame) return;
        for (const [index, body] of bodies) {
          const p = index * 3, q = index * 4;
          body.position.set(frame.xpos[p]!, frame.xpos[p + 1]!, frame.xpos[p + 2]!);
          body.quaternion.set(frame.xquat[q + 1]!, frame.xquat[q + 2]!, frame.xquat[q + 3]!, frame.xquat[q]!);
        }
      },
      palette(ground: "black" | "paper", correction: boolean) {
        contourMaterial.color.set(ground === "black" ? 0xffffff : 0x252b31);
        for (const { source, material } of materials) {
          material.color.copy(source);
          if (ghost) material.color.set(ground === "black" ? 0xc3c8cc : 0x464b51);
          else {
            if (ground === "paper") material.color.multiplyScalar(0.79);
            if (correction) material.color.lerp(new THREE.Color(ground === "black" ? 0x8fb0d6 : 0x3f6087), 0.22);
          }
        }
      },
    };
  }

  const primary = figure(false), ghost = figure(true);
  return {
    primary, ghost,
    dispose() {
      primary.root.removeFromParent();
      ghost.root.removeFromParent();
      for (const geometry of geometries.values()) geometry.dispose();
      for (const material of ownedMaterials) material.dispose();
      for (const geometry of contours.values()) geometry.dispose();
      contourMaterial.dispose();
    },
  };
}
