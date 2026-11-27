import { useLayoutEffect, useState } from "react";
import type { LoadedRun } from "../data/loader";
import type { Generation, Moment } from "../model/types";
import { acquisitionGroups, bodyLabel, bodyPose, observationPair, type ObservationTarget, type SpatialPose } from "../model/spatial";
import { useStore } from "../state/useStore";
import { PhysicalInspector } from "./PhysicalInspector";
import { Choice } from "./Choice";
import { EvidenceFlow } from "./EvidenceFlow";

interface Props { run: LoadedRun; generation: Generation; moment: Moment; body: number | null; partSelected?: boolean; target: ObservationTarget; onTarget: (target: ObservationTarget) => void; pathActive: boolean; pathSeconds: number | null; onPathSeconds: (seconds: number | null) => void }
const number = (value: number | null | undefined, digits = 3) => value == null ? "Not recorded" : value.toFixed(digits);

export function SpatialPanel({ run, generation, moment, body, partSelected = false, target, onTarget, pathActive, pathSeconds, onPathSeconds }: Props) {
  const store = useStore();
  const [coordinates, setCoordinates] = useState(partSelected ? "body" : "consumed");
  const [detail, setDetail] = useState(partSelected ? "coordinates" : "comparison");
  useLayoutEffect(() => {
    setDetail(partSelected ? "coordinates" : "comparison");
    setCoordinates(partSelected ? "body" : "consumed");
  }, [body, partSelected]);
  const row = run.samples.rows[moment.row_index] ?? null;
  const frame = run.frames?.rows[moment.row_index]?.[moment.phase] ?? null;
  const pair = observationPair(row, target);
  const selected = body === null ? null : run.model?.bodies[body];
  const pose = bodyPose(frame, body);
  const capture = row?.consumed_acquisition ?? null, acquired = row?.latest_acquisition ?? null;
  const groups = acquisitionGroups(capture);
  const source = new URL(run.record.samples.path, generation.baseUrl).href;
  const consumedRow = run.samples.rows.find((r) => r.step === row?.observation_step);
  const concrete = generation.schema === "nisayon.ui-generation.v1";
  const observationField = target === "eef" ? "robot0_eef_pos" : concrete ? "object" : "cube_pos";
  const valuePaths = concrete
    ? ["observation", "captured_observation"].map((name) => `/rows/${row?.row_index}/observations/${name}/${observationField}`)
    : [`/rows/${row?.row_index}/observation/${observationField}`];
  return <section className="spatial-panel" aria-label="Spatial inspection">
    <div className="spatial-heading"><div><p className="eyebrow">Recorded space</p><h2 tabIndex={-1}>{selected ? bodyLabel(selected.name) : "Observation comparison"}</h2></div><Choice className="spatial-detail" label="Spatial detail" value={detail} onChange={setDetail} options={[{ value: "comparison", label: "Comparison" }, { value: "coordinates", label: "Coordinates" }, { value: "physical", label: "Joints & controller" }, { value: "timing", label: "Acquisition" }, { value: "sources", label: "Sources" }]} /></div>
    {detail === "coordinates" ? <Choice label="Coordinate source" value={coordinates} onChange={setCoordinates} options={[{ value: "body", label: "Body origin" }, { value: "consumed", label: "Consumed observation" }, { value: "acquired", label: "Acquired at action" }, { value: "fingers", label: "Finger coordinates" }]} /> : null}
    {detail === "physical" ? <PhysicalInspector run={run} generation={generation} moment={moment} body={partSelected ? body : null} onSelect={(row, phase) => store.selectSample(row, phase)} /> : <EvidenceFlow label={`Spatial · ${detail}`} identity={`${generation.sha256}:${run.record.run.run_id}:${detail}:${body}:${detail === "coordinates" ? coordinates : ""}`}>
    {row ? <>
      <div className="spatial-context"><span className="num">Step {row.step} · action {number(row.action_sim_time_s)} s</span><Choice label="Observation target" value={target} onChange={value => onTarget(value as ObservationTarget)} options={[{ value: "eef", label: "End effector" }, { value: "cube", label: "Cube" }]} /></div>
      {detail === "comparison" ? <>
        <div className="spatial-metrics">
          <div><span>{target === "eef" ? "End-effector" : "Cube"} observation displacement</span><strong className="num">{number(pair.distance === null ? null : pair.distance * 1000)}{pair.distance !== null ? <small> mm</small> : null}</strong></div>
          <div><span>Consumed age at action</span><strong className="num">{number(row.observation_age_s === null ? null : row.observation_age_s * 1000)}{row.observation_age_s !== null ? <small> ms</small> : null}</strong></div>
        </div>
        <div className="observation-cards">
          <div><h3><i className="key-consumed" />Consumed</h3><p className="num">{number(capture?.oldest_sim_time_s ?? row.consumed_observation_capture_sim_time_s)}{(capture?.oldest_sim_time_s ?? row.consumed_observation_capture_sim_time_s) !== null ? " s" : ""}</p><span>step {row.observation_step ?? "unknown"}</span></div>
          <div><h3><i className="key-acquired" />Acquired at action</h3><p className="num">{number(acquired?.oldest_sim_time_s)}{acquired ? " s" : ""}</p><span>{acquired ? `step ${acquired.step}` : "Acquisition stamp unavailable"}</span></div>
        </div>
        <p className="spatial-explanation">Recorded task outcome: <strong>{run.record.task_outcome}</strong>. Markers compare {target === "eef" ? "end-effector" : "cube"} observations at this action. The robot shows the <strong>{moment.phase}</strong> configuration at <span className="num">{number(frame?.sim_time_s)} s</span>.</p>
        {pathActive ? <div className="path-window"><span>{selected ? bodyLabel(selected.name) : "Body"} path</span><Choice label="Configuration path history" value={String(pathSeconds ?? "all")} onChange={value => onPathSeconds(value === "all" ? null : Number(value))} options={[{ value: "1", label: "Last 1 second" }, { value: "3", label: "Last 3 seconds" }, { value: "all", label: "Full recorded history" }]} /></div> : null}
        <div className="spatial-actions"><button type="button" className="quiet" disabled={moment.phase === "before"} onClick={() => store.selectSample(row.row_index, "before")}>Before this action</button><button type="button" className="quiet" disabled={!consumedRow || consumedRow.row_index === row.row_index} onClick={() => consumedRow && store.selectSample(consumedRow.row_index, "before")}>Go to consumed step {row.observation_step ?? "—"}</button></div>
      </> : null}
      {detail === "coordinates" ? <>
        <p className="fine">World frame · metres · Z up. Observation quaternions are shown in their recorded x, y, z, w order.</p>
        {coordinates === "body" ? pose ? <div className="spatial-pose"><h3>{bodyLabel(selected!.name)} · configuration {moment.phase}</h3><CoordinateValues position={pose.position} /><p className="fine">Body origin, not an observation or a sensor reading.</p></div> : <p className="fine">Body configuration unavailable.</p> : null}
        {coordinates === "consumed" ? <PoseValues label="Consumed observation" pose={pair.consumed} /> : null}
        {coordinates === "acquired" ? <PoseValues label="Acquired at action" pose={pair.acquired} /> : null}
        {coordinates === "fingers" ? <div className="spatial-pose"><h3>Consumed finger coordinates</h3>{row.observation ? <><p className="num">{row.observation.robot0_gripper_qpos.map(v => `${v.toFixed(6)} m`).join(" · ")}</p><details><summary>Exact retained values</summary><code>{JSON.stringify(row.observation.robot0_gripper_qpos)}</code></details></> : <p className="fine">Not recorded</p>}</div> : null}
      </> : null}
      {detail === "timing" ? <>
        <p className="fine">Capture → action, on the recording’s simulation clock. Components with identical stamps share an interval.</p>
        <CaptureIntervals groups={groups} action={row.action_sim_time_s} end={run.samples.rows.at(-1)?.next_sim_time_s ?? row.next_sim_time_s} />
        {!groups.length ? <p className="fine">Component acquisition stamps were not recorded.</p> : <dl className="acquisition-components">{groups.map((group) => <div key={group.time}><dt>{group.names.length} components · <span className="num">{number(group.time, 6)} s → {number(row.action_sim_time_s, 6)} s</span></dt><dd>{group.names.join(" · ")}</dd></div>)}</dl>}
        <p className="fine">Latest acquisition: <span className="num">{number(acquired?.oldest_sim_time_s, 6)}{acquired ? " s" : ""}</span>. These are retained stamps, not a live connection.</p>
      </> : null}
      {detail === "sources" ? <>
        <div className="spatial-source"><h3>Observation values & acquisition stamps</h3><a href={source} target="_blank" rel="noreferrer">Open verified sample object</a><code>{run.record.samples.sha256}</code>{valuePaths.map((path) => <code key={path}>{path}</code>)}{target === "cube" && concrete ? <p className="fine">Object array: position at indices 0–2; orientation at 3–6.</p> : null}{concrete ? <><code>/rows/{row.row_index}/original/observation_capture</code><code>/rows/{row.row_index}/original/captured_observation_capture</code></> : null}</div>
        <div className="spatial-source"><h3>Original record</h3><code>{String(row.locators.source_id ?? "Source locator unavailable")}{row.locators.pointer ? ` ${row.locators.pointer}` : ""}</code>{row.locators.raw_source_id ? <code>{String(row.locators.raw_source_id)} · line {String(row.locators.raw_line)}</code> : null}</div>
        {run.record.frames && run.record.model ? <div className="spatial-source"><h3>Configuration · {moment.phase}</h3><a href={new URL(run.record.frames.path, generation.baseUrl).href} target="_blank" rel="noreferrer">Open reconstruction</a><code>{concrete ? `/frames/${moment.row_index * 2 + (moment.phase === "after" ? 1 : 0)}/bodies${body === null ? "" : `/${body}`}` : `/rows/${moment.row_index}/${moment.phase}/xpos`}</code><a href={new URL(run.record.model.path, generation.baseUrl).href} target="_blank" rel="noreferrer">Open model</a><code>{selected?.name ?? "No body selected"} · {run.record.model.sha256}</code></div> : null}
      </> : null}
    </> : !row ? <p className="fine">No recorded sample at this row.</p> : null}
    </EvidenceFlow>}
  </section>;
}

