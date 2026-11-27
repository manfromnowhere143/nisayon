// Optional GPU timer queries never wait for the GPU or call gl.finish().
// A disjoint clock invalidates pending queries; absence stays unavailable.
export function frameTiming(gl: WebGL2RenderingContext) {
  const getExtension = () => gl.getExtension("EXT_disjoint_timer_query_webgl2") as { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null;
  let extension = getExtension();
  let active: WebGLQuery | null = null;
  const pending: WebGLQuery[] = [], cpu: number[] = [], gpu: number[] = [], intervals: number[] = [];
  let previousFrame: number | null = null;
  const record = (values: number[], ms: number) => { values.push(ms); if (values.length > 240) values.shift(); };
  const collect = () => {
    if (!extension || gl.isContextLost()) return;
    if (gl.getParameter(extension.GPU_DISJOINT_EXT)) { for (const q of pending.splice(0)) gl.deleteQuery(q); return; }
    while (pending.length && gl.getQueryParameter(pending[0]!, gl.QUERY_RESULT_AVAILABLE)) {
      const q = pending.shift()!, ns = gl.getQueryParameter(q, gl.QUERY_RESULT) as number;
      if (Number.isFinite(ns) && ns >= 0) record(gpu, ns / 1e6);
      gl.deleteQuery(q);
    }
  };
  return {
    begin(continuous = false) {
      collect();
      const now = performance.now();
      // On-demand idle time is not an animation frame. Explicit camera/study
      // motion owns this series; submission and GPU samples remain separate.
      if (continuous && previousFrame !== null) record(intervals, now - previousFrame);
      previousFrame = continuous ? now : null;
      if (extension && !gl.isContextLost() && !gl.getParameter(extension.GPU_DISJOINT_EXT) && pending.length < 8 && !active) { active = gl.createQuery(); if (active) gl.beginQuery(extension.TIME_ELAPSED_EXT, active); }
      return performance.now();
    },
    end(start: number) {
      record(cpu, performance.now() - start);
      if (active && extension && !gl.isContextLost()) { gl.endQuery(extension.TIME_ELAPSED_EXT); pending.push(active); }
      active = null;
    },
    reset() { active = null; pending.length = 0; previousFrame = null; },
    clearSamples() { cpu.length = 0; gpu.length = 0; intervals.length = 0; previousFrame = null; },
    restore() { extension = getExtension(); },
    summary() {
      collect();
      const summarize = (values: number[]) => { const sorted = [...values].sort((a, b) => a - b); const at = (q: number) => sorted.length ? sorted[Math.floor((sorted.length - 1) * q)]! : null;
        return { count: values.length, p50: at(.5), p95: at(.95), p99: at(.99), max: sorted.at(-1) ?? null }; };
      return { cpu: summarize(cpu), gpu: { supported: !!extension, ...summarize(gpu) }, motionIntervals: summarize(intervals) };
    },
    dispose() { if (!gl.isContextLost()) { if (active && extension) gl.endQuery(extension.TIME_ELAPSED_EXT); if (active) gl.deleteQuery(active); for (const q of pending) gl.deleteQuery(q); } active = null; pending.length = 0; },
  };
}
