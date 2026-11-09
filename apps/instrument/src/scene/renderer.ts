// Detailed retained geometry, posed from published body frames. Studio light
// is a display treatment. No physics or pose interpolation. Renders on demand.

import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { buildNativeSurfaces } from "./nativeSurface";
import { createCollisionLayer } from "./collisionLayer";
import type { CollisionView } from "./collisionAssets";
import { frameTiming } from "../perf/frameTiming";
import { createEvidenceLayer, type SpatialLayerState } from "./evidenceLayer";
import { pickBody } from "./picking";
import type { VisualAsset } from "./visualAssets";
import { wallVisible } from "./room";
import type { FramePhase, ModelRecord } from "../model/types";
import { MUJOCO_TO_THREE, bodyPosition, toThreeVector } from "./convert";
import { fitCamera, CAMERA_FOV, DEFAULT_BOUNDS, VIEW_EYES, VIEW_ORIGIN, type SceneView, type SubjectBounds } from "./framing";
export { CAMERA_FOV, SCENE_VIEWS, type SceneView } from "./framing";

export type Ground = "black" | "paper";
export type Tone = "neutral" | "correction";

export const VIEW_TARGET = toThreeVector(...VIEW_ORIGIN);
export const VIEW_POSITIONS: Record<SceneView, THREE.Vector3> = {
  "three-quarter": toThreeVector(...VIEW_EYES["three-quarter"]),
  side: toThreeVector(...VIEW_EYES.side),
  top: toThreeVector(...VIEW_EYES.top),
};

interface Palette {
  robot: number;
  robotCorrection: number;
  joint: number;
  cube: number;
  table: number;
  ghost: number;
  site: number;
  hemiSky: number;
  hemiGround: number;
  hemiIntensity: number;
  keyIntensity: number;
}

const PALETTES: Record<Ground, Palette> = {
  black: {
    robot: 0xd9d9d3,
    robotCorrection: 0x8fb0d6,
    joint: 0xf4f4f0,
    cube: 0xc8b18a,
    table: 0x3a3a3d,
    ghost: 0xa0a09c,
    site: 0xffffff,
    hemiSky: 0xffffff,
    hemiGround: 0x1a1a1c,
    hemiIntensity: 0.8,
    keyIntensity: 1.6,
  },
  paper: {
    robot: 0x2b2b2e,
    robotCorrection: 0x3f6087,
    joint: 0x111113,
    cube: 0xb69a6c,
    table: 0xd6d1c6,
    ghost: 0x7a7a7c,
    site: 0x111113,
    hemiSky: 0xffffff,
    hemiGround: 0x949da9,
    hemiIntensity: 0.8,
    keyIntensity: 1.3,
  },
};

interface LinkMesh {
  from: number;
  to: number;
  radius: number;
  mesh: THREE.Mesh;
  length: number;
}

interface Figure {
  group: THREE.Group;
  links: LinkMesh[];
  joints: { body: number; mesh: THREE.Mesh }[];
  primitives: { geom: number; mesh: THREE.Mesh }[];
  site: THREE.Mesh;
  robotMaterial: THREE.MeshStandardMaterial;
  jointMaterial: THREE.MeshStandardMaterial;
  cubeMaterial: THREE.MeshStandardMaterial;
  tableMaterial: THREE.MeshStandardMaterial;
  supportMaterial: THREE.MeshStandardMaterial;
  floorMaterial: THREE.MeshStandardMaterial;
  wallMaterial: THREE.MeshStandardMaterial;
  structureEdge: THREE.LineBasicMaterial;
  siteMaterial: THREE.MeshBasicMaterial;
  edgeMaterial: THREE.LineBasicMaterial;
  ghost: boolean;
}

export interface SceneCallbacks {
  onContextLost: () => void;
  onContextRestored: () => void;
  onFirstFrame: () => void;
}