function PoseValues({ label, pose }: { label: string; pose: SpatialPose | null }) {
  return <div className="spatial-pose"><h3>{label}</h3>{pose ? <CoordinateValues position={pose.position} quaternion={[...pose.quaternion.slice(1), pose.quaternion[0]]} /> : <p className="fine">Pose unavailable or orientation invalid.</p>}</div>;
}

function CoordinateValues({ position, quaternion }: { position: number[]; quaternion?: number[] }) {
  return <><dl className="coordinate-grid">{position.map((v, i) => <div key={i}><dt>{["X", "Y", "Z"][i]}</dt><dd className="num">{v.toFixed(6)} <small>m</small></dd></div>)}</dl>{quaternion ? <p className="fine num">q [x y z w] · {quaternion.map(v => v.toFixed(5)).join(" · ")}</p> : null}<details><summary>Exact retained values</summary><code>position: {JSON.stringify(position)}</code>{quaternion ? <code>quaternion [x y z w]: {JSON.stringify(quaternion)}</code> : null}</details></>;
}

export function CaptureIntervals({ groups, action, end }: { groups: ReturnType<typeof acquisitionGroups>; action: number; end: number }) {
  const x = (time: number) => 12 + time / Math.max(end, 0.05) * 376;
  return <svg className="capture-intervals" viewBox={`0 0 400 ${42 + groups.length * 30}`} role="img" aria-label={groups.map((group) => `${group.names.length} components acquired at ${group.time} s, consumed at ${action} s`).join("; ") || "No acquisition intervals"}>
    <line x1="12" x2="388" y1="18" y2="18" className="interval-axis" /><text x="12" y="11">0.00 s</text><text x="388" y="11" textAnchor="end">{end.toFixed(2)} s</text>
    {groups.map((group, i) => <g key={group.time} data-capture={group.time} data-action={action}><line x1={x(group.time)} x2={x(action)} y1={32 + i * 30} y2={32 + i * 30} /><line x1={x(group.time)} x2={x(group.time)} y1={27 + i * 30} y2={37 + i * 30} /><line x1={x(action)} x2={x(action)} y1={27 + i * 30} y2={37 + i * 30} /><text x="12" y={54 + i * 30}>{group.names.length} components · {((action - group.time) * 1000).toFixed(3)} ms</text></g>)}
  </svg>;
}
