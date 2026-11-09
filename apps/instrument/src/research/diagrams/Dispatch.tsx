import type { DataMap } from "../catalog";
import {
  ControlField,
  DiagramHeader,
  Variant,
  type DiagramProps,
} from "./shared";

export function Dispatch({
  data,
  route,
  select,
}: { data: DataMap["dispatch"] } & Pick<DiagramProps, "route" | "select">) {
  const corrected = route.variant === "corrected";
  const control = data.controls[route.sample];
  const w = data.witness;
  return (
    <div>
      <DiagramHeader label="Dispatch timing · controlled native witness">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <svg
        className="mechanism-drawing dispatch-drawing"
        viewBox="0 0 720 340"
        role="img"
        aria-label={`A queued-control plan finishes at ${w.readyAt} seconds, before dispatch at ${w.dispatchAt} second. ${corrected ? "The corrected engine collects the ready plan and executes command 100." : "The original engine misses the ready plan and executes queued command 11."} These are synthetic fixture values.`}
      >
        <text x="32" y="50" className="diagram-micro">
          ONE CONTROL PERIOD
        </text>
        <path className="diagram-guide" d="M125 84H594M125 74v20M594 74v20" />
        <text x="125" y="112" className="small" textAnchor="middle">
          0 s
        </text>
        <text x="360" y="112" className="small" textAnchor="middle">
          {w.readyAt} s
        </text>
        <text x="594" y="112" className="small" textAnchor="middle">
          {w.dispatchAt} s
        </text>
        <path className="diagram-guide" d="M360 120V235M594 120V235" />
        <g className="graph-box">
          <rect x="36" y="140" width="178" height="76" rx="6" />
          <text x="125" y="168" textAnchor="middle" className="diagram-micro">
            READINESS CHECK
          </text>
          <text x="125" y="195" textAnchor="middle">
            Plan not ready
          </text>
          <rect x="282" y="140" width="156" height="76" rx="6" />
          <text x="360" y="168" textAnchor="middle" className="diagram-micro">
            DURING PACING
          </text>
          <text x="360" y="195" textAnchor="middle">
            Plan completes
          </text>
        </g>
        <g className={corrected ? "is-corrected" : "is-original"}>
          <path
            className="dispatch-connection"
            d="M214 178H282M438 178H492l-7-5m7 5-7 5"
          />
          <rect
            className="dispatch-gate"
            x="504"
            y="140"
            width="180"
            height="76"
            rx="6"
          />
          <text x="594" y="168" textAnchor="middle" className="diagram-micro">
            {corrected ? "COLLECT, THEN DISPATCH" : "DISPATCH OLD CONTROL"}
          </text>
          <text
            x="594"
            y="195"
            textAnchor="middle"
            className="dispatch-command"
          >
            Command {corrected ? w.newCommand : w.oldCommand}
          </text>
        </g>
        <text x="360" y="270" textAnchor="middle">
          {corrected
            ? "The completed plan supplies the still-unexecuted control."
            : "The next check can reject the missed plan as stale."}
        </text>
        <text x="360" y="302" textAnchor="middle" className="small">
          Genuinely late plans remain rejected as a whole.
        </text>
      </svg>
      <div className="control-summary">
        <strong>
          {corrected ? data.corrected.passed : data.baseline.passed}
          <i>/{data.controls.length}</i>
        </strong>
        <p>
          native CPU controls pass
          <br />
          <span>
            {data.newControls} timing controls · {data.nativeControls} unchanged
            upstream
          </span>
        </p>
      </div>
      <ControlField
        controls={data.controls}
        route={route}
        select={select}
        label="Dispatch timing controls"
      />
      <div className="control-reading" aria-live="polite">
        {control ? (
          <>
            <span className="research-micro">
              Control {route.sample + 1} / {data.controls.length}
            </span>
            <p>{control.name.replaceAll("_", " ")}</p>
            <span>{corrected ? control.after : control.before}</span>
          </>
        ) : (
          <p>This control is absent from the pinned evidence.</p>
        )}
      </div>
      <p className="diagram-note">
        The initial attempt also had two import setup failures; its 67 passes
        remain separate. A controlled clock does not establish a hardware
        deadline.
      </p>
    </div>
  );
}
