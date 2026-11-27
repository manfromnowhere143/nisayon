import { useState } from "react";
import type { LoadedRun } from "../data/loader";
import type { Generation, Moment } from "../model/types";
import { bodyLabel } from "../model/spatial";
import { Choice } from "./Choice";
import { SectionDeck } from "./RecordPages";
import { PhysicalHistory, physicalSamples } from "./PhysicalHistory";

const n = (value: number | undefined, digits = 5) => value === undefined ? "Not recorded" : value.toFixed(digits);

function RangeReading({ value, range, unit }: { value: number; range: [number, number] | null; unit: string }) {
  const outside = range && (value < range[0] || value > range[1]);
  const atLimit = range && (value === range[0] || value === range[1]);
  return <div className="physical-range"><strong className="num">{n(value)} <small>{unit}</small></strong>{range ? <><div className="physical-scale" role="img" aria-label={`${value} ${unit}; declared range ${range[0]} to ${range[1]}${outside ? "; outside range" : atLimit ? "; at limit" : ""}`}><i style={{ left: `${Math.max(0, Math.min(100, (value - range[0]) / (range[1] - range[0] || 1) * 100))}%` }} /></div><div className="physical-range-ends num"><span>{n(range[0], 3)}</span><span>{outside ? "Outside range" : atLimit ? "At declared limit" : "Declared range"}</span><span>{n(range[1], 3)}</span></div></> : <p className="fine">No limit declared.</p>}</div>;
}

export function PhysicalInspector({ run, generation, moment, body, onSelect }: { run: LoadedRun; generation: Generation; moment: Moment; body: number | null; onSelect?: (row: number, phase: Moment["phase"]) => void }) {
  const [jointName, setJointName] = useState("");
  const frame = run.frames?.rows[moment.row_index]?.[moment.phase];
  const physical = frame?.physical, model = run.model;
  if (!physical || !model?.joints) return <p className="depth-note">This pinned generation does not publish joint and controller state. Open the current export to inspect the extended retained readings.</p>;
  const available = model.joints.filter(j => (body === null || j.body === body) && ["hinge", "slide"].includes(j.type));
  const selected = available.find(j => j.name === jointName) ?? available[0];
  const actuators = model.actuators?.filter(a => a.joint === selected?.id) ?? [];
  const goal = physical.goal_pos;
  const gap = goal && frame ? Math.hypot(...goal.map((v, i) => v - frame.grip_site_xpos[i]!)) : null;
  const source = run.record.frames ? new URL(run.record.frames.path, generation.baseUrl).href : null;
  return <section className="physical-inspector" aria-label="Retained joint and controller state"><p className="fine">{moment.phase} configuration · {n(frame?.sim_time_s, 3)} s. Read directly from retained state; no motion interpolation or physics rerun.</p>
    {available.length > 1 ? <Choice label="Retained joint" value={selected?.name ?? ""} options={available.map(j => ({ value: j.name, label: `${bodyLabel(model.bodies[j.body]!.name)} · ${j.name}` }))} onChange={setJointName} /> : null}
    <SectionDeck label="Physical readings" sections={[
      { id: "joint", label: "Joint", content: selected ? <>
        <PhysicalHistory samples={physicalSamples(run.frames, moment.phase, f => f.physical?.qpos[selected.qposAddress])} moment={moment} label="Joint position" unit={selected.type === "hinge" ? "rad" : "m"} range={selected.range} onSelect={onSelect} />
        <article className="physical-joint"><div className="physical-joint-title"><h3>{bodyLabel(model.bodies[selected.body]!.name)}</h3><span>{selected.name}</span></div><RangeReading value={physical.qpos[selected.qposAddress]!} range={selected.range} unit={selected.type === "hinge" ? "rad" : "m"} /><div className="physical-velocity"><span>Velocity</span><strong className="num">{n(physical.qvel[selected.dofAddress])} {selected.type === "hinge" ? "rad" : "m"}/s</strong></div></article>
      </> : <p className="fine">No scalar joint is attached to this body. Select an arm link or finger to inspect its joint.</p> },
      { id: "control", label: "Control", content: actuators.length ? <>{actuators.map(actuator => <article key={actuator.id} className="physical-actuator"><p className="eyebrow">{actuator.kind} · {actuator.name}</p><PhysicalHistory samples={physicalSamples(run.frames, moment.phase, f => f.physical?.ctrl[actuator.id])} moment={moment} label={actuator.kind === "motor" ? "Applied control input" : "Servo position target"} unit={actuator.unit} range={actuator.controlRange} onSelect={onSelect} /><RangeReading value={physical.ctrl[actuator.id]!} range={actuator.controlRange} unit={actuator.unit} />{actuator.forceRange ? <p className="fine">Declared actuator force range: {actuator.forceRange.join(" to ")} {selected?.type === "hinge" ? "N m" : "N"}. This is a limit, not a measured force.</p> : null}</article>)}</> : <p className="fine">No actuator is bound to this selection.</p> },
      { id: "goal", label: "Goal", content:
    <article className="physical-controller"><p className="eyebrow">Controller goal / end effector</p><h3>Tracking at this configuration</h3><div className="spatial-metrics"><div><span>Position residual</span><strong className="num">{gap === null ? "Not recorded" : n(gap * 1000, 3)}{gap !== null ? <small> mm</small> : null}</strong></div></div><p className="fine">Descriptive distance from the retained goal position to the reconstructed grip site. It is not a task-acceptance tolerance.</p>
      <table className="physical-coordinates"><caption>World coordinates · metres · Z up</caption><thead><tr><th>Frame</th><th>X</th><th>Y</th><th>Z</th></tr></thead><tbody><tr><th>Goal</th>{[0, 1, 2].map(i => <td className="num" key={i}>{n(goal?.[i])}</td>)}</tr><tr><th>Grip site</th>{frame?.grip_site_xpos.map((v, i) => <td className="num" key={i}>{n(v)}</td>)}</tr></tbody></table>
      {physical.goal_ori ? <details><summary>Retained goal orientation</summary><table className="physical-coordinates"><caption>3 × 3 rotation matrix</caption><tbody>{physical.goal_ori.map((r, i) => <tr key={i}>{r.map((v, j) => <td className="num" key={j}>{n(v)}</td>)}</tr>)}</tbody></table></details> : <p className="fine">No goal orientation recorded.</p>}
    </article> },
      { id: "source", label: "Source", content: <>{source ? <a className="physical-source fine" href={source} target="_blank" rel="noreferrer">State source · frame {2 * moment.row_index + (moment.phase === "after" ? 1 : 0)} · {moment.phase}</a> : null}<p className="fine mono">State {frame?.state_sha256}</p><p className="fine">Configuration {moment.phase} · {n(frame?.sim_time_s, 3)} s. Joint limits and actuator ranges are model declarations. They are not measured contact forces.</p></> },
    ]} />
  </section>;
}
