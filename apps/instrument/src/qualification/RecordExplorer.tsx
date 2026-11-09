import { useLayoutEffect, useRef, useState } from "react";
import { display, JsonNumber, type Json, type JsonObject } from "./json";

const shortText = (value: string, limit: number) => value.length > limit ? `${value.slice(0, limit)}…` : value;
export const preview = (value: Json) => Array.isArray(value) ? `${value.length} items` : value !== null && typeof value === "object" && !(value instanceof JsonNumber) ? `${Object.keys(value).length} fields` : shortText(display(value), 72);

/** Values are text. Traverse records without rounding numbers, injecting HTML,
 * or rendering an unbounded tree. Every original byte remains downloadable. */
export function RecordExplorer({ value }: { value: Json | undefined }) {
  const [trail, setTrail] = useState<string[]>([]), [page, setPage] = useState(0);
  const body = useRef<HTMLDivElement>(null);
  const [capacity, setCapacity] = useState({ rows: 3, characters: 160 });
  useLayoutEffect(() => {
    const node = body.current!;
    const fit = () => {
      const { height, width } = node.getBoundingClientRect();
      if (height <= 0 || width <= 0) return;
      const font = parseFloat(getComputedStyle(node).fontSize) || 15;
      const rowHeight = Math.max(48, ...[...node.querySelectorAll(".record-field")].map(row => row.getBoundingClientRect().height + 4));
      const next = { rows: Math.max(1, Math.min(6, Math.floor(height / rowHeight))), characters: Math.max(16, Math.min(240, Math.floor(width / (font * .65)) * Math.floor(height / (font * 1.8)))) };
      setCapacity(previous => previous.rows === next.rows && previous.characters === next.characters ? previous : next);
    };
    const observer = new ResizeObserver(fit); observer.observe(node); fit();
    return () => observer.disconnect();
  }, [trail]);
  let current = value;
  for (const key of trail) current = current !== null && typeof current === "object" ? (current as JsonObject)[key] : undefined;
  const entries = current !== null && typeof current === "object" && !(current instanceof JsonNumber) ? Object.entries(current) : null;
  const raw = entries ? "" : display(current), size = capacity.rows;
  const pages = Math.max(1, Math.ceil((entries?.length ?? raw.length) / (entries ? size : capacity.characters)));
  const index = Math.min(page, pages - 1);
  return <div className="record-explorer">
    <div className="record-breadcrumb"><button disabled={!trail.length} onClick={() => { setTrail(trail.slice(0, -1)); setPage(0); }}>← Back</button><span>{trail.length ? trail.map(key => shortText(key, 72)).join(" / ") : "Record"}</span></div>
    <div className="record-explorer-body" ref={body}>{entries ? entries.slice(index * size, (index + 1) * size).map(([key, item]) => <button className="record-field" key={key} onClick={() => { setTrail([...trail, key]); setPage(0); }}><span>{shortText(key, 120)}</span><code>{preview(item)}</code><span aria-hidden="true">↗</span></button>) : <code className="record-value">{raw.slice(index * capacity.characters, (index + 1) * capacity.characters)}</code>}</div>
    <div className="review-pagination"><button disabled={index === 0} onClick={() => setPage(index - 1)} aria-label="Previous record page">←</button><span>{index + 1} / {pages}</span><button disabled={index + 1 === pages} onClick={() => setPage(index + 1)} aria-label="Next record page">→</button></div>
  </div>;
}
