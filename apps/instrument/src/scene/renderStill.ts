import { REFINEMENT_LIMITS as LIMITS, RefinementUnavailable, type RefinementState } from "./refinement";
import type { lightWork } from "./lightWork";

// Keep the playback image until every sample and the final composite have
// finished on the GPU. A timed-out or cancelled still is never presented.
export function renderStill(options: {
  signal: AbortSignal;
  started: number;
  work: Pick<ReturnType<typeof lightWork>, "ready" | "submit" | "limit">;
  samples: () => number;
  renderTile: () => void;
  compose: () => void;
  reveal: () => void;
  check: () => void;
  compiling?: () => boolean;
  calibrate?: (millisecondsPerSample: number) => void;
  update: (phase: RefinementState["phase"], samples: number) => void;
}) {
  const { signal, started, work, samples, renderTile, compose, reveal, check, update } = options;
  return new Promise<void>((resolve, reject) => {
    let task: ReturnType<typeof setTimeout>, deadline: ReturnType<typeof setTimeout>;
    let finishing = false, reported = -1, lastReport = -Infinity, phase: RefinementState["phase"] = "preparing";
    let calibrated = !options.calibrate, calibrationStart: { samples: number; time: number } | null = null;
    const stop = () => { clearTimeout(task); clearTimeout(deadline); signal.removeEventListener("abort", abort); };
    const abort = () => { stop(); resolve(); };
    if (signal.aborted) { resolve(); return; }
    signal.addEventListener("abort", abort, { once: true });
    const timeout = () => { stop(); reject(new RefinementUnavailable("The still did not finish within 20 s. The recorded view is unchanged.")); };
    deadline = setTimeout(timeout, Math.max(0, LIMITS.milliseconds - (performance.now() - started)));
    const step = () => {
      if (signal.aborted) { abort(); return; }
      try {
        check();
        if (performance.now() - started >= LIMITS.milliseconds) { timeout(); return; }
        if (work.ready()) {
          const completed = Math.floor(samples() + 1e-6);
          reported = completed;
          if (!calibrated) {
            // Exclude import, scene preparation and first-use shader work.
            if (!calibrationStart && completed >= 1) calibrationStart = { samples: completed, time: performance.now() };
            if (calibrationStart && completed >= calibrationStart.samples + 2) {
              options.calibrate!((performance.now() - calibrationStart.time) / (completed - calibrationStart.samples));
              calibrated = true; phase = "sampling"; reported = Math.floor(samples()); lastReport = performance.now();
              update(phase, reported); task = setTimeout(step, 4); return;
            }
          }
          if (finishing) {
            reveal(); update("complete", completed); stop(); resolve(); return;
          }
          if (completed >= LIMITS.samples) {
            work.submit(() => { compose(); return 0; });
            finishing = true; phase = "finishing"; update(phase, completed);
          } else {
            const next = options.compiling?.() ? "compiling" : !calibrated ? "calibrating" : completed || options.calibrate ? "sampling" : "preparing";
            if (phase !== next || performance.now() - lastReport >= 500) {
              phase = next; lastReport = performance.now(); update(phase, completed);
            }
            const cpuStart = performance.now(), count = work.limit();
            work.submit(() => {
              let tiles = 0;
              for (let i = 0; i < count; i++) {
                const before = samples(); renderTile();
                // Asynchronous shader compilation may submit no sample yet.
                if (samples() <= before) break;
                tiles++;
                if (samples() >= LIMITS.samples || performance.now() - cpuStart >= 3) break;
              }
              return tiles;
            });
          }
          // A task boundary lets GPU fences signal without waiting for a
          // display refresh per tiny tile batch. Only one batch is outstanding.
          task = setTimeout(step, 4);
        } else {
          if (performance.now() - lastReport >= 500) { lastReport = performance.now(); update(phase, Math.max(0, reported)); }
          task = setTimeout(step, 8);
        }
      } catch (error) { stop(); reject(error); }
    };
    task = setTimeout(step, 0);
  });
}
