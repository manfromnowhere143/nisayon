import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { columnAt, columnCount, EvidenceFlow, EvidenceIdentity } from "../src/ui/EvidenceFlow";
import { FieldNavigator, fieldPointer } from "../src/ui/FieldNavigator";
import { DOCUMENT_EVIDENCE_QUERY } from "../src/ui/useDocumentEvidence";

let root: Root | null = null, host: HTMLDivElement;
let width = 400, height = 300, pages = 3, figureHeight = 100;
let columns = [0, 1, 2];
const observers = new Set<() => void>();
const rect = (left: number, width: number, height: number) => ({ x: left, y: 0, left, top: 0, width, height, right: left + width, bottom: height, toJSON() {} }) as DOMRect;
async function click(element: Element) { await act(async () => element.dispatchEvent(new MouseEvent("click", { bubbles: true }))); }
async function reflow() { await act(async () => { for (const notify of observers) notify(); await new Promise(resolve => setTimeout(resolve, 35)); }); }

beforeEach(() => {
  width = 400; height = 300; pages = 3; figureHeight = 100; columns = [0, 1, 2];
  vi.stubGlobal("ResizeObserver", class {
    constructor(private callback: () => void) { observers.add(callback); }
    observe() {} unobserve() {} disconnect() { observers.delete(this.callback); }
  });
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(function () { return width; });
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function () { return height; });
  vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockImplementation(function () { return pages * (width + 32) - 32; });
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const index = Number(this.closest("[data-record]")?.getAttribute("data-record") ?? 0);
    return rect((columns[index] ?? 0) * (width + 32), width, this.tagName.toLowerCase() === "svg" ? figureHeight : 44);
  });
  vi.spyOn(Element.prototype, "getClientRects").mockImplementation(function (this: Element) { return [this.getBoundingClientRect()] as unknown as DOMRectList; });
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root?.unmount()); host.remove(); root = null; observers.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const records = (indices: number[]) => <>{indices.map(index => <article key={index} data-record={index}><p>Record {index} · exact unresolved evidence</p><button type="button">Source {index}</button></article>)}</>;
async function mount(source = "a", indices = [0, 1, 2]) { await act(async () => root!.render(<><button id="outside">Lab control</button><EvidenceIdentity.Provider value={source}><EvidenceFlow label="Readings">{records(indices)}</EvidenceFlow></EvidenceIdentity.Provider></>)); }

it("counts native fragments, clamps point selection and handles rounded CSS pixels", () => {
  expect(columnCount(1264, 400)).toBe(3);
  expect(columnCount(400.5, 400)).toBe(1);
  expect(columnCount(0, 0)).toBe(1);
  expect(columnAt(500, 400, 3)).toBe(1);
  expect(columnAt(-10, 400, 3)).toBe(0);
  expect(columnAt(9999, 400, 3)).toBe(2);
});

it("preserves the current retained node across resize, a hidden pane and repagination", async () => {
  await mount();
  await click(host.querySelector('[aria-label="Next readings page"]')!);
  const anchor = host.querySelector('[data-record="1"]');
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("2");
  width = 0; await reflow();
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("2");
  width = 500; height = 210; pages = 4; columns = [0, 2, 3]; await reflow();
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("3");
  expect(host.querySelector('[data-record="1"]')).toBe(anchor);
  expect(host.querySelector<HTMLElement>(".evidence-columns")?.style.transform).toBe("translateX(-1064px)");
  await mount("new verified source");
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("1");
});

it("reveals an off-page keyboard target without moving or replacing the record", async () => {
  await mount();
  const target = host.querySelector<HTMLButtonElement>('[data-record="2"] button')!;
  await act(async () => target.focus({ preventScroll: true }));
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("3");
  expect(document.activeElement).toBe(target);
  expect(host.querySelectorAll("[data-record]")).toHaveLength(3);
});

it("anchors the replacement reading when the previous record leaves the view", async () => {
  await mount();
  await click(host.querySelector('[aria-label="Next readings page"]')!);
  columns = [0, 1, 1];
  await mount("a", [0, 2]);
  await reflow();
  width = 500; pages = 4; columns = [0, 1, 3];
  await reflow();
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("4");
});

it("opens a full-workspace document and restores the same page, nodes, focus and inert state", async () => {
  await mount();
  const outside = host.querySelector<HTMLButtonElement>("#outside")!;
  outside.inert = false;
  await click(host.querySelector('[aria-label="Next readings page"]')!);
  const opener = host.querySelector<HTMLButtonElement>(".full-reading-link")!;
  const node = host.querySelector('[data-record="1"]');
  await click(opener);
  expect(host.querySelector('[role="dialog"][aria-modal="true"]')).not.toBeNull();
  expect(outside.inert).toBe(true);
  expect(document.activeElement).toBe(host.querySelector(".full-reading-heading"));
  const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
  await act(async () => host.querySelector(".evidence-flow")!.dispatchEvent(escape));
  expect(escape.defaultPrevented).toBe(true); // Must not close the parent Study dialog.
  expect(outside.inert).toBe(false);
  expect(document.activeElement).toBe(opener);
  expect(host.querySelector('[data-record="1"]')).toBe(node);
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("2");
});

