import { useLayoutEffect, useRef } from "react";
import type { ResearchRoute } from "./navigation";

type Surface = ResearchRoute["surface"];

export function InstrumentDock({
  surface,
  loading,
  navigate,
  transportHost,
}: {
  surface: Surface;
  loading: boolean;
  navigate: (surface: Surface) => void;
  transportHost: (host: HTMLDivElement | null) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const playback = surface === "lab" && !loading;
  useLayoutEffect(() => {
    const dock = root.current;
    if (!dock) return;
    const reserve = () => {
      const height = dock.getBoundingClientRect().height;
      if (height > 0) {
        const bottom = parseFloat(getComputedStyle(dock).bottom) || 0;
        document.documentElement.style.setProperty(
          "--instrument-dock-reserve",
          `${Math.ceil(height + bottom + 12)}px`,
        );
      }
    };
    const observer = new ResizeObserver(reserve);
    observer.observe(dock);
    reserve();
    window.addEventListener("resize", reserve);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", reserve);
      document.documentElement.style.removeProperty(
        "--instrument-dock-reserve",
      );
    };
  }, [playback]);
  return (
    <div
      ref={root}
      className="instrument-dock"
      data-view={surface}
      data-playback={playback}
    >
      <div
        className="instrument-playback"
        ref={transportHost}
        hidden={!playback}
        inert={!playback}
      />
      <nav className="research-dock" aria-label="Instrument navigation">
        <button
          aria-pressed={surface === "lab" || surface === "qualify" || surface === "checks"}
          onClick={() => navigate("lab")}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="6.5" />
            <path d="m15.5 15.5 5 5M8 10.5h5M10.5 8v5" />
          </svg>
          <span>Investigate</span>
        </button>
        <button
          aria-pressed={surface === "system" || surface === "research"}
          onClick={() => navigate("system")}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m3 8 9-5 9 5-9 5ZM3 12l9 5 9-5M3 16l9 5 9-5" />
          </svg>
          <span>Library</span>
        </button>
        <button aria-pressed={surface === "concepts"} onClick={() => navigate("concepts")}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2 8 5v10l-8 5-8-5V7ZM4 7l8 5 8-5M12 12v10" /></svg>
          <span>Concepts</span>
        </button>
        <button
          aria-pressed={surface === "develop"}
          onClick={() => navigate("develop")}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m7 7-5 5 5 5M17 7l5 5-5 5M14 4l-4 16" />
          </svg>
          <span>Develop</span>
        </button>
      </nav>
    </div>
  );
}
