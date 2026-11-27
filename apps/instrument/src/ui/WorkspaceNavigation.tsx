import type { ResearchRoute } from "../research/navigation";
import { InstrumentSymbol } from "./InstrumentSymbol";
import { BrandMark } from "./BrandMark";

type Surface = ResearchRoute["surface"];
const destinations = [
  ["lab", "Laboratory"],
  ["system", "Library"],
  ["concepts", "Ricci"],
  ["develop", "Develop"],
] as const;

/** The same destinations and current-page signal in every scene's menu. */
export function WorkspaceNavigation({
  current,
  navigate,
  prepareRicci,
  home = false,
}: {
  current: Surface;
  navigate: (surface: Surface) => void;
  prepareRicci?: (() => void) | undefined;
  home?: boolean;
}) {
  return (
    <nav className="workspace-destinations" aria-label="Instrument navigation">
      {destinations.map(([id, label]) => (
        <button
          type="button"
          key={id}
          aria-label={label}
          title={label}
          aria-current={current === id ? "page" : undefined}
          onPointerEnter={id === "concepts" ? prepareRicci : undefined}
          onPointerDown={id === "concepts" ? prepareRicci : undefined}
          onFocus={id === "concepts" ? prepareRicci : undefined}
          onClick={() => navigate(id)}
        >
          {id === "lab" ? (
            <InstrumentSymbol name="lab" />
          ) : (
            <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
              {id === "system" ? (
                <>
                  <path d="M7 7h16v20H7zM11 3h16v20M11 13h8M11 18h5" />
                  <circle cx="19" cy="22" r="1" />
                </>
              ) : null}
              {id === "concepts" ? (
                <>
                  <path d="M12 4h8l1 5-3 3h-4l-3-3ZM11 15h10l-1 8h-8ZM8 16l-2 8M24 16l2 8M13 26v3M19 26v3" />
                  <path d="M16 12v3M12 18h8" opacity=".55" />
                </>
              ) : null}
              {id === "develop" ? (
                <>
                  <path d="M8 5H5v22h3M24 5h3v22h-3M10 11h12M10 21h12" />
                  <circle cx="13" cy="11" r="2.5" />
                  <circle cx="20" cy="21" r="2.5" />
                </>
              ) : null}
            </svg>
          )}
          <span>{label}</span>
          <i aria-hidden="true" />
        </button>
      ))}
      {home ? (
        <button
          type="button"
          aria-label="Home"
          title="Home"
          onClick={() => navigate("home")}
          aria-current={current === "home" ? "page" : undefined}
        >
          <BrandMark size={28} />
          <span>Home</span>
          <i aria-hidden="true" />
        </button>
      ) : null}
    </nav>
  );
}
