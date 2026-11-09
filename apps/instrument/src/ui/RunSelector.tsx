// Paired-run switching that preserves the selected row. Light is the state:
// the selected run is brighter, not a colour.

import type { LoadIssue } from "../data/loader";
import { sameRun, type CaseRecord, type RunKey } from "../model/types";
import { useStore } from "../state/useStore";

interface Props {
  caseRecord: CaseRecord;
  selected: RunKey;
  pending: RunKey | null;
  notice: LoadIssue | null;
}

export function RunSelector({ caseRecord, selected, pending, notice }: Props) {
  const store = useStore();
  const selectedRecord = caseRecord.runs.find((r) => sameRun(r.run, selected));
  const peers = caseRecord.runs.filter((r) => r.run.bundle_sha256 === selected.bundle_sha256 && r.condition_id === selectedRecord?.condition_id && r.role !== "executed_prefix_context");
  return (
    <div className="run-selector">
      <div className="segmented" role="group" aria-label="Recorded runs in this bundle">
        {peers.map((run) => {
          const isSelected = sameRun(run.run, selected);
          const isPending = pending !== null && sameRun(run.run, pending);
          return (
            <button
              key={`${run.run.bundle_sha256}:${run.run.run_id}`}
              type="button"
              className={`segment${isSelected ? " is-selected" : ""}${run.role === "correction" ? " is-correction" : ""}`}
              aria-pressed={isSelected}
              aria-busy={isPending}
              onClick={() => store.selectRun(run.run)}
              title={`${run.run.run_id} · ${run.role} · task ${run.task_outcome} · ${run.row_count} rows`}
            >
              <span className="segment-role">{run.role}</span>
              <span className="segment-id mono">{run.run.run_id}</span>
            </button>
          );
        })}
      </div>
      {caseRecord.runs.length > peers.length ? (
        <label className="all-runs fine">
          Other recorded runs
          <select aria-label="All recorded runs" value={`${selected.bundle_sha256}:${selected.run_id}`} onChange={(event) => {
            const run = caseRecord.runs.find((r) => `${r.run.bundle_sha256}:${r.run.run_id}` === event.target.value);
            if (run) store.selectRun(run.run);
          }}>
            {caseRecord.runs.map((r) => <option key={`${r.run.bundle_sha256}:${r.run.run_id}`} value={`${r.run.bundle_sha256}:${r.run.run_id}`}>{r.stage} · {r.condition_id} · {r.run.run_id}</option>)}
          </select>
        </label>
      ) : null}
      {notice ? (
        <p className="notice" role="alert">
          {notice.kind === "integrity" ? "Integrity check failed for " : notice.kind === "absent" ? "Missing: " : "Could not load: "}
          <span className="mono">{shortUrl(notice.url)}</span> — {notice.message}. The current run stays displayed.{" "}
          <button type="button" className="quiet" onClick={() => store.clearNotice()}>
            Dismiss
          </button>
        </p>
      ) : null}
    </div>
  );
}

export function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/").filter(Boolean);
    return parts.slice(-2).join("/");
  } catch {
    return url;
  }
}
