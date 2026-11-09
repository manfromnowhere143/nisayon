import type { DataMap } from "../catalog";
import { DiagramHeader, type DiagramProps } from "./shared";

export function Competence({
  data,
  route,
  select,
}: { data: DataMap["competence"] } & Pick<DiagramProps, "route" | "select">) {
  const episode = data.episodes[route.sample];
  return (
    <div>
      <DiagramHeader label="Runtime validity ≠ checkpoint competence" />
      <div className="qualification-line">
        <span>Runtime checks</span>
        <div>
          {Object.entries(data.criteria).map(([k, v]) => (
            <span key={k} title={`${k}: ${v}`}>
              {k} ✓
            </span>
          ))}
        </div>
      </div>
      <svg
        viewBox="0 0 720 215"
        className="mechanism-drawing"
        role="img"
        aria-label={`${data.successes} of 10 tasks completed; ${data.required} required. Reference rejected.`}
      >
        <path d="M50 153H670" className="diagram-guide" />
        {data.episodes.map((e, i) => (
          <g key={e.seed}>
            <rect
              x={55 + i * 61}
              y={e.outcome === "success" ? 55 : 133}
              width="39"
              height={e.outcome === "success" ? 98 : 20}
              className={
                e.outcome === "success" ? "episode-pass" : "episode-fail"
              }
            />
            <text x={74 + i * 61} y="180" textAnchor="middle" className="small">
              {e.seed}
            </text>
          </g>
        ))}
      </svg>
      <div className="outcome-summary">
        <span>
          <strong>
            {data.successes}
            <i>/10</i>
          </strong>{" "}
          tasks completed
        </span>
        <span>
          <strong>
            {data.required}
            <i>/10</i>
          </strong>{" "}
          required
        </span>
        <p className="text-rejected">Reference rejected</p>
      </div>
      <div
        className="hypothesis-selector"
        role="group"
        aria-label="Inspect a development episode"
      >
        {data.episodes.map((e, i) => (
          <button
            key={e.seed}
            aria-pressed={route.sample === i}
            onClick={() => select({ sample: i })}
          >
            {e.seed}
          </button>
        ))}
      </div>
      <p className="selected-witness" aria-live="polite">
        {episode
          ? `Seed ${episode.seed} · ${episode.steps} controls · ${episode.outcome.replaceAll("_", " ")}`
          : "This episode is unavailable."}
      </p>
    </div>
  );
}
