import { arr, DecodeError, int, rec, str } from "./decode";
import type { Fields } from "../data/study";

export interface Opportunity { input_id: string; at: { value: string | null; clock: string; unit: string; exact_integer: boolean }; observed: string[]; attempts: string[]; refusal_reasons: string[]; counted: string | null; valid: boolean | null; acknowledged: boolean | null }
export interface TemporalRow extends Fields { identity: string; process_outcome: string; integrity: string; temporal_contract: string; assigned_contract: string; robot_task_outcome: string; source_pointer: string; assigned_usefulness: Fields & { status: string; rows: Opportunity[] } }
export interface TemporalReport { scope: string; populations: { name: string; assignments: number; rows: TemporalRow[] }[]; prefixes: TemporalRow[]; pairs: Fields[]; coverage: Fields }
const strings = (v: unknown) => arr(v, "mechanism.strings", 1000).map(x => str(x, "mechanism.string"));
const status = (v: unknown) => str(v, "mechanism.status");
export function temporalReport(value: Fields): TemporalReport {
  if (value.schema !== "nisayon.ui-temporal-contracts.v1" || value.execution_connected !== false) throw new DecodeError("temporal", "unsupported authority");
  const row = (v: unknown): TemporalRow => {
    const d = rec(v, "temporal.row"), usefulness = rec(d.assigned_usefulness, "temporal.usefulness");
    for (const k of ["identity", "process_outcome", "integrity", "temporal_contract", "assigned_contract", "robot_task_outcome", "source_pointer"]) str(d[k], `temporal.${k}`);
    status(usefulness.status);
    const rows = arr(usefulness.rows, "temporal.opportunities", 1000).map(v => {
      const o = rec(v, "opportunity"), at = rec(o.at, "opportunity.at");
      str(o.input_id, "opportunity.id"); str(at.clock, "opportunity.clock"); str(at.unit, "opportunity.unit");
      if (at.value !== null) str(at.value, "opportunity.value");
      if (typeof at.exact_integer !== "boolean" || (at.exact_integer && !/^-?\d{1,40}$/.test(String(at.value)))) throw new DecodeError("opportunity", "invalid exact clock stamp");
      for (const k of ["valid", "acknowledged"]) if (o[k] !== null && typeof o[k] !== "boolean") throw new DecodeError("opportunity", `missing ${k} is not false`);
      if (o.counted !== null) str(o.counted, "opportunity.counted");
      return { ...o, at, observed: strings(o.observed), attempts: strings(o.attempts), refusal_reasons: strings(o.refusal_reasons) } as unknown as Opportunity;
    });
    return { ...d, assigned_usefulness: { ...usefulness, rows } } as TemporalRow;
  };
  const populations = arr(value.populations, "temporal.populations", 50).map(v => {
    const p = rec(v, "population"), rows = arr(p.rows, "population.rows", 2000).map(row);
    if (int(p.assignments, "population.count") !== rows.length || new Set(rows.map(r => r.identity)).size !== rows.length) throw new DecodeError("population", "membership disagrees");
    return { name: str(p.name, "population.name"), assignments: rows.length, rows };
  });
  const coverage = rec(value.coverage, "temporal.coverage"), prefixes = arr(value.prefixes, "temporal.prefixes", 50).map(row);
  if (!populations.length || new Set(populations.map(p => p.name)).size !== populations.length) throw new DecodeError("temporal", "population membership disagrees");
  if (coverage.assignments !== populations.reduce((n, p) => n + p.rows.length, 0) || coverage.prefixes !== prefixes.length) throw new DecodeError("temporal", "coverage disagrees");
  return { scope: str(value.scope, "temporal.scope"), populations, prefixes, pairs: arr(value.pairs, "temporal.pairs", 2000).map(v => rec(v, "pair")), coverage };
}

export interface ProcessorCandidate { id: string; name: string; description: string; decision: Fields & { outcome: string; reason: string } }
export interface ProcessorReport { scope: string; candidates: ProcessorCandidate[]; executions: Fields[]; obligations: Fields[]; comparison: Fields; decision: Fields; confirmation_scope: Fields; costs: Fields; unknown_costs: string[]; boundary: string }
export function processorReport(value: Fields): ProcessorReport {
  if (value.schema !== "nisayon.ui-processor-decision.v1" || value.execution_connected !== false) throw new DecodeError("processor", "unsupported authority");
  str(value.scope, "processor.scope"); str(value.boundary, "processor.boundary");
  const candidates = arr(value.candidates, "processor.candidates", 32).map(v => {
    const c = rec(v, "candidate"), decision = rec(c.decision, "candidate.decision");
    for (const k of ["id", "name", "description"]) str(c[k], `candidate.${k}`);
    status(decision.outcome); str(decision.reason, "candidate.reason");
    return c as unknown as ProcessorCandidate;
  });
  if (!candidates.length || new Set(candidates.map(c => c.id)).size !== candidates.length) throw new DecodeError("processor", "candidate membership disagrees");
  const executions = arr(value.executions, "processor.executions", 2000).map(v => {
    const e = rec(v, "execution"); for (const k of ["id", "candidate", "feature", "processor", "direction", "agreement", "status"]) str(e[k], `execution.${k}`);
    if (!candidates.some(c => c.name === e.candidate)) throw new DecodeError("processor", "execution candidate absent");
    const expected = rec(e.expected, "execution.expected"); str(expected.class, "execution.class");
    if (typeof e.vacuous !== "boolean") throw new DecodeError("processor", "witness vacuity is missing");
    return e;
  });
  for (const k of ["decision", "comparison", "confirmation_scope", "costs"]) rec(value[k], `processor.${k}`);
  return { ...value, candidates, executions, obligations: arr(value.obligations, "processor.obligations", 100).map(v => rec(v, "obligation")), unknown_costs: strings(value.unknown_costs) } as unknown as ProcessorReport;
}

export function clockGroups(rows: readonly Opportunity[]) {
  const groups = new Map<string, { clock: string; unit: string; items: { row: Opportunity; index: number; value: bigint; x: number }[] }>();
  rows.forEach((row, index) => {
    if (!row.at.exact_integer || row.at.value === null) return;
    const key = JSON.stringify([row.at.clock, row.at.unit]);
    const group = groups.get(key) ?? { clock: row.at.clock, unit: row.at.unit, items: [] };
    group.items.push({ row, index, value: BigInt(row.at.value), x: 0 }); groups.set(key, group);
  });
  for (const group of groups.values()) {
    const stamps = group.items.map(i => i.value), min = stamps.reduce((a, b) => a < b ? a : b), max = stamps.reduce((a, b) => a > b ? a : b);
    for (const item of group.items) item.x = max === min ? .5 : Number(item.value - min) / Number(max - min);
  }
  return [...groups.values()];
}
export function clockLabel(stamp: Opportunity["at"]): string {
  if (stamp.value === null) return "unrecorded";
  if (!stamp.exact_integer) return `${stamp.value} ${stamp.unit} · invalid integer stamp`;
  if (stamp.unit !== "ns") return `${stamp.value} ${stamp.unit}`;
  const value = BigInt(stamp.value), positive = value < 0n ? -value : value, decimal = (positive % 1000000n).toString().padStart(6, "0").replace(/0+$/, "");
  return `${value < 0n ? "−" : ""}${positive / 1000000n}${decimal ? `.${decimal}` : ""} ms`;
}
