import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { GlassCard } from "../research/GlassCard";
import { associate, associateExplanation, ProjectionError, readbackCommands, type CheckSummary, type DependencyExplanation, type MeasurementReview } from "./projection";
import { openProjection, readExampleBytes, type Imported, type ProjectionSelection } from "./projectionClient";
import { PROJECTION_EXAMPLES } from "./projectionExamples";
import { DependencyInspector } from "./DependencyInspector";
import { ProjectionPages as Pages } from "./ProjectionPages";
import "../styles/projections.css";

const words = (s: string) => s.replaceAll("_", " ");
const checkStatus = (c: CheckSummary["checks"][number]) => c.status === "completed" ? c.attempted === "reuse" ? "Reused" : "Executed" : words(c.status);
const reviewTitle = (r: MeasurementReview | null) => !r ? "Measurement review not attached" : r.status === "claim_mismatch" ? "The saved claim disagrees" : !r.assessment ? "No complete assessment" : r.assessment.verdict === "supported" ? "The recorded relation holds" : r.assessment.verdict === "rejected" ? "The recorded relation fails" : "Measurement meaning is unresolved";
type Issue = { kind: string; message: string };
const issueOf = (error: unknown): Issue => ({ kind: error instanceof ProjectionError ? error.kind : "read error", message: error instanceof Error ? error.message : "The record could not be loaded." });
const time = (s: string | null) => s === null ? "Not recorded" : `${s} s`;

function Source({ selection }: { selection: ProjectionSelection }) {
  const [path, setPath] = useState("/path/to/checks.zip"), [copied, setCopied] = useState("");
  const s = selection.summary.value, r = selection.measurement?.value ?? null;
  const e = selection.explanation?.value ?? null, commands = readbackCommands(s, r, path, e);
  const example = PROJECTION_EXAMPLES.find(row => row.id === selection.example);
  return <div className="projection-detail"><p>The browser checked JSON shape and, for examples, the retained file pin. The recorded checker has not run in this browser. A matching pair establishes record consistency, not authenticity.</p>
    <dl className="projection-identities"><dt>Imported summary file</dt><dd>{selection.summary.name}</dd><dt>Archive SHA-256</dt><dd>{s.source.bundle}</dd><dt>Model SHA-256</dt><dd>{s.source.model}</dd><dt>Recorded checker SHA-256</dt><dd>{s.source.checker}</dd><dt>Imported summary SHA-256</dt><dd>{selection.summary.sha256}</dd>{selection.measurement ? <><dt>Imported measurement review SHA-256</dt><dd>{selection.measurement.sha256}</dd></> : null}{e && selection.explanation ? <><dt>Imported explanation SHA-256</dt><dd>{selection.explanation.sha256}</dd><dt>Recorded applicability file SHA-256</dt><dd>{e.source.applicability}</dd><dt>Recorded previous-state file SHA-256</dt><dd>{e.source.previousRecord}</dd><dt>Previous model SHA-256</dt><dd>{e.previousModel}</dd></> : null}</dl>
    {example ? <dl className="projection-identities"><dt>Example source commit · curator metadata</dt><dd>{example.sourceCommit}</dd></dl> : null}
    <h3>Recheck with the compatible engine</h3><p>Use the original archive and the checker matching the identity above. The projection does not contain the archive or authenticate its producer.</p>
    <label className="projection-path">Your local archive path<input value={path} maxLength={2048} onChange={event => { setPath(event.target.value); setCopied(""); }} spellCheck={false} /></label>
    {commands.map((command, i) => <div className="projection-command" key={i}><pre>{command}</pre><button onClick={() => { if (!navigator.clipboard) { setCopied("Select and copy the command manually."); return; } void navigator.clipboard.writeText(command).then(() => setCopied(`Command ${i + 1} copied`)).catch(() => setCopied("Select and copy the command manually.")); }}>Copy command {i + 1}</button></div>)}<span role="status">{copied}</span>
    <p>Commands are text to run yourself. The browser has no shell connection. {e ? "The attached explanation supplies declared edges; their consistency does not authenticate the original archive." : "The summary does not include the dependency graph. A compatible explanation can supply it."} Historical archives require their recorded checker, even when a newer engine supports the same schema.</p>
  </div>;
}

