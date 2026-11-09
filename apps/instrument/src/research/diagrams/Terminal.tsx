import type { DataMap } from "../catalog";
import {
  variantLabel,
  Variant,
  ControlField,
  DiagramHeader,
  type DiagramProps,
} from "./shared";

export function Terminal({
  data,
  route,
  select,
}: { data: DataMap["terminal"] } & Pick<DiagramProps, "route" | "select">) {
  const corrected = route.variant === "corrected",
    w = data.witness;
  const control = data.controls[route.sample];
  return (
    <div>
      <DiagramHeader label="Episode boundary · native witness">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <svg
        className="mechanism-drawing episode-drawing"
        viewBox="0 0 720 350"
        role="img"
        aria-label={`Episode starts at ${w.start}, reaches ${w.terminal}, then resets to ${w.reset}. ${variantLabel(route)} recorder retains ${corrected ? w.terminal : w.reset}; the live policy receives ${w.reset}.`}
      >
        <path d="M86 109H638M430 35V310" className="diagram-guide" />
        <text x="87" y="37" className="diagram-micro">
          EPISODE n
        </text>
        <text x="480" y="37" className="diagram-micro">
          EPISODE n + 1
        </text>
        <g className="episode-node">
          <circle cx="110" cy="110" r="32" />
          <text x="110" y="118" textAnchor="middle">
            {w.start}
          </text>
          <text x="110" y="171" textAnchor="middle" className="small">
            <tspan x="110">initial</tspan>
            <tspan x="110" dy="18">
              observation
            </tspan>
          </text>
        </g>
        <path d="M150 110H295l-8-6m8 6-8 6" className="diagram-link" />
        <text x="224" y="94" textAnchor="middle" className="diagram-micro">
          ACTION
        </text>
        <g className="episode-node">
          <circle cx="335" cy="110" r="32" />
          <text x="335" y="118" textAnchor="middle">
            {w.terminal}
          </text>
          <text x="335" y="171" textAnchor="middle" className="small">
            <tspan x="335">terminal</tspan>
            <tspan x="335" dy="18">
              observation
            </tspan>
          </text>
        </g>
        <path d="M375 110H525l-8-6m8 6-8 6" className="diagram-link" />
        <text x="455" y="94" textAnchor="middle" className="diagram-micro">
          AUTORESET
        </text>
        <g className="episode-node">
          <circle cx="566" cy="110" r="32" />
          <text x="566" y="118" textAnchor="middle">
            {w.reset}
          </text>
          <text x="566" y="171" textAnchor="middle" className="small">
            <tspan x="566">live policy</tspan>
            <tspan x="566" dy="18">
              input
            </tspan>
          </text>
        </g>
        <path
          d={corrected ? "M335 143H440V258H305" : "M566 143H650V258H305"}
          className={`episode-record ${corrected ? "is-corrected" : "is-original"}`}
        />
        <rect
          x="86"
          y="228"
          width="219"
          height="65"
          rx="3"
          className="episode-record-box"
        />
        <text x="105" y="248" className="diagram-micro">
          RETAINED EPISODE
        </text>
        <text
          x="105"
          y="278"
          className={corrected ? "text-correction" : "text-rejected"}
        >
          [{w.start}, {corrected ? w.terminal : w.reset}]
        </text>
        <text x="86" y="324" className="small">
          {corrected
            ? "final_obs preserves the ending"
            : "reset leaks across the episode boundary"}
        </text>
      </svg>
      <div className="control-summary">
        <strong>
          {corrected ? data.corrected.passed : data.baseline.passed}
          <i>/{data.controls.length}</i>
        </strong>
        <p>
          native controls pass
          <br />
          <span>
            {corrected
              ? "The eight recording regressions are repaired."
              : "Eight SAME_STEP controls fail."}
          </span>
        </p>
      </div>
      <ControlField
        controls={data.controls}
        route={route}
        select={select}
        label="Native regression controls"
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
          <p role="alert">
            This control is unavailable.{" "}
            <button onClick={() => select({ sample: 0 })}>
              Open first control
            </button>
          </p>
        )}
      </div>
      <p className="diagram-note">
        The initial fixture attempt had {data.invalid.failed} pre-assertion
        failures. Its {data.invalid.passed} passes are not added to this result.
        The separate upstream #4485 scoring correction is not part of this
        patch.
      </p>
    </div>
  );
}
