/** Screen-space layout only. These rectangles are projections of the authored
 * mesh; they are never collision geometry or physical measurements. */
export interface ScreenRect { left: number; top: number; right: number; bottom: number }
export interface AnnotationAnchor {
  x: number; y: number; width: number; height: number;
  visible: boolean; body: ScreenRect[];
  target?: { x: number; y: number };
}
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(Math.max(lo, hi), n));
const overlap = (a: ScreenRect, b: ScreenRect) =>
  Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
  Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));

export function placeRicciAnnotation(anchor: AnnotationAnchor, size: { width: number; height: number }, reserved: ScreenRect[] = [], retainedSide?: -1 | 1) {
  const pad = 10, gap = 24, w = Math.min(size.width, anchor.width - 2 * pad), h = Math.min(size.height, anchor.height - 2 * pad);
  const xs = [anchor.x - gap - w, anchor.x + gap, pad, anchor.width - w - pad];
  const ys = [anchor.y - h * .4, anchor.y - h - gap, anchor.y + gap, pad, anchor.height - h - pad];
  // Scan the available vertical space as well as the anchor's immediate area.
  // On a phone a shoulder and a sole often need different sides and heights.
  for (let y = pad; y <= anchor.height - h - pad; y += 24) ys.push(y);
  for (const band of anchor.body) xs.push(band.left - gap - w, band.right + gap);
  const protectedPart = { left: anchor.x - 22, right: anchor.x + 22, top: anchor.y - 22, bottom: anchor.y + 22 };
  // Screen side follows the projected part, not its anatomical name. Central
  // assemblies may use either side; paired limbs stay on their own side.
  const side = retainedSide ?? (Math.abs(anchor.x - anchor.width / 2) < 8 ? 0 : Math.sign(anchor.x - anchor.width / 2));
  let best = { left: pad, top: pad, score: Infinity };
  for (const x of new Set(xs.map(x => Math.round(clamp(x, pad, anchor.width - w - pad))))) {
    if (side && Math.sign(x + w / 2 - anchor.width / 2) !== side) continue;
    for (const y of new Set(ys.map(y => Math.round(clamp(y, pad, anchor.height - h - pad))))) {
      const rect = { left: x, top: y, right: x + w, bottom: y + h };
      const distance = Math.hypot(clamp(anchor.x, x, x + w) - anchor.x, clamp(anchor.y, y, y + h) - anchor.y);
      const covered = anchor.body.reduce((sum, band) => sum + overlap(rect, band), 0);
      const blocked = reserved.reduce((sum, box) => sum + overlap(rect, box), 0);
      const score = distance + covered * .15 + blocked * 5 + overlap(rect, protectedPart) * 10 + (x > anchor.x ? 2 : 0);
      if (score < best.score) best = { left: x, top: y, score };
    }
  }
  const edgeX = clamp(anchor.x, best.left, best.left + w), edgeY = clamp(anchor.y, best.top + 16, best.top + h - 16);
  // The end belongs to the panel's perimeter, including above/below placement.
  const end = anchor.x < best.left || anchor.x > best.left + w
    ? { x: edgeX, y: edgeY }
    : { x: clamp(anchor.x, best.left + 16, best.left + w - 16), y: anchor.y < best.top ? best.top : best.top + h };
  const bend = { x: end.x + (anchor.x < end.x ? -14 : 14), y: end.y };
  return { left: best.left, top: best.top, width: w, height: h, end, bend };
}
