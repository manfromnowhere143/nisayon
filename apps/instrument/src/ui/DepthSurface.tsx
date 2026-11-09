// Contextual depths around the selected moment: Fork, Conditions, Decision.
// Each keeps the moment and offers Back to its parent.

import { useEffect, useRef } from "react";
import { recordingEnd, type LoadIssue, type LoadedRun } from "../data/loader";
import { describeMismatch, evaluatorForRun, firstActionMismatch } from "../model/findings";
import { sameRun, shortSha, type CaseRecord, type Depth, type Moment } from "../model/types";
import { useStore } from "../state/useStore";
import { Icon } from "./Icon";
import { EvidenceFlow } from "./EvidenceFlow";
import { PagedFacts, RecordPages, SectionDeck } from "./RecordPages";

interface Props {
  caseRecord: CaseRecord;
  run: LoadedRun;
  ghost: LoadedRun | null;
  ghostIssue: LoadIssue | null;
  moment: Moment;
  depth: Depth;
  condition: string | null;
}

const PARENT: Record<Depth, Depth | null> = { moment: null, fork: "moment", conditions: "fork", decision: "moment" };
const TITLE: Record<Depth, string> = { moment: "Moment", fork: "Fork", conditions: "Conditions", decision: "Decision" };

export function DepthSurface({ caseRecord, run, ghost, ghostIssue, moment, depth, condition }: Props) {
  const store = useStore();
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (depth !== "moment") headingRef.current?.focus({ preventScroll: true });
  }, [depth]);
  if (depth === "moment") return null;
  const parent = depth === "fork" && condition ? "conditions" : PARENT[depth];
  return (
    <section className="depth" aria-labelledby="depth-heading" data-depth={depth}>
      <div className="depth-bar">
        <button type="button" className="quiet depth-back" onClick={() => store.back()} aria-label={`Back to ${TITLE[parent ?? "moment"]}`}>
          <Icon name="back" /> {TITLE[parent ?? "moment"]}
        </button>
        <h2 id="depth-heading" ref={headingRef} tabIndex={-1} className="depth-title">
          {TITLE[depth]}
        </h2>
        <span className="depth-anchor num">
          {run.record.run.run_id} · row {moment.row_index} · {moment.phase}
        </span>
      </div>
      {depth === "fork" ? <EvidenceFlow label="Fork comparison"><Fork caseRecord={caseRecord} run={run} ghost={ghost} ghostIssue={ghostIssue} /></EvidenceFlow> : null}
      {depth === "conditions" ? <EvidenceFlow label="Conditions"><Conditions caseRecord={caseRecord} condition={condition} /></EvidenceFlow> : null}
      {depth === "decision" ? <Decision caseRecord={caseRecord} run={run} /> : null}
    </section>
  );
}

