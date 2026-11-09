// DOM/SVG fallback drawing the same published frames when WebGL2 is
// unavailable or the graphics context is lost. Orthographic, labeled.

import { useMemo } from "react";
import type { FramePhase, ModelRecord } from "../model/types";
import { poseAt, quatRotate, type Quat, type Vec3 } from "../model/pose";
import { projectPoint, type Projected } from "./project";
import type { SceneView } from "./renderer";
import { corners, DEFAULT_BOUNDS, type SubjectBounds } from "./framing";
import { axisEnds, cubeHalfSize, observationPair, OBSERVATION_AXIS_LENGTH } from "../model/spatial";
import type { SpatialLayerState } from "./evidenceLayer";
import { controllerFrame, observedFingerPads } from "../model/physicalDisplay";
import { CollisionSvg } from "./CollisionSvg";
import type { CollisionView } from "./collisionAssets";

interface Props {
  frame: FramePhase | null;
  ghostFrame: FramePhase | null;
  model: ModelRecord;
  view: SceneView;
  width: number;
  height: number;
  correction: boolean;
  bounds?: SubjectBounds;
  spatial?: SpatialLayerState;
  collision?: CollisionView | null;
}

interface Mark {
  depth: number;
  element: React.ReactNode;
}

export function SchematicSvg({ frame, ghostFrame, model, view, width, height, correction, bounds = DEFAULT_BOUNDS, spatial, collision }: Props) {
  const fit = useMemo(() => {
    const projected = corners(bounds).map(([x, y, z]) => projectPoint(x, y, z, view));
    const xs = projected.map((p) => p.x);
    const ys = projected.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const scale = Math.min((width - 24) / (maxX - minX), (height - 24) / (maxY - minY));
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    return {
      scale,
      map(p: Projected): [number, number] {
        return [width / 2 + (p.x - cx) * scale, height / 2 - (p.y - cy) * scale];
      },
    };
  }, [view, width, height, bounds]);

  const marks = useMemo(() => {
    const indexOf = new Map(model.bodies.map((b) => [b.name, b.index]));
    const out: Mark[] = [];
    const draw = (f: FramePhase, ghost: boolean): void => {
      const pt = (i: number): Projected => projectPoint(f.xpos[i * 3] as number, f.xpos[i * 3 + 1] as number, f.xpos[i * 3 + 2] as number, view);
      const cls = ghost ? "svg-ghost" : "svg-solid";
      const bodyName = new Map(model.bodies.map((b) => [b.index, b.name]));
      for (const index of model.schematic.drawable_geoms) {
        const geom = model.geoms[index];
        if (!geom || index * 7 + 6 >= f.geoms.length) continue;
        const owner = bodyName.get(geom.body) ?? "";
        const isCube = owner.startsWith("cube");
        if (ghost && !isCube) continue;
        const pose = poseAt(f.geoms, index);
        if (geom.type === "box") {
          const corners = boxCorners(pose.pos, pose.quat, geom.size);
          const projected = corners.map((c) => projectPoint(c[0], c[1], c[2], view));
          const depth = projected.reduce((sum, p) => sum + p.depth, 0) / projected.length;
          const edges: [number, number][] = [
            [0, 1], [1, 3], [3, 2], [2, 0],
            [4, 5], [5, 7], [7, 6], [6, 4],
            [0, 4], [1, 5], [2, 6], [3, 7],
          ];
          out.push({
            depth,
            element: (
              <g key={`${geom.name}-${ghost}`} data-body={ghost ? undefined : geom.body} data-selected={!ghost && spatial?.selectedBody === geom.body} className={`${cls} ${isCube ? "svg-cube" : "svg-table"}`}>
                {edges.map(([a, b], i) => {
                  const [x1, y1] = fit.map(projected[a] as Projected);
                  const [x2, y2] = fit.map(projected[b] as Projected);
                  return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />;
                })}
              </g>
            ),
          });
        } else if (geom.type === "cylinder" && !ghost) {
          const axis = quatRotate(pose.quat, [0, 0, geom.size[1]]);
          const top = projectPoint(pose.pos[0] + axis[0], pose.pos[1] + axis[1], pose.pos[2] + axis[2], view);
          const bottom = projectPoint(pose.pos[0] - axis[0], pose.pos[1] - axis[1], pose.pos[2] - axis[2], view);
          const [x1, y1] = fit.map(top);
          const [x2, y2] = fit.map(bottom);
          out.push({
            depth: (top.depth + bottom.depth) / 2,
            element: <line key={geom.name} data-body={geom.body} data-selected={spatial?.selectedBody === geom.body} className="svg-table" x1={x1} y1={y1} x2={x2} y2={y2} strokeWidth={Math.max(1, geom.size[0] * 2 * fit.scale)} />,
          });
        }
      }
      for (const [fromName, toName, radius] of model.schematic.links) {
        const from = indexOf.get(fromName);
        const to = indexOf.get(toName);
        if (from === undefined || to === undefined) continue;
        const a = pt(from);
        const b = pt(to);
        const [x1, y1] = fit.map(a);
        const [x2, y2] = fit.map(b);
        if (Math.hypot(x2 - x1, y2 - y1) < 0.5) continue;
        out.push({
          depth: (a.depth + b.depth) / 2,
          element: (
            <line
              key={`${fromName}-${toName}-${ghost}`}
              data-body={ghost ? undefined : to}
              data-selected={!ghost && spatial?.selectedBody === to}
              className={`${cls} svg-link${correction && !ghost ? " svg-correction" : ""}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              strokeWidth={Math.max(1.5, radius * 2 * fit.scale)}
              strokeLinecap="round"
            />
          ),
        });
      }
      if (!ghost) {
        for (const name of model.schematic.joint_marks) {
          const body = indexOf.get(name);
          if (body === undefined) continue;
          const p = pt(body);
          const [x, y] = fit.map(p);
          out.push({ depth: p.depth + 0.001, element: <circle key={name} data-body={body} data-selected={spatial?.selectedBody === body} className="svg-joint" cx={x} cy={y} r={Math.max(2, 0.03 * fit.scale)} /> });
        }
        if (Number.isFinite(f.grip_site_xpos[0])) {
          const site = projectPoint(f.grip_site_xpos[0], f.grip_site_xpos[1], f.grip_site_xpos[2], view);
          const [sx, sy] = fit.map(site);
          out.push({ depth: site.depth + 0.002, element: <circle key="site" className="svg-site" cx={sx} cy={sy} r={Math.max(3, 0.0075 * fit.scale)} /> });
        }
      }
    };
    if (ghostFrame) draw(ghostFrame, true);
    if (frame) draw(frame, false);
    out.sort((a, b) => a.depth - b.depth);
    return out.map((m) => m.element);
  }, [frame, ghostFrame, model, view, fit, correction, spatial?.selectedBody]);

  const map = (p: Vec3) => fit.map(projectPoint(...p, view));
  const line = (from: Vec3, to: Vec3, key: string) => {
    const a = map(from), b = map(to);
    return <line key={key} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} />;
  };
  const eef = observationPair(spatial?.row ?? null, "eef"), cube = observationPair(spatial?.row ?? null, "cube");
  const half = cubeHalfSize(model);
  const path = spatial?.options.path ? Array.from({ length: Math.max(0, spatial.count - spatial.start) }, (_, i) => map(Array.from(spatial.path.slice((i + spatial.start) * 3, (i + spatial.start) * 3 + 3)) as Vec3)) : [];
  const comparison = spatial?.target === "cube" ? cube : eef;
  const goal = spatial?.options.goal ? controllerFrame(frame) : null;
  const box = (position: Vec3, quaternion: Quat, size: Vec3, key: string) => { const vertices = boxCorners(position, quaternion, size); return [[0,1],[1,3],[3,2],[2,0],[4,5],[5,7],[7,6],[6,4],[0,4],[1,5],[2,6],[3,7]].map(([a,b], i) => line(vertices[a!]!, vertices[b!]!, `${key}-${i}`)); };

  return (
    <svg className="schematic-svg" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Schematic reconstruction drawn as SVG from the same published body frames">
      <title>SVG fallback of the schematic reconstruction</title>
      {marks}
      <g className="svg-evidence" pointerEvents="none">
        {path.length ? <g className="svg-configuration-path" data-samples={path.length}><polyline points={path.map((p) => p.join(",")).join(" ")} />{path.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="1.1" />)}</g> : null}
        {spatial?.options.observations ? <>
          {comparison.consumed && comparison.acquired ? <g className="svg-consumed">{line(comparison.consumed.position, comparison.acquired.position, "latency")}</g> : null}
          {(["consumed", "acquired"] as const).map((role) => {
            const tool = spatial.target === "eef" ? eef[role] : null, object = spatial.target === "cube" ? cube[role] : null;
            const centre = tool ? map(tool.position) : null;
            const vertices = object && half ? boxCorners(object.position, object.quaternion, half) : null;
            return <g key={role} className={`svg-${role}`} data-observation={role}>
              {tool ? axisEnds(tool, OBSERVATION_AXIS_LENGTH).map((end, i) => line(tool.position, end, `tool-${i}`)) : null}
              {tool ? observedFingerPads(model, spatial.before ?? null, spatial.row, role === "consumed" ? spatial.row?.observation ?? null : spatial.row?.captured_observation ?? null).map(p => <g key={p.name}>{box(p.pose.position, p.pose.quaternion, p.half, p.name)}</g>) : null}
              {centre ? role === "consumed" ? <path d={`M${centre[0]},${centre[1] - 6}l6,6 -6,6 -6,-6Z`} /> : <circle cx={centre[0]} cy={centre[1]} r="3" /> : null}
              {vertices ? [[0,1],[1,3],[3,2],[2,0],[4,5],[5,7],[7,6],[6,4],[0,4],[1,5],[2,6],[3,7]].map(([a,b], i) => line(vertices[a!]!, vertices[b!]!, `cube-${i}`)) : null}
            </g>;
          })}
        </> : null}
        {spatial?.pose && spatial.options.axes ? <g className="svg-body-axes">{axisEnds(spatial.pose).map((end, i) => {
          const p = map(end); return <g key={i}>{line(spatial.pose!.position, end, `${i}`)}<text x={p[0] + 4} y={p[1] - 4}>{["X", "Y", "Z"][i]}</text></g>;
        })}</g> : null}
        {spatial?.pose && spatial.selectedBody !== null ? <circle className="svg-selection-origin" cx={map(spatial.pose.position)[0]} cy={map(spatial.pose.position)[1]} r="9" /> : null}
        {goal ? <g className="svg-controller">{[...goal.ends, goal.grip].map((p, i) => line(goal.position, p, `goal-${i}`))}<circle cx={map(goal.position)[0]} cy={map(goal.position)[1]} r="4" /></g> : null}
        {spatial?.options.collision && collision && frame ? <CollisionSvg view={collision} frame={frame} project={map} /> : null}
      </g>
    </svg>
  );
}

function boxCorners(centre: Vec3, q: Quat, half: [number, number, number]): Vec3[] {
  const corners: Vec3[] = [];
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
    const r = quatRotate(q, [sx * half[0], sy * half[1], sz * half[2]]);
    corners.push([centre[0] + r[0], centre[1] + r[1], centre[2] + r[2]]);
  }
  return corners;
}
