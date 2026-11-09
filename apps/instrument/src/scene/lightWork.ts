// One outstanding GPU batch. Fences are polled with a zero timeout; neither
// waiting for the device nor estimating its speed blocks the main thread.
export function lightWork(gl: WebGL2RenderingContext) {
  const timer = gl.getExtension("EXT_disjoint_timer_query_webgl2") as { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null;
  let pending: { fence: WebGLSync; query: WebGLQuery | null; tiles: number } | null = null;
  let tileMs: number | null = null, limit = timer ? 1 : 2, polls = 0, batches = 0;
  const measurements: number[] = [];
  const release = () => {
    if (!pending) return;
    if (!gl.isContextLost()) { gl.deleteSync(pending.fence); if (pending.query) gl.deleteQuery(pending.query); }
    pending = null;
  };
  return {
    limit: () => limit,
    ready() {
      if (!pending) return true;
      const result = gl.clientWaitSync(pending.fence, 0, 0);
      if (result === gl.WAIT_FAILED) throw Error("Lighting GPU work failed");
      if (result === gl.TIMEOUT_EXPIRED) { polls++; return false; }
      if (pending.tiles) {
        const disjoint = timer && gl.getParameter(timer.GPU_DISJOINT_EXT);
        if (disjoint) { tileMs = null; measurements.length = 0; }
        const measured = timer && pending.query && !disjoint && gl.getQueryParameter(pending.query, gl.QUERY_RESULT_AVAILABLE);
        const ms = measured ? (gl.getQueryParameter(pending.query!, gl.QUERY_RESULT) as number) / 1e6 : null;
        if (ms !== null && Number.isFinite(ms) && ms > 0) {
          measurements.push(ms); if (measurements.length > 256) measurements.shift();
          const perTile = ms / pending.tiles;
          // React immediately to a slower batch; increase throughput gradually.
          tileMs = tileMs === null ? perTile : Math.max(perTile, .75 * tileMs + .25 * perTile);
          limit = Math.max(1, Math.min(8, limit * 2, Math.floor(6 / tileMs)));
        } else {
          // Fence latency is not a GPU timer. Without a valid measurement use
          // a conservative batch and retain "unmeasured" in diagnostics.
          limit = polls ? 1 : 2;
        }
      }
      release(); return true;
    },
    submit(draw: () => number) {
      if (pending) throw Error("Lighting GPU work is still pending");
      const query = timer && !gl.getParameter(timer.GPU_DISJOINT_EXT) ? gl.createQuery() : null;
      let tiles: number;
      if (query) gl.beginQuery(timer!.TIME_ELAPSED_EXT, query);
      try { tiles = draw(); }
      catch (error) { if (query) { gl.endQuery(timer!.TIME_ELAPSED_EXT); gl.deleteQuery(query); } throw error; }
      if (query) gl.endQuery(timer!.TIME_ELAPSED_EXT);
      const fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      if (!fence) { if (query) gl.deleteQuery(query); throw Error("Lighting GPU fence unavailable"); }
      pending = { fence, query, tiles }; polls = 0; batches++;
      gl.flush(); // Submit, never synchronously drain, the GPU queue.
    },
    summary() {
      const sorted = [...measurements].sort((a, b) => a - b);
      return { timerSupported: !!timer, batches, measuredBatches: sorted.length, p95BatchMs: sorted.length ? sorted[Math.floor((sorted.length - 1) * .95)]! : null };
    },
    dispose: release,
  };
}
