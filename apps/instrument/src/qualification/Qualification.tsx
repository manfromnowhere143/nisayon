import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { GlassCard } from "../research/GlassCard";
import { RecordPages, SectionDeck } from "../ui/RecordPages";
import { Choice } from "../ui/Choice";
import { openReview } from "./client";
import { CheckReview } from "./CheckReview";
import { isCheckBundle, type ReviewBundle } from "./checkBundle";
import { RecordExplorer, preview } from "./RecordExplorer";
export { RecordExplorer } from "./RecordExplorer";
import { readRecord, type QualificationBundle } from "./bundle";
import { array, display, object, string, type Json, type JsonObject } from "./json";

const shortText = (value: string, limit: number) => value.length > limit ? `${value.slice(0, limit)}…` : value;
const words = (value: Json | undefined) => typeof value === "string" ? value.replaceAll("_", " ") : display(value);
function SafeRecord({ bundle, path }: { bundle: QualificationBundle; path: string }) {
  try { return <RecordExplorer key={path} value={readRecord(bundle.files, path)} />; }
  catch { return <p className="review-note">This original record cannot be displayed as supported JSON. Save its original bytes to inspect it.</p>; }
}
const download = (bundle: QualificationBundle, path: string) => {
  const bytes = bundle.files.get(path);
  if (!bytes) return;
  const url = URL.createObjectURL(new Blob([bytes as Uint8Array<ArrayBuffer>], { type: "application/octet-stream" }));
  const link = document.createElement("a"); link.href = url; link.download = path.split("/").at(-1)!; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
};

function Comparison({ bundle, comparison }: { bundle: QualificationBundle; comparison: JsonObject }) {
  const [source, setSource] = useState("comparison");
  const probe = string(comparison.probe);
  const assignments = array(bundle.plan.assignments, "assignments").map(v => object(v)).filter(v => v.probe === probe);
  const options = [{ value: "comparison", label: "Saved comparison" }, { value: "probe", label: "Declared input & oracle" }, ...assignments.flatMap(a => {
    const id = string(a.id), role = words(a.role);
    return ["request", "observation", "record", "intent"].filter(part => bundle.files.has(`evidence/${id}/${part}.json`)).map(part => ({ value: `evidence/${id}/${part}.json`, label: `${role} · ${part}` }));
  })];
  const value = source === "comparison" ? comparison : bundle.probes.find(p => p.id === probe);
  const difference = comparison.candidate_difference === null ? null : object(comparison.candidate_difference);
  const overview = <div className="comparison-overview">
    <div className="comparison-relation"><span>Reference</span><svg viewBox="0 0 100 16" aria-hidden="true"><path d="M1 8h96m-6-5 6 5-6 5" /></svg><span>Candidate</span><strong data-difference={!!difference}>{difference ? "Difference retained" : "Declared relation satisfied"}</strong></div>
    <RecordPages label="Comparison explanation">
      {difference ? <><div className="comparison-path"><span>First differing path</span><code>{shortText(string(difference.path), 240) || "/ (root)"}</code><p>{shortText(words(difference.reason), 160)}</p></div><div className="comparison-values">{(["reference", "candidate"] as const).map(role => <div key={role}><span>{role}</span><code>{preview(difference[role]!)}</code></div>)}</div><p className="review-note">This is the first reported difference, not a claim about its cause. Open the saved comparison for the complete values.</p></> : <p className="review-note">The saved SDK comparison reports agreement on this probe under the declared contract.</p>}
      <div className="comparison-controls"><div><span>Reference → declared oracle</span><strong>{comparison.reference_oracle_difference === null ? "Agrees" : "Differs"}</strong></div><div><span>Negative control → reference</span><strong>{comparison.negative_control_difference === null ? "No difference on this probe" : "Difference observed"}</strong></div></div>
    </RecordPages>
  </div>;
  const records = <div className="review-detail">
    <Choice label="Comparison record" value={source} onChange={setSource} options={options} />
    {source.startsWith("evidence/") ? <SafeRecord bundle={bundle} path={source} /> : <RecordExplorer key={source} value={value} />}
    {source.startsWith("evidence/") ? <button className="research-text-action" onClick={() => download(bundle, source)}>Save original record ↓</button> : null}
  </div>;
  return <SectionDeck label="Probe inspection" sections={[{ id: "difference", label: "Comparison", content: overview, fit: false }, { id: "records", label: "Original records", content: records, fit: false }]} />;
}

