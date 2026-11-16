import { resolveWithin, type LoadedRun } from "../data/loader";
import { contextualFinding, pairedRun, statusWords } from "../model/findings";
import type { CaseRecord, Depth, Generation } from "../model/types";
import "../styles/caseBrief.css";

interface Props {
  generation: Generation;
  caseRecord: CaseRecord;
  run: LoadedRun;
  onNavigate: (depth: Depth) => void;
}

// This is a reading path through already verified records, not another evaluator.
export function CaseBrief({ generation, caseRecord, run, onNavigate }: Props) {
  const finding = contextualFinding(caseRecord, run.record, run.samples.rows);
  const words = statusWords(run.record);
  const paired = pairedRun(caseRecord, run.record);
  const limitations = [...new Set([...caseRecord.limitations, ...generation.limitations])];
  return <section className="case-brief" aria-labelledby="case-brief-title" tabIndex={0}>
    <header className="case-brief-heading">
      <p className="research-micro">FOLLOW THE EVIDENCE</p>
      <h3 id="case-brief-title">From change to decision.</h3>
      <p>Compare the recorded runs, inspect their conditions, then read the evaluator’s decision.</p>
    </header>

    <div className="case-brief-records"><section className="case-brief-finding" aria-labelledby="case-brief-finding">
      <p className="case-brief-label">Selected run · {run.record.role.replaceAll("_", " ")}</p>
      <h4 id="case-brief-finding">{finding.headline}</h4>
      <p className="case-brief-detail num">{finding.detail}</p>
      <p className="case-brief-run mono">{run.record.run.run_id} · {run.record.condition_id}</p>
      <dl className="case-brief-status">
        <div><dt>Execution</dt><dd>{words.process || "not recorded"}</dd></div>
        <div><dt>Measurement</dt><dd>{words.measurement || "not recorded"}</dd></div>
        <div><dt>Task outcome</dt><dd>{words.task || "not recorded"}</dd></div>
      </dl>
      <button type="button" className="quiet" onClick={() => onNavigate("moment")}>Inspect readings <span aria-hidden="true">↗</span></button>
    </section>

    <section className="case-brief-decisions" aria-labelledby="case-brief-decisions">
      <h4 id="case-brief-decisions">Recorded decisions</h4>
      <p>These apply to the experiment records. A completed execution alone does not establish a correction.</p>
      <dl>
        <DecisionSummary label="Diagnostic" record={caseRecord.decisions.diagnostic_decision} />
        <DecisionSummary label="Separate confirmation" record={caseRecord.decisions.confirmation_decision} />
      </dl>
      <button type="button" className="quiet" onClick={() => onNavigate("decision")}>Read decision & reasons <span aria-hidden="true">↗</span></button>
    </section></div>

    <nav className="case-brief-path" aria-label="Follow this experiment">
      <button type="button" onClick={() => onNavigate("fork")}><span>Compare runs <span aria-hidden="true">↗</span></span><small>{paired ? `${run.record.run.run_id} / ${paired.run.run_id}` : "Inspect the available comparison record"}</small></button>
      <button type="button" onClick={() => onNavigate("conditions")}><span>Inspect conditions <span aria-hidden="true">↗</span></span><small>Check the scope of the confirmation</small></button>
    </nav>

    <section className="case-brief-scope" aria-labelledby="case-brief-scope">
      <h4 id="case-brief-scope">Scope & sources</h4>
      <p>{words.origin === "simulator" ? "Recorded simulation. The laboratory reconstructs retained configurations; it is not a live robot or a new experiment." : `Recorded evidence · origin: ${words.origin || "not declared"}. The laboratory is a view of the retained record.`}</p>
      <p>{limitations[0] ?? "No scope limitations are declared in this record. This does not establish general applicability."}</p>
      {limitations.length > 1 ? <details><summary>All retained limitations ({limitations.length})</summary><ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul></details> : null}
      <div className="case-brief-sources">
        <a href={generation.manifestUrl} target="_blank" rel="noreferrer">Generation manifest <span className="sr-only">(JSON, new tab)</span><span aria-hidden="true">↗</span></a>
        <a href={resolveWithin(generation.baseUrl, run.record.samples.path, "run")} target="_blank" rel="noreferrer">Selected run samples <span className="sr-only">(JSON, new tab)</span><span aria-hidden="true">↗</span></a>
      </div>
    </section>
  </section>;
}

function DecisionSummary({ label, record }: { label: string; record: CaseRecord["decisions"][string] | undefined }) {
  const content = record?.content;
  const decision = content && typeof content === "object" && "decision" in content && typeof content.decision === "string" && content.decision.trim() ? content.decision : null;
  return <div><dt>{label}</dt><dd>{decision ?? (record ? "not embedded" : "not referenced")}</dd></div>;
}
