import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createHash } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";
import { openCase, openGeneration, openRun, ResourceCache, type LoaderOptions } from "../src/data/loader";
import { CaseBrief } from "../src/ui/CaseBrief";
import { fetchFromDisk } from "./fixture";

const options: LoaderOptions = {
  fetch: fetchFromDisk(),
  digest: async (bytes) => createHash("sha256").update(Buffer.from(new Uint8Array(bytes))).digest("hex"),
  maxBytes: 16 * 1024 * 1024,
};
let root: Root | undefined;
let host: HTMLDivElement;
afterEach(async () => { if (root) await act(async () => root!.unmount()); host?.remove(); root = undefined; });

async function load(id = "D01-gripper-sign") {
  const cache = new ResourceCache();
  const { generation } = await openGeneration(`http://fixture.test/fixtures/ui/recorded/${id}/evidence.json`, undefined, options);
  const caseRecord = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = await openRun(generation, caseRecord, caseRecord.runs.find((r) => r.role === "regression")!.run, undefined, options, cache);
  return { generation, caseRecord, run };
}

async function render(props: Awaited<ReturnType<typeof load>>) {
  const navigate = vi.fn();
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  await act(async () => root!.render(<CaseBrief {...props} onNavigate={navigate} />));
  return navigate;
}

describe("source-derived case brief", () => {
  it("keeps a completed execution separate from task failure and links the exact retained sources", async () => {
    const loaded = await load();
    const navigate = await render(loaded);
    expect(host.querySelector(".case-brief-status")!.textContent).toBe("ExecutioncompletedMeasurementobservedTask outcomefailed");
    expect(host.querySelector(".case-brief-finding h3")!.textContent).toBe("Gripper command reversed at step 0.");
    expect(host.querySelector(".case-brief-scope")!.textContent).toContain("Both original development comparisons found no decision or efficiency advantage.");
    expect(host.textContent).toContain("Recorded simulation, not a live robot or a new experiment.");
    expect(host.querySelector(".case-brief-more")!.hasAttribute("hidden")).toBe(true);
    await act(async () => host.querySelector<HTMLButtonElement>(".case-brief-sources button")!.click());
    expect(host.querySelector(".case-brief-more")!.hasAttribute("hidden")).toBe(false);
    expect(host.querySelectorAll('.case-brief-more > details')).toHaveLength(3);
    expect(host.querySelectorAll('.case-brief-more > details[open]')).toHaveLength(1);
    expect(host.querySelector('.case-brief-detail')!.textContent).toContain("−1.000135");
    const links = Array.from(host.querySelectorAll<HTMLAnchorElement>(".case-brief-sources a"));
    expect(links[0]!.href).toBe(loaded.generation.manifestUrl);
    expect(links[1]!.href).toBe(new URL(loaded.run.record.samples.path, loaded.generation.baseUrl).href);
    const samples = await options.fetch(links[1]!.href);
    expect(await options.digest(await samples.arrayBuffer())).toBe(loaded.run.record.samples.sha256);
    await act(async () => Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.startsWith("Compare runs"))!.click());
    expect(navigate).toHaveBeenCalledWith("fork");
  });

  it("does not invent confirmation or acceptance when a record is absent or its decision is not embedded", async () => {
    const loaded = await load();
    loaded.caseRecord = { ...loaded.caseRecord, decisions: { diagnostic_decision: { ...loaded.caseRecord.decisions.diagnostic_decision!, content: {} }, confirmation_decision: null } };
    await render(loaded);
    expect(host.querySelector(".case-brief-decisions dl")!.textContent).toBe("Diagnosticnot embeddedSeparate confirmationnot referenced");
  });

  it.each(["D06-stateless-inference", "D08-old-future-replay", "D10-opaque-policy-state"])("preserves the unresolved decision for %s", async (id) => {
    await render(await load(id));
    expect(host.querySelector(".case-brief-decisions dl > div:first-child dd")!.textContent).toBe("unresolved");
    expect(host.textContent).not.toContain("undefined");
    if (id === "D10-opaque-policy-state") expect(host.querySelector(".case-brief-finding h3")!.textContent).toBe("Policy state was not recorded.");
  });
});
