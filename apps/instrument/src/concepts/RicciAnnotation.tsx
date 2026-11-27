import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import {
  RICCI_CATALOG,
  RICCI_PACKAGES,
  type RicciPartId,
} from "./ricciCatalog";
import {
  placeRicciAnnotation,
  type AnnotationAnchor,
} from "./annotationPlacement";
import { InstrumentSymbol } from "../ui/InstrumentSymbol";

/** One object detail, from the first fact through the complete retained text.
 * Narrow scenes reserve a detail pocket before selection, so disclosure never
 * changes the orbit camera or covers the robot. */
export function RicciAnnotation({
  id,
  instance,
  anchor,
  unavailable,
  open,
  motion,
  sceneFrame,
  onClose,
}: {
  id: RicciPartId;
  instance: string | undefined;
  anchor: AnnotationAnchor | null;
  unavailable: boolean;
  open: boolean;
  motion: boolean;
  sceneFrame?: RefObject<HTMLDivElement | null>;
  onOpen?: (target: HTMLElement) => void;
  onClose: () => void;
}) {
  const root = useRef<HTMLDivElement>(null),
    card = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null),
    label = useId();
  const [viewport, setViewport] = useState({
    width: 320,
    height: 600,
    frameWidth: 320,
    frameHeight: 600,
  });
  const [height, setHeight] = useState(132),
    [expanded, setExpanded] = useState(false);
  const part = RICCI_CATALOG.find((value) => value.id === id)!,
    spec = RICCI_PACKAGES[id];
  useLayoutEffect(() => {
    const node = root.current;
    if (!node) return;
    const measure = () =>
      setViewport({
        width: node.clientWidth,
        height: node.clientHeight,
        frameWidth: sceneFrame?.current?.clientWidth ?? node.clientWidth,
        frameHeight: sceneFrame?.current?.clientHeight ?? node.clientHeight,
      });
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    if (sceneFrame?.current) observer.observe(sceneFrame.current);
    measure();
    return () => observer.disconnect();
  }, [sceneFrame]);
  useLayoutEffect(() => {
    setExpanded(false);
  }, [id, instance]);
  useLayoutEffect(() => {
    if (open && (anchor || unavailable))
      title.current?.focus({ preventScroll: true });
  }, [open, id, instance, Boolean(anchor), unavailable]);
  const frame = anchor ?? {
    width: viewport.frameWidth,
    height: viewport.frameHeight,
    x: viewport.frameWidth / 2,
    y: viewport.frameHeight / 2,
    visible: false,
    body: [],
  };
  const sidePocket = viewport.width > frame.width + 100;
  const lowerPocket = viewport.height > frame.height + 80;
  const pocket = sidePocket || lowerPocket;
  const width = sidePocket
    ? viewport.width - frame.width - 28
    : lowerPocket
      ? Math.min(340, viewport.width - 32)
      : Math.min(expanded ? 300 : 208, viewport.width - 24);
  const maxHeight = sidePocket
    ? viewport.height - 32
    : lowerPocket
      ? viewport.height - frame.height - 24
      : Math.min(400, viewport.height - 24);
  useLayoutEffect(() => {
    const node = card.current;
    if (!node || !open) return;
    const measure = () => setHeight(node.getBoundingClientRect().height || 132);
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    measure();
    return () => observer.disconnect();
  }, [open, expanded, id, width, maxHeight]);
  const target = { ...frame, ...(frame.target ?? {}) };
  const compact = placeRicciAnnotation(target, { width, height: 132 });
  const side = compact.left + width / 2 > frame.width / 2 ? 1 : -1;
  const placed = placeRicciAnnotation(
    target,
    { width, height: Math.min(height, maxHeight) },
    [],
    side,
  );
  const position = sidePocket
    ? { left: frame.width + 12, top: 16 }
    : lowerPocket
      ? { left: (viewport.width - width) / 2, top: frame.height + 12 }
      : unavailable
        ? { left: 10, top: 10 }
        : { left: placed.left, top: placed.top };
  const dimension = spec.envelope.split(" · ")[0]!;
  const fact = /^\d/.test(dimension)
    ? dimension.replace(/ [LHWD]$/, "") + (/mm/.test(dimension) ? "" : " mm")
    : "Envelope unresolved";
  const dimensionName = / L$/.test(dimension)
    ? "Length"
    : / H$/.test(dimension)
      ? "Height"
      : / W$/.test(dimension)
        ? "Width"
        : / D$/.test(dimension)
          ? "Depth"
          : "Envelope";
  return (
    <div
      ref={root}
      className="ricci-annotation"
      data-ready={Boolean(anchor) || unavailable}
      data-part={id}
      data-pocket={sidePocket ? "side" : lowerPocket ? "below" : "anchored"}
    >
      {open && frame.visible && !pocket ? (
        <svg
          className="ricci-leader"
          width="100%"
          height="100%"
          aria-hidden="true"
        >
          <path
            d={`M${frame.x},${frame.y} L${placed.bend.x},${placed.bend.y} L${placed.end.x},${placed.end.y}`}
          />
          <circle cx={frame.x} cy={frame.y} r="2" />
        </svg>
      ) : null}
      {open ? (
        <dialog
          open
          ref={card}
          className="ricci-callout"
          data-expanded={expanded}
          aria-labelledby={label}
          style={{
            ...position,
            width,
            maxHeight: Math.max(96, maxHeight),
          }}
        >
          <header>
            <h2 id={label} ref={title} tabIndex={-1}>
              {part.shortLabel}
              {instance?.endsWith("left") ? (
                <small>Left</small>
              ) : instance?.endsWith("right") ? (
                <small>Right</small>
              ) : null}
            </h2>
            <button
              type="button"
              className="ricci-close"
              onClick={onClose}
              aria-label="Close part inspection"
            >
              <InstrumentSymbol name="close" />
            </button>
          </header>
          <div className="ricci-callout-scroll" id={`${label}-content`}>
            <p className="ricci-callout-fact">
              {fact}
              <small>{dimensionName} · proposed</small>
            </p>
            {expanded ? (
              <div className="ricci-callout-detail">
                <dl className="ricci-part-copy">
                  <div>
                    <dt>Proposed materials</dt>
                    <dd>{spec.material}</dd>
                  </div>
                  <div>
                    <dt>Purpose</dt>
                    <dd>{part.purpose}</dd>
                  </div>
                  <div>
                    <dt>Study envelope</dt>
                    <dd>{spec.envelope}</dd>
                  </div>
                  <div>
                    <dt>What is proposed</dt>
                    <dd>{part.proposal}</dd>
                  </div>
                  <div>
                    <dt>What would justify it</dt>
                    <dd>{part.observation}</dd>
                  </div>
                </dl>
                {id === "ankle_foot" && !motion ? (
                  <p className="ricci-reveal-label">
                    Sole layer separated for inspection.
                  </p>
                ) : null}
                <p className="ricci-part-limit">{part.limit}</p>
                <p className="ricci-part-source">
                  Rev A · R01 ·{" "}
                  <a
                    href="/media/ricci/study-sources.txt"
                    target="_blank"
                    rel="noopener"
                  >
                    Source boundary
                  </a>
                </p>
              </div>
            ) : null}
            {anchor && !frame.visible ? (
              <p className="ricci-occluded">Out of sight · turn to locate</p>
            ) : null}
          </div>
          <footer>
            <span>Proposed · unmeasured</span>
            <button
              type="button"
              aria-expanded={expanded}
              aria-controls={`${label}-content`}
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? "Less" : "Details"}
            </button>
          </footer>
        </dialog>
      ) : null}
    </div>
  );
}
