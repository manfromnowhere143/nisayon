import type { DataMap } from "../catalog";
import { fmt, Variant, DiagramHeader, type DiagramProps } from "./shared";

export function Routing({
  data,
  route,
  select,
}: { data: DataMap["routing"] } & Pick<DiagramProps, "route" | "select">) {
  const fixed = route.variant === "corrected",
    run = fixed ? data.after : data.before,
    counts = fixed ? data.corrected : data.original;
  return (
    <div>
      <DiagramHeader label="Binary client identity · retained queue witness">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <div className="routing-flow">
        {run.pushes.map((p, i) => (
          <div className="routing-client" key={p.rid}>
            <span className="research-micro">
              CLIENT {i + 1} / REQUEST {p.rid}
            </span>
            <div className="byte-frames">
              {p.envelope_hex.map((f, j) => (
                <code key={j}>{f || "empty frame"}</code>
              ))}
            </div>
            <span className="routing-arrow">↓</span>
            <span className="research-micro">ENCODED IDENTITY</span>
            <code className={fixed ? "text-correction" : "text-rejected"}>
              {p.key_hex}
            </code>
            <p>{p.result}</p>
          </div>
        ))}
      </div>
      <div className="queue-output">
        <span className="research-micro">RETAINED QUEUE ORDER</span>
        {run.pop_order.map((r) => (
          <span className="queue-request" key={r}>
            Request {r}
          </span>
        ))}
        <strong>{fixed ? "Separate identities" : "Request 1 displaced"}</strong>
      </div>
      <div className="outcome-summary">
        <span>
          <strong>{fmt(counts.unique_keys)}</strong> distinct keys
        </span>
        <span>
          <strong>{fmt(counts.additional_inputs_colliding)}</strong> colliding
          inputs
        </span>
      </div>
      <p className="diagram-note">
        Finite enumeration of {fmt(counts.inputs)} declared envelopes. It does
        not prove injectivity over all possible inputs.
      </p>
    </div>
  );
}
