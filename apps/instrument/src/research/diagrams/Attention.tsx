import type { DataMap } from "../catalog";
import {
  DiagramHeader,
  Variant,
  ControlField,
  type DiagramProps,
} from "./shared";

export function Attention({
  data,
  route,
  select,
}: { data: DataMap["attention"] } & Pick<DiagramProps, "route" | "select">) {
  const corrected = route.variant === "corrected";
  const weights = corrected ? [0, 0, 0, 1] : [0.25, 0.25, 0.25, 0.25];
  const control = data.controls[route.sample];
  return (
    <div className="attention-instrument">
      <DiagramHeader label="State-query visibility · exact CPU fixture">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <svg
        className="mechanism-drawing attention-drawing"
        viewBox="0 0 720 330"
        role="img"
        aria-label={`Training lets the state query see only its state. ${corrected ? "Corrected cached attention preserves this visibility." : "Original cached attention averages cached video, current video, action and state."} State output ${corrected ? data.correctedState : data.originalState}; required ${data.trainingState}.`}
      >
        {["Cache", "Video", "Action", "State"].map((label, i) => (
          <text
            key={label}
            x={271 + i * 90}
            y="45"
            textAnchor="middle"
            className="small"
          >
            {label}
          </text>
        ))}
        <text x="654" y="45" textAnchor="middle" className="small">
          Output
        </text>
        {[[0, 0, 0, 1], weights].map((row, r) => (
          <g
            key={r}
            className={
              r === 1 ? (corrected ? "is-corrected" : "is-original") : ""
            }
          >
            <text x="24" y={106 + r * 100}>
              {r === 0 ? "Training" : "Cached"}
            </text>
            <text x="24" y={132 + r * 100} className="small">
              state query
            </text>
            {row.map((weight, c) => (
              <g
                key={c}
                className={`attention-cell ${weight ? "is-visible" : ""}`}
              >
                <rect
                  x={236 + c * 90}
                  y={78 + r * 100}
                  width="70"
                  height="62"
                  rx="3"
                />
                <text x={271 + c * 90} y={116 + r * 100} textAnchor="middle">
                  {weight === 0.25 ? "¼" : weight}
                </text>
              </g>
            ))}
            <path
              d={`M588 ${109 + r * 100}h29l-7-5m7 5-7 5`}
              className="diagram-link"
            />
            <text
              x="654"
              y={117 + r * 100}
              textAnchor="middle"
              className="attention-output"
            >
              {r === 0
                ? data.trainingState
                : corrected
                  ? data.correctedState
                  : data.originalState}
            </text>
          </g>
        ))}
        <path d="M24 269H690" className="diagram-guide" />
        <text x="24" y="305" className="small">
          Key values
        </text>
        {data.values.map((value, i) => (
          <text
            key={i}
            x={271 + i * 90}
            y="305"
            textAnchor="middle"
            className="small"
          >
            {value}
          </text>
        ))}
      </svg>
      <p className="diagram-note">
        Uniform attention in the constructed witness. These are exact fixture
        weights, not a learned model’s attention map. State keys and values
        remain available to the video and action queries.
      </p>
      <div className="outcome-summary">
        <span>
          <strong>
            {corrected ? data.correctedAction : data.originalAction}
          </strong>{" "}
          later action value
        </span>
        <span>
          <strong>{data.trainingAction}</strong> training-path reference
        </span>
      </div>
      <p className="diagram-note">
        The difference reaches a later action in two constructed attention
        layers. This is not a checkpoint rollout or a robot outcome.
      </p>
      <div className="control-summary">
        <strong>
          {corrected ? data.corrected.passed : data.baseline.passed}
          <i>/{data.controls.length}</i>
        </strong>
        <p>
          frozen CPU controls pass
          <br />
          <span>Portable tests reuse these same fixtures.</span>
        </p>
      </div>
      <ControlField
        controls={data.controls}
        route={route}
        select={select}
        label="Attention contract controls"
      />
      <div className="control-reading" aria-live="polite">
        {control ? (
          <>
            <span className="research-micro">
              Control {route.sample + 1} / {data.controls.length}
            </span>
            <p>{control.name.replaceAll("_", " ")}</p>
            <span>
              {control.before} → {control.after}
            </span>
          </>
        ) : (
          <p>The selected control is unavailable.</p>
        )}
      </div>
    </div>
  );
}
