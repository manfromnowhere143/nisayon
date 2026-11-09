import { createContext, useContext, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { FixedEvidenceLayout, useDocumentEvidence } from "./useDocumentEvidence";

const FlowContext = createContext(false);
export const EvidenceIdentity = createContext("");
export const useEvidenceFlow = () => useContext(FlowContext);
const GAP = 32;

// The browser fragments text at actual line boundaries. A page is one column,
// not a guessed number of rows. Changing page is instantaneous; no scroll or
// translate animation is used. The same DOM and local form state survive reflow.
export function columnCount(contentWidth: number, width: number, gap = GAP): number {
  return width > 0 ? Math.max(1, Math.ceil((contentWidth + gap - 1) / (width + gap))) : 1;
}
export function columnAt(left: number, width: number, count: number, gap = GAP): number {
  return Math.max(0, Math.min(count - 1, Math.floor((left + 1) / (width + gap))));
}

export function EvidenceFlow({ children, label, identity = label }: { children: ReactNode; label: string; identity?: string }) {
  const nested = useEvidenceFlow();
  const source = useContext(EvidenceIdentity);
  return nested ? <>{children}</> : <Flow label={label} identity={`${source}:${identity}`}>{children}</Flow>;
}

function Flow({ children, label, identity }: { children: ReactNode; label: string; identity: string }) {
  const fixed = useContext(FixedEvidenceLayout);
  const documentLayout = useDocumentEvidence();
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const anchor = useRef<Element | null>(null);
  const current = useRef({ page: 0, pages: 1, width: 0, height: 0 });
  const [layout, setLayout] = useState(current.current);
  const [full, setFull] = useState(false);
  const [oversize, setOversize] = useState(false);
  const opener = useRef<HTMLElement | null>(null);
  const previousIdentity = useRef(identity);
  const measureNow = useRef<() => void>(() => {});

  const captureAnchor = (page: number) => {
    const node = content.current;
    if (!node) return;
    const base = node.getBoundingClientRect().left;
    const { width, pages } = current.current;
    anchor.current = Array.from(node.querySelectorAll("h2,h3,h4,p,dt,button,summary,a,svg")).find(element =>
      Array.from(element.getClientRects()).some(rect => rect.width > 0 && columnAt(rect.left - base, width, pages) === page),
    ) ?? null;
  };
  const go = (requested: number) => {
    const page = Number.isFinite(requested) ? Math.max(0, Math.min(current.current.pages - 1, Math.trunc(requested))) : current.current.page;
    current.current = { ...current.current, page };
    captureAnchor(page);
    setLayout(current.current);
  };

  useLayoutEffect(() => {
    if ((full && !fixed) || documentLayout) return;
    const box = viewport.current, node = content.current;
    if (!box || !node) return;
    let raf = 0, cancelled = false;
    const measure = () => {
      raf = 0;
      const width = box.clientWidth, height = box.clientHeight;
      // Hidden panels must not invalidate their reading position or the scene.
      if (width <= 0) return;
      if (height <= 0) { current.current = { ...current.current, height: 0 }; setOversize(true); return; }
      const pages = columnCount(node.scrollWidth, width);
      const previous = current.current;
      let page = Math.min(previous.page, pages - 1);
      if (anchor.current && (!anchor.current.isConnected || !node.contains(anchor.current))) anchor.current = null;
      if (anchor.current?.isConnected && node.contains(anchor.current)) {
        const base = node.getBoundingClientRect().left;
        const rect = anchor.current.getClientRects()[0];
        if (rect) page = columnAt(rect.left - base, width, pages);
      }
      const changed = width !== previous.width || height !== previous.height || pages !== previous.pages;
      // Content can grow without changing the viewport or the column count.
      // Unfragmentable figures receive a full-document view instead of being
      // clipped, including after a disclosure or selected record changes.
      const tooTall = height < 100 || Array.from(node.querySelectorAll("svg,table,img,.trace-group,.physical-history,[data-keep-together]")).some(element =>
        Array.from(element.getClientRects()).some(rect => rect.height > height + 1),
      );
      setOversize(tooTall);
      if (changed || page !== previous.page) {
        current.current = { width, height, pages, page };
        setLayout(current.current);
      }
      if (!anchor.current) captureAnchor(page);
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };
    measureNow.current = measure;
    const resize = new ResizeObserver(schedule);
    resize.observe(box);
    const mutation = new MutationObserver(schedule);
    mutation.observe(node, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["open", "hidden"] });
    node.addEventListener("load", schedule, true);
    measure();
    void document.fonts?.ready.then(() => { if (!cancelled) schedule(); });
    return () => {
      cancelled = true;
      resize.disconnect(); mutation.disconnect();
      node.removeEventListener("load", schedule, true);
      if (raf) cancelAnimationFrame(raf);
      measureNow.current = () => {};
    };
  }, [full, fixed, documentLayout]);

  useLayoutEffect(() => {
    if (previousIdentity.current === identity) return;
    previousIdentity.current = identity;
    anchor.current = null;
    current.current = { ...current.current, page: 0 };
    setLayout(current.current);
    measureNow.current();
  }, [identity]);

  useLayoutEffect(() => {
    if (!full || !root.current) return;
    const node = root.current;
    // The top layer escapes size containment and the Study dialog's stacking
    // context while keeping the same nodes, chart state and source identity.
    if (typeof node.showPopover === "function") node.showPopover();
    // Make the full-workspace reading mode modal without cloning records or
    // moving their React tree. Restore every sibling's prior inert state.
    const siblings: { element: HTMLElement; inert: boolean }[] = [];
    for (let branch: HTMLElement | null = node; branch?.parentElement; branch = branch.parentElement) {
      for (const sibling of branch.parentElement.children) {
        if (sibling !== branch && sibling instanceof HTMLElement) {
          siblings.push({ element: sibling, inert: sibling.inert }); sibling.inert = true;
        }
      }
      if (branch.parentElement === document.body) break;
    }
    node.querySelector<HTMLElement>(".full-reading-heading")?.focus({ preventScroll: true });
    return () => {
      if (typeof node.hidePopover === "function" && node.matches(":popover-open")) node.hidePopover();
      for (const { element, inert } of siblings) element.inert = inert;
      opener.current?.focus({ preventScroll: true });
    };
  }, [full]);

  const enterFull = (source: HTMLElement) => { opener.current = source; setFull(true); };
  const clipped = oversize && !full && !documentLayout;
  return <div ref={root} className="evidence-flow" popover={full ? "manual" : undefined} data-evidence-layout={documentLayout ? "document" : "pages"} data-full-reading={full} data-oversize={clipped} role={full ? "dialog" : "region"} aria-modal={full || undefined} aria-label={full ? `${label} — full reading` : label} onKeyDown={event => {
    if (!full) return;
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setFull(false); }
    if (event.key === "Tab") {
      const controls = Array.from(root.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input,select,textarea,summary,[tabindex="0"]') ?? []).filter(node => !node.closest('[hidden],[inert]') && node.getClientRects().length);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement === root.current?.querySelector(".full-reading-heading"))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }}>
    {full ? <header className="full-reading-bar"><h2 className="full-reading-heading" tabIndex={-1}>{label}</h2><button type="button" className="quiet" onClick={() => setFull(false)}>Return to workspace <span aria-hidden="true">↙</span></button></header> : null}
    <div ref={viewport} className="evidence-viewport">
      <div ref={content} id={id} className="evidence-columns" inert={clipped} aria-hidden={clipped || undefined} style={(!full || fixed) && !documentLayout ? { transform: `translateX(${-layout.page * (layout.width + GAP)}px)` } : undefined} onFocusCapture={event => {
        if ((full && !fixed) || documentLayout || !content.current || !layout.width) return;
        const rect = event.target.getClientRects()[0];
        if (rect) go(columnAt(rect.left - content.current.getBoundingClientRect().left, layout.width, layout.pages));
      }}><FlowContext.Provider value={true}>{children}</FlowContext.Provider></div>
      {clipped ? <div className="evidence-full-prompt"><p>This view needs more room at this window or text size.</p><button type="button" className="quiet" onClick={event => enterFull(event.currentTarget)}>Read in full <span aria-hidden="true">↗</span></button></div> : null}
    </div>
    <footer className="evidence-pagination" hidden={(full && !fixed) || documentLayout} aria-label={`${label} pages`}>
      <button type="button" className="full-reading-link" onClick={event => enterFull(event.currentTarget)}>Read in full <span aria-hidden="true">↗</span></button>
      {layout.pages > 1 && (!oversize || (full && fixed)) ? <div className="evidence-page-navigation"><button type="button" className="ibtn" aria-label={`Previous ${label.toLowerCase()} page`} aria-controls={id} disabled={layout.page === 0} onClick={() => go(layout.page - 1)}>‹</button><label className="evidence-page-number"><span className="sr-only">{label} page</span><input type="number" min={1} max={layout.pages} value={layout.page + 1} aria-controls={id} onChange={event => { if (event.target.value) go(Number(event.target.value) - 1); }} /><span aria-hidden="true">/ {layout.pages}</span></label><button type="button" className="ibtn" aria-label={`Next ${label.toLowerCase()} page`} aria-controls={id} disabled={layout.page === layout.pages - 1} onClick={() => go(layout.page + 1)}>›</button></div> : <span className="evidence-page-count">{clipped ? "Full reading available" : layout.width ? "1 / 1" : ""}</span>}
      <span className="sr-only" role="status">{layout.width ? `${label}, page ${layout.page + 1} of ${layout.pages}` : ""}</span>
    </footer>
  </div>;
}
