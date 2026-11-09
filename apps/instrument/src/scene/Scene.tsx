// Present the detailed, source-bound Panda. A load or graphics failure is an
// explicit recoverable state; it never silently substitutes a schematic robot.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { FramePhase, Frames, Generation, ModelRecord } from "../model/types";
import { checkVisualBinding, loadVisualAsset, type VisualAsset } from "./visualAssets";
import { trajectoryBounds } from "./framing";
import { defaultOptions } from "../data/loader";
import { createSceneRenderer, type Ground, type SceneHandle, type SceneView, type Tone } from "./renderer";
import { sameSpatialLayer, type SpatialLayerState } from "./evidenceLayer";
import type { Vec3 } from "../model/pose";
import { corners } from "./framing";
import { loadCollisionView, type CollisionView } from "./collisionAssets";

interface Props {
  frame: FramePhase | null;
  ghostFrame: FramePhase | null;
  model: ModelRecord;
  modelSha: string;
  generation: Generation;
  ghostModel: ModelRecord | null;
  ghostModelSha: string | null;
  recordings: readonly Frames[];
  focus: "workspace" | "grasp" | "lab";
  view: SceneView;
  ground: Ground;
  tone: Tone;
  reducedMotion: boolean;
  onFirstFrame: () => void;
  onUnavailable?: (() => void) | undefined;
  onLoadProgress?: ((detail: string) => void) | undefined;
  onHandle: (handle: SceneHandle | null) => void;
  spatial: SpatialLayerState;
  observationBounds: readonly Vec3[];
  onPick: (body: number) => void;
}

type Mode = "webgl" | "webgl-unavailable" | "webgl-lost";

