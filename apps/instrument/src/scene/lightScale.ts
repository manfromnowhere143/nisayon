import { REFINEMENT_LIMITS } from "./refinement";

// Choose the tracing resolution from completed work on this scene/device.
// This is a workload estimate, not a promised finish time. Keep the output
// canvas, exact depth and evidence overlays at their original resolution.
export function lightScale(millisecondsPerSample: number): number {
  if (!Number.isFinite(millisecondsPerSample) || millisecondsPerSample <= 0) return 1;
  const scale = Math.sqrt(6000 / (millisecondsPerSample * REFINEMENT_LIMITS.samples));
  return Math.max(.5, Math.min(1, Math.floor(scale * 16) / 16));
}