export default function ProjectionReview({ selection, setSelection, archives, heading: externalHeading }: { selection: ProjectionSelection | null; setSelection: (v: ProjectionSelection | null) => void; archives: () => void; heading?: RefObject<HTMLHeadingElement | null> }) {
  const [busy, setBusy] = useState(false), [issue, setIssue] = useState<Issue | null>(null), [panel, setPanel] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null), localHeading = useRef<HTMLHeadingElement>(null), pending = useRef<AbortController | null>(null), retry = useRef<(() => void) | null>(null);
  const heading = externalHeading ?? localHeading;
  const latest = useRef(selection); latest.current = selection;
  const begin = () => { pending.current?.abort(); const controller = new AbortController(); pending.current = controller; setBusy(true); setIssue(null); setPanel(null); return controller; };
  const current = (controller: AbortController) => pending.current === controller && !controller.signal.aborted;
  useLayoutEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  useEffect(() => () => pending.current?.abort(), []);
  const clearExampleLink = () => { const params = new URLSearchParams(location.hash.slice(1)); params.delete("record"); history.replaceState(null, "", `${location.pathname}${location.search}#${params}`); };

  async function loadFiles(files: File[]) {
    const controller = begin(); retry.current = () => void loadFiles(files);
    try {
      if (!files.length || files.length > 3) throw new ProjectionError("capacity", "Choose one summary, one explanation and one measurement review at most.");
      const results = await Promise.allSettled(files.map(file => openProjection(file, controller.signal)));
      if (!current(controller)) return;
      const imported = results.flatMap(r => r.status === "fulfilled" ? [r.value] : []), failures = results.filter(r => r.status === "rejected");
      const summaries = imported.filter((r): r is Imported<CheckSummary> => r.value.kind === "summary"), reviews = imported.filter((r): r is Imported<MeasurementReview> => r.value.kind === "measurement"), explanations = imported.filter((r): r is Imported<DependencyExplanation> => r.value.kind === "explanation");
      if (summaries.length > 1 || reviews.length > 1 || explanations.length > 1) throw new ProjectionError("invalid", "Choose at most one record of each role; duplicate roles were refused.");
      const summary = summaries[0] ?? latest.current?.summary;
      if (!summary) { if (failures[0]) throw failures[0].reason; throw new ProjectionError("association", "Open a summary before attaching an explanation or measurement review."); }
      if (summaries[0]) { setSelection({ summary, measurement: null, explanation: null, example: null }); clearExampleLink(); }
      if (failures[0]) throw failures[0].reason;
      const measurement = reviews[0] ?? (summaries[0] ? null : latest.current?.measurement ?? null);
      const explanation = explanations[0] ?? (summaries[0] ? null : latest.current?.explanation ?? null);
      if (measurement) associate(summary.value, measurement.value);
      if (explanation) associateExplanation(summary.value, explanation.value, measurement?.value);
      setSelection({ summary, measurement, explanation, example: null }); clearExampleLink();
      retry.current = null;
    } catch (error) { if (current(controller)) setIssue(issueOf(error)); }
    finally { if (current(controller)) setBusy(false); }
  }
  async function loadExample(id: string) {
    const controller = begin(); retry.current = () => void loadExample(id);
    const deadline = setTimeout(() => { if (current(controller)) { setIssue({ kind: "read error", message: "The example did not load within ten seconds. Retry or open local JSON." }); setBusy(false); controller.abort(); } }, 10_000);
    try {
      const example = PROJECTION_EXAMPLES.find(e => e.id === id);
      if (!example) throw new ProjectionError("unsupported", "This recorded example is not available. No substitute has been selected.");
      const load = async (record: { file: string; sha256: string }) => {
        const response = await fetch(`${import.meta.env.BASE_URL}examples/check-records/${record.file}`, { signal: controller.signal });
        if (!response.ok) throw new Error("The recorded example is unavailable. Retry or open local JSON.");
        // Static, pinned examples only. User imports never enter a fetch URL.
        const bytes = await readExampleBytes(response);
        return openProjection(new File([bytes], record.file, { type: "application/json" }), controller.signal, record.sha256);
      };
      const [summary, measurement, explanation] = await Promise.all([load(example.summary), example.measurement ? load(example.measurement) : Promise.resolve(null), example.explanation ? load(example.explanation) : Promise.resolve(null)]);
      if (!current(controller)) return;
      if (summary.value.kind !== "summary" || measurement && measurement.value.kind !== "measurement" || explanation && explanation.value.kind !== "explanation") throw new ProjectionError("invalid", "The example files have conflicting roles.");
      if (measurement) associate(summary.value, measurement.value as MeasurementReview);
      if (explanation) associateExplanation(summary.value, explanation.value as DependencyExplanation, measurement?.value as MeasurementReview | undefined);
      setSelection({ summary: summary as Imported<CheckSummary>, measurement: measurement as Imported<MeasurementReview> | null, explanation: explanation as Imported<DependencyExplanation> | null, example: example.id }); retry.current = null;
    } catch (error) { if (current(controller)) { setIssue(issueOf(error)); setBusy(false); controller.abort(); } }
    finally { clearTimeout(deadline); if (current(controller)) setBusy(false); }
  }
  const exampleLoader = useRef(loadExample); exampleLoader.current = loadExample;
  useEffect(() => {
    const navigate = () => {
      const params = new URLSearchParams(location.hash.slice(1)), id = params.get("record");
      if (params.getAll("record").length > 1) { pending.current?.abort(); setBusy(false); setIssue({ kind: "invalid", message: "This link contains conflicting example selections." }); return; }
      if (id && id !== latest.current?.example) void exampleLoader.current(id);
    };
    navigate(); window.addEventListener("popstate", navigate); window.addEventListener("hashchange", navigate);
    return () => { window.removeEventListener("popstate", navigate); window.removeEventListener("hashchange", navigate); };
  }, []);
  const selectExample = (id: string) => {
    if (!id) return;
    const params = new URLSearchParams(location.hash.slice(1)); params.set("view", "checks"); params.set("record", id);
    history.pushState(null, "", `${location.pathname}${location.search}#${params}`); void loadExample(id);
  };
  const s = selection?.summary.value, r = selection?.measurement?.value ?? null, e = selection?.explanation?.value ?? null, example = PROJECTION_EXAMPLES.find(e => e.id === selection?.example);
  const completed = s?.checks.filter(c => c.status === "completed") ?? [], reused = completed.filter(c => c.attempted === "reuse");
  return <main id="research-content" className="qualification-workspace projection-workspace" aria-label="Recorded engine checks">
    <input ref={picker} type="file" accept=".json,application/json" multiple className="sr-only" tabIndex={-1} aria-label="Choose summary, optional explanation and measurement JSON" onChange={event => { const files = Array.from(event.target.files ?? []); event.target.value = ""; if (files.length) void loadFiles(files); }} />
    <div className="projection-top"><button className="research-text-action" onClick={archives}>← Library</button><span>RECORDED ENGINE EVIDENCE</span></div>
    <div className="qualification-heading"><div><p className="research-micro">EXECUTION / DEPENDENCIES / CLAIM</p><h1 ref={heading} tabIndex={-1}>The record and the claim.</h1></div><button className="research-action" onClick={() => picker.current?.click()}>Open local JSON </button></div>
    <div className="projection-load"><label>Study a recorded example<select value={selection?.example ?? ""} onChange={event => selectExample(event.target.value)}><option value="" disabled>Choose an example</option>{[...new Set(PROJECTION_EXAMPLES.map(e => e.group))].map(group => <optgroup key={group} label={group}>{PROJECTION_EXAMPLES.filter(e => e.group === group).map(e => <option key={e.id} value={e.id}>{e.title}</option>)}</optgroup>)}</select></label><p>Summary v1 · explanation v1 · measurement review v1<br />Local imports stay in this browser.</p></div>
    {busy ? <div className="review-message" role="status">Reading and checking JSON… <button onClick={() => { pending.current?.abort(); setBusy(false); }}>Cancel import</button></div> : null}
    {issue ? <div className="review-message projection-error" role="alert"><div><strong>{issue.kind === "association" ? "Companion not attached" : issue.kind === "capacity" ? "Consumer capacity limit" : "Record not accepted"}</strong><p>{issue.message}</p>{selection ? <small>The selected summary remains readable.</small> : null}</div><button onClick={() => retry.current?.()}>Retry</button><button onClick={() => setIssue(null)}>Dismiss</button></div> : null}
    {s ? <>
      <section className="projection-verdict" data-status={r?.status ?? "absent"} aria-label="Recorded result">
        <div><p className="research-micro">{r ? "RECORDED MEASUREMENT REVIEW" : "EXECUTION SUMMARY"}</p><h2>{reviewTitle(r)}</h2>{r?.status === "claim_mismatch" ? <div className="projection-claim"><span>Saved <strong>{r.recorded}</strong></span><span aria-hidden="true">→</span><span>Recomputed <strong>{r.assessment?.verdict}</strong></span></div> : <p>{r?.assessment ? "The compatible engine reported this relation over the captured records." : r ? "The execution remains unresolved; its prefix results are not a complete assessment." : "The process record is available. A handler's saved claim has not been semantically assessed here."}</p>}{r?.status === "claim_mismatch" ? <p>The complete saved assessment differs. {r.recorded === r.assessment?.verdict ? "Its headline verdict agrees, but that does not make the assessments equivalent." : "The saved and recomputed verdicts differ."} This projection does not identify every differing field.</p> : null}</div>
        <dl><div><dt>Execution</dt><dd>{words(s.status)}</dd></div><div><dt>Input acquisition</dt><dd>{words(s.acquisition.status)}</dd></div><div><dt>Saved claim agreement</dt><dd>{!r ? "Not reviewed" : r.matches === null ? "Not assessed" : r.matches ? "Agrees" : "Disagrees"}</dd></div><div><dt>Deployment</dt><dd>Unresolved</dd></div></dl>
      </section>
      {example ? <p className="projection-author"><span>Example context · author description</span>{example.description}</p> : null}
      <div className="projection-context"><span>Experimental question <strong>Not bound by this format</strong></span><span>Physical / simulation provenance <strong>Not classified by the summary</strong></span></div>
      <section className="projection-execution" aria-label="Recorded execution"><div className="projection-section-title"><h2>What actually ran</h2><span>{completed.length} / {s.checks.length} complete · {reused.length} reused</span></div>
        <Pages rows={s.checks} label="Recorded checks" render={c => <div className="projection-check" key={c.id}><div><strong>{c.id}</strong><span>{c.kind}</span></div><span>{checkStatus(c)}</span><small>Planned {c.planned}{c.attempted === null ? " · never attempted" : ""}</small></div>} />
      </section>
      {e ? <DependencyInspector key={selection!.explanation!.sha256} explanation={e} /> : <p className="projection-boundary">Dependency explanation not attached. The summary remains readable without a graph.</p>}
      <nav className="projection-details" aria-label="Record details">{[["changes", "Changes & inputs"], ["measurements", "Measured conditions"], ["source", "Source & CLI"], ["cost", "Costs & limits"]].map(([key, label]) => <button key={key} onClick={() => setPanel(key!)}>{label} </button>)}{r ? <button onClick={() => { pending.current?.abort(); setBusy(false); setSelection({ ...selection!, measurement: null, example: null }); clearExampleLink(); heading.current?.focus({ preventScroll: true }); }}>Detach measured review</button> : <button onClick={() => picker.current?.click()}>Attach measured review +</button>}{e ? <button onClick={() => { pending.current?.abort(); setBusy(false); setSelection({ ...selection!, explanation: null, example: null }); clearExampleLink(); heading.current?.focus({ preventScroll: true }); }}>Detach explanation</button> : <button onClick={() => picker.current?.click()}>Attach explanation +</button>}</nav>
      <p className="projection-boundary">Unsigned recorded results. No fresh execution, task adjudication or automatic acceptance. This evidence is not bound to the selected laboratory scene.</p>
    </> : <section className="projection-empty"><div className="projection-sequence" aria-hidden="true"><span>01<small>Execution</small></span><i /><span>02<small>Relation</small></span><i /><span>03<small>Saved claim</small></span></div><h2>Completion is only the beginning.</h2><p>Read what executed, trace the declared dependencies, and see whether the measured relation agrees with the saved claim. Choose an exposed example or open a local summary.</p><button className="research-action" onClick={() => selectExample("scoring-change")}>Trace a scoring change</button></section>}
    {selection && s && panel ? <GlassCard title={panel === "source" ? "Source and rechecking" : panel === "measurements" ? "Measured conditions" : panel === "changes" ? "Changes and input identities" : "Recorded costs and limits"} eyebrow="RECORDED EVIDENCE" wide onClose={() => setPanel(null)}>
      {panel === "source" ? <Source selection={selection} /> : panel === "changes" ? <div className="projection-detail"><p>{s.previous === 0 ? "No previous check receipts are retained. An empty change list is not a tested unchanged deployment." : `${s.previous} previous check receipts retained. Model identity ${s.modelChanged ? "changed" : "unchanged"}.`}</p><p>Changed input IDs: {s.changed.length ? s.changed.join(", ") : "None listed"}. {e ? "The attached explanation supplies declared dependencies and previous input identities in the dependency inspector." : "The summary does not include per-check selection reasons or previous input identities."}</p><p>Acquisition: {words(s.acquisition.status)}{s.acquisition.reason ? ` · ${words(s.acquisition.reason)}` : ""}{s.acquisition.resource ? ` · ${s.acquisition.resource}` : ""}. Execution errors: {s.errors}.</p><Pages rows={s.inputs} label="Input identities" render={input => <div className="projection-input" key={input.id}><strong>{input.id}</strong><span>{input.kind} · {input.status}</span><code>{input.sha ?? "Identity unknown"}</code></div>} /></div>
      : panel === "measurements" ? <div className="projection-detail">{r?.assessment ? <><p><strong>Producer-declared scope</strong><br />{r.assessment.scope}</p><p>Recomputed verdict: {r.assessment.verdict}. The browser displays the recorded review; it does not recompute scientific arithmetic.</p><Pages rows={r.assessment.checks} label="Measured conditions" render={(c, i) => <div className="projection-condition" key={i}><strong>{c.metric}</strong><span>{c.condition}</span><b>{c.holds ? "Holds" : "Does not hold"}</b></div>} /><h3>Failures</h3><p>{r.assessment.failures.join(" · ") || "None recorded"}</p><h3>Semantic errors</h3><Pages rows={r.assessment.errors} label="Semantic errors" render={(error, i) => <p key={i}>{error}</p>} />{!r.assessment.errors.length ? <p>None recorded</p> : null}<p>{r.assessment.limit}</p><dl className="projection-identities"><dt>Normalized contract SHA-256</dt><dd>{r.assessment.contract}</dd><dt>Bound contract input SHA-256</dt><dd>{r.source.contract}</dd><dt>Observation SHA-256</dt><dd>{r.source.observation}</dd><dt>Saved assessment SHA-256</dt><dd>{r.source.saved}</dd></dl></> : <p>{r ? "Execution incomplete. No complete measurement assessment is released." : "No compatible measured review is attached. A summary alone cannot adjudicate the handler's claim."}</p>}<p>Confirmation: not assessed. Task outcome: not adjudicated.</p></div>
      : <div className="projection-detail"><dl><dt>Recorded workflow time</dt><dd>{time(s.workflow)}</dd><dt>Human engineering time</dt><dd>Unknown</dd><dt>Complete cost</dt><dd>Unknown</dd><dt>Execution timestamp</dt><dd>Not included in the projection</dd></dl><p>Attempt intervals are nested within workflow time. Do not add them again, infer savings or treat these clocks as independently measured.</p><Pages rows={s.checks} label="Attempt times" render={c => <div className="projection-condition" key={c.id}><strong>{c.id}</strong><span>{time(c.seconds)}</span></div>} /><h3>Retained limits</h3><ul>{s.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul></div>}
    </GlassCard> : null}
  </main>;
}
