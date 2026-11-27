import { useEffect, useRef, useState } from "react";
import type { LoadedRun } from "../data/loader";
import type { CaseRecord, Generation, Moment, SampleRow } from "../model/types";
import { actionLabel, signed } from "../model/findings";
import { acquisitionGroups, observationPair, type ObservationTarget } from "../model/spatial";
import { Choice } from "./Choice";
import { EvidenceFlow } from "./EvidenceFlow";
import { Icon } from "./Icon";

export type InspectionStep = "capture" | "command" | "result";
interface Props {
  run: LoadedRun; generation: Generation; caseRecord: CaseRecord; moment: Moment;
  step: InspectionStep; onStep: (step: InspectionStep) => void;
  target: ObservationTarget; onTarget: (target: ObservationTarget) => void;
  compact?: boolean;
  onRow?: (delta: number) => void; onPhase?: () => void;
  onClose: () => void; onCompare: () => void; onDecision: () => void;
}
const fixed = (value: number | null | undefined, digits = 3) => value == null ? "Not recorded" : value.toFixed(digits);

// The persistent transport owns playback. This reading follows its exact sample;
// changing the lens never advances the recording or changes scientific acceptance.
export function MomentInspection({ run, generation, caseRecord, moment, step, onStep, target, onTarget, onClose, onCompare, onDecision, onRow, onPhase, compact = false }: Props) {
  const [detail, setDetail] = useState(false);
  const title = useRef<HTMLHeadingElement>(null);
  const [requestedComponent, setComponent] = useState(6);
  useEffect(() => { if (!compact) title.current?.focus({ preventScroll: true }); }, [compact]);
  const row = run.samples.rows[moment.row_index] ?? null;
  const pair = observationPair(row, target);
  const groups = acquisitionGroups(row?.consumed_acquisition ?? null);
  const component = Math.min(requestedComponent, Math.max(0, (row?.intended_action.length ?? 1) - 1));
  const intended = row?.intended_action[component], executed = row?.executed_action[component];
  const frameTime = run.frames?.rows[moment.row_index]?.[moment.phase].sim_time_s;
  const source = new URL(run.record.samples.path, generation.baseUrl).href;
  const expanded = !compact || detail;
  const steps = [["capture", "Observe"], ["command", "Command"], ["result", "Result"]] as const;
  return <section className="moment-inspection" data-compact={compact} data-detail={detail} data-step={step} aria-label="Inspect this moment" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } }}>
    {!compact ? <header className="inspection-heading"><div><p className="eyebrow">Recorded moment · step {row?.step ?? moment.row_index}</p><h2 ref={title} tabIndex={-1}>Inspect this moment</h2></div><button type="button" className="ibtn" aria-label="Close moment inspection" onClick={onClose}>×</button></header> : null}
    <nav className="inspection-steps" aria-label="Moment inspection steps">{steps.map(([id, label]) => <button key={id} type="button" aria-pressed={step === id} onClick={() => onStep(id)}>{label}</button>)}</nav>
    <EvidenceFlow label={`Moment · ${step}`} identity={`${generation.sha256}:${run.record.run.run_id}:${step}`}>
    {row ? <>
      <div className="inspection-body">
        <p className="inspection-context">{step === "capture" ? `${target === "eef" ? "Tool" : "Cube"} observation` : step === "command" ? `${actionLabel(component)} · normalized` : "Post-action height"}</p>
        {step === "capture" ? <div className="inspection-measures"><Measure label="Age" value={row.observation_age_s === null ? null : row.observation_age_s * 1000} unit="ms" digits={expanded ? 3 : 1} /><Measure label="Observation gap" value={pair.distance === null ? null : pair.distance * 1000} unit="mm" digits={expanded ? 3 : 1} /></div> : null}
        {step === "command" ? <div className="inspection-command"><div><span>Intended</span><strong className="num">{intended == null ? "Not recorded" : signed(intended, expanded ? 6 : 3)}</strong></div><span className="command-arrow" aria-hidden="true">→</span><div><span>Executed</span><strong className="num">{executed == null ? "Not recorded" : signed(executed, expanded ? 6 : 3)}</strong></div></div> : null}
        {step === "result" ? <><div className="inspection-measures"><Measure label="Cube" value={row.cube_height_m * 1000} unit="mm" digits={expanded ? 4 : 1} /><div><span>Threshold</span><strong className="num">&gt; {(caseRecord.predicates.min_cube_height_m * 1000).toFixed(1)}<small> mm</small></strong></div></div><p className="inspection-result-note">{row.cube_height_m > caseRecord.predicates.min_cube_height_m ? "Above threshold" : "Threshold not met"}<span> · this sample</span></p></> : null}
      </div>
      <div className="inspection-row-controls" role="group" aria-label="Moment controls">
        {onRow ? <><button type="button" aria-label="Previous row" onClick={() => onRow(-1)} disabled={moment.row_index <= 0}><Icon name="prev" /></button><span className="num">Step {row.step}</span><button type="button" aria-label="Next row" onClick={() => onRow(1)} disabled={moment.row_index >= run.record.row_count - 1}><Icon name="next" /></button></> : null}
        {compact ? <button type="button" className="inspection-detail-toggle" aria-expanded={detail} onClick={() => setDetail(value => !value)}>{detail ? "Less" : "Details"}<span aria-hidden="true">{detail ? "−" : "+"}</span></button> : null}
      </div>
      <div className="inspection-details" hidden={!expanded}>
        {step === "capture" ? <>
          <Choice label="Inspection observation target" value={target} onChange={value => onTarget(value as ObservationTarget)} options={[{ value: "eef", label: "End effector" }, { value: "cube", label: "Cube" }]} />
          <MomentClock row={row} />
          <p className="inspection-explanation">{groups.length === 1 ? `${groups[0]!.names.length} components share the capture stamp.` : groups.length > 1 ? `${groups.reduce((sum, group) => sum + group.names.length, 0)} components have ${groups.length} capture stamps; the clock marks each one.` : "Component capture stamps were not recorded."} {pair.distance === null ? "The observation pair is unavailable." : `The markers compare consumed and current ${target === "eef" ? "tool" : "cube"} observations.`}</p>
        </> : step === "command" ? <>
          <Choice label="Inspection action component" value={String(component)} onChange={value => setComponent(Number(value))} options={row.intended_action.map((_, index) => ({ value: String(index), label: actionLabel(index) }))} />
          <p className="inspection-explanation">At {fixed(row.action_sim_time_s)} s · component {component}. Original policy output and recorded execution. Normalized actions are clipped before execution; these are not actuator torques.</p>
          <p className="fine">Target frame: retained controller goal at {fixed(frameTime)} s. Axis lengths are a display convention; the connector shows positional tracking error.</p>
        </> : <p className="inspection-explanation">The height condition {row.cube_height_m > caseRecord.predicates.min_cube_height_m ? "holds" : "does not hold"} at this sample. Whole-run task outcome: <strong>{run.record.task_outcome}</strong>. This sample alone does not establish a correction.</p>}
        <div className="inspection-source"><span>Robot: {moment.phase} · <span className="num">{fixed(frameTime)} s</span></span>{onPhase ? <button type="button" onClick={onPhase} aria-label={`Phase ${moment.phase}; switch to ${moment.phase === "before" ? "after" : "before"}`}>Show {moment.phase === "before" ? "after" : "before"}</button> : null}<a href={source} target="_blank" rel="noreferrer" title={`SHA-256 ${run.record.samples.sha256} · /rows/${row.row_index}`}>Source row {row.row_index}</a></div>
        <div className="inspection-actions"><button type="button" className="quiet" onClick={onCompare}>Compare recordings</button><button type="button" className="quiet" onClick={onDecision}>Decision</button></div>
      </div>
    </> : <p className="fine">No recorded sample at this moment.</p>}
    </EvidenceFlow>
  </section>;
}

