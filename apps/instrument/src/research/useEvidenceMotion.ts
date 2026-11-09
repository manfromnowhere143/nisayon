import { useLayoutEffect, type RefObject } from "react";

/** Motion traces the selected mechanism after its evidence has committed.
 * Readings change immediately; no interpolated value becomes a fake result. */
export function useEvidenceMotion(
  surface: RefObject<HTMLElement | null>,
  identity: string,
) {
  useLayoutEffect(() => {
    const node = surface.current;
    if (
      !identity ||
      !node ||
      !node.clientWidth ||
      typeof node.animate !== "function"
    )
      return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    if (motion.matches) return;
    const animations: Animation[] = [];
    const finish = () => animations.forEach((animation) => animation.cancel());
    // A small assembly of relationships. All motion is finite and cancellable
    // when a new selection arrives, or reduced motion is enabled mid-sequence.
    const groups = node.querySelectorAll<SVGElement | HTMLElement>(
      ".mechanism-drawing > g, .routing-client, .queue-request, .dependency-chain > div",
    );
    groups.forEach((group, i) => {
      animations.push(
        group.animate(
          [
            { opacity: 0.35, transform: "translateY(5px)" },
            { opacity: 1, transform: "translateY(0)" },
          ],
          {
            duration: 480,
            delay: Math.min(i * 36, 144),
            easing: "cubic-bezier(.2,.8,.2,1)",
            fill: "backwards",
          },
        ),
      );
    });
    node
      .querySelectorAll<SVGPathElement>(
        ".episode-record, .copy-links > path, .hypothesis > path, .vector-arrow > path:first-child, .promotion-connection, .dispatch-connection",
      )
      .forEach((path) => {
        const length = path.getTotalLength();
        if (length > 0)
          animations.push(
            path.animate(
              [
                { strokeDasharray: `${length}`, strokeDashoffset: `${length}` },
                { strokeDasharray: `${length}`, strokeDashoffset: "0" },
              ],
              { duration: 650, easing: "cubic-bezier(.2,.7,.2,1)" },
            ),
          );
      });
    motion.addEventListener("change", finish, { once: true });
    return () => {
      finish();
      motion.removeEventListener("change", finish);
    };
  }, [identity, surface]);
}