function Fork({ caseRecord, run, ghost, ghostIssue }: { caseRecord: CaseRecord; run: LoadedRun; ghost: LoadedRun | null; ghostIssue: LoadIssue | null }) {
  const store = useStore();
  const alignment = caseRecord.alignment;
  const primaryMismatch = firstActionMismatch(run.samples.rows);
  const ghostMismatch = ghost ? firstActionMismatch(ghost.samples.rows) : null;
  const plans = caseRecord.plans as { id?: unknown; deployment?: unknown; intervention?: unknown }[];
  const planFor = (planId: string) => plans.find((p) => p.id === planId);
  const primaryPlan = planFor(run.record.plan_id);
  const ghostPlan = ghost ? planFor(ghost.record.plan_id) : undefined;
  const diff = deploymentDiff(primaryPlan?.deployment, ghostPlan?.deployment);
  const intervention = [run, ghost].filter((r): r is LoadedRun => r !== null).map((r) => {
    const ev = r.record.evaluator;
    const candidate = ev && typeof ev.candidate === "object" && ev.candidate ? (ev.candidate as Record<string, unknown>) : null;
    return `${r.record.run.run_id}: ${r.record.role}${ev && typeof ev.revision === "string" ? `, ${ev.revision} revision` : ""}${candidate ? `, candidate ${String(candidate.id)} ${String(candidate.digest ?? "").slice(0, 8)}` : ""}`;
  });
  const confirmationAvailable = caseRecord.confirmation?.available_in_fixture === true || caseRecord.confirmation?.availability === "available" || caseRecord.confirmation?.availability === "recorded";
  return (
    <div className="depth-body">
      <p className="depth-lede">
        <strong>{run.record.run.run_id}</strong> ({run.record.role}, task {run.record.task_outcome}) drawn solid;{" "}
        {ghost ? (
          <>
            <strong>{ghost.record.run.run_id}</strong> ({ghost.record.role}, task {ghost.record.task_outcome}) drawn as a ghost at the same simulation time and phase, when that sample exists.
          </>
        ) : ghostIssue ? (
          <span className="depth-warn">paired run unavailable: {ghostIssue.message}.</span>
        ) : (
          <span>loading the paired run…</span>
        )}
      </p>
      <PagedFacts label="Comparison facts">
        <div>
          <dt>Alignment</dt>
          <dd>{String(alignment.declared ?? alignment.kind ?? "not declared")}</dd>
        </div>
        <div>
          <dt>Same-time rows</dt>
          <dd>{String(alignment.same_time_rows ?? "not declared")}</dd>
        </div>
        <div>
          <dt>Configuration difference</dt>
          <dd>
            {diff.length === 0 ? (
              intervention.length ? intervention.join(" · ") : "no deployment record differs between the two plans"
            ) : (
              <><p className="fine">{run.record.run.run_id} → {ghost?.record.run.run_id}. Differences between their declared deployment plans.</p><ul className="plain">
                {diff.map((d) => (
                  <li key={d.key} className="mono">
                    {d.key}: {d.a} → {d.b}
                  </li>
                ))}
              </ul></>
            )}
          </dd>
        </div>
        <div>
          <dt>First mismatch</dt>
          <dd>
            <span className="num">
              {run.record.run.run_id}: {describeMismatch(primaryMismatch, run.record.row_count).headline}
            </span>
            {ghost ? (
              <>
                <br />
                <span className="num">
                  {ghost.record.run.run_id}: {describeMismatch(ghostMismatch, ghost.record.row_count).headline}
                </span>
              </>
            ) : null}
          </dd>
        </div>
        <div>
          <dt>Recordings</dt>
          <dd className="num">
            {run.record.run.run_id} ends at row {run.record.recording.ends_at_row} ({recordingEnd(run).toFixed(2)} s)
            {ghost ? `; ${ghost.record.run.run_id} ends at row ${ghost.record.recording.ends_at_row} (${recordingEnd(ghost).toFixed(2)} s)` : ""}. Neither is stretched.
          </dd>
        </div>
      </PagedFacts>
      <div className="depth-actions">
        {ghost ? (
          <button type="button" className="quiet" onClick={() => store.selectRun(ghost.record.run)}>
            Swap: select {ghost.record.run.run_id}
          </button>
        ) : null}
        <button type="button" className="quiet depth-open" onClick={() => store.setDepth("conditions")} aria-describedby={confirmationAvailable ? undefined : "conditions-note"}>
          Conditions <Icon name="open" />
        </button>
        <button type="button" className="quiet depth-open" onClick={() => store.setDepth("decision")}>
          Decision <Icon name="open" />
        </button>
      </div>
      {!confirmationAvailable ? (
        <p id="conditions-note" className="depth-note">
          This generation carries no confirmation runs ({String(caseRecord.confirmation?.availability ?? caseRecord.confirmation?.note ?? "not available")}); Conditions shows what is retained about the separate confirmation.
        </p>
      ) : null}
    </div>
  );
}

type Pair = Record<string, unknown>;

const KNOWN_VERDICTS = new Set(["fixed", "pass", "regression", "both_failed", "improved", "gap", "invalid", "unresolved"]);

function verdictClass(verdict: unknown): string {
  const v = String(verdict ?? "");
  return KNOWN_VERDICTS.has(v) ? `v-${v}` : "v-other";
}

