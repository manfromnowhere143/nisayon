import { useEffect, useMemo } from "react";
import * as THREE from "three";
import type { FramePhase } from "../model/types";
import type { Vec3 } from "../model/pose";
import type { CollisionView } from "./collisionAssets";
import { createCollisionLayer } from "./collisionLayer";

export function CollisionSvg({ view, frame, project }: { view: CollisionView; frame: FramePhase; project: (point: Vec3) => [number, number] }) {
  const layer = useMemo(() => createCollisionLayer(view), [view]);
  useEffect(() => () => layer.dispose(), [layer]);
  layer.pose(frame, true); layer.root.updateMatrixWorld(true);
  const paths: { name: string; path: string }[] = [], p = new THREE.Vector3();
  layer.root.traverse(object => {
    if (!(object instanceof THREE.LineSegments)) return;
    const positions = object.geometry.getAttribute("position"); let path = "";
    for (let i = 0; i < positions.count; i++) {
      p.fromBufferAttribute(positions, i).applyMatrix4(object.matrixWorld);
      const [x, y] = project([p.x, p.y, p.z]);
      path += `${i % 2 ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
    }
    paths.push({ name: object.name, path });
  });
  return <g className="svg-collision" aria-label="Finite collision geometry; no contact evidence">{paths.map(p => <path key={p.name} d={p.path}><title>{p.name}</title></path>)}</g>;
}