function ReviewEvidence({ bundle, section }: { bundle: QualificationBundle; section: string }) {
  const paths = [...bundle.files.keys()].filter(p => p !== "bundle.json").sort();
  const [path, setPath] = useState("assessment.json");
  const [filter, setFilter] = useState("");
  const matching = paths.filter(p => p.toLowerCase().includes(filter.toLowerCase()));
  if (section === "question") return <RecordExplorer value={bundle.case.question} />;
  return section === "records" ? <div className="review-detail">
    <input className="review-search" type="search" aria-label="Filter original records" placeholder="Find a record…" value={filter} onChange={e => setFilter(e.target.value)} />
    <Choice label="Original record" value={path} options={[...new Set([path, ...matching])].map(value => ({ value, label: value }))} onChange={setPath} />
    {path.endsWith(".json") ? <SafeRecord bundle={bundle} path={path} /> : <p className="review-note">Original log · {bundle.files.get(path)?.byteLength.toLocaleString()} bytes. Save to inspect the complete text.</p>}
    <button className="research-text-action" onClick={() => download(bundle, path)}>Save original bytes ↓</button>
  </div> : <SectionDeck label="Assessment detail" initial={section} sections={[
    { id: "scope", label: "Scope", content: <RecordExplorer value={{ scope: bundle.assessment.scope ?? null, premises: bundle.assessment.premises ?? null, obligations: bundle.assessment.obligations ?? null }} />, fit: false },
    { id: "costs", label: "Costs", content: <><p className="review-note">Unknown costs remain unknown. Attempt time is inside runner time.</p><RecordExplorer value={bundle.assessment.costs} /></>, fit: false },
    { id: "identity", label: "Identity", content: <><p className="review-note">Transport bytes checked locally. The saved SDK assessment has not been recomputed in this browser.</p><dl className="review-identities"><dt>Review SHA-256</dt><dd>{bundle.sha256}</dd><dt>Plan SHA-256</dt><dd>{bundle.planSha256}</dd></dl><RecordExplorer value={bundle.assessment.assessment_tool} /></>, fit: false },
  ]} />;
}

