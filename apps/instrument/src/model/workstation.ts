// A read-only projection of the admitted recording. The workstation owns no
// clock, requests, task state or acceptance logic of its own.
import type { LoadedRun } from "../data/loader";
import { actionLabel, timeForPhase } from "./findings";
import { sameRun, type CaseRecord, type Generation, type Moment, type SampleRow } from "./types";

export interface TraceColumn {
  time: number;
  min: number | null;
  max: number | null;
  first: number | null;
  last: number | null;
  gap: boolean;
}
export interface WorkstationSeries {
  kind: "age" | "command" | "height";
  component: number;
  label: string;
  unit: string;
  reference: number | null;
  columns: readonly TraceColumn[];
  start: number;
  end: number;
  min: number;
  max: number;
}
export interface WorkstationReading {
  identity: string;
  caseLabel: string;
  runLabel: string;
  status: "recorded" | "loading" | "unavailable";
  phase: "before" | "after";
  time: number | null;
  signalTime: number | null;
  row: number;
  step: number | null;
  count: number;
  value: number | null;
  comparison: number | null;
  series: WorkstationSeries;
}
const finite = (value: number | null | undefined): number | null => typeof value === "number" && Number.isFinite(value) ? value : null;
const valueAt = (row: SampleRow, kind: WorkstationSeries["kind"], component: number) =>
  finite(kind === "age" ? row.observation_age_s === null ? null : row.observation_age_s * 1000
    : kind === "command" ? row.executed_action[component] : row.cube_height_m * 1000);

/** Preserve extrema, including one-row spikes. Missing samples break the trace;
 * no interpolation or zeros are manufactured to fill a missing observation. */
export function workstationSeries(caseRecord: CaseRecord, run: LoadedRun): WorkstationSeries {
  const findings = caseRecord.findings.filter(finding => sameRun(finding.run, run.record.run));
  const command = findings.find(finding => ["gripper_transport_mismatch", "first_action_mismatch"].includes(finding.code));
  const kind = findings.some(finding => finding.code === "observation_age_violation") ? "age" : command ? "command" : "height";
  const component = command?.component ?? 6;
  const label = kind === "age" ? "Observation age" : kind === "command" ? `${actionLabel(component)} command` : "Cube height";
  const reference = finite(kind === "age" ? caseRecord.predicates.max_observation_age_s * 1000 : kind === "height" ? caseRecord.predicates.min_cube_height_m * 1000 : null);
  const rows = run.samples.rows;
  const size = Math.max(1, Math.ceil(rows.length / 192));
  const columns: TraceColumn[] = [];
  let min = Math.min(0, reference ?? 0), max = Math.max(0, reference ?? 0);
  for (let start = 0; start < rows.length; start += size) {
    const block = rows.slice(start, start + size);
    const values = block.map(row => valueAt(row, kind, component));
    const valid = values.filter((value): value is number => value !== null);
    const low = valid.length ? Math.min(...valid) : null, high = valid.length ? Math.max(...valid) : null;
    min = Math.min(min, low ?? min); max = Math.max(max, high ?? max);
    const first = block[0]!;
    columns.push({ time: kind === "height" ? first.next_sim_time_s : first.action_sim_time_s, min: low, max: high, first: values[0] ?? null, last: values.at(-1) ?? null, gap: valid.length !== values.length });
  }
  const first = rows[0], last = rows.at(-1);
  return { kind, component, label, unit: kind === "age" ? "ms" : kind === "command" ? "normalized" : "mm", reference, columns,
    start: first ? kind === "height" ? first.next_sim_time_s : first.action_sim_time_s : 0,
    end: last ? kind === "height" ? last.next_sim_time_s : last.action_sim_time_s : 0,
    min, max: max === min ? min + 1 : max };
}

export function workstationReading(generation: Generation, caseRecord: CaseRecord, run: LoadedRun, moment: Moment, series: WorkstationSeries, pending: boolean): WorkstationReading {
  // Check the full binding, not a run label shared by many bundles. A refused
  // binding clears values even if an old row happens to exist at that index.
  const bound = generation.sha256 === moment.generation_sha256 && caseRecord.case_key === moment.case_key
    && sameRun(run.record.run, moment.run) && sameRun(run.samples.run, moment.run);
  const row = bound ? run.samples.rows[moment.row_index] ?? null : null;
  const framesBound = run.frames && sameRun(run.frames.run, moment.run);
  const frame = framesBound ? run.frames!.rows[moment.row_index]?.[moment.phase] : null;
  return {
    identity: `${generation.sha256}:${caseRecord.case_key}:${run.record.run.bundle_sha256}:${run.record.run.run_id}:${moment.row_index}:${moment.phase}`,
    caseLabel: caseRecord.case_id, runLabel: run.record.run.run_id,
    status: !bound || !row ? "unavailable" : pending ? "loading" : "recorded",
    phase: moment.phase, time: row ? finite(frame?.sim_time_s ?? timeForPhase(row, moment.phase)) : null,
    signalTime: row ? series.kind === "height" ? row.next_sim_time_s : row.action_sim_time_s : null,
    row: moment.row_index, step: row?.step ?? null, count: run.samples.rows.length,
    value: row ? valueAt(row, series.kind, series.component) : null,
    comparison: row ? series.kind === "command" ? finite(row.intended_action[series.component]) : series.reference : null,
    series,
  };
}
