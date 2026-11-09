import { timeForPhase } from "./findings";
import type { Phase, SampleRow } from "./types";

// Hold the last retained sample at or before the playback clock. Use actual
// timestamps so a gap in the recording cannot be turned into invented motion.
export function playbackRow(rows: readonly SampleRow[], phase: Phase, start: number, elapsed: number): number {
  if (!rows.length) return 0;
  const first = Math.max(0, Math.min(rows.length - 1, start));
  const time = timeForPhase(rows[first]!, phase) + Math.max(0, elapsed);
  let low = first, high = rows.length;
  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (timeForPhase(rows[mid]!, phase) <= time) low = mid + 1;
    else high = mid;
  }
  return Math.max(first, low - 1);
}
