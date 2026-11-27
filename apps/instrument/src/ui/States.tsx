// Deliberate states: loading, absent or corrupt data, unsupported schema and
// invalid locators. None of them is shaped like a valid moment.

import type { LoadError } from "../data/loader";
import { useLayoutEffect, useRef, useState } from "react";
import { useInstrumentState, useStore } from "../state/useStore";
import { DEFAULT_EVIDENCE } from "../state/locator";
import { issueTitle } from "./Inspector";
import { shortUrl } from "./RunSelector";
import { VISUAL_ASSET } from "../scene/visualAssetPin";

// Control the original HTML opening without replacing its mark or wordmark.
// They retain the same DOM and critical styles throughout the application handoff.
export interface OpeningStatus {
  waiting: boolean;
  stage: string;
  detail: string;
  progress?: number | undefined;
}

export function SiteOpening({ sceneReady, sceneDetail, sceneBytes = 0, onReadiness }: { sceneReady: boolean; sceneDetail?: string; sceneBytes?: number; onReadiness?: ((status: OpeningStatus) => void) | undefined }) {
  const state = useInstrumentState();
  const [opening] = useState(() => document.getElementById("site-opening"));
  const dismissed = useRef(false);
  const waiting = !dismissed.current && (state.initializing || (state.screen.kind === "ready" && !sceneReady));
  const stage = state.screen.kind === "loading" ? state.screen.stage : waiting ? "reconstruction" : "ready";
  const detail = state.screen.kind === "loading" ? state.screen.detail : waiting ? sceneDetail ?? "Preparing reconstruction" : state.screen.kind === "ready" ? "Instrument ready" : "The instrument needs attention";
  // The denominator comes from retained resource lengths, not stage weights or
  // elapsed time. Geometry is included before its transfer starts, so one line
  // continues across data, digest verification, worker decoding and first paint.
  const record = state.screen.kind === "ready" ? state.screen.run.record : null;
  const bytes = record ? record.samples.byte_length + (record.model?.byte_length ?? 0) + (record.frames?.byte_length ?? 0) : 0;
  const transfer = state.screen.kind === "loading" ? state.screen.transfer : record ? { loaded: bytes, total: bytes, reconstruction: !!(record.model && record.frames) } : undefined;
  const total = transfer ? transfer.total + (transfer.reconstruction ? VISUAL_ASSET.byte_length : 0) : 0;
  const progress = transfer && total > 0 ? Math.min(1, (transfer.loaded + (transfer.reconstruction ? sceneBytes : 0)) / total) : undefined;
  useLayoutEffect(() => {
    // The shared experience owns its opening. Report the qualified first frame
    // (or an explicit error), never merely the end of the data download.
    if (onReadiness) {
      onReadiness({ waiting, stage, detail, progress });
      if (!waiting) dismissed.current = true;
      return;
    }
    if (!opening || dismissed.current) return;
    opening.dataset.loadStage = stage;
    opening.dataset.revealed = String(!waiting);
    opening.setAttribute("aria-busy", String(waiting));
    const announcement = opening.querySelector(".boot-announcement");
    if (announcement) announcement.textContent = detail;
    if (waiting) return;
    // The qualified scene is already drawn. Remove the opaque opening in this
    // same paint, so the wordmark can never be superimposed on the robot.
    dismissed.current = true;
    opening.remove();
  }, [opening, waiting, stage, detail, progress, state.reducedMotion, onReadiness]);
  return null;
}

export function ErrorView({ error, evidenceUrl }: { error: LoadError; evidenceUrl: string }) {
  const store = useStore();
  const issue = error.issue;
  return (
    <div className="state state-error" role="alert">
      <p className="state-kicker">{error.stage} · {issue.kind}</p>
      <h1 className="state-title">{issueTitle(issue)}</h1>
      <p className="state-body">{issue.message}</p>
      <dl className="facts compact">
        <div>
          <dt>file</dt>
          <dd className="mono">{shortUrl(issue.url)}</dd>
        </div>
        {issue.expected !== null ? (
          <div>
            <dt>expected</dt>
            <dd className="mono">{issue.expected}</dd>
          </div>
        ) : null}
        {issue.actual !== null ? (
          <div>
            <dt>found</dt>
            <dd className="mono">{issue.actual}</dd>
          </div>
        ) : null}
        <div>
          <dt>evidence</dt>
          <dd className="mono">{evidenceUrl}</dd>
        </div>
      </dl>
      <p className="fine">Nothing from this generation is shown until its root and the selected resources verify. A displayed value never comes from unverified bytes.</p>
      <div className="state-actions">
        <button type="button" className="quiet" onClick={() => store.retry()}>
          Retry
        </button>
        {evidenceUrl !== DEFAULT_EVIDENCE ? (
          <button type="button" className="quiet" onClick={() => store.setEvidence(DEFAULT_EVIDENCE)}>
            Open the default evidence
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function InvalidLocatorView({ problems, hasSuggestion, label }: { problems: string[]; hasSuggestion: boolean; label: string | null }) {
  const store = useStore();
  return (
    <div className="state state-invalid" role="alert">
      <p className="state-kicker">invalid locator</p>
      <h1 className="state-title">This link does not name a moment in the current evidence.</h1>
      <ul className="plain state-body">
        {problems.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
      <p className="fine">The instrument never opens a different row or generation silently.{label ? ` Current evidence: ${label}.` : ""}</p>
      {hasSuggestion ? (
        <div className="state-actions">
          <button type="button" className="quiet" onClick={() => store.openSuggestion()}>
            Open the computed first mismatch in the current generation
          </button>
        </div>
      ) : (
        <div className="state-actions">
          <button type="button" className="quiet" onClick={() => store.setEvidence(DEFAULT_EVIDENCE)}>
            Open the default evidence
          </button>
        </div>
      )}
    </div>
  );
}
