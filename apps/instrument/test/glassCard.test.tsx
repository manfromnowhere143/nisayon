import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { GlassCard } from "../src/research/GlassCard";
import { installFocusPresentation } from "../src/ui/focusPresentation";

let host: HTMLDivElement, root: Root, dispose: () => void;
beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  delete document.documentElement.dataset.focusModality;
  dispose = installFocusPresentation(document);
});
afterEach(async () => {
  await act(async () => root.unmount());
  dispose(); host.remove();
  delete document.documentElement.dataset.focusModality;
  vi.restoreAllMocks(); vi.useRealTimers();
});
function Harness({ closed }: { closed: () => void }) {
  const [open, setOpen] = useState(false);
  return <div className="instrument-root"><button onClick={() => setOpen(true)}>Evidence</button>{open ? <GlassCard title="Experiment evidence" onClose={() => { closed(); setOpen(false); }}><button>Inspect record</button></GlassCard> : null}</div>;
}
async function pointerClick(element: HTMLElement) {
  await act(async () => {
    element.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    element.focus();
    element.dispatchEvent(new MouseEvent("click", { detail: 1, bubbles: true }));
  });
}
async function open(closed = vi.fn()) {
  await act(async () => root.render(<Harness closed={closed} />));
  const opener = host.querySelector("button")!;
  await pointerClick(opener);
  return { opener, closed, card: host.querySelector("dialog")! };
}
function enableMotion() {
  vi.spyOn(window, "matchMedia").mockImplementation(query => ({ matches: query === "(prefers-reduced-motion: no-preference)" }) as MediaQueryList);
  vi.spyOn(document, "hidden", "get").mockReturnValue(false);
}
async function animationEnd(target: Element, name: string) {
  const event = new Event("animationend", { bubbles: true });
  Object.defineProperty(event, "animationName", { value: name });
  await act(async () => target.dispatchEvent(event));
}

it("opens a pointer card with accessible title focus and restores its exact opener", async () => {
  const { card, opener, closed } = await open();
  const heading = card.querySelector("h2")!;
  expect(document.activeElement).toBe(heading);
  expect(card.getAttribute("aria-labelledby")).toBe(heading.id);
  expect(heading.dataset.pointerFocus).toBe("true");
  await pointerClick(card.querySelector(".glass-card-close")!);
  expect(closed).toHaveBeenCalledOnce();
  expect(host.querySelector("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
  expect(opener.dataset.pointerFocus).toBe("true");
});

it("retains keyboard and assistive focus indicators when opening and returning", async () => {
  await act(async () => root.render(<Harness closed={vi.fn()} />));
  const opener = host.querySelector("button")!;
  await act(async () => { opener.focus(); opener.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); opener.click(); });
  const heading = host.querySelector("h2")!;
  expect(document.activeElement).toBe(heading);
  expect(heading.dataset.pointerFocus).toBeUndefined();
  await act(async () => host.querySelector("dialog")!.dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })));
  expect(document.activeElement).toBe(opener);
  expect(opener.dataset.pointerFocus).toBeUndefined();
});

it("keeps the modal in the top layer until its coordinated exit completes", async () => {
  vi.useFakeTimers(); enableMotion();
  const { card, closed, opener } = await open();
  await pointerClick(card.querySelector(".glass-card-close")!);
  expect(card.open).toBe(true);
  expect(card.dataset.closing).toBe("true");
  expect(closed).not.toHaveBeenCalled();
  await animationEnd(card.querySelector("h2")!, "nisayon-card-leave");
  await animationEnd(card, "nisayon-scrim-leave");
  expect(closed).not.toHaveBeenCalled();
  await animationEnd(card, "nisayon-card-leave");
  expect(closed).toHaveBeenCalledOnce();
  expect(document.activeElement).toBe(opener);
  await act(async () => vi.advanceTimersByTime(1000));
  expect(closed).toHaveBeenCalledOnce();
});

it("closes once within a bound if the browser suppresses animation events", async () => {
  vi.useFakeTimers(); enableMotion();
  const { card, closed } = await open();
  await act(async () => { card.dispatchEvent(new Event("cancel", { cancelable: true })); card.dispatchEvent(new Event("cancel", { cancelable: true })); });
  expect(closed).not.toHaveBeenCalled();
  await act(async () => vi.advanceTimersByTime(240));
  expect(closed).toHaveBeenCalledOnce();
  expect(host.querySelector("dialog")).toBeNull();
});

it("cancels pending exit callbacks when navigation removes the card", async () => {
  vi.useFakeTimers(); enableMotion();
  const { card, closed } = await open();
  await pointerClick(card.querySelector(".glass-card-close")!);
  await act(async () => root.render(<div>Another view</div>));
  await act(async () => vi.advanceTimersByTime(1000));
  expect(closed).not.toHaveBeenCalled();
});

it("closes immediately when motion is reduced", async () => {
  vi.spyOn(window, "matchMedia").mockImplementation(query => ({ matches: query === "(prefers-reduced-motion: reduce)" }) as MediaQueryList);
  const { card, closed } = await open();
  await pointerClick(card.querySelector(".glass-card-close")!);
  expect(closed).toHaveBeenCalledOnce();
  expect(host.querySelector("dialog")).toBeNull();
});
