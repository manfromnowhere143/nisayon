import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { useOutsideTap } from "../src/ui/useOutsideTap";

it("dismisses outside activation once, without dismissing drags, cancellation, inside or mesh-owned events", async () => {
  const dismiss = vi.fn(), host = document.createElement("div"); document.body.append(host);
  function Surface() { useOutsideTap(true, "dialog, canvas, [data-inspect]", dismiss); return <><dialog open><button>Read</button></dialog><canvas /><button data-inspect>Inspect</button><button>Outside</button></>; }
  const root = createRoot(host); await act(async () => root.render(<Surface />));
  const event = (target: Element, type: string, x = 0) => {
    const e = new MouseEvent(type, { bubbles: true, button: 0, clientX: x });
    Object.defineProperties(e, { pointerId: { value: 1 }, isPrimary: { value: true } }); target.dispatchEvent(e);
  };
  const outside = host.lastElementChild!;
  for (const target of [host.querySelector("dialog button")!, host.querySelector("canvas")!, host.querySelector("[data-inspect]")!]) {
    event(target, "pointerdown"); event(target, "click");
  }
  event(outside, "pointerdown"); event(outside, "pointermove", 30); event(outside, "pointermove", 0); event(outside, "click");
  event(outside, "pointerdown"); event(outside, "pointercancel"); event(outside, "click");
  expect(dismiss).not.toHaveBeenCalled();
  event(outside, "pointerdown"); event(outside, "click"); event(outside, "click");
  expect(dismiss).toHaveBeenCalledTimes(1);
  await act(async () => root.unmount()); event(outside, "pointerdown"); event(outside, "click");
  expect(dismiss).toHaveBeenCalledTimes(1); host.remove();
});
