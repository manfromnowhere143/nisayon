// One floating transport, mounted for the life of the instrument. Discrete
// rows, exact readings, keyboard and touch equivalents for every control.

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { LoadedRun } from "../data/loader";
import { contextualFinding, timeForPhase } from "../model/findings";
import type { CaseRecord, Moment } from "../model/types";
import { useStore } from "../state/useStore";
import { Icon } from "./Icon";

interface Props {
  caseRecord: CaseRecord;
  run: LoadedRun;
  moment: Moment;
  playing: boolean;
  inspectorOpen: boolean;
  host?: HTMLElement | null | undefined;
}

export function Transport({ caseRecord, run, moment, playing, inspectorOpen, host }: Props) {
  const store = useStore();
  const dockRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const dock = dockRef.current;
    if (!dock || host !== undefined) return;
    const reserve = () => {
      const height = dock.getBoundingClientRect().height;
      if (height > 0) document.documentElement.style.setProperty("--transport-reserve", `${Math.ceil(height + (parseFloat(getComputedStyle(dock).bottom) || 0) + 18)}px`);
    };
    const observer = new ResizeObserver(reserve);
    observer.observe(dock);
    reserve();
    window.addEventListener("resize", reserve);
    return () => { observer.disconnect(); window.removeEventListener("resize", reserve); document.documentElement.style.removeProperty("--transport-reserve"); };
  }, [host]);
  const last = run.record.row_count - 1;
  const row = run.samples.rows[moment.row_index] ?? null;
  const ended = row === null;
  const finding = contextualFinding(caseRecord, run.record, run.samples.rows);
  const time = row ? timeForPhase(row, moment.phase) : null;
  const valueText = row ? `row ${row.row_index}, step ${row.step}, ${moment.phase} phase, ${time!.toFixed(2)} seconds` : `no sample at row ${moment.row_index}; recording ends at row ${last}`;
  // A settled selection is announced once; playback stays silent until it pauses.
  const [announcement, setAnnouncement] = useState("");
  useEffect(() => {
    if (playing) return;
    const id = window.setTimeout(() => setAnnouncement(`${run.record.run.run_id}: ${valueText}`), 350);
    return () => window.clearTimeout(id);
  }, [valueText, playing, run.record.run.run_id]);

  const controls = (
    <div ref={dockRef} className="transport-dock" role="group" aria-label="Transport">
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      <div className="transport-rail glass">
        <input
          className="transport-slider"
          type="range"
          min={0}
          max={last}
          step={1}
          value={Math.min(moment.row_index, last)}
          aria-label="Selected row"
          aria-valuetext={valueText}
          onInput={(event) => store.setRow(Number((event.target as HTMLInputElement).value), "coalesce")}
          onPointerDown={() => store.pause()}
        />
      </div>
      <div className="transport glass">
        <button type="button" className="tbtn" aria-label="Previous row" onClick={() => store.stepRow(-1)} disabled={moment.row_index <= 0}>
          <Icon name="prev" />
        </button>
        <button type="button" className="tbtn tbtn-play" aria-label={playing ? "Pause" : "Play recorded rows"} aria-pressed={playing} onClick={() => store.togglePlay()} disabled={moment.row_index >= last && !playing}>
          <Icon name={playing ? "pause" : "play"} />
        </button>
        <button type="button" className="tbtn" aria-label="Next row" onClick={() => store.stepRow(1)} disabled={moment.row_index >= last}>
          <Icon name="next" />
        </button>
        <button
          type="button"
          className="tbtn tbtn-finding"
          aria-label={finding.row !== null ? `Go to described finding, row ${finding.row}` : "This finding has no recorded sample locator"}
          onClick={() => store.jumpToFinding()}
          disabled={finding.row === null}
          aria-pressed={finding.row !== null && finding.row === moment.row_index}
        >
          <Icon name="fork" />
        </button>
        <output className="transport-readout" aria-live="off">
          {ended ? (
            <>
              <span className="transport-time num">ended</span>
              <span className="transport-row num">row {last} was last</span>
            </>
          ) : (
            <>
              <span className="transport-time num">{time!.toFixed(2)} s</span>
              <span className="transport-row num">
                row {row.row_index}
                {row.step !== row.row_index ? ` · step ${row.step}` : ""}
              </span>
            </>
          )}
        </output>
        <button type="button" className="tbtn tbtn-phase" aria-label={`Phase ${moment.phase}; switch to ${moment.phase === "before" ? "after" : "before"}`} onClick={() => store.togglePhase()}>
          <span className="phase-word">{moment.phase}</span>
        </button>
        <button type="button" className="tbtn tbtn-inspect" aria-label={inspectorOpen ? "Close inspector" : "Open inspector"} aria-pressed={inspectorOpen} aria-controls="inspector" onClick={() => store.toggleInspector()}>
          <Icon name="inspect" />
        </button>
      </div>
    </div>
  );
  // A portal keeps the store context and playback state while the shared dock
  // owns placement and viewport reservation. Standalone App keeps its dock.
  return host === undefined ? controls : host ? createPortal(controls, host) : null;
}
