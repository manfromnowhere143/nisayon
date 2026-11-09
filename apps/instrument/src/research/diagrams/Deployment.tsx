import type { DataMap } from "../catalog";
import { DiagramHeader } from "./shared";

export function Deployment({ data }: { data: DataMap["deployment"] }) {
  return (
    <div>
      <DiagramHeader label="Declared deployment · dependency intersection" />
      <div className="dependency-chain">
        <div>
          <span>Long-WAM</span>
          <code>numpy {data.numpy}</code>
        </div>
        <b aria-hidden="true">↓ infra</b>
        <div>
          <span>LeRobot {data.lerobot}</span>
          <code>rerun-sdk {data.rerun}</code>
        </div>
        <b aria-hidden="true">↓ requires</b>
        <div>
          <span>Rerun</span>
          <code>numpy {data.rerunNumpy}</code>
        </div>
      </div>
      <svg
        viewBox="0 0 720 165"
        className="mechanism-drawing"
        role="img"
        aria-label="NumPy below 2 and NumPy 2 or newer have no common version."
      >
        <path d="M60 100H660" className="diagram-guide" />
        <path d="M105 67H360M360 132H650" className="dependency-range" />
        <circle cx="360" cy="67" r="6" className="open-point" />
        <circle cx="360" cy="132" r="6" className="closed-point" />
        <path d="M360 40v112" className="diagram-threshold" />
        <text x="105" y="48" className="small">
          1.26
        </text>
        <text x="360" y="27" textAnchor="middle" className="small">
          2.0
        </text>
        <text x="650" y="113" textAnchor="end" className="small">
          NumPy ≥ 2
        </text>
      </svg>
      <div className="outcome-summary">
        <span>
          <strong>
            {data.executed}
            <i>/{data.planned}</i>
          </strong>{" "}
          native tests executed
        </span>
        <p className="text-unresolved">
          Empty intersection
          <br />
          <span>Consistent deployment pins needed</span>
        </p>
      </div>
      <div className="resolver-controls">
        {Object.entries(data.controls).map(([k, v]) => (
          <div key={k}>
            <span>{k.replaceAll("-", " ")}</span>
            <span>{v === 0 ? "resolves" : "conflict reproduced"}</span>
          </div>
        ))}
      </div>
      <p className="diagram-note">
        These four checks resolve dependencies. They are separate from the{" "}
        {data.planned} native tests, which remain unrun.
      </p>
    </div>
  );
}