function Conditions({ caseRecord, condition }: { caseRecord: CaseRecord; condition: string | null }) {
  const store = useStore();
  const decision = caseRecord.decisions.confirmation_decision ?? null;
  const content = decision?.content as Record<string, unknown> | null | undefined;
  const conf = caseRecord.confirmation?.availability === "recorded" ? caseRecord.confirmation : content && typeof content.confirmation === "object" && content.confirmation ? (content.confirmation as Record<string, unknown>) : null;
  const pairs: Pair[] = conf && Array.isArray(conf.pairs) ? (conf.pairs as unknown[]).filter((p): p is Pair => typeof p === "object" && p !== null) : [];
  const summary = conf && typeof conf.summary === "object" && conf.summary ? (conf.summary as Record<string, unknown>) : null;
  const findings = conf && Array.isArray(conf.findings) ? (conf.findings as unknown[]).filter((f): f is Pair => typeof f === "object" && f !== null) : [];
  const selected = pairs.find((p) => p.condition_id === condition) ?? null;
  const inFixture = caseRecord.confirmation?.available_in_fixture === true || caseRecord.confirmation?.availability === "available" || caseRecord.confirmation?.availability === "recorded";
  const counts = new Map<string, number>();
  for (const p of pairs) counts.set(String(p.verdict ?? "unknown"), (counts.get(String(p.verdict ?? "unknown")) ?? 0) + 1);
  const reasons = reasonsOf(content);
  const selectedFindings = selected ? [...findings.filter((f) => f.condition_id === selected.condition_id), ...reasons.filter((r) => r.run_id === selected.reference_run_id || r.run_id === selected.candidate_run_id)] : [];
  const pairRuns = selected && inFixture ? caseRecord.runs.filter((r) => r.run.bundle_sha256 === conf?.bundle_sha256 && (r.run.run_id === selected.reference_run_id || r.run.run_id === selected.candidate_run_id)) : [];
  return (
    <div className="depth-body">
      <p className="depth-lede">
        {pairs.length
          ? `${pairs.length} paired conditions in the referenced confirmation record: ${Array.from(counts, ([k, n]) => `${n} ${k}`).join(", ")}.`
          : `No paired conditions are referenced in this generation (confirmation: ${String(caseRecord.confirmation?.availability ?? caseRecord.confirmation?.note ?? "not available")}).`}
      </p>
      {summary ? (
        <p className="depth-note num">
          {Object.entries(summary)
            .map(([k, v]) => `${k.replace(/_/g, " ")} ${String(v)}`)
            .join(" · ")}
        </p>
      ) : null}
      {!inFixture && pairs.length ? (
        <p className="depth-note">These pairs come from the separate confirmation decision. Their runs are not in this diagnostic bundle, so no sample opens from them here; the selected moment stays where it is.</p>
      ) : null}
      {pairs.length ? (
        <div className="cond-field" hidden={selected !== null} role="group" aria-label="Paired confirmation conditions; select one to read its pair">
          <RecordPages label="Conditions">
          {pairs.map((p) => {
            const id = String(p.condition_id ?? "");
            const isSelected = selected !== null && selected.condition_id === p.condition_id;
            return (
              <button
                key={id}
                type="button"
                className={`cond ${verdictClass(p.verdict)}${isSelected ? " is-selected" : ""}`}
                aria-pressed={isSelected}
                aria-label={`${id}, ${String(p.role ?? "")}, verdict ${String(p.verdict ?? "unknown")}`}
                onClick={() => store.selectCondition(isSelected ? null : id)}
              >
                <span className="cond-mark" aria-hidden="true" />
                <span className="cond-id num">{id.replace(/^seed-/, "")}</span>
              </button>
            );
          })}
          </RecordPages>
        </div>
      ) : null}
      {selected ? (
        <div aria-label={`Pair ${String(selected.condition_id)}`}><button type="button" className="quiet" onClick={() => store.selectCondition(null)}>All conditions</button><PagedFacts label="Pair fields">
          {Object.entries(selected).map(([k, v]) => (
            <div key={k}>
              <dt>{k.replace(/_/g, " ")}</dt>
              <dd className={k.endsWith("run_id") ? "mono" : "num"}>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
            </div>
          ))}
        </PagedFacts></div>
      ) : pairs.length ? (
        <p className="depth-note">Select a condition to read its pair verbatim.</p>
      ) : null}
      {selected && pairRuns.length ? <div className="depth-actions">{pairRuns.map((r) => <button key={r.run.run_id} type="button" className="quiet" onClick={() => store.selectRun(r.run, true)}>Inspect {r.role} · {r.run.run_id}</button>)}</div> : null}
      {selected && selectedFindings.some((f) => !("step" in f)) ? <p className="depth-note">The condition-level reason supplies no sample locator. Opening an execution begins at its first recorded sample.</p> : null}
      {selected && selectedFindings.length ? (
        <RecordPages label="Condition findings">
          {selectedFindings.map((f, i) => (
            <div key={i} className={`reason sev-${String(f.severity)}`}>
              <span className="reason-code mono">{String(f.code)}</span>
              <span className="reason-sev">{String(f.severity)}</span>
              <span className="reason-detail">{String(f.detail)}</span>
            </div>
          ))}
        </RecordPages>
      ) : null}
      {findings.length && !selected ? (
        <RecordPages label="Condition findings">
          {findings.map((f, i) => (
            <div key={i} className={`reason sev-${String(f.severity)}`}>
              <span className="reason-code mono">{String(f.code)}</span>
              <span className="reason-sev">{String(f.severity)}</span>
              <span className="reason-detail">{String(f.detail)}</span>
            </div>
          ))}
        </RecordPages>
      ) : null}
      {decision ? (
        <p className="decision-source mono">
          {decision.path} · {shortSha(decision.sha256)} · {decision.byte_length} bytes
          {content?.decided_at ? ` · decided ${String(content.decided_at)}` : ""}
        </p>
      ) : (
        <p className="depth-note">{String(caseRecord.confirmation?.note ?? "No confirmation record is referenced.")}</p>
      )}
      <div className="depth-actions">
        <button type="button" className="quiet depth-open" onClick={() => store.setDepth("decision")}>
          Decision <Icon name="open" />
        </button>
      </div>
    </div>
  );
}

