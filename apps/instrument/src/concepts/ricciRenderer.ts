import { bindOrbitGestures } from "../scene/orbitGestures";
import {
  frameRicciCamera,
  ricciFramePoint,
  type RicciFrame,
} from "./ricciViewport";
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import {
  createRicci,
  SoleReveal,
  type RicciPick,
  type RicciSide,
} from "./ricciGeometry";
import { createArchitecture } from "../scene/architecture";
import { loadFloorOcclusion } from "../scene/floorOcclusion";
import { DAYLIGHT, daylightEnvironment } from "../scene/daylight";
import { createCarryPreview, type TraceCase } from "./ricciTrace";
import type { RicciPartId } from "./ricciCatalog";
import type { AnnotationAnchor, ScreenRect } from "./annotationPlacement";
import { createRicciWorkstation, ricciDeskReading } from "./ricciWorkstation";

export type RicciView = "front" | "oblique" | "rear";
export interface RicciAnchor extends AnnotationAnchor {
  part: RicciPartId;
  instance: string;
}
export interface RicciCameraState {
  yaw: number;
  pitch: number;
  scale: number;
}
export interface RicciRenderer {
  camera: (state: RicciCameraState) => void;
  laboratory: (enabled: boolean) => void;
  trace: (time: number, variant: TraceCase, enabled: boolean) => void;
  select: (id: RicciPartId | null, instance?: string) => void;
  view: (view: RicciView) => void;
  orbit: (delta: number) => void;
  zoom: (delta: number) => void;
  reset: () => void;
  dispose: () => void;
}

/** One on-demand physical-material scene. Lighting is generated from geometry;
 * no photograph, HDR file, robot asset, physics engine or network request. */
