import type { DataMap } from "../catalog";
import {
  variantLabel,
  Variant,
  DiagramHeader,
  type DiagramProps,
} from "./shared";

export function Transfer({
  data,
  route,
  select,
}: { data: DataMap["transfer"] } & Pick<DiagramProps, "route" | "select">) {
  const pair = data.pairs[route.sample];
  if (!pair)
    return (
      <p role="alert">
        This paired condition is absent from the pinned evidence.{" "}
        <button onClick={() => select({ sample: 0 })}>
          Open the first pair
        </button>
      </p>
    );
  const corrected = route.variant === "corrected";
  const success = corrected ? pair.corrected_success : pair.unchanged_success;
  const steps = corrected ? pair.corrected_steps : pair.unchanged_steps;
  return (
    <div className="transfer-instrument">
      <DiagramHeader label="Observation convention · schematic">
        <Variant route={route} select={select} />
      </DiagramHeader>
      <svg
        viewBox="0 0 720 280"
        className="mechanism-drawing"
        role="img"
        aria-label={`The last three observation values point ${corrected ? "from cube to gripper, restored for the legacy policy" : "from gripper to cube in the changed runtime"}. The observation remains ten dimensional.`}
      >
        <path d="M82 208H642M365 50V230" className="diagram-guide" />
        <g className="vector-object">
          <path d="m502 91 37-21 37 21v44l-37 21-37-21Z M502 91l37 22 37-22M539 113v43" />
          <text x="539" y="193" textAnchor="middle">
            cube
          </text>
        </g>
        <g className="vector-gripper">
          <path d="M151 68h56v38h-15v30h-12v-44h-2v44h-12v-30h-15Z" />
          <text x="179" y="193" textAnchor="middle">
            gripper
          </text>
        </g>
        <g
          className={
            corrected ? "vector-arrow is-corrected" : "vector-arrow is-original"
          }
        >
          <path d="M236 110H477" />
          <path d={corrected ? "m250 102-14 8 14 8" : "m463 102 14 8-14 8"} />
          <text x="355" y="88" textAnchor="middle">
            {corrected ? "gripper − cube" : "cube − gripper"}
          </text>
        </g>
        <g className="vector-cells">
          {Array.from({ length: 10 }, (_, i) => (
            <rect
              key={i}
              x={189 + i * 34}
              y="229"
              width="27"
              height="19"
              className={
                i >= 7 ? (corrected ? "is-corrected" : "is-original") : ""
              }
            />
          ))}
          <text x="355" y="275" textAnchor="middle">
            object[7:10] ·{" "}
            {corrected
              ? "sign restored at policy input"
              : "same shape, reversed convention"}
          </text>
        </g>
      </svg>
      <div className="outcome-summary">
        <span>
          <strong>
            {data.unchanged}
            <i>/10</i>
          </strong>{" "}
          unchanged
        </span>
        <span className="outcome-arrow" aria-hidden="true">
          →
        </span>
        <span>
          <strong>
            {data.corrected}
            <i>/10</i>
          </strong>{" "}
          corrected
        </span>
        <p>
          Fresh paired tasks
          <br />
          <span>8 repairs required · weights unchanged</span>
        </p>
      </div>
      <div
        className="pair-field"
        role="group"
        aria-label="Ten paired development conditions"
      >
        {data.pairs.map((p, i) => (
          <button
            key={p.seed}
            aria-pressed={route.sample === i}
            aria-label={`Seed ${p.seed}: unchanged failed; corrected ${p.corrected_success ? "succeeded" : "failed"}`}
            onClick={() => select({ sample: i })}
          >
            <span className="pair-dot is-failed">×</span>
            <span
              className={`pair-dot ${p.corrected_success ? "is-passed" : "is-failed"}`}
            >
              {p.corrected_success ? "✓" : "×"}
            </span>
            <span>{String(p.seed).slice(-2)}</span>
          </button>
        ))}
      </div>
      <div className="selected-witness" aria-live="polite">
        <span>
          Seed <b>{pair.seed}</b>
        </span>
        <span>
          {variantLabel(route)} · {steps} controls
        </span>
        <span className={success ? "text-correction" : "text-rejected"}>
          {success ? "Task completed" : "Task failed at horizon"}
        </span>
      </div>
      <div
        className="control-length"
        aria-label={`${steps} of 400 control steps`}
      >
        <span
          style={{ width: `${steps / 4}%` }}
          className={success ? "is-passed" : "is-failed"}
        />
        <i>0</i>
        <i>400 controls</i>
      </div>
      <p className="diagram-note">
        The two rows show unchanged and corrected outcomes. Seed 180104 remains
        a failure; it was not rerun or removed.
      </p>
    </div>
  );
}
