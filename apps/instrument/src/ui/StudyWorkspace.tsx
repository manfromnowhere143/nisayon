import { SectionDeck } from "./RecordPages";
import { FieldNavigator } from "./FieldNavigator";
import { EvidenceFlow } from "./EvidenceFlow";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useDocumentEvidence } from "./useDocumentEvidence";
import { discoverStudy, loadStudy, loadStudyReport, loadStudyTrial, studyUrl, type Fields, type Study, type StudyTrial, type StudyEntry } from "../data/study";
import type { LoaderOptions } from "../data/loader";
import type { FileRef } from "../model/types";
import { Choice } from "./Choice";
import { initialStudyRoute, STUDY_SECTIONS, type StudyRoute } from "../state/studyRoute";
import { diagnosticSceneLink, loadStudyScenes, studySceneLink, type StudyScenes } from "../data/studyScenes";
import type { LibraryCase } from "../data/library";
import { decisivePair, ProgressComparison } from "./StudyObligations";
import { useSurfaceArrival } from "./useSurfaceArrival";
import { ProcessorView, TemporalView } from "./MechanismViews";

const STUDY_VIEWS = [["trials", "Trials"], ["temporal", "Temporal contracts"], ["processor", "Processor correction"], ["external", "External evidence"], ["decision_case", "DC01 comparison"], ["declaration_score", "Declarations"], ["recovery", "Recovery"]];
const fields = (v: unknown): Fields => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Fields : {};
const list = (v: unknown): unknown[] => Array.isArray(v) ? v : [];
const text = (v: unknown): string => v == null ? "Not recorded" : typeof v === "object" ? JSON.stringify(v) : String(v);
const label = (v: unknown) => text(v).replaceAll("_", " ");
const numeric = (v: unknown, digits = 4) => typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "Not recorded";
const when = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v)) ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(v)) : "Not recorded";

function DetailFields({ value }: { value: Fields }) {
  return <dl className="study-facts">{Object.entries(value).map(([key, v]) => <div key={key}><dt>{label(key)}</dt><dd><DetailValue value={v} path={[key]} /></dd></div>)}</dl>;
}
function DetailValue({ value, path }: { value: unknown; path: string[] }) {
  const [open, setOpen] = useState(false);
  if (value === null || typeof value !== "object") return <>{text(value)}</>;
  return <details onToggle={event => setOpen(event.currentTarget.open)}><summary>{Array.isArray(value) ? `${value.length} retained entries` : "Retained fields"}</summary>{open ? <FieldNavigator value={value} path={path} /> : null}</details>;
}

function CostView({ value }: { value: Fields }) {
  const total = value.preparation_plus_phase_wall_s;
  const names = ["preparation_wall_s", "execution_and_integrity_wall_s", "final_evaluation_wall_s"];
  return <><p className="eyebrow">Recorded confirmation cost</p><p className="study-number">{numeric(total, 3)} <small>s</small></p>
    <p className="fine">Preparation plus phase. Nested rollout walls are displayed separately and never added again.</p>
    <div className="cost-composition">{names.map(name => <div key={name}><div><span>{label(name).replace(" wall s", "")}</span><strong className="num">{numeric(value[name], 3)} s</strong></div><div className="cost-track"><i style={{ width: typeof total === "number" && total > 0 && typeof value[name] === "number" ? `${Math.min(100, (value[name] as number) / total * 100)}%` : "0%" }} /></div></div>)}</div>
    <DetailFields value={{ nested_rollout_wall_s: value.nested_reset_rollout_trace_write_wall_s, physical_rollouts: value.physical_rollouts, unallocated_execution_scope_s: value.execution_scope_unallocated_s, phase_timer_discrepancy_s: value.phase_timer_discrepancy_s }} />
    <p className="fine">{text(value.scope)}</p><h3>Original trial ledger</h3><DetailFields value={fields(value.historical_trial_costs)} />
  </>;
}

