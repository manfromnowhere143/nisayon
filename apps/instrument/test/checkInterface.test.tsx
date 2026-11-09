import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Qualification } from "../src/qualification/Qualification";
import { inspectReview, isCheckBundle, type ReviewBundle } from "../src/qualification/checkBundle";

const client = vi.hoisted(() => ({ openReview: vi.fn() }));
vi.mock("../src/qualification/client", () => client);
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  vi.stubGlobal("crypto", { subtle: { digest: async (_: string, bytes: Uint8Array) => new Uint8Array(createHash("sha256").update(bytes).digest()).buffer } });
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.clearAllMocks(); });
async function retained(name: string) { return inspectReview(new Uint8Array(readFileSync(`test/fixtures/checks/${name}.nisayon.zip`)).buffer, `${name}.zip`); }
async function inspectRecord(name: string) { return inspectReview(new Uint8Array(readFileSync(`test/fixtures/inspect-checks/inspect-${name}.nisayon.zip`)).buffer, `${name}.zip`); }
async function click(label: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => !b.closest("[hidden]") && (b.textContent?.trim() === label || b.getAttribute("aria-label") === label));
  expect(button, label).toBeDefined(); await act(async () => button!.click());
}
function Harness({ initial }: { initial: ReviewBundle }) {
  const [bundle, setBundle] = useState<ReviewBundle | null>(initial);
  return <Qualification active bundle={bundle} setBundle={setBundle} develop={() => {}} />;
}
it("presents check reuse in the existing review surface with scoped saved claims", async () => {
  await act(async () => root.render(<Harness initial={await retained("rescored")} />));
  expect(host.querySelector('[data-decision="reject"]')).not.toBeNull();
  expect(host.textContent).toContain("Saved claim");
  expect(host.textContent).toContain("Bytes checked · saved SDK reconstruction");
  expect(host.querySelector(".is-unresolved")?.textContent).toBe("Unresolved");
  await click("Inspect observe: Reused");
  expect(host.querySelector("dialog")?.textContent).toContain("Reused · observation");
  expect(host.querySelector("dialog")?.textContent).toContain("does not establish a fresh physical experiment");
});
it("keeps historical simulation scope and unknown costs visible", async () => {
  await act(async () => root.render(<Harness initial={await retained("historical")} />));
  expect(host.querySelector(".review-question")?.textContent).toContain("Unconverged");
  await click("costs ↗");
  expect(host.querySelector("dialog")?.textContent).toContain("Complete cost remains unknown");
});
it.each(["unknown", "failed"])("retains %s checks with unresolved deployment", async name => {
  await act(async () => root.render(<Harness initial={await retained(name)} />));
  expect(host.querySelector('[data-decision="unresolved"]')).not.toBeNull();
  await click("Incomplete");
  expect(host.querySelectorAll(".probe-tile").length).toBeGreaterThan(0);
  expect(host.textContent).toContain("Not attempted");
});
it("retains a prior check review when a replacement fails", async () => {
  client.openReview.mockRejectedValue(new Error("Invalid execution authority"));
  await act(async () => root.render(<Harness initial={await retained("historical")} />));
  const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
  Object.defineProperty(input, "files", { configurable: true, value: [new File(["bad"], "bad.zip")] });
  await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("authority");
  expect(host.querySelector('[data-decision="supported"]')).not.toBeNull();
});
it("closes the detail when the instrument changes surface", async () => {
  const initial = await retained("rescored");
  await act(async () => root.render(<Qualification active bundle={initial} setBundle={() => {}} develop={() => {}} />));
  await click("Inspect observe: Reused");
  expect(host.querySelector("dialog")).not.toBeNull();
  await act(async () => root.render(<Qualification active={false} bundle={initial} setBundle={() => {}} develop={() => {}} />));
  expect(host.querySelector("dialog")).toBeNull();
});
it("renders hostile check results as text in the existing inspector", async () => {
  const initial = await retained("historical");
  if (!isCheckBundle(initial)) throw new Error("wrong fixture");
  initial.checks.find(c => c.id === "observe")!.result = '<img src=x onerror="alert(1)">';
  await act(async () => root.render(<Harness initial={initial} />));
  await click("Inspect observe: Executed"); await click("Saved result");
  expect(host.querySelector("img")).toBeNull();
  expect(host.querySelector("dialog")?.textContent).toContain("<img");
});
it("keeps the retained Inspect reuse visible in the existing check detail", async () => {
  await act(async () => root.render(<Harness initial={await inspectRecord("tolerance_only")} />));
  expect(host.querySelector(".review-question")?.textContent).toContain("Inspect Robots #572");
  expect(host.querySelector('[data-decision="supported"]')).not.toBeNull();
  await click("Inspect observe: Reused");
  expect(host.querySelector("dialog")?.textContent).toContain("Reused · observation");
});
it("retains the refused old observation after a supported fresh software check", async () => {
  await act(async () => root.render(<Harness initial={await inspectRecord("data_bytes")} />));
  await click("Inspect score: Executed"); await click("Saved result");
  let initial: HTMLButtonElement | undefined;
  for (let page = 0; page < 10; page++) {
    initial = [...host.querySelectorAll<HTMLButtonElement>(".record-field")].find(button => !button.closest("[hidden]") && button.querySelector("span")?.textContent === "initial");
    if (initial) break;
    await click("Next record page");
  }
  expect(initial).toBeDefined(); await act(async () => initial!.click());
  expect(host.querySelector("dialog")?.textContent).toContain("mismatched_fixture_sha256");
  expect(host.querySelector("dialog")?.textContent).toContain("invalid");
});
