import { useMemo } from "react";
import type { Fields } from "../data/study";
import { clockGroups, clockLabel, processorReport, temporalReport, type Opportunity, type TemporalRow } from "../model/mechanisms";
import { SectionDeck } from "./RecordPages";
import { Choice } from "./Choice";

const text = (v: unknown) => v === null || v === undefined ? "unrecorded" : String(v).replaceAll("_", " ");
const boolean = (v: boolean | null) => v === null ? "unresolved" : v ? "yes" : "no";
const list = (v: unknown) => Array.isArray(v) ? v : [];
const fields = (v: unknown): Fields => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Fields : {};
const seconds = (v: unknown) => typeof v === "number" && Number.isFinite(v) ? v.toFixed(6) : "unrecorded";
interface Props { record: Fields; item: string | null; onItem: (item: string) => void }

function Facts({ values }: { values: [string, unknown][] }) {
  return <dl className="mechanism-facts">{values.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{text(value)}</dd></div>)}</dl>;
}

function OpportunityAxis({ rows, selected, onSelect }: { rows: readonly Opportunity[]; selected: number; onSelect: (index: number) => void }) {
  const groups = useMemo(() => clockGroups(rows), [rows]);
  return <div className="opportunity-axes">{groups.map(group => <div key={`${group.clock}/${group.unit}`}><p className="fine">{group.clock} · recorded opportunities · {group.unit}</p><svg viewBox="0 0 700 58" aria-label={`Opportunities on the ${group.clock} clock`}>
    <line x1="14" x2="686" y1="22" y2="22" className="opportunity-rule" />
    {group.items.map(({ row, index, x }) => <g key={row.input_id} role="button" tabIndex={0} aria-label={`${row.input_id}, ${clockLabel(row.at)}, ${row.counted ?? "unresolved"}`} aria-pressed={index === selected} onClick={() => onSelect(index)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(index); } }}>
      <rect x={14 + x * 672 - 12} y="0" width="24" height="44" fill="transparent" />
      <circle cx={14 + x * 672} cy="22" r={index === selected ? 5 : 3} className="opportunity-point" data-counted={row.counted ?? "unknown"} />
    </g>)}
    <text x="14" y="54">{clockLabel(group.items.reduce((a, b) => a.value < b.value ? a : b).row.at)}</text>
    {group.items.some(i => i.x !== .5) ? <text x="686" y="54" textAnchor="end">{clockLabel(group.items.reduce((a, b) => a.value > b.value ? a : b).row.at)}</text> : null}
  </svg></div>)}{rows.some(row => !row.at.exact_integer) ? <p className="fine">Non-integer or missing clock stamps remain in the record and are not plotted.</p> : null}</div>;
}

