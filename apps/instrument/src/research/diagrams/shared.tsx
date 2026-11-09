import { Pages, useCompactWorkspace } from "../WorkspaceControls";
import type { ReactNode } from "react";
import type { ResearchCase } from "../catalog";
import type { ResearchRoute } from "../navigation";

export interface DiagramProps {
  entry: ResearchCase;
  route: ResearchRoute;
  select: (patch: Partial<ResearchRoute>, replace?: boolean) => void;
}
export const fmt = (n: number) =>
  new Intl.NumberFormat("en", { maximumFractionDigits: 3 }).format(n);
export const variantLabel = (route: ResearchRoute) =>
  route.variant === "corrected" ? "Corrected" : "Unchanged";

export function Variant({
  route,
  select,
}: Pick<DiagramProps, "route" | "select">) {
  return (
    <div
      className="research-variant"
      role="group"
      aria-label="Source variant"
      data-variant={route.variant}
    >
      {(["original", "corrected"] as const).map((v) => (
        <button
          key={v}
          type="button"
          aria-pressed={route.variant === v}
          onClick={() => select({ variant: v })}
        >
          {v === "original" ? "Unchanged" : "Corrected"}
        </button>
      ))}
    </div>
  );
}
export function DiagramHeader({
  label,
  children,
}: {
  label: string;
  children?: ReactNode;
}) {
  return (
    <div className="diagram-heading">
      <span className="research-micro">{label}</span>
      {children}
    </div>
  );
}

export function ControlField({
  controls,
  route,
  select,
  label,
}: {
  controls: { name: string; before: string; after: string }[];
  label: string;
} & Pick<DiagramProps, "route" | "select">) {
  const compact = useCompactWorkspace();
  const pageSize = compact ? 12 : 48;
  // Follow the selected witness, including incoming shared links and resizing.
  const page = Math.floor(
    Math.min(route.sample, controls.length - 1) / pageSize,
  );
  return (
    <>
      <div className="test-field" role="group" aria-label={label}>
        {controls
          .slice(page * pageSize, (page + 1) * pageSize)
          .map((c, offset) => {
            const i = page * pageSize + offset;
            const result = route.variant === "corrected" ? c.after : c.before;
            return (
              <button
                key={c.name}
                className={result === "passed" ? "is-passed" : "is-failed"}
                aria-label={`Control ${i + 1}: ${c.name}, ${result}`}
                aria-pressed={route.sample === i}
                onClick={() => select({ sample: i })}
              >
                {result === "passed" ? "✓" : "×"}
              </button>
            );
          })}
      </div>
      {controls.length > pageSize ? (
        <Pages
          page={page}
          count={Math.ceil(controls.length / pageSize)}
          onChange={(p) => select({ sample: p * pageSize })}
          label="control group"
        />
      ) : null}
    </>
  );
}