function Decisions({ trial, onPair }: { trial: StudyTrial; onPair: (id: string) => void }) {
  const decision = trial.historical_decision ?? {};
  const reasons = list(decision.reasons);
  const candidates = fields(decision.candidates);
  return <><div className="study-decision"><p className="eyebrow">Retained evaluator decision</p><h3>{label(decision.decision ?? trial.historical_status)}</h3><p>{text(decision.scope ?? "Historical development record; no new scientific acceptance is created by this display.")}</p></div>
    <DetailFields value={{ obligation: decision.obligation, decided_at: when(decision.decided_at), evidence_state: trial.state }} />
    {reasons.length ? <ul className="study-reasons">{reasons.map((r, i) => { const reason = fields(r); return <li key={i}><strong>{label(reason.code ?? reason.reason ?? r)}</strong><p>{text(reason.detail ?? reason.message ?? reason.status)}</p></li>; })}</ul> : null}
    {decisivePair(trial) ? <button type="button" className="quiet" onClick={() => onPair(decisivePair(trial)!.id)}>Inspect decisive condition ↗</button> : null}
    {Object.entries(candidates).map(([id, v]) => { const c = fields(v); return <div key={id} className="study-obligation"><h4>Candidate · {id.slice(0, 8)}</h4><DetailFields value={{ status: c.status, valid_runs: c.valid_runs, obligation_failures: c.obligation_failures, invalid_or_unresolved_runs: c.invalid_or_unresolved_runs }} /></div>; })}
    {trial.issues.length ? <p role="status">Evidence issues: {trial.issues.map(text).join(" · ")}</p> : null}
  </>;
}

interface RunContext { trial: StudyTrial; scenes: StudyScenes | null; onScene?: ((url: string) => void) | undefined }
function RunReading({ record, title, evaluator, trial, scenes, onScene }: { record: Fields; title: string; evaluator: Fields } & RunContext) {
  const progress = fields(record.progress), ordinary = fields(record.ordinary_checks);
  const reasons = list(evaluator.reasons);
  const scene = studySceneLink(scenes, trial, record);
  return <article className="study-run"><p className="eyebrow">{title}</p><h4>{text(record.run_id)}</h4>
    <div className="study-run-metrics"><div><span>Task</span><strong>{label(record.measured_task_outcome)}</strong></div><div><span>Progress gain</span><strong className="num">{numeric(progress.value, 6)} <small>{text(progress.unit)}</small></strong></div></div>
    <DetailFields value={{ process: record.process_status, measurement: record.measurement_status, progress: progress.status, timing: record.timing, action_bounds: record.executed_action_bounds, observation_age_s: record.maximum_observation_age_s, reset: fields(fields(record.reset).policy_state_reset).status, evidence_role: record.role, cost_parent_run_id: record.cost_parent_run_id }} />
    {reasons.filter(r => ["rejected", "unresolved", "invalid"].includes(text(fields(r).severity))).map((r, i) => <p className="study-reason" key={i}><strong>{label(fields(r).code)}</strong> {text(fields(r).detail)}</p>)}
    <details><summary>Configuration and checks</summary><DetailFields value={fields(record.deployment)} /><DetailFields value={ordinary} /></details>
    <p className="fine mono">Record {text(record.record_content_sha256)}</p>
    {scene && onScene ? <button type="button" className="quiet" onClick={() => onScene(scene.url)}>Inspect recorded result ↗</button> : <p className="fine">No verified reconstruction is linked to this execution. Original measurements remain available.</p>}
  </article>;
}

function Executions({ trial, selected, onSelect, scenes, onScene }: RunContext & { selected: string | null; onSelect: (id: string) => void }) {
  const records = trial.confirmation?.observations ?? [], record = selected === null ? records[0] : records.find(r => r.run_id === selected);
  return <>{records.length ? <><Choice label="Retained execution" value={record ? text(record.run_id) : ""} options={[...(!record ? [{ value: "", label: "Execution unavailable in this publication" }] : []), ...records.map(r => ({ value: text(r.run_id), label: `${text(r.run_id)} · ${label(r.role)}` }))]} onChange={onSelect} /><p className="fine">Every retained execution, including prefixes and reproduction. Roles stay separate from fresh confirmation pairs.</p>{record ? <RunReading trial={trial} scenes={scenes} onScene={onScene} record={record} title={label(record.role)} evaluator={fields(fields(trial.historical_decision?.runs)[text(record.run_id)])} /> : <p role="alert">The pinned execution is absent. Select a retained execution explicitly.</p>}</> : <p>No confirmation executions were retained for this assignment.</p>}</>;
}