it("offers full reading for an oversized figure rather than a clipped interactive chart", async () => {
  height = 150; figureHeight = 100;
  await act(async () => root!.render(<EvidenceFlow label="Signal"><svg aria-label="Complete signal" /><p>Original record unchanged</p></EvidenceFlow>));
  const flow = host.querySelector(".evidence-flow")!;
  expect(flow.getAttribute("data-oversize")).toBe("false");
  // A new figure can exceed the height while width and column count stay fixed.
  figureHeight = 320;
  await reflow();
  expect(flow.getAttribute("data-oversize")).toBe("true");
  expect(host.querySelector(".evidence-columns")!.hasAttribute("inert")).toBe(true);
  const svg = host.querySelector("svg");
  await click(host.querySelector(".evidence-full-prompt button")!);
  expect(flow.getAttribute("data-full-reading")).toBe("true");
  expect(host.querySelector("svg")).toBe(svg);
  expect(host.querySelector(".evidence-columns")!.hasAttribute("inert")).toBe(false);
});

it("keeps full reading available when chrome exhausts the body height and recovers on rotation", async () => {
  height = 0;
  await mount();
  expect(host.querySelector(".evidence-flow")!.getAttribute("data-oversize")).toBe("true");
  expect(host.querySelector(".full-reading-link")).not.toBeNull();
  height = 300;
  await reflow();
  expect(host.querySelector(".evidence-flow")!.getAttribute("data-oversize")).toBe("false");
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.max).toBe("3");
});

it("keeps every record interactive on a phone without measuring a clipped rectangle", async () => {
  vi.spyOn(window, "matchMedia").mockImplementation(query => ({ matches: query === DOCUMENT_EVIDENCE_QUERY, media: query, addEventListener() {}, removeEventListener() {} }) as unknown as MediaQueryList);
  height = 0;
  await mount();
  expect(observers.size).toBe(0);
  expect(host.querySelector(".evidence-flow")!.getAttribute("data-evidence-layout")).toBe("document");
  expect(host.querySelector(".evidence-columns")!.hasAttribute("inert")).toBe(false);
  expect(host.querySelector(".evidence-columns")!.hasAttribute("aria-hidden")).toBe(false);
  expect(host.querySelector<HTMLElement>(".evidence-columns")!.style.transform).toBe("");
  expect(host.querySelector<HTMLElement>(".evidence-pagination")!.hidden).toBe(true);
  expect(host.querySelector(".evidence-full-prompt")).toBeNull();
  const last = host.querySelector<HTMLButtonElement>('[data-record="2"] button')!;
  await act(async () => last.focus());
  expect(document.activeElement).toBe(last);
  expect(host.querySelectorAll("[data-record]")).toHaveLength(3);
});

it("switches between phone reading and fitted pages without replacing evidence or disclosure state", async () => {
  let compact = false;
  const notifications = new Set<() => void>();
  vi.spyOn(window, "matchMedia").mockImplementation(query => ({
    matches: query === DOCUMENT_EVIDENCE_QUERY && compact, media: query,
    addEventListener: (_event: string, notify: () => void) => notifications.add(notify),
    removeEventListener: (_event: string, notify: () => void) => notifications.delete(notify),
  }) as unknown as MediaQueryList);
  await act(async () => root!.render(<EvidenceFlow label="Witnesses"><details open><summary>Binding and source</summary>{records([0, 1, 2])}</details></EvidenceFlow>));
  await click(host.querySelector('[aria-label="Next witnesses page"]')!);
  const record = host.querySelector('[data-record="2"]');
  await act(async () => { compact = true; for (const notify of notifications) notify(); });
  expect(observers.size).toBe(0);
  expect(host.querySelector<HTMLDetailsElement>("details")!.open).toBe(true);
  expect(host.querySelector('[data-record="2"]')).toBe(record);
  expect(host.querySelector<HTMLElement>(".evidence-columns")!.style.transform).toBe("");
  await act(async () => { compact = false; for (const notify of notifications) notify(); });
  expect(observers.size).toBe(1);
  expect(host.querySelector<HTMLInputElement>(".evidence-page-number input")?.value).toBe("2");
  expect(host.querySelector<HTMLDetailsElement>("details")!.open).toBe(true);
  expect(host.querySelector('[data-record="2"]')).toBe(record);
});

it("navigates a large retained array by exact pointer without mounting its nested records", async () => {
  const value = { "a/b~c": Array.from({ length: 1500 }, (_, i) => ({ observed: i === 1499 ? null : i, status: "unresolved" })) };
  await act(async () => root!.render(<FieldNavigator value={value} />));
  expect(fieldPointer(["a/b~c", "1499", "observed"])).toBe("/a~1b~0c/1499/observed");
  expect(host.textContent).not.toContain("unresolved");
  await click(host.querySelector(".field-descend")!);
  await click(host.querySelector('[aria-label="Retained field /a~1b~0c"]')!);
  await click([...document.querySelectorAll('[role="option"]')].find(option => option.textContent === "[1499]")!);
  await click(host.querySelector(".field-descend")!);
  expect(host.querySelector(".field-pointer")?.textContent).toBe("/a~1b~0c/1499/observed");
  expect(host.querySelector(".field-value")?.textContent).toBe("null");
  await click(host.querySelector(".field-navigation button")!);
  expect(host.querySelector(".field-pointer")?.textContent).toBe("/a~1b~0c/1499");
  expect(host.querySelectorAll(".field-navigator")).toHaveLength(1);
});
