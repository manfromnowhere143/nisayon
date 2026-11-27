import { prepareRicci } from "../concepts/loadRicci";
// The quiet identity line: case, task, stage, generation digest, the fixture
// label when the manifest carries one, the ground control and the link.

import { useLayoutEffect, useRef } from "react";
import { WorkspaceMenu, type WorkspaceAction } from "./WorkspaceMenu";
import { workspaceUtilities } from "./WorkspaceActions";
import { InstrumentSymbol } from "./InstrumentSymbol";
import { WorkspaceNavigation } from "./WorkspaceNavigation";
import { StudyWorkspace } from "./StudyWorkspace";
import type { CaseRecord, Generation } from "../model/types";
import { useInstrumentState, useStore } from "../state/useStore";
import { BrandMark } from "./BrandMark";
import { Choice } from "./Choice";
import { openResearch } from "../research/navigation";

interface Props {
  generation: Generation;
  caseRecord: CaseRecord;
  active?: boolean;
}

export function Identity({ generation, caseRecord, active = true }: Props) {
  const store = useStore();
  const state = useInstrumentState();
  const header = useRef<HTMLElement>(null);
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
  const actions: WorkspaceAction[] = [
    { id: "study", label: state.study?.pin ? "Return to study" : "Study", icon: <InstrumentSymbol name="study" />, onSelect: () => store.openStudy() },
    { id: "sources", label: `Generation ${generation.sha256}; open the inspector's sources`, title: "Sources", icon: <InstrumentSymbol name="sources" />, onSelect: () => store.toggleInspector(true) },
    ...(caseSelector ? [{ id: "recording", label: "Recorded experiment", icon: <InstrumentSymbol name="recording" />, content: <>
      <label className="workspace-recording"><span>Recorded experiment</span><select aria-label="Choose a recorded experiment" value={caseRecord.case_key} onChange={event => state.library.length ? store.selectLibraryCase(event.target.value) : store.selectCase(event.target.value)}>
        {state.library.length ? <>{!state.library.some(entry => entry.caseKey === caseRecord.case_key) ? <option value={caseRecord.case_key}>Current generation</option> : null}{state.library.map(entry => <option key={entry.caseKey} value={entry.caseKey}>{entry.caseId}</option>)}</> : generation.cases.map(entry => <option key={entry.case_key} value={entry.case_key}>{entry.case_key}</option>)}
      </select></label>
      {state.pendingSelection ? <p role="status">Opening recording…</p> : null}
      {currentExport && currentExport.generation !== generation.sha256 ? <button type="button" className="export-update" onClick={() => store.selectLibraryCase(currentExport.caseKey)}>Open current export</button> : null}
      {fixture ? <span className="fine">Development fixture</span> : null}
    </> }] : []),
    ...workspaceUtilities({ ground: state.ground, toggleGround: () => store.toggleGround(), copyLink: () => { void store.copyLink(); }, copyLabel: "Copy a link to this exact moment" }),
  ];
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
      <WorkspaceMenu active={active} label="Workspace" onOpen={prepareRicci} navigation={<WorkspaceNavigation current="lab" navigate={openResearch} prepareRicci={prepareRicci} />} actions={actions} />
      {state.copied !== "idle" ? (
        <p className="copied" role="status">
          {state.copied === "copied" ? "Link copied." : "Clipboard unavailable; copy from the inspector's link field."}
        </p>
      ) : null}
      {active && state.study?.open ? <StudyWorkspace initialCase={caseRecord.case_key} route={state.study} onRoute={(route, mode) => store.setStudy(route, mode)} onClose={() => store.closeStudy()} library={state.library} onScene={url => store.openStudyScene(url)} /> : null}
    </header>
  );
}
