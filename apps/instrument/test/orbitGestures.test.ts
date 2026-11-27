import { expect, it, vi } from "vitest";
import { bindOrbitGestures } from "../src/scene/orbitGestures";
function setup() {
  const element = document.createElement("canvas");
  element.setPointerCapture = vi.fn();
  const orbit = vi.fn(), zoom = vi.fn(), tap = vi.fn();
  const dispose = bindOrbitGestures(element, { orbit, zoom, tap });
  const send = (type: string, id: number, x: number, y: number) => {
    const event = new MouseEvent(type, { clientX: x, clientY: y, button: 0 });
    Object.defineProperties(event, { pointerId: { value: id }, pointerType: { value: "touch" }, isPrimary: { value: id === 1 } });
    element.dispatchEvent(event);
  };
  return { element, orbit, zoom, tap, send, dispose };
}
it("rotates vertically by touch without activating a part", () => {
  const s = setup(); s.send("pointerdown", 1, 100, 100); s.send("pointermove", 1, 100, 140); s.send("pointerup", 1, 100, 140); s.element.click();
  expect(s.orbit).toHaveBeenCalledWith(0, 40); expect(s.tap).not.toHaveBeenCalled(); s.dispose();
});
it("zooms with the non-primary second finger and never selects after pinch release", () => {
  const s = setup(); s.send("pointerdown", 1, 100, 100); s.send("pointerdown", 2, 200, 100); s.send("pointermove", 2, 250, 100);
  expect(s.zoom).toHaveBeenLastCalledWith(100 / 150);
  s.send("pointermove", 2, 175, 100); expect(s.zoom).toHaveBeenLastCalledWith(2);
  s.send("pointerup", 2, 175, 100); s.send("pointermove", 1, 100, 120); s.send("pointerup", 1, 100, 120); s.element.click();
  expect(s.tap).not.toHaveBeenCalled(); s.dispose();
});
it("activates only a deliberate completed tap and cancels interrupted gestures", () => {
  const s = setup(); s.send("pointerdown", 1, 20, 20); s.send("pointerup", 1, 20, 20); expect(s.tap).not.toHaveBeenCalled(); s.element.click(); expect(s.tap).toHaveBeenCalledTimes(1);
  s.send("pointerdown", 1, 20, 20); s.send("pointercancel", 1, 20, 20); s.element.click(); expect(s.tap).toHaveBeenCalledTimes(1); s.dispose();
});