function Diagnostics({ trial }: { trial: StudyTrial }) {
  const d = trial.diagnostic;
  return <><p className="eyebrow">Diagnostic search</p><h3>{label(d.status)}</h3><p className="fine">{text(d.partition)}</p><DetailFields value={{ physical_rollouts: d.rollouts, records_retained: d.records_retained, phase_wall_s: d.phase_wall_s, final_check_wall_s: d.diagnostic_final_check_wall_s }} />{list(d.proposals).map((v, i) => { const p = fields(v); return <article className="study-obligation" key={i}><p className="eyebrow">Proposal {i + 1} · {p.rejected_before_execution === true ? "rejected before execution" : p.executed === true ? "executed" : "execution not established"}</p><h4>{text(p.reason)}</h4><DetailFields value={fields(p.ordinary_checks)} /><p className="fine mono">Candidate {text(p.candidate_digest)}</p><details><summary>Proposal record</summary><DetailFields value={p} /></details></article>; })}<details><summary>Diagnostic source and cost scope</summary><DetailFields value={fields(d.bundle_source)} /><DetailFields value={fields(d.recorded_run_costs)} /></details></>;
}

function PairView({ trial, selected, onSelect, scenes, onScene }: RunContext & { selected: string | null; onSelect: (id: string) => void }) {
  const confirmation = trial.confirmation;
  if (!confirmation) return <div className="study-empty"><h3>Confirmation was not scheduled</h3><p>This trial has no retained confirmation pairs. That absence remains separate from a failed confirmation.</p></div>;
  const pair = selected === null ? confirmation.pairs[0] : confirmation.pairs.find(p => p.id === selected);
  if (!pair) return <p role="alert">The pinned pair is absent from this publication. <button type="button" className="quiet" onClick={() => confirmation.pairs[0] && onSelect(confirmation.pairs[0].id)}>Open first assigned pair</button></p>;
  const decisionRuns = fields(trial.historical_decision?.runs);
  return <><Choice label="Assigned condition pair" value={pair.id} options={confirmation.pairs.map(p => ({ value: p.id, label: `${text(p.identity.condition_id)} · ${label(p.identity.role)}` }))} onChange={onSelect} />
    <div className="study-pair-context"><span>{label(pair.state)}</span><span>{label(pair.identity.role)}</span></div>
    <p className="fine">Original measurements under the same assigned condition. Matching task outcomes do not discharge an absolute progress obligation.</p>
    <ProgressComparison trial={trial} pair={pair} />
    <div className="study-pair">{(["reference", "candidate"] as const).map(side => <div key={side}>{pair[side].record_indices.length ? pair[side].record_indices.map(i => { const r = confirmation.observations[i]!; return <RunReading key={i} trial={trial} scenes={scenes} onScene={onScene} title={side} record={r} evaluator={fields(decisionRuns[text(r.run_id)])} />; }) : <p>{side}: record unavailable</p>}</div>)}</div>
    {pair.issues.length ? <p>{pair.issues.map(text).join(" · ")}</p> : null}
    <details><summary>Frozen acceptance predicates</summary><DetailFields value={fields(confirmation.protocol.predicates)} /></details>
  </>;
}

