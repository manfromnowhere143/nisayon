import { focusReturnTarget } from "./focusPresentation";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  type ReactNode,
} from "react";
import { EvidenceScroll } from "./EvidenceFlow";
import { InstrumentSymbol } from "./InstrumentSymbol";
import { useOutsideTap } from "./useOutsideTap";
import "../styles/scene-detail.css";

/** Context belongs beside the scene. A non-modal dialog keeps orbit available;
 * its own reading region scrolls, while focus and qualified taps dismiss it. */
export function SceneDetail({
  title,
  children,
  onClose,
  kind = "reading",
  caption,
  exclude = "",
  returnFocus,
  className = "",
  floating = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  kind?: "reading" | "selector" | "moment";
  caption?: string | undefined;
  exclude?: string;
  returnFocus?: HTMLElement | null;
  className?: string;
  floating?: boolean;
}) {
  const id = useId(),
    heading = useRef<HTMLHeadingElement>(null);
  const origin = useRef<HTMLElement | null>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useOutsideTap(
    true,
    `[data-scene-detail], [data-detail-trigger], .scene-playback, [popover]${exclude ? ", " + exclude : ""}`,
    () => close.current(),
  );
  useLayoutEffect(() => {
    origin.current = returnFocus ?? focusReturnTarget(document.activeElement);
    heading.current?.focus({ preventScroll: true });
  }, [title, returnFocus]);
  useLayoutEffect(
    () => () => {
      if (origin.current?.isConnected)
        origin.current.focus({ preventScroll: true });
    },
    [],
  );
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (
        event.key !== "Escape" ||
        event.defaultPrevented ||
        (event.target instanceof Element && !!event.target.closest("[popover]"))
      )
        return;
      event.preventDefault();
      close.current();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, []);
  return (
    <dialog
      open
      data-scene-detail
      className={`scene-detail scene-detail-${kind}${floating ? " scene-detail-floating" : ""} ${className}`}
      aria-labelledby={id}
      onCancel={(event) => {
        event.preventDefault();
        close.current();
      }}
    >
      <header className="scene-detail-heading">
        <div>
          <h2 id={id} ref={heading} tabIndex={-1}>
            {title}
          </h2>
          {caption ? <p>{caption}</p> : null}
        </div>
        <button type="button" aria-label={`Close ${title}`} onClick={onClose}>
          <InstrumentSymbol name="close" />
        </button>
      </header>
      <div className="scene-detail-content">
        <EvidenceScroll>{children}</EvidenceScroll>
      </div>
    </dialog>
  );
}
