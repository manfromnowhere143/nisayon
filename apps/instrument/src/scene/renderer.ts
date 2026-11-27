// Detailed retained geometry, posed from published body frames. Studio light
// is a display treatment. No physics or pose interpolation. Renders on demand.

import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { buildNativeSurfaces } from "./nativeSurface";
import { createCollisionLayer } from "./collisionLayer";
import type { CollisionView } from "./collisionAssets";
import { frameTiming } from "../perf/frameTiming";
import { createEvidenceLayer, type SpatialLayerState } from "./evidenceLayer";
import { pickScene, type ScenePick } from "./picking";
import { createWorkstationDisplay, contactWorkstationReading } from "./workstationDisplay";
import type { WorkstationReading } from "../model/workstation";
import { confineLabCamera } from "./labCamera";
import { projectBodyAnnotation, sameBodyAnnotation, type BodyAnnotation } from "./bodyAnnotation";
import type { VisualAsset } from "./visualAssets";
import { wallVisible } from "./room";
import { createArchitecture, type LabSetting, type LabDestination } from "./architecture";
import { loadFloorOcclusion } from "./floorOcclusion";
import { DAYLIGHT, daylightEnvironment } from "./daylight";
import { cameraEase, readRenderProfile, renderPixelRatio, RENDER_PROFILES, saveRenderProfile, type RenderProfile } from "./renderProfile";
import type { ContactView } from "../lab/contactData";
import { LAB_LAYOUT } from "./laboratoryLayout";
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
  onPartAnchor?: (anchor: BodyAnnotation | null) => void;
}

export interface SceneHandle {
  setBounds(bounds: SubjectBounds, animate?: boolean): void;
  setSetting(setting: LabSetting, destination: LabDestination): void;
  setModel(model: ModelRecord, asset: VisualAsset | null): void;
  present(): void;
  setPrimary(frame: FramePhase | null, tone: Tone): void;
  setGhost(frame: FramePhase | null): void;
  setSpatial(state: SpatialLayerState): void;
  setWorkstation(reading: WorkstationReading | null): void;
  setCollision(view: CollisionView | null): void;
  pick(x: number, y: number): ScenePick | null;
  setView(view: SceneView, animate: boolean): void;
  setGround(ground: Ground): void;
  orbit(deltaAzimuth: number, deltaElevation: number): void;
  zoom(factor: number): void;
  resetView(): void;
  resize(): void;
  simulateContextLoss(): boolean;
  setQuality(profile: RenderProfile): void;
  cameraStudy(): void;
  setContact(active: boolean, view: ContactView | null): void;
  info(): { geometries: number; textures: number; calls: number; triangles: number; frames: number; quality: RenderProfile; drawingBuffer: { width: number; height: number }; timing: ReturnType<ReturnType<typeof frameTiming>["summary"]>; workstation: { uploads: number; textureBytes: number; identity: string | null; pending: boolean } | null };
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
  let quality = readRenderProfile();
  renderer.setPixelRatio(renderPixelRatio(window.innerWidth, window.innerHeight, window.devicePixelRatio || 1, quality));
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.autoUpdate = false;
  renderer.shadowMap.needsUpdate = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.localClippingEnabled = true;
  // Reflector invokes a nested render. Accumulate all passes until the outer
  // frame completes; the default reset reports only the final pass's calls.
  renderer.info.autoReset = false;

  const scene = new THREE.Scene();
  const compact = Math.min(window.innerWidth, window.innerHeight) < 600;
  const architecture = createArchitecture({ compact, planarReflection: RENDER_PROFILES[quality].planarReflection });
  const workstation = createWorkstationDisplay(document.createElement("canvas"), compact ? 512 : 768);
  let recordingDisplay: WorkstationReading | null = null, contactDisplayActive = false;
  architecture.workstations.bindDisplay(workstation?.material ?? null);
  scene.add(architecture.root);
  let setting: LabSetting = "architecture";
  let destination: LabDestination = "lab";
  // Studio illumination is a display treatment, never a recorded sensor value.
  // Its cube texture is shared by the scene and released with the renderer.
  let environment: THREE.WebGLRenderTarget | null = null;

