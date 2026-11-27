import { useId, useLayoutEffect, useRef, type ReactNode } from "react";
import { focusReturnTarget } from "../ui/focusPresentation";

/** A reading within the Library canvas. The stage and view controls stay usable. */
export function LibraryReading({ title, eyebrow, children, onClose }: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const id = useId();
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useLayoutEffect(() => {
    const node = dialog.current!;
    const origin = focusReturnTarget(document.activeElement);
    heading.current?.focus({ preventScroll: true });
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      // Let an open workspace popover consume its own Escape first.
      if (document.querySelector('.workspace-menu[aria-expanded="true"]') ||
        (event.target instanceof Element && event.target.closest("[popover]"))) return;
      event.preventDefault();
      close.current();
    };
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("keydown", escape);
      const active = document.activeElement;
      if (active === document.body || node.contains(active)) queueMicrotask(() => {
        // React must first remove hidden/inert from the restored drawing.
        // A newly opened reading or deliberately focused control owns focus.
        const current = document.activeElement;
        if (origin?.isConnected && !origin.closest("[hidden], [inert]") &&
          (current === document.body || current === active || node.contains(current))) origin.focus({ preventScroll: true });
      });
    };
  }, []);
  return <dialog open ref={dialog} className="library-reading" aria-labelledby={id} onCancel={event => { event.preventDefault(); onClose(); }}>
    <header className="library-reading-header">
      <div>
        {eyebrow ? <p className="research-micro">{eyebrow}</p> : null}
        <h2 id={id} ref={heading} tabIndex={-1}>{title}</h2>
      </div>
      <button className="library-reading-close" aria-label={`Close ${title}`} onClick={onClose}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" /></svg>
      </button>
    </header>
    <div className="library-reading-content">{children}</div>
  </dialog>;
}
