// @vitest-environment node
import { describe, expect, it } from "vitest";
import { wallVisible } from "../src/scene/room";

describe("retained room cutaway", () => {
  const front: [number, number, number, number] = [-0.5, -0.5, 0.5, 0.5];
  const rear: [number, number, number, number] = [0.5, 0.5, 0.5, 0.5];
  it("hides the recorded front wall when zooming moves the camera outside it", () => {
    expect(wallVisible([1, -1, 1.5], [0, 0, 0.9], [3, 0, 1.5], front, 0.01)).toBe(true);
    expect(wallVisible([4, -2, 2], [0, 0, 0.9], [3, 0, 1.5], front, 0.01)).toBe(false);
  });
  it("keeps the backdrop and handles the opposite side after orbiting", () => {
    expect(wallVisible([4, -2, 2], [0, 0, 0.9], [-2, 0, 1.5], rear, 0.01)).toBe(true);
    expect(wallVisible([-4, 0, 2], [0, 0, 0.9], [-2, 0, 1.5], rear, 0.01)).toBe(false);
    expect(wallVisible([3, 0, 2], [0, 0, 0.9], [3, 0, 1.5], front, 0.01)).toBe(false);
  });
});
