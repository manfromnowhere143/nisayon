import { useEffect, useState, type ReactNode } from "react";
import type { LoadedRun } from "../data/loader";
import type { CaseRecord, FileRef, Generation } from "../model/types";
import { Choice } from "./Choice";
import { EvidenceFlow } from "./EvidenceFlow";
import { PagedFacts, RecordPages, SectionDeck } from "./RecordPages";

type Catalog = {
  schema: "nisayon.public-system.v1";
  execution_connected: false;
  interfaces: { name: string; kind: string; description: string; parameters: string; access: string; transport: string; source: { path: string; sha256: string; line: number } }[];
  modules: { name: string; description: string; source: { path: string; sha256: string }; entries: { name: string; kind: string; line: number }[] }[];
  http: { method: string; path: string; purpose: string }[];
};

function Facts({ value, label }: { value: Record<string, unknown>; label: string }) {
  const fields: [string, unknown][] = [];
  const visit = (value: unknown, path: string): void => {
    if (value !== null && typeof value === "object" && Object.keys(value).length) {
      for (const [key, item] of Object.entries(value)) visit(item, path ? `${path}.${key}` : key);
    } else fields.push([path, value]);
  };
  for (const [key, item] of Object.entries(value)) visit(item, key);
  return fields.length ? <PagedFacts label={label}>{fields.map(([name, value]) => <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd className="num">{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>)}</PagedFacts> : <p className="depth-note">No fields are included in this record.</p>;
}

const record = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};

