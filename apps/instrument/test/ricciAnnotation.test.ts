import { expect, it } from "vitest";
import { placeRicciAnnotation, type AnnotationAnchor } from "../src/concepts/annotationPlacement";
const frame: AnnotationAnchor = { x: 690, y: 350, width: 1200, height: 700, visible: true, body: [{ left: 480, right: 720, top: 40, bottom: 650 }] };
it("places right and left parts on their screen side, outside a silhouette when space permits", () => {
  for (const x of [510, 690]) {
    const result = placeRicciAnnotation({ ...frame, x }, { width: 248, height: 164 });
    expect(Math.sign(result.left + result.width / 2 - 600)).toBe(Math.sign(x - 600));
    expect(x > 600 ? result.left >= 720 : result.left + result.width <= 480).toBe(true);
    expect(result.top).toBeGreaterThanOrEqual(10);
  }
});
it("keeps phone labels in bounds and off the selected surface, without swapping screen sides", () => {
  for (const width of [320, 390]) for (const x of [width * .35, width * .65]) {
    const result = placeRicciAnnotation({ ...frame, x, y: 480, width, height: 540, body: [{ left: width * .35, right: width * .65, top: 40, bottom: 510 }] }, { width: 148, height: 148 });
    expect(result.left).toBeGreaterThanOrEqual(10); expect(result.left + result.width).toBeLessThanOrEqual(width - 10);
    expect(result.top + result.height).toBeLessThanOrEqual(530);
    expect(Math.sign(result.left + result.width / 2 - width / 2)).toBe(Math.sign(x - width / 2));
    expect(x > result.left && x < result.left + result.width && 480 > result.top && 480 < result.top + result.height).toBe(false);
  }
});
it("avoids the playback and view controls in short landscape", () => {
  const reserved = [{ left: 0, top: 150, right: 284, bottom: 202 }];
  const result = placeRicciAnnotation({ ...frame, x: 280, y: 140, width: 820, height: 202, body: [{ left: 360, right: 460, top: 8, bottom: 190 }] }, { width: 248, height: 130 }, reserved);
  expect(result.top + result.height).toBeLessThanOrEqual(150);
});
it("preserves the compact card's side when disclosure changes its height", () => {
  const anchor = { ...frame, x: 195, y: 300, width: 390, height: 540 };
  for (const side of [-1, 1] as const) {
    for (const height of [136, 420]) {
      const result = placeRicciAnnotation(anchor, { width: 180, height }, [], side);
      expect(Math.sign(result.left + result.width / 2 - anchor.width / 2)).toBe(side);
      expect(result.top + result.height).toBeLessThanOrEqual(anchor.height - 10);
    }
  }
});
