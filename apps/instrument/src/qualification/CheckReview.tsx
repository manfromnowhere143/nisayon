import { useEffect, useState } from "react";
import { GlassCard } from "../research/GlassCard";
import { RecordPages, SectionDeck } from "../ui/RecordPages";
import { Choice } from "../ui/Choice";
import { readRecord } from "./bundle";
import type { CheckBundle, ExecutionCheck } from "./checkBundle";
import { display, string, type Json } from "./json";
import { RecordExplorer } from "./RecordExplorer";
import { isNativeTaskResult, NativeTaskResult } from "./NativeTaskResult";

const words = (value: Json | undefined) => typeof value === "string" ? value.replaceAll("_", " ") : display(value);
const status = (check: ExecutionCheck) => !check.attempt ? "Not attempted" : check.attempt.status !== "completed" ? words(check.attempt.status) : check.selection.action === "reuse" ? "Reused" : "Executed";
const clip = (value: string, size = 120) => value.length > size ? value.slice(0, size) + "…" : value;
const optionalRecord = (bundle: CheckBundle, path: string): Json => {
  try { return readRecord(bundle.files, path) ?? null; }
  catch { return "Original bytes retained; not supported JSON. Inspect them in Original records."; }
};

function OriginalRecords({ bundle }: { bundle: CheckBundle }) {
  const paths = [...bundle.files.keys()].sort();
  const [path, setPath] = useState("assessment.json");
  const raw = bundle.files.get(path)!;
  let value: Json | undefined;
  try { value = readRecord(bundle.files, path); } catch { /* Original bytes remain available. */ }
  const save = () => {
    const url = URL.createObjectURL(new Blob([raw as Uint8Array<ArrayBuffer>], { type: "application/octet-stream" }));
    const a = document.createElement("a"); a.href = url; a.download = path.split("/").at(-1)!; a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <div className="review-record-browser"><Choice label="Original execution record" value={path} options={paths.map(name => ({ value: name, label: name }))} onChange={setPath} />
    {value === undefined ? <p className="review-note">Original bytes · {raw.byteLength.toLocaleString()} bytes. Save to inspect the complete file.</p> : <RecordExplorer key={path} value={value} />}
    <button className="research-text-action" onClick={save}>Save original bytes ↓</button>
  </div>;
}

function CheckDetail({ check }: { check: ExecutionCheck }) {
  return <SectionDeck label="Check detail" sections={[
    { id: "selection", label: "Why this check", content: <><p className="review-note">{status(check)} · {words(check.declaration.kind)}. This describes check execution; it does not establish a fresh physical experiment.</p><RecordExplorer value={{ dependencies: check.declaration.depends_on ?? null, selection: check.selection, attempt: check.attempt ?? null }} /></>, fit: false },
    { id: "result", label: "Saved result", content: <><p className="review-note">Producer-recorded result. Historical observations retain their original scope.</p>{isNativeTaskResult(check.result) ? <NativeTaskResult value={check.result} /> : <RecordExplorer value={check.result} />}</>, fit: false },
  ]} />;
}

/** Uses the instrument's existing fitted evidence surfaces and native dialogs. */
export function CheckReview({ bundle, active }: { bundle: CheckBundle; active: boolean }) {
  const [panel, setPanel] = useState<string | null>(null), [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  useEffect(() => { if (!active) { setPanel(null); setSelected(null); } }, [active]);
  const check = bundle.checks.find(row => row.id === selected);
  const nativeTask = bundle.checks.find(row => row.id === "reconstruct" && isNativeTaskResult(row.result));
  const matching = bundle.checks.filter(row => filter === "all" || !row.attempt || row.attempt.status !== "completed");
  const distinct = new Set(bundle.claims.map(claim => claim.value));
  const claim = bundle.execution.status !== "completed" ? "unresolved" : distinct.size === 1 ? [...distinct][0]! : distinct.size ? "multiple claims" : "not assessed";
  const detail = panel === "records" ? <OriginalRecords bundle={bundle} /> : panel === "scope" ? <RecordExplorer value={{ scope: bundle.model.scope ?? null, claims: bundle.claims.map(value => ({ ...value })), deployment: "unresolved", review_limit: bundle.assessment.limit ?? null, measurement_contract: optionalRecord(bundle, `${bundle.prefix}/inputs/scoring`) }} /> : panel === "changes" ? <RecordExplorer value={{ changed_inputs: bundle.applicability.changed_inputs ?? null, obligations: bundle.applicability.obligations ?? null, execution_errors: bundle.execution.errors ?? null }} /> : panel === "costs" ? <><p className="review-note">Complete cost remains unknown. Check times sit inside workflow time; neither includes all human work.</p><RecordExplorer value={bundle.execution.costs} /></> : <><p className="review-note">The browser checked package bytes. The SDK reconstruction was saved at export; it has not been rerun here.</p><dl className="review-identities"><dt>Review SHA-256</dt><dd>{bundle.sha256}</dd><dt>Model SHA-256</dt><dd>{bundle.modelSha256}</dd></dl><p className="review-note">Reconstruct locally with <code>nisayon-qualify review-check-bundle</code> and this file.</p><RecordExplorer value={bundle.assessment.checker_tool} /></>;
  return <>
    <div className="review-summary"><button className="review-question" aria-haspopup="dialog" onClick={() => setPanel("scope")}>{clip(string(bundle.model.scope), 600)}</button><div className="review-decisions"><div><span>Saved claim</span><strong data-decision={claim}>{words(claim)}</strong></div><div><span>Execution</span><strong>{words(bundle.execution.status)}</strong></div><div><span>Deployment</span><strong className="is-unresolved">Unresolved</strong></div></div></div>
    <section className="review-probes" aria-label="Declared checks"><div className="review-section-heading"><h2>{bundle.checks.length} declared checks</h2><div className="review-filter" role="group" aria-label="Check filter"><button aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All</button><button aria-pressed={filter === "attention"} onClick={() => setFilter("attention")}>Incomplete</button></div></div>
      <RecordPages label="Declared checks">{matching.map(row => <button className="probe-tile" key={row.id} onClick={() => setSelected(row.id)} aria-label={`Inspect ${row.id}: ${status(row)}`}><span className="probe-index">{String(bundle.checks.indexOf(row) + 1).padStart(2, "0")}</span><span style={{ overflowWrap: "anywhere", minWidth: 0 }}>{clip(row.id)}</span><span className="probe-result">{status(row)}</span></button>)}</RecordPages>
      {matching.length === 0 ? <p className="review-note">All declared checks completed. Their results can still reject the claim or leave it unresolved.</p> : null}
    </section>
    <div className="review-bottom"><span className="review-note">Bytes checked · saved SDK reconstruction</span><div>{nativeTask ? <button onClick={() => setPanel("task")}>Task outcomes </button> : null}{["changes", "scope", "costs", "identity", "records"].map(id => <button key={id} onClick={() => setPanel(id)}>{id} </button>)}</div></div>
    {active && check ? <GlassCard title={check.id} eyebrow="SAVED CHECK" wide onClose={() => setSelected(null)}><CheckDetail check={check} /></GlassCard> : null}
    {active && panel ? <GlassCard title={panel === "records" ? "Original records" : panel === "task" ? "Retained task outcomes" : "Execution details"} eyebrow="LOCAL REVIEW" wide onClose={() => setPanel(null)}>{panel === "task" ? <NativeTaskResult value={nativeTask?.result} /> : detail}</GlassCard> : null}
  </>;
}
