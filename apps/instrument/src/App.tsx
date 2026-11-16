import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { recordingEnd, type LoadedRun, type LoaderOptions } from "./data/loader";
import type { FramePhase } from "./model/types";
import { alignedRow } from "./model/findings";
import { SCENE_VIEWS, type SceneHandle, type SceneView } from "./scene/renderer";
import { Scene } from "./scene/Scene";
import { InstrumentStore } from "./state/store";
import { StoreContext, useInstrumentState, useStore } from "./state/useStore";
import { DepthSurface } from "./ui/DepthSurface";
import { EnginePanel } from "./ui/EnginePanel";
import { EvidenceIdentity } from "./ui/EvidenceFlow";
import { SectionDeck } from "./ui/RecordPages";
import { GlassCard } from "./research/GlassCard";
import { Diagnostics } from "./ui/Diagnostics";
import { Finding } from "./ui/Finding";
import { CaseBrief } from "./ui/CaseBrief";
import { Identity } from "./ui/Identity";
import { Inspector } from "./ui/Inspector";
import { Lanes } from "./ui/Lanes";
import { RunSelector } from "./ui/RunSelector";
import { ErrorView, InvalidLocatorView, SiteOpening, type OpeningStatus } from "./ui/States";
import { installFocusPresentation } from "./ui/focusPresentation";
import { Transport } from "./ui/Transport";
import { SpatialPanel } from "./ui/SpatialPanel";
import { MomentInspection, type InspectionStep } from "./ui/MomentInspection";
import { Choice } from "./ui/Choice";
import { useSurfaceArrival } from "./ui/useSurfaceArrival";
import { bodyLabel, bodyPose, configurationPath, observationPose, pathCount, pathStart, type SpatialOptions, type ObservationTarget } from "./model/spatial";
import type { SpatialLayerState } from "./scene/evidenceLayer";

const VIEW_LABEL: Record<SceneView, string> = { "three-quarter": "three-quarter", side: "side", top: "top" };

export function App({ loader, onStore, onReadiness, transportHost, active = true }: { loader?: LoaderOptions; onStore?: (store: InstrumentStore | null) => void; onReadiness?: (status: OpeningStatus) => void; transportHost?: HTMLElement | null; active?: boolean }) {
  const [store] = useState(() => (loader ? new InstrumentStore(loader) : new InstrumentStore()));
  const [sceneReady, setSceneReady] = useState(false);
  const [sceneDetail, setSceneDetail] = useState("Preparing the detailed lab");
  const onSceneReady = useCallback(() => setSceneReady(true), []);
  useEffect(() => { onStore?.(store); return () => onStore?.(null); }, [store, onStore]);
  useEffect(() => {
    store.start();
    const restoreFocusPresentation = installFocusPresentation(document);
    const stopMeasurements = store.metrics.observeBrowser();
    const onPop = (): void => store.handlePopState();
    const onResearch = (): void => store.pause();
    window.addEventListener("popstate", onPop);
    window.addEventListener("nisayon:navigate", onResearch);
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    const onMotion = (): void => store.setReducedMotion(motion.matches);
    motion.addEventListener("change", onMotion);
    const onVisibility = (): void => {
      if (document.visibilityState !== "visible") store.pause();
      else void store.refreshLibrary();
    };
    document.addEventListener("visibilitychange", onVisibility);
    const discoveryTimer = window.setInterval(() => { if (document.visibilityState === "visible") void store.refreshLibrary(); }, 15_000);
    (window as unknown as { __nisayon?: unknown }).__nisayon = { store, metrics: () => store.metrics.summary() };
    return () => {
      store.dispose();
      restoreFocusPresentation();
      stopMeasurements();
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("nisayon:navigate", onResearch);
      motion.removeEventListener("change", onMotion);
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearInterval(discoveryTimer);
    };
  }, [store]);
  return (
    <StoreContext.Provider value={store}>
      <Instrument onSceneReady={onSceneReady} onSceneProgress={setSceneDetail} transportHost={transportHost} active={active} />
      <SiteOpening sceneReady={sceneReady} sceneDetail={sceneDetail} onReadiness={onReadiness} />
    </StoreContext.Provider>
  );
}

