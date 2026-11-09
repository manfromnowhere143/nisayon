import type { Fields, StudyPair, StudyTrial } from "../data/study";

const fields = (v: unknown): Fields => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Fields : {};
const finite = (v: unknown): number | null => typeof v === "number" && Number.isFinite(v) ? v : null;

export function decisivePair(trial: StudyTrial): StudyPair | null {
  const reasons = Array.isArray(trial.historical_decision?.reasons) ? trial.historical_decision.reasons : [];
  for (const value of reasons) {
    const reason = fields(value);
    if (!["rejected", "invalid", "unresolved"].includes(String(reason.severity))) continue;
    const pair = trial.confirmation?.pairs.find(p => p.reference.run_id === reason.run_id || p.candidate.run_id === reason.run_id);
    if (pair) return pair;
  }
  return null;
}

export function ProgressComparison({ trial, pair }: { trial: StudyTrial; pair: StudyPair }) {
  const predicates = fields(trial.confirmation?.protocol.predicates);
  const minimum = finite(predicates.progress_minimum_gain_m);
  const readings = (["reference", "candidate"] as const).map(side => {
    const indices = pair[side].record_indices;
    // Ambiguous/missing records remain unknown, never a silently chosen sample.
    const record = indices.length === 1 ? trial.confirmation?.observations[indices[0]!] : undefined;
    const progress = fields(record?.progress);
    return { side, value: progress.unit === "m" ? finite(progress.value) : null, status: String(progress.status ?? "not recorded"), outcome: String(record?.measured_task_outcome ?? "not recorded") };
  });
  const values = readings.flatMap(r => r.value === null ? [] : [r.value]);
  const lo = Math.min(0, minimum ?? 0, ...values), hi = Math.max(.001, minimum ?? 0, ...values);
  const span = hi - lo || .001;
  const x = (v: number) => 10 + (v - lo) / span * 280;
  return <section className="obligation-comparison" aria-label="Absolute progress obligation">
    <div className="obligation-heading"><h4>Absolute progress</h4><span className="num">{minimum === null ? "Minimum not recorded" : `Minimum ${minimum.toFixed(4)} m`}</span></div>
    <p className="fine">First to final recorded cube height. Task outcome and progress are separate obligations.</p>
    {readings.map(r => <div className="obligation-reading" key={r.side}>
      <div><span>{r.side}</span><strong className="num">{r.value === null ? "Not recorded" : `${r.value.toFixed(6)} m`}</strong><span>{r.outcome} · progress {r.status}</span></div>
      <svg viewBox="0 0 300 30" role="img" aria-label={`${r.side} gain ${r.value ?? "unknown"} m; minimum ${minimum ?? "unknown"} m`}>
        <line x1="10" x2="290" y1="15" y2="15" className="obligation-track" />
        {minimum !== null ? <line x1={x(minimum)} x2={x(minimum)} y1="4" y2="26" className="obligation-minimum" /> : null}
        {r.value !== null ? <><line x1={x(0)} x2={x(r.value)} y1="15" y2="15" className="obligation-value" /><circle cx={x(r.value)} cy="15" r="3" /></> : null}
      </svg>
      <span className="fine num">{r.value !== null && minimum !== null ? `${r.value - minimum < 0 ? "Below" : "Above or at"} minimum by ${Math.abs(r.value - minimum).toFixed(6)} m` : "Margin unavailable"}</span>
    </div>)}
    <p className="fine">Markers describe the retained values. The frozen evaluator decision remains authoritative.</p>
  </section>;
}
