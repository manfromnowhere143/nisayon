import type { DataMap } from "../catalog";
import { DiagramHeader, type DiagramProps } from "./shared";

export function Decisions({
  data,
  route,
  select,
}: { data: DataMap["decisions"] } & Pick<DiagramProps, "route" | "select">) {
  const outcome = data.outcomes[route.sample];
  const survivors = outcome?.survivors ?? [];
  return (
    <div>
      <DiagramHeader label="Decision sufficiency · constructed model" />
      <div
        className="hypothesis-selector"
        role="group"
        aria-label="Inspect a constructed outcome"
      >
        {data.outcomes.map((o, i) => (
          <button
            key={o.hypothesis}
            aria-pressed={route.sample === i}
            onClick={() => select({ sample: i })}
          >
            {o.hypothesis}
          </button>
        ))}
      </div>
      <svg
        className="mechanism-drawing"
        viewBox="0 0 720 360"
        role="img"
        aria-label={
          outcome
            ? `Constructed outcome ${outcome.hypothesis} leaves ${survivors.join(" and ")} possible, with choice ${outcome.label}.`
            : "Unavailable constructed outcome"
        }
      >
        {["a1", "a2", "b1", "b2"].map((h, i) => (
          <g
            key={h}
            className={`hypothesis ${survivors.includes(h) ? "is-survivor" : ""}`}
          >
            <path d={`M${125 + i * 155} 117V170L${i < 2 ? 205 : 515} 233`} />
            <circle cx={125 + i * 155} cy="82" r="35" />
            <text x={125 + i * 155} y="89" textAnchor="middle">
              {h}
            </text>
          </g>
        ))}
        <path d="M65 178H655" className="diagram-guide" />
        <text x="360" y="165" textAnchor="middle" className="diagram-micro">
          ONE DECLARED DECISION PROBE
        </text>
        {["A", "B"].map((l, i) => (
          <g
            key={l}
            className={`decision-choice ${survivors[0]?.startsWith(l.toLowerCase()) ? "is-survivor" : ""}`}
          >
            <rect x={120 + i * 310} y="233" width="170" height="70" rx="3" />
            <text x={205 + i * 310} y="261" textAnchor="middle">
              Restore {l}
            </text>
            <text
              x={205 + i * 310}
              y="282"
              textAnchor="middle"
              className="small"
            >
              then confirm {l}
            </text>
          </g>
        ))}
      </svg>
      <div className="decision-costs">
        {[
          ["Identify every cause", data.fullCost],
          ["Choose a correction", data.decisionCost],
          ["Competent native choice", data.nativeCost],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <p className="selected-witness" aria-live="polite">
        {outcome
          ? `${survivors.join(" / ")} remain possible. The declared choice agrees; task confirmation is not assessed.`
          : "The selected outcome is unavailable."}
      </p>
      <p className="diagram-note">
        Costs are caller-declared observation units. The fair comparator ties.
        No probe or robot is executed by this view.
      </p>
    </div>
  );
}