export function TemporalView({ record, item, onItem }: Props) {
  const report = useMemo(() => temporalReport(record), [record]);
  const [populationName, identity, selectedIndex] = (item ?? "").split("/");
  const groups = [...report.populations, { name: "interrupted_prefixes", assignments: report.prefixes.length, rows: report.prefixes }];
  const population = groups.find(p => p.name === populationName) ?? groups.find(p => p.name === "combined_deadline") ?? groups[0]!;
  const row: TemporalRow | undefined = population.rows.find(r => r.identity === identity) ?? population.rows[0];
  if (!row) return <p>No assignments retained in this population.</p>;
  const opportunities = row.assigned_usefulness.rows;
  const selected = /^\d+$/.test(selectedIndex ?? "") ? Math.min(Number(selectedIndex), Math.max(0, opportunities.length - 1)) : 0;
  const opportunity = opportunities[selected];
  const select = (index: number) => onItem(`${population.name}/${row.identity}/${index}`);
  const pair = report.pairs.find(p => p.population === population.name && (p.selected === row.identity || p.conventional === row.identity));
  return <div className="mechanism-view">
    <div className="mechanism-picker"><Choice label="Temporal population" value={population.name} options={groups.map(p => ({ value: p.name, label: `${text(p.name)} · ${p.assignments}` }))} onChange={name => { const p = groups.find(p => p.name === name)!; onItem(`${name}/${p.rows[0]?.identity ?? ""}/0`); }} /><Choice label="Temporal assignment" value={row.identity} options={population.rows.map(r => ({ value: r.identity, label: r.identity }))} onChange={id => onItem(`${population.name}/${id}/0`)} /></div>
    {item && (populationName !== population.name || identity !== row.identity) ? <p role="status" className="fine">The requested assignment is absent from this publication. Showing the first available assignment in this population.</p> : null}
    <div className="mechanism-scope"><span>Execution disconnected</span><span>Virtual software clocks</span><span>Robot outcome: {text(row.robot_task_outcome)}</span></div>
    <SectionDeck label="Temporal evidence" sections={[
      { id: "overview", label: "Overview", content: <><div className="mechanism-intro"><p className="eyebrow">Temporal integration / recorded software</p><h3>Was the command still valid when it was sent?</h3><p>Inspect the frozen contract, recorded dispatch opportunities and acknowledged delivery separately. Robot task outcome remains {text(row.robot_task_outcome)}.</p></div>
    <Facts values={[["Process", row.process_outcome], ["Frozen temporal contract", row.temporal_contract], ["Assigned contract", row.assigned_contract], ["Assigned usefulness", row.assigned_usefulness.status]]} /></> },
      { id: "opportunities", label: "Opportunities", content: <>
    <h4>Recorded opportunities</h4>
    <p className="fine">Each clock has its own axis. A software send attempt, its validity and an acknowledgement are separate readings.</p>
    <OpportunityAxis rows={opportunities} selected={selected} onSelect={select} />
    {opportunity ? <><Choice label="Recorded opportunity" value={String(selected)} options={opportunities.map((o, i) => ({ value: String(i), label: `${o.input_id} · ${clockLabel(o.at)}` }))} onChange={v => select(Number(v))} /><Facts values={[["Observed event", opportunity.observed.length ? opportunity.observed.join(" · ") : "not observed"], ["Counted as", opportunity.counted ?? "unresolved"], ["Valid", boolean(opportunity.valid)], ["Acknowledged", boolean(opportunity.acknowledged)]]} />
      <p className="fine">{text(opportunity.at.clock)} · exact stamp <code>{opportunity.at.value ?? "unrecorded"} {opportunity.at.unit}</code></p>
      {opportunity.refusal_reasons.length ? <div className="mechanism-reason"><strong>Refusal</strong><p>{opportunity.refusal_reasons.map(text).join(" · ")}</p></div> : null}
      <details><summary>Attempt identities</summary>{opportunity.attempts.length ? opportunity.attempts.map(id => <p className="fine mono" key={id}>{id}</p>) : <p className="fine">No send attempt is recorded for this opportunity.</p>}</details>
    </> : <p>No assigned dispatch opportunity was retained.</p>}
    <p className="fine">{text(row.assigned_usefulness.premise)}</p></> },
      { id: "paired", label: "Comparison", content: <>
    {pair ? <section className="mechanism-comparison"><h4>Paired conventional procedure</h4><Facts values={[["Events identical", pair.events_equal], ["Full assessments identical", pair.full_assessments_equal]]} /><button type="button" className="quiet" onClick={() => onItem(`${population.name}/${pair.selected === row.identity ? pair.conventional : pair.selected}/0`)}>Inspect paired assignment ↗</button><p className="fine">A matched result does not establish comparative advantage.</p></section> : null}{!pair ? <p>No paired conventional assignment is retained.</p> : null}</> },
      { id: "source", label: "Source", content: <>
    <details><summary>Contract interpretation and source</summary><p className="fine">The frozen temporal contract and the later assigned-opportunity contract have distinct definitions. Refusal can satisfy a timing rule without completing useful work.</p><Facts values={[["Integrity", row.integrity], ["Source pointer", row.source_pointer], ["Trace SHA-256", row.trace_sha256], ["Snapshot SHA-256", row.snapshot_sha256]]} /><p className="fine">{report.scope}</p></details></> },
    ]} />
  </div>;
}