function DeclarationView({ trial }: { trial: StudyTrial }) {
  const protocol = trial.confirmation?.protocol ?? {}, diagnostic = trial.diagnostic;
  const timeline = fields(diagnostic.timeline);
  const candidate = fields(protocol.candidate);
  return <><p className="eyebrow">Custody and chronology</p><h3>{trial.declaration.contract ? "Bound declaration" : "Historical result-derived claim"}</h3><p>{text(trial.declaration.exposure)}</p>
    <ol className="study-chronology"><li><span>Diagnosis started</span><strong>{when(timeline.started_at)}</strong></li><li><span>Diagnosis ended</span><strong>{when(timeline.ended_at)}</strong></li><li><span>Candidate frozen</span><strong>{when(protocol.frozen_at)}</strong></li><li><span>Decision recorded</span><strong>{when(trial.historical_decision?.decided_at)}</strong></li></ol>
    <DetailFields value={{ joint_freeze_sha256: protocol.joint_freeze_sha256, protocol: protocol.protocol_id, evidence_partition: protocol.evidence_partition, stopping_rule: protocol.stopping_rule }} /><details><summary>Frozen candidate configuration</summary><DetailFields value={candidate} /></details>
    <h3>Retrospective declaration demonstrations</h3><p className="fine">These later demonstrations use exposed development evidence. They are not prospective trials.</p>
    {trial.retrospective_declarations.length ? trial.retrospective_declarations.map((d, i) => <details key={i}><summary>{text(d.kind)}</summary><DetailFields value={fields(d.record)} /><p className="fine mono">Source {text(d.source_sha256)}</p></details>) : <p>No declaration demonstration is bound to this assignment.</p>}
  </>;
}

function RecoveryView({ trial }: { trial: StudyTrial }) {
  const confirmation = trial.confirmation;
  return <><p className="eyebrow">Evidence continuity</p><h3>{label(trial.state)}</h3><DetailFields value={{ raw_evidence_status: confirmation?.raw_source.status, verification: confirmation?.raw_source.verification, retries: trial.retries, issues: trial.issues, diagnostic_rollouts: trial.diagnostic.rollouts, retained_diagnostic_records: trial.diagnostic.records_retained }} />
    <p className="fine">A reused record retains its original identity and cost. A completed process is distinct from an accepted correction. No execution worker is connected to this website.</p>
    <h3>Diagnostic proposals</h3>{list(trial.diagnostic.proposals).map((p, i) => <details key={i}><summary>Proposal {i + 1}</summary><DetailFields value={fields(p)} /></details>)}
  </>;
}

