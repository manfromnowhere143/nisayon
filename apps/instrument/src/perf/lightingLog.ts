import type { RefinementLog } from "../scene/refinement";

// Development-only renderer diagnostics over Vite's existing local socket.
// No evidence, URL, browser content or credentials; production sends nothing.
let page: string | null = null;
export function logLighting(entry: RefinementLog): void {
  if (!import.meta.env.DEV || import.meta.env.TEST || !import.meta.hot) return;
  try {
    page ??= crypto.randomUUID();
    import.meta.hot.send("nisayon:lighting", { page, ...entry });
  } catch { /* Diagnostics must never interrupt rendering. */ }
}
