// Two trace lanes on one simulation-time axis: the intended and executed
// gripper command at action time, and the original cube-height reading at
// its post-action time with the frozen threshold. A recording ends where it
// ends. Tapping a lane selects the nearest recorded row.

import { useEffect, useMemo, useRef, useState } from "react";
import { recordingEnd, type LoadedRun } from "../data/loader";
import { actionLabel, alignedRow } from "../model/findings";
import type { Moment, Phase, Predicates, SampleRow } from "../model/types";

interface Props {
  primary: LoadedRun;
  ghost: LoadedRun | null;
  moment: Moment;
  predicates: Predicates;
  expanded: boolean;
  onSelectRow: (row: number, phase: Phase) => void;
}

const GRIPPER = 6;
const LANE_H = 64;
const PAD_L = 10;
const PAD_R = 10;
const TOP = 8;
const BOTTOM = 10;

export function signalSample(rows: readonly SampleRow[], time: number, clock: "action" | "next" | "interval"): number {
  if (clock === "interval") {
    const containing = rows.find((row) => time >= row.action_sim_time_s && time < row.next_sim_time_s);
    if (containing) return containing.row_index;
  }
  let best = 0, distance = Infinity;
  for (const row of rows) {
    const delta = Math.abs((clock === "action" ? row.action_sim_time_s : row.next_sim_time_s) - time);
    if (delta < distance) { best = row.row_index; distance = delta; }
  }
  return best;
}

function useWidth(ref: React.RefObject<HTMLDivElement | null>): number {
  const [width, setWidth] = useState(360);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(Math.max(120, el.clientWidth)));
    observer.observe(el);
    setWidth(Math.max(120, el.clientWidth));
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

