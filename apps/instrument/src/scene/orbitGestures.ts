/** One pointer rotates on both axes; two pointers change distance. A pinch or
 * cancelled gesture can never activate a part, including after one finger lifts. */
export function bindOrbitGestures(element: HTMLElement, callbacks: {
  orbit: (dx: number, dy: number) => void;
  zoom: (factor: number) => void;
  tap: (event: PointerEvent) => void;
  hover?: (event: PointerEvent) => void;
}, activation: "click" | "pointerup" = "click") {
  type Point = { x: number; y: number; startX: number; startY: number; moved: boolean };
  const points = new Map<number, Point>();
  let distance = 0, eligible: PointerEvent | null = null;
  const separation = () => { const [a, b] = [...points.values()]; return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0; };
  const down = (event: PointerEvent) => {
    if (event.button !== 0 || (event.target instanceof Element && event.target.closest("button, a, input"))) return;
    eligible = null;
    points.set(event.pointerId, { x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, moved: false });
    element.setPointerCapture(event.pointerId);
    if (points.size > 1) { points.forEach(p => p.moved = true); distance = separation(); }
  };
  const move = (event: PointerEvent) => {
    const p = points.get(event.pointerId);
    if (!p) { callbacks.hover?.(event); return; }
    const dx = event.clientX - p.x, dy = event.clientY - p.y;
    p.x = event.clientX; p.y = event.clientY;
    if (points.size > 1) {
      const next = separation();
      if (distance > 0 && next > 0) callbacks.zoom(distance / next);
      distance = next;
    } else {
      if (Math.hypot(p.x - p.startX, p.y - p.startY) > 6) p.moved = true;
      if (p.moved) { callbacks.orbit(dx, dy); element.style.cursor = "grabbing"; }
    }
  };
  const up = (event: PointerEvent) => {
    const p = points.get(event.pointerId);
    if (!p) return;
    eligible = points.size === 1 && !p.moved && Math.hypot(event.clientX - p.startX, event.clientY - p.startY) <= 6 ? event : null;
    points.delete(event.pointerId); distance = 0;
    if (element.hasPointerCapture?.(event.pointerId)) element.releasePointerCapture(event.pointerId);
    element.style.cursor = "grab";
    if (activation === "pointerup" && eligible) { callbacks.tap(eligible); eligible = null; }
  };
  const click = () => { const tap = eligible; eligible = null; if (tap) callbacks.tap(tap); };
  const cancel = () => { points.clear(); distance = 0; eligible = null; element.style.cursor = "grab"; };
  const lost = (event: PointerEvent) => { if (points.has(event.pointerId)) cancel(); };
  const wheel = (event: WheelEvent) => { if (event.ctrlKey || event.metaKey) { event.preventDefault(); callbacks.zoom(Math.exp(event.deltaY * .002)); } };
  element.addEventListener("pointerdown", down);
  element.addEventListener("pointermove", move);
  element.addEventListener("pointerup", up);
  element.addEventListener("pointercancel", cancel);
  element.addEventListener("lostpointercapture", lost);
  element.addEventListener("click", click);
  element.addEventListener("wheel", wheel, { passive: false });
  return () => {
    cancel();
    element.removeEventListener("pointerdown", down); element.removeEventListener("pointermove", move);
    element.removeEventListener("pointerup", up); element.removeEventListener("pointercancel", cancel);
    element.removeEventListener("lostpointercapture", lost); element.removeEventListener("click", click);
    element.removeEventListener("wheel", wheel);
  };
}
