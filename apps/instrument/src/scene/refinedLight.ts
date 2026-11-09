// Rejected experiment, disconnected from the application. Two completed
// attempts took over 17 seconds and the operator's 20 September screenshot
// rejects their image quality. Retained for diagnosis only; sample count does
// not qualify a picture. See docs/ui/qualification/lighting-stall-2026-09-20.
import * as THREE from "three";
import { DenoiseMaterial, WebGLPathTracer } from "three-gpu-pathtracer";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { FullScreenQuad } from "three/addons/postprocessing/Pass.js";
import { lightSnapshot } from "./lightSnapshot";
import { lightBvh } from "./lightBvh";
import { lightWork } from "./lightWork";
import { renderStill } from "./renderStill";
import { lightScale } from "./lightScale";
import { RefinementUnavailable, refinementSize, type RefinementState } from "./refinement";

export async function refineLight(host: HTMLElement, scene: THREE.Scene, camera: THREE.PerspectiveCamera, signal: AbortSignal, update: (state: RefinementState) => void) {
  if (signal.aborted) return;
  const started = performance.now();
  const snapshot = lightSnapshot(scene, camera);
  const size = refinementSize(host.clientWidth * Math.min(devicePixelRatio || 1, 2), host.clientHeight * Math.min(devicePixelRatio || 1, 2));
  const canvas = document.createElement("canvas");
  canvas.className = "scene-refined-canvas"; canvas.setAttribute("aria-hidden", "true"); canvas.style.visibility = "hidden";
  let renderer: THREE.WebGLRenderer | null = null, tracer: WebGLPathTracer | null = null;
  let environment: THREE.WebGLCubeRenderTarget | null = null, worker: ReturnType<typeof lightBvh> | null = null;
  let work: ReturnType<typeof lightWork> | null = null;
  let timeout = 0, disposed = false, shaderFailed = false;
  let calibrationMsPerSample: number | undefined;
  const rendering = new AbortController();
  const depth = new THREE.MeshBasicMaterial({ colorWrite: false });
  // A small edge-aware spatial filter, not a neural reconstruction. Apply it
  // only to light; measured markers and contours are drawn afterwards.
  const denoise = new DenoiseMaterial({ sigma: 2, kSigma: 1, threshold: .1 });
  const filtered = new FullScreenQuad(denoise);
  const cleanup = () => {
    if (disposed) return;
    disposed = true; clearTimeout(timeout);
    rendering.abort();
    signal.removeEventListener("abort", cleanup); canvas.removeEventListener("webglcontextlost", contextLost);
    work?.dispose(); worker?.dispose(); tracer?.dispose(); environment?.dispose(); depth.dispose();
    filtered.dispose(); denoise.dispose(); snapshot.dispose();
    // v0.0.24 does not release every internal auxiliary texture on dispose.
    // Releasing this dedicated context bounds those allocations too; the
    // instrument's main context, geometry and playback remain alive.
    renderer?.dispose(); renderer?.forceContextLoss(); canvas.remove();
  };
  const contextLost = (event: Event) => {
    event.preventDefault(); shaderFailed = true;
    // A completed still has no animation loop left to observe context loss.
    // Remove it immediately so the qualified playback canvas stays visible.
    cleanup();
    update({ phase: "unavailable", samples: 0, reason: "The lighting preview lost its graphics context. The recorded view is unchanged." });
  };
  signal.addEventListener("abort", cleanup, { once: true });
  try {
    // This canvas draws once, then waits for its GPU fence before becoming
    // visible. Preserve that one buffer across animation frames; otherwise
    // the browser may clear it before presentation. Playback is unaffected.
    const context = canvas.getContext("webgl2", { alpha: true, antialias: false, powerPreference: "low-power", preserveDrawingBuffer: true });
    if (!context || !context.getExtension("EXT_color_buffer_float")) throw new RefinementUnavailable("This browser cannot create the floating-point lighting target. The recorded view is unchanged.");
    renderer = new THREE.WebGLRenderer({ canvas, context, alpha: true });
    work = lightWork(context);
    renderer.setPixelRatio(1); renderer.setSize(size.width, size.height, false);
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .95;
    renderer.setClearColor(0, 0);
    renderer.debug.onShaderError = () => { shaderFailed = true; };
    canvas.addEventListener("webglcontextlost", contextLost);
    host.appendChild(canvas);
    // Sample the same procedural studio used by the raster display. This is
    // illustrative illumination, not a room measurement or camera observation.
    environment = new THREE.WebGLCubeRenderTarget(128, { type: THREE.HalfFloatType });
    const room = new RoomEnvironment();
    try { new THREE.CubeCamera(.1, 100, environment).update(renderer, room); } finally { room.dispose(); }
    snapshot.physical.environment = environment.texture;
    tracer = new WebGLPathTracer(renderer);
    tracer.bounces = 4; tracer.transmissiveBounces = 2;
    tracer.tiles.set(4, 4); tracer.textureSize.set(128, 128);
    tracer.renderDelay = 0; tracer.fadeDuration = 0;
    tracer.rasterizeScene = false; tracer.dynamicLowRes = false;
    tracer.renderToCanvas = false;
    const compose = () => {
      const render = renderer!;
      // Rebuild exact depth for the snapshot, then composite illumination and
      // the crisp, independent evidence layer. No line enters the light BVH.
      render.autoClear = true;
      snapshot.physical.overrideMaterial = depth;
      render.render(snapshot.physical, snapshot.camera);
      snapshot.physical.overrideMaterial = null;
      render.autoClear = false;
      denoise.map = tracer!.target.texture;
      filtered.render(render);
      render.render(snapshot.overlays, snapshot.camera);
      render.autoClear = true;
    };
    worker = lightBvh(signal); tracer.setBVHWorker(worker);
    await Promise.race([
      tracer.setSceneAsync(snapshot.physical, snapshot.camera),
      new Promise<never>((_resolve, reject) => { timeout = window.setTimeout(() => reject(new RefinementUnavailable("Still preparation exceeded 10 s. The recorded view is unchanged.")), 10000); }),
    ]);
    clearTimeout(timeout);
    if (disposed || signal.aborted) return;
    worker.dispose(); worker = null;
    await renderStill({
      signal: rendering.signal, started, work,
      samples: () => tracer!.samples,
      renderTile: () => tracer!.renderSample(),
      compose,
      reveal: () => { canvas.style.visibility = "visible"; },
      check: () => { if (disposed || shaderFailed || renderer!.getContext().isContextLost()) throw new RefinementUnavailable("The lighting shader or graphics context failed. The recorded view is unchanged."); },
      // Public v0.0.24 getter; its bundled declarations omit this property.
      compiling: () => (tracer as WebGLPathTracer & { readonly isCompiling: boolean }).isCompiling,
      calibrate: millisecondsPerSample => {
        calibrationMsPerSample = millisecondsPerSample;
        const scale = lightScale(millisecondsPerSample);
        if (scale < 1) { tracer!.renderScale = scale; tracer!.reset(); }
      },
      update: (phase, samples) => update({ phase, samples, ...size,
        traceWidth: Math.floor(size.width * tracer!.renderScale), traceHeight: Math.floor(size.height * tracer!.renderScale),
        ...(calibrationMsPerSample !== undefined ? { calibrationMsPerSample } : {}),
        elapsedMs: performance.now() - started, gpu: work!.summary() }),
    });
  } catch (error) { cleanup(); throw error; }
}
