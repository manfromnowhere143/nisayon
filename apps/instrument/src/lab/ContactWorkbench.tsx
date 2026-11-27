import { useEffect, useMemo, useRef, useState } from "react";
import { SceneDetail } from "../ui/SceneDetail";
import { sha256Hex } from "../data/digest";
import { transferBytes } from "../data/transfer";
import { strictParseJson } from "../data/strictJson";
import { CONTACT_PREVIEW } from "./contactPreview";
import { contactPair, decodeContactPacket, labRequest, type ContactCapabilities, type ContactExperiment, type ContactPacket, type ContactView } from "./contactData";
import "../styles/contact-workbench.css";

export function ContactWorkbench({ open, onClose, origin, onView }: {
  open: boolean; onClose: () => void; origin: HTMLElement | null;
  onView: (active: boolean, value: ContactView | null) => void;
}) {
  const [caps, setCaps] = useState<ContactCapabilities | null>(null);
  const [packet, setPacket] = useState<ContactPacket | null>(null);
  const [parameters, setParameters] = useState<Record<string, number>>({});
  const [validated, setValidated] = useState<ContactExperiment | null>(null);
  const [section, setSection] = useState<"protocol" | "measurements" | "decision">("measurements");
  const [condition, setCondition] = useState<"low" | "high">("low"), [index, setIndex] = useState(0);
  const [forces, setForces] = useState(true), [playing, setPlaying] = useState(false);
  const [error, setError] = useState(""), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [run, setRun] = useState<string | null>(null), [progress, setProgress] = useState("");
  const [executing, setExecuting] = useState(false);
  const live = useRef(true), onViewRef = useRef(onView); onViewRef.current = onView;
  const instrument = caps?.instruments.find(i => i.id === "contact");
  const view = useMemo(() => packet ? { packet, condition, index, forces } : null, [packet, condition, index, forces]);
  const pair = view ? contactPair(view) : null;
  const rows = Math.max(pair?.reference?.rows.length ?? 0, pair?.candidate?.rows.length ?? 0);
  const current = pair?.candidate?.rows[index], reference = pair?.reference?.rows[index];

  useEffect(() => {
    live.current = true;
    const controller = new AbortController();
    void labRequest("/api/lab/capabilities", { signal: controller.signal }).then(value => {
      const c = value as ContactCapabilities;
      if (c.schema !== "nisayon.lab.capabilities.v1" || typeof c.session !== "string" || !Array.isArray(c.instruments)) return;
      const contact = c.instruments.find(i => i.id === "contact");
      if (!contact || contact.default?.spec.protocol.schema !== "nisayon.lab.contact.v1") return;
      if (live.current) { setCaps(c); setParameters(contact.default.spec.parameters); }
    }).catch(() => { /* Retained review remains available without a local executor. */ });
    void transferBytes(CONTACT_PREVIEW.path, (url, init) => fetch(url, init), { signal: controller.signal, maxBytes: 2_000_000, timeoutMs: 12000 }).then(async bytes => {
      if (await sha256Hex(bytes) !== CONTACT_PREVIEW.sha256) throw new Error("Retained contact example failed its source digest");
      const value = decodeContactPacket(strictParseJson(new TextDecoder().decode(bytes)));
      if (live.current) { setPacket(value); setParameters(old => Object.keys(old).length ? old : value.experiment.spec.parameters); }
    }).catch(error => { if (live.current && !controller.signal.aborted) setError(String(error)); })
      .finally(() => { if (live.current) setLoading(false); });
    return () => { live.current = false; controller.abort(); };
  }, []);
  useEffect(() => { onViewRef.current(open, view); }, [open, view, onView]);
  useEffect(() => () => onViewRef.current(false, null), []);
  useEffect(() => { if (!open) setPlaying(false); }, [open]);
  useEffect(() => {
    if (!playing || !open || rows < 2) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    if (motion.matches) { setPlaying(false); return; }
    const started = performance.now(), initial = index;
    let raf = 0;
    const frame = () => {
      // 0.1x replay of exact samples. Rendering never invents physical poses.
      const next = Math.min(rows - 1, initial + Math.floor((performance.now() - started) * .1 / 5));
      setIndex(next);
      if (next === rows - 1) setPlaying(false); else raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    const stop = () => setPlaying(false);
    motion.addEventListener("change", stop);
    return () => { cancelAnimationFrame(raf); motion.removeEventListener("change", stop); };
    // Starting a play captures the row; frame updates must not reset its clock.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, open, rows]);

  const validate = async () => {
    if (!caps) return;
    setError(""); setBusy(true);
    try {
      const value = await labRequest("/api/lab/validate", { session: caps.session, body: parameters }) as ContactExperiment;
      if (value.spec?.schema !== "nisayon.lab.experiment.v1" || !/^[a-f0-9]{64}$/.test(value.experiment_id)) throw new Error("Invalid validation response");
      if (live.current) setValidated(value);
    } catch (error) { if (live.current) setError(String(error)); }
    finally { if (live.current) setBusy(false); }
  };
  const execute = async () => {
    if (!caps || !validated) return;
    setError(""); setBusy(true); setExecuting(true); setRun(null); setPlaying(false); setPacket(null); setSection("measurements"); setIndex(0);
    try {
      let job = await labRequest("/api/lab/runs", { session: caps.session, body: { parameters: validated.spec.parameters, expected_id: validated.experiment_id } }) as { id: string; status: string; progress?: { measurements: number; expected_measurements: number }; error?: string };
      if (!/^[a-f0-9]{32}$/.test(job.id)) throw new Error("Invalid execution identity");
      setRun(job.id);
      const started = performance.now();
      while (job.status === "queued" || job.status === "running") {
        if (!live.current) return;
        setProgress(job.progress ? `${job.progress.measurements} / ${job.progress.expected_measurements} measurements retained` : "Preparing the declared experiment");
        if (performance.now() - started > 20000) throw new Error(`Status connection timed out. Execution ${job.id} remains in the local service.`);
        await new Promise(resolve => setTimeout(resolve, 250));
        job = await labRequest(`/api/lab/runs/${job.id}`) as typeof job;
      }
      if (job.error) throw new Error(job.error);
      const evidence = decodeContactPacket(await labRequest(`/api/lab/runs/${job.id}/packet`));
      if (evidence.experiment.experiment_id !== validated.experiment_id) throw new Error("Execution returned a different experimental identity");
      if (live.current) { setPacket(evidence); setProgress(""); }
    } catch (error) { if (live.current) setError(String(error)); }
    finally { if (live.current) { setBusy(false); setExecuting(false); } }
  };
  if (!open) return null;
  return <SceneDetail floating title="Contact dynamics" kind="reading" className="contact-workbench" caption={busy ? "Local execution" : packet ? "Retained simulation · research preview" : "Research preview"} returnFocus={origin} onClose={onClose}>
    <nav className="contact-sections" aria-label="Contact experiment">
      {(["protocol", "measurements", "decision"] as const).map(id => <button key={id} type="button" aria-pressed={section === id} onClick={() => setSection(id)}>{id[0]!.toUpperCase()+id.slice(1)}</button>)}
    </nav>
    {loading ? <p role="status">Verifying the retained contact experiment…</p> : null}
    {error ? <p role="alert" className="contact-error">{error}</p> : null}
    {busy ? <div role="status"><p>{progress || (executing ? "Preparing the declared experiment" : "Validating the experiment")}</p>{executing && run && caps ? <button type="button" onClick={() => void labRequest(`/api/lab/runs/${run}/cancel`, { session: caps.session, body: {} }).catch(e => setError(String(e)))}>Cancel execution</button> : null}</div> : null}
    {section === "protocol" ? <>
      <p>Does changed motion come from contact friction or force interpretation? Compare two prescribed force levels from the same initial state.</p>
      {instrument ? <form onSubmit={event => { event.preventDefault(); void validate(); }}>
        <fieldset disabled={busy || !instrument.executable} className="contact-parameters"><legend>Controlled variables</legend>
          {Object.entries(instrument.parameters_schema.properties).map(([name, field]) => <label key={name}><span>{field.title}</span><span className="contact-input"><input type="number" required aria-label={field.title} min={field.minimum} max={field.maximum} step={field.multipleOf ?? "any"} value={Number.isFinite(parameters[name]) ? parameters[name] : ""} onChange={event => { const value = event.currentTarget.valueAsNumber; setValidated(null); setParameters(p => ({...p, [name]: value})); }}/><span>{field.unit}</span></span></label>)}
        </fieldset>
        <div className="contact-actions"><button type="submit" disabled={busy || !instrument.executable}>Validate protocol</button><button type="button" disabled={!validated || busy || !instrument.executable} onClick={() => void execute()}>Execute locally</button></div>
        {validated ? <p className="contact-note">Validated <code title={validated.experiment_id}>{validated.experiment_id.slice(0,16)}</code>. Editing any parameter requires validation again.</p> : null}
      </form> : <>
        <p className="contact-note">This site can inspect retained evidence. Execution requires the local Nisayon native environment.</p>
        <code className="contact-command">uv run --frozen --group native python -m nisayon.lab serve --frontend apps/instrument/dist</code>
        {packet ? <dl className="contact-facts">{Object.entries(packet.experiment.spec.parameters).map(([key,value]) => <div key={key}><dt>{key.replaceAll("_"," ")}</dt><dd>{value}</dd></div>)}</dl> : null}
      </>}
      <details><summary>Fixed model and limits</summary><p>Guided rigid slider, known mass, MuJoCo 3.3.2 soft contact. Physics at 1 ms; retained measurements at 5 ms. No learned controller, hardware sensor or autonomous experiment selection.</p><p>The two inputs are prescribed. Effective friction and gain are conditional fits of mean motion. Instantaneous contact forces remain visible, including solver variation.</p></details>
    </> : null}
    {section === "measurements" && packet ? <>
      <div className="contact-condition" role="group" aria-label="Controlled force"><span>Applied command</span>{(["low","high"] as const).map(c => <button key={c} type="button" aria-pressed={condition===c} onClick={() => { setCondition(c); setIndex(0); setPlaying(false); }}>{packet.experiment.spec.parameters[c+"_force_n"]} N</button>)}</div>
      <ContactTracePlot view={view!} />
      <div className="contact-playback"><button type="button" aria-label={playing ? "Pause contact replay" : "Play contact replay at one tenth speed"} aria-pressed={playing} disabled={rows<2} onClick={() => { if (index===rows-1) setIndex(0); setPlaying(v=>!v); }}>{playing ? "Pause" : "Play 0.1×"}</button><label><span className="sr-only">Contact measurement row</span><input type="range" min={0} max={Math.max(0,rows-1)} value={index} onChange={event=>{setPlaying(false);setIndex(Number(event.target.value));}} /></label><output>{(current?.t_s ?? reference?.t_s)?.toFixed(3) ?? "—"} s</output></div>
      <p className="contact-note">Exact row {index}. Blue: reference. Sand: candidate. Each trace is a separate physical execution from the matched reset.</p>
      <dl className="contact-facts"><div><dt>Candidate position</dt><dd>{format(current?.x_m,4)} m</dd></div><div><dt>Reference position</dt><dd>{format(reference?.x_m,4)} m</dd></div><div><dt>Applied motor force</dt><dd>{format(current?.applied_n,3)} N</dd></div><div><dt>Contact force, travel</dt><dd>{format(current?.contact_x_n,3)} N</dd></div><div><dt>Normal contact force</dt><dd>{format(current?.normal_n,3)} N</dd></div></dl>
      <label className="contact-layer"><input type="checkbox" checked={forces} onChange={event=>setForces(event.target.checked)}/>Contact and motor-force vectors</label>
      <p className="contact-note">The track scale marks 0.1 m from reset. Vectors use 0.02 m per N. Forces are simulated; the scene is not a camera observation. No pose interpolation.</p>
    </> : null}
    {section === "decision" && packet ? <>
      <p className="contact-verdict">{packet.result.qualification.verdict === "supported" ? "Within the declared tolerance" : packet.result.qualification.verdict === "rejected" ? "Displacement changed" : "Qualification unresolved"}</p>
      <p>{packet.result.qualification.scope}.</p>
      <p className="contact-note">Kernel result: {packet.result.qualification.verdict}. Deployment remains unresolved. Execution: {packet.result.status}.</p>
      <table className="contact-estimates"><caption>Conditional mean-motion fit</caption><thead><tr><th>System</th><th>Force gain</th><th>Effective friction</th></tr></thead><tbody>{(["reference","candidate"] as const).map(role=><tr key={role}><th>{role}</th><td>{format(packet.analysis.estimates[role].gain,3)}</td><td>{format(packet.analysis.estimates[role].effective_friction,3)}</td></tr>)}</tbody></table>
      <p>One force level cannot independently identify both quantities under the stated model. The second level supplies additional excitation. This exposed example establishes neither autonomous discovery nor external engineering savings.</p>
      {packet.result.error ? <p>{packet.result.error}</p> : null}
    </> : null}
    {packet ? <details className="contact-provenance"><summary>Source and reproduction</summary><p>Experiment <code>{packet.experiment.experiment_id}</code></p><p>Packet <code>{packet.packet_sha256}</code></p><p>Protocol <code>{packet.experiment.spec.protocol_sha256}</code></p><p>Integrity checked by the local reader; declared relations recomputed by the qualification kernel. Hashes do not establish physical truth.</p>{run ? <a href={`/api/lab/runs/${run}/export`} download>Export complete evidence packet</a> : <a href={CONTACT_PREVIEW.archive} download>Download retained example and reproduction source</a>}</details> : null}
  </SceneDetail>;
}

function format(value: number | null | undefined, digits: number) { return value == null ? "Unavailable" : value.toFixed(digits); }
function ContactTracePlot({ view }: { view: ContactView }) {
  const pair = contactPair(view), traces = [pair.reference, pair.candidate];
  const maxTime = Math.max(.005,...traces.flatMap(t=>t?.rows.map(r=>r.t_s) ?? []));
  const maxVelocity = Math.max(.05,...traces.flatMap(t=>t?.rows.map(r=>r.v_m_s) ?? []));
  const x = (t:number) => 26+314*t/maxTime, y=(v:number)=>124-102*v/maxVelocity;
  return <svg className="contact-trace" viewBox="0 0 360 154" role="img" aria-label={`Retained reference and candidate velocity against simulation time, ${view.condition} force condition`}>
    <path d="M26 12v112h314" fill="none" stroke="currentColor" opacity=".25"/>
    <text x="26" y="9">{maxVelocity.toFixed(2)} m/s</text><text x="26" y="145">0</text><text x="305" y="145">{maxTime.toFixed(2)} s</text>
    {traces.map((trace,i)=>trace ? <g key={trace.role} stroke={i===0?"#93bdd4":"#d9b784"}><path fill="none" strokeWidth="1.7" d={trace.rows.map((r,j)=>`${j?"L":"M"}${x(r.t_s).toFixed(2)},${y(r.v_m_s).toFixed(2)}`).join(" ")}/>{trace.rows[view.index] ? <circle cx={x(trace.rows[view.index]!.t_s)} cy={y(trace.rows[view.index]!.v_m_s)} r="3.4" fill="currentColor" strokeWidth="1.5"/> : null}</g>:null)}
  </svg>;
}
