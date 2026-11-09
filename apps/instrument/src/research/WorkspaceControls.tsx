import { useEffect, useState } from "react";

export function useCompactWorkspace() {
  const [compact, setCompact] = useState(
    () =>
      typeof matchMedia !== "undefined" &&
      matchMedia("(max-width: 760px)").matches,
  );
  useEffect(() => {
    const media = matchMedia("(max-width: 760px)");
    const update = () => setCompact(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return compact;
}

export function Pages({
  page,
  count,
  onChange,
  label,
}: {
  page: number;
  count: number;
  onChange: (page: number) => void;
  label: string;
}) {
  return (
    <nav className="workspace-pages" aria-label={label}>
      <button
        aria-label={`Previous ${label}`}
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
      >
        ←
      </button>
      <span role="status">
        {page + 1} / {Math.max(1, count)}
      </span>
      <button
        aria-label={`Next ${label}`}
        disabled={page >= count - 1}
        onClick={() => onChange(page + 1)}
      >
        →
      </button>
    </nav>
  );
}

/** Preserve every word of long source docstrings in bounded reading cards. */
export function textPages(text: string, limit = 430): string[] {
  const result: string[] = [];
  let remaining = text.trim();
  while (remaining.length > limit) {
    const prefix = remaining.slice(0, limit + 1);
    const sentence = Math.max(
      prefix.lastIndexOf(". "),
      prefix.lastIndexOf("\n"),
    );
    const cut = sentence > limit / 2 ? sentence + 1 : prefix.lastIndexOf(" ");
    const end = cut > 0 ? cut : limit;
    result.push(remaining.slice(0, end));
    remaining = remaining.slice(end).trimStart();
  }
  if (remaining) result.push(remaining);
  return result.length ? result : [""];
}

export function TextReading({ text, label }: { text: string; label: string }) {
  const compact = useCompactWorkspace();
  const [requested, setPage] = useState(0);
  const pages = textPages(text, compact ? 320 : 430);
  const page = Math.min(requested, pages.length - 1);
  return (
    <div className="text-reading">
      <p>{pages[page]}</p>
      {pages.length > 1 ? (
        <Pages
          page={page}
          count={pages.length}
          onChange={setPage}
          label={label}
        />
      ) : null}
    </div>
  );
}
