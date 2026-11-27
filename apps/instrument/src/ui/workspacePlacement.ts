interface Viewport { left: number; top: number; width: number; height: number }
interface Insets { left: number; right: number; top: number; bottom: number }

/** Fit the actual visible area, including a keyboard, zoom and display cutouts.
 * Navigation keeps its aligned rail; a low camera invoker opens upward. */
export function workspacePlacement(
  anchor: Pick<DOMRect, "top" | "right" | "bottom">,
  viewport: Viewport,
  insets: Insets,
  requestedWidth: number,
  contentHeight: number,
  placement: "rail" | "auto" | "above" | "above-center" = "auto",
) {
  const leftEdge = viewport.left + Math.max(12, insets.left);
  const rightEdge = viewport.left + viewport.width - Math.max(12, insets.right);
  const topEdge = viewport.top + Math.max(12, insets.top);
  const bottomEdge = viewport.top + viewport.height - Math.max(12, insets.bottom);
  const width = Math.max(0, Math.min(requestedWidth, rightEdge - leftEdge));
  const requestedLeft = placement === "above-center" ? viewport.left + (viewport.width - width) / 2 : anchor.right - width;
  const left = Math.max(leftEdge, Math.min(requestedLeft, rightEdge - width));
  if (placement === "rail") {
    const top = Math.max(topEdge, Math.min(anchor.top, bottomEdge - 48));
    return { left, top, width, maxHeight: Math.max(0, bottomEdge - top) };
  }
  const below = Math.max(0, bottomEdge - Math.max(anchor.bottom + 6, topEdge));
  const above = Math.max(0, Math.min(anchor.top - 6, bottomEdge) - topEdge);
  const upward = placement.startsWith("above") ? above >= 44 || above >= below : contentHeight > below && above > below;
  const maxHeight = upward ? above : below;
  const height = Math.min(contentHeight, maxHeight);
  const top = Math.max(topEdge, Math.min(upward ? anchor.top - 6 - height : anchor.bottom + 6, bottomEdge - height));
  return { left, top, width, maxHeight };
}
