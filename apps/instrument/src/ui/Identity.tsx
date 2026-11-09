// The quiet identity line: case, task, stage, generation digest, the fixture
// label when the manifest carries one, the ground control and the link.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { GlassCard } from "../research/GlassCard";
import { StudyWorkspace } from "./StudyWorkspace";
import type { CaseRecord, Generation } from "../model/types";
import { shortSha } from "../model/types";
import { useInstrumentState, useStore } from "../state/useStore";
import { Icon } from "./Icon";
import { BrandMark } from "./BrandMark";
import { Choice } from "./Choice";
import { openResearch } from "../research/navigation";
import { AppAccessButton } from "../pwa/AppAccess";

interface Props {
  generation: Generation;
  caseRecord: CaseRecord;
  active?: boolean;
}

export function Identity({ generation, caseRecord, active = true }: Props) {
  const store = useStore();
  const state = useInstrumentState();
  const header = useRef<HTMLElement>(null);
  const [controls, setControls] = useState(false);
  useEffect(() => { if (!active) setControls(false); }, [active]);
  useLayoutEffect(() => {
    const node = header.current;
    if (!node) return;
    const measure = () => {
      if (node.offsetHeight > 0) document.documentElement.style.setProperty("--identity-h", `${node.offsetHeight}px`);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(node); measure();
    return () => { observer.disconnect(); document.documentElement.style.removeProperty("--identity-h"); };
  }, []);
  const currentExport = state.library.find((entry) => entry.caseKey === caseRecord.case_key);
  const stage = state.screen.kind === "ready" ? state.screen.run.record.stage ?? caseRecord.stage : caseRecord.stage;
  const fixture = generation.label !== null && /fixture/i.test(generation.label);
  const arm = caseRecord.arm ? ` · arm ${caseRecord.arm}` : "";
  const caseSelector = state.library.length > 0 ? (
        <div className="case-select" data-pending={state.pendingSelection !== null}>
          <Choice label="Recorded experiment" value={state.library.some((c) => c.caseKey === caseRecord.case_key) ? caseRecord.case_key : ""} options={[
            ...(!state.library.some((c) => c.caseKey === caseRecord.case_key) ? [{ value: "", label: "Current generation" }] : []),
            ...state.library.map((entry) => ({ value: entry.caseKey, label: entry.caseId })),
          ]} onChange={(value) => store.selectLibraryCase(value)} busy={state.pendingSelection !== null} />
          {state.pendingSelection ? <span className="choice-pending" role="status">Opening {state.library.find((entry) => entry.caseKey === state.pendingSelection?.caseKey)?.caseId ?? "recording"}…</span> : null}
        </div>
      ) : generation.cases.length > 1 ? (
        <div className="case-select"><Choice label="Case in this generation" value={caseRecord.case_key} options={generation.cases.map((entry) => ({ value: entry.case_key, label: entry.case_key }))} onChange={(value) => store.selectCase(value)} busy={state.pendingSelection !== null} /></div>
      ) : null;
  return (
    <header ref={header} className="identity">
      <a className="identity-brand" href="/" aria-label="Nisayon home" onClick={(event) => { if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey && event.button === 0) { event.preventDefault(); openResearch("home"); } }}><BrandMark /><span>Nisayon</span></a>
      <div className="identity-main">
        <span className="identity-case">
          {caseRecord.case_id}
          {arm}
        </span>
        <span className="identity-sep" aria-hidden="true">
          ·
        </span>
        <span className="identity-task">{caseRecord.task ?? caseRecord.experiment_id}</span>
        <span className="identity-sep" aria-hidden="true">
          ·
        </span>
        <span className="identity-stage">{stage} · recorded</span>
      </div>
      {caseSelector}
      {state.selectionIssue ? <p className="selection-notice" role="alert">Could not open that selection: {state.selectionIssue.message}. The previous verified experiment remains displayed. <button type="button" className="quiet" onClick={() => store.clearSelectionIssue()}>Dismiss</button></p> : null}
      {state.libraryIssue ? <span className="fine" role="status">Library unavailable · current source remains open</span> : null}
      <button className="workspace-menu" aria-haspopup="dialog" onClick={() => setControls(true)} aria-label="Workspace controls"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/></svg></button>
      {active && controls ? <GlassCard title="Workspace controls" onClose={() => setControls(false)}><div className="identity-side">
        {caseSelector ? <section className="workspace-recording" aria-label="Choose a recorded experiment"><p className="eyebrow">Recorded experiment</p>{caseSelector}</section> : null}
        <AppAccessButton />
        <button type="button" className="chip research-open" onClick={() => openResearch()}>Investigate ↗</button>
        <button type="button" className="chip study-open" aria-haspopup="dialog" onClick={() => store.openStudy()}>{state.study?.pin ? "Return to study ↗" : "Study ↗"}</button>
        {currentExport && currentExport.generation !== generation.sha256 ? <button type="button" className="chip export-update" onClick={() => store.selectLibraryCase(currentExport.caseKey)} title="Open the generation currently listed by the export catalog. Back returns to this pinned moment.">Open current export ↗</button> : null}
        {fixture ? (
          <span className="chip chip-warn" title={generation.label ?? ""}>
            development fixture
          </span>
        ) : null}
        <button type="button" className="chip mono" title={`generation ${generation.sha256}`} aria-label={`Generation ${generation.sha256}; open the inspector's sources`} onClick={() => store.toggleInspector(true)}>
          {shortSha(generation.sha256)}
        </button>
        <button type="button" className="ibtn" aria-label={`Ground: ${state.ground}. Switch to ${state.ground === "black" ? "paper" : "black"}`} aria-pressed={state.ground === "paper"} onClick={() => store.toggleGround()}>
          <Icon name="ground" />
        </button>
        <button type="button" className="ibtn" aria-label="Copy a link to this exact moment" onClick={() => void store.copyLink()}>
          <Icon name="link" />
        </button>
      </div></GlassCard> : null}
      {state.copied !== "idle" ? (
        <p className="copied" role="status">
          {state.copied === "copied" ? "Link copied." : "Clipboard unavailable; copy from the inspector's link field."}
        </p>
      ) : null}
      {active && state.study?.open ? <StudyWorkspace initialCase={caseRecord.case_key} route={state.study} onRoute={(route, mode) => store.setStudy(route, mode)} onClose={() => store.closeStudy()} library={state.library} onScene={url => store.openStudyScene(url)} /> : null}
    </header>
  );
}
