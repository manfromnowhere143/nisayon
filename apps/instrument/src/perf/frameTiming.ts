// Optional GPU timer queries never wait for the GPU or call gl.finish().
// A disjoint clock invalidates pending queries; absence stays unavailable.
export function frameTiming(gl: WebGL2RenderingContext) {
  const getExtension = () => gl.getExtension("EXT_disjoint_timer_query_webgl2") as { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null;
  let extension = getExtension();
  let active: WebGLQuery | null = null;
  const pending: WebGLQuery[] = [], cpu: number[] = [], gpu: number[] = [];
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
    begin() {
      collect();
      if (extension && !gl.isContextLost() && !gl.getParameter(extension.GPU_DISJOINT_EXT) && pending.length < 8 && !active) { active = gl.createQuery(); if (active) gl.beginQuery(extension.TIME_ELAPSED_EXT, active); }
      return performance.now();
    },
    end(start: number) {
      record(cpu, performance.now() - start);
      if (active && extension && !gl.isContextLost()) { gl.endQuery(extension.TIME_ELAPSED_EXT); pending.push(active); }
      active = null;
    },
    reset() { active = null; pending.length = 0; },
    restore() { extension = getExtension(); },
    summary() {
      collect();
      const summarize = (values: number[]) => { const sorted = [...values].sort((a, b) => a - b); return { count: values.length, p95: sorted.length ? sorted[Math.floor((sorted.length - 1) * .95)]! : null }; };
      return { cpu: summarize(cpu), gpu: { supported: !!extension, ...summarize(gpu) } };
    },
    dispose() { if (!gl.isContextLost()) { if (active && extension) gl.endQuery(extension.TIME_ELAPSED_EXT); if (active) gl.deleteQuery(active); for (const q of pending) gl.deleteQuery(q); } active = null; pending.length = 0; },
  };
}
