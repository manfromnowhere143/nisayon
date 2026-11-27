import { PerspectiveCamera, Vector3 } from "three";
import { expect, it } from "vitest";
import { frameRicciCamera, ricciFramePoint } from "../src/concepts/ricciViewport";

const layouts = [
  { width: 1440, height: 900, frame: { left: 20, top: 150, width: 1400, height: 642 } },
  { width: 390, height: 844, frame: { left: 0, top: 138, width: 390, height: 359 } },
  { width: 320, height: 568, frame: { left: 0, top: 122, width: 320, height: 172 } },
  { width: 844, height: 320, frame: { left: 16, top: 64, width: 512, height: 181 } },
];
it.each(layouts)("extends a $width × $height stage without changing the robot's screen position, scale or picking projection", viewport => {
  for (const yaw of [0, -.48, 1.2]) for (const scale of [1, 1.32]) {
    const pose = { yaw, pitch: .1, scale };
    const bounded = new PerspectiveCamera(26, 1, .01, 80);
    const full = new PerspectiveCamera(26, 1, .01, 80);
    const original = { ...viewport.frame, left: 0, top: 0 };
    frameRicciCamera(bounded, original, original, pose);
    frameRicciCamera(full, viewport, viewport.frame, pose);
    expect(full.position.toArray()).toEqual(bounded.position.toArray());
    for (const point of [new Vector3(0, 1.7, 0), new Vector3(.3, .9, .1), new Vector3(-.1, .05, -.1)]) {
      const expected = ricciFramePoint(point.clone().project(bounded), original, original);
      const actual = ricciFramePoint(point.clone().project(full), viewport, viewport.frame);
      expect(actual.x).toBeCloseTo(expected.x, 9);
      expect(actual.y).toBeCloseTo(expected.y, 9);
      const reconstructed = point.clone().project(full).unproject(full);
      expect(reconstructed.distanceTo(point)).toBeLessThan(1e-10);
    }
  }
});

it("changes camera distance when zooming a narrow full-height phone stage", () => {
  const camera = new PerspectiveCamera(26, 1, .01, 80), frame = { left: 0, top: 0, width: 390, height: 844 };
  const target = new Vector3(0, .86, 0);
  frameRicciCamera(camera, frame, frame, { yaw: 0, pitch: .035, scale: 1 });
  const before = camera.position.distanceTo(target);
  frameRicciCamera(camera, frame, frame, { yaw: 0, pitch: .035, scale: 1.5 });
  expect(camera.position.distanceTo(target)).toBeCloseTo(before / 1.5, 9);
});
