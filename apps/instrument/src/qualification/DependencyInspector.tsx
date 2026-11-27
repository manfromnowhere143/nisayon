import { useRef, useState } from "react";
import type { DependencyExplanation } from "./projection";
import { ProjectionPages as Pages } from "./ProjectionPages";

type Check = DependencyExplanation["checks"][number];
type Input = DependencyExplanation["inputs"][number];
const words = (value: string) => value.replaceAll("_", " ");
export const attemptLabel = (check: Check) => check.status === "completed" ? check.attempted === "reuse" ? "Reused · completed" : "Ran · completed" : check.attempted === null ? "Not attempted" : `${words(check.attempted)} · ${words(check.status)}`;
const priorLabel = (input: Input) => !input.previousPresent ? "Not previously declared" : input.previousSha === null ? "Previously unknown" : "Previously bound";
const reasons: Record<Check["reasons"][number]["code"], string> = {
  dependency_model_changed: "The declared dependency model changed.",
  dependency_model_review_unavailable: "The dependency model review was unavailable.",
  missing_receipt: "No previous receipt was available for this check.",
  unavailable_upstream_evidence: "Upstream evidence was unavailable for reuse.",
  receipt_dependency_mismatch: "The previous receipt did not match the declared dependencies.",
  artifact_bytes_changed: "The previous artifact's bytes changed.",
  fresh_check_required: "The declared refresh rule requires a new execution.",
  upstream_requires_check: "A direct upstream check was also selected to run.",
  recorded_reason_detail_withheld: "Diagnostic detail withheld. Its text is available only in the local source record.",
};

