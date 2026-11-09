import { useEffect, useState } from "react";
import type { ResearchCatalog } from "./catalog";
import { STATUS_LABEL, type ProgressRecord } from "./progress";
const EMPTY: NonNullable<ResearchCatalog["upstream"]> = [];

export function UpstreamLine({
  records = EMPTY,
  onOpen,
}: {
  records: ResearchCatalog["upstream"] | ProgressRecord[];
  onOpen?: () => void;
}) {
  const [index, setIndex] = useState(0),
    [paused, setPaused] = useState(false),
    [hovered, setHovered] = useState(false),
    [focused, setFocused] = useState(false);
  const [reduced, setReduced] = useState(
    () => matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [visible, setVisible] = useState(() => !document.hidden);
  const [presented, setPresented] = useState(records);
  useEffect(() => {
    if (!hovered && !focused) setPresented(records);
  }, [records, hovered, focused]);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    const motion = () => setReduced(media.matches),
      visibility = () => setVisible(!document.hidden);
    media.addEventListener("change", motion);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      media.removeEventListener("change", motion);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  useEffect(() => {
    if (
      presented.length < 2 ||
      paused ||
      hovered ||
      focused ||
      reduced ||
      !visible
    )
      return;
    const timer = window.setInterval(() => {
      if (!document.querySelector("dialog[open]"))
        setIndex((i) => (i + 1) % presented.length);
    }, 8000);
    return () => window.clearInterval(timer);
  }, [presented.length, paused, hovered, focused, reduced, visible]);
  const current = presented[index % presented.length];
  if (!current) return null;
  return (
    <div
      className="upstream-line"
      role="group"
      aria-label={onOpen ? "Public progress" : "Verified upstream changes"}
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setFocused(false);
      }}
    >
      <a
        key={current.url}
        href={current.url}
        target="_blank"
        rel="noopener noreferrer"
        title={"observedAt" in current ? `Status observed ${current.observedAt.slice(0, 10)}. ${current.title}` : `Verified ${current.date}. Retained status; not a live feed.`}
      >
        <span className="upstream-status">
          {STATUS_LABEL[current.status]} ·{" "}
          <time dateTime={current.date}>
            {current.date.slice(5).replace("-", "/")}
          </time>
        </span>
        <span className="upstream-title">{current.title} ↗</span>
      </a>
      {onOpen ? <button className="progress-open" type="button" onClick={onOpen} aria-label={`View all ${records.length} progress records`}><span>{records.length}</span><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 6h12M4 10h12M4 14h12" /></svg></button> : null}
      {presented.length > 1 ? (
        <>
          {!reduced ? (
            <button
              type="button"
              aria-label={
                paused ? "Resume upstream rotation" : "Pause upstream rotation"
              }
              onClick={() => setPaused((value) => !value)}
            >
              <svg viewBox="0 0 20 20" aria-hidden="true">
                {paused ? (
                  <path d="m7 5 7 5-7 5Z" />
                ) : (
                  <path d="M7 5v10M13 5v10" />
                )}
              </svg>
            </button>
          ) : null}
          <button
            type="button"
            aria-label="Next upstream change"
            onClick={() => setIndex((i) => (i + 1) % presented.length)}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="m8 5 5 5-5 5" />
            </svg>
          </button>
        </>
      ) : null}
    </div>
  );
}