export interface SceneHandle {
  setBounds(bounds: SubjectBounds): void;
  setModel(model: ModelRecord, asset: VisualAsset | null): void;
  present(): void;
  setPrimary(frame: FramePhase | null, tone: Tone): void;
  setGhost(frame: FramePhase | null): void;
  setSpatial(state: SpatialLayerState): void;
  setCollision(view: CollisionView | null): void;
  pick(x: number, y: number): number | null;
  setView(view: SceneView, animate: boolean): void;
  setGround(ground: Ground): void;
  orbit(deltaAzimuth: number, deltaElevation: number): void;
  zoom(factor: number): void;
  resetView(): void;
  resize(): void;
  simulateContextLoss(): boolean;
  info(): { geometries: number; textures: number; calls: number; frames: number; timing: ReturnType<ReturnType<typeof frameTiming>["summary"]> };
  dispose(): void;
}

const Y_AXIS = new THREE.Vector3(0, 1, 0);
const Z_AXIS = new THREE.Vector3(0, 0, 1);

export function createSceneRenderer(canvas: HTMLCanvasElement, initialGround: Ground, callbacks: SceneCallbacks): SceneHandle | null {
  let renderer: THREE.WebGLRenderer;
  try {
    const context = canvas.getContext("webgl2", { antialias: true, alpha: true, powerPreference: "low-power" });
    if (!context) return null;
    renderer = new THREE.WebGLRenderer({ canvas, context, antialias: true, alpha: true });
  } catch { return null; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.autoUpdate = false;
  renderer.shadowMap.needsUpdate = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;

  const scene = new THREE.Scene();
  // Studio illumination is a display treatment, never a recorded sensor value.
  // Its cube texture is shared by the scene and released with the renderer.
  let environment: THREE.WebGLRenderTarget | null = null;
  function lightEnvironment() {
    environment?.dispose();
    environment = null;
    scene.environment = null;
    const room = new RoomEnvironment();
    const pmrem = new THREE.PMREMGenerator(renderer);
    try {
      environment = pmrem.fromScene(room, 0.04, 0.1, 100, { size: 128 });
      scene.environment = environment.texture;
      scene.environmentIntensity = 0.55;
    } catch { /* Direct lighting remains a complete rendering path. */ }
    finally { room.dispose(); pmrem.dispose(); }
  }
  lightEnvironment();

  const root = new THREE.Group();
  root.quaternion.copy(MUJOCO_TO_THREE);
  scene.add(root);
  const evidence = createEvidenceLayer();
  root.add(evidence.root);
  const raycaster = new THREE.Raycaster();
  let spatial: SpatialLayerState | null = null;

  const camera = new THREE.PerspectiveCamera(CAMERA_FOV, 1, 0.05, 30);
  const TARGET = VIEW_TARGET.clone();
  let subjectBounds = DEFAULT_BOUNDS;
  let selectedView: SceneView = "three-quarter";
  let automaticFraming = true;
  let fittedDistance = 3;
  const hemi = new THREE.HemisphereLight(0xffffff, 0x222222, 1);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xffffff, 1.4);
  key.position.copy(toThreeVector(1.6, -2.2, 3.2));
  key.target.position.copy(TARGET);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.left = -1.2;
  key.shadow.camera.right = 1.2;
  key.shadow.camera.top = 1.2;
  key.shadow.camera.bottom = -1.2;
  key.shadow.camera.near = 0.1;
  key.shadow.camera.far = 8;
  key.shadow.normalBias = 0.004;
  key.shadow.bias = -0.0001;
  scene.add(key, key.target);
  const fill = new THREE.DirectionalLight(0xffffff, 0.35);
  fill.position.copy(toThreeVector(-2.5, 1.5, 1.2));
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.6);
  rim.position.copy(toThreeVector(-1.5, 1.4, 2.4));
  scene.add(rim);

  let ground: Ground = initialGround;
  let model: ModelRecord | null = null;
  let visualAsset: VisualAsset | null = null;
  let native: ReturnType<typeof buildNativeSurfaces> | null = null;
  let collision: ReturnType<typeof createCollisionLayer> | null = null;
  let collisionView: CollisionView | null = null;
  let primary: Figure | null = null;
  let ghost: Figure | null = null;
  let lastPrimaryFrame: FramePhase | null = null;
  let lastGhostFrame: FramePhase | null = null;
  let lastTone: Tone = "neutral";
  let frameCount = 0;
  let firstFrameReported = false;
  let disposed = false;
  let lost = false;

  // Camera state in spherical coordinates around a fixed target.
  const spherical = new THREE.Spherical();
  const offset = new THREE.Vector3();
  let animation: { from: THREE.Spherical; to: THREE.Spherical; start: number; duration: number; raf: number } | null = null;

  function placeCameraFromSpherical(): void {
    offset.setFromSpherical(spherical);
    camera.position.copy(TARGET).add(offset);
    camera.lookAt(TARGET);
  }

  function sphericalOf(position: THREE.Vector3): THREE.Spherical {
    return new THREE.Spherical().setFromVector3(new THREE.Vector3().subVectors(position, TARGET));
  }

  function fittedView(view: SceneView): THREE.Spherical {
    const fit = fitCamera(view, camera.aspect, subjectBounds);
    TARGET.copy(toThreeVector(...fit.target));
    fittedDistance = fit.distance;
    const result = sphericalOf(toThreeVector(...fit.position));
    result.radius *= 1.06;
    return result;
  }

  spherical.copy(fittedView("three-quarter"));
  placeCameraFromSpherical();

  let renderRequested = 0;
  const timing = frameTiming(renderer.getContext() as WebGL2RenderingContext);
  function renderFrame(): void {
    if (disposed || lost || !canvas.parentElement?.clientWidth || !canvas.parentElement.clientHeight) return;
    if (primary && model) for (const primitive of primary.primitives) {
      const geom = model.geoms[primitive.geom]!;
      if (!geom.name.startsWith("wall_")) continue;
      const p = primitive.mesh.position, q = primitive.mesh.quaternion;
      primitive.mesh.visible = wallVisible([camera.position.x, -camera.position.z, camera.position.y], [TARGET.x, -TARGET.z, TARGET.y], [p.x, p.y, p.z], [q.w, q.x, q.y, q.z], geom.size[2]);
    }
    const started = timing.begin();
    try { renderer.render(scene, camera); } finally { timing.end(started); }
    frameCount += 1;
    if (!firstFrameReported && primary && lastPrimaryFrame) {
      firstFrameReported = true;
      callbacks.onFirstFrame();
    }
  }
  function requestRender(): void {
    if (disposed || lost || renderRequested || !canvas.parentElement?.clientWidth || !canvas.parentElement.clientHeight) return;
    renderRequested = requestAnimationFrame(() => {
      renderRequested = 0;
      renderFrame();
    });
  }

  function applyPalette(): void {
    const p = PALETTES[ground];
    hemi.color.set(p.hemiSky);
    hemi.groundColor.set(p.hemiGround);
    hemi.intensity = p.hemiIntensity;
    key.intensity = p.keyIntensity;
    for (const figure of [primary, ghost]) {
      if (!figure) continue;
      const tone = figure === primary ? lastTone : "neutral";
      figure.robotMaterial.color.set(figure.ghost ? p.ghost : tone === "correction" ? p.robotCorrection : p.robot);
      figure.jointMaterial.color.set(figure.ghost ? p.ghost : p.joint);
      figure.cubeMaterial.color.set(figure.ghost ? p.ghost : p.cube);
      figure.tableMaterial.color.set(ground === "black" ? 0x30373d : 0xc4cbd4);
      figure.supportMaterial.color.set(ground === "black" ? 0x485158 : 0x818b99);
      figure.floorMaterial.color.set(ground === "black" ? 0x101317 : 0xd0d6df);
      figure.wallMaterial.color.set(ground === "black" ? 0x0b0d10 : 0xe3e7ee);
      figure.structureEdge.color.set(ground === "black" ? 0x8d999f : 0x636c6e);
      figure.siteMaterial.color.set(p.site);
      figure.edgeMaterial.color.set(ground === "black" ? 0xf4ead5 : 0x453522);
    }
    native?.primary.palette(ground, lastTone === "correction");
    native?.ghost.palette(ground, false);
    collision?.palette(ground);
    updateSpatial();
    requestRender();
  }

  function updateSpatial(): void {
    if (!spatial || !model) { evidence.root.visible = false; return; }
    evidence.root.visible = true;
    evidence.update(model, spatial.row, spatial.pose, spatial.path, spatial.count, spatial.options, spatial.selectedBody !== null, ground === "paper", spatial.target, spatial.start, lastPrimaryFrame, spatial.before ?? null);
    native?.primary.select(spatial.selectedBody);
  }

  function buildFigure(record: ModelRecord, isGhost: boolean): Figure {
    const p = PALETTES[ground];
    const group = new THREE.Group();
    group.userData.recordingOverlay = isGhost;
    const common = { roughness: 0.42, metalness: 0.16 };
    const robotMaterial = new THREE.MeshStandardMaterial({ color: p.robot, ...common });
    const jointMaterial = new THREE.MeshStandardMaterial({ color: p.joint, roughness: 0.58, metalness: 0.08 });
    const cubeMaterial = new THREE.MeshStandardMaterial({ color: p.cube, roughness: 0.36, metalness: 0.08 });
    const tableMaterial = new THREE.MeshStandardMaterial({ color: p.table, roughness: 0.42, metalness: 0.3 });
    const supportMaterial = new THREE.MeshStandardMaterial({ roughness: 0.29, metalness: 0.7 });
    const floorMaterial = new THREE.MeshStandardMaterial({ roughness: 0.58, metalness: 0.12 });
    const wallMaterial = new THREE.MeshStandardMaterial({ roughness: 0.96, metalness: 0 });
    const structureEdge = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.18 });
    const siteMaterial = new THREE.MeshBasicMaterial({ color: p.site });
    const edgeMaterial = new THREE.LineBasicMaterial({ color: ground === "black" ? 0xf4ead5 : 0x453522, transparent: true, opacity: isGhost ? 0.35 : 0.22 });
    if (isGhost) {
      for (const m of [robotMaterial, jointMaterial, cubeMaterial]) {
        m.transparent = true;
        m.opacity = 0.34;
        m.depthWrite = false;
      }
      robotMaterial.color.set(p.ghost);
      jointMaterial.color.set(p.ghost);
      cubeMaterial.color.set(p.ghost);
    }
    const indexOf = new Map(record.bodies.map((b) => [b.name, b.index]));
    const links: LinkMesh[] = [];
    for (const [fromName, toName, radius] of record.schematic.links) {
      const from = indexOf.get(fromName);
      const to = indexOf.get(toName);
      if (from === undefined || to === undefined) continue;
      const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(radius, 1, 8, 24), robotMaterial);
      mesh.castShadow = !isGhost;
      mesh.receiveShadow = !isGhost;
      mesh.visible = false;
      mesh.userData.body = to;
      group.add(mesh);
      links.push({ from, to, radius, mesh, length: 1 });
    }
    const joints: Figure["joints"] = [];
    if (!isGhost) {
      for (const name of record.schematic.joint_marks) {
        const body = indexOf.get(name);
        if (body === undefined) continue;
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 12), jointMaterial);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.userData.body = body;
        group.add(mesh);
        joints.push({ body, mesh });
      }
    }
    const primitives: Figure["primitives"] = [];
    const bodyName = new Map(record.bodies.map((b) => [b.index, b.name]));
    const environmentGeoms = record.geoms.filter((g) => g.type === "plane" || g.name.startsWith("wall_")).map((g) => g.index);
    for (const index of new Set([...record.schematic.drawable_geoms, ...environmentGeoms])) {
      const geom = record.geoms[index];
      if (!geom) continue;
      const owner = bodyName.get(geom.body) ?? "";
      const isCube = owner.startsWith("cube");
      const isRobot = owner.startsWith("robot0_") || owner.startsWith("gripper0_");
      if (isGhost && !isCube) continue;
      let geometry: THREE.BufferGeometry;
      if (geom.type === "plane") {
        geometry = new THREE.PlaneGeometry(geom.size[0] * 2, geom.size[1] * 2);
      } else if (geom.type === "box") {
        geometry = new THREE.BoxGeometry(geom.size[0] * 2, geom.size[1] * 2, geom.size[2] * 2);
      } else if (geom.type === "cylinder") {
        geometry = new THREE.CylinderGeometry(geom.size[0], geom.size[0], geom.size[1] * 2, 20);
        // MuJoCo cylinders run along their z axis; three.js cylinders along y.
        geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(Y_AXIS, Z_AXIS));
      } else {
        continue;
      }
      const mesh = new THREE.Mesh(geometry, isCube ? cubeMaterial : isRobot ? robotMaterial : geom.name === "floor" ? floorMaterial : geom.name.startsWith("wall_") ? wallMaterial : geom.name.includes("leg") ? supportMaterial : tableMaterial);
      mesh.userData.body = geom.body;
      mesh.castShadow = !isGhost && !geom.name.startsWith("wall_") && geom.name !== "floor";
      mesh.receiveShadow = !isGhost;
      if (geom.name === "table_visual") mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), structureEdge));
      if (isCube) mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 30), edgeMaterial));
      group.add(mesh);
      primitives.push({ geom: index, mesh });
    }
    const site = new THREE.Mesh(new THREE.SphereGeometry(0.0075, 12, 8), siteMaterial);
    site.userData.body = indexOf.get("gripper0_eef");
    site.visible = !isGhost;
    group.add(site);
    root.add(group);
    return { group, links, joints, primitives, site, robotMaterial, jointMaterial, cubeMaterial, tableMaterial, siteMaterial, edgeMaterial, supportMaterial, floorMaterial, wallMaterial, structureEdge, ghost: isGhost };
  }

  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const dir = new THREE.Vector3();
  const q = new THREE.Quaternion();

  function poseFigure(figure: Figure, frame: FramePhase | null): void {
    if (!frame) {
      figure.group.visible = false;
      return;
    }
    figure.group.visible = true;
    for (const link of figure.links) {
      if (native) { link.mesh.visible = false; continue; }
      bodyPosition(frame.xpos, link.from, a);
      bodyPosition(frame.xpos, link.to, b);
      dir.subVectors(b, a);
      const length = dir.length();
      if (length < 0.002) {
        link.mesh.visible = false;
        continue;
      }
      link.mesh.visible = true;
      if (Math.abs(length - link.length) > 1e-6) {
        link.mesh.geometry.dispose();
        link.mesh.geometry = new THREE.CapsuleGeometry(link.radius, length, 8, 24);
        link.length = length;
      }
      link.mesh.position.copy(a).addScaledVector(dir, 0.5);
      dir.divideScalar(length);
      link.mesh.quaternion.copy(q.setFromUnitVectors(Y_AXIS, dir));
    }
    for (const joint of figure.joints) {
      joint.mesh.visible = !native;
      bodyPosition(frame.xpos, joint.body, joint.mesh.position);
    }
    for (const primitive of figure.primitives) {
      const owner = model?.bodies[model.geoms[primitive.geom]!.body]?.name ?? "";
      const detailedMount = visualAsset?.parts.some((part) => model?.bodies[part.body]?.name.startsWith("mount0_"));
      if (native && (/^(robot0_|gripper0_)/.test(owner) || (detailedMount && owner.startsWith("mount0_")))) { primitive.mesh.visible = false; continue; }
      const o = primitive.geom * 7;
      if (o + 6 >= frame.geoms.length) {
        primitive.mesh.visible = false;
        continue;
      }
      primitive.mesh.visible = true;
      primitive.mesh.position.set(frame.geoms[o] as number, frame.geoms[o + 1] as number, frame.geoms[o + 2] as number);
      primitive.mesh.quaternion.set(frame.geoms[o + 4] as number, frame.geoms[o + 5] as number, frame.geoms[o + 6] as number, frame.geoms[o + 3] as number);
    }
    figure.site.visible = !native && !figure.ghost && Number.isFinite(frame.grip_site_xpos[0]);
    figure.site.position.set(frame.grip_site_xpos[0], frame.grip_site_xpos[1], frame.grip_site_xpos[2]);
  }

  function disposeFigure(figure: Figure): void {
    root.remove(figure.group);
    figure.group.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) object.geometry.dispose();
    });
    for (const m of [figure.robotMaterial, figure.jointMaterial, figure.cubeMaterial, figure.tableMaterial, figure.siteMaterial, figure.edgeMaterial, figure.supportMaterial, figure.floorMaterial, figure.wallMaterial, figure.structureEdge]) m.dispose();
  }

  let lastWidth = 0, lastHeight = 0;
  function resize(): void {
    const parent = canvas.parentElement;
    if (!parent) return;
    // A hidden mobile pane retains its camera and render target.
    if (parent.clientWidth <= 0 || parent.clientHeight <= 0) return;
    const width = Math.floor(parent.clientWidth);
    const height = Math.floor(parent.clientHeight);
    if (width === lastWidth && height === lastHeight) { requestRender(); return; }
    lastWidth = width; lastHeight = height;
    // Resolve contact and joint shadows on a large stage without adding a
    // second renderer, postprocessing pass or idle animation. Compact stages
    // keep the original shadow budget. Release the old target on transitions.
    const shadowSize = width >= 900 && height >= 500 && renderer.capabilities.maxTextureSize >= 2048 ? 2048 : 1024;
    if (key.shadow.mapSize.x !== shadowSize) {
      key.shadow.map?.dispose();
      key.shadow.map = null;
      key.shadow.mapSize.set(shadowSize, shadowSize);
      renderer.shadowMap.needsUpdate = true;
    }
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (automaticFraming) {
      stopAnimation();
      spherical.copy(fittedView(selectedView));
      placeCameraFromSpherical();
    }
    requestRender();
  }

  function stopAnimation(): void {
    if (animation) {
      cancelAnimationFrame(animation.raf);
      animation = null;
    }
  }

  function easeOut(t: number): number {
    return 1 - Math.pow(1 - t, 3);
  }

  function onContextLost(event: Event): void {
    event.preventDefault();
    lost = true;
    timing.reset();
    if (renderRequested) {
      cancelAnimationFrame(renderRequested);
      renderRequested = 0;
    }
    callbacks.onContextLost();
  }

  function onContextRestored(): void {
    lost = false;
    timing.restore();
    renderer.shadowMap.needsUpdate = true;
    lightEnvironment();
    callbacks.onContextRestored();
    requestRender();
  }

  canvas.addEventListener("webglcontextlost", onContextLost, false);
  canvas.addEventListener("webglcontextrestored", onContextRestored, false);

  applyPalette();
  resize();

  return {
    setBounds(bounds) {
      subjectBounds = bounds;
      automaticFraming = true;
      stopAnimation();
      spherical.copy(fittedView(selectedView));
      placeCameraFromSpherical();
      requestRender();
    },
    setModel(record, asset) {
      if (model === record && visualAsset === asset) return;
      renderer.shadowMap.needsUpdate = true;
      if (model !== record) {
        collision?.dispose(); collision = null; collisionView = null;
        model = record;
        if (primary) disposeFigure(primary);
        if (ghost) disposeFigure(ghost);
        primary = buildFigure(record, false);
        ghost = buildFigure(record, true);
      }
      // The caller qualifies the asset against each new model. The shared
      // source geometry survives case/run changes; only body transforms move.
      if (asset !== visualAsset) {
        native?.dispose();
        native = null;
        visualAsset = asset;
        if (asset) {
          native = buildNativeSurfaces(asset);
          root.add(native.primary.root, native.ghost.root);
          native.primary.pose(lastPrimaryFrame);
          native.ghost.pose(lastGhostFrame);
        }
      }
      if (primary) poseFigure(primary, lastPrimaryFrame);
      if (ghost) poseFigure(ghost, lastGhostFrame);
      applyPalette();
    },
    present() {
      // Commit a sample together with its DOM clock, before browser paint.
      // Cancel the pending draw rather than enqueue another frame of latency.
      if (renderRequested) cancelAnimationFrame(renderRequested);
      renderRequested = 0;
      renderFrame();
    },
    setPrimary(frame, tone) {
      lastPrimaryFrame = frame;
      renderer.shadowMap.needsUpdate = true;
      if (tone !== lastTone) {
        lastTone = tone;
        applyPalette();
      }
      if (primary) poseFigure(primary, frame);
      native?.primary.pose(frame);
      collision?.pose(frame, !!spatial?.options.collision);
      requestRender();
    },
    setGhost(frame) {
      lastGhostFrame = frame;
      if (ghost) poseFigure(ghost, frame);
      native?.ghost.pose(frame);
      requestRender();
    },
    setSpatial(state) {
      spatial = state;
      updateSpatial();
      collision?.pose(lastPrimaryFrame, !!state.options.collision);
      requestRender();
    },
    setCollision(view) {
      if (view === collisionView) return;
      collision?.dispose(); collision = null; collisionView = view;
      if (view) { collision = createCollisionLayer(view); root.add(collision.root); collision.palette(ground); collision.pose(lastPrimaryFrame, !!spatial?.options.collision); }
      requestRender();
    },
    pick(x, y) {
      if (!lastPrimaryFrame || disposed || lost) return null;
      root.updateMatrixWorld(true);
      camera.updateMatrixWorld(true);
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      return pickBody(raycaster, [primary?.group, native?.primary.root].filter((group): group is THREE.Group => group !== undefined));
    },
    setView(view, animate) {
      stopAnimation();
      selectedView = view;
      automaticFraming = true;
      const to = fittedView(view);
      if (!animate) {
        spherical.copy(to);
        placeCameraFromSpherical();
        requestRender();
        return;
      }
      const from = spherical.clone();
      const start = performance.now();
      const duration = 320;
      const step = (): void => {
        if (!animation) return;
        const t = Math.min(1, (performance.now() - start) / duration);
        const k = easeOut(t);
        spherical.radius = from.radius + (to.radius - from.radius) * k;
        spherical.phi = from.phi + (to.phi - from.phi) * k;
        let dTheta = to.theta - from.theta;
        if (dTheta > Math.PI) dTheta -= Math.PI * 2;
        if (dTheta < -Math.PI) dTheta += Math.PI * 2;
        spherical.theta = from.theta + dTheta * k;
        placeCameraFromSpherical();
        requestRender();
        if (t < 1) animation!.raf = requestAnimationFrame(step);
        else animation = null;
      };
      animation = { from, to, start, duration, raf: requestAnimationFrame(step) };
    },
    setGround(next) {
      if (next === ground) return;
      ground = next;
      applyPalette();
    },
    orbit(deltaAzimuth, deltaElevation) {
      stopAnimation();
      automaticFraming = false;
      spherical.theta -= deltaAzimuth;
      spherical.phi = Math.min(Math.PI * 0.49, Math.max(0.12, spherical.phi - deltaElevation));
      placeCameraFromSpherical();
      requestRender();
    },
    zoom(factor) {
      stopAnimation();
      automaticFraming = false;
      spherical.radius = Math.min(fittedDistance * 1.45, Math.max(Math.max(0.22, fittedDistance * 0.38), spherical.radius * factor));
      placeCameraFromSpherical();
      requestRender();
    },
    resetView() {
      automaticFraming = true;
      stopAnimation();
      spherical.copy(fittedView(selectedView));
      placeCameraFromSpherical();
      requestRender();
    },
    resize,
    simulateContextLoss() {
      const extension = renderer.getContext().getExtension("WEBGL_lose_context");
      if (!extension) return false;
      extension.loseContext();
      window.setTimeout(() => extension.restoreContext(), 1500);
      return true;
    },
    info() {
      return { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures, calls: renderer.info.render.calls, frames: frameCount, timing: timing.summary() };
    },
    dispose() {
      disposed = true;
      timing.dispose();
      key.shadow.map?.dispose();
      environment?.dispose();
      stopAnimation();
      if (renderRequested) cancelAnimationFrame(renderRequested);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      canvas.removeEventListener("webglcontextrestored", onContextRestored);
      native?.dispose();
      collision?.dispose();
      evidence.dispose();
      if (primary) disposeFigure(primary);
      if (ghost) disposeFigure(ghost);
      renderer.dispose();
    },
  };
}
