import { placeRicciAnnotation, type AnnotationAnchor, type ScreenRect } from "../concepts/annotationPlacement";

/** Use Ricci's silhouette-aware placement inside the space left by the real
 * header, safe area and playback. No camera movement is needed to read a part. */
export function partInspectionPlacement(anchor: AnnotationAnchor, size: { width: number; height: number }, safe: ScreenRect, retainedSide?: -1 | 1) {
  const width = Math.max(20, safe.right - safe.left), height = Math.max(20, safe.bottom - safe.top);
  const local = { ...anchor, x: anchor.x - safe.left, y: anchor.y - safe.top, width, height,
    body: anchor.body.map(rect => ({ left: rect.left - safe.left, right: rect.right - safe.left, top: rect.top - safe.top, bottom: rect.bottom - safe.top })) };
  const placed = placeRicciAnnotation(local, { width: Math.min(size.width, width - 20), height: Math.min(size.height, height - 20) }, [], retainedSide);
  return { ...placed, left: placed.left + safe.left, top: placed.top + safe.top,
    end: { x: placed.end.x + safe.left, y: placed.end.y + safe.top },
    bend: { x: placed.bend.x + safe.left, y: placed.bend.y + safe.top } };
}
