// Descriptive findings derived in the browser from verified rows. They are not
// evaluator decisions and never replace a reason code.

import { sameRun, type CaseRecord, type MismatchResult, type RunRecord, type SampleRow } from "./types";
import { isRecord } from "./decode";

export const ACTION_LABELS = ["x", "y", "z", "rot x", "rot y", "rot z", "gripper"] as const;

export function actionLabel(component: number): string {
  return ACTION_LABELS[component] ?? `component ${component}`;
}

// First row where any intended component differs exactly from its executed
// component. Tolerance is zero; the comparison is stated with the result.
export function firstActionMismatch(rows: readonly SampleRow[]): MismatchResult | null {
  for (const row of rows) {
    const n = Math.min(row.intended_action.length, row.executed_action.length);
    for (let c = 0; c < n; c += 1) {
      const intended = row.intended_action[c] as number;
      const executed = row.executed_action[c] as number;
      if (intended !== executed) {
        return { row_index: row.row_index, step: row.step, component: c, intended, executed, action_sim_time_s: row.action_sim_time_s };
      }
    }
  }
  return null;
}

export function mismatchAgrees(a: MismatchResult | null, b: MismatchResult | null): boolean {
  if (a === null || b === null) return a === b;
  return a.row_index === b.row_index && a.component === c(b) && a.intended === b.intended && a.executed === b.executed;
  function c(x: MismatchResult): number {
    return x.component;
  }
}

export interface MismatchDescription {
  headline: string;
  detail: string;
}

export function describeMismatch(result: MismatchResult | null, rowCount: number): MismatchDescription {
  if (result === null) {
    return { headline: "Intended and executed actions agree on every row.", detail: `${rowCount} rows compared exactly.` };
  }
  const label = actionLabel(result.component);
  const reversed = Math.sign(result.intended) !== Math.sign(result.executed) && result.intended !== 0 && result.executed !== 0;
  const magnitude = Math.abs(result.executed - result.intended);
  const headline = reversed
    ? `${capital(label)} command reversed at step ${result.step}.`
    : magnitude < 1e-3
      ? `${capital(label)} command clipped at step ${result.step}.`
      : `${capital(label)} command differs at step ${result.step}.`;
  const detail = `intended ${signed(result.intended)} · executed ${signed(result.executed)} · component ${result.component} (${label}) · ${result.action_sim_time_s.toFixed(2)} s`;
  return { headline, detail };
}

export function signed(value: number, digits = 6): string {
  const s = value.toFixed(digits);
  return value > 0 ? `+${s}` : value === 0 ? ` ${s}` : s.replace("-", "−");
}