  const lighting = "shared-procedural";
  function lightEnvironment() {
    environment?.dispose();
    environment = null;
    scene.environment = null;
    const room = setting === "architecture" ? daylightEnvironment() : new RoomEnvironment();
    const pmrem = new THREE.PMREMGenerator(renderer);
    try {
      environment = pmrem.fromScene(room instanceof THREE.Scene ? room : room.scene, 0.06, 0.1, 100, { size: 128, position: new THREE.Vector3(0, 1, 0) });
      scene.environment = environment.texture;
      scene.environmentIntensity = setting === "architecture" ? 1.05 : .55;
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

  const camera = new THREE.PerspectiveCamera(CAMERA_FOV, 1, 0.05, 80);
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
  key.shadow.mapSize.set(2048, 2048);
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
  let annotationBodies: ReadonlySet<number> = new Set();
  let visualAsset: VisualAsset | null = null;
  let native: ReturnType<typeof buildNativeSurfaces> | null = null;
  let collision: ReturnType<typeof createCollisionLayer> | null = null;
  let collisionView: CollisionView | null = null;
  let primary: Figure | null = null;
  let ghost: Figure | null = null;
  let lastPrimaryFrame: FramePhase | null = null;
  let lastPartAnchor: BodyAnnotation | null = null;
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
  let contactCamera: { target: THREE.Vector3; spherical: THREE.Spherical; fov: number; automatic: boolean; distance: number } | null = null;
  let contactPortrait = false;
  function composeContactCamera() {
    const portrait = contactCamera !== null && camera.aspect < .85;
    if (portrait !== contactPortrait) {
      spherical.radius *= portrait ? 1.55 : 1 / 1.55;
      fittedDistance = spherical.radius; contactPortrait = portrait;
    }
    // Reserve the lower portrait region for accessible floating readings.
    // An off-axis projection moves the instrument optically, never physically.
    if (portrait) camera.setViewOffset(lastWidth,lastHeight,0,lastHeight*.24,lastWidth,lastHeight);
    else camera.clearViewOffset();
  }

  function placeCameraFromSpherical(): void {
    offset.setFromSpherical(spherical);
    camera.position.copy(TARGET).add(offset);
    if (setting === "architecture") confineLabCamera(camera.position, TARGET, spherical.phi < .5);
    camera.lookAt(TARGET);
  }

  function sphericalOf(position: THREE.Vector3): THREE.Spherical {
    return new THREE.Spherical().setFromVector3(new THREE.Vector3().subVectors(position, TARGET));
  }

  function fittedView(view: SceneView): THREE.Spherical {
    const hall = setting === "architecture" && destination === "lab";
    camera.fov = hall ? 48 : CAMERA_FOV;
    camera.updateProjectionMatrix();
    if (hall) {
      TARGET.set(-.2, 1.5, -.4);
      const eye = view === "top" ? new THREE.Vector3(.4, 8.5, 3.5)
        : view === "side" ? new THREE.Vector3(5, 2.2, 1.2)
        : new THREE.Vector3(3.1, 2.5, 7.2);
      // A portrait window enters nearer to the bay; its content stays useful.
      if (camera.aspect < .85) { TARGET.set(-.15, 1.25, 0); eye.set(3.8, 2.5, 5.8); }
      fittedDistance = eye.distanceTo(TARGET);
      return sphericalOf(eye);
    }
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
    architecture.cutaway(setting === "architecture" && spherical.phi < .5);
    if (primary && model) for (const primitive of primary.primitives) {
      const geom = model.geoms[primitive.geom]!;
      // Only the display treatment is replaced. Its recorded geometry remains
      // in the source view and in the model/collision data without alteration.
      if (geom.type === "plane") { primitive.mesh.visible = setting === "source"; continue; }
      if (!geom.name.startsWith("wall_")) continue;
      const p = primitive.mesh.position, q = primitive.mesh.quaternion;
      primitive.mesh.visible = setting === "source" && wallVisible([camera.position.x, -camera.position.z, camera.position.y], [TARGET.x, -TARGET.z, TARGET.y], [p.x, p.y, p.z], [q.w, q.x, q.y, q.z], geom.size[2]);
    }
    const started = timing.begin(animation !== null);
    try {
      if (architecture.root.visible) workstation?.flush();
      renderer.info.reset();
      renderer.render(scene, camera);
    } finally { timing.end(started); }
    frameCount += 1;
    publishPartAnchor();
    if (!firstFrameReported && primary && lastPrimaryFrame) {
      firstFrameReported = true;
      callbacks.onFirstFrame();
    }
  }
  function publishPartAnchor() {
    if (!callbacks.onPartAnchor) return;
    const body = spatial?.selectedBody, box = canvas.parentElement;
    let next: BodyAnnotation | null = null;
    if (model && lastPrimaryFrame && body != null && box?.clientWidth && box.clientHeight) {
      // Selection is committed in React's layout phase. Project it immediately,
      // before paint, rather than showing a provisional label until the next GPU draw.
      root.updateMatrixWorld(true); camera.updateMatrixWorld(true);
      const index = body * 3;
      const origin = toThreeVector(lastPrimaryFrame.xpos[index]!, lastPrimaryFrame.xpos[index + 1]!, lastPrimaryFrame.xpos[index + 2]!);
      next = projectBodyAnnotation([native?.primary.root ?? primary?.group].filter((value): value is THREE.Group => !!value),
        body, origin, camera, box.clientWidth, box.clientHeight, annotationBodies);
    }
    if (!sameBodyAnnotation(lastPartAnchor, next)) { lastPartAnchor = next; callbacks.onPartAnchor(next); }
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
    architecture.palette(ground === "paper");
    architecture.root.visible = setting === "architecture";
    const hall = setting === "architecture";
    renderer.toneMappingExposure = hall ? 1.1 : .95;
    scene.background = hall ? new THREE.Color(0x969e9f) : null;
    scene.fog = hall ? new THREE.Fog(0x969e9f, 18, 43) : null;
    hemi.color.set(p.hemiSky);
    hemi.groundColor.set(p.hemiGround);
    hemi.intensity = hall ? 1.15 : p.hemiIntensity;
    hemi.color.set(hall ? 0xd9e0eb : p.hemiSky); hemi.groundColor.set(hall ? 0x33373d : p.hemiGround);
    key.intensity = hall ? DAYLIGHT.intensity : p.keyIntensity;
    key.color.set(hall ? DAYLIGHT.colour : 0xffffff);
    key.position.copy(hall ? new THREE.Vector3(...DAYLIGHT.sun) : toThreeVector(1.6, -2.2, 3.2));
    key.target.position.copy(hall ? new THREE.Vector3(...DAYLIGHT.target) : VIEW_TARGET);
    const span = hall ? 3.2 : 1.2;
    Object.assign(key.shadow.camera, { left: -span, right: span, top: span, bottom: -span, far: hall ? 42 : 8 });
    key.shadow.camera.updateProjectionMatrix();
    key.shadow.normalBias = hall ? .003 : .004;
    fill.intensity = hall ? .4 : .35; rim.intensity = hall ? .3 : .6;
    renderer.shadowMap.needsUpdate = true;
    for (const figure of [primary, ghost]) {
      if (!figure) continue;
      const tone = figure === primary ? lastTone : "neutral";
      figure.robotMaterial.color.set(figure.ghost ? p.ghost : tone === "correction" ? p.robotCorrection : p.robot);
      figure.jointMaterial.color.set(figure.ghost ? p.ghost : p.joint);
      figure.cubeMaterial.color.set(figure.ghost ? p.ghost : p.cube);
      figure.tableMaterial.color.set(ground === "black" ? 0x30373d : 0xc4cbd4);
      figure.supportMaterial.color.set(ground === "black" ? 0x485158 : 0x818b99);
      figure.floorMaterial.color.set(setting === "architecture" ? ground === "black" ? 0x303d41 : 0x929d99 : ground === "black" ? 0x101317 : 0xd0d6df);
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
    renderer.setPixelRatio(renderPixelRatio(width, height, window.devicePixelRatio || 1, quality));
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
    if (contactCamera) { composeContactCamera(); placeCameraFromSpherical(); }
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

  function moveToView(view: SceneView, animate: boolean) {
    stopAnimation();
    const fromTarget = TARGET.clone(), from = spherical.clone();
    const to = fittedView(view), toTarget = TARGET.clone();
    if (!animate || !firstFrameReported || (fromTarget.distanceToSquared(toTarget) < 1e-12 && Math.abs(from.radius-to.radius) + Math.abs(from.phi-to.phi) + Math.abs(from.theta-to.theta) < 1e-8)) {
      spherical.copy(to); placeCameraFromSpherical(); requestRender(); return;
    }
    TARGET.copy(fromTarget);
    const start = performance.now(), duration = 420;
    const step = () => {
      if (!animation) return;
      const t = Math.min(1, (performance.now() - start) / duration), k = cameraEase(t);
      TARGET.lerpVectors(fromTarget, toTarget, k);
      spherical.radius = THREE.MathUtils.lerp(from.radius, to.radius, k);
      spherical.phi = THREE.MathUtils.lerp(from.phi, to.phi, k);
      let theta = to.theta - from.theta;
      if (theta > Math.PI) theta -= Math.PI * 2;
      if (theta < -Math.PI) theta += Math.PI * 2;
      spherical.theta = from.theta + theta * k;
      placeCameraFromSpherical(); requestRender();
      if (t < 1) animation.raf = requestAnimationFrame(step); else animation = null;
    };
    animation = { from, to, start, duration, raf: requestAnimationFrame(step) };
  }

  function onContextLost(event: Event): void {
    event.preventDefault();
    lost = true;
    lastPartAnchor = null;
    callbacks.onPartAnchor?.(null);
    timing.reset();
    // Release the old target while its context is lost. Disposing it after
    // restoration would try to delete GPU objects from the previous context.
    environment?.dispose();
    environment = null;
    scene.environment = null;
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
    workstation?.restore();
    callbacks.onContextRestored();
    requestRender();
  }

  canvas.addEventListener("webglcontextlost", onContextLost, false);
  canvas.addEventListener("webglcontextrestored", onContextRestored, false);

  applyPalette();
  resize();

  // This contact mask belongs to the revised static room. The previous warm
  // room light map is a different revision and remains unused.
  const releaseFloorOcclusion = loadFloorOcclusion(architecture, requestRender);

  return {
    setSetting(next, nextDestination) {
      if (next === setting && nextDestination === destination) return;
      const changed = setting !== next;
      setting = next; destination = nextDestination;
      if (changed) lightEnvironment();
      applyPalette();
    },
    setBounds(bounds, animate = false) {
      subjectBounds = bounds;
      automaticFraming = true;
      moveToView(selectedView, animate);
    },
    setModel(record, asset) {
      if (model === record && visualAsset === asset) return;
      renderer.shadowMap.needsUpdate = true;
      if (model !== record) {
        collision?.dispose(); collision = null; collisionView = null;
        model = record;
        annotationBodies = new Set(record.bodies.filter(body => /^(robot|gripper)/.test(body.name)).map(body => body.index));
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
      publishPartAnchor();
      requestRender();
    },
    setWorkstation(reading) {
      recordingDisplay = reading;
      if (!contactDisplayActive && workstation?.set(reading) && architecture.root.visible) requestRender();
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
      architecture.root.updateMatrixWorld(true);
      camera.updateMatrixWorld(true);
      raycaster.setFromCamera(new THREE.Vector2(x, y), camera);
      return pickScene(raycaster, [architecture.root, primary?.group, native?.primary.root].filter((group): group is THREE.Group => group !== undefined));
    },
    setView(view, animate) {
      selectedView = view;
      automaticFraming = true;
      moveToView(view, animate);
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
    setQuality(profile) {
      quality = profile; saveRenderProfile(profile);
      architecture.setReflection(RENDER_PROFILES[profile].planarReflection);
      lastWidth = 0; lastHeight = 0; resize();
    },
    setContact(active, view) {
      architecture.contact.update(view,active);
      contactDisplayActive = active;
      workstation?.set(active ? view ? contactWorkstationReading(view) : null : recordingDisplay);
      if (active && !contactCamera) {
        stopAnimation();
        contactCamera = { target: TARGET.clone(), spherical: spherical.clone(), fov: camera.fov, automatic: automaticFraming, distance: fittedDistance };
        automaticFraming = false; TARGET.set(...LAB_LAYOUT.contactInspection.target); camera.fov = 35;
        spherical.copy(sphericalOf(new THREE.Vector3(...LAB_LAYOUT.contactInspection.eye))); fittedDistance = spherical.radius;
        composeContactCamera();
        camera.updateProjectionMatrix(); placeCameraFromSpherical();
      } else if (!active && contactCamera) {
        stopAnimation(); TARGET.copy(contactCamera.target); spherical.copy(contactCamera.spherical);
        camera.fov = contactCamera.fov; fittedDistance = contactCamera.distance; automaticFraming = contactCamera.automatic;
        contactCamera = null; contactPortrait = false; camera.clearViewOffset(); camera.updateProjectionMatrix(); placeCameraFromSpherical();
      }
      renderer.shadowMap.needsUpdate = true;
      requestRender();
    },
    cameraStudy() {
      stopAnimation(); timing.clearSamples();
      const from = spherical.clone(), start = performance.now(), duration = 6000;
      const step = () => {
        if (!animation) return;
        const t = Math.min(1, (performance.now() - start) / duration);
        const arc = t <= .5 ? cameraEase(t * 2) : 1 - cameraEase((t - .5) * 2);
        spherical.theta = from.theta + .55 * arc;
        placeCameraFromSpherical(); requestRender();
        if (t < 1) animation.raf = requestAnimationFrame(step); else animation = null;
      };
      animation = { from, to: from.clone(), start, duration, raf: requestAnimationFrame(step) };
    },
    info() {
      return { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures, calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, frames: frameCount, quality, drawingBuffer: { width: canvas.width, height: canvas.height }, timing: timing.summary(), lighting, workstation: workstation?.info() ?? null };
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
      workstation?.dispose();
      releaseFloorOcclusion();
      architecture.dispose();
      collision?.dispose();
      evidence.dispose();
      if (primary) disposeFigure(primary);
      if (ghost) disposeFigure(ghost);
      renderer.dispose();
    },
  };
}
