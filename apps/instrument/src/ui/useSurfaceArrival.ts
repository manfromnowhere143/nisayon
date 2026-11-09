import { useLayoutEffect, useRef, type RefObject } from "react";

// Arrival follows an already committed selection. It cannot postpone input,
// blend evidence, or let an old completion callback overwrite a newer state.
export function useSurfaceArrival(surface: RefObject<HTMLElement | null>, identity: string, reduced: boolean) {
  const previous = useRef(identity);
  useLayoutEffect(() => {
    if (!identity) return;
    const changed = !!previous.current && !!identity && previous.current !== identity;
    previous.current = identity;
    const node = surface.current?.querySelector<HTMLElement>(".moment-inspection, .reading-content:not([hidden])") ?? surface.current;
    if (!changed || reduced || !node?.animate) return;
    const animation = node.animate([{ opacity: 0.72 }, { opacity: 1 }], { duration: 140, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" });
    return () => animation.cancel();
  }, [identity, reduced, surface]);
}
