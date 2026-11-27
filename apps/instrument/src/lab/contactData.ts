import { transferBytes } from "../data/transfer";
import { strictParseJson } from "../data/strictJson";

export interface ContactRow {
  t_s: number; x_m: number; z_m: number; v_m_s: number; a_m_s2: number;
  command_n: number; applied_n: number; contact_x_n: number; normal_n: number;
  contacts: { position_m: [number, number, number]; force_on_slider_world_n: [number, number, number] }[];
}
export interface ContactTrace {
  role: "reference" | "candidate"; condition: "low" | "high";
  complete: boolean; initial_state_sha256: string; model_sha256: string; rows: ContactRow[];
}
export interface ContactExperiment {
  experiment_id: string;
  spec: { schema: "nisayon.lab.experiment.v1"; protocol_sha256: string;
    parameters: Record<string, number>;
    protocol: { schema: "nisayon.lab.contact.v1"; measurement_period_s: number; limits: string[];
      visualization: { slider_half_size_m: [number, number, number]; force_arrow_scale_m_per_n: number } };
    producer: Record<string, string>; runtime: Record<string, unknown> };
}
export interface ContactPacket {
  schema: "nisayon.lab.inspection.v1"; integrity: "verified"; packet_sha256: string;
  experiment: ContactExperiment; traces: ContactTrace[];
  result: { status: "complete" | "cancelled" | "failed"; complete: boolean; error: string | null; wall_s: number;
    qualification: { verdict: "supported" | "rejected" | "unresolved"; deployment_decision: "unresolved"; scope: string; failures: string[] } };
  analysis: { estimates: Record<"reference" | "candidate", { status: "model_fit" | "unresolved";
    gain: number | null; effective_friction: number | null; reason: string }> };
}
export interface ContactView {
  packet: ContactPacket; condition: "low" | "high"; index: number; forces: boolean;
}
export interface ContactCapabilities {
  schema: "nisayon.lab.capabilities.v1"; session: string;
  instruments: { id: string; executable: boolean; default: ContactExperiment;
    parameters_schema: { required: string[]; properties: Record<string, { title: string; minimum: number; maximum: number; unit: string; default: number; multipleOf?: number }> } }[];
}

const object = (x: unknown): Record<string, any> => {
  if (!x || typeof x !== "object" || Array.isArray(x)) throw new Error("Expected an evidence object");
  return x as Record<string, any>;
};
const sha = (x: unknown) => typeof x === "string" && /^[a-f0-9]{64}$/.test(x);
const number = (x: unknown) => typeof x === "number" && Number.isFinite(x);

