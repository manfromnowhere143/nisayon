import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  createRicciRenderer,
  type RicciAnchor,
  type RicciRenderer,
  type RicciCameraState,
} from "./ricciRenderer";
import { RicciSections } from "./RicciSections";
import type { RicciPartId } from "./ricciCatalog";
import { WorkspaceMenu } from "../ui/WorkspaceMenu";
import { Icon } from "../ui/Icon";
import { RicciAnnotation } from "./RicciAnnotation";
import type { TraceCase } from "./ricciTrace";
import type { RicciPick } from "./ricciGeometry";

export function RicciScene({
  selected,
  instance,
  onSelect,
  onReset,
  laboratory = false,
  time = 0,
  variant = "load",
  motion = false,
  onInspect,
  inspectionOpen = false,
  onCloseInspection,
  onOutsideTap,
  controls = true,
  cameraState,
  onCamera,
  viewControlsHost,
  viewControlsActive = true,
  onViewOpen,
  onWorkstation,
}: {
  viewControlsHost?: HTMLElement | null;
  viewControlsActive?: boolean;
  onViewOpen?: () => void;
  onWorkstation?: () => void;
  cameraState?: RicciCameraState;
  onCamera?: (state: RicciCameraState) => void;
  laboratory?: boolean;
  time?: number;
  variant?: TraceCase;
  motion?: boolean;
  controls?: boolean;
  onInspect?: (target: HTMLElement) => void;
  inspectionOpen?: boolean;
  onCloseInspection?: () => void;
  onOutsideTap?: () => void;
  selected: RicciPartId | null;
  instance: string | undefined;
  onSelect: (
    id: RicciPartId,
    target: HTMLElement | SVGElement,
    instance?: string,
  ) => void;
  onReset: () => void;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null),
    handle = useRef<RicciRenderer | null>(null);
  const [attempt, retry] = useState(0),
    [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [prepared, setPrepared] = useState(0);
  const [anchor, setAnchor] = useState<RicciAnchor | null>(null);
  const [failure, setFailure] = useState("");
  const retryFocus = useRef(false);
  const pickRef = useRef(onSelect);
  pickRef.current = onSelect;
  const cameraRef = useRef(onCamera);
  cameraRef.current = onCamera;
  const outsideRef = useRef(onOutsideTap);
  outsideRef.current = onOutsideTap;
  const workstationRef = useRef(onWorkstation);
  workstationRef.current = onWorkstation;
  const latest = useRef({
    selected,
    instance,
    laboratory,
    time,
    variant,
    motion,
    cameraState,
  });
  latest.current = {
    selected,
    instance,
    laboratory,
    time,
    variant,
    motion,
    cameraState,
  };
  useEffect(() => {
    const node = canvas.current!;
    let live = true;
    let paint = 0,
      timer: ReturnType<typeof setTimeout> | undefined;
    const initialize = () => {
      if (!live) return;
      setStatus("loading");
      setPrepared(0);
      try {
        handle.current = createRicciRenderer(
          node,
          {
            pick: (pick: RicciPick) =>
              pickRef.current(pick.id, node, pick.instance),
            miss: () => outsideRef.current?.(),
            workstation: () => workstationRef.current?.(),
            camera: (state) => cameraRef.current?.(state),
            anchor: (next) => {
              if (live)
                setAnchor((old) =>
                  JSON.stringify(old) === JSON.stringify(next) ? old : next,
                );
            },
            progress: completed => { if (live) setPrepared(completed); },
            ready: () => {
              if (live) setStatus("ready");
            },
            failure: (message) => {
              if (live) {
                setFailure(message);
                setStatus("failed");
              }
            },
          },
          {
            id: latest.current.selected,
            ...(latest.current.instance
              ? { instance: latest.current.instance }
              : {}),
            ...(frame.current ? { frame: frame.current } : {}),
            ...(latest.current.cameraState
              ? { camera: latest.current.cameraState }
              : {}),
            laboratory: latest.current.laboratory,
            time: latest.current.time,
            variant: latest.current.variant,
            motion: latest.current.motion,
          },
        );
      } catch (error) {
        setFailure(
          error instanceof Error
            ? error.message
            : "Graphics initialization failed",
        );
        setStatus("failed");
      }
    };
    // Commit a usable interface before allocating GPU resources. The timer
    // after rAF gives that commit a paint; hidden tabs do not depend on rAF.
    // Strict Mode can cancel its rehearsal before creating a graphics context.
    if (document.hidden) timer = setTimeout(initialize, 0);
    else
      paint = requestAnimationFrame(() => {
        timer = setTimeout(initialize, 0);
      });
    return () => {
      live = false;
      cancelAnimationFrame(paint);
      clearTimeout(timer);
      handle.current?.dispose();
      handle.current = null;
    };
  }, [attempt]);
  useLayoutEffect(() => {
    handle.current?.select(selected, instance);
  }, [selected, instance, attempt]);
  useEffect(() => {
    handle.current?.laboratory?.(laboratory);
  }, [laboratory, attempt]);
  useEffect(() => {
    handle.current?.trace?.(time, variant, motion);
  }, [time, variant, motion, attempt]);
  useEffect(() => {
    if (cameraState) handle.current?.camera?.(cameraState);
  }, [cameraState, attempt]);
  useEffect(() => {
    if (status === "ready" && retryFocus.current) {
      retryFocus.current = false;
      canvas.current?.focus({ preventScroll: true });
    }
  }, [status]);
  return (
    <div
      className="ricci-render"
      data-renderer={status}
      data-selection={Boolean(selected)}
    >
      <div ref={frame} className="ricci-frame">
        {status === "failed" ? (
          <div
            className="ricci-render-failure"
            data-ricci-inspect
            role="status"
          >
            <h2>3D view interrupted</h2>
            <p>{failure}</p>
            <button
              className="ricci-text-control"
              onClick={() => {
                retryFocus.current = true;
                retry((value) => value + 1);
              }}
            >
              Retry 3D view
            </button>
            <p>All part descriptions remain in the section list.</p>
            <details>
              <summary>Accessible section diagram</summary>
              <RicciSections selected={selected} onSelect={onSelect} />
              <p id="ricci-diagram-note">
                Section index, not a substitute robot rendering.
              </p>
            </details>
          </div>
        ) : null}
      </div>
      <canvas
        key={attempt}
        ref={canvas}
        className="ricci-canvas"
        data-focus-control
        tabIndex={status === "failed" ? -1 : 0}
        aria-hidden={status === "failed" || undefined}
        role="img"
        aria-label="Ricci, proposed 3D architecture. Select a visible part. Drag to rotate; pinch to zoom; arrow keys turn or zoom; Home restores the front. In the laboratory, Enter opens Motion Study. Every part is also in the section list."
      />
      {status !== "failed" ? <div className="ricci-preparation" data-ready={status === "ready"} aria-hidden={status === "ready"}>
        <progress max={3} value={prepared} aria-label="3D preparation" aria-valuetext={`${prepared} of 3 preparation stages complete`} />
        <span aria-hidden="true">{Math.round(prepared / 3 * 100)}%</span>
      </div> : null}
      {selected && controls ? (
        <RicciAnnotation
          id={selected}
          instance={instance}
          anchor={
            anchor?.part === selected &&
            anchor.instance ===
              (instance ??
                (selected === "ankle_foot" ? "ankle_foot_left" : "")) &&
            status === "ready"
              ? anchor
              : null
          }
          unavailable={status === "failed"}
          sceneFrame={frame}
          open={inspectionOpen}
          motion={motion}
          onOpen={(target) => onInspect?.(target)}
          onClose={() => onCloseInspection?.()}
        />
      ) : null}
      {controls && viewControlsHost ? createPortal(
        <nav className="ricci-view-controls" aria-label="Ricci view controls">
          <WorkspaceMenu label="View" title="View" symbol="view" placement="above-center" active={viewControlsActive} onOpen={onViewOpen} popoverClassName="ricci-view-popover" closeOnSelect={false}>
            <div className="ricci-view-options">
              <div className="ricci-view-presets" role="group" aria-label="Camera angles">
              <button
                type="button"
                onClick={() => handle.current?.view("front")}
              >
                Front
              </button>
              <button
                type="button"
                onClick={() => handle.current?.view("oblique")}
              >
                Three-quarter
              </button>
              <button
                type="button"
                title="Proposed rear geometry"
                onClick={() => handle.current?.view("rear")}
              >
                Rear
              </button>
              </div>
              <div className="ricci-view-adjust" role="group" aria-label="Adjust camera">
              <button
                type="button"
                aria-label="Turn left" title="Turn left"
                onClick={() => handle.current?.orbit(-0.18)}
              >
                <Icon name="prev" />
              </button>
              <button
                type="button"
                aria-label="Zoom out from Ricci" title="Zoom out"
                onClick={() => handle.current?.zoom(-0.06)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" /></svg>
              </button>
              <button
                type="button" aria-label="Reset view" title="Reset view"
                onClick={() => {
                  handle.current?.reset();
                  onReset();
                }}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8a8 8 0 1 1-1 8M5 3v5h5" /></svg>
              </button>
              <button type="button" aria-label="Zoom in on Ricci" title="Zoom in" onClick={() => handle.current?.zoom(0.06)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M12 5v14" /></svg>
              </button>
              <button type="button" aria-label="Turn right" title="Turn right" onClick={() => handle.current?.orbit(0.18)}><Icon name="next" /></button>
              </div>
            </div>
          </WorkspaceMenu>
          <span aria-hidden="true">View</span>
        </nav>, viewControlsHost
      ) : null}
    </div>
  );
}