export function createRicciRenderer(
  canvas: HTMLCanvasElement,
  callbacks: {
    pick: (pick: RicciPick) => void;
    miss?: () => void;
    workstation?: () => void;
    ready: () => void;
    progress?: (completed: number) => void;
    anchor?: (anchor: RicciAnchor | null) => void;
    camera?: (state: RicciCameraState) => void;
    failure: (message: string) => void;
  },
  initial?: {
    id: RicciPartId | null;
    instance?: string;
    frame?: HTMLElement;
    camera?: RicciCameraState;
    laboratory?: boolean;
    time?: number;
    variant?: TraceCase;
    motion?: boolean;
  },
): RicciRenderer {
  const started = performance.now();
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x090a0c);
  const environment = new RoomEnvironment(),
    pmrem = new THREE.PMREMGenerator(renderer);
  const lightMap = pmrem.fromScene(environment, 0.04);
  scene.environment = lightMap.texture;
  scene.environmentIntensity = 0.65;
  environment.dispose();
  pmrem.dispose();
  callbacks.progress?.(1);
  performance.measure?.("nisayon:ricci:environment", {
    start: started,
    end: performance.now(),
  });
  const modelStarted = performance.now();
  const model = createRicci();
  scene.add(model.root);
  callbacks.progress?.(2);
  performance.measure?.("nisayon:ricci:geometry", {
    start: modelStarted,
    end: performance.now(),
  });
  const reveal = new SoleReveal(model);
  const study = createCarryPreview(model);
  scene.add(study.root);
  study.root.visible = false;
  const studyOccluders: THREE.Mesh[] = [],
    labOccluders: THREE.Mesh[] = [];
  study.root.traverse((object) => {
    if (object instanceof THREE.Mesh) studyOccluders.push(object);
  });
  let studyEnabled = false;
  let architecture: ReturnType<typeof createArchitecture> | null = null,
    labMap: THREE.WebGLRenderTarget | null = null;
  let workstation: ReturnType<typeof createRicciWorkstation> = null;
  let releaseFloorOcclusion: (() => void) | null = null;
  let deskReading = ricciDeskReading(initial?.time ?? 0, initial?.variant ?? "load", !!initial?.motion);

  const floorGeometry = new THREE.PlaneGeometry(30, 30);
  // Shadow catcher leaves the black stage intact instead of reflecting the
  // studio's light cards into a grey strip under the controls.
  const floorMaterial = new THREE.ShadowMaterial({
    color: 0x000000,
    opacity: 0.4,
  });
  const floor = new THREE.Mesh(floorGeometry, floorMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.002;
  floor.receiveShadow = true;
  scene.add(floor);
  scene.fog = new THREE.Fog(0x090a0c, 5, 12);
  const key = new THREE.DirectionalLight(0xffffff, 2.8);
  key.position.set(-2, 3.4, 3);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -1.2;
  key.shadow.camera.right = 1.2;
  key.shadow.camera.top = 2.1;
  key.shadow.camera.bottom = -1;
  key.shadow.normalBias = 0.005;
  key.shadow.bias = -0.0001;
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xe8ecf4, 2.2);
  rim.position.set(2, 2.4, -2);
  scene.add(rim);
  const fill = new THREE.DirectionalLight(0xffffff, 0.6);
  fill.position.set(2, 1.5, 3);
  scene.add(fill);
  const ambient = new THREE.HemisphereLight(0xf0f3fa, 0x2c3038, 0);
  scene.add(ambient);
  const camera = new THREE.PerspectiveCamera(26, 1, 0.01, 80);
  const raycaster = new THREE.Raycaster(),
    pointer = new THREE.Vector2();
  let yaw = 0,
    pitch = 0.035,
    scale = 1,
    width = 1,
    height = 1;
  let disposed = false,
    lost = false,
    raf = 0,
    previous = 0,
    notified = false;
  let selected: RicciPartId | null = null,
    selectedInstance = "";
  let selectedHit: { mesh: THREE.Object3D; point: THREE.Vector3 } | null = null;
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reduced = media.matches;
  let frame: RicciFrame = { left: 0, top: 0, width: 1, height: 1 };
  const updateCamera = () =>
    frameRicciCamera(camera, { width, height }, frame, { yaw, pitch, scale }, !!architecture?.root.visible);
  const framePoint = (point: { x: number; y: number }) =>
    ricciFramePoint(point, { width, height }, frame);
  const publishCamera = () => callbacks.camera?.({ yaw, pitch, scale });
  const draw = (time: number) => {
    raf = 0;
    if (disposed || lost) return;
    const moving = reveal.update(
      previous ? (time - previous) / 1000 : 1 / 60,
      reduced,
    );
    previous = time;
    try {
      if (architecture?.root.visible) workstation?.flush();
      renderer.render(scene, camera);
      projectSelection();
    } catch (error) {
      lost = true;
      callbacks.failure(
        error instanceof Error
          ? error.message
          : "The 3D frame could not be drawn.",
      );
      return;
    }
    if (!notified) {
      notified = true;
      performance.measure?.("nisayon:ricci:first-frame", {
        start: started,
        end: performance.now(),
      });
      callbacks.progress?.(3);
      callbacks.ready();
    }
    if (moving) invalidate();
    else previous = 0;
  };
  function invalidate() {
    if (!raf && !disposed && !lost) raf = requestAnimationFrame(draw);
  }
  const resize = () => {
    const box = canvas.getBoundingClientRect();
    width = Math.max(1, box.width);
    height = Math.max(1, box.height);
    const focus = initial?.frame?.getBoundingClientRect() ?? box;
    frame = {
      left: focus.left - box.left,
      top: focus.top - box.top,
      width: Math.max(1, focus.width),
      height: Math.max(1, focus.height),
    };
    renderer.setSize(width, height, false);
    updateCamera();
    invalidate();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  if (initial?.frame) observer.observe(initial.frame);
  const select = (id: RicciPartId | null, instance?: string) => {
    selected = id;
    selectedInstance =
      instance ?? (id === "ankle_foot" ? "ankle_foot_left" : "");
    if (
      selectedHit?.mesh.userData.id !== id ||
      (selectedInstance &&
        selectedHit?.mesh.userData.instance !== selectedInstance)
    )
      selectedHit = null;
    const side: RicciSide | null =
      id === "ankle_foot"
        ? selectedInstance.endsWith("right")
          ? "right"
          : "left"
        : null;
    reveal.select(studyEnabled ? null : side);
    if (reduced) reveal.update(0, true);
    for (const mesh of model.meshes) {
      const matches =
        mesh.userData.id === selected &&
        (!selectedInstance || mesh.userData.instance === selectedInstance) &&
        (selected !== "ankle_foot" ||
          (side !== null && mesh.parent === model.soles[side]));
      mesh.material.emissive.setHex(matches ? 0x4c4c4c : 0x000000);
      mesh.material.emissiveIntensity = matches ? 0.28 : 0;
    }
    scene.updateMatrixWorld(true);
    projectSelection();
    invalidate();
  };
  const inspectionSurfaces = () => [
    ...model.meshes,
    ...(studyEnabled ? studyOccluders : []),
    ...(architecture?.root.visible ? labOccluders : []),
  ];
  function layoutOffset(mesh: THREE.Object3D) {
    const delta = new THREE.Vector3();
    if (studyEnabled) return delta;
    for (const side of ["left", "right"] as const)
      if (mesh.parent === model.soles[side]) {
        const sole = model.soles[side],
          selectedSide = selectedInstance.endsWith("right") ? "right" : "left";
        const targetX =
          selected === "ankle_foot" && selectedSide === side
            ? side === "left"
              ? 0.16
              : -0.16
            : 0;
        delta.set(targetX, sole.position.y, sole.position.z);
        sole.parent!.localToWorld(delta);
        delta.sub(sole.getWorldPosition(new THREE.Vector3()));
      }
    return delta;
  }
  function projectedBody(): ScreenRect[] {
    // A compact set of horizontal bands from actual mesh bounds. These only
    // keep labels out of the silhouette; selection still raycasts real triangles.
    const bands = Array.from({ length: 28 }, (_, i) => ({
      left: Infinity,
      right: -Infinity,
      top: (i * frame.height) / 28,
      bottom: ((i + 1) * frame.height) / 28,
    }));
    const point = new THREE.Vector3();
    for (const mesh of model.meshes) {
      if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
      const box = mesh.geometry.boundingBox!;
      const offset = layoutOffset(mesh);
      let left = Infinity,
        right = -Infinity,
        top = Infinity,
        bottom = -Infinity;
      for (const x of [box.min.x, box.max.x])
        for (const y of [box.min.y, box.max.y])
          for (const z of [box.min.z, box.max.z]) {
            point
              .set(x, y, z)
              .applyMatrix4(mesh.matrixWorld)
              .add(offset)
              .project(camera);
            const pixel = framePoint(point);
            left = Math.min(left, pixel.x);
            right = Math.max(right, pixel.x);
            top = Math.min(top, pixel.y);
            bottom = Math.max(bottom, pixel.y);
          }
      for (const band of bands)
        if (bottom >= band.top && top <= band.bottom) {
          band.left = Math.min(band.left, left);
          band.right = Math.max(band.right, right);
        }
    }
    return bands
      .filter((b) => Number.isFinite(b.left))
      .map((b) => ({
        left: Math.round(b.left),
        right: Math.round(b.right),
        top: Math.round(b.top),
        bottom: Math.round(b.bottom),
      }));
  }
  function projectSelection() {
    if (!selected) {
      callbacks.anchor?.(null);
      return;
    }
    const candidates = model.meshes.filter(
      (m) =>
        m.userData.id === selected &&
        (!selectedInstance || m.userData.instance === selectedInstance) &&
        (selected !== "ankle_foot" ||
          studyEnabled ||
          m.parent ===
            model.soles[selectedInstance.endsWith("right") ? "right" : "left"]),
    );
    const center = new THREE.Vector3(),
      projected = new THREE.Vector3(),
      body = projectedBody();
    let hiddenPoint = { x: frame.width / 2, y: frame.height / 2 };
    if (selectedHit && (selected !== "ankle_foot" || studyEnabled)) {
      // Track the surface actually tapped, including fingertips and the lower
      // shin, rather than jumping to the first mesh of a grouped R01 section.
      projected.copy(selectedHit.point);
      selectedHit.mesh.localToWorld(projected);
      projected.project(camera);
      raycaster.setFromCamera(
        new THREE.Vector2(projected.x, projected.y),
        camera,
      );
      const first = raycaster.intersectObjects(inspectionSurfaces(), false)[0];
      const visible =
        Math.abs(projected.x) < 1 &&
        Math.abs(projected.y) < 1 &&
        first?.object.userData.id === selected &&
        (!selectedInstance ||
          first.object.userData.instance === selectedInstance);
      callbacks.anchor?.({
        ...framePoint(projected),
        width: frame.width,
        height: frame.height,
        visible,
        body,
        part: selected,
        instance: selectedInstance,
      });
      return;
    }
    for (const mesh of candidates) {
      if (!mesh.geometry.boundingSphere) mesh.geometry.computeBoundingSphere();
      center.copy(mesh.geometry.boundingSphere!.center);
      mesh.localToWorld(center);
      projected.copy(center).project(camera);
      hiddenPoint = framePoint(projected);
      if (Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) continue;
      raycaster.setFromCamera(
        new THREE.Vector2(projected.x, projected.y),
        camera,
      );
      const first = raycaster.intersectObjects(inspectionSurfaces(), false)[0];
      if (
        first &&
        first.object.userData.id === selected &&
        (!selectedInstance ||
          first.object.userData.instance === selectedInstance)
      ) {
        // Allocate the panel against the reveal's destination, while its line
        // follows the moving sole. Layout cannot hunt between empty spaces on
        // every damping frame. This is authored display motion, not physics.
        const destination = center
          .clone()
          .add(layoutOffset(mesh))
          .project(camera);
        callbacks.anchor?.({
          ...hiddenPoint,
          width: frame.width,
          height: frame.height,
          visible: true,
          body,
          part: selected,
          instance: selectedInstance,
          target: framePoint(destination),
        });
        return;
      }
    }
    callbacks.anchor?.({
      ...hiddenPoint,
      width: frame.width,
      height: frame.height,
      visible: false,
      body,
      part: selected,
      instance: selectedInstance,
    });
  }
  const laboratory = (enabled: boolean) => {
    if (enabled && !architecture) {
      const compact = Math.min(innerWidth, innerHeight) < 600;
      architecture = createArchitecture({ compact });
      releaseFloorOcclusion = loadFloorOcclusion(architecture, invalidate);
      workstation = createRicciWorkstation(document.createElement("canvas"), compact ? 512 : 768);
      workstation?.set(deskReading);
      architecture.workstations.bindDisplay(workstation?.material ?? null, "study");
      architecture.palette(false);
      scene.add(architecture.root);
      architecture.root.traverse((object) => {
        // Decorative line picking has a world-space tolerance and is not a
        // depth surface. Transparent glazing also does not hide an annotation.
        if (
          object instanceof THREE.Mesh &&
          !object.userData.ignorePick &&
          !Array.isArray(object.material) &&
          !(object.material.transparent && object.material.opacity < 0.5)
        )
          labOccluders.push(object);
      });
      const room = daylightEnvironment(),
        generator = new THREE.PMREMGenerator(renderer);
      labMap = generator.fromScene(room.scene, 0.06);
      room.dispose();
      generator.dispose();
    }
    if (architecture) architecture.root.visible = enabled;
    floor.visible = !enabled;
    scene.environment = enabled ? labMap!.texture : lightMap.texture;
    scene.environmentIntensity = enabled ? 0.7 : 0.65;
    scene.background = new THREE.Color(enabled ? 0x969e9f : 0x090a0c);
    scene.fog = enabled
      ? new THREE.Fog(0x7d858b, 10, 27)
      : new THREE.Fog(0x090a0c, 5, 12);
    key.position.copy(
      enabled
        ? new THREE.Vector3(...DAYLIGHT.sun)
        : new THREE.Vector3(-2, 3.4, 3),
    );
    key.intensity = enabled ? DAYLIGHT.intensity : 2.8;
    key.color.set(enabled ? DAYLIGHT.colour : 0xffffff);
    key.shadow.camera.far = 42;
    key.shadow.camera.updateProjectionMatrix();
    rim.intensity = enabled ? 0.65 : 2.2;
    fill.intensity = enabled ? 1.2 : 0.6;
    ambient.intensity = enabled ? 1.15 : 0;
    updateCamera();
    invalidate();
  };
  const trace = (time: number, variant: TraceCase, enabled: boolean) => {
    deskReading = ricciDeskReading(time, variant, enabled);
    workstation?.set(deskReading);
    studyEnabled = enabled;
    study.apply(time, variant, enabled);
    reveal.select(
      enabled
        ? null
        : selected === "ankle_foot"
          ? selectedInstance.endsWith("right")
            ? "right"
            : "left"
          : null,
    );
    if (enabled) reveal.update(0, true);
    invalidate();
  };
  const pointPick = (x: number, y: number) => {
    const box = canvas.getBoundingClientRect();
    pointer.set(
      ((x - box.left) / box.width) * 2 - 1,
      (-(y - box.top) / box.height) * 2 + 1,
    );
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(inspectionSurfaces(), false)[0];
    if (hit?.object.userData.workstation === "study") return { workstation: true as const };
    // Props can occlude a part, but can never become an invisible selection map.
    return hit?.object.userData.id
      ? {
          id: hit.object.userData.id as RicciPartId,
          instance: hit.object.userData.instance as string,
          detail: hit.object.userData.detail as string,
          anchor: {
            mesh: hit.object,
            point: hit.object.worldToLocal(hit.point.clone()),
          },
        }
      : null;
  };
  const disposeGestures = bindOrbitGestures(canvas, {
    orbit: (dx, dy) => {
      yaw -= dx * .008;
      pitch = THREE.MathUtils.clamp(pitch + dy * .005, -.12, .58);
      updateCamera(); publishCamera(); invalidate();
    },
    zoom: factor => {
      scale = THREE.MathUtils.clamp(scale / factor, .65, 1.8);
      updateCamera(); publishCamera(); invalidate();
    },
    hover: event => {
      if (event.pointerType !== "touch") canvas.style.cursor = pointPick(event.clientX, event.clientY) ? "pointer" : "grab";
    },
    tap: event => {
      const pick = pointPick(event.clientX, event.clientY);
      if (pick) {
        if ("workstation" in pick) { callbacks.workstation?.(); return; }
        selectedHit = pick.anchor;
        callbacks.pick({ id: pick.id, instance: pick.instance, detail: pick.detail });
        invalidate();
      } else callbacks.miss?.();
    },
  });
  const view = (next: RicciView) => {
    yaw = next === "front" ? 0 : next === "rear" ? Math.PI : -0.48;
    pitch = next === "front" ? 0.035 : 0.1;
    updateCamera();
    publishCamera();
    invalidate();
  };
  const orbit = (delta: number) => {
    yaw += delta;
    updateCamera();
    publishCamera();
    invalidate();
  };
  const zoom = (delta: number) => {
    scale = THREE.MathUtils.clamp(scale + delta, .65, 1.8);
    updateCamera();
    publishCamera();
    invalidate();
  };
  const keydown = (event: KeyboardEvent) => {
    if (event.key === "Enter" && architecture?.root.visible) { event.preventDefault(); callbacks.workstation?.(); return; }
    if (
      [
        "ArrowLeft",
        "ArrowRight",
        "ArrowUp",
        "ArrowDown",
        "Home",
        "+",
        "=",
        "-",
      ].includes(event.key)
    )
      event.preventDefault();
    if (event.key === "ArrowLeft") orbit(-0.14);
    if (event.key === "ArrowRight") orbit(0.14);
    if (event.key === "ArrowUp" || event.key === "+" || event.key === "=")
      zoom(0.06);
    if (event.key === "ArrowDown" || event.key === "-") zoom(-0.06);
    if (event.key === "Home") {
      scale = 1;
      view("front");
    }
  };
  const motion = () => {
    reduced = media.matches;
    if (reduced) reveal.update(0, true);
    invalidate();
  };
  const contextLost = (event: Event) => {
    event.preventDefault();
    lost = true;
    cancelAnimationFrame(raf);
    raf = 0;
    callbacks.failure(
      "The 3D renderer was interrupted. Your selection and part descriptions are preserved.",
    );
  };
  const contextRestored = () => {
    lost = false;
    workstation?.restore();
    notified = false;
    invalidate();
  };
  canvas.addEventListener("keydown", keydown);
  canvas.addEventListener("webglcontextlost", contextLost);
  canvas.addEventListener("webglcontextrestored", contextRestored);
  media.addEventListener("change", motion);
  if (initial?.camera) {
    yaw = initial.camera.yaw;
    pitch = initial.camera.pitch;
    scale = initial.camera.scale;
  }
  resize();
  if (initial?.laboratory) laboratory(true);
  if (initial?.motion)
    trace(initial.time ?? 0, initial.variant ?? "load", true);
  // A direct part link opens as a coherent assembly on its first frame. Only
  // subsequent inspection actions animate; loading is never an introduction.
  if (initial?.id) {
    select(initial.id, initial.instance);
    reveal.update(0, true);
  }
  // First-frame readiness must not depend on an animation clock: browsers can
  // suspend rAF in an occluded window while the document itself is inspectable.
  cancelAnimationFrame(raf);
  raf = 0;
  draw(performance.now());
  return {
    camera: (state) => {
      yaw = state.yaw;
      pitch = state.pitch;
      scale = state.scale;
      updateCamera();
      invalidate();
    },
    select,
    view,
    orbit,
    zoom,
    laboratory,
    trace,
    reset: () => {
      scale = 1;
      view("front");
    },
    dispose: () => {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(raf);
      observer.disconnect();
      disposeGestures();
      media.removeEventListener("change", motion);
      canvas.removeEventListener("keydown", keydown);
      canvas.removeEventListener("webglcontextlost", contextLost);
      canvas.removeEventListener("webglcontextrestored", contextRestored);
      study.dispose();
      releaseFloorOcclusion?.();
      architecture?.dispose();
      workstation?.dispose();
      labMap?.dispose();
      model.dispose();
      floorGeometry.dispose();
      floorMaterial.dispose();
      lightMap.dispose();
      key.shadow.dispose();
      renderer.dispose();
      scene.clear();
    },
  };
}