/** Verify display obligations; the server's existing kernel owns the decision. */
export function decodeContactPacket(value: unknown): ContactPacket {
  const p = object(value), experiment = object(p.experiment), spec = object(experiment.spec), protocol = object(spec.protocol);
  const result = object(p.result), verdict = object(result.qualification);
  if (p.schema !== "nisayon.lab.inspection.v1" || p.integrity !== "verified" || !sha(p.packet_sha256)
      || !sha(experiment.experiment_id) || spec.schema !== "nisayon.lab.experiment.v1"
      || protocol.schema !== "nisayon.lab.contact.v1" || !sha(spec.protocol_sha256)) throw new Error("Unsupported contact evidence identity");
  if (!["complete", "cancelled", "failed"].includes(result.status) || result.complete !== (result.status === "complete")
      || !["supported", "rejected", "unresolved"].includes(verdict.verdict) || verdict.deployment_decision !== "unresolved"
      || (!result.complete && verdict.verdict !== "unresolved")) throw new Error("Incompatible execution or qualification status");
  if (protocol.measurement_period_s !== .005 || !Array.isArray(protocol.limits) || !protocol.limits.every((x: unknown) => typeof x === "string")) throw new Error("Unsupported measurement clock");
  const parameters = object(spec.parameters);
  for (const key of ["mass_kg", "reference_friction", "candidate_friction", "reference_gain", "candidate_gain", "low_force_n", "high_force_n", "duration_s", "displacement_tolerance_m"])
    if (!number(parameters[key])) throw new Error(`Unavailable protocol parameter: ${key}`);
  if (parameters.duration_s < .1 || parameters.duration_s > .5 || Math.abs(parameters.duration_s / .005 - Math.round(parameters.duration_s / .005)) > 1e-10
      || typeof verdict.scope !== "string" || !number(result.wall_s) || result.wall_s < 0) throw new Error("Unsupported protocol horizon or qualification scope");
  const visual = object(protocol.visualization);
  if (JSON.stringify(visual.slider_half_size_m) !== JSON.stringify([.04,.03,.02]) || visual.force_arrow_scale_m_per_n !== .02) throw new Error("Unsupported physical visualization binding");
  if (!Array.isArray(p.traces) || p.traces.length > 4 || (result.complete && p.traces.length !== 4)) throw new Error("Incomplete paired coverage");
  const pairs = new Set(), starts = new Set();
  for (const raw of p.traces) {
    const trace = object(raw), key = `${trace.role}:${trace.condition}`;
    if (!["reference", "candidate"].includes(trace.role) || !["low", "high"].includes(trace.condition)
        || pairs.has(key) || !sha(trace.initial_state_sha256) || !sha(trace.model_sha256) || typeof trace.complete !== "boolean") throw new Error("Incompatible paired trace");
    pairs.add(key); starts.add(trace.initial_state_sha256);
    if (!Array.isArray(trace.rows) || !trace.rows.length || trace.rows.length > 101) throw new Error("Contact row budget exceeded");
    trace.rows.forEach((rawRow: unknown, index: number) => {
      const row = object(rawRow);
      for (const key of ["t_s", "x_m", "z_m", "v_m_s", "a_m_s2", "command_n", "applied_n", "contact_x_n", "normal_n"])
        if (!number(row[key])) throw new Error(`Unavailable ${key} in contact row`);
      if (Math.abs(row.t_s - index * .005) > 1e-10 || row.x_m < -.01 || row.x_m > 1.51 || row.z_m < 0 || row.z_m > .2) throw new Error("Contact row outside the supported clock or spatial bound");
      if (!Array.isArray(row.contacts) || row.contacts.length > 8) throw new Error("Contact vector budget exceeded");
      for (const contact of row.contacts) for (const key of ["position_m", "force_on_slider_world_n"]) {
        const v = object(contact)[key];
        if (!Array.isArray(v) || v.length !== 3 || !v.every(number)) throw new Error("Unavailable contact vector");
      }
    });
    if (result.complete && !trace.complete) throw new Error("Incomplete trace marked complete");
    if (trace.complete && trace.rows.length !== Math.round(parameters.duration_s / .005) + 1) throw new Error("Truncated measurement horizon");
  }
  if (starts.size > 1) throw new Error("Initial states are not matched");
  const estimates = object(object(p.analysis).estimates);
  for (const role of ["reference", "candidate"]) {
    const estimate = object(estimates[role]);
    if (!["model_fit", "unresolved"].includes(estimate.status) || typeof estimate.reason !== "string"
        || (estimate.status === "model_fit" && (!number(estimate.gain) || !number(estimate.effective_friction)))
        || (estimate.status === "unresolved" && (estimate.gain !== null || estimate.effective_friction !== null))) throw new Error("Unsupported model fit");
  }
  return value as ContactPacket;
}

export async function labRequest(path: string, options: { signal?: AbortSignal; session?: string; body?: unknown } = {}): Promise<unknown> {
  let status = 200;
  const bytes = await transferBytes(path, async (url, { signal }) => {
    const response = await fetch(url, {
      signal, cache: "no-store", ...(options.body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json", "X-Nisayon-Session": options.session ?? "" }, body: JSON.stringify(options.body) } : {}),
    });
    status = response.status;
    // Read refused responses through the same byte/time bounds so the actual
    // validation reason reaches the operator, rather than an opaque HTTP code.
    return response.ok ? response : new Response(response.body,{ status: 200, headers: response.headers });
  }, { signal: options.signal, maxBytes: 2_000_000, timeoutMs: 12_000, stallTimeoutMs: 6_000 });
  let result: unknown;
  try { result = strictParseJson(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch (error) { if (status >= 400) throw Error(`Local laboratory returned HTTP ${status}`); throw error; }
  if (status >= 400) throw Error(result && typeof result === "object" && "error" in result && typeof result.error === "string" ? result.error.slice(0,500) : `Local laboratory returned HTTP ${status}`);
  return result;
}

export function contactPair(view: ContactView) {
  const find = (role: ContactTrace["role"]) => view.packet.traces.find(t => t.role === role && t.condition === view.condition);
  return { reference: find("reference"), candidate: find("candidate") };
}