function frameFor(run: LoadedRun | null, row: number, phase: "before" | "after"): FramePhase | null {
  return run?.frames?.rows[row]?.[phase] ?? null;
}

function Instrument({ onSceneReady, onSceneProgress, transportHost, active }: { onSceneReady: () => void; onSceneProgress: (detail: string) => void; transportHost: HTMLElement | null | undefined; active: boolean }) {
  const store = useStore();
  const state = useInstrumentState();
  const [compact, setCompact] = useState(() => matchMedia("(max-width: 1023px), (max-height: 780px)").matches);
  useEffect(() => {
    const query = matchMedia("(max-width: 1023px), (max-height: 780px)");
    const update = () => setCompact(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const [engineOpen, setEngineOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const briefNavigation = useRef(false);
  useLayoutEffect(() => {
    if (!briefOpen && briefNavigation.current) {
      briefNavigation.current = false;
      readingRef.current?.querySelector<HTMLElement>('.analysis-tab[aria-pressed="true"]')?.focus({ preventScroll: true });
    }
  }, [briefOpen]);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [labSetting, setLabSetting] = useState<"architecture" | "source">("architecture");
  const [inspection, setInspection] = useState<InspectionStep | null>(null);
  const inspectionOrigin = useRef<HTMLElement | null>(null);
  const inspectionOriginPane = useRef<"scene" | "evidence">("scene");
  const inspectionReturn = useRef<"origin" | "analysis" | null>(null);
  const [readingsSection, setReadingsSection] = useState("signals");
  const [spatialOptions, setSpatialOptions] = useState<SpatialOptions>({ observations: false, path: false, axes: false });
  const [observationTarget, setObservationTarget] = useState<ObservationTarget>("eef");
  const [pathSeconds, setPathSeconds] = useState<number | null>(1);
  useEffect(() => { if (state.part) setReadingsSection("spatial"); }, [state.part]);
  const [mobilePane, setMobilePane] = useState<"scene" | "evidence">("scene");
  useEffect(() => {
    if (!active) { setToolsOpen(false); setMobilePane("scene"); setInspection(null); setEngineOpen(false); store.toggleInspector(false); if (store.getState().study?.open) store.closeStudy(); }
  }, [active, store]);
  const selectedDepth = state.screen.kind === "ready" ? state.screen.depth : "moment";
  useEffect(() => { if (selectedDepth !== "moment" || state.diagnostics) { setMobilePane("evidence"); setBriefOpen(false); } }, [selectedDepth, state.diagnostics]);
  const readingRef = useRef<HTMLElement>(null);
  const focusPartDetails = useRef(false);
  const partDetailsButton = useRef<HTMLButtonElement>(null);
  const returnToPart = useRef(false);
  useLayoutEffect(() => {
    if (mobilePane === "scene" && returnToPart.current) {
      returnToPart.current = false; partDetailsButton.current?.focus({ preventScroll: true });
    }
  }, [mobilePane]);
  useLayoutEffect(() => {
    if (!focusPartDetails.current) return;
    const heading = readingRef.current?.querySelector<HTMLElement>(".spatial-heading h2");
    if (heading) { focusPartDetails.current = false; heading.focus({ preventScroll: true }); }
  });
  const caseIdentity = state.screen.kind === "ready" ? `${state.screen.generation.sha256}:${state.screen.caseRecord.case_key}` : "";
  const priorCase = useRef(caseIdentity);
  useLayoutEffect(() => {
    if (caseIdentity && priorCase.current && caseIdentity !== priorCase.current) {
      setEngineOpen(false); setBriefOpen(false); setInspection(null); setReadingsSection("signals"); store.toggleInspector(false);
    }
    priorCase.current = caseIdentity;
  }, [caseIdentity, store]);
  useSurfaceArrival(readingRef, caseIdentity ? `${caseIdentity}:${state.screen.kind === "ready" ? state.screen.depth : ""}:${state.part?.name ?? ""}:${engineOpen}:${inspection}:${readingsSection}:${mobilePane}` : "", state.reducedMotion);
  const openInspection = (origin: HTMLElement) => {
    setToolsOpen(false); setBriefOpen(false);
    inspectionOrigin.current = origin;
    inspectionOriginPane.current = mobilePane;
    store.pause(); store.toggleInspector(false); store.setDepth("moment");
    setEngineOpen(false); setMobilePane("evidence"); setInspection("capture");
  };
  const closeInspection = () => {
    inspectionReturn.current = "origin";
    setMobilePane(inspectionOriginPane.current);
    setInspection(null);
  };
  useLayoutEffect(() => {
    if (inspection !== null || !inspectionReturn.current) return;
    const target = inspectionReturn.current === "origin" ? inspectionOrigin.current : document.querySelector<HTMLElement>('.analysis-nav button[aria-pressed="true"]');
    inspectionReturn.current = null;
    target?.focus({ preventScroll: true });
  }, [inspection]);
  useEffect(() => { if (state.inspector) setInspection(null); }, [state.inspector]);
  const [scene, setScene] = useState<SceneHandle | null>(null);
  const sceneRef = useRef<SceneHandle | null>(null);
  const onHandle = useCallback((handle: SceneHandle | null) => {
    sceneRef.current = handle;
    setScene(handle);
  }, []);
  const onFirstFrame = useCallback(() => { store.metrics.markFirstUsefulView(); onSceneReady(); }, [store, onSceneReady]);

  // Control response is measured from the input to the DOM commit that follows.
  useLayoutEffect(() => {
    store.metrics.commitInput();
  });

  useEffect(() => {
    document.documentElement.style.fontSize = state.textScale === 100 ? "" : `${state.textScale}%`;
  }, [state.textScale]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.defaultPrevented) return;
      if (document.documentElement.dataset.surface && document.documentElement.dataset.surface !== "lab") return;
      const target = event.target instanceof HTMLElement ? event.target : null;
      if (target?.closest('dialog[open], [role="combobox"], [role="listbox"]')) return;
      if (event.key === "Escape" && engineOpen) { setEngineOpen(false); return; }
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable)) {
        if (event.key === "Escape") store.back();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === " " && target?.closest("button, a")) return;
      switch (event.key) {
        case "ArrowLeft":
          event.preventDefault();
          store.stepRow(event.shiftKey ? -10 : -1);
          break;
        case "ArrowRight":
          event.preventDefault();
          store.stepRow(event.shiftKey ? 10 : 1);
          break;
        case "Home":
          event.preventDefault();
          store.setRow(0, "replace");
          break;
        case "End":
          event.preventDefault();
          store.goToLastRow();
          break;
        case " ":
          event.preventDefault();
          store.togglePlay();
          break;
        case "m":
        case "M":
          store.jumpToFinding();
          break;
        case "p":
        case "P":
          store.togglePhase();
          break;
        case "i":
        case "I":
          store.toggleInspector();
          break;
        case "t":
        case "T":
          store.toggleGround();
          break;
        case "r":
        case "R":
          store.cycleRun();
          break;
        case "v":
        case "V": {
          const index = SCENE_VIEWS.indexOf(state.view);
          store.setView(SCENE_VIEWS[(index + 1) % SCENE_VIEWS.length]!);
          break;
        }
        case "d":
        case "D":
          store.toggleDiagnostics();
          break;
        case "Escape":
          store.back();
          break;
        default:
          return;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [store, state.view, engineOpen]);

  const screen = state.screen;
  const primaryFrames = screen.kind === "ready" ? screen.run.frames : null;
  const pairedFrames = screen.kind === "ready" && screen.depth === "fork" ? screen.ghost?.frames : null;
  const recordings = useMemo(() => [primaryFrames, pairedFrames].filter((f) => f != null), [primaryFrames, pairedFrames]);
  const activeRun = screen.kind === "ready" ? screen.run : null;
  useEffect(() => { if (activeRun && (!activeRun.model || !activeRun.frames)) onFirstFrame(); }, [activeRun, onFirstFrame]);
  const selectedBody = activeRun?.model?.bodies.find((body) => body.name === state.part?.name)?.index ?? null;
  const inspectedBody = selectedBody ?? activeRun?.model?.bodies.find((body) => body.name === "gripper0_eef")?.index ?? null;
  const path = useMemo(() => configurationPath(primaryFrames, inspectedBody), [primaryFrames, inspectedBody]);
  const observationBounds = useMemo(() => (activeRun?.samples.rows ?? []).flatMap((row) => [row.observation, row.captured_observation].flatMap((observation) => [observationPose(observation, "eef"), observationPose(observation, "cube")].flatMap((pose) => pose ? [pose.position] : []))), [activeRun?.samples]);
  if (screen.kind === "loading") {
    return (
      <div className="app app-state">
        {!state.initializing ? <div className="state" role="status"><p className="state-body">{screen.detail}</p></div> : null}
      </div>
    );
  }
  if (screen.kind === "error") {
    return (
      <div className="app app-state">
        <ErrorView error={screen.error} evidenceUrl={state.evidenceUrl} />
        <Diagnostics scene={null} />
      </div>
    );
  }
  if (screen.kind === "invalid-locator") {
    return (
      <div className="app app-state">
        <InvalidLocatorView problems={screen.problems} hasSuggestion={screen.suggestion !== null} label={screen.label} />
        <Diagnostics scene={null} />
      </div>
    );
  }

  const { generation, caseRecord, moment, depth, run, ghost, ghostIssue, pendingRun, notice, condition } = screen;
  const frame = frameFor(run, moment.row_index, moment.phase);
  const row = run.samples.rows[moment.row_index] ?? null;
  const ghostRow = ghost ? alignedRow(row, ghost.samples.rows, moment.phase) : null;
  const ghostFrame = depth === "fork" && ghostRow ? frameFor(ghost, ghostRow.row_index, moment.phase) : null;
  const tone = run.record.role === "correction" ? "correction" : "neutral";
  const inspecting = inspection !== null && depth === "moment" && !engineOpen && !state.inspector;
  const spatial: SpatialLayerState = { row, before: frameFor(run, moment.row_index, "before"), pose: bodyPose(frame, inspectedBody), path, count: pathCount(moment.row_index, moment.phase, path), start: pathStart(primaryFrames, moment.row_index, moment.phase, pathSeconds), target: observationTarget, options: inspecting ? { ...spatialOptions, observations: inspection === "capture", goal: inspection === "command" } : spatialOptions, selectedBody };
  const inspectPart = (name: string | null) => {
    setBriefOpen(false);
    setInspection(null);
    setEngineOpen(false); setReadingsSection("spatial");
    if (name) setObservationTarget(name === "cube_main" ? "cube" : "eef");
    store.selectPart(name, "moment");
    if (state.inspector) store.toggleInspector(false);
  };
  const selectReadings = (id: string) => {
    setReadingsSection(id);
    if (id === "spatial") setSpatialOptions((options) => ({ ...options, observations: true }));
  };
  const openPartDetails = () => { setBriefOpen(false); setToolsOpen(false); store.pause(); returnToPart.current = true; focusPartDetails.current = true; setInspection(null); setEngineOpen(false); setReadingsSection("spatial"); setMobilePane("evidence"); store.setDepth("moment"); };
  const selectAnalysis = (value: typeof depth) => { setBriefOpen(false); setEngineOpen(false); store.setDepth(value); };
  const signals = <><Lanes primary={run} ghost={null} moment={moment} predicates={caseRecord.predicates} expanded={state.lanesExpanded} onSelectRow={(r, phase) => store.selectSample(r, phase)} /><div className="lanes-more"><button type="button" className="quiet" aria-expanded={state.lanesExpanded} onClick={() => store.toggleLanes()}>{state.lanesExpanded ? "Task signals" : "Timing & memory"}</button></div></>;
  const spatialPanel = <SpatialPanel run={run} generation={generation} moment={moment} body={inspectedBody} partSelected={state.part !== null} target={observationTarget} onTarget={setObservationTarget} pathActive={spatialOptions.path} pathSeconds={pathSeconds} onPathSeconds={setPathSeconds} />;

  return (
    <EvidenceIdentity.Provider value={`${generation.sha256}:${run.record.run.bundle_sha256}:${run.record.run.run_id}`}><div className="app" data-setting={labSetting} data-destination={state.sceneFocus} data-depth={depth} data-mobile-pane={mobilePane} data-inspecting={inspecting} data-inspector={state.inspector ? "open" : "closed"}>
      <Identity generation={generation} caseRecord={caseRecord} active={active} />
      <nav className="workspace-actions" aria-label="Experiment workspace">
        <button onClick={() => { store.pause(); setInspection(null); setEngineOpen(false); setBriefOpen(depth === "moment" && !state.diagnostics); setMobilePane("evidence"); }}>Evidence <span aria-hidden="true">↗</span></button>
        <button className="scene-inspect-action" disabled={!row} onClick={event => openInspection(event.currentTarget)}>Moment <span aria-hidden="true">↗</span></button>
        <button onClick={() => { store.pause(); setToolsOpen(true); }}>Scene <span aria-hidden="true">↗</span></button>
        <button onClick={() => { store.pause(); store.toggleInspector(true); }}>Sources <span aria-hidden="true">↗</span></button>
      </nav>
      <main className="stage">
        <section className="scene-area" aria-label="Reconstruction">
          <div className="scene-heading"><span className="lab-location">LABORATORY <span>/</span> BAY 01</span><h1>{caseRecord.task ?? caseRecord.case_id}</h1><span className="research-micro">{run.record.evidence_origin === "simulator" ? "RECORDED SIMULATION" : "RECORDED EXPERIMENT"}</span><p>{run.record.role.replaceAll("_", " ")}<span> / </span>{caseRecord.case_id}</p><p className="scene-outcome">Task outcome · {run.record.task_outcome || "not recorded"}</p></div>
          <button ref={partDetailsButton} type="button" className="selected-part-control" aria-label="Show selected part details" onClick={openPartDetails}><span>{state.part ? bodyLabel(state.part.name) : "End effector"}</span><span aria-hidden="true">↗</span></button>
          {active && toolsOpen ? <GlassCard title="Scene controls" eyebrow="RECONSTRUCTION" onClose={() => setToolsOpen(false)}>
          <SectionDeck label="Scene tools" sections={[{ id: "layers", label: "Body & layers", content: <div className="scene-tools" aria-label="Spatial tools">
            <div className="part-picker"><span>Inspect</span><Choice label="Inspect model body" value={state.part?.name ?? ""} disabled={!run.model} options={[{ value: "", label: "End effector overview", group: "overview" }, ...(run.model?.bodies.map((body) => ({ value: body.name, label: bodyLabel(body.name), group: body.name.startsWith("gripper") ? "gripper" : body.name.startsWith("robot") ? "robot" : body.name.startsWith("mount") ? "mount" : "scene" })) ?? [])]} onChange={(value) => inspectPart(value || null)} /><button type="button" className="part-details quiet" onClick={openPartDetails}>Details <span aria-hidden="true">↗</span></button></div>
            <div className="overlay-tools" role="group" aria-label="Recorded overlays">{([['path', 'Path'], ['axes', 'Axes'], ['goal', 'Goal'], ['collision', 'Collision']] as const).map(([key, label]) => <button key={key} type="button" aria-pressed={!!spatialOptions[key]} disabled={!run.frames || (key === 'goal' && !frame?.physical?.goal_pos)} onClick={() => setSpatialOptions((options) => ({ ...options, [key]: !options[key] }))}>{label}</button>)}</div>
          </div> }, { id: "camera", label: "Camera", content: <div className="scene-camera-tools"><p className="fine">Camera controls change the view. The retained configuration stays exact.</p><div className="overlay-tools" role="group" aria-label="Camera angle">{SCENE_VIEWS.map(view => <button key={view} aria-pressed={state.view === view} onClick={() => store.setView(view)}>{VIEW_LABEL[view]}</button>)}</div><button className="quiet" onClick={() => { store.setSceneFocus("lab"); store.setView("three-quarter"); scene?.resetView(); setToolsOpen(false); }}>Reset camera</button></div> }]} /></GlassCard> : null}
          {run.model && run.frames ? (
            <Scene frame={frame} ghostFrame={ghostFrame} model={run.model} modelSha={run.record.model!.sha256} generation={generation} ghostModel={depth === "fork" ? ghost?.model ?? null : null} ghostModelSha={depth === "fork" ? ghost?.record.model?.sha256 ?? null : null} recordings={recordings} focus={state.sceneFocus} setting={labSetting} view={state.view} ground={state.ground} tone={tone} reducedMotion={state.reducedMotion} onFirstFrame={onFirstFrame} onUnavailable={onSceneReady} onLoadProgress={onSceneProgress} onHandle={onHandle} spatial={spatial} observationBounds={observationBounds} onPick={(index) => { const body = run.model?.bodies[index]; if (body) inspectPart(body.name); }} />
          ) : (
            <div className="scene-box scene-unavailable" role="status">
              <p className="scene-unavailable-title">Reconstruction unavailable</p>
              <p className="fine">
                {run.framesIssue ? `${run.framesIssue.message}` : run.modelIssue ? run.modelIssue.message : "no frames published"}. The exact readings and controls remain available in Evidence and Sources.
              </p>
            </div>
          )}
          <div className="scene-caption">
            <span>
              {run.frames ? labSetting === "architecture" ? "Conceptual architecture · recorded robot & task" : "Source room · retained configuration" : "no reconstruction"}
              {depth === "fork" && ghost ? ` · ghost: ${ghost.record.run.run_id}` : ""}
              {depth === "fork" && ghost && !ghostRow ? " · no paired sample at this time" : ""}
            </span>
            <span className="num">
              {row === null ? `no sample at row ${moment.row_index}` : moment.phase === "before" ? `before · ${row.action_sim_time_s.toFixed(2)} s` : `after · ${row.next_sim_time_s.toFixed(2)} s`}
            </span>
          </div>
          <div className="view-controls" role="group" aria-label="Camera view">
            {(["lab", "workspace", "grasp"] as const).map(focus => <button key={focus} className="segment" aria-pressed={state.sceneFocus === focus} onClick={() => store.setSceneFocus(focus)}>{focus === "lab" ? "Hall" : focus === "workspace" ? "Bay" : "Grasp"}</button>)}
            <button className="segment source-room-toggle" aria-pressed={labSetting === "source"} onClick={() => setLabSetting(value => value === "source" ? "architecture" : "source")}>Source room</button>
            <button type="button" className="segment camera-preset" aria-label={`Camera: ${VIEW_LABEL[state.view]}. Change view`} onClick={() => store.setView(SCENE_VIEWS[(SCENE_VIEWS.indexOf(state.view) + 1) % SCENE_VIEWS.length]!)}>{VIEW_LABEL[state.view]}</button>
            <button type="button" className="segment camera-reset" aria-label="Reset camera" onClick={() => { store.setSceneFocus("lab"); store.setView("three-quarter"); scene?.resetView(); }}>↺</button>
            <button type="button" className="segment" aria-label="Zoom in on reconstruction" onClick={() => scene?.zoom(0.85)} disabled={!scene}>+</button>
            <button type="button" className="segment" aria-label="Zoom out on reconstruction" onClick={() => scene?.zoom(1.15)} disabled={!scene}>−</button>
          </div>
          {row === null ? (
            <p className="ended" role="status">
              {run.record.run.run_id} ended at row {run.record.row_count - 1} ({recordingEnd(run).toFixed(2)} s). There is no sample at row {moment.row_index}.{" "}
              <button type="button" className="quiet" onClick={() => store.goToLastRow()}>
                Go to its last row
              </button>
            </p>
          ) : null}
        </section>
        {active && (mobilePane === "evidence" || inspecting || engineOpen) ? <GlassCard title={inspecting ? "Inspect this moment" : "Experiment evidence"} eyebrow={`${caseRecord.case_id} · ROW ${moment.row_index} · ${moment.phase.toUpperCase()}`} wide onClose={() => { store.pause(); setMobilePane("scene"); setInspection(null); setEngineOpen(false); }}><section ref={readingRef} className="reading" aria-label="Experiment analysis">
          {inspecting ? <MomentInspection run={run} generation={generation} caseRecord={caseRecord} moment={moment} step={inspection} onStep={setInspection} target={observationTarget} onTarget={setObservationTarget} onClose={closeInspection} onCompare={() => { inspectionReturn.current = "analysis"; setInspection(null); setMobilePane("evidence"); store.setDepth("fork"); }} onDecision={() => { inspectionReturn.current = "analysis"; setInspection(null); setMobilePane("evidence"); store.setDepth("decision"); }} /> : null}
          <nav className="analysis-nav" aria-label="Analysis view" hidden={inspecting}>
            <button type="button" className="analysis-tab" aria-pressed={briefOpen && !engineOpen} onClick={() => { setEngineOpen(false); store.setDepth("moment"); setBriefOpen(true); }}>Case brief</button>
            {([['moment', 'Readings'], ['fork', 'Compare'], ['conditions', 'Conditions'], ['decision', 'Decision']] as const).map(([value, label]) => <button key={value} type="button" className="analysis-tab" aria-pressed={!briefOpen && !engineOpen && depth === value} onClick={() => selectAnalysis(value)}>{label}</button>)}
            <button type="button" className="analysis-tab" aria-pressed={engineOpen} onClick={() => { setBriefOpen(false); setEngineOpen(true); }}>Engine</button>
          </nav>
          <div className="reading-content" hidden={inspecting}>
            {briefOpen && !engineOpen && !state.diagnostics ? <CaseBrief generation={generation} caseRecord={caseRecord} run={run} onNavigate={(value) => { briefNavigation.current = true; selectAnalysis(value); }} /> : null}
            <div className="moment-view" hidden={briefOpen || state.diagnostics || engineOpen || depth !== "moment"}>
              {state.partNote ? <p className="selection-note fine" role="status">{state.partNote}</p> : null}
              {compact ? <SectionDeck label="Recorded detail" selected={readingsSection === "signals" ? "overview" : readingsSection} onSelect={selectReadings} sections={[
                { id: "overview", label: "Overview", content: <>
              <Finding caseRecord={caseRecord} run={run} moment={moment} depth={depth} onInspect={openInspection} />
              <RunSelector caseRecord={caseRecord} selected={moment.run} pending={pendingRun} notice={notice} />
              {screen.selectionNote ? <p className="selection-note fine" role="status">{screen.selectionNote}</p> : null}

                </> },
                { id: "compact-signals", label: "Signals", content: signals },
                { id: "spatial", label: "Spatial", fit: false, content: spatialPanel },
              ]} /> : <>
              <div hidden={readingsSection === "spatial"}><Finding caseRecord={caseRecord} run={run} moment={moment} depth={depth} onInspect={openInspection} /></div>
              <RunSelector caseRecord={caseRecord} selected={moment.run} pending={pendingRun} notice={notice} />
              {screen.selectionNote ? <p className="selection-note fine" role="status">{screen.selectionNote}</p> : null}
              <SectionDeck label="Recorded detail" selected={readingsSection === "spatial" ? "spatial" : "signals"} onSelect={selectReadings} sections={[{ id: "signals", label: "Signals", content: signals }, { id: "spatial", label: "Spatial", fit: false, content: spatialPanel }]} />
              </>}
            </div>
            <div className="context-view" hidden={briefOpen || state.diagnostics || engineOpen || depth === "moment"}>
              {depth === "fork" ? <SectionDeck label="Comparison detail" sections={[
                { id: "comparison", label: "Comparison", fit: false, content: <DepthSurface caseRecord={caseRecord} run={run} ghost={ghost} ghostIssue={ghostIssue} moment={moment} depth={depth} condition={condition} /> },
                { id: "signals", label: "Aligned signals", content: <><RunSelector caseRecord={caseRecord} selected={moment.run} pending={pendingRun} notice={notice} /><Lanes primary={run} ghost={ghost} moment={moment} predicates={caseRecord.predicates} expanded={state.lanesExpanded} onSelectRow={(r, phase) => store.selectSample(r, phase)} /></> },
              ]} /> : <DepthSurface caseRecord={caseRecord} run={run} ghost={ghost} ghostIssue={ghostIssue} moment={moment} depth={depth} condition={condition} />}
            </div>
            {engineOpen && !state.diagnostics ? <EnginePanel generation={generation} caseRecord={caseRecord} run={run} /> : null}
            <Diagnostics scene={scene} />
          </div>
        </section></GlassCard> : null}
        <Inspector generation={generation} caseRecord={caseRecord} run={run} moment={moment} open={active && state.inspector} />
      </main>
      <Transport caseRecord={caseRecord} run={run} moment={moment} playing={state.playing} inspectorOpen={state.inspector} host={transportHost} />
    </div></EvidenceIdentity.Provider>
  );
}