export function DependencyInspector({ explanation: e }: { explanation: DependencyExplanation }) {
  const [selected, setSelected] = useState(e.checks.find(c => c.kind === "analysis")?.id ?? e.checks[0]!.id);
  const selector = useRef<HTMLSelectElement>(null);
  const input = e.inputs.find(i => i.id === selected), check = e.checks.find(c => c.id === selected), decision = e.decisions.find(d => d.id === selected);
  const type = input ? "Input" : check ? "Check" : "Decision requirements";
  const dependencies = check?.depends ?? decision?.depends ?? [];
  const dependents = [...e.checks.filter(c => c.depends.includes(selected)), ...e.decisions.filter(d => d.depends.includes(selected))].map(node => node.id);
  const choose = (id: string) => { setSelected(id); selector.current?.focus({ preventScroll: true }); };
  const nodeKind = (id: string) => e.inputs.some(i => i.id === id) ? "input" : e.checks.some(c => c.id === id) ? "check" : "decision requirements";
  const link = (id: string) => <button type="button" onClick={() => choose(id)} aria-label={`Inspect ${nodeKind(id)} ${id}`}><span>{id}</span><small>{nodeKind(id)}</small></button>;
  return <section className="dependency-inspector" aria-labelledby="dependency-heading">
    <div className="projection-section-title"><h2 id="dependency-heading">Why these checks?</h2><span>Recorded plan · {e.planning.status}</span></div>
    <p className="dependency-intro">Follow the declared dependencies, then compare the plan with what actually happened. These links describe a program, not demonstrated physical causes.</p>
    {e.modelChanged ? <p className="dependency-notice">The dependency model changed. Equal input hashes do not establish equivalent meaning across models.</p> : null}
    <label className="dependency-selector">Inspect a recorded node<select ref={selector} value={selected} onChange={event => setSelected(event.target.value)}><optgroup label="Checks">{e.checks.map(c => <option key={c.id} value={c.id}>{c.id} · {c.kind}</option>)}</optgroup><optgroup label="Inputs">{e.inputs.map(i => <option key={i.id} value={i.id}>{i.id} · {i.status}</option>)}</optgroup><optgroup label="Decision requirements">{e.decisions.map(d => <option key={d.id} value={d.id}>{d.id}</option>)}</optgroup></select></label>
    <div className="dependency-route" key={selected}>
      <div><h3>Declared dependencies</h3><Pages rows={dependencies} label="Direct dependencies" render={id => <div key={id}>{link(id)}</div>} />{!dependencies.length ? <p>This input is a declared starting point.</p> : null}</div>
      <div className="dependency-selected"><span>{type}</span><strong>{selected}</strong><span aria-live="polite">{check ? attemptLabel(check) : input ? `Current identity ${input.status}` : "Historical plan requirements"}</span></div>
      <div><h3>Declared dependents</h3><Pages rows={dependents} label="Direct dependents" render={id => <div key={id}>{link(id)}</div>} />{!dependents.length ? <p>No direct dependent is declared.</p> : null}</div>
    </div>
    <div className="dependency-reading" key={`reading:${selected}`}>
      {check ? <>
        <dl className="dependency-actions"><div><dt>Planned action</dt><dd>{check.planned === "reuse" ? "Reuse recorded evidence" : "Run check"}</dd></div><div><dt>Recorded attempt</dt><dd>{attemptLabel(check)}</dd></div></dl>
        {check.planned === "reuse" && check.attempted === null ? <p className="dependency-notice">Reuse was planned, but never attempted. This execution did not consume that evidence.</p> : null}
        <h3>Recorded selection reasons</h3>
        <Pages rows={check.reasons} label="Selection reasons" render={(reason, i) => <p className="dependency-reason" key={i}>{reasons[reason.code]}{reason.check ? <> Upstream check: <button className="dependency-inline" onClick={() => choose(reason.check!)}>{reason.check}</button>.</> : null}</p>} />
        {!check.reasons.length ? <p>No reason codes were recorded. Read affected inputs and the planned action together; an empty reason list does not grant reuse.</p> : null}
        <h3>Affected inputs</h3>
        <Pages rows={check.affected} label="Affected inputs" render={(item, i) => {
          const source = e.inputs.find(input => input.id === item.input)!;
          return <div className="dependency-affected" key={i}><div><button className="dependency-inline" onClick={() => choose(item.input)}>{item.input}</button><span>{item.reason === "unknown" ? "Unknown in the recorded planning comparison" : "Changed in the recorded comparison"}</span></div><p>Through <button className="dependency-inline" onClick={() => choose(item.via)}>{item.via}</button> · {priorLabel(source)} · current identity {source.status}.</p>{item.reason === "unknown" && source.status === "bound" ? <p>The current input is bound. The planning reason can describe its earlier unknown identity.</p> : null}</div>;
        }} />{!check.affected.length ? <p>No affected inputs are listed for this check.</p> : null}
        <p>Previous receipt: {check.previousReceipt ? "present" : "absent"}. Receipt presence alone does not establish usable evidence.</p>
        {check.refresh === "always" ? <p>Always-refresh is a program rule. This execution does not itself prove a fresh physical trial.</p> : null}
        <details><summary>Recorded codes and artifact identities</summary><dl><dt>Refresh rule</dt><dd>{check.refresh}</dd><dt>Reason codes</dt><dd>{check.reasons.map(r => r.code + (r.check ? `:${r.check}` : "")).join(" · ") || "None recorded"}</dd><dt>Current artifact SHA-256</dt><dd>{check.artifact ?? "No current artifact identity"}</dd><dt>Previous receipt artifact SHA-256</dt><dd>{check.previousArtifact ?? "No previous receipt"}</dd></dl></details>
      </> : input ? <>
        <h3>Input identity over the recorded change</h3><dl className="dependency-actions"><div><dt>Previous declaration</dt><dd>{priorLabel(input)}</dd></div><div><dt>Current identity</dt><dd>{input.status === "bound" ? "Bound to bytes" : "Unknown"}</dd></div></dl>
        <p>{!input.previousPresent ? "No prior declaration is recorded for this input." : input.previousSha === null ? "The input existed previously with an explicitly unknown identity." : "The previous digest is recorded metadata. It does not establish that the old input remains available."}</p>
        <details><summary>Compare input fingerprints</summary><dl><dt>Previous SHA-256</dt><dd>{input.previousSha ?? (input.previousPresent ? "Unknown" : "Not previously declared")}</dd><dt>Current SHA-256</dt><dd>{input.sha ?? "Unknown"}</dd></dl><p>Matching bytes do not authenticate measurements or establish physical equivalence.</p></details>
      </> : decision ? <>
        <h3>Requirements at the start of this execution</h3><p>These are historical selection requirements. A required check may already have completed; this list does not request another run.</p>
        <div className="dependency-actions"><div><h4>Required to run</h4><Pages rows={decision.required} label="Historically required checks" render={id => <div className="dependency-requirement" key={id}>{link(id)}<span>{attemptLabel(e.checks.find(c => c.id === id)!)}</span></div>} />{!decision.required.length ? <p>None listed.</p> : null}</div><div><h4>Planned as reusable</h4><Pages rows={decision.reusable} label="Historically reusable checks" render={id => <div className="dependency-requirement" key={id}>{link(id)}<span>{attemptLabel(e.checks.find(c => c.id === id)!)}</span></div>} />{!decision.reusable.length ? <p>None listed.</p> : null}</div></div>
        <p>Recorded applicability: {words(decision.applicability)}. Outcome: not adjudicated. Deployment: unresolved.</p><details><summary>Recorded obligation codes</summary><Pages rows={decision.obligations} label="Decision obligations" render={(code, i) => <p key={i}><code>{code}</code></p>} />{!decision.obligations.length ? <p>None listed for this decision.</p> : null}</details>
      </> : null}
    </div>
    <p className="projection-boundary">{e.planning.obligations} global planning obligations recorded. Their diagnostic text is not included. The browser checked displayed structure and record association; it did not rerun the engine.</p>
  </section>;
}
