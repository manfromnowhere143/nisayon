import { useId, type CSSProperties } from "react";

export function SystemDiagram({ active }: { active: number }) {
  const id = useId().replaceAll(":", "");
  return (
    <svg
      className="system-diagram"
      viewBox="0 0 780 680"
      role="img"
      aria-labelledby={`${id}-title ${id}-desc`}
    >
      <title id={`${id}-title`}>
        The experiment, separated into five inspectable layers
      </title>
      <desc id={`${id}-desc`}>
        Bind deployment identities, execute in closed loop, confirm on fresh
        conditions, account for complete cost, and retain the regression. This
        is an architecture drawing, not measured geometry.
      </desc>
      <defs>
        <linearGradient id={`${id}-plate`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity=".09" />
          <stop offset="1" stopColor="currentColor" stopOpacity=".015" />
        </linearGradient>
      </defs>
      <g
        className="system-scaffold"
        fill="none"
        stroke="currentColor"
        strokeWidth=".7"
        opacity=".14"
      >
        <path
          d="M65 415 390 580 735 405M390 580V90M65 155 390 320 735 145M145 456V194M640 450V195"
          strokeDasharray="3 7"
        />
        {[0, 1, 2, 3, 4].map((i) => (
          <path key={i} d={`M${130 + i * 42} ${455 + i * 21} l344 -175`} />
        ))}
      </g>
      {[4, 3, 2, 1, 0].map((i) => {
        const y = 80 + i * 72;
        return (
          <g
            key={i}
            className="system-assembly"
            style={
              {
                "--assembly-delay": `${(4 - i) * 85}ms`,
                "--assembly-rise": `${20 + (4 - i) * 32}px`,
              } as CSSProperties
            }
          >
            <g className={`system-plate ${active === i ? "is-active" : ""}`}>
              <g className="system-plate-surface">
                <path
                  className="system-perimeter"
                  pathLength="1"
                  d={`M390 ${y} 654 ${y + 131} 390 ${y + 262} 126 ${y + 131}Z`}
                  fill={`url(#${id}-plate)`}
                  stroke="currentColor"
                  strokeWidth={active === i ? 1.25 : 0.7}
                />
                <path
                  d={`M126 ${y + 131}v9l264 131 264-131v-9M390 ${y + 262}v9`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth=".6"
                  opacity=".35"
                />
                <ellipse
                  cx="390"
                  cy={y + 131}
                  rx="108"
                  ry="53.5"
                  fill="none"
                  stroke="currentColor"
                  opacity=".3"
                />
                <ellipse
                  cx="390"
                  cy={y + 131}
                  rx="57"
                  ry="28"
                  fill="none"
                  stroke="currentColor"
                  opacity=".65"
                />
                <path
                  d={`M390 ${y + 103}v56M334 ${y + 131}h112`}
                  stroke="currentColor"
                  opacity=".3"
                />
                <path
                  d={`M126 ${y + 131}H75l-18 -18H20`}
                  fill="none"
                  stroke="currentColor"
                  opacity=".6"
                />

                <path
                  d={`M654 ${y + 131}h63l18 -18h30`}
                  fill="none"
                  stroke="currentColor"
                  opacity=".6"
                />
                <circle
                  cx="654"
                  cy={y + 131}
                  r="3"
                  fill={active === i ? "currentColor" : "var(--ground)"}
                  stroke="currentColor"
                />
              </g>
              <text x="20" y={y + 102} className="diagram-mono">
                0{i + 1}
              </text>
            </g>
          </g>
        );
      })}
      <g className="system-core" fill="none" stroke="currentColor">
        <path d="M390 184V516" strokeDasharray="2 6" opacity=".5" />
        <g
          className="system-core-position"
          style={{ transform: `translateY(${active * 72}px)` }}
        >
          <circle cx="390" cy="203" r="5" fill="currentColor" />
        </g>
      </g>
      <text x="20" y="30" className="diagram-micro">
        EXPERIMENT ANATOMY
      </text>
      <text x="765" y="30" textAnchor="end" className="diagram-micro">
        SCHEMATIC / 05 LAYERS
      </text>
    </svg>
  );
}
