import { expect, it } from "vitest";
import { workspacePlacement } from "../src/ui/workspacePlacement";

const clear = { top: 0, right: 0, bottom: 0, left: 0 };

it.each([320, 390, 768, 1440])("keeps an upward camera menu reachable at %ipx without covering its invoker", width => {
  const anchor = { top: 470, bottom: 518, right: width / 2 + 60 };
  const box = workspacePlacement(anchor, { left: 0, top: 0, width, height: 568 }, clear, 312, 146, "above");
  expect(box.left).toBeGreaterThanOrEqual(12);
  expect(box.left + box.width).toBeLessThanOrEqual(width - 12);
  expect(box.top + 146).toBeLessThanOrEqual(anchor.top - 6);
  expect(box.top).toBeGreaterThanOrEqual(12);
});

it("fits the navigation rail between landscape display cutouts and the home indicator", () => {
  const box = workspacePlacement({ top: 20, bottom: 68, right: 800 }, { left: 0, top: 0, width: 844, height: 390 }, { top: 0, left: 47, right: 47, bottom: 21 }, 360, 256, "rail");
  expect(box.left + box.width).toBe(797);
  expect(box.top).toBe(20);
  expect(box.maxHeight).toBe(349);
});

it("bounds a scrollable rail to the visual viewport when a keyboard reduces its height", () => {
  const box = workspacePlacement({ top: 61, bottom: 109, right: 376 }, { left: 0, top: 0, width: 390, height: 280 }, { ...clear, top: 47 }, 206, 256, "rail");
  expect(box.top).toBe(61);
  expect(box.maxHeight).toBe(207);
  expect(box.top + box.maxHeight).toBeLessThanOrEqual(268);
});

it("flips a low disclosure and respects the panned origin of a zoomed viewport", () => {
  const viewport = { left: 180, top: 90, width: 320, height: 240 };
  const anchor = { top: 280, bottom: 324, right: 470 };
  const box = workspacePlacement(anchor, viewport, clear, 312, 600);
  expect(box).toEqual({ left: 192, top: 102, width: 296, maxHeight: 172 });
});

it("keeps the entire disclosure above a keyboard even when its invoker is obscured", () => {
  const box = workspacePlacement({ top: 470, bottom: 518, right: 280 }, { left: 0, top: 0, width: 390, height: 280 }, clear, 312, 600, "above");
  expect(box.top).toBe(12);
  expect(box.maxHeight).toBe(256);
  expect(box.top + box.maxHeight).toBe(268);
});