export function ProcessorView({ record, item, onItem }: Props) {
  const report = useMemo(() => processorReport(record), [record]);
  const candidate = report.candidates.find(c => c.id === item) ?? report.candidates.find(c => c.name === "explicit_override") ?? report.candidates[0]!;
  const executions = report.executions.filter(e => e.candidate === candidate.name);
  return <div className="mechanism-view">
    <div className="mechanism-candidates" role="group" aria-label="Processor candidates">{report.candidates.map(c => <button key={c.id} type="button" aria-pressed={c.id === candidate.id} onClick={() => onItem(c.id)}><span>{c.id.split("_")[0]}</span><strong>{text(c.name)}</strong><small>{text(c.decision.outcome)}</small></button>)}</div>
    {item && item !== candidate.id ? <p className="fine" role="status">The requested candidate is absent from this publication. Showing the explicit override assessment.</p> : null}
    <div className="mechanism-scope"><span>Execution disconnected</span><span>Robot outcome: {text(report.decision.robot_task_outcome)}</span></div>
    <SectionDeck label="Processor evidence" sections={[
      { id: "decision", label: "Decision", content: <><div className="mechanism-intro"><p className="eyebrow">External processor / retained correction</p><h3>Correct arithmetic needs the right statistics.</h3><p>{report.scope}</p></div>
    <Facts values={[["Software decision", candidate.decision.outcome], ["Deployment binding", candidate.decision.deployment_binding ?? report.decision.deployment_binding], ["Robot task outcome", report.decision.robot_task_outcome]]} />
    <div className="mechanism-reason"><p>{candidate.decision.reason}</p>{candidate.decision.binding_note ? <p className="fine">{text(candidate.decision.binding_note)}</p> : null}</div></> },
      { id: "witnesses", label: "Witnesses", content: <>
    <h4>What each witness establishes · arm B</h4>
    {executions.length ? <div className="processor-witnesses">{executions.map(e => { const expected = fields(e.expected); return <article key={String(e.id)}><div><span className="eyebrow">{text(e.processor)} · {text(e.direction)}</span><strong>{String(e.feature)}</strong></div><div><span className="processor-result">{text(expected.class)}</span><p className="fine">{text(expected.detail)}</p></div><dl><div><dt>Reference</dt><dd>{text(e.agreement)}</dd></div><div><dt>Non-vacuous witness</dt><dd>{e.vacuous === false ? "yes" : "no"}</dd></div><div><dt>Statistics provenance</dt><dd>{text(e.stats_provenance)}</dd></div></dl><details><summary>Binding & source</summary><p className="fine">Bound key: {text(expected.bound_key)} · matches: {list(expected.matches).length}</p><p className="fine mono">{String(e.id)} · assessment {String(e.source_pointer)}</p></details></article>; })}</div> : <p>This candidate was not executed. Its outcome remains unresolved.</p>}</> },
      { id: "obligations", label: "Obligations", content: <>
    <details><summary>Frozen obligations</summary>{report.obligations.map(o => <p className="fine" key={String(o.id)}><strong>{text(o.id)} · {text(o.feature)}</strong><br />{text(o.requirement)}</p>)}</details></> },
      { id: "comparison", label: "Comparison", content: <>
    <section className="mechanism-comparison"><h4>What the comparison can establish</h4><p>{text(report.comparison.reason)}</p><Facts values={[["Comparative value", report.comparison.comparative_value], ["Complete cost advantage", report.comparison.complete_cost_advantage]]} /><div className="mechanism-costs">{Object.entries(report.costs).map(([arm, v]) => <div key={arm}><span>Arm {arm} · command wall</span><strong>{seconds(fields(v).wall_seconds)} <small>s</small></strong></div>)}</div><p className="fine">One warm local execution. Unmeasured costs: {report.unknown_costs.map(text).join(", ")}.</p></section></> },
      { id: "scope", label: "Scope", content: <>
    <p className="fine">{report.boundary}</p><div className="mechanism-scope"><span>Execution disconnected</span><span>Private model inputs are not redistributed</span></div></> },
    ]} />
  </div>;
}
