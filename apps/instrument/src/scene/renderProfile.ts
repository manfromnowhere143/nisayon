/** Presentation budgets only. Nothing here may enter an experimental identity. */
export type RenderProfile = "interactive" | "detail";
export const RENDER_PROFILES = {
  interactive: { label: "Interactive", maxDpr: 1.5, pixels: 3_000_000, planarReflection: false },
  detail: { label: "Detailed", maxDpr: 2, pixels: 6_000_000, planarReflection: true },
} as const;

export function readRenderProfile(): RenderProfile {
  try { return localStorage.getItem("nisayon.render-profile") === "detail" ? "detail" : "interactive"; }
  catch { return "interactive"; }
}
export function saveRenderProfile(profile: RenderProfile) {
  try { localStorage.setItem("nisayon.render-profile", profile); } catch { /* Session remains usable. */ }
}
export function renderPixelRatio(width: number, height: number, dpr: number, profile: RenderProfile): number {
  const budget = RENDER_PROFILES[profile];
  if (![width, height, dpr].every(v => Number.isFinite(v) && v > 0)) return 1;
  return Math.min(dpr, budget.maxDpr, Math.sqrt(budget.pixels / (width * height)));
}

/** Zero endpoint velocity and acceleration; finite jerk for a finite duration. */
export function cameraEase(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x * x * x * (x * (6 * x - 15) + 10);
}
