import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import type { Plugin } from "vite";

// This is a bounded local development log, never a production telemetry API.
// Admit only the renderer's small diagnostic schema, not arbitrary client data.
export function lightingEvent(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Record<string, unknown>;
  if (typeof v.page !== "string" || !/^[a-f0-9-]{36}$/.test(v.page) ||
    !["idle", "preparing", "compiling", "calibrating", "sampling", "finishing", "complete", "unavailable"].includes(String(v.phase)) ||
    typeof v.at !== "string" || !/^\d{4}-\d{2}-\d{2}T[\d:.]+Z$/.test(v.at)) return null;
  const number = (n: unknown, limit: number): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= limit;
  if (!number(v.attempt, 100000) || !Number.isInteger(v.attempt) || !number(v.samples, 1000)) return null;
  const result: Record<string, unknown> = { page: v.page, at: v.at, attempt: v.attempt, phase: v.phase, samples: v.samples };
  for (const name of ["width", "height", "traceWidth", "traceHeight", "calibrationMsPerSample", "elapsedMs"] as const) if (number(v[name], 3600000)) result[name] = v[name];
  if (typeof v.reason === "string" && v.reason.length <= 512) result.reason = v.reason;
  if (v.gpu && typeof v.gpu === "object") {
    const gpu = v.gpu as Record<string, unknown>;
    if (typeof gpu.timerSupported === "boolean" && number(gpu.batches, 1000000) && number(gpu.measuredBatches, 1000000) &&
      (gpu.p95BatchMs === null || number(gpu.p95BatchMs, 3600000))) {
      result.gpu = { timerSupported: gpu.timerSupported, batches: gpu.batches, measuredBatches: gpu.measuredBatches, p95BatchMs: gpu.p95BatchMs };
    }
  }
  return result;
}

export function lightingLogPlugin(path: string): Plugin {
  return {
    name: "nisayon-local-lighting-log",
    configureServer(server) {
      const events: Record<string, unknown>[] = [];
      let timer: ReturnType<typeof setTimeout> | undefined, writing = false, dirty = false, closed = false;
      const flush = async () => {
        timer = undefined;
        if (writing || !dirty || closed) return;
        writing = true; dirty = false;
        try {
          await mkdir(dirname(path), { recursive: true });
          await writeFile(path, JSON.stringify({ schema: "nisayon.local-lighting-log.v1", events }, null, 2) + "\n");
        } catch { server.config.logger.warn("Could not save the local lighting log."); }
        finally { writing = false; if (dirty && !closed) timer = setTimeout(() => void flush(), 500); }
      };
      const receive = (value: unknown) => {
        const entry = lightingEvent(value);
        if (!entry || closed) return;
        events.push({ received_at: new Date().toISOString(), ...entry });
        if (events.length > 256) events.shift();
        dirty = true;
        if (!timer && !writing) timer = setTimeout(() => void flush(), 500);
      };
      server.ws.on("nisayon:lighting", receive);
      server.httpServer?.once("close", () => { closed = true; clearTimeout(timer); server.ws.off("nisayon:lighting", receive); });
    },
  };
}
