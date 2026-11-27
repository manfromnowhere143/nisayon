import { useId, useState } from "react";
import { resolveWithin, type LoadedRun } from "../data/loader";
import {
  contextualFinding,
  pairedRun,
  signed,
  statusWords,
} from "../model/findings";
import {
  sameRun,
  type CaseRecord,
  type Depth,
  type Generation,
} from "../model/types";
import "../styles/caseBrief.css";
import type { InspectionStep } from "./MomentInspection";

interface Props {
  generation: Generation;
  caseRecord: CaseRecord;
  run: LoadedRun;
  onNavigate: (depth: Depth) => void;
  compact?: boolean;
  onMoment?: (origin: HTMLElement, step: InspectionStep) => void;
}
/** Progressive presentation of verified records, never another evaluator. */
export function CaseBrief({ generation, caseRecord, run, onNavigate, onMoment, compact = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const id = useId(),
    finding = contextualFinding(caseRecord, run.record, run.samples.rows);
  const words = statusWords(run.record),
    paired = pairedRun(caseRecord, run.record);
  const limitations = [
    ...new Set([...caseRecord.limitations, ...generation.limitations]),
  ];
  const transport = caseRecord.findings.find(
    (value) =>
      value.code === "gripper_transport_mismatch" &&
      sameRun(value.run, run.record.run),
  );
  const row =
    transport?.row_index == null ? null : run.samples.rows[transport.row_index];
  return (
    <section className="case-brief" aria-label="Case brief" data-compact={compact} data-expanded={expanded}>
      <section className="case-brief-finding" aria-labelledby={id}>
        <h3 id={id}>{finding.headline}</h3>
        <p className="brief-summary"><span>{words.origin === "simulator" ? "Recorded simulation" : "Recorded evidence"}</span><span>Task {words.task || "not recorded"}</span></p>
        {row && transport ? <dl className="brief-command" aria-label="Normalized gripper command at the finding">
          <div><dt>Intended</dt><dd>{signed(row.intended_action[6]!, 3)}</dd></div>
          <div><dt>Executed</dt><dd>{signed(row.executed_action[6]!, 3)}</dd></div>
        </dl> : null}
      </section>
      <nav className="brief-explore" aria-label="Explore this finding">
        {onMoment && finding.row !== null ? <button type="button" data-see-moment onClick={event => onMoment(event.currentTarget, transport ? "command" : "capture")}>See moment <span aria-hidden="true">↗</span></button> : null}
        {paired ? <button type="button" onClick={() => onNavigate("fork")}>Compare runs <span aria-hidden="true">↔</span></button> : null}
      </nav>
      <div className="case-brief-sources">
        <button type="button" aria-expanded={expanded} aria-controls={`${id}-details`} onClick={() => setExpanded(value => !value)}>{expanded ? "Less" : "Details"}<span aria-hidden="true">{expanded ? " −" : " +"}</span></button>
      </div>
      <div id={`${id}-details`} className="case-brief-more" hidden={!expanded}>
        <details className="brief-record" name={`${id}-sections`} open>
          <summary>Record</summary>
          <div className="brief-detail-body">
            <p className="case-brief-run">{run.record.role.replaceAll("_", " ")} · {run.record.run.run_id} · {run.record.condition_id}</p>
            <p className="case-brief-detail">{finding.detail}</p>
            {row && transport ? <p className="brief-qualification">Mismatch checked after clipping · threshold {transport.threshold}</p> : null}
            <dl className="case-brief-status">
              <div><dt>Execution</dt><dd>{words.process || "not recorded"}</dd></div>
              <div><dt>Measurement</dt><dd>{words.measurement || "not recorded"}</dd></div>
              <div><dt>Task outcome</dt><dd>{words.task || "not recorded"}</dd></div>
            </dl>
            <button type="button" className="quiet" onClick={() => onNavigate("moment")}>Inspect readings</button>
            <div className="case-brief-sources">
              <a href={generation.manifestUrl} target="_blank" rel="noreferrer">Generation manifest<span className="sr-only"> (JSON, new tab)</span></a>
              <a href={resolveWithin(generation.baseUrl, run.record.samples.path, "run")} target="_blank" rel="noreferrer">Selected run samples<span className="sr-only"> (JSON, new tab)</span></a>
            </div>
          </div>
        </details>
        <details className="case-brief-decisions" name={`${id}-sections`}>
          <summary>Decision</summary>
          <div className="brief-detail-body">
            <dl><DecisionSummary label="Diagnostic" record={caseRecord.decisions.diagnostic_decision} /><DecisionSummary label="Separate confirmation" record={caseRecord.decisions.confirmation_decision} /></dl>
            <p>A completed execution alone does not establish a correction.</p>
            <button type="button" className="quiet" onClick={() => onNavigate("decision")}>Read decision & reasons</button>
            <button type="button" className="quiet" onClick={() => onNavigate("conditions")}>Inspect conditions</button>
          </div>
        </details>
        <details className="case-brief-scope" name={`${id}-sections`}>
          <summary>Scope · {limitations.length} limits</summary>
          <div className="brief-detail-body">
            <p>{words.origin === "simulator" ? "Recorded simulation, not a live robot or a new experiment." : `Recorded evidence · origin: ${words.origin || "not declared"}.`}</p>
            <ul>{limitations.map(item => <li key={item}>{item}</li>)}</ul>
            {!limitations.length ? <p>No limitations are declared. This does not establish general applicability.</p> : null}
          </div>
        </details>
      </div>
    </section>
  );
}

function DecisionSummary({
  label,
  record,
}: {
  label: string;
  record: CaseRecord["decisions"][string] | undefined;
}) {
  const content = record?.content;
  const decision =
    content &&
    typeof content === "object" &&
    "decision" in content &&
    typeof content.decision === "string" &&
    content.decision.trim()
      ? content.decision
      : null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{decision ?? (record ? "not embedded" : "not referenced")}</dd>
    </div>
  );
}