interface Reason {
  code: string;
  severity: string;
  detail: string;
  run_id?: string;
  step?: number;
}

function reasonsOf(content: unknown): Reason[] {
  if (!content || typeof content !== "object") return [];
  const raw = (content as Record<string, unknown>).reasons;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null)
    .map((r) => ({
      code: String(r.code ?? ""),
      severity: String(r.severity ?? ""),
      detail: String(r.detail ?? ""),
      ...(typeof r.run_id === "string" ? { run_id: r.run_id } : {}),
      ...(typeof r.step === "number" ? { step: r.step } : {}),
    }));
}

function Decision({ caseRecord, run }: { caseRecord: CaseRecord; run: LoadedRun }) {
  const store = useStore();
  const diagnostic = caseRecord.decisions.diagnostic_decision ?? null;
  const confirmation = caseRecord.decisions.confirmation_decision ?? null;
  const trial = caseRecord.decisions.trial ?? null;
  const diagnosticContent = diagnostic?.content as Record<string, unknown> | null | undefined;
  const confirmationContent = confirmation?.content as Record<string, unknown> | null | undefined;
  const trialContent = trial?.content as Record<string, unknown> | null | undefined;
  const runEntry = evaluatorForRun(caseRecord, run.record);
  const runFindings = runEntry && Array.isArray(runEntry.findings) ? (runEntry.findings as Record<string, unknown>[]) : [];
  const jump = (step: number): void => {
    const row = run.samples.rows.find((r) => r.step === step);
    if (row) store.setRow(row.row_index, "push");
  };
  return <SectionDeck label="Decision records" sections={[
    { id: "diagnostic", label: "Diagnostic", content: <DecisionBlock title="Diagnostic decision" ref_={diagnostic} content={diagnosticContent} /> },
    { id: "evaluation", label: `Evaluator · ${runFindings.length}`, content: <div className="decision-run">
      <h3 className="sub">Evaluator entry for {run.record.run.run_id}</h3>
      {runEntry ? <>
        <dl className="status-matrix">
          {(["process", "measurement", "progress", "constraints", "timing"] as const).map((key) => <div key={key}><dt>{key}</dt><dd>{String(runEntry[key] ?? "—")}</dd></div>)}
          <div><dt>outcome</dt><dd>{typeof runEntry.outcome === "object" && runEntry.outcome ? `observed ${String((runEntry.outcome as Record<string, unknown>).observed)} · claimed ${String((runEntry.outcome as Record<string, unknown>).claimed)}` : String(runEntry.outcome ?? "—")}</dd></div>
        </dl>
        <RecordPages label="Evaluator findings" key={run.record.run.bundle_sha256 + run.record.run.run_id}>
          {runFindings.map((f, i) => <div key={i} className={`reason sev-${String(f.severity)}`}>
            <span className="reason-code mono">{String(f.code)}</span><span className="reason-sev">{String(f.severity)}</span>
            <span className="reason-detail">{String(f.detail)}</span>
            {typeof f.step === "number" ? <button type="button" className="quiet" onClick={() => jump(f.step as number)}>step {String(f.step)}</button> : null}
          </div>)}
        </RecordPages>
      </> : <p className="depth-note">No evaluator entry is referenced for this run.</p>}
    </div> },
    { id: "trial", label: "Trial", content: <div className="decision-run">
      <h3 className="sub">Trial record</h3>
      {trial ? <>
        <dl className="facts compact">
          <div><dt>status</dt><dd>{String(trialContent?.status ?? "—")}</dd></div>
          <div><dt>arm claimed acceptance</dt><dd>{String(trialContent?.arm_claimed_acceptance ?? "—")}</dd></div>
          <div><dt>confirmation rollouts</dt><dd className="num">{String(trialContent?.confirmation_rollouts ?? "—")}</dd></div>
          <div><dt>record</dt><dd className="mono">{trial.path} · {shortSha(trial.sha256)}</dd></div>
        </dl>
        {Array.isArray(trialContent?.proposals) ? <RecordPages label="Candidate proposals">{(trialContent.proposals as Record<string, unknown>[]).map((p, i) => <div key={i} className="reason"><span className="reason-code mono">proposal {String(p.candidate_digest ?? "").slice(0, 8)}</span><span className="reason-sev">{p.rejected_before_execution === true ? "rejected before execution · no observed future" : p.executed === true ? "executed" : "not executed"}</span><span className="reason-detail">{String(p.reason ?? "")}</span></div>)}</RecordPages> : null}
      </> : <p className="depth-note">No trial record is referenced.</p>}
    </div> },
    { id: "confirmation", label: "Confirmation", content: <DecisionBlock title="Confirmation decision (separate record)" ref_={confirmation} content={confirmationContent} /> },
  ]} />;
}