interface StudyWorkspaceProps {
  initialCase: string; onClose: () => void; options?: LoaderOptions;
  route?: StudyRoute; onRoute?: (route: StudyRoute, mode: "push" | "replace") => void;
  library?: LibraryCase[]; onScene?: (url: string) => void;
}
const EMPTY_LIBRARY: LibraryCase[] = [];
export function StudyWorkspace({ initialCase, onClose, options, route, onRoute, library = EMPTY_LIBRARY, onScene }: StudyWorkspaceProps) {
  const dialog = useRef<HTMLDialogElement>(null), content = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const documentLayout = useDocumentEvidence();
  const [localRoute, setLocalRoute] = useState(() => initialStudyRoute(initialCase));
  const selection = route ?? localRoute;
  const selectionRef = useRef(selection), onRouteRef = useRef(onRoute);
  selectionRef.current = selection; onRouteRef.current = onRoute;
  const select = (patch: Partial<StudyRoute>, mode: "push" | "replace" = "push") => {
    const next = { ...selectionRef.current, ...patch }; selectionRef.current = next;
    if (onRouteRef.current) onRouteRef.current(next, mode); else setLocalRoute(next);
  };
  const [study, setStudy] = useState<Study | null>(null), [latest, setLatest] = useState<FileRef | null>(null);
  const source = useRef<Study | null>(null);
  const [checked, setChecked] = useState<number | null>(null), [issue, setIssue] = useState<string | null>(null);
  const [trialIssue, setTrialIssue] = useState<string | null>(null);
  const [query, setQuery] = useState(""), [arm, setArm] = useState("all");
  const [admitted, setAdmitted] = useState<{ entry: StudyEntry; trial: StudyTrial } | null>(null);
  const [scenes, setScenes] = useState<StudyScenes | null>(null);
  const [mobileDetail, setMobileDetail] = useState(selection.pin !== null);
  const [copyStatus, setCopyStatus] = useState("");
  useEffect(() => { if (!copyStatus) return; const timer = setTimeout(() => setCopyStatus(""), 2500); return () => clearTimeout(timer); }, [copyStatus]);
  const copy = async () => { try { if (!navigator.clipboard) throw new Error("Clipboard unavailable"); await navigator.clipboard.writeText(window.location.href); setCopyStatus("Link copied"); } catch { setCopyStatus("Use address bar"); } };
  const { trial: key, section, view } = selection;
  useLayoutEffect(() => {
    // A new question starts at its heading; expanding a record or selecting a
    // sample keeps the reader's position. The close control stays outside this
    // single scroll surface, even with enlarged text or browser chrome.
    if (documentLayout && body.current) body.current.scrollTop = 0;
  }, [documentLayout, view, section, key, mobileDetail]);
  useEffect(() => { const origin = document.activeElement as HTMLElement | null; dialog.current?.showModal(); return () => { origin?.focus({ preventScroll: true }); }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    const open = async () => {
      try {
        const ref = selectionRef.current.pin ?? await discoverStudy(controller.signal, options);
        const value = source.current?.sha === ref.sha256 ? source.current : await loadStudy(ref, controller.signal, options);
        if (controller.signal.aborted) return;
        source.current = value; setStudy(value); setIssue(null); setLatest(null);
        select({ pin: ref, trial: selectionRef.current.trial || value.trials[0]!.key }, "replace");
      } catch (error) { if (!controller.signal.aborted) setIssue(error instanceof Error ? error.message : "Publication unavailable"); }
    };
    void open(); return () => controller.abort();
  }, [selection.pin?.sha256, selection.pin?.byte_length, options]);
  useEffect(() => {
    if (!study) return;
    const controller = new AbortController(); let busy = false;
    const check = async () => {
      if (busy || document.visibilityState === "hidden") return; busy = true;
      try {
        const ref = await discoverStudy(controller.signal, options);
        if (!controller.signal.aborted) { setLatest(ref.sha256 === study.sha ? null : ref); setChecked(Date.now()); }
      } catch { /* Retain the pinned study; a failed discovery cannot replace it. */ }
      finally { busy = false; }
    };
    void check(); const timer = window.setInterval(() => void check(), 15000);
    document.addEventListener("visibilitychange", check);
    return () => { controller.abort(); clearInterval(timer); document.removeEventListener("visibilitychange", check); };
  }, [study, options]);
  const requestedEntry = study?.trials.find(t => t.key === key);
  useEffect(() => {
    if (!requestedEntry || study?.sha !== selection.pin?.sha256) return;
    const controller = new AbortController(); setTrialIssue(null);
    void loadStudyTrial(requestedEntry, controller.signal, options).then(value => {
      if (controller.signal.aborted) return;
      setAdmitted({ entry: requestedEntry, trial: value });
      select({ pair: selectionRef.current.pair ?? value.confirmation?.pairs[0]?.id ?? null, execution: selectionRef.current.execution ?? (value.confirmation?.observations[0]?.run_id as string | undefined) ?? null }, "replace");
    }).catch(error => { if (!controller.signal.aborted) setTrialIssue(error instanceof Error ? error.message : "Trial unavailable"); });
    return () => controller.abort();
  }, [requestedEntry, study?.sha, selection.pin?.sha256, options]);
  useEffect(() => {
    setScenes(null);
    if (!admitted) return;
    const controller = new AbortController();
    void loadStudyScenes(admitted.entry.key, library, controller.signal, options).then(value => { if (!controller.signal.aborted) setScenes(value); }).catch(() => { /* Readings remain usable without a scene. */ });
    return () => controller.abort();
  }, [admitted, library, options]);
  const entry = admitted?.entry, trial = admitted?.trial;
  const pending = requestedEntry?.object.sha256 !== entry?.object.sha256 || study?.sha !== selection.pin?.sha256;
  const filtered = study?.trials.filter(t => (arm === "all" || t.arm === arm) && `${t.case_id} ${t.comparison} ${t.historical_status}`.toLowerCase().includes(query.toLowerCase())) ?? [];
  const selectPair = (id: string) => select({ section: "pairs", pair: id });
  const divergence = trial ? diagnosticSceneLink(scenes, trial) : null;
  useSurfaceArrival(content, pending ? "" : `${entry?.object.sha256}:${section}:${selection.pair}:${selection.execution}`, typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches);
  return <dialog ref={dialog} className="study-workspace" aria-labelledby="study-title" onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="study-header"><div><p className="eyebrow">Nisayon / retained experiments</p><h2 id="study-title">Study</h2></div><span className="study-mode">Recorded · execution disconnected</span><button type="button" className="quiet study-copy" onClick={() => void copy()}>{copyStatus || "Copy link"}</button><span className="sr-only" role="status">{copyStatus}</span><button type="button" className="ibtn" onClick={onClose} aria-label="Close study">×</button></header>
    <div ref={body} className="study-body">
    <div className="study-instrument-choice"><Choice label="Study instrument" value={view} options={STUDY_VIEWS.map(([value, label]) => ({ value: value!, label: label! }))} onChange={view => select({ view: view as StudyRoute["view"], item: null })} /></div>
    <nav className="section-tabs study-views" aria-label="Study instruments">{STUDY_VIEWS.map(([id, title]) => <button type="button" className={`section-tab${view === id ? " is-selected" : ""}`} key={id} aria-pressed={view === id} onClick={() => select({ view: id as StudyRoute["view"], item: null })}>{title}</button>)}</nav>
    <div className="study-publication"><span>{study ? <>Publication {study.sha.slice(0, 8)} · verified {when(study.verified_at)}</> : "Reading verified publication…"}</span>{checked ? <span title={new Date(checked).toISOString()}>Catalog checked {new Date(checked).toLocaleTimeString()}</span> : null}{latest ? <button className="quiet" onClick={() => select({ pin: latest, pair: null, execution: null })}>Open newer publication</button> : null}</div>
    <p className="fine study-freshness">This investigation stays pinned when new evidence arrives. Sealed publications are checked every 15 seconds while visible. <a href="/api/publication.json" target="_blank" rel="noreferrer">Publication record ↗</a></p>
    {issue ? <p className="study-issue" role="alert">{issue}. The requested publication could not be verified.</p> : null}
    {trialIssue ? <p className="study-issue" role="alert">{trialIssue}. The requested trial could not be verified.</p> : null}
    {study && !requestedEntry && view === "trials" ? <p className="study-issue" role="alert">The pinned trial is absent from this publication. Choose a retained assignment explicitly.</p> : null}
    {study && view !== "trials" ? <StudyReport key={view} study={study} kind={view} options={options} item={selection.item} onItem={item => select({ item })} /> : null}
    {study && view === "trials" ? <><div className="study-totals">{[[study.counts.trials, "trial assignments"], [study.counts.pairs, "condition pairs"], [study.counts.records, "confirmation records"], [study.counts.unscheduled, "not scheduled"]].map(([n, title]) => <div key={title}><strong className="num">{n}</strong><span>{title}</span></div>)}</div>
      <div className="study-grid" data-detail={mobileDetail}><aside className="study-library"><div className="study-filters"><input type="search" aria-label="Find a trial" placeholder="Find a case, study or result" value={query} onChange={e => setQuery(e.target.value)} /><Choice label="Study arm" value={arm} options={[{ value: "all", label: "Both arms" }, { value: "A", label: "Arm A" }, { value: "B", label: "Arm B" }]} onChange={setArm} /></div><div className="study-trials" aria-label="Trial assignments"><EvidenceFlow label="Trial assignments" identity={`${query}:${arm}`}>{filtered.map(t => <button type="button" key={t.key} aria-pressed={key === t.key} className="study-trial" onClick={() => { select({ trial: t.key, section: "decision", pair: null, execution: null }); setMobileDetail(true); }}><span><strong>{t.case_id}</strong><small>{t.comparison} · arm {t.arm}</small></span><span className="study-status">{label(t.historical_status)}</span></button>)}{!filtered.length ? <p>No matching assignments.</p> : null}</EvidenceFlow></div><p className="fine study-scope">{study.scope}</p></aside>
      <section className="study-detail" aria-label="Selected trial evidence" aria-busy={pending}><button className="quiet study-mobile-back" onClick={() => setMobileDetail(false)}>← All trials</button><p className="study-pending fine" role="status">{pending ? `Verifying ${requestedEntry?.case_id ?? "requested trial"}…` : ""}</p>{entry && trial ? <>
        <div className="study-trial-heading"><p className="eyebrow">{entry.comparison} · arm {entry.arm}</p><h3>{entry.case_id}</h3><a href={studyUrl(entry.object)} target="_blank" rel="noreferrer">Exact source ↗</a></div>
        <nav className="study-path" aria-label="Investigation path" inert={pending}><button onClick={() => select({ section: "diagnostics" })}>01 Change</button><button disabled={!divergence || !onScene} onClick={() => divergence && onScene?.(divergence)}>02 Divergence ↗</button><button onClick={() => selectPair(decisivePair(trial)?.id ?? selection.pair ?? trial.confirmation?.pairs[0]?.id ?? "")} disabled={!trial.confirmation?.pairs.length}>03 Condition</button><button onClick={() => select({ section: "decision" })}>04 Obligation</button><button onClick={() => select({ section: "declaration" })}>05 Freeze & source</button></nav>
        <div className="study-section-choice"><Choice label="Trial evidence section" value={section} disabled={pending} options={STUDY_SECTIONS.map(value => ({ value, label: value[0]!.toUpperCase() + value.slice(1) }))} onChange={section => select({ section: section as StudyRoute["section"] })} /></div>
        <nav className="section-tabs" aria-label="Trial evidence" inert={pending}>{STUDY_SECTIONS.map(s => <button type="button" key={s} className={`section-tab${section === s ? " is-selected" : ""}`} aria-pressed={section === s} onClick={() => select({ section: s })}>{s[0]!.toUpperCase() + s.slice(1)}</button>)}</nav>
        <div ref={content} className="study-detail-content" inert={pending}><EvidenceFlow label={`Trial · ${section}`} identity={`${entry.key}:${section}:${selection.pair}:${selection.execution}`}>{section === "decision" ? <Decisions trial={trial} onPair={selectPair} /> : section === "pairs" ? <PairView trial={trial} scenes={scenes} onScene={onScene} selected={selection.pair} onSelect={id => select({ pair: id })} /> : section === "executions" ? <Executions trial={trial} scenes={scenes} onScene={onScene} selected={selection.execution} onSelect={id => select({ execution: id })} /> : section === "diagnostics" ? <Diagnostics trial={trial} /> : section === "declaration" ? <DeclarationView trial={trial} /> : section === "costs" ? <CostView value={trial.costs} /> : <RecoveryView trial={trial} />}</EvidenceFlow></div>
      </> : <p role="status">Verifying trial evidence…</p>}</section></div></> : null}
    </div>
  </dialog>;
}

