import { useEffect, useRef } from "react";

/** Light dismissal must be an activation, not pointer-down: scrolling a panel
 * or orbiting a scene can finish outside the element where the gesture began.
 * Scene canvases own their own hit/miss qualification and are excluded here. */
export function useOutsideTap(active: boolean, inside: string, dismiss: () => void) {
  const latest = useRef(dismiss); latest.current = dismiss;
  useEffect(() => {
    if (!active) return;
    let press: { id: number; x: number; y: number; moved: boolean } | null = null;
    const excluded = (target: EventTarget | null) => target instanceof Element && !!target.closest(inside);
    const down = (event: PointerEvent) => {
      press = event.isPrimary && event.button === 0 && !excluded(event.target)
        ? { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false } : null;
    };
    const move = (event: PointerEvent) => {
      if (press?.id === event.pointerId && Math.hypot(event.clientX - press.x, event.clientY - press.y) > 7) press.moved = true;
    };
    const cancel = () => { press = null; };
    const click = (event: MouseEvent) => {
      const completed = press; press = null;
      if (completed && !completed.moved && !excluded(event.target)) latest.current();
    };
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("pointermove", move, true);
    document.addEventListener("pointercancel", cancel, true);
    document.addEventListener("click", click);
    return () => {
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("pointercancel", cancel, true);
      document.removeEventListener("click", click);
    };
  }, [active, inside]);
}
