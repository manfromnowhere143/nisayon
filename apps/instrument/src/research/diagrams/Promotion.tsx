import type { DataMap } from "../catalog";
import {
  ControlField,
  DiagramHeader,
  Variant,
  type DiagramProps,
} from "./shared";

export function Promotion({
  data,
  route,
  select,
}: { data: DataMap["promotion"] } & Pick<DiagramProps, "route" | "select">) {
  const corrected = route.variant === "corrected";
  const control = data.controls[route.sample];
  return (
    <div>
      <DiagramHeader label="Promotion evidence · constructed native witness">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <svg
        className="mechanism-drawing promotion-drawing"
        viewBox="0 0 720 340"
        role="img"
        aria-label={`An unlisted passing sidecar overrides an embedded failure. ${corrected ? "Corrected gate blocks the packet because a consumed file is unbound." : "Original gate promotes despite the missing binding."}`}
      >
        <path className="diagram-guide" d="M30 174H690" />
        <g className="graph-box">
          <rect x="32" y="53" width="190" height="83" rx="5" />
          <text x="48" y="79" className="diagram-micro">
            DEPLOYMENT RECEIPT
          </text>
          <text x="48" y="108">
            Embedded policy: fail
          </text>
          <rect x="32" y="218" width="190" height="83" rx="5" />
          <text x="48" y="244" className="diagram-micro">
            UNLISTED SIDECAR
          </text>
          <text x="48" y="273">
            Policy override: pass
          </text>
        </g>
        <g className={corrected ? "is-corrected" : "is-original"}>
          <path className="promotion-connection" d="M222 95H278V151H319" />
          <path className="promotion-connection" d="M222 260H278V198H319" />
          <rect
            className="promotion-gate"
            x="319"
            y="127"
            width="168"
            height="94"
            rx="6"
          />
          <text x="403" y="159" textAnchor="middle" className="diagram-micro">
            MANIFEST CHECK
          </text>
          <text x="403" y="188" textAnchor="middle">
            {corrected ? "Unbound input" : "Coverage skipped"}
          </text>
          <path
            className="promotion-connection"
            d="M487 174H536l-7-5m7 5-7 5"
          />
          <circle className="promotion-gate" cx="604" cy="174" r="54" />
          <text
            x="604"
            y="180"
            textAnchor="middle"
            className="promotion-decision"
          >
            {corrected ? "BLOCK" : "PROMOTE"}
          </text>
        </g>
        <text x="403" y="262" textAnchor="middle" className="small">
          {corrected
            ? "Every consumed file must be bound"
            : "The decision reads more than it verifies"}
        </text>
        <text x="403" y="284" textAnchor="middle" className="small">
          under the required-hash profile
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
            {data.nativeControls} unchanged upstream tests · counted once
          </span>
        </p>
      </div>
      <ControlField
        controls={data.controls}
        route={route}
        select={select}
        label="Promotion integrity controls"
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
        A manifest can bind bytes without proving their truth. This correction
        assumes stable local files; it is not a physical-safety guarantee.
      </p>
    </div>
  );
}
