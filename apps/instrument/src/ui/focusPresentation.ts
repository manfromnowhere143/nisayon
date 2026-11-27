// Based on the retained portfolio focus finding: correct pointer presentation
// without blurring controls, changing tab order, or hiding keyboard focus.
// Static headings are intentional focus destinations when a dialog or reading
// opens. They need the same input-modality policy as the invoking control.
// Text entry and arbitrary tabindex containers remain under native heuristics.
const CONTROL = "button, a[href], summary, select, input[type=range], [role=button], [data-focus-control], :is(h1,h2,h3,h4,h5,h6)[tabindex='-1']";
const MODIFIERS = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock"]);
const installations = new WeakMap<Document, { users: number; dispose: () => void }>();

// The shell and independently mounted lab share one listener set. Opening the
// lab must not reset the input modality of Library, Develop or a native dialog.
export function installFocusPresentation(document: Document): () => void {
  let entry = installations.get(document);
  if (!entry) {
    entry = { users: 0, dispose: listen(document) };
    installations.set(document, entry);
  }
  entry.users++;
  let disposed = false;
  return () => {
    if (disposed) return;
    disposed = true;
    if (--entry.users === 0) {
      entry.dispose();
      installations.delete(document);
    }
  };
}

const scopeOf = (element: Element | null) =>
  element?.closest(".instrument-root") ?? element?.closest(".app") ?? null;

function listen(document: Document): () => void {
  let pointerScope: Element | null = null;
  let nativeSelect: HTMLSelectElement | null = null;
  let popupOwner: HTMLElement | null = null;
  const marked = new Set<HTMLElement>();
  const clear = () => {
    pointerScope = null;
    nativeSelect = null;
    popupOwner = null;
    for (const control of marked) delete control.dataset.pointerFocus;
    marked.clear();
  };
  const mark = (target: EventTarget | null) => {
    if (!(target instanceof Element) || !pointerScope?.contains(target)) return;
    const control = target.closest<HTMLElement>(CONTROL);
    if (control && pointerScope.contains(control)) {
      control.dataset.pointerFocus = "true";
      marked.add(control);
    }
  };
  // Capability media queries alone cannot identify a touchscreen tap on a
  // laptop with a mouse. Keep actual pointer type separate from focus modality.
  const pointerType = (event: Event) => {
    const type = (event as PointerEvent).pointerType;
    if (type) document.documentElement.dataset.pointerType = type;
  };
  const pointer = (event: Event) => {
    pointerType(event);
    document.documentElement.dataset.focusModality = "pointer";
    const popup = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-focus-owner]") : null;
    const owner = popup?.dataset.focusOwner ? document.getElementById(popup.dataset.focusOwner) : null;
    popupOwner = owner;
    pointerScope = scopeOf(event.target instanceof Element ? event.target : null) ?? scopeOf(owner);
    nativeSelect = event.target instanceof Element ? event.target.closest<HTMLSelectElement>("select") : null;
    mark(event.target);
    // A top-layer popup keeps DOM focus on its invoker. Mark that invoker even
    // when it was opened by keyboard and pointer selection emits no new focus.
    if (owner) mark(owner);
  };
  const key = (event: KeyboardEvent) => {
    if (!MODIFIERS.has(event.key)) { document.documentElement.dataset.focusModality = "keyboard"; clear(); }
  };
  const click = (event: MouseEvent) => {
    if (event.detail !== 0) return;
    // PointerEvent clicks can have a zero count (including native completion).
    // Use their actual device type before applying the keyboard/AT fallback.
    // Keyboard and assistive clicks have no pointerType and remain visible.
    if ((event as PointerEvent).pointerType) { pointer(event); return; }
    const popup = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-focus-owner]") : null;
    if (popupOwner && popup?.dataset.focusOwner === popupOwner.id && document.activeElement === popupOwner) { mark(popupOwner); return; }
    // Native popup completion can have a zero click count. That count alone
    // does not undo the pointerdown which opened this very select. A real key
    // clears nativeSelect before activation; other assistive clicks still clear.
    const selected = event.target instanceof Element ? event.target.closest("select") : null;
    if (nativeSelect && selected === nativeSelect && document.activeElement === nativeSelect) { mark(nativeSelect); return; }
    document.documentElement.dataset.focusModality = "keyboard";
    clear();
  };
  const focus = (event: FocusEvent) => mark(event.target);
  // Preserve the last actual input modality when development hot reload or a
  // component remount reinstalls listeners while a native control keeps focus.
  if (document.documentElement.dataset.focusModality === "pointer" && document.activeElement instanceof Element) {
    pointerScope = scopeOf(document.activeElement);
    nativeSelect = document.activeElement.closest<HTMLSelectElement>("select");
    mark(document.activeElement);
  }
  document.addEventListener("pointerdown", pointer, true);
  document.addEventListener("pointermove", pointerType, true);
  document.addEventListener("keydown", key, true);
  document.addEventListener("click", click, true);
  document.addEventListener("focusin", focus, true);
  return () => {
    clear();
    document.removeEventListener("pointerdown", pointer, true);
    document.removeEventListener("pointermove", pointerType, true);
    document.removeEventListener("keydown", key, true);
    document.removeEventListener("click", click, true);
    document.removeEventListener("focusin", focus, true);
  };
}

/** A control inside a closing native popover cannot receive visible focus. */
export function focusReturnTarget(element: Element | null): HTMLElement | null {
  if (!(element instanceof HTMLElement)) return null;
  let target = element;
  const visited = new Set<HTMLElement>();
  while (!visited.has(target)) {
    visited.add(target);
    const popover = target.closest<HTMLElement>("[popover]");
    if (!popover) break;
    const invoker = [...document.querySelectorAll<HTMLButtonElement>("[popovertarget]")]
      .find(button => button.getAttribute("popovertarget") === popover.id);
    if (!invoker) break;
    target = invoker;
  }
  return target;
}