function StudyReport({ study, kind, options, item, onItem }: { study: Study; kind: string; options?: LoaderOptions | undefined; item: string | null; onItem: (item: string) => void }) {
  const [report, setReport] = useState<Awaited<ReturnType<typeof loadStudyReport>> | null>(null), [error, setError] = useState<string | null>(null);
  const ref = study.reports[kind];
  useEffect(() => { if (!ref) return; const controller = new AbortController(); setReport(null); setError(null); void loadStudyReport(ref, controller.signal, options).then(value => { if ((kind === "temporal" && value.record.schema !== "nisayon.ui-temporal-contracts.v1") || (kind === "processor" && value.record.schema !== "nisayon.ui-processor-decision.v1")) throw new Error("Retained report kind disagrees with the requested instrument"); if (!controller.signal.aborted) setReport(value); }).catch(e => { if (!controller.signal.aborted) setError(text(e instanceof Error ? e.message : e)); }); return () => controller.abort(); }, [ref, options, kind]);
  if (!ref) return <p className="study-report">This publication does not include that report.</p>;
  if (!report) return <p className="study-report" role={error ? "alert" : "status"}>{error ?? "Verifying retained report…"}</p>;
  const d = report.record;
  return <section className="study-report"><div className="study-report-heading"><p className="eyebrow">Retained report</p><a href={studyUrl(ref)} target="_blank" rel="noreferrer">Exact source ↗</a></div><SectionDeck label="Report detail" sections={[{ id: "reading", label: "Reading", fit: kind !== "temporal" && kind !== "processor", content: <>
    {kind === "temporal" ? <TemporalView record={d} item={item} onItem={onItem} /> : null}
    {kind === "processor" ? <ProcessorView record={d} item={item} onItem={onItem} /> : null}
    {kind === "external" ? <><h3>What the external recording establishes</h3><p>{text(d.producer)} · {text(d.episode)} · {text(d.rows)} recorded rows</p><p className="fine">{text(d.native_rule)}</p><DetailFields value={{ producer_declared_success: d.declared_success, repair_comparison_applicable: d.repair_comparison_applicable, reading: d.reading }} /><div className="study-obligations">{list(d.obligations).map((v, i) => { const o = fields(v); return <article key={i}><h4>{label(o.obligation)}</h4><p className="study-status">{label(o.status)}</p><p>{text(o.evidence)}</p><p className="fine">Additional measurement: {text(o.smallest_additional_measurement)}</p></article>; })}</div><details><summary>Positive observables and source</summary><DetailFields value={fields(d.positive_observables)} /><DetailFields value={fields(d.source)} /></details></> : null}
    {kind === "recovery" ? <><h3>Partial evidence → restored reference</h3><p>{text(d.scope)}</p><div className="study-pair"><article><p className="eyebrow">Partial reference</p><h4>{label(fields(d.partial_recovery).status)}</h4><p>{text(d.partial_pair_count)} assigned pairs</p></article><article><p className="eyebrow">Restored reference</p><h4>{text(d.recovered_pair_count)} assigned pairs</h4><p>Same pair identities: {text(d.same_pair_identities)}</p></article></div><DetailFields value={{ repeated_partial_read_identical: d.repeated_partial_read_identical, repeated_complete_read_identical: d.repeated_complete_read_identical, historical_costs_counted_once_per_view: d.historical_costs_counted_once_per_view, scientific_acceptance: d.scientific_acceptance, physical_execution_guarantee: d.physical_execution_guarantee }} /></> : null}
    {kind === "decision_case" ? <><h3>Controller-target comparison</h3><p>DC01 · retained exposed development pairs</p><p className="fine">The retained comparison establishes no repair advantage. Its equivalence result is distinct from proof about arbitrary controller conventions.</p><DetailFields value={fields(d.summary)} />{list(d.pairs).map((v, i) => <article className="study-obligation" key={i}><h4>Pair {i + 1}</h4><DetailFields value={fields(v)} /></article>)}<details><summary>Criteria and recorded attempts</summary><DetailFields value={fields(d.criterion)} />{list(d.attempts).map((v, i) => <DetailFields key={i} value={fields(v)} />)}</details></> : null}
    {kind === "declaration_score" ? <><h3>Declarations and adjudication</h3><DetailFields value={fields(d.declarations)} /><div className="study-pair">{Object.entries(fields(d.arms)).map(([arm, value]) => <article key={arm}><h4>Arm {arm}</h4><DetailFields value={fields(value)} /></article>)}</div><p className="fine">Historical development comparison. Retrospective declarations do not establish prospective custody.</p></> : null}
    </> }, { id: "source", label: "Source", content: <><p className="fine">{report.scope}</p><h3>All projected fields</h3><FieldNavigator value={d} /><p className="fine mono">{text(report.source.path)} · {text(report.source.sha256)}</p></> }]} /></section>;
}
