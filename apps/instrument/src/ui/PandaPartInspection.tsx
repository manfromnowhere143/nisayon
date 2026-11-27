import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { BodyAnnotation } from "../scene/bodyAnnotation";
import type { SpatialPose } from "../model/spatial";
import { bodyLabel } from "../model/spatial";
import { EvidenceScroll } from "./EvidenceFlow";
import { InstrumentSymbol } from "./InstrumentSymbol";
import { partInspectionPlacement } from "./partInspectionPlacement";
import "../styles/part-inspection.css";

export function PandaPartInspection({ name, body, pose, time, phase, anchor, unavailable = false, expanded, onExpanded, onClose, children }: {
  name: string; body: number; pose: SpatialPose | null; time: number | null; phase: "before" | "after";
  anchor: BodyAnnotation | null; expanded: boolean; onExpanded: (value: boolean) => void;
  unavailable?: boolean;
  onClose: () => void; children: ReactNode;
}) {
  const id = useId(), root = useRef<HTMLDivElement>(null), card = useRef<HTMLDialogElement>(null), title = useRef<HTMLHeadingElement>(null);
  const [layout, setLayout] = useState({ width: 390, height: 700, left: 6, right: 384, top: 94, bottom: 590 });
  const [height, setHeight] = useState(158);
  const [measured, setMeasured] = useState(false);
  const bound = !unavailable && anchor?.bodyId === body ? anchor : null;
  const ready = measured && (!!bound || unavailable);
  const close = useRef(onClose); close.current = onClose;
  useLayoutEffect(() => {
    const node = root.current;
    if (!node) return;
    const measure = () => {
      const rect = node.getBoundingClientRect(), width = rect.width || innerWidth, height = rect.height || innerHeight;
      const vv = window.visualViewport;
      const left = Math.max(6, (vv?.offsetLeft ?? 0) - rect.left + 6);
      const right = Math.min(width - 6, (vv?.offsetLeft ?? 0) + (vv?.width ?? width) - rect.left - 6);
      let top = Math.max(70, (vv?.offsetTop ?? 0) - rect.top + 8), bottom = Math.min(height - 94, (vv?.offsetTop ?? 0) + (vv?.height ?? height) - rect.top - 12);
      const playback = document.querySelector<HTMLElement>(".scene-playback")?.getBoundingClientRect();
      if (playback && playback.height && playback.top > rect.top) bottom = Math.min(bottom, playback.top - rect.top - 16);
      const header = document.querySelector<HTMLElement>(".identity")?.getBoundingClientRect();
      if (header?.height) top = Math.max(top, header.bottom - rect.top + 8);
      setLayout(previous => previous.width === width && previous.height === height && previous.top === top && previous.bottom === bottom && previous.left === left && previous.right === right ? previous : { width, height, left, right, top, bottom });
      setMeasured(true);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    const playback = document.querySelector(".scene-playback"); if (playback) observer.observe(playback);
    const header = document.querySelector(".identity"); if (header) observer.observe(header);
    window.visualViewport?.addEventListener("resize", measure);
    window.visualViewport?.addEventListener("scroll", measure);
    measure();
    return () => { observer.disconnect(); window.visualViewport?.removeEventListener("resize", measure); window.visualViewport?.removeEventListener("scroll", measure); };
  }, []);
  useLayoutEffect(() => {
    const node = card.current; if (!node) return;
    const measure = () => setHeight(node.getBoundingClientRect().height || (expanded ? 380 : 158));
    const observer = new ResizeObserver(measure); observer.observe(node); measure();
    return () => observer.disconnect();
  }, [expanded, name]);
  useLayoutEffect(() => { if (ready) title.current?.focus({ preventScroll: true }); }, [name, ready]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented || (event.target instanceof Element && event.target.closest("[popover]"))) return;
      event.preventDefault(); close.current();
    };
    document.addEventListener("keydown", escape); return () => document.removeEventListener("keydown", escape);
  }, []);
  const frame = bound ?? { x: layout.width / 2, y: layout.height * .54, width: layout.width, height: layout.height, visible: false, body: [] };
  const width = Math.max(0, Math.min(expanded ? 300 : 248, layout.right - layout.left - 20));
  const maxHeight = Math.max(0, Math.min(460, layout.bottom - layout.top - 20));
  const compact = partInspectionPlacement(frame, { width, height: Math.min(158, maxHeight) }, layout);
  const side = compact.left + width / 2 > (layout.left + layout.right) / 2 ? 1 : -1;
  const placed = partInspectionPlacement(frame, { width, height: Math.min(height, maxHeight) }, layout, side);
  return <div ref={root} className="panda-part-inspection" data-part={name} data-ready={ready} inert={!ready} aria-hidden={!ready}>
    {bound?.visible ? <svg className="panda-part-leader" aria-hidden="true"><path d={`M${bound.x},${bound.y} L${placed.bend.x},${placed.bend.y} L${placed.end.x},${placed.end.y}`} /><circle cx={bound.x} cy={bound.y} r="2" /></svg> : null}
    <dialog open ref={card} className="panda-part-callout" data-expanded={expanded} aria-labelledby={id} style={{ left: placed.left, top: placed.top, width, maxHeight }}>
      <header><h2 id={id} ref={title} tabIndex={-1}>{bodyLabel(name)}</h2><button type="button" className="panda-part-close" aria-label="Close part inspection" onClick={onClose}><InstrumentSymbol name="close" /></button></header>
      <div className="panda-part-content" id={`${id}-details`}>
        {expanded ? <EvidenceScroll>{children}</EvidenceScroll> : <>
          {pose ? <dl className="panda-part-coordinates">{pose.position.map((value, axis) => <div key={axis}><dt>{["X", "Y", "Z"][axis]}</dt><dd>{value.toFixed(6)}</dd></div>)}</dl> : <p className="panda-part-unavailable">Body configuration unavailable.</p>}
          <p className="panda-part-basis">Body origin · world frame · m</p>
        </>}
        {bound && !bound.visible ? <p className="panda-part-unavailable">Outside the view · turn to locate</p> : null}
      </div>
      <footer><span>Recorded · {phase}<small>{time === null ? "Time unavailable" : `${time.toFixed(3)} s`}</small></span><button type="button" aria-label={expanded ? "Show fewer part details" : "Show selected part details"} aria-expanded={expanded} aria-controls={`${id}-details`} onClick={() => onExpanded(!expanded)}>{expanded ? "Less" : "Details"}</button></footer>
    </dialog>
  </div>;
}