export function Qualification({ active, develop, bundle: selectedBundle, setBundle, initialExample = null, onExampleConsumed }: { active: boolean; develop: () => void; bundle: ReviewBundle | null; setBundle: (value: ReviewBundle) => void; initialExample?: "rejected" | null; onExampleConsumed?: () => void }) {
  const [busy, setBusy] = useState(""), [error, setError] = useState("");
  const [panel, setPanel] = useState<string | null>(null), [probe, setProbe] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const picker = useRef<HTMLInputElement>(null), pending = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => { if (!active) { pending.current?.abort(); setBusy(""); setPanel(null); setProbe(null); } }, [active]);
  const load = async (file: File) => {
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller;
    setError(""); setBusy("Reading local review");
    const progress = (message: string) => { if (!controller.signal.aborted && pending.current === controller) setBusy(message); };
    try { const result = await openReview(file, controller.signal, progress); if (!controller.signal.aborted) { setBundle(result); setFilter("all"); setProbe(null); setPanel(null); } }
    catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "This review could not be opened."); }
    finally { if (!controller.signal.aborted) setBusy(""); }
  };
  const bundle = selectedBundle && !isCheckBundle(selectedBundle) ? selectedBundle : null;
  const comparison = bundle?.comparisons.find(c => c.probe === probe);
  const example = async (name: "accepted" | "rejected") => {
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller;
    setError(""); setBusy("Reading public SDK example");
    try {
      const response = await fetch(`/examples/qualification/${name}.nisayon.zip`, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("The public SDK example is unavailable. You can still open a local review.");
      const result = await openReview(new File([await response.arrayBuffer()], `${name}.nisayon.zip`), controller.signal, message => { if (!controller.signal.aborted && pending.current === controller) setBusy(message); });
      if (!controller.signal.aborted) { setBundle(result); setFilter("all"); setProbe(null); setPanel(null); }
    } catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "Could not open the example."); }
    finally { if (!controller.signal.aborted) setBusy(""); }
  };
  const consumeExample = useRef(onExampleConsumed);
  consumeExample.current = onExampleConsumed;
  useEffect(() => {
    if (!active || !initialExample) return;
    const task = example(initialExample), request = pending.current;
    void task.then(() => { if (request === pending.current && !request?.signal.aborted) consumeExample.current?.(); });
    return () => request?.abort();
  }, [active, initialExample]);
  const matching = bundle?.probes.filter(p => filter === "all" || (bundle.comparisons.find(c => c.probe === p.id)?.candidate_difference != null)) ?? [];
  const firstDifference = bundle?.comparisons.find(c => c.candidate_difference != null);
  return <main className="qualification-workspace" hidden={!active} aria-label="Software qualification">
    <input ref={picker} type="file" accept=".zip" className="sr-only" tabIndex={-1} aria-label="Choose a Nisayon review file" onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; if (file) void load(file); }} />
    <div className="qualification-heading"><div><p className="research-micro">NATIVE QUALIFICATION</p><h1 ref={heading} tabIndex={-1}>One change. A checkable decision.</h1></div><button className="research-action" onClick={() => picker.current?.click()}>Open review <span aria-hidden="true">↗</span></button></div>
    {busy || error ? <div className="review-message" role={error ? "alert" : "status"}><span>{error || busy}{selectedBundle ? " · Previous review remains selected." : ""}</span>{busy ? <button onClick={() => { pending.current?.abort(); setBusy(""); }}>Cancel</button> : <button onClick={() => setError("")}>Dismiss</button>}</div> : null}
    {selectedBundle && isCheckBundle(selectedBundle) ? <CheckReview key={selectedBundle.sha256} active={active} bundle={selectedBundle} /> : bundle ? <>
      <div className="review-summary"><button className="review-question" aria-haspopup="dialog" onClick={() => setPanel("question")}>{shortText(string(bundle.case.question), 600)}</button><div className="review-decisions"><div><span>Saved software decision</span><strong data-decision={string(bundle.assessment.software_decision)}>{words(bundle.assessment.software_decision)}</strong></div><div><span>Execution</span><strong>{words(bundle.assessment.execution_validity)}</strong></div><div><span>Deployment</span><strong className="is-unresolved">Unresolved</strong></div></div></div>
      <dl className="review-boundaries"><div><dt>Applicability</dt><dd>Frozen software probes</dd></div><div><dt>Fresh task confirmation</dt><dd>Not established here</dd></div><div><dt>Unresolved obligations</dt><dd><button className="research-text-action" onClick={() => setPanel("scope")}>Read scope & premises ↗</button></dd></div></dl>
      {firstDifference ? <section className="review-first-difference" aria-label="First saved difference"><div><p>First saved difference · {string(firstDifference.probe)}</p><code>{shortText(string(object(firstDifference.candidate_difference).path), 160) || "/ (root)"}</code></div><button onClick={() => setProbe(string(firstDifference.probe))}>Inspect first difference ↗</button></section> : null}
      <section className="review-probes" aria-label="Declared probes"><div className="review-section-heading"><h2>{bundle.probes.length} declared probes</h2><div className="review-filter" role="group" aria-label="Probe filter"><button aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All</button><button aria-pressed={filter === "differences"} onClick={() => setFilter("differences")}>Differences</button></div></div>
        <RecordPages label="Declared probes">{matching.map((p, i) => { const c = bundle.comparisons.find(c => c.probe === p.id); const state = !c ? "Not compared" : c.candidate_difference === null ? "Agrees" : "Differs"; return <button className="probe-tile" key={string(p.id)} onClick={() => { if (c) setProbe(string(p.id)); else setPanel("records"); }} data-result={state}><span className="probe-index">{String(bundle.probes.indexOf(p) + 1 || i + 1).padStart(2, "0")}</span><span>{string(p.id)}</span><span className="probe-result">{state}</span><span aria-hidden="true">↗</span></button>; })}</RecordPages>
        {matching.length === 0 ? <p className="review-note">No saved candidate differences in this selection.</p> : null}
      </section>
      <div className="review-bottom"><span className="review-note" title={bundle.fileName}>Bytes checked · saved assessment</span><div>{["question", "scope", "costs", "identity", "records"].map(id => <button key={id} onClick={() => setPanel(id)}>{id} <span aria-hidden="true">↗</span></button>)}</div></div>
    </> : <div className="review-empty"><div className="qualification-orbit" aria-hidden="true"><div className="orbit-ring orbit-one" /><div className="orbit-ring orbit-two" /><svg viewBox="0 0 280 190"><path d="M40 95H105M175 95H240M140 37V65M140 125V153"/><circle cx="140" cy="95" r="31"/><path d="m126 96 10 10 19-23"/><circle cx="40" cy="95" r="5"/><circle cx="240" cy="95" r="5"/><circle cx="140" cy="32" r="5"/><circle cx="140" cy="158" r="5"/></svg></div><h2>Bring the evidence.</h2><p>Open a review exported by the Nisayon SDK.<br />Inspect the decision, the differences, and the original records.</p><div className="review-example-actions" aria-label="Public SDK examples"><button className="research-action" onClick={() => void example("accepted")}>Inspect a passing example ↗</button><button className="research-text-action" onClick={() => void example("rejected")}>Inspect a detected defect ↗</button></div><p className="review-note">Two exposed Python vectors. Software checks; no robot execution.</p><button className="research-text-action" onClick={develop}>Run the example yourself →</button><span className="review-local">Local to this browser. No upload.</span></div>}
    {active && bundle && comparison ? <GlassCard title={string(comparison.probe)} eyebrow="SAVED COMPARISON" wide onClose={() => setProbe(null)}><Comparison bundle={bundle} comparison={comparison} /></GlassCard> : null}
    {active && bundle && panel ? <GlassCard title={panel === "records" ? "Original records" : "Assessment details"} eyebrow="LOCAL REVIEW" wide onClose={() => setPanel(null)}><ReviewEvidence bundle={bundle} section={panel} /></GlassCard> : null}
  </main>;
}