export function Scene({ frame, ghostFrame, model, modelSha, generation, ghostModel, ghostModelSha, recordings, focus, view, ground, tone, reducedMotion, onFirstFrame, onUnavailable, onLoadProgress, onHandle, spatial, observationBounds, onPick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<SceneHandle | null>(null);
  const presentedSpatial = useRef<SpatialLayerState | null>(null);
  const [visual, setVisual] = useState<{ model: ModelRecord; asset: VisualAsset | null; issue: string | null } | null>(null);
  const [painted, setPainted] = useState(false);
  const [mode, setMode] = useState<Mode>("webgl");
  const [attempt, setAttempt] = useState(0);
  const [collision, setCollision] = useState<{ model: ModelRecord; view: CollisionView | null; issue: string | null } | null>(null);
  const collisionView = collision?.model === model ? collision.view : null;
  const qualified = useMemo(() => {
    if (!visual?.asset) return { ready: visual?.model === model, asset: null, issue: visual?.issue ?? null };
    try {
      // Requalify cached geometry synchronously for every source and pairing.
      // No blank frame or temporary schematic between compatible recordings.
      checkVisualBinding(visual.asset, model, modelSha, generation);
      if (ghostModel && ghostModelSha) checkVisualBinding(visual.asset, ghostModel, ghostModelSha, generation);
      return { ready: true, asset: visual.asset, issue: null };
    } catch (error) {
      return { ready: true, asset: null, issue: error instanceof Error ? error.message : "Detailed geometry unavailable" };
    }
  }, [visual, model, modelSha, generation, ghostModel, ghostModelSha]);
  const asset = mode === "webgl" ? qualified.asset : null;
  const bounds = useMemo(() => {
    const bounds = trajectoryBounds(model, recordings, focus, asset);
    if (!spatial.options.observations || !observationBounds.length) return bounds;
    const points = [...(bounds.fitPoints ?? corners(bounds))];
    const min = [...bounds.min] as Vec3, max = [...bounds.max] as Vec3;
    for (const point of observationBounds) for (const x of [-0.075, 0.075]) for (const y of [-0.075, 0.075]) for (const z of [-0.075, 0.075]) {
      const p: Vec3 = [point[0] + x, point[1] + y, point[2] + z]; points.push(p);
      for (let i = 0; i < 3; i++) { min[i] = Math.min(min[i]!, p[i]!); max[i] = Math.max(max[i]!, p[i]!); }
    }
    return { min, max, fitPoints: points };
  }, [model, recordings, focus, asset, spatial.options.observations, observationBounds]);
  const firstFrameRef = useRef(onFirstFrame);
  firstFrameRef.current = onFirstFrame;
  const unavailableRef = useRef(onUnavailable);
  unavailableRef.current = onUnavailable;
  const progressRef = useRef(onLoadProgress);
  progressRef.current = onLoadProgress;
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const handle = createSceneRenderer(canvas, ground, {
      onContextLost: () => setMode("webgl-lost"),
      onContextRestored: () => setMode("webgl"),
      onFirstFrame: () => { setPainted(true); firstFrameRef.current(); },
    });
    handleRef.current = handle;
    onHandle(handle);
    if (!handle) {
      setMode("webgl-unavailable");
    }
    return () => {
      handle?.dispose();
      handleRef.current = null;
      presentedSpatial.current = null;
      onHandle(null);
    };
    // Recreate only on an explicit recovery attempt. Selection changes reuse it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const observer = new ResizeObserver(() => {
      if (box.clientWidth <= 0 || box.clientHeight <= 0) return;
      handleRef.current?.resize();
    });
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!handleRef.current || qualified.ready) return;
    progressRef.current?.("Loading detailed Panda geometry");
    void loadVisualAsset(model, modelSha, generation, {
      ...defaultOptions(),
      onProgress: ({ loaded, total }) => {
        if (cancelled) return;
        progressRef.current?.(total && loaded < total
          ? `Loading Panda geometry · ${Math.floor(100 * loaded / total)}%`
          : "Verifying detailed Panda geometry");
      },
    }).then((asset) => {
      if (cancelled) return;
      progressRef.current?.("Preparing the detailed lab");
      setVisual({ model, asset, issue: null });
    }).catch((error: unknown) => {
      if (!cancelled) setVisual({ model, asset: null, issue: error instanceof Error ? error.message : "Detailed geometry unavailable" });
    });
    return () => { cancelled = true; };
  }, [model, modelSha, generation, qualified.ready, attempt]);

  // Ordered layout effects prepare the entire verified scene before its DOM
  // labels are painted. Model/asset replacement is presented synchronously.
  useLayoutEffect(() => {
    if (qualified.ready && asset) handleRef.current?.setModel(model, asset);
  }, [model, asset, qualified.ready]);

  useEffect(() => {
    if (!spatial.options.collision || collision?.model === model) return;
    let cancelled = false;
    void loadCollisionView(model, modelSha, generation).then(view => { if (!cancelled) setCollision({ model, view, issue: null }); }).catch((error: unknown) => { if (!cancelled) setCollision({ model, view: null, issue: error instanceof Error ? error.message : "Collision geometry unavailable" }); });
    return () => { cancelled = true; };
  }, [model, modelSha, generation, spatial.options.collision, collision?.model]);
  useLayoutEffect(() => { if (asset) handleRef.current?.setCollision(collisionView); }, [model, collisionView, asset]);

  useLayoutEffect(() => { if (asset) handleRef.current?.setBounds(bounds); }, [bounds, asset]);

  useLayoutEffect(() => {
    if (asset) handleRef.current?.setPrimary(frame, tone);
  }, [frame, tone, asset]);

  useLayoutEffect(() => {
    if (asset) handleRef.current?.setGhost(ghostFrame);
  }, [ghostFrame, asset]);

  useLayoutEffect(() => {
    if (asset && !sameSpatialLayer(presentedSpatial.current, spatial)) {
      handleRef.current?.setSpatial(spatial);
      presentedSpatial.current = spatial;
    }
  }, [spatial, asset]);

  useLayoutEffect(() => {
    handleRef.current?.setView(view, !reducedMotion);
  }, [view, reducedMotion, attempt]);

  useLayoutEffect(() => {
    handleRef.current?.setGround(ground);
  }, [ground, attempt]);

  useLayoutEffect(() => {
    if (asset) handleRef.current?.present();
  }, [model, asset, frame, ghostFrame, tone]);

  useEffect(() => {
    if (mode !== "webgl" || (qualified.ready && !asset)) unavailableRef.current?.();
  }, [mode, qualified.ready, asset]);

  const sceneIssue = mode === "webgl-lost" ? "The graphics connection was interrupted."
    : mode === "webgl-unavailable" ? "This window could not start the detailed 3D renderer."
    : qualified.ready && !asset ? qualified.issue ?? "The detailed geometry could not be verified." : null;
  const retry = () => {
    setVisual(null);
    setPainted(false);
    setMode("webgl");
    setAttempt((value) => value + 1);
  };

  // Pointer orbit: mouse drags orbit freely; touch drags orbit horizontally so
  // vertical page scrolling stays available (touch-action: pan-y).
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    let dragging: { id: number; x: number; y: number; startX: number; startY: number; moved: boolean; touch: boolean; body: string | null } | null = null;
    const down = (event: PointerEvent): void => {
      if (event.button !== 0) return;
      if (event.target instanceof Element && event.target.closest("button, a")) return;
      const target = event.target instanceof Element ? event.target.closest("[data-body]") : null;
      dragging = { id: event.pointerId, x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, moved: false, touch: event.pointerType === "touch", body: target?.getAttribute("data-body") ?? null };
      box.setPointerCapture(event.pointerId);
    };
    const move = (event: PointerEvent): void => {
      if (!dragging || event.pointerId !== dragging.id) return;
      if (!dragging.moved && Math.hypot(event.clientX - dragging.startX, event.clientY - dragging.startY) < 5) return;
      dragging.moved = true;
      const dx = event.clientX - dragging.x;
      const dy = event.clientY - dragging.y;
      dragging.x = event.clientX;
      dragging.y = event.clientY;
      handleRef.current?.orbit(dx * 0.006, dragging.touch ? 0 : dy * 0.006);
    };
    const up = (event: PointerEvent): void => {
      if (!dragging || event.pointerId !== dragging.id) return;
      if (event.type === "pointerup" && !dragging.moved && Math.hypot(event.clientX - dragging.startX, event.clientY - dragging.startY) < 5) {
        const rect = box.getBoundingClientRect();
        const body = handleRef.current && rect.width && rect.height ? handleRef.current.pick((event.clientX - rect.left) / rect.width * 2 - 1, 1 - (event.clientY - rect.top) / rect.height * 2) : dragging.body === null ? null : Number(dragging.body);
        if (body !== null && Number.isInteger(body)) pickRef.current(body);
      }
      dragging = null;
    };
    const wheel = (event: WheelEvent): void => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      handleRef.current?.zoom(Math.exp(event.deltaY * 0.002));
    };
    box.addEventListener("pointerdown", down);
    box.addEventListener("pointermove", move);
    box.addEventListener("pointerup", up);
    box.addEventListener("pointercancel", up);
    box.addEventListener("wheel", wheel, { passive: false });
    return () => {
      box.removeEventListener("pointerdown", down);
      box.removeEventListener("pointermove", move);
      box.removeEventListener("pointerup", up);
      box.removeEventListener("pointercancel", up);
      box.removeEventListener("wheel", wheel);
    };
  }, []);

  return (
    <div ref={boxRef} className="scene-box" data-mode={mode} data-focus={focus} data-presentation={sceneIssue ? "unavailable" : asset && painted ? "ready" : "preparing"}>
      <div className="scene-model-label">
        <span>Panda</span>
        <span className="scene-model-kind" title={qualified.issue ?? "Reconstruction of retained configuration; lighting is illustrative."}>
          {sceneIssue ? "detailed scene unavailable" : asset ? "source geometry" : "preparing reconstruction"}
        </span>
      </div>
      <canvas ref={canvasRef} className="scene-canvas" aria-hidden="true" style={{ visibility: asset && painted ? "visible" : "hidden" }} />
      {sceneIssue ? (
        <div className="scene-recovery" role="alert">
          <p className="scene-recovery-title">The detailed lab needs to reconnect.</p>
          <p>{sceneIssue}</p>
          <button type="button" className="quiet" onClick={retry}>Retry detailed lab</button>
        </div>
      ) : null}
      {spatial.options.observations || spatial.options.path || spatial.options.axes || spatial.options.goal || spatial.options.collision || spatial.selectedBody !== null ? <div className="scene-legend" aria-label="Spatial overlay key">
        {spatial.options.observations ? <><span><i className="key-consumed" />Consumed</span><span><i className="key-acquired" />Acquired at action</span></> : null}
        {spatial.options.path ? <span><i className="key-path" />{spatial.start > 0 ? "Recent configuration path" : "Configuration path"}</span> : null}
        {spatial.options.axes ? <span>Body axes · X Y Z</span> : null}
        {spatial.options.goal ? <span>Controller goal · selected configuration {frame?.sim_time_s.toFixed(3)} s</span> : null}
        {spatial.options.collision ? <span role="status">{collisionView ? "Collision X-ray · finite shapes; no contacts" : collision?.model === model && collision.issue ? collision.issue : "Verifying collision geometry…"}</span> : null}
        {spatial.selectedBody !== null ? <span>{asset ? "Selected surface / body origin" : "Selected body origin"}</span> : null}
      </div> : null}
    </div>
  );
}
