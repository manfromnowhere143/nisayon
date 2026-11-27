import { useEffect, useState } from "react";
import { SceneDetail } from "../ui/SceneDetail";
import { Icon } from "../ui/Icon";
import { transferBytes } from "../data/transfer";
import { strictParseJson } from "../data/strictJson";
import { sha256Hex } from "../data/digest";
import { BRAIN_PREVIEW } from "./brainPreview";
import { brainRow, decodeBrainInspection, type BrainInspection as Packet, type BrainRow, type BrainTrace } from "./brainData";
import "../styles/brain-inspection.css";

type Perspective = "Observe" | "Decide" | "Act" | "Evidence";
export function BrainInspection({ onClose, origin }: { onClose: () => void; origin: HTMLElement | null }) {
  const [packet, setPacket] = useState<Packet | null>(null), [error, setError] = useState("");
  const [role, setRole] = useState<"candidate" | "privileged">("candidate");
  const [index, setIndex] = useState(0), [playing, setPlaying] = useState(false);
  const [perspective, setPerspective] = useState<Perspective>("Decide");
  useEffect(() => {
    const abort = new AbortController();
    void transferBytes(BRAIN_PREVIEW.path, (url, init) => fetch(url, init), { signal: abort.signal, maxBytes: 3_000_000, timeoutMs: 12000 }).then(async bytes => {
      if (await sha256Hex(bytes) !== BRAIN_PREVIEW.sha256) throw Error("Brain 01 evidence failed its source digest");
      const data = decodeBrainInspection(strictParseJson(new TextDecoder("utf-8", { fatal: true }).decode(bytes)));
      if (!abort.signal.aborted) setPacket(data);
    }).catch(e => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, []);
  const baseline = packet?.traces.find(t => t.role === "baseline"), comparison = packet?.traces.find(t => t.role === role);
  const rows = baseline && comparison ? Math.max(baseline.rows.length, comparison.rows.length) : 0;
  const b = baseline ? brainRow(baseline, index) : null, c = comparison ? brainRow(comparison, index) : null;
  const decision = comparison?.rows.find(r => r.decision_time_s !== null)?.decision_time_s;
  const seek = (next: number) => { setPlaying(false); setIndex(Math.max(0, Math.min(rows - 1, next))); };
  useEffect(() => {
    if (!playing || rows < 2) return;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    if (preference.matches) { setPlaying(false); return; }
    const start = performance.now(), first = index;
    let raf = 0;
    const advance = () => {
      if (document.hidden) { setPlaying(false); return; }
      const next = Math.min(rows - 1, first + Math.floor((performance.now() - start) / 80));
      setIndex(next);
      if (next === rows - 1) setPlaying(false); else raf = requestAnimationFrame(advance);
    };
    raf = requestAnimationFrame(advance);
    const stop = () => setPlaying(false);
    preference.addEventListener("change", stop);
    return () => { cancelAnimationFrame(raf); preference.removeEventListener("change", stop); };
    // Capture the exact starting tick once, without restarting the clock per row.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, rows]);
  return <>
    <SceneDetail floating title="Brain 01" caption="G1 reference · retained simulation" className="brain-inspection" returnFocus={origin} onClose={onClose} exclude=".ricci-canvas, .brain-transport">
      {!packet && !error ? <p role="status">Verifying the retained experiment…</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {packet && baseline && comparison ? <>
        <nav className="brain-perspectives" aria-label="Scientific inspection">
          {(["Observe", "Decide", "Act", "Evidence"] as const).map(name => <button key={name} type="button" aria-pressed={perspective === name} onClick={() => setPerspective(name)}>{name}</button>)}
        </nav>
        <div className="brain-comparison"><span>Baseline /</span><select aria-label="Comparison policy" value={role} onChange={e => { setRole(e.target.value as typeof role); setPlaying(false); setIndex(0); }}><option value="candidate">Candidate</option><option value="privileged">Privileged diagnostic</option></select></div>
        {perspective !== "Evidence" ? <table className="brain-readings"><caption className="sr-only">Exact readings at control tick {index}</caption><thead><tr><th>Signal</th><th>Baseline</th><th>{role === "candidate" ? "Candidate" : "Diagnostic"}</th></tr></thead><tbody>
          {perspective === "Observe" ? <>
            <Reading title="Acquired" a={b} b={c} value={r => r.observation ? seconds(r.observation.acquired_s) : "Unavailable"}/>
            <Reading title="Delivered" a={b} b={c} value={r => r.observation ? seconds(r.observation.delivered_s) : "Unavailable"}/>
            <Reading title="Contact · left / right" a={b} b={c} value={r => r.estimate?.contact_reliable.map(v => v ? "accepted" : "rejected").join(" / ") ?? "Unavailable"}/>
            <Reading title="Right knee" a={b} b={c} value={r => r.observation?.valid[1] ? `${r.observation.joint_rad.toFixed(3)} rad` : "Unavailable"}/>
          </> : perspective === "Decide" ? <>
            <Reading title="Hypothesis" a={b} b={c} value={r => plain(r.belief.mode)}/>
            <Reading title="Action" a={b} b={c} value={r => plain(r.action)}/>
            <Reading title="Optimization" a={b} b={c} value={r => r.controller.status}/>
            <Reading title="Admission" a={b} b={c} value={r => plain(r.guard.mode)}/>
          </> : <>
            <Reading title="Knee · issued" a={b} b={c} value={r => `${r.issued_nm.toFixed(2)} N m`}/>
            <Reading title="Knee · applied" a={b} b={c} value={r => `${r.applied_nm.toFixed(2)} N m`}/>
            <Reading title="Torso tilt" a={b} b={c} value={r => `${r.after.torso_tilt_rad.toFixed(3)} rad`}/>
            <Reading title="Physical reading" a={b} b={c} value={r => seconds(r.after.t_s)}/>
          </>}
        </tbody></table> : null}
        {perspective === "Observe" ? <details><summary>Sensor validity</summary><p className="brain-note">IMU / joints / feet / wrists. Missing observations remain unavailable. Contact acceptance belongs to the estimator.</p><table className="brain-readings"><tbody><Reading title="Valid channels" a={b} b={c} value={r => r.observation?.valid.map(v => v ? "yes" : "no").join(" / ") ?? "Unavailable"}/></tbody></table></details> : null}
        {perspective === "Decide" ? <details><summary>Residuals and computation</summary><p className="brain-note">Compatibility scores, not probabilities. Smaller values indicate a closer residual fit under the declared hypothesis bank.</p><table className="brain-readings"><tbody>
          {["nominal", "unreliable_support", "moving_load"].map(key => <Reading key={key} title={plain(key)} a={b} b={c} value={r => r.belief.scores?.[key]?.toFixed(2) ?? "Unavailable"}/>)}
          <Reading title="Host solve" a={b} b={c} value={r => r.controller.solve_wall_s == null ? "Unavailable" : `${(r.controller.solve_wall_s * 1000).toFixed(2)} ms`}/>
          <Reading title="Constraint residual" a={b} b={c} value={r => r.controller.normalized_constraint_residual?.toExponential(2) ?? "Unavailable"}/>
          <Reading title="Admission reasons" a={b} b={c} value={r => r.guard.reasons.join(", ") || "None recorded"}/>
        </tbody></table></details> : null}
        {perspective === "Act" ? <><BrainPlot baseline={baseline} comparison={comparison} index={index}/><p className="brain-note">Issued commands enter the next 20 ms interval. The physical sample follows the applied command. No pose interpolation.</p></> : null}
        {perspective === "Evidence" ? <>
          <p className="brain-finding">{role === "candidate" ? "Both executions fail this case." : "The privileged diagnostic completes this case."}</p>
          <p className="brain-note">{packet.interpretation}</p>
          <details><summary>Outcomes and timing</summary><table className="brain-readings"><tbody>{[baseline, comparison].map(t => <tr key={t.role}><th>{t.role}</th><td colSpan={2}>{plain(t.outcome.outcome)}<br/>{t.outcome.constraint_violations.join(", ") || "No declared constraint violation"}</td></tr>)}</tbody></table><p className="brain-note">First applied torque difference ≥ 0.1 N m: {comparison.first_different_applied_s == null ? "none retained" : seconds(comparison.first_different_applied_s)}. This is distinct from the first physical effect. No qualified safe stop or hardware capability is established.</p></details>
          <details className="brain-provenance"><summary>Source and reproduction</summary><p>{packet.comparison}. {packet.replay}.</p><p>{packet.coordinate_frame}.</p>{[baseline, comparison].map(t => <div key={t.role}><p>{t.episode}</p><code>Episode {t.manifest_sha256}</code><code>Source {t.source_commit}</code><code>Model {t.model_sha256}</code><code>Inspection {t.projection_sha256}</code></div>)}<a href={BRAIN_PREVIEW.path} download>Download the inspected readings</a></details>
        </> : null}
        <p className="brain-boundary">Ricci’s body is conceptual. Recorded signals belong to the G1 reference.</p>
      </> : null}
    </SceneDetail>
    {packet && comparison ? <section className="brain-transport" aria-label="Recorded Brain timeline">
      <p>Brain 01 · exact retained ticks · replay 0.25×</p>
      <div className="brain-time-controls">
        <button type="button" aria-label={playing ? "Pause Brain replay" : "Play Brain replay"} onClick={() => {
          if (matchMedia("(prefers-reduced-motion: reduce)").matches) { seek(index + 1); return; }
          if (index === rows - 1) setIndex(0); setPlaying(v => !v);
        }}><Icon name={playing ? "pause" : "play"}/></button>
        <label><span className="sr-only">Brain control tick</span><input className="scene-scrubber" type="range" min={0} max={rows - 1} step={1} value={index} onChange={e => seek(Number(e.target.value))}/></label>
        <output>{(index * .02).toFixed(2)} s</output>
      </div>
      <nav className="brain-events" aria-label="Recorded events"><button type="button" onClick={() => seek(0)}>Reset</button><button type="button" onClick={() => seek(Math.round(packet.onset_s / .02))}>Perturbation</button>{decision != null ? <button type="button" onClick={() => seek(Math.round(decision / .02))}>Decision</button> : null}<button type="button" onClick={() => seek(comparison.rows.length - 1)}>Final sample</button></nav>
    </section> : null}
  </>;
}
function plain(s: string) { return s.replaceAll("_", " "); }
function seconds(n: number) { return `${n.toFixed(3)} s`; }
function Reading({ title, a, b, value }: { title: string; a: BrainRow | null; b: BrainRow | null; value: (r: BrainRow) => string }) {
  return <tr><th>{title}</th><td>{a ? value(a) : "Execution ended"}</td><td>{b ? value(b) : "Execution ended"}</td></tr>;
}
function BrainPlot({ baseline, comparison, index }: { baseline: BrainTrace; comparison: BrainTrace; index: number }) {
  const traces = [baseline, comparison], max = Math.max(...traces.flatMap(t => t.rows.map(r => r.after.torso_tilt_rad)), .01);
  const end = Math.max(...traces.map(t => t.rows.at(-1)!.after.t_s));
  const x = (t: number) => 20 + 320 * t / end, y = (v: number) => 78 - 56 * v / max;
  return <svg className="brain-plot" viewBox="0 0 360 102" role="img" aria-label="Retained torso tilt against physical simulation time; baseline and comparison. Lines end with their execution.">
    <path d="M20 16v62h320" fill="none" stroke="currentColor" opacity=".25"/><text x="20" y="10">Torso tilt · {max.toFixed(2)} rad</text><text x="20" y="98">0</text><text x="306" y="98">{end.toFixed(1)} s</text>
    {traces.map((t, i) => <g key={t.role} className={i === 0 ? "brain-reference" : "brain-candidate"}><path fill="none" stroke="currentColor" strokeWidth="1.6" strokeDasharray={i === 0 ? "4 3" : undefined} d={t.rows.map((r, j) => `${j ? "L" : "M"}${x(r.after.t_s).toFixed(2)},${y(r.after.torso_tilt_rad).toFixed(2)}`).join(" ")}/>{t.rows[index] ? <circle cx={x(t.rows[index]!.after.t_s)} cy={y(t.rows[index]!.after.torso_tilt_rad)} r="3" fill="currentColor"/> : null}</g>)}
  </svg>;
}
