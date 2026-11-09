import { expect, it } from "vitest";
import { lightScale } from "../src/scene/lightScale";

it("fits slow measured work to a bounded tracing resolution and keeps fast devices at full resolution", () => {
  // The failed local attempt measured roughly 280 ms/sample at full resolution.
  expect(lightScale(280)).toBe(.5625);
  expect(lightScale(40)).toBe(1);
  expect(lightScale(5000)).toBe(.5);
  for (const value of [NaN, Infinity, -10, 0]) expect(lightScale(value)).toBe(1);
});