function capital(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// Rows whose consumed observation is older than the declared maximum age.
export function observationAgeViolations(rows: readonly SampleRow[], maxAgeS: number): SampleRow[] {
  return rows.filter((row) => row.observation_age_s !== null && row.observation_age_s > maxAgeS);
}

export interface StatusWords {
  process: string;
  measurement: string;
  task: string;
  execution: string;
  origin: string;
}

export function statusWords(run: RunRecord): StatusWords {
  return {
    process: run.process_status,
    measurement: run.measurement_status,
    task: run.task_outcome,
    execution: run.execution_mode,
    origin: run.evidence_origin,
  };
}

export function pairedRun(caseRecord: CaseRecord, run: RunRecord): RunRecord | null {
  const pairs = caseRecord.confirmation?.pairs;
  if (Array.isArray(pairs)) {
    for (const pair of pairs) {
      if (!isRecord(pair) || !isRecord(pair.reference_run) || !isRecord(pair.candidate_run)) continue;
      const referenceKey = pair.reference_run;
      const candidateKey = pair.candidate_run;
      const reference = caseRecord.runs.find((r) => r.run.bundle_sha256 === referenceKey.bundle_sha256 && r.run.run_id === referenceKey.run_id);
      const candidate = caseRecord.runs.find((r) => r.run.bundle_sha256 === candidateKey.bundle_sha256 && r.run.run_id === candidateKey.run_id);
      if (reference && candidate) {
        if (sameRun(run.run, reference.run)) return candidate;
        if (sameRun(run.run, candidate.run)) return reference;
      }
    }
  }
  const peers = caseRecord.runs.filter((r) => r.run.bundle_sha256 === run.run.bundle_sha256 && r.condition_id === run.condition_id && r.stage === run.stage && !sameRun(r.run, run.run));
  return run.role === "reference" ? peers.find((r) => r.role === "regression") ?? peers.find((r) => r.role === "correction") ?? null : peers.find((r) => r.role === "reference") ?? null;
}

// A frozen evaluator entry is scoped by stage and execution bundle, not name.
export function evaluatorForRun(caseRecord: CaseRecord, run: RunRecord): Record<string, unknown> | null {
  const content = caseRecord.decisions[`${run.stage ?? "diagnostic"}_decision`]?.content;
  if (!isRecord(content)) return null;
  const bundle = content.execution_bundle_sha256 ?? content.bundle_sha256;
  if (typeof bundle === "string" && bundle !== run.run.bundle_sha256) return null;
  if (!isRecord(content.runs)) return null;
  const entry = content.runs[run.run.run_id];
  return isRecord(entry) ? entry : null;
}

export interface ContextFinding { headline: string; detail: string; row: number | null; step: number | null }
export function contextualFinding(caseRecord: CaseRecord, run: RunRecord, rows: readonly SampleRow[]): ContextFinding {
  if (caseRecord.findings.some((f) => f.code === "first_action_mismatch" && sameRun(f.run, run.run))) {
    const mismatch = firstActionMismatch(rows);
    return { ...describeMismatch(mismatch, rows.length), row: mismatch?.row_index ?? null, step: mismatch?.step ?? null };
  }
  const unavailable = rows.filter((r) => r.policy.before === "unavailable" || r.policy.after === "unavailable");
  if (unavailable.length) return { headline: "Policy state was not recorded.", detail: `Telemetry is unavailable at ${unavailable.length} of ${rows.length} rows. Episode reset and unavailable hidden state remain separate facts.`, row: unavailable[0]!.row_index, step: unavailable[0]!.step };
  const finding = caseRecord.findings.find((f) => sameRun(f.run, run.run));
  if (finding) {
    const row = finding.row_index === null ? null : rows[finding.row_index];
    if (finding.code === "observation_age_violation" && row) return { headline: `Observation arrives late at step ${row.step}.`, detail: `Consumed observation age ${(row.observation_age_s! * 1000).toFixed(0)} ms · limit ${caseRecord.predicates.max_observation_age_s} s · task ${run.task_outcome}.`, row: row.row_index, step: row.step };
    if (finding.code === "gripper_transport_mismatch" && row) return { headline: `Gripper command reversed at step ${row.step}.`, detail: `intended ${signed(row.intended_action[6]!)} · executed ${signed(row.executed_action[6]!)} · after normalized clipping · threshold ${finding.threshold}.`, row: row.row_index, step: row.step };
    return { headline: finding.detail ?? finding.code, detail: finding.definition, row: finding.row_index, step: finding.step };
  }
  const entry = evaluatorForRun(caseRecord, run);
  const findings = entry && Array.isArray(entry.findings) ? entry.findings : [];
  const reason = findings.find((f) => isRecord(f) && f.code === "progress_lost");
  if (isRecord(reason)) return { headline: "The correction loses required progress.", detail: String(reason.detail), row: null, step: null };
  const trialStatus = caseRecord.trial?.status;
  if (trialStatus === "unsupported" || trialStatus === "invalid") return { headline: `Trial ${trialStatus}.`, detail: `Diagnostic evaluator ${String((caseRecord.decisions.diagnostic_decision?.content as Record<string, unknown> | undefined)?.decision ?? "unavailable")}. These are distinct retained conclusions.`, row: null, step: null };
  if (caseRecord.label?.includes("development fixture")) {
    const mismatch = firstActionMismatch(rows);
    return { ...describeMismatch(mismatch, rows.length), row: mismatch?.row_index ?? null, step: mismatch?.step ?? null };
  }
  return { headline: `Recorded task ${run.task_outcome}.`, detail: `Measurement ${run.measurement_status}. Inspect original actions, observations and the scoped evaluator decision.`, row: null, step: null };
}

export function alignedRow(primary: SampleRow | null, other: readonly SampleRow[], phase: "before" | "after"): SampleRow | null {
  if (!primary) return null;
  const time = timeForPhase(primary, phase);
  return other.find((r) => timeForPhase(r, phase) === time) ?? null;
}

export function timeForPhase(row: SampleRow, phase: "before" | "after"): number {
  return phase === "before" ? row.action_sim_time_s : row.next_sim_time_s;
}

export function formatSeconds(t: number): string {
  return `${t.toFixed(2)} s`;
}

export function formatMetres(m: number, digits = 6): string {
  return `${m.toFixed(digits)} m`;
}
