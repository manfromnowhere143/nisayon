import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createHash } from "node:crypto";
import { afterEach, expect, it, vi } from "vitest";
import { StudyWorkspace } from "../src/ui/StudyWorkspace";
import { fetchFromDisk } from "./fixture";
import type { LoaderOptions } from "../src/data/loader";
import { discoverStudy, loadStudy, loadStudyReport } from "../src/data/study";
import { processorReport } from "../src/model/mechanisms";
import { DOCUMENT_EVIDENCE_QUERY } from "../src/ui/useDocumentEvidence";

const options: LoaderOptions = { fetch: fetchFromDisk(), digest: async bytes => createHash("sha256").update(new Uint8Array(bytes)).digest("hex"), maxBytes: 16 * 1024 * 1024 };
let root: Root | null = null, host: HTMLDivElement;
async function waitFor(predicate: () => boolean) {
  const deadline = Date.now() + 6000;
  while (!predicate()) { if (Date.now() > deadline) throw new Error("Study did not reach expected state"); await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); }); }
}
const click = async (element: Element) => { await act(async () => { element.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
afterEach(async () => { await act(async () => root?.unmount()); host?.remove(); root = null; vi.restoreAllMocks(); });

it("opens every processor section on mobile with complete witnesses and an always-available study exit", async () => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  vi.spyOn(window, "matchMedia").mockImplementation(query => ({ matches: query === DOCUMENT_EVIDENCE_QUERY, media: query, addEventListener() {}, removeEventListener() {} }) as unknown as MediaQueryList);
  const study = await loadStudy(await discoverStudy(undefined, options), undefined, options);
  const report = processorReport((await loadStudyReport(study.reports.processor!, undefined, options)).record);
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  const close = vi.fn();
  await act(async () => root!.render(<StudyWorkspace initialCase="development-ablation-001/D05-recurrent-carry/A" onClose={close} options={options} />));
  await waitFor(() => !!host.querySelector(".study-decision"));
  const choose = async (label: string, option: string) => {
    await click(host.querySelector(`[aria-label="${label}"]`)!);
    await click([...host.querySelectorAll('[role="option"]')].find(e => e.lastElementChild?.textContent === option)!);
  };
  const body = host.querySelector<HTMLElement>(".study-body")!;
  body.scrollTop = 500;
  await choose("Study instrument", "Processor correction");
  await waitFor(() => !!host.querySelector('[aria-label="Processor candidates"]'));
  expect(body.scrollTop).toBe(0);
  for (const section of ["Decision", "Witnesses", "Obligations", "Comparison", "Scope"]) {
    await choose("Processor evidence section", section);
    const flow = [...host.querySelectorAll('.evidence-flow')].find(e => e.getAttribute("aria-label") === `Processor evidence · ${section}`)!;
    expect(flow.closest("[hidden],[inert]"), section).toBeNull();
    expect(flow.getAttribute("data-evidence-layout"), section).toBe("document");
    expect(flow.querySelector(".evidence-columns")!.hasAttribute("inert"), section).toBe(false);
    expect(flow.querySelector(".evidence-columns")!.hasAttribute("aria-hidden"), section).toBe(false);
    if (section === "Witnesses") {
      const expected = report.executions.filter(e => e.candidate === "explicit_override");
      expect(flow.querySelectorAll(".processor-witnesses article")).toHaveLength(expected.length);
      expect(flow.textContent).toContain(String(expected.at(-1)!.source_pointer));
      const disclosure = flow.querySelector<HTMLDetailsElement>(".processor-witnesses article:last-child details")!;
      await act(async () => { disclosure.open = true; });
      expect(disclosure.closest("[hidden],[inert]")).toBeNull();
    }
    if (section === "Obligations") {
      const disclosure = flow.querySelector<HTMLDetailsElement>("details")!;
      await act(async () => { disclosure.open = true; });
      expect(flow.querySelectorAll("details p")).toHaveLength(report.obligations.length);
    }
  }
  expect(body.contains(host.querySelector('[aria-label="Close study"]'))).toBe(false);
  await click(host.querySelector('[aria-label="Close study"]')!);
  expect(close).toHaveBeenCalledOnce();
});

it("opens all retained assignments, keeps modal choices interactive, and exposes D05 rejection and external gaps", async () => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  const close = vi.fn();
  await act(async () => root!.render(<StudyWorkspace initialCase="development-ablation-001/D05-recurrent-carry/A" onClose={close} options={options} />));
  await waitFor(() => host.querySelector(".study-decision h3")?.textContent === "rejected");
  expect(host.querySelectorAll(".study-trial")).toHaveLength(26);
  expect(host.textContent).toContain("progress lost");
  expect(host.textContent).toContain("execution disconnected");
  await click([...host.querySelectorAll("button")].find(e => e.textContent === "Inspect decisive condition")!);
  expect(host.querySelector('[aria-label="Absolute progress obligation"]')?.textContent).toContain("Minimum 0.0100 m");
  expect(host.querySelector('[aria-label="Absolute progress obligation"]')?.textContent).toContain("Below minimum");
  const arm = host.querySelector('[aria-label="Study arm"]')!;
  await click(arm);
  expect(host.querySelector("dialog")!.contains(document.querySelector('[role="listbox"]'))).toBe(true);
  await click([...host.querySelectorAll('[role="option"]')].find(e => e.textContent?.includes("Arm B"))!);
  expect(host.querySelectorAll(".study-trial")).toHaveLength(13);
  await click([...host.querySelectorAll(".study-views button")].find(e => e.textContent === "External evidence")!);
  await waitFor(() => !!host.querySelector(".study-obligations"));
  expect(host.textContent).toContain("measurable with evaluator predicate");
  expect(host.textContent).toContain("not a new evaluation");
  await click(host.querySelector('[aria-label="Close study"]')!);
  expect(close).toHaveBeenCalledOnce();
});

it("keeps admitted evidence visible during a delayed trial change and ignores a superseded completion", async () => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); } });
  const study = await loadStudy(await discoverStudy(undefined, options), undefined, options);
  const delayed = study.trials.find(t => t.case_id === "D03-observation-backlog" && t.arm === "B")!;
  let release!: () => void;
  const delay = new Promise<void>(resolve => { release = resolve; });
  const delayedOptions: LoaderOptions = { ...options, fetch: async (input, init) => {
    if (String(input).includes(delayed.object.path)) await delay;
    return options.fetch(input, init);
  } };
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  await act(async () => root!.render(<StudyWorkspace initialCase="development-ablation-001/D05-recurrent-carry/A" onClose={() => {}} options={delayedOptions} />));
  await waitFor(() => host.querySelector(".study-decision h3")?.textContent === "rejected");
  const trialButton = (name: string, arm: string) => [...host.querySelectorAll(".study-trial")].find(e => e.textContent?.includes(name) && e.textContent?.includes(`arm ${arm}`))!;
  await click(trialButton("D03-observation-backlog", "B"));
  expect(host.querySelector(".study-detail")?.getAttribute("aria-busy")).toBe("true");
  expect(host.querySelector(".study-trial-heading h3")?.textContent).toBe("D05-recurrent-carry");
  expect(host.querySelector(".study-pending")?.textContent).toContain("D03-observation-backlog");
  await click(trialButton("D01-gripper-sign", "A"));
  await waitFor(() => host.querySelector(".study-trial-heading h3")?.textContent === "D01-gripper-sign");
  await act(async () => { release(); await delay; await new Promise(resolve => setTimeout(resolve, 20)); });
  expect(host.querySelector(".study-trial-heading h3")?.textContent).toBe("D01-gripper-sign");
  expect(host.querySelector(".study-decision h3")?.textContent).toBe("accepted");
  expect(host.querySelector(".study-detail")?.getAttribute("aria-busy")).toBe("false");
});
