import { afterEach, beforeEach, expect, it } from "vitest";
import { installFocusPresentation } from "../src/ui/focusPresentation";

it("tracks real input on hybrid screens independently from keyboard focus", () => {
  const dispose = installFocusPresentation(document);
  const send = (type: string, pointerType: string) => {
    const event = new Event(type, { bubbles: true }); Object.defineProperty(event, "pointerType", { value: pointerType }); document.dispatchEvent(event);
  };
  send("pointerdown", "touch"); expect(document.documentElement.dataset.pointerType).toBe("touch");
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
  expect(document.documentElement.dataset.focusModality).toBe("keyboard");
  expect(document.documentElement.dataset.pointerType).toBe("touch");
  send("pointermove", "mouse"); expect(document.documentElement.dataset.pointerType).toBe("mouse");
  dispose(); delete document.documentElement.dataset.pointerType;
});

let cleanup: () => void;
let button: HTMLButtonElement;
beforeEach(() => {
  delete document.documentElement.dataset.focusModality;
  document.body.innerHTML = '<main class="app"><button id="control">Zoom</button><button id="close">Close</button><input type="text" /><select><option>Robot base</option><option>Gripper</option></select></main><button id="outside">Outside</button>';
  button = document.querySelector("#control")!;
  cleanup = installFocusPresentation(document);
});
afterEach(() => { cleanup(); document.body.innerHTML = ""; delete document.documentElement.dataset.focusModality; });
it("keeps native pointer focus while suppressing only its presentation", () => {
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.focus();
  expect(document.activeElement).toBe(button);
  expect(button.dataset.pointerFocus).toBe("true");
  const close = document.querySelector<HTMLButtonElement>("#close")!;
  close.focus();
  expect(close.dataset.pointerFocus).toBe("true");
  button.focus();
  expect(document.activeElement).toBe(button);
  expect(button.dataset.pointerFocus).toBe("true");
});
it("restores keyboard presentation for Tab including Safari Option+Tab from outside", () => {
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Alt", bubbles: true }));
  expect(button.dataset.pointerFocus).toBe("true");
  document.querySelector("#outside")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", altKey: true, bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
  button.focus();
  expect(button.dataset.pointerFocus).toBeUndefined();
});
it("preserves keyboard and assistive activation and leaves text fields unmarked", () => {
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.dispatchEvent(new MouseEvent("click", { detail: 0, bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
  const input = document.querySelector("input")!;
  input.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  input.focus();
  expect(input.dataset.pointerFocus).toBeUndefined();
});
it("retains pointer presentation when a native select completes with a zero-count click", () => {
  const select = document.querySelector("select")!;
  select.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  select.focus();
  select.value = "Gripper";
  select.dispatchEvent(new Event("change", { bubbles: true }));
  select.dispatchEvent(new MouseEvent("click", { detail: 0, bubbles: true }));
  expect(document.activeElement).toBe(select);
  expect(select.dataset.pointerFocus).toBe("true");
  select.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
  expect(select.dataset.pointerFocus).toBeUndefined();
  select.dispatchEvent(new MouseEvent("click", { detail: 0, bubbles: true }));
  expect(select.dataset.pointerFocus).toBeUndefined();
});
it.each(["mouse", "touch", "pen"])("preserves a zero-count %s PointerEvent click without losing keyboard focus", pointerType => {
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.focus();
  const event = new MouseEvent("click", { detail: 0, bubbles: true });
  Object.defineProperty(event, "pointerType", { value: pointerType });
  button.dispatchEvent(event);
  expect(button.dataset.pointerFocus).toBe("true");
  expect(document.activeElement).toBe(button);
  button.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
});
it("preserves pointer modality across listener replacement without blurring the focused control", () => {
  const select = document.querySelector("select")!;
  select.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  select.focus();
  cleanup();
  cleanup = installFocusPresentation(document);
  expect(document.activeElement).toBe(select);
  expect(select.dataset.pointerFocus).toBe("true");
  select.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
  expect(select.dataset.pointerFocus).toBeUndefined();
});
it("returns pointer presentation from a top-layer choice even when its invoker kept keyboard focus", () => {
  button.focus();
  const popup = document.createElement("div"); popup.dataset.focusOwner = button.id;
  popup.innerHTML = '<div role="option">Arm link 4</div>'; document.body.appendChild(popup);
  button.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
  popup.firstElementChild!.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  popup.firstElementChild!.dispatchEvent(new MouseEvent("click", { detail: 0, bubbles: true }));
  expect(document.activeElement).toBe(button);
  expect(button.dataset.pointerFocus).toBe("true");
  button.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
});

it("covers the instrument shell before the robot lab has ever mounted", () => {
  document.querySelector("main")!.className = "instrument-root";
  const workspace = document.createElement("section"); workspace.className = "research-workspace";
  workspace.append(button); document.querySelector("main")!.append(workspace);
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.focus();
  expect(document.activeElement).toBe(button);
  expect(button.dataset.pointerFocus).toBe("true");
  button.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
});

it("retains shell focus when a second lab subscriber mounts and leaves", () => {
  button.dispatchEvent(new Event("pointerdown", { bubbles: true })); button.focus();
  const labCleanup = installFocusPresentation(document);
  expect(button.dataset.pointerFocus).toBe("true");
  labCleanup(); labCleanup();
  expect(button.dataset.pointerFocus).toBe("true");
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
  expect(button.dataset.pointerFocus).toBeUndefined();
});

it.each(["h1", "h2", "h3", "h4", "h5", "h6"])("keeps a pointer-opened %s focus destination free of a keyboard indicator", tag => {
  const heading = document.createElement(tag);
  heading.tabIndex = -1;
  heading.textContent = "Evidence";
  document.querySelector("main")!.append(heading);
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.focus();
  // Native dialog opening moves focus to its static title. That title must
  // keep focus for reading order without acquiring a pointer focus rectangle.
  heading.focus();
  expect(document.activeElement).toBe(heading);
  expect(heading.dataset.pointerFocus).toBe("true");
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true }));
  expect(heading.dataset.pointerFocus).toBeUndefined();
  button.focus();
  expect(button.dataset.pointerFocus).toBeUndefined();
});

it("preserves visible heading focus for keyboard and assistive dialog opening", () => {
  const heading = document.createElement("h2");
  heading.tabIndex = -1;
  document.querySelector("main")!.append(heading);
  button.dispatchEvent(new Event("pointerdown", { bubbles: true }));
  button.dispatchEvent(new MouseEvent("click", { detail: 0, bubbles: true }));
  heading.focus();
  expect(document.activeElement).toBe(heading);
  expect(heading.dataset.pointerFocus).toBeUndefined();
});

it("carries actual mesh pointer modality through an inspector and back to its canvas", () => {
  const canvas=document.createElement("canvas"); canvas.tabIndex=0; canvas.dataset.focusControl="";
  const heading=document.createElement("h2"); heading.tabIndex=-1;
  document.querySelector("main")!.append(canvas,heading);
  canvas.dispatchEvent(new Event("pointerdown",{bubbles:true})); heading.focus();
  expect(heading.dataset.pointerFocus).toBe("true");
  document.querySelector("#close")!.dispatchEvent(new Event("pointerdown",{bubbles:true})); canvas.focus();
  expect(canvas.dataset.pointerFocus).toBe("true"); expect(document.activeElement).toBe(canvas);
  canvas.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowLeft",bubbles:true}));
  expect(canvas.dataset.pointerFocus).toBeUndefined();
});