function DecisionBlock({ title, ref_, content }: { title: string; ref_: CaseRecord["decisions"][string]; content: Record<string, unknown> | null | undefined }) {
  if (!ref_) {
    return (
      <div className="decision-block">
        <h3 className="sub">{title}</h3>
        <p className="depth-note">No record referenced.</p>
      </div>
    );
  }
  const reasons = reasonsOf(content);
  const decision = String(content?.decision ?? "not embedded");
  return (
    <div className="decision-block" data-decision={decision}>
      <h3 className="sub">{title}</h3>
      <p className="decision-word">
        <span className={`decision-mark decision-${decision}`} aria-hidden="true" />
        <strong>{decision}</strong>
        {content?.scope ? <span className="decision-scope"> · {String(content.scope)}</span> : null}
      </p>
      {reasons.length ? <RecordPages label="Decision reasons" key={ref_.sha256}>
        {reasons.map((r, i) => <div key={i} className={`reason sev-${r.severity}`}>
          <span className="reason-code mono">{r.code}</span><span className="reason-sev">{r.severity}</span><span className="reason-detail">{r.detail}</span>
        </div>)}
      </RecordPages> : <p className="depth-note">{content ? "No reasons listed in this record." : ref_.omitted_reason ?? "Content not embedded."}</p>}

      <p className="decision-source mono">
        {ref_.path} · {shortSha(ref_.sha256)} · {ref_.byte_length} bytes
        {content?.bundle_sha256 ? ` · bundle ${String(content.bundle_sha256).replace("sha256:", "").slice(0, 8)}` : ""}
      </p>
    </div>
  );
}

function deploymentDiff(a: unknown, b: unknown): { key: string; a: string; b: string }[] {
  if (!a || !b || typeof a !== "object" || typeof b !== "object") return [];
  const ra = a as Record<string, unknown>;
  const rb = b as Record<string, unknown>;
  const keys = new Set([...Object.keys(ra), ...Object.keys(rb)]);
  const out: { key: string; a: string; b: string }[] = [];
  for (const key of keys) {
    const va = JSON.stringify(ra[key]);
    const vb = JSON.stringify(rb[key]);
    if (va !== vb) out.push({ key, a: va ?? "absent", b: vb ?? "absent" });
  }
  return out;
}

export function isSameRunKey(a: { bundle_sha256: string; run_id: string }, b: { bundle_sha256: string; run_id: string }): boolean {
  return sameRun(a, b);
}
