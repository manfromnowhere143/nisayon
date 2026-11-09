import { useLayoutEffect, useRef, useState } from "react";

/** Page original characters; copying always uses the complete command above. */
export function commandPages(command: string, columns: number, rows: number): string[] {
  const pages: string[] = [];
  let start = 0, column = 0, row = 0;
  for (let at = 0; at < command.length; at++) {
    if (row >= Math.max(1, rows)) { pages.push(command.slice(start, at)); start = at; row = 0; column = 0; }
    if (command[at] === "\n") { column = 0; row++; }
    else if (++column >= Math.max(1, columns)) { column = 0; row++; }
  }
  if (start < command.length || !pages.length) pages.push(command.slice(start));
  return pages;
}

export function CommandBlock({ command }: { command: string }) {
  const root = useRef<HTMLDivElement>(null), sample = useRef<HTMLSpanElement>(null);
  const [layout, setLayout] = useState({ columns: 100, rows: 6, shortRows: 4 }), [page, setPage] = useState(0);
  useLayoutEffect(() => {
    const node = root.current!;
    const measure = () => {
      const rect = node.getBoundingClientRect(), font = getComputedStyle(sample.current!);
      const glyph = sample.current!.getBoundingClientRect().width / 10;
      if (rect.width <= 0 || rect.height <= 0 || glyph <= 0) return;
      const line = parseFloat(font.lineHeight) || 24;
      const columns = Math.max(1, Math.floor((rect.width - 2) / glyph));
      const next = { columns, rows: Math.max(1, Math.floor((rect.height - 4) / line)), shortRows: Math.max(1, Math.floor((rect.height - 48) / line)) };
      setLayout(old => old.columns === next.columns && old.rows === next.rows && old.shortRows === next.shortRows ? old : next);
    };
    const observer = new ResizeObserver(measure); observer.observe(node); measure();
    return () => observer.disconnect();
  }, []);
  const full = commandPages(command, layout.columns, layout.rows);
  const pages = full.length === 1 ? full : commandPages(command, layout.columns, layout.shortRows);
  const current = Math.min(page, pages.length - 1);
  return <div className="command-block" ref={root}>
    <span ref={sample} className="command-measure" aria-hidden="true">MMMMMMMMMM</span>
    <pre aria-label="SDK command"><code>{pages[current]}</code></pre>
    {pages.length > 1 ? <div className="command-pages"><button disabled={current === 0} onClick={() => setPage(current - 1)} aria-label="Previous command page">←</button><span aria-live="polite">{current + 1} / {pages.length}</span><button disabled={current === pages.length - 1} onClick={() => setPage(current + 1)} aria-label="Next command page">→</button></div> : null}
  </div>;
}