export function Lanes({ primary, ghost, moment, predicates, expanded, onSelectRow }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const width = useWidth(boxRef);
  const rows = primary.samples.rows;
  const ghostRows = ghost?.samples.rows ?? null;
  const primaryEnd = recordingEnd(primary);
  const ghostEnd = ghost ? recordingEnd(ghost) : 0;
  const tEnd = Math.max(primaryEnd, ghostEnd, 0.05);
  const x = (t: number): number => PAD_L + (t / tEnd) * (width - PAD_L - PAD_R);

  const gripper = useMemo(() => {
    const yFor = (v: number): number => TOP + ((1.15 - v) / 2.3) * (LANE_H - TOP - BOTTOM);
    const path = (source: typeof rows, pick: (r: (typeof rows)[number]) => number): string =>
      source.map((r, i) => `${i === 0 ? "M" : "L"}${x(r.action_sim_time_s).toFixed(1)},${yFor(pick(r)).toFixed(1)}`).join(" ");
    return {
      yFor,
      intended: path(rows, (r) => r.intended_action[GRIPPER] ?? 0),
      executed: path(rows, (r) => r.executed_action[GRIPPER] ?? 0),
      ghostExecuted: ghostRows ? path(ghostRows, (r) => r.executed_action[GRIPPER] ?? 0) : null,
    };
  }, [rows, ghostRows, width, tEnd]);

  const height = useMemo(() => {
    const all = rows.map((r) => r.cube_height_m).concat(ghostRows ? ghostRows.map((r) => r.cube_height_m) : [], [predicates.min_cube_height_m]);
    const min = Math.min(...all) - 0.004;
    const max = Math.max(...all) + 0.004;
    const yFor = (v: number): number => TOP + ((max - v) / (max - min)) * (LANE_H - TOP - BOTTOM);
    const path = (source: typeof rows): string => source.map((r, i) => `${i === 0 ? "M" : "L"}${x(r.next_sim_time_s).toFixed(1)},${yFor(r.cube_height_m).toFixed(1)}`).join(" ");
    return { yFor, min, max, primary: path(rows), ghost: ghostRows ? path(ghostRows) : null };
  }, [rows, ghostRows, width, tEnd, predicates.min_cube_height_m]);

  const memory = useMemo(() => {
    if (!ghostRows && !expanded) return null;
    const cells: { x0: number; x1: number; state: "equal" | "differs" | "unpaired" | "unavailable" | "present"; row: number }[] = [];
    let diverges: number | null = null;
    for (const r of rows) {
      const other = ghostRows ? alignedRow(r, ghostRows, "after") : null;
      const state: "equal" | "differs" | "unpaired" | "unavailable" | "present" = r.policy.after === "unavailable" || other?.policy.after === "unavailable" ? "unavailable" : !ghostRows ? "present" : !other ? "unpaired" : other.policy.state_after_sha256 !== null && r.policy.state_after_sha256 !== null ? (other.policy.state_after_sha256 === r.policy.state_after_sha256 ? "equal" : "differs") : "unavailable";
      if (state === "differs" && diverges === null) diverges = r.row_index;
      cells.push({ x0: x(r.action_sim_time_s), x1: x(r.next_sim_time_s), state, row: r.row_index });
    }
    const resets = rows.filter((r) => r.policy.reset_before_inference).map((r) => x(r.action_sim_time_s));
    const uninitialised = rows.filter((r) => r.policy.before === "initialized_none").map((r) => x(r.action_sim_time_s));
    return { cells, diverges, resets, uninitialised, unavailable: cells.filter((c) => c.state === "unavailable").length, unpaired: cells.filter((c) => c.state === "unpaired").length };
  }, [rows, ghostRows, expanded, width, tEnd]);

  const age = useMemo(() => {
    const values = rows.map((r) => r.observation_age_s).filter((v): v is number => v !== null);
    const top = Math.max(0.05, predicates.max_observation_age_s * 1.5, ...values.map((v) => v * 1.15));
    const yFor = (v: number): number => TOP + ((top - v) / top) * (LANE_H - TOP - BOTTOM);
    let d = "";
    let pen = false;
    for (const r of rows) {
      if (r.observation_age_s === null) {
        pen = false;
        continue;
      }
      d += `${pen ? "L" : "M"}${x(r.action_sim_time_s).toFixed(1)},${yFor(r.observation_age_s).toFixed(1)} `;
      pen = true;
    }
    const violations = rows.filter((r) => r.observation_age_s !== null && r.observation_age_s > predicates.max_observation_age_s);
    return { yFor, path: d, top, violations };
  }, [rows, width, tEnd, predicates.max_observation_age_s]);

  const row = rows[moment.row_index] ?? null;
  const cursorAction = row ? x(row.action_sim_time_s) : null;
  const cursorNext = row ? x(row.next_sim_time_s) : null;

  const select = (event: React.PointerEvent<SVGSVGElement>, clock: "action" | "next" | "interval"): void => {
    const rect = event.currentTarget.getBoundingClientRect();
    const local = (event.clientX - rect.left) * (width / (rect.width || width));
    const t = ((local - PAD_L) / (width - PAD_L - PAD_R)) * tEnd;
    onSelectRow(signalSample(rows, t, clock), clock === "action" ? "before" : "after");
  };

  const endX = x(primaryEnd);
  const ghostEndX = ghost ? x(ghostEnd) : null;
  const gripperValue = row ? `${(row.intended_action[GRIPPER] ?? 0).toFixed(6)} intended, ${(row.executed_action[GRIPPER] ?? 0).toFixed(6)} executed` : "no sample";
  const heightValue = row ? `${row.cube_height_m.toFixed(6)} m` : "no sample";
  const ticks = axisTicks(tEnd, width);
  const keyboard = (event: React.KeyboardEvent<SVGSVGElement>, clock: "action" | "next" | "interval") => {
    const last = rows.length - 1;
    const index = event.key === "Home" ? 0 : event.key === "End" ? last : event.key === "ArrowLeft" ? Math.max(0, moment.row_index - (event.shiftKey ? 10 : 1)) : event.key === "ArrowRight" ? Math.min(last, moment.row_index + (event.shiftKey ? 10 : 1)) : null;
    if (index === null || last < 0) return;
    event.preventDefault();
    onSelectRow(rows[index]!.row_index, clock === "action" ? "before" : "after");
  };
  const slider = (clock: "action" | "next" | "interval", value: string) => ({
    role: "slider", tabIndex: 0, "aria-valuemin": 0, "aria-valuemax": Math.max(0, rows.length - 1), "aria-valuenow": row ? moment.row_index : undefined, "aria-valuetext": `Step ${row?.step ?? moment.row_index}, ${value}`, onKeyDown: (event: React.KeyboardEvent<SVGSVGElement>) => keyboard(event, clock),
  } as const);

  return (
    <div ref={boxRef} className="lanes" data-signal-group={expanded ? "timing" : "task"}>
      {row ? (
        <dl className="selected-readings" aria-label="Values at the selected recorded step">
          <div><dt>Intended <span className="reading-clock">{row.action_sim_time_s.toFixed(2)} s</span></dt><dd className="num">{row.intended_action[GRIPPER]?.toFixed(4) ?? "not recorded"}</dd></div>
          <div><dt>Executed <span className="reading-clock">{row.action_sim_time_s.toFixed(2)} s</span></dt><dd className="num">{row.executed_action[GRIPPER]?.toFixed(4) ?? "not recorded"}</dd></div>
          <div><dt>Cube height <span className="reading-clock">{row.next_sim_time_s.toFixed(2)} s</span></dt><dd className="num">{row.cube_height_m.toFixed(4)} <span className="reading-unit">m</span></dd></div>
          <div><dt>Observation age</dt><dd className="num">{row.observation_age_s === null ? "not recorded" : <>{(row.observation_age_s * 1000).toFixed(0)} <span className="reading-unit">ms</span></>}</dd></div>
        </dl>
      ) : null}
      <section className="trace-group lane-task" aria-label="Gripper command">
      <TraceHeader title="Gripper command" detail="Normalized · at action" />
      <div className="trace-legend" aria-hidden="true"><span><i className="trace-key intended" />Intended</span><span><i className="trace-key executed" />Executed</span>{ghost ? <span><i className="trace-key paired" />{ghost.record.run.run_id}</span> : null}</div>
      <svg
        className="lane"
        width={width}
        height={LANE_H}
        {...slider("action", gripperValue)}
        aria-label={`Gripper command lane, ${actionLabel(GRIPPER)} component; selected row ${moment.row_index}: ${gripperValue}`}
        onPointerDown={(event) => select(event, "action")}
      >
        <line className="lane-rule" x1={PAD_L} x2={width - PAD_R} y1={gripper.yFor(0)} y2={gripper.yFor(0)} />
        {gripper.ghostExecuted ? <path className="lane-ghost" d={gripper.ghostExecuted} /> : null}
        <path className="lane-intended" d={gripper.intended} />
        <path className="lane-executed" d={gripper.executed} />
        {cursorAction !== null ? <line className={`lane-cursor${moment.phase === "before" ? " is-phase" : ""}`} x1={cursorAction} x2={cursorAction} y1={TOP - 6} y2={LANE_H - BOTTOM} /> : null}
        {row ? <circle className="lane-dot lane-dot-intended" cx={cursorAction ?? 0} cy={gripper.yFor(row.intended_action[GRIPPER] ?? 0)} r={2.75} /> : null}
        {row ? <circle className="lane-dot lane-dot-executed" cx={cursorAction ?? 0} cy={gripper.yFor(row.executed_action[GRIPPER] ?? 0)} r={2.75} /> : null}
        <EndMark x={endX} y={LANE_H - BOTTOM} label={`${primary.record.run.run_id} ends ${primaryEnd.toFixed(2)} s`} />
        {ghostEndX !== null && ghost ? <EndMark x={ghostEndX} y={LANE_H - BOTTOM} label={`${ghost.record.run.run_id} ends ${ghostEnd.toFixed(2)} s`} ghost /> : null}
      </svg>
      </section>
      <section className="trace-group lane-task" aria-label="Cube height">
      <TraceHeader title="Cube height" detail="Metres · after action" />
      <div className="trace-legend"><span>Original reading</span><span className="trace-limit"><i className="trace-key threshold" aria-hidden="true" />Required &gt; {predicates.min_cube_height_m.toFixed(2)} m</span></div>
      <svg className="lane" width={width} height={LANE_H} {...slider("next", heightValue)} aria-label={`Cube height lane, original post-action reading; selected row ${moment.row_index}: ${heightValue}; threshold ${predicates.min_cube_height_m} m`} onPointerDown={(event) => select(event, "next")}>
        <line className="lane-threshold" x1={PAD_L} x2={width - PAD_R} y1={height.yFor(predicates.min_cube_height_m)} y2={height.yFor(predicates.min_cube_height_m)} />
        {height.ghost ? <path className="lane-ghost" d={height.ghost} /> : null}
        <path className="lane-executed" d={height.primary} />
        {cursorNext !== null ? <line className={`lane-cursor${moment.phase === "after" ? " is-phase" : ""}`} x1={cursorNext} x2={cursorNext} y1={TOP - 6} y2={LANE_H - BOTTOM} /> : null}
        {row ? <circle className="lane-dot lane-dot-executed" cx={cursorNext ?? 0} cy={height.yFor(row.cube_height_m)} r={2.75} /> : null}
        <EndMark x={endX} y={LANE_H - BOTTOM} label="" />
      </svg>
      </section>
      {memory ? (
        <section className="trace-group trace-memory" aria-label="Policy memory">
        <TraceHeader title="Policy memory" detail={ghost ? `Compared with ${ghost.record.run.run_id}` : "Availability & reset"} />
        <p className="trace-note">{memory.unavailable ? `${memory.unavailable} rows unavailable` : memory.unpaired ? `${memory.unpaired} rows unpaired` : !ghost ? "Recorded" : memory.diverges === null ? "Equal throughout" : `Digests differ from row ${memory.diverges}`}</p>
        <svg className="lane lane-memory" width={width} height={36} {...slider("interval", row?.policy.after ?? "unavailable")} aria-label={`Policy memory lane: recurrent-state digest equality between ${primary.record.run.run_id} and ${ghost?.record.run.run_id ?? "no paired run"} after each row; ${memory.unavailable} rows unavailable; ${memory.unpaired} unpaired; ${memory.diverges === null ? "no divergence recorded" : `digests diverge from row ${memory.diverges}`}`} onPointerDown={(event) => select(event, "interval")}>
          {memory.cells.map((c) => (
            <rect key={c.row} className={`mem-cell mem-${c.state}`} x={c.x0} y={8} width={Math.max(0.5, c.x1 - c.x0)} height={14} />
          ))}
          {memory.resets.map((rx, i) => (
            <line key={`reset-${i}`} className="mem-reset" x1={rx} x2={rx} y1={4} y2={26} />
          ))}
          {memory.uninitialised.map((ux, i) => (
            <circle key={`none-${i}`} className="mem-none" cx={ux} cy={15} r={4} />
          ))}
          {cursorNext !== null ? <line className="lane-cursor is-phase" x1={cursorNext} x2={cursorNext} y1={2} y2={30} /> : null}
        </svg>
        <p className="trace-note">{ghost ? "Filled: equal · open: differs · hatch: unavailable · ring: initialized None" : "Filled: present · hatch: unavailable · ring: initialized None · tick: reset"}</p>
        </section>
      ) : null}
      {expanded ? (
        <section className="trace-group" aria-label="Observation age">
        <TraceHeader title="Observation age" detail="Seconds · at action" />
        <div className="trace-legend"><span>Consumed observation</span><span className="trace-limit"><i className="trace-key threshold" aria-hidden="true" />Maximum {predicates.max_observation_age_s} s</span></div>
        <svg className="lane" width={width} height={LANE_H} {...slider("action", row?.observation_age_s == null ? "unavailable" : `${row?.observation_age_s} s`)} aria-label={`Observation age lane; selected row ${moment.row_index}: ${row && row.observation_age_s !== null ? `${row.observation_age_s.toFixed(6)} s` : "no sample"}; declared maximum ${predicates.max_observation_age_s} s; ${age.violations.length} rows exceed it`} onPointerDown={(event) => select(event, "action")}>
          <line className="lane-threshold" x1={PAD_L} x2={width - PAD_R} y1={age.yFor(predicates.max_observation_age_s)} y2={age.yFor(predicates.max_observation_age_s)} />
          <path className="lane-executed" d={age.path} />
          {row?.consumed_observation_capture_sim_time_s != null ? <g className="lane-age-interval" aria-label={`Capture ${row.consumed_observation_capture_sim_time_s} s to action ${row.action_sim_time_s} s`}>
            <line x1={x(row.consumed_observation_capture_sim_time_s)} x2={x(row.action_sim_time_s)} y1={TOP - 3} y2={TOP - 3} />
            <line x1={x(row.consumed_observation_capture_sim_time_s)} x2={x(row.consumed_observation_capture_sim_time_s)} y1={TOP - 6} y2={TOP + 2} />
            <line x1={x(row.action_sim_time_s)} x2={x(row.action_sim_time_s)} y1={TOP - 6} y2={TOP + 2} />
          </g> : null}
          {cursorAction !== null ? <line className={`lane-cursor${moment.phase === "before" ? " is-phase" : ""}`} x1={cursorAction} x2={cursorAction} y1={TOP - 6} y2={LANE_H - BOTTOM} /> : null}
          {row && row.observation_age_s !== null ? <circle className="lane-dot lane-dot-executed" cx={cursorAction ?? 0} cy={age.yFor(row.observation_age_s)} r={2.75} /> : null}
          <EndMark x={endX} y={LANE_H - BOTTOM} label="" />
        </svg>
        <p className="trace-note">{age.violations.length ? `${age.violations.length} rows exceed the declared maximum` : "No recorded values exceed the declared maximum"}</p>
        </section>
      ) : null}
      <svg className="trace-axis" width={width} height={24} aria-hidden="true">
        {ticks.map((t) => <g key={t}><line className="lane-tick" x1={x(t)} x2={x(t)} y1={0} y2={4} /><text className="lane-axis" x={x(t)} y={19} textAnchor={t === 0 ? "start" : t === tEnd ? "end" : "middle"}>{t.toFixed(t === tEnd || tEnd < 1 ? 2 : 1)} s</text></g>)}
      </svg>
      <div className="trace-footnote"><span>Simulation time</span><span className="num">{ghost ? `${primary.record.run.run_id}: ` : "Ends "}{primaryEnd.toFixed(2)} s{ghost ? ` · ${ghost.record.run.run_id}: ${ghostEnd.toFixed(2)} s` : ""}</span></div>
    </div>
  );
}

function TraceHeader({ title, detail }: { title: string; detail: string }) {
  return <div className="trace-heading"><h3>{title}</h3><span>{detail}</span></div>;
}

function EndMark({ x, y, label, ghost = false }: { x: number; y: number; label: string; ghost?: boolean }) {
  return <g className={ghost ? "lane-end lane-end-ghost" : "lane-end"}><title>{label}</title><line x1={x} x2={x} y1={y - 5} y2={y + 1} /></g>;
}

export function axisTicks(tEnd: number, width: number): number[] {
  const count = Math.max(2, Math.floor((width - PAD_L - PAD_R) / 80));
  const target = tEnd / count;
  const magnitude = 10 ** Math.floor(Math.log10(target));
  const step = [1, 2, 5, 10].map((n) => n * magnitude).find((n) => n >= target)!;
  const ticks = [0];
  for (let t = step; t < tEnd - step * 0.6; t += step) ticks.push(Number(t.toPrecision(12)));
  ticks.push(tEnd);
  return ticks;
}
