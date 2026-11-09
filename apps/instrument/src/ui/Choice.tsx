import { useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export interface ChoiceOption { value: string; label: string; group?: string }
interface Props {
  label: string; value: string; options: readonly ChoiceOption[];
  onChange: (value: string) => void; disabled?: boolean; busy?: boolean;
  className?: string;
}

// Stay below the invoker. Long menus scroll within the visible viewport instead
// of flipping or invoking the operating system's full-screen choice surface.
export function choicePlacement(rect: Pick<DOMRect, "left" | "bottom" | "width">, viewport: { left: number; top: number; width: number; height: number }) {
  const width = Math.min(Math.max(rect.width, 264), Math.max(0, viewport.width - 24));
  const top = rect.bottom + 6;
  return { left: Math.max(viewport.left + 12, Math.min(rect.left, viewport.left + viewport.width - width - 12)), top, width, maxHeight: Math.max(0, Math.min(392, viewport.top + viewport.height - top - 16)) };
}

export function Choice({ label, value, options, onChange, disabled = false, busy = false, className = "" }: Props) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null), popup = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const typed = useRef({ text: "", at: 0 });
  const pointerStart = useRef<{ x: number; y: number } | null>(null);
  const selected = Math.max(0, options.findIndex((option) => option.value === value));
  const activeIndex = Math.min(active, Math.max(0, options.length - 1));
  const canPopover = typeof HTMLElement !== "undefined" && typeof HTMLElement.prototype.showPopover === "function";
  const close = () => setOpen(false);
  const show = (index = selected) => { typed.current = { text: "", at: 0 }; setActive(index); setOpen(true); };
  const commit = (index: number, restore = true) => {
    const option = options[index];
    setOpen(false);
    if (restore) trigger.current?.focus({ preventScroll: true });
    if (option && (busy || option.value !== value)) onChange(option.value);
  };

  useLayoutEffect(() => {
    if (!open || disabled) return;
    const button = trigger.current, panel = popup.current;
    if (!button || !panel) return;
    const place = () => {
      const viewport = window.visualViewport;
      const box = choicePlacement(button.getBoundingClientRect(), { left: viewport?.offsetLeft ?? 0, top: viewport?.offsetTop ?? 0, width: viewport?.width ?? window.innerWidth, height: viewport?.height ?? window.innerHeight });
      Object.assign(panel.style, { left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, maxHeight: `${box.maxHeight}px` });
    };
    place();
    if (canPopover) panel.showPopover();
    // Also support browsers without Popover. Pointer-down observes dismissal;
    // choosing an option happens on click, so a touch scroll cannot select it.
    const outside = (event: Event) => { const node = event.target as Node; if (!panel.contains(node) && !button.contains(node)) close(); };
    const toggled = (event: Event) => { if ((event as ToggleEvent).newState === "closed") close(); };
    const focus = (event: FocusEvent) => { if (!panel.contains(event.target as Node) && !button.contains(event.target as Node)) close(); };
    const scrolled = (event: Event) => { if (!panel.contains(event.target as Node)) place(); };
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("focusin", focus);
    document.addEventListener("scroll", scrolled, true);
    panel.addEventListener("toggle", toggled);
    window.addEventListener("resize", place);
    window.visualViewport?.addEventListener("resize", place);
    window.visualViewport?.addEventListener("scroll", place);
    const observer = new ResizeObserver(place); observer.observe(button);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      document.removeEventListener("focusin", focus);
      document.removeEventListener("scroll", scrolled, true);
      panel.removeEventListener("toggle", toggled);
      window.removeEventListener("resize", place);
      window.visualViewport?.removeEventListener("resize", place);
      window.visualViewport?.removeEventListener("scroll", place);
      observer.disconnect();
      if (canPopover && panel.matches(":popover-open")) panel.hidePopover();
    };
  }, [open, disabled, canPopover]);

  useLayoutEffect(() => {
    if (!open) return;
    const panel = popup.current, option = document.getElementById(`${id}-option-${activeIndex}`);
    if (!panel || !option) return;
    // Scroll only this menu, never the dashboard or browser document.
    const top = option.offsetTop, bottom = top + option.offsetHeight;
    if (top < panel.scrollTop) panel.scrollTop = top;
    else if (bottom > panel.scrollTop + panel.clientHeight) panel.scrollTop = bottom - panel.clientHeight;
  }, [open, activeIndex, id]);

  const key = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.metaKey || event.ctrlKey || disabled) return;
    const last = options.length - 1;
    if (last < 0) return;
    if (event.key === "Tab") { if (open) commit(activeIndex, false); return; }
    if (event.key === "Escape") { if (open) { event.preventDefault(); event.stopPropagation(); close(); } return; }
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open ? commit(activeIndex) : show(); return; }
    if (["ArrowDown", "ArrowUp", "Home", "End", "PageDown", "PageUp"].includes(event.key)) {
      event.preventDefault();
      if (event.altKey && event.key === "ArrowUp" && open) { commit(activeIndex); return; }
      const index = event.key === "Home" ? 0 : event.key === "End" ? last : !open ? selected : Math.max(0, Math.min(last, activeIndex + (event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : event.key === "PageDown" ? 10 : -10)));
      setActive(index); setOpen(true); return;
    }
    if (event.key.length === 1 && !event.altKey) {
      event.preventDefault();
      const now = performance.now(), letter = event.key.toLocaleLowerCase();
      const text = now - typed.current.at < 600 ? typed.current.text + letter : letter;
      typed.current = { text, at: now };
      const repeated = [...text].every((character) => character === letter);
      const query = repeated ? letter : text;
      const start = repeated ? (open ? activeIndex : selected) + 1 : open ? activeIndex : selected;
      for (let offset = 0; offset < options.length; offset++) {
        const index = (start + offset) % options.length;
        if (options[index]!.label.toLocaleLowerCase().startsWith(query)) { setActive(index); break; }
      }
      setOpen(true);
    }
  };

  return <>
    <button id={`${id}-trigger`} ref={trigger} type="button" role="combobox" className={`choice-trigger ${className}`} aria-label={label} aria-haspopup="listbox" aria-expanded={open && !disabled} aria-controls={`${id}-list`} aria-activedescendant={open && !disabled ? `${id}-option-${activeIndex}` : undefined} aria-busy={busy} disabled={disabled} onKeyDown={key} onClick={() => open ? close() : show()}>
      <span className="choice-value">{options.find((option) => option.value === value)?.label ?? "Choose"}</span><svg className="choice-chevron" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </button>
    {open && !disabled ? createPortal(<div ref={popup} id={`${id}-list`} role="listbox" aria-label={label} className="choice-popup" popover={canPopover ? "manual" : undefined} data-direction="down" data-focus-owner={`${id}-trigger`}>
      {options.map((option, index) => <div key={option.value} role="option" id={`${id}-option-${index}`} aria-selected={index === activeIndex} data-current={option.value === value} data-active={index === activeIndex} className={`choice-option${option.group && options[index - 1]?.group !== option.group ? " choice-group-start" : ""}`} onPointerMove={(event) => { if (event.pointerType === "mouse" && (event.movementX || event.movementY)) setActive(index); }} onPointerDown={(event) => { pointerStart.current = { x: event.clientX, y: event.clientY }; if (event.pointerType === "mouse") event.preventDefault(); }} onClick={(event) => { const start = pointerStart.current; pointerStart.current = null; if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 8) return; commit(index); }}>
        <span className="choice-check" aria-hidden="true">{option.value === value ? "✓" : ""}</span><span>{option.label}</span>
      </div>)}
    </div>, trigger.current?.closest("dialog") ?? document.body) : null}
  </>;
}
