import { useMemo } from "react";
import type { FramePhase, Frames, Moment } from "../model/types";

export interface PhysicalSample { row: number; time: number; value: number }
export function physicalSamples(frames: Frames | null, phase: Moment["phase"], read: (frame: FramePhase) => number | undefined): PhysicalSample[] {
  return frames?.rows.flatMap((row, i) => {
    const frame = row[phase], value = frame && read(frame);
    return frame && value !== undefined && Number.isFinite(value) ? [{ row: i, time: frame.sim_time_s, value }] : [];
  }) ?? [];
}
export function nearestPhysicalSample(samples: PhysicalSample[], time: number): PhysicalSample | null {
  let best: PhysicalSample | null = null;
  for (const sample of samples) if (!best || Math.abs(sample.time - time) < Math.abs(best.time - time)) best = sample;
  return best;
}

export function PhysicalHistory({ samples, moment, label, unit, range, onSelect }: { samples: PhysicalSample[]; moment: Moment; label: string; unit: string; range: [number, number] | null; onSelect?: ((row: number, phase: Moment["phase"]) => void) | undefined }) {
  const geometry = useMemo(() => {
    const first = samples[0]?.time ?? 0, last = samples.at(-1)?.time ?? first + 1;
    let low = range?.[0] ?? Infinity, high = range?.[1] ?? -Infinity;
    for (const s of samples) { low = Math.min(low, s.value); high = Math.max(high, s.value); }
    const pad = Math.max((high - low) * .1, .0001); low -= pad; high += pad;
    const x = (time: number) => 14 + (time - first) / (last - first || 1) * 572;
    const y = (value: number) => 18 + (high - value) / (high - low || 1) * 78;
    return { first, last, x, y, path: samples.map((s, i) => `${i ? "L" : "M"}${x(s.time).toFixed(3)},${y(s.value).toFixed(3)}`).join(" ") };
  }, [samples, range]);
  const current = samples.find(s => s.row === moment.row_index), index = samples.findIndex(s => s.row === moment.row_index);
  if (!samples.length) return <p className="fine">{label}: no retained samples.</p>;
  return <div className="physical-history">
    <div className="history-heading"><span>{label}</span><span>{unit} · {moment.phase} configuration</span></div>
    <svg viewBox="0 0 600 128" role={onSelect ? "slider" : "img"} tabIndex={onSelect ? 0 : undefined} aria-label={`${label} history`} aria-valuemin={samples[0]!.row} aria-valuemax={samples.at(-1)!.row} aria-valuenow={current?.row} aria-valuetext={current ? `${current.value} ${unit}, ${current.time} seconds, ${moment.phase} configuration` : "Sample unavailable"}
      onClick={e => { const box = e.currentTarget.getBoundingClientRect(); if (!box.width) return; const fraction = Math.max(0, Math.min(1, (600 * (e.clientX - box.left) / box.width - 14) / 572)); const sample = nearestPhysicalSample(samples, geometry.first + fraction * (geometry.last - geometry.first)); if (sample) onSelect?.(sample.row, moment.phase); }}
      onKeyDown={e => { let next = index; if (e.key === "ArrowLeft" || e.key === "ArrowDown") next--; else if (e.key === "ArrowRight" || e.key === "ArrowUp") next++; else if (e.key === "Home") next = 0; else if (e.key === "End") next = samples.length - 1; else return; e.preventDefault(); e.stopPropagation(); const sample = samples[Math.max(0, Math.min(samples.length - 1, next))]; if (sample) onSelect?.(sample.row, moment.phase); }}>
      {range?.map((v, i) => <g key={i}><line className="history-limit" x1="14" x2="586" y1={geometry.y(v)} y2={geometry.y(v)} /><text x="586" y={geometry.y(v) - 4} textAnchor="end">{v} {unit}</text></g>)}
      <path className="history-trace" d={geometry.path} />
      {range ? samples.filter(s => s.value <= range[0] || s.value >= range[1]).map(s => <path key={s.row} className="history-limit-mark" d={`M${geometry.x(s.time)},${geometry.y(s.value) - 3}v6`} />) : null}
      {current ? <g><line className="history-cursor" x1={geometry.x(current.time)} x2={geometry.x(current.time)} y1="12" y2="101" /><circle className="history-dot" cx={geometry.x(current.time)} cy={geometry.y(current.value)} r="2.7" /></g> : null}
      <text x="14" y="122">{geometry.first.toFixed(3)} s</text><text x="586" y="122" textAnchor="end">{geometry.last.toFixed(3)} s</text>
    </svg>
    {range ? <p className="fine">Dashed lines: declared limits. Ticks: recorded values at or beyond a limit.</p> : null}
  </div>;
}
