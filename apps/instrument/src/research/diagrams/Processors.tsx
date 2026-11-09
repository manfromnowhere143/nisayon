import type { DataMap } from "../catalog";
import {
  variantLabel,
  Variant,
  DiagramHeader,
  type DiagramProps,
} from "./shared";

export function Processors({
  data,
  route,
  select,
}: { data: DataMap["processors"] } & Pick<DiagramProps, "route" | "select">) {
  const fixed = route.variant === "corrected";
  return (
    <div>
      <DiagramHeader label="Processor relationship · native witness">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <svg
        className="mechanism-drawing processor-drawing"
        viewBox="0 0 720 390"
        role="img"
        aria-label={`${variantLabel(route)} copies use ${fixed ? "shared current state 10 and produce 11" : "stale state 100 and produce 101"}. Required target 11.`}
      >
        <path d="M80 75h560M80 310h560" className="diagram-guide" />
        <text x="80" y="53" className="diagram-micro">
          WORKER-LOCAL PROCESSOR GRAPH
        </text>
        <g className="graph-box">
          <rect x="80" y="104" width="180" height="66" rx="4" />
          <text x="170" y="131" textAnchor="middle">
            Preprocessor
          </text>
          <text x="170" y="151" textAnchor="middle" className="small">
            relative actions
          </text>
          <rect x="460" y="104" width="180" height="66" rx="4" />
          <text x="550" y="131" textAnchor="middle">
            Postprocessor
          </text>
          <text x="550" y="151" textAnchor="middle" className="small">
            absolute actions
          </text>
        </g>
        <path d="M260 137H460" className="diagram-link" />
        <text x="360" y="117" textAnchor="middle" className="diagram-micro">
          ACTION +{data.relativeAction}
        </text>
        <g
          className={
            fixed ? "copy-links is-corrected" : "copy-links is-original"
          }
        >
          <path d="M170 170V229H307" />
          <path d={fixed ? "M550 170V229H413" : "M550 170V255"} />
          <circle cx="360" cy="229" r="53" />
          <text x="360" y="231" textAnchor="middle" className="graph-value">
            {data.currentState}
          </text>
          <text x="360" y="251" textAnchor="middle" className="small">
            current state
          </text>
          {!fixed ? (
            <>
              <circle cx="550" cy="272" r="30" />
              <text x="550" y="280" textAnchor="middle">
                {data.staleState}
              </text>
              <text x="550" y="328" textAnchor="middle" className="small">
                detached stale copy
              </text>
            </>
          ) : null}
        </g>
        <text x="80" y="373" className="diagram-micro">
          {fixed
            ? "deepcopy((preprocessor, postprocessor))"
            : "deepcopy(preprocessor)   ·   deepcopy(postprocessor)"}
        </text>
      </svg>
      <div className="outcome-summary">
        <span>
          <strong>{fixed ? data.required : data.actual}</strong> resulting
          target
        </span>
        <span className="outcome-arrow">/</span>
        <span>
          <strong>{data.required}</strong> required target
        </span>
      </div>
      <p className="diagram-note">
        {fixed ? data.corrected : data.baseline} of {data.total} native controls
        pass. This diagram illustrates object references, not robot coordinates.
      </p>
    </div>
  );
}
