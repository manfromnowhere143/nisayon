import * as THREE from "three";
import { AXIS_LENGTH, OBSERVATION_AXIS_LENGTH, cubeHalfSize, observationPair, type ObservationTarget, type SpatialOptions, type SpatialPose } from "../model/spatial";
import type { FramePhase, ModelRecord, SampleRow } from "../model/types";
import { controllerFrame, observedFingerPads } from "../model/physicalDisplay";

export interface SpatialLayerState {
  row: SampleRow | null;
  pose: SpatialPose | null;
  path: Float32Array;
  count: number;
  start: number;
  target: ObservationTarget;
  options: SpatialOptions;
  selectedBody: number | null;
  before?: FramePhase | null;
}

// Catalog discovery recreates props while the selected recording stays pinned.
// Compare the retained values, not the identity of a React wrapper: otherwise
// a metadata refresh cancels a paused still every 15 seconds.
export function sameSpatialLayer(a: SpatialLayerState | null, b: SpatialLayerState): boolean {
  if (!a) return false;
  const poseEqual = a.pose === b.pose || (a.pose !== null && b.pose !== null &&
    a.pose.position.every((n, i) => n === b.pose!.position[i]) && a.pose.quaternion.every((n, i) => n === b.pose!.quaternion[i]));
  return poseEqual && a.row === b.row && a.before === b.before && a.path === b.path &&
    a.count === b.count && a.start === b.start && a.target === b.target && a.selectedBody === b.selectedBody &&
    a.options.observations === b.options.observations && a.options.path === b.options.path &&
    a.options.axes === b.options.axes && !!a.options.goal === !!b.options.goal && !!a.options.collision === !!b.options.collision;
}

const CONSUMED = 0xb7bdc3, ACQUIRED = 0xf2f3ef;

