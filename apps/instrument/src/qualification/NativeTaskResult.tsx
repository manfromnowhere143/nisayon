import { array, JsonNumber, object, string, type Json } from "./json";
import { RecordExplorer } from "./RecordExplorer";

export function isNativeTaskResult(value: Json | undefined): boolean {
  return !!value && typeof value === "object" && !Array.isArray(value) && !(value instanceof JsonNumber) && value.schema === "nisayon.qualification.native_task_assessment.v1";
}

const count = (value: Json | undefined) => {
  if (!(value instanceof JsonNumber) || !/^(0|[1-9][0-9]{0,5})$/.test(value.raw)) throw new Error("Unsupported episode count");
  return value.raw;
};

/** Present saved native results without promoting producer agreement to task truth. */
export function NativeTaskResult({ value }: { value: Json | undefined }) {
  try {
    const result = object(value);
    if (!isNativeTaskResult(value) || result.new_native_execution !== false || result.measurement_adequacy !== "unresolved" || result.deployment_decision !== "unresolved") throw new Error("Unsupported native task scope");
    const valid = result.status === "valid_retained_records";
    if (!valid && result.status !== "invalid") throw new Error("Unsupported record status");
    const pairs = array(result.pairs);
    if (pairs.length > 256 || (valid && !pairs.length)) throw new Error("Unsupported pair coverage");
    const seen = new Set<string>();
    const rows = pairs.map(value => {
      const row = object(value), initial = count(row.initial_state);
      if (seen.has(initial) || typeof row.reference_success !== "boolean" || typeof row.candidate_success !== "boolean") throw new Error("Invalid paired outcome");
      seen.add(initial);
      const transition = row.reference_success && !row.candidate_success ? "regression" : row.candidate_success && !row.reference_success ? "improvement" : "unchanged";
      if (row.transition !== transition) throw new Error("Inconsistent saved transition");
      return { initial, reference: row.reference_success, candidate: row.candidate_success, referenceSteps: count(row.reference_steps), candidateSteps: count(row.candidate_steps), transition };
    });
    const errors = array(result.errors).map(value => string(value));
    const missing = array(result.missing_evidence).map(value => string(value));
    if (errors.length > 64 || missing.length > 32 || (valid && errors.length)) throw new Error("Unsupported result details");
    const regressions = rows.filter(row => row.transition === "regression").length;
    if (valid && (result.recorded_outcome !== (regressions ? "observed_regression" : "no_regression_observed") || result.verdict !== (regressions ? "rejected" : "supported"))) throw new Error("Inconsistent saved outcome");
    return <section className="native-task-result" aria-label="Retained task outcomes">
      <p className="review-note">{string(result.scope)}</p>
      <p>{valid ? regressions ? `${regressions} recorded regression${regressions === 1 ? "" : "s"} in ${rows.length} pairs.` : `No regression observed in ${rows.length} recorded pairs.` : "The task records are invalid. They do not establish a task result."}</p>
      {valid ? <div className="native-task-table-wrap" role="region" aria-label="Paired native outcomes" tabIndex={0}><table className="native-task-table">
        <caption>Saved native success flags · initial-state pairs</caption>
        <thead><tr><th scope="col">Initial state</th><th scope="col">Reference</th><th scope="col">Candidate</th><th scope="col">Change</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.initial}><th scope="row">{row.initial}</th><td>{row.reference ? "Success" : "Failure"}<small>{row.referenceSteps} steps</small></td><td>{row.candidate ? "Success" : "Failure"}<small>{row.candidateSteps} steps</small></td><td>{row.transition}</td></tr>)}</tbody>
      </table></div> : <ul>{errors.map((error, i) => <li key={i}>{error}</li>)}</ul>}
      <p className="review-note"><strong>Measurement adequacy: unresolved.</strong> The summary and step flags share the native evaluator. This review contains no new robot execution.</p>
      <details><summary>Evidence still needed</summary><ul>{missing.map((item, i) => <li key={i}>{item}</li>)}</ul></details>
      <details><summary>Complete saved record</summary><RecordExplorer value={value} /></details>
    </section>;
  } catch {
    return <><p className="review-note" role="alert">This native task result has an unsupported or inconsistent structure. Inspect the original record; no task conclusion is shown.</p><RecordExplorer value={value ?? null} /></>;
  }
}