function Measure({ label, value, unit, digits = 3 }: { label: string; value: number | null; unit: string; digits?: number }) {
  return <div><span>{label}</span><strong className="num">{fixed(value, digits)}{value !== null ? <small> {unit}</small> : null}</strong></div>;
}

function MomentClock({ row }: { row: SampleRow }) {
  const groups = acquisitionGroups(row.consumed_acquisition);
  const capture = row.consumed_observation_capture_sim_time_s;
  const captures = groups.length ? groups.map((group) => group.time) : capture === null ? [] : [capture];
  const start = Math.min(row.action_sim_time_s, ...captures);
  const end = Math.max(row.next_sim_time_s, row.action_sim_time_s, ...captures);
  const x = (t: number) => 10 + 380 * (t - start) / Math.max(end - start, 1e-9);
  return <div className="moment-clock">
    <div className="moment-clock-values"><div><span>{groups.length > 1 ? "Oldest capture" : "Capture"}</span><b className="num">{fixed(capture)}{capture !== null ? " s" : ""}</b></div><div><span>Action</span><b className="num">{fixed(row.action_sim_time_s)} s</b></div><div><span>Result</span><b className="num">{fixed(row.next_sim_time_s)} s</b></div></div>
    <svg viewBox="0 0 400 30" role="img" aria-label={`Local simulation-time axis: ${captures.length ? `capture ${captures.map((t) => `${t} s`).join(", ")}` : "capture unavailable"}; action ${row.action_sim_time_s} s; result ${row.next_sim_time_s} s`}>
      <line className="clock-rule" x1="10" x2="390" y1="15" y2="15" />
      {captures.map((time) => <g key={time} className="clock-capture" data-capture={time}><title>Capture {time} s</title><path d={`M${x(time)},9 l6,6 -6,6 -6,-6 Z`} /></g>)}
      <line className="clock-action" x1={x(row.action_sim_time_s)} x2={x(row.action_sim_time_s)} y1="5" y2="25" />
      <circle className="clock-result" cx={x(row.next_sim_time_s)} cy="15" r="3" />
    </svg>
  </div>;
}
