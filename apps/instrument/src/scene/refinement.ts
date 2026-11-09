// Optional still rendering has no authority over playback, pose or evidence.
// A changed moment invalidates its pending import, worker and canvas together.
// v0.0.24's alpha accumulator exposes blend target 1. An odd full sample ends
// in that target; an even count would expose the previous sample instead.
export const REFINEMENT_LIMITS = { samples: 65, pixels: 786432, edge: 1280, milliseconds: 20000, triangles: 500000, geometryBytes: 64 * 1024 * 1024 } as const;
export class RefinementUnavailable extends Error {}
export interface RefinementState {
  phase: "idle" | "preparing" | "compiling" | "calibrating" | "sampling" | "finishing" | "complete" | "unavailable";
  samples: number;
  width?: number;
  height?: number;
  traceWidth?: number;
  traceHeight?: number;
  calibrationMsPerSample?: number;
  elapsedMs?: number;
  reason?: string;
  gpu?: { timerSupported: boolean; batches: number; measuredBatches: number; p95BatchMs: number | null };
}
export const refinementSize = (width: number, height: number) => {
  const w = Math.max(1, width), h = Math.max(1, height);
  const scale = Math.min(1, REFINEMENT_LIMITS.edge / Math.max(w, h), Math.sqrt(REFINEMENT_LIMITS.pixels / (w * h)));
  return { width: Math.max(1, Math.floor(w * scale)), height: Math.max(1, Math.floor(h * scale)) };
};

export interface RefinementLog extends RefinementState { at: string; attempt: number }

export function refinementSession(notify: (state: RefinementState) => void, record?: (entry: RefinementLog) => void) {
  let current: { controller: AbortController; started: number; timer: ReturnType<typeof setTimeout> } | null = null;
  let attempt = 0;
  const history: RefinementLog[] = [];
  let state: RefinementState = { phase: "idle", samples: 0 };
  const emit = (value: RefinementState) => {
    state = value;
    const entry = { ...value, at: new Date().toISOString(), attempt };
    history.push(entry); if (history.length > 128) history.shift();
    record?.(entry); notify(value);
  };
  const cancel = (reason = "Lighting cancelled.") => {
    // A later resize or metadata update must not erase the failure reason.
    if (!current) return;
    const active = current; current = null;
    clearTimeout(active.timer); active.controller.abort();
    emit({ phase: "idle", samples: 0, ...(state.phase === "complete" ? {} : { reason, elapsedMs: performance.now() - active.started }) });
  };
  return {
    cancel,
    state: () => state,
    history: () => [...history],
    start(build: (signal: AbortSignal, update: (state: RefinementState) => void) => Promise<void>) {
      cancel();
      const controller = new AbortController(), started = performance.now();
      attempt++;
      const fail = (reason: string) => {
        if (current?.controller !== controller || controller.signal.aborted) return;
        clearTimeout(current.timer); current = null;
        controller.abort();
        emit({ ...state, phase: "unavailable", elapsedMs: performance.now() - started, reason });
      };
      // Covers the lazy import, preparation, shader compilation and rendering.
      // It is independent of animation frames and clears on every terminal path.
      const timer = setTimeout(() => fail("Lighting stopped after 20 s. The recorded view is unchanged. Try a smaller window or close other graphics-heavy tabs."), REFINEMENT_LIMITS.milliseconds);
      current = { controller, started, timer };
      emit({ phase: "preparing", samples: 0, elapsedMs: 0 });
      const update = (value: RefinementState) => {
        if (current?.controller !== controller || controller.signal.aborted) return;
        if (value.phase === "unavailable") { fail(value.reason ?? "Lighting preview unavailable."); return; }
        if (value.phase === "complete") clearTimeout(timer);
        emit({ ...value, elapsedMs: performance.now() - started });
      };
      const failed = (error: unknown) => fail(error instanceof RefinementUnavailable ? error.message : "Lighting preview unavailable. The recorded view is unchanged.");
      try { void build(controller.signal, update).catch(failed); } catch (error) { failed(error); }
    },
  };
}
