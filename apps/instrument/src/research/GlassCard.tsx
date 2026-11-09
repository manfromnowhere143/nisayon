import { useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";

/** Native modal semantics keep the underlying experiment still and inert.
 * Only opacity and transform animate; the optical layer is never animated. */
export function GlassCard({
  title,
  eyebrow,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const id = useId();
  const [closing, setClosing] = useState(false);
  const pendingClose = useRef(false);
  const finishedClose = useRef(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latestClose = useRef(onClose);
  latestClose.current = onClose;
  const finishClose = () => {
    if (finishedClose.current) return;
    finishedClose.current = true;
    clearTimeout(closeTimer.current);
    latestClose.current();
  };
  const requestClose = () => {
    if (pendingClose.current) return;
    pendingClose.current = true;
    if (!window.matchMedia("(prefers-reduced-motion: no-preference)").matches || document.hidden) {
      finishClose();
      return;
    }
    // Keep the native modal and its scrim together until both have faded.
    // The deadline also closes if the browser cancels/suppresses animation.
    setClosing(true);
    closeTimer.current = setTimeout(finishClose, 240);
  };
  useLayoutEffect(() => {
    const node = dialog.current!;
    const origin =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    if (typeof node.showModal === "function") node.showModal();
    else node.setAttribute("open", "");
    heading.current?.focus({ preventScroll: true });
    return () => {
      clearTimeout(closeTimer.current);
      if (typeof node.close === "function") node.close();
      origin?.isConnected && origin.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className={`research-glass-card${wide ? " is-wide" : ""}`}
      data-closing={closing || undefined}
      aria-labelledby={id}
      onAnimationEnd={(event) => {
        if (pendingClose.current && event.target === dialog.current && event.animationName === "nisayon-card-leave") finishClose();
      }}
      onKeyDownCapture={(event) => {
        if (pendingClose.current) { event.preventDefault(); event.stopPropagation(); }
      }}
      onCancel={(event) => {
        event.preventDefault();
        requestClose();
      }}
      onClick={(event) => {
        if (event.target !== dialog.current) return;
        const rect = dialog.current.getBoundingClientRect();
        if (
          event.clientX < rect.left ||
          event.clientX > rect.right ||
          event.clientY < rect.top ||
          event.clientY > rect.bottom
        )
          requestClose();
      }}
    >
      <header className="glass-card-header">
        <div>
          {eyebrow ? <p className="research-micro">{eyebrow}</p> : null}
          <h2 id={id} ref={heading} tabIndex={-1}>
            {title}
          </h2>
        </div>
        <button
          className="glass-card-close"
          aria-label={`Close ${title}`}
          onClick={requestClose}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m7 7 10 10M17 7 7 17" />
          </svg>
        </button>
      </header>
      <div className="glass-card-content">{children}</div>
    </dialog>
  );
}