export function EnginePanel({ generation, caseRecord, run }: { generation: Generation; caseRecord: CaseRecord; run: LoadedRun }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [issue, setIssue] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [moduleName, setModuleName] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/engine.json", { signal: controller.signal, cache: "no-cache" }).then(async (response) => {
      if (!response.ok) throw new Error(`Engine inventory returned HTTP ${response.status}`);
      const data = await response.json() as Catalog;
      if (data.schema !== "nisayon.public-system.v1" || data.execution_connected !== false || !Array.isArray(data.interfaces) || !Array.isArray(data.modules) || !Array.isArray(data.http)) throw new Error("Engine inventory format is unavailable");
      setCatalog(data);
    }).catch((error: unknown) => { if (!controller.signal.aborted) setIssue(error instanceof Error ? error.message : "Engine inventory unavailable"); });
    return () => controller.abort();
  }, []);
  const refs = [run.record.samples, run.record.frames, run.record.model, ...generation.cases.filter((ref) => ref.case_key === caseRecord.case_key), ...caseRecord.decisionRefs].filter((ref): ref is FileRef => ref !== null);
  const files = Array.from(new Map(refs.map((ref) => [ref.path, ref])).values());
  const trial = caseRecord.trial ?? record(caseRecord.decisions.trial?.content);
  const diagnosis = record(trial.diagnosis_record);
  const costs = caseRecord.costs ?? record(trial.costs);
  const entries = catalog?.modules.filter((module) => `${module.name} ${module.entries.map((entry) => entry.name).join(" ")}`.toLowerCase().includes(query.toLowerCase())) ?? [];
  const module = entries.find(entry => entry.name === moduleName) ?? entries[0];
  const inventoryState = issue ? <p role="status" className="depth-note">{issue}. The verified experiment remains available.</p> : <p className="depth-note">Reading the published engine inventory…</p>;
  const source = (path: string, sha: string): ReactNode => <p className="decision-source mono">{path}<br />SHA-256 {sha}</p>;
  return <section className="engine-panel" aria-labelledby="engine-heading">
    <div className="engine-heading"><div><p className="eyebrow">Nisayon / experiment engine</p><h2 id="engine-heading">Inside this experiment</h2><p className="engine-connection"><span>Execution disconnected</span> · <code>execution_connected: false</code></p></div><a className="chip" href="/about/">About Nisayon ↗</a></div>
    <SectionDeck label="Engine evidence" sections={[
      { id: "case", label: "Contract", content: <><h3 className="sub">Task and acceptance predicates</h3><Facts value={caseRecord.predicates.raw} label="Contract fields" /><p className="depth-note">{caseRecord.runs.length} retained run records in this case. A completed process, valid measurement, task outcome, and accepted correction are separate findings.</p></> },
      { id: "plans", label: "Diagnosis", fit: false, content: <><h3 className="sub">Selection, interventions, and budget</h3><SectionDeck label="Diagnostic records" sections={[
        { id: "selection", label: "Selection", content: <Facts value={record(diagnosis.selection)} label="Selection fields" /> },
        { id: "budget", label: "Budget", content: <Facts value={record(diagnosis.budget)} label="Budget fields" /> },
        { id: "proposals", label: "Proposals", content: <Facts value={{ proposals: diagnosis.proposals ?? trial.proposals ?? [], candidate: diagnosis.candidate ?? null, status: diagnosis.status ?? trial.status ?? "not recorded" }} label="Proposal fields" /> },
        { id: "reset", label: "Execution", content: <Facts value={{ run_id: run.record.run.run_id, bundle_sha256: run.record.run.bundle_sha256, stage: run.record.stage, condition_id: run.record.condition_id, execution_mode: run.record.execution_mode, evidence_origin: run.record.evidence_origin, candidate_sha256: run.record.candidate_sha256, configuration_sha256: run.record.configuration_sha256, policy_reset: run.record.policy_reset, policy_state_reset: run.record.policy_state_reset, constraint_violations: run.record.constraint_violations }} label="Execution fields" /> },
        ...(caseRecord.plans.length ? [{ id: "plans", label: "Plans", content: <RecordPages label="Execution plans">{caseRecord.plans.map((plan, index) => <Facts key={index} value={record(plan)} label="Plan fields" />)}</RecordPages> }] : []),
      ]} /></> },
      { id: "costs", label: "Costs", content: <><h3 className="sub">Measured cost / {run.record.run.run_id}</h3>{run.record.costs.length ? <RecordPages label="Run costs">{run.record.costs.map((cost, index) => <div key={index} className="cost-row"><span>{cost.category.replaceAll("_", " ")}</span><strong className="num">{cost.value === null ? "unknown" : `${cost.value} ${cost.unit ?? ""}`}</strong>{cost.value === null ? <p className="fine">{cost.missing_reason ?? "No measurement was retained."}</p> : null}</div>)}</RecordPages> : <p className="depth-note">No run costs were recorded.</p>}{Object.keys(costs).length ? <><h3 className="sub">Trial cost record</h3><Facts value={costs} label="Trial costs" />{typeof trial.cost_scope === "string" ? <p className="depth-note">{trial.cost_scope}</p> : null}</> : null}</> },
      { id: "evidence", label: "Files", content: <><h3 className="sub">Verified data endpoints</h3><p className="depth-note">The files below are the exact objects used for this selected run. Each object is checked against the generation before display.</p><p><a href={generation.manifestUrl} target="_blank" rel="noreferrer">Open generation manifest ↗</a></p><RecordPages label="Evidence files">{files.map((ref) => <div key={ref.path} className="endpoint-record"><a href={new URL(ref.path, generation.baseUrl).href} target="_blank" rel="noreferrer">{ref.kind ?? "data"} ↗</a><span className="num">{ref.byte_length.toLocaleString()} bytes</span>{source(ref.path, ref.sha256)}</div>)}</RecordPages></> },
      { id: "interfaces", label: "Interfaces", content: <><h3 className="sub">Published reads and local tools</h3><p className="depth-note">This deployment reads published records. The engine runs locally; its execution and workspace tools are not connected to this public site.</p>{catalog ? <><div className="endpoint-links">{catalog.http.map((endpoint) => <a key={endpoint.path} href={endpoint.path} target="_blank" rel="noreferrer" title={endpoint.purpose}><span className="mono">{endpoint.method} {endpoint.path}</span> ↗</a>)}</div><RecordPages label="Local MCP interfaces">{catalog.interfaces.map((entry) => <div key={entry.name} className="interface-record"><h4 className="mono">{entry.name}</h4><p>{entry.description}</p><p className="fine">{entry.kind} · {entry.access} · {entry.transport}</p><p className="mono">{entry.parameters || "No parameters"}</p>{source(`${entry.source.path}:${entry.source.line}`, entry.source.sha256)}</div>)}</RecordPages></> : inventoryState}</> },
      { id: "source", label: "System", fit: false, content: <>
        <label className="module-search"><span className="sr-only">Find an engine module or function</span><input type="search" placeholder="Find a module or function" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        {catalog ? <><div className="module-picker"><Choice label="Source module" value={module?.name ?? ""} disabled={!entries.length} options={entries.map(entry => ({ value: entry.name, label: entry.name }))} onChange={setModuleName} /><span className="fine">{entries.length} of {catalog.modules.length}</span></div>
        <EvidenceFlow label="Source module" identity={module?.name ?? "empty"}>
          {module ? <><h3 className="sub mono">{module.name}</h3><p className="module-description">{module.description}</p><h4>Entry points · {module.entries.length}</h4><RecordPages label="Module entry points">{module.entries.map(entry => <div key={entry.name} className="module-entry"><span className="mono">{entry.name}</span><span className="fine">{entry.kind} · line {entry.line}</span></div>)}</RecordPages>{source(module.source.path, module.source.sha256)}</> : <p className="fine">No matching source module.</p>}
          <p className="depth-note">Inventory from the deployed source snapshot. This is not a running worker.</p>
        </EvidenceFlow></> : inventoryState}
      </> },
    ]} />
  </section>;
}
