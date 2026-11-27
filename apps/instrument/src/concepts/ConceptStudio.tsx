import { Icon } from "../ui/Icon";
import { useEffect, useRef, useState, type RefObject, type CSSProperties } from "react";
import {
  RICCI_CATALOG,
  readRicciSelection,
  ricciSelectionHash,
  type RicciPartId,
} from "./ricciCatalog";
import { RicciScene } from "./RicciScene";
import { RICCI_TRACE, tracePose, type TraceCase } from "./ricciTrace";
import type { RicciCameraState } from "./ricciRenderer";
import { useOutsideTap } from "../ui/useOutsideTap";
import { SceneDetail } from "../ui/SceneDetail";
import { InstrumentSymbol } from "../ui/InstrumentSymbol";
import { BrainInspection } from "./BrainInspection";
import "../styles/ricci-exhibit.css";

type Panel = "part" | "parts" | "study" | "brain" | null;
const parameters = () => new URLSearchParams(location.hash.slice(1));

export function ConceptStudio({
  heading,
  laboratory,
}: {
  heading: RefObject<HTMLHeadingElement | null>;
  laboratory: () => void;
}) {
  const [selection, setSelection] = useState(() =>
    readRicciSelection(location.hash),
  );
  const [inLab, setInLab] = useState(() => parameters().get("stage") === "lab");
  const [panel, setPanel] = useState<Panel>(() =>
    readRicciSelection(location.hash).id ? "part" : null,
  );
  const [motion, setMotion] = useState(false),
    [preview, setPreview] = useState(false);
  const [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false);
  const [variant, setVariant] = useState<TraceCase>("load"),
    [compare, setCompare] = useState(false);
  const [camera, setCamera] = useState<RicciCameraState>({
    yaw: 0,
    pitch: 0.035,
    scale: 1,
  });
  const [motionOptions, setMotionOptions] = useState(false);
  const [viewControlsHost, setViewControlsHost] = useState<HTMLDivElement | null>(null);
  useOutsideTap(motionOptions, ".ricci-transport, [data-detail-trigger]", () => setMotionOptions(false));
  const motionControl = useRef<HTMLButtonElement>(null);
  const root = useRef<HTMLElement>(null),
    origin = useRef<HTMLElement | SVGElement | null>(null);
  const current = tracePose(time, variant);
  const write = (params: URLSearchParams, push = false) =>
    history[push ? "pushState" : "replaceState"](
      { ...history.state, nisayon: true },
      "",
      `${location.pathname}${location.search}#${params}`,
    );

  useEffect(() => {
    const read = () => {
      if (parameters().get("view") !== "concepts") return;
      const next = readRicciSelection(location.hash);
      setSelection(next);
      setInLab(parameters().get("stage") === "lab");
      setPanel(next.id ? "part" : null);
    };
    window.addEventListener("popstate", read);
    window.addEventListener("hashchange", read);
    return () => {
      window.removeEventListener("popstate", read);
      window.removeEventListener("hashchange", read);
    };
  }, []);
  useEffect(() => {
    if (!playing) return;
    let raf = 0,
      last = 0;
    const tick = (now: number) => {
      if (document.hidden) {
        setPlaying(false);
        return;
      }
      if (last) setTime((t) => Math.min(12, t + (now - last) / 1000));
      last = now;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
  useEffect(() => {
    if (time >= 12) setPlaying(false);
  }, [time]);
  useEffect(() => {
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    const changed = () => {
      if (preference.matches) setPlaying(false);
    };
    preference.addEventListener("change", changed);
    return () => preference.removeEventListener("change", changed);
  }, []);

  const select = (
    id: RicciPartId,
    target: HTMLElement | SVGElement,
    instance?: string,
  ) => {
    origin.current = target;
    setPlaying(false);
    const next = new URLSearchParams(
      ricciSelectionHash(location.hash, id, instance).slice(1),
    );
    next.set("inspect", "part");
    write(next);
    setSelection({ id, issue: null, ...(instance ? { instance } : {}) });
    setPanel("part");
  };
  // Dismissal is deliberately independent of the animation clock and camera.
  // There is no second label state and no asynchronous history.back race.
  const dismissPart = () => {
    setSelection({ id: null, issue: null });
    setPanel(null);
    const next = new URLSearchParams(
      ricciSelectionHash(location.hash, null).slice(1),
    );
    next.delete("inspect");
    write(next);
  };
  const reset = () => {
    setPlaying(false);
    setTime(0);
    setPreview(false);
    dismissPart();
  };
  const openPanel = (next: "parts" | "study" | "brain", target: HTMLElement) => {
    origin.current = target;
    setPanel(next);
    setPlaying(false);
  };
  const closePanel = () => setPanel(selection.id ? "part" : null);
  const outside = () => {
    if (!root.current?.isConnected) return;
    if (panel === "part") dismissPart();
    else if (panel === "parts" || panel === "study" || panel === "brain") closePanel();
  };
  useOutsideTap(
    panel === "part",
    "canvas, [data-scene-detail], .ricci-callout, [data-ricci-inspect], [popover]",
    outside,
  );
  const dismissWithFocus = () => {
    dismissPart();
    const target = origin.current?.isConnected
      ? origin.current
      : root.current?.querySelector<HTMLElement>(".ricci-canvas");
    target?.focus({ preventScroll: true });
  };
  const toggleLab = () => {
    const next = !inLab;
    setInLab(next);
    const p = parameters();
    if (next) p.set("stage", "lab");
    else p.delete("stage");
    write(p);
  };
  const play = () => {
    setPreview(true);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setTime((t) => RICCI_TRACE.phases.find((p) => p.at > t)?.at ?? 0);
      return;
    }
    if (time >= 12) setTime(0);
    setPlaying((value) => !value);
  };

  return (
    <main
      ref={root}
      className="ricci-exhibit"
      id="research-content"
      data-stage={inLab ? "lab" : "black"}
      data-motion={motion}
      data-part-open={panel === "part"}
      data-brain-open={panel === "brain"}
      data-context-open={panel !== null}
      onKeyDown={(event) => {
        // The native camera disclosure owns the first Escape, before playback.
        if (event.key === "Escape" && root.current?.querySelector('.workspace-menu[aria-expanded="true"]')) return;
        if (event.key === "Escape" && motionOptions && panel === null) {
          event.preventDefault(); setMotionOptions(false); root.current?.querySelector<HTMLElement>(".ricci-options-toggle")?.focus();
        } else if (event.key === "Escape" && panel === "part") {
          event.preventDefault();
          dismissWithFocus();
        } else if (event.key === "Escape" && panel === null && motion) {
          event.preventDefault();
          setMotion(false);
          setPreview(false);
          setCompare(false);
          setMotionOptions(false);
          setPlaying(false);
          motionControl.current?.focus({ preventScroll: true });
        }
      }}
    >
      <header className="ricci-title">
        <h1 ref={heading} tabIndex={-1}>
          Ricci
        </h1>
      </header>
      <section
        className={`ricci-stage${compare ? " ricci-comparing" : ""}`}
        aria-label="Ricci exhibit"
      >
        <RicciScene
          selected={selection.id}
          instance={selection.instance}
          onSelect={select}
          onReset={reset}
          laboratory={inLab}
          time={time}
          variant={variant}
          motion={preview}
          cameraState={camera}
          onCamera={setCamera}
          inspectionOpen={panel === "part"}
          onCloseInspection={dismissWithFocus}
          onOutsideTap={outside}
          viewControlsHost={viewControlsHost}
          onWorkstation={() => {
            if (selection.id) dismissPart(); else setPanel(null);
            setMotion(true); setPreview(true); setMotionOptions(false); setPlaying(false);
            motionControl.current?.focus({ preventScroll: true });
          }}
          viewControlsActive={!motion && panel === null}
          onViewOpen={() => {
            setMotion(false);
            setMotionOptions(false);
            setPlaying(false);
            // Keep the authored pose and clock while changing the view.
            if (selection.id) dismissPart(); else setPanel(null);
          }}
        />
        {compare ? (
          <RicciScene
            selected={null}
            instance={undefined}
            onSelect={() => {}}
            onReset={() => {}}
            laboratory={inLab}
            time={time}
            variant={variant === "load" ? "slip" : "load"}
            motion={preview}
            cameraState={camera}
            onCamera={setCamera}
            controls={false}
          />
        ) : null}
        {preview ? (
          <div className="ricci-trace-caption">
            <span>
              {RICCI_TRACE.status} · {current.phase.label}
            </span>
            <small>
              {compare
                ? "Left: " +
                  (variant === "load"
                    ? "shifting load · Right: slipping foot"
                    : "slipping foot · Right: shifting load")
                : current.phase.contact}
            </small>
          </div>
        ) : null}
      </section>
      <nav className="ricci-stage-actions" aria-label="Ricci controls">
        <button
          type="button"
          data-ricci-inspect
          data-detail-trigger
          onClick={toggleLab}
          aria-pressed={inLab}
        >
          <InstrumentSymbol name="lab" />
          <span>{inLab ? "Black stage" : "Enter the Lab"}</span>
        </button>
        <button
          type="button"
          data-ricci-inspect
          data-detail-trigger
          ref={motionControl}
          aria-label="Motion study"
          aria-pressed={motion}
          onClick={() => {
            if (panel === "part") dismissPart(); else setPanel(null);
            const next = !motion;
            setMotion(next);
            setPreview(next);
            setCompare(false);
            setMotionOptions(false);
            setPlaying(false);
          }}
        >
          <InstrumentSymbol name="motion" />
          <span>Motion Study</span>
        </button>
        <div className="ricci-camera-access" ref={setViewControlsHost} />
        <button type="button" data-ricci-inspect data-detail-trigger aria-expanded={panel === "brain"}
          onClick={event => { if (panel === "brain") closePanel(); else { dismissPart(); setMotion(false); setCompare(false); setMotionOptions(false); openPanel("brain", event.currentTarget); } }}>
          <InstrumentSymbol name="brain" /><span>Brain 01</span>
        </button>
        <button
          type="button"
          data-ricci-inspect
          data-detail-trigger
          className="ricci-parts-access"
          aria-expanded={panel === "parts"}
          onClick={(event) =>
            panel === "parts"
              ? closePanel()
              : openPanel("parts", event.currentTarget)
          }
        >
          <InstrumentSymbol name="parts" />
          <span>Parts</span>
        </button>
      </nav>
      {motion && panel === null ? (
        <section
          className="ricci-transport"
          aria-label="Authored motion playback"
        >
          <p>Authored preview · not measured motion</p>
          <div className="ricci-time-controls">
            <button type="button" className="ricci-preview-play" aria-label={playing ? "Pause preview" : "Play preview"} onClick={play}><Icon name={playing ? "pause" : "play"}/></button>
            <label className="sr-only" htmlFor="ricci-preview-time">
              Preview time
            </label>
            <input
              className="scene-scrubber"
              style={{ "--progress": `${time / 12 * 100}%` } as CSSProperties}
              onPointerDown={() => setPlaying(false)}
              id="ricci-preview-time"
              type="range"
              min="0"
              max="12"
              step=".05"
              value={time}
              onChange={(event) => {
                setPlaying(false);
                setPreview(true);
                setTime(Number(event.currentTarget.value));
              }}
            />
            <output>{time.toFixed(1)} s</output>
            <button type="button" className="ricci-options-toggle" aria-label="Study options" aria-expanded={motionOptions} onClick={() => setMotionOptions(v => !v)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 17h16M9 3v8m6 2v8"/></svg></button>
          </div>
          {motionOptions ? <div className="ricci-motion-options"><nav aria-label="Preview contact moments">
            {RICCI_TRACE.phases.slice(0, 4).map((phase) => (
              <button
                key={phase.at}
                type="button"
                data-ricci-inspect
                onClick={(event) => {
                  setPlaying(false);
                  setPreview(true);
                  setTime(phase.at);
                  setMotionOptions(false);
                  select(phase.part, event.currentTarget);
                }}
              >
                {phase.label}
              </button>
            ))}
          </nav>
          <div className="ricci-study-actions">
            <button
              type="button"
              aria-pressed={compare}
              onClick={() => setCompare((value) => !value)}
            >
              {compare ? "Single view" : "Compare"}
            </button>
            <button
              type="button"
              data-detail-trigger
              onClick={(event) => openPanel("study", event.currentTarget)}
            >
              Study notes
            </button>
          </div></div> : null}
        </section>
      ) : null}
      {selection.issue ? (
        <div className="ricci-selection-error" role="status">
          {selection.issue}
          <button type="button" onClick={dismissPart}>
            Reset selection
          </button>
        </div>
      ) : null}
      {panel === "parts" ? (
        <SceneDetail
          title="Parts"
          kind="selector"
          exclude="canvas"
          onClose={closePanel}
        >
          <nav className="ricci-parts" aria-label="Ricci part list">
            <ol>
              {RICCI_CATALOG.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    data-list-part={item.id}
                    aria-pressed={selection.id === item.id}
                    onClick={(event) => select(item.id, event.currentTarget)}
                  >
                    {item.label}
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        </SceneDetail>
      ) : null}
      {panel === "study" ? (
        <SceneDetail
          title="Motion study"
          returnFocus={motionControl.current}
          exclude="canvas"
          caption="Authored preview · no measured outcome"
          onClose={closePanel}
        >
          <dl className="ricci-part-copy">
            <div>
              <dt>Authored motion · {RICCI_TRACE.revision}</dt>
              <dd>
                The poses and contacts illustrate the proposed setup. No
                computed trial or recovery outcome is encoded in this authored study.
              </dd>
            </div>
            <div>
              <dt>What Ricci could observe</dt>
              <dd>{RICCI_TRACE.observations}</dd>
            </div>
            <div>
              <dt>What a simulator would know</dt>
              <dd>
                Payload offset, friction and actual contact forces belong to
                evaluator truth. They must not be exposed as controller inputs.
              </dd>
            </div>
            <div>
              <dt>Proposed comparison</dt>
              <dd>{RICCI_TRACE.comparison}</dd>
            </div>
          </dl>
          <label className="ricci-study-choice">
            Preview scenario
            <select
              value={variant}
              onChange={(event) =>
                setVariant(event.currentTarget.value as TraceCase)
              }
            >
              <option value="load">Shifting tray load</option>
              <option value="slip">Slipping stance foot</option>
            </select>
          </label>
          <a
            href="/media/ricci/study-sources.txt"
            target="_blank"
            rel="noopener"
          >
            Study inputs and source boundary
          </a>
          <button
            type="button"
            className="ricci-text-control"
            onClick={laboratory}
          >
            Inspect the retained Panda experiment
          </button>
        </SceneDetail>
      ) : null}
      {panel === "brain" ? <BrainInspection origin={origin.current instanceof HTMLElement ? origin.current : null} onClose={closePanel}/> : null}
    </main>
  );
}
