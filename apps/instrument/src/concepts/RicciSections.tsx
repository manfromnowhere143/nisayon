import { useRef } from "react";
import { RICCI_CATALOG, type RicciPartId } from "./ricciCatalog";

/** A section index, deliberately not a silhouette. Visible vector targets;
 * no image hit regions, anatomical coordinates or hidden-geometry claims. */
export function RicciSections({ selected, onSelect }: {
  selected: RicciPartId | null;
  onSelect: (id: RicciPartId, origin: SVGElement) => void;
}) {
  const pointer = useRef<{ id: number; x: number; y: number; dragged: boolean } | null>(null);
  return <svg className="ricci-sections" viewBox="0 0 320 516" role="group" aria-label="Ricci section diagram" aria-describedby="ricci-diagram-note">
    <g aria-hidden="true" className="ricci-index-rule">
      <path d="M8 16h304M8 500h304" />
      <text x="8" y="39">SECTION INDEX</text><text x="312" y="39" textAnchor="end">01—12</text>
    </g>
    {RICCI_CATALOG.map((part, index) => {
      const x = 8 + (index % 2) * 156, y = 58 + Math.floor(index / 2) * 73;
      const active = selected === part.id;
      return <g key={part.id} transform={`translate(${x} ${y})`} role="button" tabIndex={0}
        className="ricci-section" data-part={part.id} aria-label={`Inspect ${part.label.toLowerCase()}`}
        aria-pressed={active} aria-controls="ricci-inspector"
        onKeyDown={event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(part.id, event.currentTarget); }
        }}
        onPointerDown={event => { pointer.current = { id: event.pointerId, x: event.clientX, y: event.clientY, dragged: false }; }}
        onPointerMove={event => {
          const start = pointer.current;
          if (start?.id === event.pointerId && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) start.dragged = true;
        }}
        onPointerCancel={() => { if (pointer.current) pointer.current.dragged = true; }}
        onClick={event => {
          const dragged = pointer.current?.dragged; pointer.current = null;
          if (event.detail !== 0 && dragged) return;
          onSelect(part.id, event.currentTarget);
        }}>
        <rect width="148" height="65" rx="2" />
        <text className="ricci-index-number" x="12" y="23">{String(index + 1).padStart(2, "0")}</text>
        <text className="ricci-index-label" x="12" y="49">{part.shortLabel}</text>
        {active ? <path className="ricci-index-check" d="m120 18 4 4 9-9" aria-hidden="true" /> : null}
      </g>;
    })}
  </svg>;
}
