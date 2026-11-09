import { useEffect, useRef, useState } from "react";
import type { LoadedRun } from "../data/loader";
import type { CaseRecord, Generation, Moment, SampleRow } from "../model/types";
import { actionLabel, signed } from "../model/findings";
import { acquisitionGroups, observationPair, type ObservationTarget } from "../model/spatial";
import { Choice } from "./Choice";
import { EvidenceFlow } from "./EvidenceFlow";

export type InspectionStep = "capture" | "command" | "result";
interface Props {
  run: LoadedRun; generation: Generation; caseRecord: CaseRecord; moment: Moment;
  step: InspectionStep; onStep: (step: InspectionStep) => void;
  target: ObservationTarget; onTarget: (target: ObservationTarget) => void;
  onClose: () => void; onCompare: () => void; onDecision: () => void;
}
const fixed = (value: number | null | undefined, digits = 3) => value == null ? "Not recorded" : value.toFixed(digits);

// One selected sample throughout. The sequence changes the explanation, never
// the sample, camera, phase, evidence or scientific acceptance.
export function MomentInspection({ run, generation, caseRecord, moment, step, onStep, target, onTarget, onClose, onCompare, onDecision }: Props) {
  const title = useRef<HTMLHeadingElement>(null);
  const [requestedComponent, setComponent] = useState(6);
  useEffect(() => { title.current?.focus({ preventScroll: true }); }, []);
  const row = run.samples.rows[moment.row_index] ?? null;
  const pair = observationPair(row, target);
  const groups = acquisitionGroups(row?.consumed_acquisition ?? null);
  const component = Math.min(requestedComponent, Math.max(0, (row?.intended_action.length ?? 1) - 1));
  const intended = row?.intended_action[component], executed = row?.executed_action[component];
  const frameTime = run.frames?.rows[moment.row_index]?.[moment.phase].sim_time_s;
  const source = new URL(run.record.samples.path, generation.baseUrl).href;
  const steps = [["capture", "Capture"], ["command", "Command"], ["result", "Result"]] as const;
  return <section className="moment-inspection" data-step={step} aria-label="Inspect this moment" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } }}>
    <header className="inspection-heading"><div><p className="eyebrow">Recorded moment · step {row?.step ?? moment.row_index}</p><h2 ref={title} tabIndex={-1}>Inspect this moment</h2></div><button type="button" className="ibtn" aria-label="Close moment inspection" onClick={onClose}>×</button></header>
    <nav className="inspection-steps" aria-label="Moment inspection steps">{steps.map(([id, label], index) => <button key={id} type="button" aria-pressed={step === id} onClick={() => onStep(id)}><span aria-hidden="true">0{index + 1}</span>{label}</button>)}</nav>
    <EvidenceFlow label={`Moment · ${step}`} identity={`${generation.sha256}:${run.record.run.run_id}:${step}`}>
    {row ? <>
      <MomentClock row={row} />
      <div className="inspection-body">
      {step === "capture" ? <>
        <div className="inspection-context"><span>Recorded observations</span><Choice label="Inspection observation target" value={target} onChange={value => onTarget(value as ObservationTarget)} options={[{ value: "eef", label: "End effector" }, { value: "cube", label: "Cube" }]} /></div>
        <div className="inspection-measures"><Measure label="Consumed age" value={row.observation_age_s === null ? null : row.observation_age_s * 1000} unit="ms" /><Measure label={`${target === "eef" ? "Tool" : "Cube"} observation separation`} value={pair.distance === null ? null : pair.distance * 1000} unit="mm" /></div>
        <p className="inspection-explanation">{groups.length === 1 ? `${groups[0]!.names.length} components share the capture stamp.` : groups.length > 1 ? `${groups.reduce((sum, group) => sum + group.names.length, 0)} components have ${groups.length} capture stamps; the clock marks each one.` : "Component capture stamps were not recorded."} {pair.distance === null ? "The observation pair is unavailable." : `The markers compare consumed and current ${target === "eef" ? "tool" : "cube"} observations.`}</p>
      </> : null}
      {step === "command" ? <>
        <div className="inspection-context"><span>Normalized command</span><Choice label="Inspection action component" value={String(component)} onChange={value => setComponent(Number(value))} options={row.intended_action.map((_, index) => ({ value: String(index), label: actionLabel(index) }))} /></div>
        <div className="inspection-command"><div><span>Intended</span><strong className="num">{intended == null ? "Not recorded" : signed(intended)}</strong></div><span className="command-arrow" aria-hidden="true">→</span><div><span>Executed</span><strong className="num">{executed == null ? "Not recorded" : signed(executed)}</strong></div></div>
        <p className="inspection-explanation">At {fixed(row.action_sim_time_s)} s · component {component}. Original policy output and recorded execution. The adapter clips normalized actions before execution; this is not an actuator torque reading.</p>
        <p className="fine">The scene’s target frame is the controller goal retained with the selected {moment.phase} configuration at {fixed(frameTime)} s. Axis lengths are a display convention; the connector shows positional tracking error.</p>
      </> : null}
      {step === "result" ? <>
        <div className="inspection-context"><span>Original post-action reading</span><span className="num">{fixed(row.next_sim_time_s)} s</span></div>
        <div className="inspection-measures"><Measure label="Cube height" value={row.cube_height_m} unit="m" digits={6} /><div><span>Declared height condition</span><strong className="num">&gt; {caseRecord.predicates.min_cube_height_m.toFixed(2)}<small> m</small></strong></div></div>
        <p className="inspection-explanation">The height condition {row.cube_height_m > caseRecord.predicates.min_cube_height_m ? "holds" : "does not hold"} at this sample. Whole-run task outcome: <strong>{run.record.task_outcome}</strong>. Review the comparison and decision records for what the experiment establishes.</p>
      </> : null}
      </div>
      <div className="inspection-source"><span>Robot: {moment.phase} configuration · <span className="num">{fixed(frameTime)} s</span></span><a href={source} target="_blank" rel="noreferrer" title={`SHA-256 ${run.record.samples.sha256} · /rows/${row.row_index}`}>Source row {row.row_index} ↗</a></div>
      <div className="inspection-actions">{step === "capture" ? <button type="button" className="quiet inspection-next" onClick={() => onStep("command")}>Inspect command <span aria-hidden="true">→</span></button> : step === "command" ? <button type="button" className="quiet inspection-next" onClick={() => onStep("result")}>Inspect result <span aria-hidden="true">→</span></button> : <><button type="button" className="quiet" onClick={onCompare}>Compare recordings</button><button type="button" className="quiet" onClick={onDecision}>Decision <span aria-hidden="true">↗</span></button></>}</div>
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