// This is a drawing of observations and recorded configurations, not another
// simulated robot. All geometry is allocated once; a seek updates transforms.
export function createEvidenceLayer() {
  const root = new THREE.Group();
  root.name = "Recorded spatial evidence";
  const ownedGeometry = new Set<THREE.BufferGeometry>();
  const ownedMaterial = new Set<THREE.Material>();
  const ownGeometry = <T extends THREE.BufferGeometry>(value: T): T => { ownedGeometry.add(value); return value; };
  const ownMaterial = <T extends THREE.Material>(value: T): T => { ownedMaterial.add(value); return value; };
  const lineMaterial = (color: number, dashed = false) => ownMaterial(dashed
    ? new THREE.LineDashedMaterial({ color, dashSize: 0.005, gapSize: 0.003, transparent: true, opacity: 0.9, depthTest: false, depthWrite: false })
    : new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.88, depthTest: false, depthWrite: false }));
  const observations = new THREE.Group();
  root.add(observations);
  function marker(color: number, consumed: boolean) {
    const group = new THREE.Group(), tool = new THREE.Group();
    const material = lineMaterial(color, consumed);
    const frameGeometry = ownGeometry(new THREE.BufferGeometry());
    frameGeometry.setAttribute("position", new THREE.Float32BufferAttribute([0, 0, 0, OBSERVATION_AXIS_LENGTH, 0, 0, 0, 0, 0, 0, OBSERVATION_AXIS_LENGTH, 0, 0, 0, 0, 0, 0, OBSERVATION_AXIS_LENGTH], 3));
    const axes = new THREE.LineSegments(frameGeometry, material); axes.computeLineDistances(); tool.add(axes);
    const octahedron = new THREE.OctahedronGeometry(0.009);
    const dot = consumed
      ? new THREE.LineSegments(ownGeometry(new THREE.EdgesGeometry(octahedron)), material)
      : new THREE.Mesh(ownGeometry(new THREE.SphereGeometry(0.004, 12, 8)), ownMaterial(new THREE.MeshBasicMaterial({ color, depthTest: false, depthWrite: false })));
    octahedron.dispose();
    if (dot instanceof THREE.LineSegments) dot.computeLineDistances();
    tool.add(dot); group.add(tool);
    const box = new THREE.BoxGeometry(2, 2, 2);
    const cube = new THREE.LineSegments(ownGeometry(new THREE.EdgesGeometry(box)), material); box.dispose();
    cube.computeLineDistances(); group.add(cube); observations.add(group);
    const fingers = [0, 1].map(() => { const pad = new THREE.LineSegments(cube.geometry, material); pad.computeLineDistances(); group.add(pad); return pad; });
    return { group, tool, cube, material, fingers };
  }
  const consumed = marker(CONSUMED, true), acquired = marker(ACQUIRED, false);
  const connectorGeometry = ownGeometry(new THREE.BufferGeometry());
  connectorGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3).setUsage(THREE.DynamicDrawUsage));
  connectorGeometry.setAttribute("lineDistance", new THREE.BufferAttribute(new Float32Array(2), 1).setUsage(THREE.DynamicDrawUsage));
  const connector = new THREE.Line(connectorGeometry, lineMaterial(CONSUMED, true));
  observations.add(connector);
  const axes = new THREE.AxesHelper(AXIS_LENGTH);
  ownGeometry(axes.geometry);
  for (const m of Array.isArray(axes.material) ? axes.material : [axes.material]) { ownMaterial(m); m.depthTest = false; m.depthWrite = false; }
  root.add(axes);
  const selectionMaterial = lineMaterial(0xffffff);
  const ringGeometry = new THREE.RingGeometry(0.012, 0.014, 40);
  // Three orthogonal contours mark the body origin without pretending to bound
  // a collision shape. Their size is a display convention, never a measurement.
  const selection = new THREE.Group();
  const ringEdges = ownGeometry(new THREE.EdgesGeometry(ringGeometry)); ringGeometry.dispose();
  for (let i = 0; i < 3; i++) { const ring = new THREE.LineSegments(ringEdges, selectionMaterial); if (i === 1) ring.rotation.x = Math.PI / 2; if (i === 2) ring.rotation.y = Math.PI / 2; selection.add(ring); }
  root.add(selection);
  const goalGeometry = ownGeometry(new THREE.BufferGeometry());
  goalGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(24), 3).setUsage(THREE.DynamicDrawUsage));
  goalGeometry.setAttribute("lineDistance", new THREE.BufferAttribute(new Float32Array(8), 1).setUsage(THREE.DynamicDrawUsage));
  const goalMaterial = lineMaterial(0xffffff, true);
  const goal = new THREE.LineSegments(goalGeometry, goalMaterial); root.add(goal);
  const pathGeometry = ownGeometry(new THREE.BufferGeometry());
  pathGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(), 3));
  const pathMaterial = lineMaterial(0xb8c1c9);
  const trail = new THREE.Line(pathGeometry, pathMaterial);
  const samples = new THREE.Points(pathGeometry, ownMaterial(new THREE.PointsMaterial({ color: 0xb8c1c9, size: 2.3, sizeAttenuation: false, depthTest: false, depthWrite: false })));
  root.add(trail, samples);
  root.traverse((object) => { object.renderOrder = 5; });
  let lastPath: Float32Array | null = null;

  function place(object: THREE.Object3D, pose: SpatialPose | null) {
    object.visible = pose !== null;
    if (!pose) return;
    object.position.set(...pose.position);
    object.quaternion.set(pose.quaternion[1], pose.quaternion[2], pose.quaternion[3], pose.quaternion[0]);
  }
  return {
    root,
    update(model: ModelRecord, row: SampleRow | null, pose: SpatialPose | null, path: Float32Array, count: number, options: SpatialOptions, selected: boolean, paper: boolean, target: ObservationTarget = "eef", start = 0, frame: FramePhase | null = null, before: FramePhase | null = null) {
      observations.visible = options.observations && row !== null;
      const eef = observationPair(row, "eef"), cube = observationPair(row, "cube"), half = cubeHalfSize(model);
      for (const [marker, toolPose, cubePose, observation] of [[consumed, eef.consumed, cube.consumed, row?.observation], [acquired, eef.acquired, cube.acquired, row?.captured_observation]] as const) {
        place(marker.tool, target === "eef" ? toolPose : null); place(marker.cube, half && target === "cube" ? cubePose : null);
        if (half) marker.cube.scale.set(...half);
        const pads = target === "eef" ? observedFingerPads(model, before, row, observation ?? null) : [];
        marker.fingers.forEach((mesh, i) => { const pad = pads[i]; place(mesh, pad?.pose ?? null); if (pad) mesh.scale.set(...pad.half); });
      }
      consumed.material.color.set(paper ? 0x677078 : CONSUMED);
      acquired.material.color.set(paper ? 0x222d34 : ACQUIRED);
      acquired.tool.traverse((object) => { if (object instanceof THREE.Mesh) (object.material as THREE.MeshBasicMaterial).color.copy(acquired.material.color); });
      connector.material.color.copy(consumed.material.color);
      const pair = target === "eef" ? eef : cube;
      connector.visible = pair.consumed !== null && pair.acquired !== null;
      if (pair.consumed && pair.acquired) {
        const buffer = connectorGeometry.getAttribute("position") as THREE.BufferAttribute;
        buffer.setXYZ(0, ...pair.consumed.position); buffer.setXYZ(1, ...pair.acquired.position); buffer.needsUpdate = true;
        const distances = connectorGeometry.getAttribute("lineDistance") as THREE.BufferAttribute;
        distances.setX(1, pair.distance!); distances.needsUpdate = true;
        connectorGeometry.computeBoundingSphere();
      }
      place(axes, options.axes ? pose : null);
      place(selection, selected ? pose : null);
      selectionMaterial.color.set(paper ? 0x17242b : 0xffffff);
      if (lastPath !== path) {
        // Release the old uploaded buffer before replacing the single attribute.
        pathGeometry.dispose();
        pathGeometry.setAttribute("position", new THREE.BufferAttribute(path, 3));
        pathGeometry.computeBoundingSphere(); lastPath = path;
      }
      pathGeometry.setDrawRange(start, Math.max(0, count - start));
      trail.visible = samples.visible = options.path && pose !== null && count > 0;
      pathMaterial.color.set(paper ? 0x485a67 : 0xb8c1c9);
      samples.material.color.copy(pathMaterial.color);
      const targetFrame = options.goal ? controllerFrame(frame) : null;
      goal.visible = targetFrame !== null;
      if (targetFrame) {
        const positions = goalGeometry.getAttribute("position") as THREE.BufferAttribute;
        const distances = goalGeometry.getAttribute("lineDistance") as THREE.BufferAttribute;
        [...targetFrame.ends, targetFrame.grip].forEach((end, i) => { positions.setXYZ(i * 2, ...targetFrame.position); positions.setXYZ(i * 2 + 1, ...end); distances.setX(i * 2, 0); distances.setX(i * 2 + 1, Math.hypot(...end.map((v, axis) => v - targetFrame.position[axis]!))); });
        positions.needsUpdate = distances.needsUpdate = true; goalGeometry.setDrawRange(0, (targetFrame.ends.length + 1) * 2); goalGeometry.computeBoundingSphere();
        goalMaterial.color.set(paper ? 0x253138 : 0xf2f3ef);
      }
    },
    dispose() { root.removeFromParent(); for (const geometry of ownedGeometry) geometry.dispose(); for (const material of ownedMaterial) material.dispose(); },
  };
}
