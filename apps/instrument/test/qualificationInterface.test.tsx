import { act, StrictMode, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { join } from "node:path";
import { REPO_ROOT } from "./fixture";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Qualification, RecordExplorer } from "../src/qualification/Qualification";
import type { ReviewBundle } from "../src/qualification/checkBundle";
import { inspectBundle } from "../src/qualification/bundle";
import { parseRecord } from "../src/qualification/json";

const client = vi.hoisted(() => ({ openReview: vi.fn() }));
vi.mock("../src/qualification/client", () => client);
let host: HTMLDivElement, root: Root;
beforeEach(() => {
  vi.stubGlobal("crypto", { subtle: { digest: async (_algorithm: string, bytes: Uint8Array) => new Uint8Array(createHash("sha256").update(new Uint8Array(bytes)).digest()).buffer } });
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.clearAllMocks(); });
async function retained(name = "restored-defect") { return inspectBundle(new Uint8Array(readFileSync(join(REPO_ROOT, "apps/instrument/test/fixtures/qualification", `${name}.nisayon.zip`))).buffer, `${name}.nisayon.zip`); }
async function click(label: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => !b.closest("[hidden]") && (b.textContent?.trim() === label || b.getAttribute("aria-label") === label));
  expect(button, label).toBeDefined(); await act(async () => button!.click());
}
function Harness({ initial }: { initial: ReviewBundle | null }) {
  const [bundle, setBundle] = useState<ReviewBundle | null>(initial);
  return <Qualification active bundle={bundle} setBundle={setBundle} develop={() => {}} />;
}
it.each([['accepted', 'passing example', 'adopt'], ['rejected', 'detected defect', 'reject']])("opens the public %s SDK example through the local review reader", async (name, label, decision) => {
  const raw = readFileSync(join(REPO_ROOT, "apps/instrument/test/fixtures/qualification", `sdk-v2-${name}.nisayon.zip`));
  const fetcher = vi.fn().mockResolvedValue({ ok: true, arrayBuffer: async () => new Uint8Array(raw).buffer });
  vi.stubGlobal("fetch", fetcher);
  client.openReview.mockResolvedValue(await retained(`sdk-v2-${name}`));
  await act(async () => root.render(<Harness initial={null} />));
  await click(`Inspect a ${label}`);
  expect(fetcher).toHaveBeenCalledWith(`/examples/qualification/${name}.nisayon.zip`, expect.objectContaining({ signal: expect.any(AbortSignal) }));
  expect(client.openReview.mock.calls[0]![0].name).toBe(`${name}.nisayon.zip`);
  expect(host.querySelector(`[data-decision="${decision}"]`)).not.toBeNull();
  expect(host.querySelector(".is-unresolved")?.textContent).toBe("Unresolved");
  expect(host.querySelector('.review-message[role="status"]')).toBeNull();
});
it("keeps local import available when a public example cannot be fetched", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
  await act(async () => root.render(<Harness initial={null} />));
  await click("Inspect a passing example");
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("still open a local review");
  expect(host.querySelector('input[type="file"]')).not.toBeNull();
  expect(client.openReview).not.toHaveBeenCalled();
});
it("cancels a public example fetch without reporting an import failure", async () => {
  const fetcher = vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => options.signal!.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")))));
  vi.stubGlobal("fetch", fetcher);
  await act(async () => root.render(<Harness initial={null} />));
  await click("Inspect a passing example");
  await click("Cancel");
  expect(fetcher.mock.calls[0]![1].signal!.aborted).toBe(true);
  expect(host.querySelector('[role="alert"]')).toBeNull();
  expect(host.querySelector('[role="status"]')).toBeNull();
  expect(client.openReview).not.toHaveBeenCalled();
});
it("shows the saved rejection, keeps deployment unresolved and traces the actual first difference", async () => {
  await act(async () => root.render(<Harness initial={await retained()} />));
  expect(host.querySelector('[data-decision="reject"]')?.textContent).toBe("reject");
  expect(host.querySelector(".is-unresolved")?.textContent).toBe("Unresolved");
  expect(host.textContent).toContain("Bytes checked · saved assessment");
  await click("Differences");
  expect(host.querySelectorAll('.probe-tile[data-result="Differs"]')).toHaveLength(13);
  await act(async () => host.querySelector<HTMLButtonElement>(".probe-tile")!.click());
  expect(host.querySelector("dialog")?.textContent).toContain("/accepted");
  expect([...host.querySelectorAll(".comparison-values code")].map(n => n.textContent)).toEqual(["true", "false"]);
  await click("Original records");
  await click("Comparison record");
  expect(document.querySelector('[role="listbox"]')?.textContent).toContain("candidate · observation");
});
it("keeps the previous verified package when a replacement cannot be opened", async () => {
  client.openReview.mockRejectedValue(new Error("The package cannot verify assessment.json."));
  await act(async () => root.render(<Harness initial={await retained("merged")} />));
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { configurable: true, value: [new File(["bad"], "bad.zip")] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("cannot verify");
  expect(host.querySelector('[data-decision="adopt"]')).not.toBeNull();
  expect(host.querySelectorAll(".probe-tile")).toHaveLength(22);
});
it("cancels pending import without replacing the current evidence", async () => {
  client.openReview.mockImplementation((_file, signal: AbortSignal) => new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")))));
  await act(async () => root.render(<Harness initial={await retained("merged")} />));
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { configurable: true, value: [new File(["pending"], "pending.zip")] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  await click("Cancel");
  expect(client.openReview.mock.calls[0]![1].aborted).toBe(true);
  expect(host.querySelector('[data-decision="adopt"]')).not.toBeNull();
  expect(host.querySelector('[role="alert"]')).toBeNull();
});
it("ignores late results and progress when a later import replaces an earlier request", async () => {
  const pending: { resolve: (value: ReviewBundle) => void; signal: AbortSignal; progress: (message: string) => void }[] = [];
  client.openReview.mockImplementation((_file, signal, progress) => new Promise(resolve => pending.push({ resolve, signal, progress })));
  await act(async () => root.render(<Harness initial={null} />));
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  for (const name of ["earlier.zip", "later.zip"]) {
    Object.defineProperty(input, "files", { configurable: true, value: [new File([name], name)] });
    await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  }
  expect(pending[0]!.signal.aborted).toBe(true);
  await act(async () => pending[1]!.resolve(await retained("sdk-v2-rejected")));
  await act(async () => { pending[0]!.progress("Old request still reading"); pending[0]!.resolve(await retained("sdk-v2-accepted")); });
  expect(host.querySelector('[data-decision="reject"]')).not.toBeNull();
  expect(host.querySelector('.review-message[role="status"]')).toBeNull();
  expect(host.textContent).not.toContain("Old request");
});
it("cancels on navigation and leaves a later reopened import independent", async () => {
  const pending: { resolve: (value: ReviewBundle) => void; signal: AbortSignal; progress: (message: string) => void }[] = [];
  client.openReview.mockImplementation((_file, signal, progress) => new Promise(resolve => pending.push({ resolve, signal, progress })));
  const setBundle = vi.fn();
  const render = async (active: boolean) => act(async () => root.render(<Qualification active={active} bundle={null} setBundle={setBundle} develop={() => {}} />));
  await render(true);
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { configurable: true, value: [new File(["data"], "first.zip")] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  await render(false);
  expect(pending[0]!.signal.aborted).toBe(true);
  await render(true);
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  await act(async () => { pending[0]!.progress("Late progress"); pending[0]!.resolve(await retained()); });
  expect(setBundle).not.toHaveBeenCalled();
  await act(async () => pending[1]!.resolve(await retained("sdk-v2-accepted")));
  expect(setBundle).toHaveBeenCalledOnce();
  expect(host.querySelector('[role="status"]')).toBeNull();
});
it("opens the hero's real example through Strict Mode and consumes it only after the current read", async () => {
  const consumed = vi.fn(), selected = vi.fn();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) }));
  client.openReview.mockResolvedValue(await retained("sdk-v2-rejected"));
  await act(async () => root.render(<StrictMode><Qualification active bundle={null} setBundle={selected} develop={() => {}} initialExample="rejected" onExampleConsumed={consumed} /></StrictMode>));
  expect(selected).toHaveBeenCalledOnce();
  expect(consumed).toHaveBeenCalledOnce();
  expect(selected.mock.calls[0]![0].assessment.software_decision).toBe("reject");
});
it("lets the reviewer reach every numeric byte and renders hostile values as text", async () => {
  const record = parseRecord('{"number":9007199254740993,"zero":-0.0,"html":"<img src=x onerror=alert(1)>"}');
  await act(async () => root.render(<RecordExplorer value={record} />));
  await act(async () => host.querySelector<HTMLButtonElement>(".record-field")!.click());
  expect(host.querySelector(".record-value")?.textContent).toBe("9007199254740993");
  await click("← Back");
  await act(async () => host.querySelectorAll<HTMLButtonElement>(".record-field")[1]!.click());
  expect(host.querySelector(".record-value")?.textContent).toBe("-0.0");
  await click("← Back");
  await act(async () => host.querySelectorAll<HTMLButtonElement>(".record-field")[2]!.click());
  expect(host.querySelector("img")).toBeNull();
  expect(host.querySelector(".record-value")?.textContent).toContain("<img");
});
