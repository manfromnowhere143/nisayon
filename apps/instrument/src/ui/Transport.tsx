import { useEffect, useState, type CSSProperties } from "react";
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
  onMoment?: (origin: HTMLElement) => void;
  onEvidence?: () => void;
  detail?: "moment" | "evidence" | null;
}
function momentLabel(run: LoadedRun, moment: Moment) {
  const row = run.samples.rows[moment.row_index];
  return row
    ? `row ${row.row_index}, step ${row.step}, ${moment.phase}, ${timeForPhase(row, moment.phase).toFixed(2)} seconds`
    : `no sample at row ${moment.row_index}`;
}
/** Playback and exact recorded-row scrubbing share one unbacked control line. */
export function Transport({
  run,
  moment,
  playing,
  host,
  onMoment,
  onEvidence,
  detail,
}: Props) {
  const store = useStore(),
    [announcement, setAnnouncement] = useState("");
  const label = momentLabel(run, moment),
    row = run.samples.rows[moment.row_index];
  useEffect(() => {
    if (playing) return;
    const timer = setTimeout(
      () => setAnnouncement(`${run.record.run.run_id}: ${label}`),
      350,
    );
    return () => clearTimeout(timer);
  }, [label, playing, run.record.run.run_id]);
  const controls = (
    <div className="scene-playback" role="group" aria-label="Transport">
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>
      <button
        type="button"
        className="scene-play-control"
        aria-label={playing ? "Pause" : "Play recorded rows"}
        aria-pressed={playing}
        onClick={() => { if (!playing && moment.row_index >= run.record.row_count - 1) store.setRow(0); store.togglePlay(); }}
      >
        <Icon name={playing ? "pause" : "play"} />
      </button>
      <input className="scene-scrubber" type="range" min={0} max={Math.max(0, run.record.row_count - 1)} step={1}
        value={Math.min(moment.row_index, run.record.row_count - 1)} aria-label="Recording position" aria-valuetext={label}
        style={{ "--progress": `${run.record.row_count > 1 ? moment.row_index / (run.record.row_count - 1) * 100 : 0}%` } as CSSProperties}
        onPointerDown={() => store.pause()}
        onInput={event => { store.pause(); store.setRow(Number(event.currentTarget.value), "coalesce"); }} />
      <button
        type="button"
        className="scene-evidence-control"
        data-detail-trigger
        aria-expanded={detail === "evidence"}
        aria-haspopup="dialog"
        onClick={onEvidence ?? (() => store.setDepth("moment"))}
      >
        <span>Evidence</span>
        <small data-outcome={run.record.task_outcome}>Task {run.record.task_outcome || "not recorded"}</small>
      </button>
      <button
        type="button"
        className="scene-moment-control"
        data-detail-trigger
        aria-expanded={detail === "moment"}
        aria-haspopup="dialog"
        aria-label={`Inspect moment: ${label}`}
        onClick={(event) =>
          onMoment ? onMoment(event.currentTarget) : store.toggleInspector(true)
        }
      >
        <span>Moment</span>
        <output className="transport-time">
          {row
            ? `${timeForPhase(row, moment.phase).toFixed(2)} s`
            : "Recording ended"}
        </output>
      </button>
    </div>
  );
  return host === undefined
    ? controls
    : host
      ? createPortal(controls, host)
      : null;
}
export function RecordedTimeline({
  caseRecord,
  run,
  moment,
  compact = false,
}: Pick<Props, "caseRecord" | "run" | "moment"> & { compact?: boolean }) {
  const store = useStore(),
    last = run.record.row_count - 1;
  const finding = contextualFinding(caseRecord, run.record, run.samples.rows);
  return (
    <div className={`recorded-timeline${compact ? " recorded-timeline-compact" : ""}`} aria-label="Recorded row controls">
      {!compact ? <label>
        <span>{momentLabel(run, moment)}</span>
        <input
          type="range"
          min={0}
          max={last}
          step={1}
          value={Math.min(moment.row_index, last)}
          aria-label="Selected row"
          aria-valuetext={momentLabel(run, moment)}
          onInput={(event) =>
            store.setRow(Number(event.currentTarget.value), "coalesce")
          }
          onPointerDown={() => store.pause()}
        />
      </label> : null}
      <div>
        <button
          type="button"
          aria-label="Previous row"
          onClick={() => store.stepRow(-1)}
          disabled={moment.row_index <= 0}
        >
          <Icon name="prev" />
        </button>
        <button
          type="button"
          aria-label="Next row"
          onClick={() => store.stepRow(1)}
          disabled={moment.row_index >= last}
        >
          <Icon name="next" />
        </button>
        <button
          type="button"
          aria-label={
            finding.row !== null
              ? `Go to described finding, row ${finding.row}`
              : "Finding has no sample locator"
          }
          onClick={() => store.jumpToFinding()}
          disabled={finding.row === null}
        >
          Finding
        </button>
        <button
          type="button"
          aria-label={`Phase ${moment.phase}; switch to ${moment.phase === "before" ? "after" : "before"}`}
          onClick={() => store.togglePhase()}
        >
          {moment.phase}
        </button>
        <button
          type="button"
          aria-label="Open inspector"
          onClick={() => store.toggleInspector(true)}
        >
          Sources
        </button>
      </div>
    </div>
  );
}
