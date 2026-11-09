import type { DataMap } from "../catalog";
import { fmt, DiagramHeader, type DiagramProps } from "./shared";

export function Cost({
  data,
  route,
  select,
}: { data: DataMap["cost"] } & Pick<DiagramProps, "route" | "select">) {
  const context = route.contextCost,
    setup = route.otherCost;
  const extra = context * data.extraContexts + setup,
    balance = data.saving - extra;
  return (
    <div>
      <DiagramHeader label="Cost sensitivity · hypothetical inputs" />
      <div className="cost-headroom">
        <span className="research-micro">AVAILABLE BEFORE EXTRA WORK</span>
        <strong>{fmt(data.saving)}</strong>
        <span>execution cost units</span>
      </div>
      <svg
        className="cost-drawing"
        viewBox="0 0 720 210"
        role="img"
        aria-label={`Illustrative extra cost ${fmt(extra)} against ${fmt(data.saving)} available. Balance ${fmt(balance)} execution cost units.`}
      >
        <path d="M45 155H675M45 35V155" className="diagram-guide" />
        <rect
          x="45"
          y="51"
          width={(data.saving / 16) * 630}
          height="26"
          className="cost-capacity"
        />
        <rect
          x="45"
          y="104"
          width={(extra / 16) * 630}
          height="26"
          className={balance >= 0 ? "cost-used" : "cost-over"}
        />
        <path
          d={`M${45 + (data.saving / 16) * 630} 35v130`}
          className="diagram-threshold"
        />
        <text x="45" y="195" className="small">
          0
        </text>
        <text x="675" y="195" textAnchor="end" className="small">
          16 cost units
        </text>
        <text x="45" y="41" className="small">
          Available saving
        </text>
        <text x="45" y="95" className="small">
          Illustrative extra cost
        </text>
      </svg>
      <label className="research-slider">
        <span>
          Cost per extra context <output>{context.toFixed(2)}</output>
        </span>
        <input
          type="range"
          min="0"
          max="0.5"
          step="0.01"
          value={context}
          onChange={(e) =>
            select({ contextCost: Number(e.target.value) }, true)
          }
        />
      </label>
      <label className="research-slider">
        <span>
          Other extra work <output>{setup.toFixed(2)}</output>
        </span>
        <input
          type="range"
          min="0"
          max="6"
          step="0.1"
          value={setup}
          onChange={(e) => select({ otherCost: Number(e.target.value) }, true)}
        />
      </label>
      <div className="selected-witness" aria-live="polite">
        <span>{fmt(data.extraContexts)} extra expected contexts</span>
        <strong className={balance < 0 ? "text-rejected" : "text-correction"}>
          {balance < 0 ? "Saving erased" : `${fmt(balance)} units remain`}
        </strong>
      </div>
      <p className="diagram-note">
        Sliders start at zero as an illustrative lower bound. Actual costs are
        unknown. With no other extra work, the context break-even is{" "}
        {fmt(data.breakEven)} per execution unit.
      </p>
    </div>
  );
}
