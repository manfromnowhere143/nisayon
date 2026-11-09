import { EvidenceFlow } from "./EvidenceFlow";
import { GlassCard } from "../research/GlassCard";
// The accessible DOM inspector: every reading on the canvas resolves here to
// the same generation, bundle, run, row and phase, with its digests.

import { createContext, useContext, useState } from "react";
import type { LoadIssue, LoadedRun } from "../data/loader";
import { actionLabel, firstActionMismatch, signed, timeForPhase } from "../model/findings";
import { shortSha, type CaseRecord, type Generation, type Moment } from "../model/types";
import { useStore } from "../state/useStore";
import { VISUAL_ASSET } from "../scene/visualAssetPin";
import { Icon } from "./Icon";
import { PagedFacts } from "./RecordPages";
import { shortUrl } from "./RunSelector";
import { bodyDepth, bodyLabel } from "../model/spatial";

interface Props {
  generation: Generation;
  caseRecord: CaseRecord;
  run: LoadedRun;
  moment: Moment;
  open: boolean;
}

const InspectorSection = createContext("Selection");
const INSPECTOR_SECTIONS = ["Selection", "Model bodies", "Actions at this row", "Original readings", "Reconstruction", "Policy memory", "Run status", "Display geometry", "Sources", "Keys"];

