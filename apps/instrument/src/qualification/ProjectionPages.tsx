import { useState, type ReactNode } from "react";

export function ProjectionPages<T>({ rows, label, render }: { rows: T[]; label: string; render: (row: T, i: number) => ReactNode }) {
  const [page, setPage] = useState(0), size = 8, count = Math.max(1, Math.ceil(rows.length / size)), current = Math.min(page, count - 1);
  return <section className="projection-pages" aria-label={label}><div>{rows.slice(current * size, (current + 1) * size).map((row, i) => render(row, current * size + i))}</div>{count > 1 ? <nav aria-label={`${label} pages`}><button disabled={!current} onClick={() => setPage(current - 1)}>Previous</button><span>{current + 1} / {count}</span><button disabled={current === count - 1} onClick={() => setPage(current + 1)}>Next</button></nav> : null}</section>;
}
