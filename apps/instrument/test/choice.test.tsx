import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { Choice, choicePlacement } from "../src/ui/Choice";

let root: Root | null = null, host: HTMLDivElement;
const options = [{ value: "a", label: "Arm link 1" }, { value: "b", label: "Arm link 2" }, { value: "c", label: "Cube" }];
async function mount(onChange = vi.fn(), busy = false) {
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  await act(async () => root!.render(<><Choice label="Part" value="a" options={options} onChange={onChange} busy={busy} /><button>Outside</button></>));
  return host.querySelector<HTMLButtonElement>('[role="combobox"]')!;
}
async function key(button: HTMLElement, key: string) { await act(async () => button.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }))); }
async function click(element: Element) { await act(async () => element.dispatchEvent(new MouseEvent("click", { bubbles: true }))); }
afterEach(async () => { await act(async () => root?.unmount()); host?.remove(); root = null; vi.restoreAllMocks(); });

it("opens below the control at narrow, landscape and desktop sizes and constrains the available height", () => {
  for (const width of [320, 390, 844, 1440]) for (const height of [320, 568, 900]) {
    const rect = { left: width - 240, bottom: 154, width: 220 };
    const box = choicePlacement(rect, { left: 0, top: 0, width, height });
    expect(box.top).toBe(160);
    expect(box.left).toBeGreaterThanOrEqual(12);
    expect(box.left + box.width).toBeLessThanOrEqual(width - 12);
    expect(box.top + box.maxHeight).toBeLessThanOrEqual(height - 16);
  }
  expect(choicePlacement({ left: 5, bottom: 250, width: 200 }, { left: 0, top: 0, width: 320, height: 260 }).maxHeight).toBe(0);
});

it("browses options without selecting, commits by Enter, and cancels by Escape", async () => {
  const change = vi.fn(), button = await mount(change); button.focus();
  await key(button, "ArrowDown");
  expect(button.getAttribute("aria-expanded")).toBe("true");
  await key(button, "ArrowDown");
  expect(change).not.toHaveBeenCalled();
  expect(document.getElementById(button.getAttribute("aria-activedescendant")!)?.textContent).toContain("Arm link 2");
  await key(button, "Escape");
  expect(change).not.toHaveBeenCalled(); expect(document.activeElement).toBe(button);
  expect(document.querySelector('[role="listbox"]')).toBeNull();
  await key(button, "End"); await key(button, "Enter");
  expect(change).toHaveBeenCalledExactlyOnceWith("c");
  expect(document.querySelector('[role="listbox"]')).toBeNull();
});

it("supports typeahead and Tab while leaving document focus order intact", async () => {
  const change = vi.fn(), button = await mount(change); button.focus();
  await key(button, "c");
  expect(document.getElementById(button.getAttribute("aria-activedescendant")!)?.textContent).toContain("Cube");
  const event = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
  await act(async () => button.dispatchEvent(event));
  expect(event.defaultPrevented).toBe(false); expect(change).toHaveBeenCalledExactlyOnceWith("c");
});

it("dismisses outside, cancels a touch drag, and selects only the clicked option", async () => {
  const change = vi.fn(), button = await mount(change);
  await click(button);
  await act(async () => host.querySelector("button:last-child")!.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true })));
  expect(document.querySelector('[role="listbox"]')).toBeNull();
  await click(button);
  const cube = [...document.querySelectorAll('[role="option"]')].find((node) => node.textContent?.includes("Cube"))!;
  await act(async () => { cube.dispatchEvent(new MouseEvent("pointerdown", { clientX: 40, clientY: 100, bubbles: true })); cube.dispatchEvent(new MouseEvent("click", { clientX: 40, clientY: 140, bubbles: true })); });
  expect(change).not.toHaveBeenCalled();
  await click(cube); expect(change).toHaveBeenCalledExactlyOnceWith("c");
  expect(document.activeElement).toBe(button);
});

it("allows choosing the current recording to cancel an outstanding selection", async () => {
  const change = vi.fn(), button = await mount(change, true);
  await click(button); await click(document.querySelector('[role="option"]')!);
  expect(change).toHaveBeenCalledExactlyOnceWith("a");
});

it("repositions after viewport changes without moving above the trigger", async () => {
  const button = await mount();
  let bottom = 100;
  vi.spyOn(button, "getBoundingClientRect").mockImplementation(() => ({ left: 30, bottom, width: 230 } as DOMRect));
  await click(button);
  const popup = document.querySelector<HTMLElement>('[role="listbox"]')!;
  expect(popup.style.top).toBe("106px");
  bottom = 140;
  await act(async () => window.dispatchEvent(new Event("resize")));
  expect(popup.style.top).toBe("146px");
});