export function Inspector({ generation, caseRecord, run, moment, open }: Props) {
  const store = useStore();
  const [section, setSection] = useState("Selection");
  if (!open) return null;

  const row = run.samples.rows[moment.row_index] ?? null;
  const frame = run.frames?.rows[moment.row_index]?.[moment.phase] ?? null;
  const mismatch = firstActionMismatch(run.samples.rows);
  const exported = caseRecord.findings.find((f) => f.run.run_id === run.record.run.run_id && f.run.bundle_sha256 === run.record.run.bundle_sha256);
  const observation = row ? (moment.phase === "before" ? row.observation : row.next_observation) : null;
  const link = store.currentUrl();
  const maxima = run.frames?.maximum_residuals ?? null;
  const originalCubeZ = row ? (moment.phase === "before" ? (row.observation?.cube_pos[2] ?? null) : row.cube_height_m) : null;

  return (
    <GlassCard title="Source inspector" eyebrow="RETAINED EVIDENCE" wide onClose={() => store.toggleInspector(false)}><aside id="inspector" className="inspector" aria-labelledby="inspector-heading">
      <div className="inspector-bar">
        <h2 id="inspector-heading" className="inspector-title">
          Inspector
        </h2>
        <button type="button" className="ibtn" aria-label="Close inspector" onClick={() => store.toggleInspector(false)}>
          <Icon name="close" />
        </button>
      </div>

      <label className="panel-select"><span>Inspect</span><select aria-label="Inspector section" value={section} onChange={(event) => setSection(event.target.value)}>{INSPECTOR_SECTIONS.map((name) => <option key={name}>{name}</option>)}</select></label>
      <div className="inspector-content"><InspectorSection.Provider value={section}>
      <Section title="Selection">
        <PagedFacts label="Inspector details">
          <Fact k="generation" v={generation.sha256} mono />
          <Fact k="case" v={`${caseRecord.case_key} · ${caseRecord.case_id}`} />
          <Fact k="bundle" v={moment.run.bundle_sha256} mono />
          <Fact k="run" v={`${moment.run.run_id} · ${run.record.role} · plan ${run.record.plan_id} · condition ${run.record.condition_id}`} />
          <Fact k="row" v={row ? `${row.row_index} (step ${row.step}) of 0 to ${run.record.row_count - 1}` : `${moment.row_index}: no sample; recording ends at row ${run.record.row_count - 1}`} />
          <Fact k="phase" v={moment.phase === "before" ? "before the action: retained configuration; the consumed observation may be older" : "after the action: stored configuration and reading at the next sample"} />
          <Fact k="clock" v={row ? `simulation · ${timeForPhase(row, moment.phase).toFixed(6)} s (action ${row.action_sim_time_s.toFixed(6)} s, next ${row.next_sim_time_s.toFixed(6)} s)` : "simulation"} />
          {row && row.locators.pointer ? <Fact k="source locator" v={`${String(row.locators.source_id ?? "")} ${String(row.locators.pointer ?? "")}${row.locators.raw_line !== null && row.locators.raw_line !== undefined ? ` · raw line ${String(row.locators.raw_line)} of ${String(row.locators.raw_source_id ?? "")}` : ""}`} mono /> : null}
          <Fact k="link" v={<input className="link-field mono" readOnly value={link} aria-label="Pinned link to this moment" onFocus={(e) => e.currentTarget.select()} />} />
        </PagedFacts>
      </Section>

      <Section title="Model bodies">
        {run.model ? <><p className="fine">Select a recorded body. The selection is included in the shared link; the camera stays in place.</p><ul className="body-tree" aria-label="Model body hierarchy">{run.model.bodies.map((body) => <li key={body.index} style={{ paddingInlineStart: bodyDepth(run.model!, body.index) * 8 }}><button type="button" aria-pressed={store.getState().part?.name === body.name} onClick={() => store.selectPart(body.name)}><span>{bodyLabel(body.name)}</span><code>{body.name}</code></button></li>)}</ul></> : <p className="fine">Model unavailable.</p>}
      </Section>

      {row ? (
        <Section title="Actions at this row">
          <table className="actions">
            <thead>
              <tr>
                <th scope="col">component</th>
                <th scope="col" className="num">
                  intended
                </th>
                <th scope="col" className="num">
                  executed
                </th>
              </tr>
            </thead>
            <tbody>
              {row.intended_action.map((v, i) => {
                const e = row.executed_action[i] ?? Number.NaN;
                const differs = v !== e;
                return (
                  <tr key={i} className={differs ? "differs" : undefined}>
                    <th scope="row">
                      {i} · {actionLabel(i)}
                    </th>
                    <td className="num">{signed(v)}</td>
                    <td className="num">{signed(e)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="fine">
            Rows compared exactly (tolerance 0). Browser-computed first mismatch:{" "}
            <span className="num">{mismatch ? `row ${mismatch.row_index}, component ${mismatch.component}` : "none"}</span>
            {exported ? (
              <>
                {" "}
                · export's finding <span className="mono">{exported.code}</span>: <span className="num">{exported.row_index !== null ? `row ${exported.row_index}` : "none"}</span> ({exported.definition}
                {exported.threshold !== null ? `, threshold ${exported.threshold}` : ""})
              </>
            ) : (
              " · no export finding for this run"
            )}
            .
          </p>
        </Section>
      ) : null}

      {row ? (
        <Section title={`Original readings · ${moment.phase}`}>
          <PagedFacts label="Inspector details">
            <Fact k="cube height (post-action reading)" v={`${row.cube_height_m.toFixed(9)} m at ${row.next_sim_time_s.toFixed(6)} s`} />
            <Fact k="task success at this row" v={String(row.task_success)} />
            {observation ? (
              <>
                <Fact k="end-effector position" v={observation.robot0_eef_pos.map((x) => x.toFixed(6)).join(", ")} />
                <Fact k="end-effector quaternion (xyzw)" v={observation.robot0_eef_quat.map((x) => x.toFixed(6)).join(", ")} />
                <Fact k="gripper joint positions" v={observation.robot0_gripper_qpos.map((x) => x.toFixed(6)).join(", ")} />
                <Fact k="cube position" v={observation.cube_pos.map((x) => x.toFixed(6)).join(", ")} />
              </>
            ) : (
              <Fact k="observation" v="not published for this phase" />
            )}
            <Fact k="consumed observation captured at" v={row.consumed_observation_capture_sim_time_s !== null ? `${row.consumed_observation_capture_sim_time_s.toFixed(6)} s` : "not published"} />
            <Fact k="observation age" v={row.observation_age_s !== null ? `${row.observation_age_s.toFixed(6)} s (declared maximum ${caseRecord.predicates.max_observation_age_s} s)` : "not published"} />
            <Fact k="inference wall (host clock)" v={row.inference_wall_host_s !== null ? `${(row.inference_wall_host_s * 1000).toFixed(3)} ms` : "not published"} />
          </PagedFacts>
        </Section>
      ) : null}

      <Section title="Reconstruction">
        {frame ? (
          <PagedFacts label="Inspector details">
            <Fact k="source" v={`retained configuration → ${String(run.frames?.derivation.method ?? "mj_kinematics")} (MuJoCo ${String(run.frames?.derivation.mujoco_version ?? "3.2.7")}); source-bound display surfaces when qualified; schematic fallback`} />
            <Fact k="stored time" v={`${frame.sim_time_s.toFixed(6)} s`} />
            {frame.state_sha256 ? <Fact k="state digest" v={frame.state_sha256} mono /> : null}
            <Fact k="derived cube z" v={frame.derived_cube_z_m !== null ? `${frame.derived_cube_z_m.toFixed(9)} m` : "no cube body in the model"} />
            <Fact k={moment.phase === "before" ? "original cube z (consumed observation)" : "original cube height (post-action reading)"} v={originalCubeZ !== null ? `${originalCubeZ.toFixed(9)} m` : "not published"} />
            <Fact
              k="residual at this row"
              v={`${frame.residual_cube_height_m !== null ? `${frame.residual_cube_height_m.toExponential(3)} m cube height` : "cube height: not defined before the action"} · ${frame.residual_eef_m !== null ? `${frame.residual_eef_m.toExponential(3)} m end-effector (max coordinate)` : "end-effector: not published"}`}
            />
            <Fact k="grip site (derived)" v={Number.isFinite(frame.grip_site_xpos[0]) ? frame.grip_site_xpos.map((x) => x.toFixed(6)).join(", ") : "not published"} />
            <Fact k="retained maxima (this run)" v={maxima ? `${fmt(maxima.cube_height_difference_m)} m cube · ${fmt(maxima.eef_coordinate_difference_m)} m end-effector; not a tolerance` : "—"} />
          </PagedFacts>
        ) : (
          <p className="fine">
            {run.framesIssue ? `Frames unavailable: ${run.framesIssue.message} (${shortUrl(run.framesIssue.url)}).` : "No frame at this row."} Original readings above remain valid.
          </p>
        )}
      </Section>

      {row ? (
        <Section title="Policy memory">
          <PagedFacts label="Inspector details">
            <Fact k="telemetry" v={row.policy.availability} />
            <Fact k="episode reset" v={row.policy.episode_reset === null ? "not published per row" : String(row.policy.episode_reset)} />
            <Fact k="reset before this inference" v={String(row.policy.reset_before_inference)} />
            <Fact k="state before" v={row.policy.before === "present" ? "present" : row.policy.before === "initialized_none" ? "initialized None (episode boundary; not unavailable telemetry)" : "unavailable telemetry"} />
            <Fact k="state after" v={row.policy.after === "present" ? "present" : row.policy.after === "initialized_none" ? "initialized None" : "unavailable telemetry"} />
            {row.policy.counter_before !== null ? <Fact k="counter" v={`${row.policy.counter_before} → ${row.policy.counter_after ?? "—"}`} /> : null}
            <Fact k="state digest before" v={row.policy.state_before_sha256 ?? "none"} mono />
            <Fact k="state digest after" v={row.policy.state_after_sha256 ?? "none"} mono />
            <Fact k="episode reset (run)" v={run.record.policy_reset ? JSON.stringify(run.record.policy_reset) : "not published"} mono />
          </PagedFacts>
          <p className="fine">Digest equality is exact byte equality of the serialized state. It measures nothing else.</p>
        </Section>
      ) : null}

      <Section title="Run status">
        <PagedFacts label="Inspector details">
          <Fact k="process" v={run.record.process_status} />
          <Fact k="measurement" v={run.record.measurement_status} />
          <Fact k="task outcome" v={run.record.task_outcome} />
          <Fact k="execution" v={`${run.record.execution_mode} · ${run.record.evidence_origin}`} />
          <Fact k="candidate" v={run.record.candidate_sha256 ?? "—"} mono />
          <Fact k="configuration" v={run.record.configuration_sha256 ?? "—"} mono />
          <Fact k="constraint violations" v={run.record.constraint_violations.length ? JSON.stringify(run.record.constraint_violations) : "none recorded"} />
          <Fact
            k="costs"
            v={
              run.record.costs.length
                ? run.record.costs.map((c) => `${c.category}: ${c.value === null ? `unknown (${c.missing_reason ?? "no reason"})` : `${c.value.toFixed(3)} ${c.unit ?? ""}`}`).join("; ")
                : "none recorded"
            }
          />
        </PagedFacts>
      </Section>

      <Section title="Display geometry">
        <PagedFacts label="Inspector details">
          <Fact k="optional package" v={<a href={VISUAL_ASSET.path} target="_blank" rel="noreferrer">{VISUAL_ASSET.sha256}</a>} mono />
          <Fact k="binding" v="The detailed model is shown only when its model digest, body order and source asset digests match this generation." />
          <Fact k="presentation" v="Retained shapes and poses; illustrative materials, lighting and shadows. Foreground room walls cut away for inspection." />
          <Fact k="attribution" v={<a href="/fixtures/ui/visual/ROBOSUITE-LICENSE.txt" target="_blank" rel="noreferrer">robosuite 1.4.1 · retained license</a>} />
        </PagedFacts>
      </Section>
      <Section title="Sources">
        <PagedFacts label="Inspector details">
          <Fact k="manifest" v={`${shortUrl(generation.manifestUrl)} · ${generation.sha256}`} mono />
          <Fact k="samples" v={`${run.record.samples.path} · ${run.record.samples.sha256} · ${run.record.samples.byte_length} bytes`} mono />
          <Fact k="frames" v={run.record.frames ? `${run.record.frames.path} · ${run.record.frames.sha256} · ${run.record.frames.byte_length} bytes` : "none"} mono />
          {run.record.sources.map((s) => (
            <Fact key={s.path} k={s.kind} v={`${s.path} · ${s.sha256}`} mono />
          ))}
          {generation.source_bindings.map((b) => (
            <Fact key={b.kind + b.path} k={b.kind} v={`${b.path} · ${shortSha(b.sha256)} · ${b.binding}`} mono />
          ))}
        </PagedFacts>
        <p className="fine">{generation.label ?? `adapter ${String(generation.adapter.name ?? "")}`}</p>
        <ul className="plain fine">
          {[...generation.limitations, ...caseRecord.limitations, ...(run.model?.limitations ?? [])].map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </Section>
      <Section title="Keys">
        <PagedFacts label="Keyboard shortcuts">
          <Fact k="← →" v="previous / next row (Shift: ten rows)" />
          <Fact k="Home End" v="first / last row" />
          <Fact k="Space" v="play / pause recorded rows" />
          <Fact k="M" v="go to the described finding" />
          <Fact k="P" v="before / after phase" />
          <Fact k="R" v="next recorded run, matching simulation time when available" />
          <Fact k="V" v="next camera view" />
          <Fact k="I" v="inspector" />
          <Fact k="T" v="black / paper ground" />
          <Fact k="Esc" v="close inspector, then back to the parent depth" />
          <Fact k="D" v="diagnostics (measured timings)" />
        </PagedFacts>
      </Section>
      </InspectorSection.Provider></div>
    </aside></GlassCard>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const selected = useContext(InspectorSection);
  return (
    <section className="inspector-section" hidden={!title.startsWith(selected)}>
      <h3 className="inspector-section-title">{title}</h3>
      <EvidenceFlow label={title}>{children}</EvidenceFlow>
    </section>
  );
}

function Fact({ k, v, mono = false }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt>{k}</dt>
      <dd className={mono ? "mono" : "num"}>{v}</dd>
    </div>
  );
}

function fmt(v: unknown): string {
  return typeof v === "number" ? v.toExponential(3) : "—";
}

export function issueTitle(issue: LoadIssue): string {
  switch (issue.kind) {
    case "integrity":
      return "Bytes do not match the manifest";
    case "absent":
      return "A required file is missing";
    case "unsupported-schema":
      return "Unknown schema version";
    case "decode":
      return "The file could not be decoded";
    case "digest-unavailable":
      return "Digest verification unavailable";
    case "network":
      return "The file could not be fetched";
    case "aborted":
      return "Load superseded";
    default:
      return "Load failed";
  }
}
