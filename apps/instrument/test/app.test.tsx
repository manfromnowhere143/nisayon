// DOM-level agreement checks: what the caption, transport and inspector say
// about the selected moment must be the same generation, run, row, phase and
// clock. jsdom has no WebGL, so this also exercises the SVG fallback path.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createHash } from "node:crypto";
import { App } from "../src/App";
import type { LoaderOptions } from "../src/data/loader";
import { fetchFromDisk } from "./fixture";

const options: LoaderOptions = {
  fetch: fetchFromDisk(),
  // jsdom and Node realms differ; hash through Node's own buffer type.
  digest: async (bytes) => createHash("sha256").update(Buffer.from(new Uint8Array(bytes))).digest("hex"),
  maxBytes: 64 * 1024 * 1024,
};

let container: HTMLDivElement | undefined;
let root: Root | undefined;

async function mount(search: string, readings = true): Promise<void> {
  if (root) { await act(async () => root!.unmount()); container?.remove(); }
  window.history.replaceState(null, "", `${window.location.origin}/${search}`);
  const el = document.createElement("div");
  document.body.appendChild(el);
  container = el;
  const r = createRoot(el);
  root = r;
  await act(async () => {
    r.render(<App loader={options} />);
  });
  await waitFor(() => container!.querySelector(".transport") !== null || container!.querySelector(".state") !== null);
  // Analysis is now an explicit centered surface; preserve the existing
  // evidence-agreement controls by opening it through its public affordance.
  const evidence = container!.querySelector<HTMLButtonElement>('.workspace-actions button');
  if (evidence) await act(async () => evidence.click());
  if (readings && container!.querySelector('.case-brief')) await act(async () => {
    Array.from(container!.querySelectorAll<HTMLButtonElement>('.analysis-tab')).find((button) => button.textContent === "Readings")!.click();
  });
}

async function waitFor(predicate: () => boolean, timeout = 4000): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeout) throw new Error("timed out waiting for the DOM");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
  }
}

function text(selector: string): string {
  return container!.querySelector(selector)?.textContent?.replace(/\s+/g, " ").trim() ?? "";
}

async function press(key: string, extra: Partial<KeyboardEventInit> = {}): Promise<void> {
  await act(async () => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, ...extra }));
  });
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(async () => {
  const r = root;
  if (r) {
    await act(async () => {
      r.unmount();
    });
  }
  container?.remove();
  root = undefined;
  container = undefined;
});

describe("the instrument in a DOM", () => {
  it("opens a case brief without changing the moment, then moves focus to the requested reading view", async () => {
    await mount("", false);
    const selected = window.location.search;
    expect(container!.querySelector(".case-brief")).not.toBeNull();
    expect(text(".scene-heading")).toContain("RECORDED SIMULATION");
    const inspect = Array.from(container!.querySelectorAll<HTMLButtonElement>(".case-brief button")).find((button) => button.textContent?.startsWith("Inspect readings"))!;
    inspect.focus();
    await act(async () => inspect.click());
    expect(container!.querySelector(".case-brief")).toBeNull();
    expect(document.activeElement?.textContent).toBe("Readings");
    expect(window.location.search).toBe(selected);
  });

  it("keeps a deep-linked comparison open instead of replacing it with a brief", async () => {
    await mount("?d=fork", false);
    expect(container!.querySelector(".case-brief")).toBeNull();
    expect(text(".depth-title")).toBe("Compare");
    expect(new URLSearchParams(window.location.search).get("d")).toBe("fork");
  });

  it("opens the computed first mismatch of the regression run and pins it in the URL", async () => {
    await mount("");
    expect(text(".finding-headline")).toBe("Gripper command reversed at step 0.");
    expect(text(".transport-row")).toBe("row 0");
    expect(text(".transport-time")).toBe("0.05 s");
    const params = new URLSearchParams(window.location.search);
    expect(params.get("r")).toBe("regression-0");
    expect(params.get("i")).toBe("0");
    expect(params.get("p")).toBe("after");
    expect(params.get("g")).toMatch(/^[0-9a-f]{64}$/);
    expect(container!.querySelector(".chip-warn")).toBeNull();
    expect(text(".identity-case")).toBe("D01-gripper-sign · arm B");
    expect(container!.querySelector(".scene-box")?.getAttribute("data-mode")).toBe("webgl-unavailable");
    expect(container!.querySelector(".schematic-svg")).toBeNull();
    expect(container!.querySelector(".scene-recovery")?.textContent).toContain("Retry detailed lab");
  });

  it("keeps display, transport and inspector on the same row, phase and clock", async () => {
    await mount("");
    await press("ArrowRight");
    await press("ArrowRight");
    await press("p");
    expect(text(".transport-row")).toBe("row 2");
    expect(text(".transport-time")).toBe("0.10 s");
    expect(text(".scene-caption .num")).toBe("before · 0.10 s");
    await press("i");
    const inspector = container!.querySelector("#inspector");
    expect(inspector).not.toBeNull();
    const facts = Array.from(inspector!.querySelectorAll(".facts > div")).map((d) => d.textContent?.replace(/\s+/g, " ").trim() ?? "");
    expect(facts.find((f) => f.startsWith("row"))).toContain("2 (step 2) of 0 to 399");
    expect(facts.find((f) => f.startsWith("phase"))).toContain("before the action");
    expect(facts.find((f) => f.startsWith("clock"))).toContain("simulation · 0.100000 s");
    expect(facts.find((f) => f.startsWith("run"))).toContain("regression-0");
    const params = new URLSearchParams(window.location.search);
    expect(params.get("i")).toBe("2");
    expect(params.get("p")).toBe("before");
  });

  it("returns keyboard focus to the inspector opener without changing the moment", async () => {
    await mount("");
    await act(async () => container!.querySelector<HTMLButtonElement>(".glass-card-close")!.click());
    const opener = container!.querySelector<HTMLButtonElement>('.tbtn[aria-controls="inspector"]')!;
    expect(opener).not.toBeNull();
    opener.focus();
    await act(async () => opener.click());
    // The visible modal title owns focus; the embedded inspector's duplicate
    // heading is hidden. Keyboard focus must stay on the named dialog title.
    const dialog = container!.querySelector("#inspector")!.closest("dialog")!;
    const title = dialog.querySelector(".glass-card-header h2")!;
    expect(title.textContent).toBe("Source inspector");
    expect(dialog.getAttribute("aria-labelledby")).toBe(title.id);
    expect(document.activeElement).toBe(title);
    expect(title.getAttribute("data-pointer-focus")).toBeNull();
    const selected = window.location.search;
    await act(async () => dialog.dispatchEvent(new Event("cancel", { cancelable: true })));
    expect(container!.querySelector("#inspector")).toBeNull();
    expect(document.activeElement).toBe(opener);
    expect(window.location.search).toBe(selected);
  });

  it("switches to an actual aligned sample, reports a shorter recording and reloads the same view", async () => {
    await mount("");
    await press("End");
    expect(text(".transport-row")).toBe("row 399");
    await press("r");
    await waitFor(() => new URLSearchParams(window.location.search).get("r") !== "regression-0");
    const selected = new URLSearchParams(window.location.search).get("r");
    expect(selected).not.toBe("regression-0");
    expect(new URLSearchParams(window.location.search).get("i")).toBe("43");
    expect(text(".selection-note")).toContain("No sample at 20.00 s");
    expect(text(".transport-time")).toBe("2.20 s");
    const query = window.location.search;
    await mount(query);
    expect(text(".transport-time")).toBe("2.20 s");
    expect(text(".transport-row")).toBe("row 43");
  });

  it("opens Compare with the paired run as a ghost and preserves the fork locator", async () => {
    await mount("");
    await act(async () => {
      (Array.from(container!.querySelectorAll(".depth-open")).find((b) => b.textContent?.startsWith("Compare")) as HTMLButtonElement).click();
    });
    await waitFor(() => text(".depth-lede").includes("ghost"));
    expect(new URLSearchParams(window.location.search).get("d")).toBe("fork");
    expect(text(".depth-lede")).toContain("reference-0");
    await act(async () => { Array.from(container!.querySelectorAll<HTMLButtonElement>(".section-tab")).find((button) => button.textContent === "Aligned signals")!.click(); });
    expect(container!.querySelectorAll(".lane-ghost").length).toBe(2);
    await act(async () => {
      window.history.back();
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await waitFor(() => container!.querySelector(".depth") === null);
    expect(text(".transport-row")).toBe("row 0");
  });

  it("refuses an out-of-range row and offers the computed default explicitly", async () => {
    await mount("?i=900");
    expect(container!.querySelector(".state-invalid")).not.toBeNull();
    const problems = Array.from(container!.querySelectorAll(".state-body li")).map((li) => li.textContent ?? "");
    expect(problems.some((p) => p.includes("row 900 is outside"))).toBe(true);
    await act(async () => {
      (container!.querySelector(".state-actions button") as HTMLButtonElement).click();
    });
    await waitFor(() => container!.querySelector(".transport") !== null);
    expect(text(".transport-row")).toBe("row 0");
  });

  it("reports corrupt bytes of another run as a notice and keeps the verified run displayed", async () => {
    // The tampered file is reference-0's samples; regression-0 verifies and opens normally.
    await mount("?evidence=dev-fixture-corrupt-child%2Fevidence.json");
    expect(text(".transport-row")).toBe("row 0");
    const reference = Array.from(container!.querySelectorAll(".segment")).find((b) => b.textContent?.includes("reference-0")) as HTMLButtonElement;
    await act(async () => {
      reference.click();
    });
    await waitFor(() => container!.querySelector(".notice") !== null);
    expect(text(".notice")).toContain("Integrity check failed");
    expect(text(".notice")).toContain("reference-0.samples.json");
    expect(new URLSearchParams(window.location.search).get("r")).toBe("regression-0");
    expect(text(".finding-headline")).toBe("Gripper command reversed at step 0.");
  });

  it("shows a wrong root digest as an integrity state with both digests and no readings", async () => {
    await mount("?evidence=dev-fixture-wrong-root%2Fevidence.json");
    expect(container!.querySelector(".state-error")).not.toBeNull();
    expect(text(".state-kicker")).toBe("manifest · integrity");
    expect(text(".state-error")).toContain("expected");
    expect(container!.querySelector(".transport")).toBeNull();
  });

  it("keeps original readings when frames are missing", async () => {
    await mount("?evidence=dev-fixture-missing-frames%2Fevidence.json&i=3");
    // The default run is regression-0, whose frames exist in this variant; reference-0's frames file is the missing one.
    expect(text(".transport-row")).toBe("row 3");
    const reference = Array.from(container!.querySelectorAll(".segment")).find((b) => b.textContent?.includes("reference-0")) as HTMLButtonElement;
    await act(async () => {
      reference.click();
    });
    await waitFor(() => text(".scene-unavailable-title") === "Reconstruction unavailable");
    expect(new URLSearchParams(window.location.search).get("r")).toBe("reference-0");
    expect(text(".transport-row")).toBe("row 3");
    expect(text(".transport-time")).toBe("0.20 s");
    expect(container!.querySelector(".lane")).not.toBeNull();
  });
});

describe("depths that read the frozen records", () => {
  it("says when a generation carries no confirmation instead of inventing pairs", async () => {
    await mount("?evidence=fixtures/ui/d01/evidence.json&d=conditions");
    await waitFor(() => container!.querySelector(".depth") !== null);
    expect(text(".depth-lede")).toContain("No paired conditions are referenced in this generation");
    expect(text(".depth-lede")).toContain("not_in_this_generation");
    expect(container!.querySelector(".cond-field")).toBeNull();
  });

  it("renders the paired-conditions field from the referenced confirmation record and pins the selected pair", async () => {
    await mount("?evidence=dev-fixture%2Fevidence.json&d=conditions");
    await waitFor(() => container!.querySelector(".cond-field") !== null);
    const marks = container!.querySelectorAll(".cond");
    expect(marks.length).toBe(33);
    expect(text(".depth-lede")).toContain("33 paired conditions");
    const target = Array.from(marks).find((m) => m.getAttribute("aria-label")?.startsWith("seed-10000,")) as HTMLButtonElement;
    await act(async () => {
      target.click();
    });
    expect(new URLSearchParams(window.location.search).get("k")).toBe("seed-10000");
    const facts = Array.from(container!.querySelectorAll(".facts > div")).map((d) => d.textContent?.replace(/\s+/g, " ").trim() ?? "");
    expect(facts.some((f) => f.startsWith("verdict"))).toBe(true);
    expect(facts.find((f) => f.startsWith("condition id"))).toContain("seed-10000");
    // The moment itself did not move.
    expect(text(".transport-row")).toBe("row 0");
    await act(async () => {
      window.history.back();
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await waitFor(() => new URLSearchParams(window.location.search).get("k") === null);
    expect(container!.querySelector(".cond.is-selected")).toBeNull();
  });

  it("draws the memory digest-equality lane in Fork and names the divergence row", async () => {
    await mount("?d=fork");
    await act(async () => { Array.from(container!.querySelectorAll<HTMLButtonElement>(".section-tab")).find((button) => button.textContent === "Aligned signals")!.click(); });
    await waitFor(() => container!.querySelector(".lane-memory") !== null);
    const label = container!.querySelector(".lane-memory")?.getAttribute("aria-label") ?? "";
    expect(label).toContain("regression-0 and reference-0");
    expect(label).toContain("diverge from row 1");
    expect(container!.querySelectorAll(".mem-none").length).toBe(1);
  });

  it("shows the literal evaluator reasons of the verified decision object in Decision", async () => {
    await mount("?evidence=fixtures/ui/d01/evidence.json&d=decision");
    await waitFor(() => container!.querySelector(".decision-block") !== null);
    const blocks = Array.from(container!.querySelectorAll(".decision-block")).map((b) => b.textContent?.replace(/\s+/g, " ") ?? "");
    expect(blocks[0]).toContain("unresolved");
    expect(blocks[0]).toContain("confirmation_missing");
    expect(blocks[0]).toContain("no frozen candidate confirmed");
    expect(blocks[1]).toContain("No record referenced");
    const entry = Array.from(container!.querySelectorAll(".decision-run")).map((d) => d.textContent?.replace(/\s+/g, " ") ?? "").find((t) => t.includes("Evaluator entry")) ?? "";
    expect(entry).toContain("regression-0");
    expect(entry).toContain("lost");
  });

  it("shows both decisions verbatim for the development fixture", async () => {
    await mount("?evidence=dev-fixture%2Fevidence.json&d=decision");
    await waitFor(() => container!.querySelector(".decision-block") !== null);
    const blocks = Array.from(container!.querySelectorAll(".decision-block")).map((b) => b.textContent?.replace(/\s+/g, " ") ?? "");
    expect(blocks[0]).toContain("unresolved");
    expect(blocks[0]).toContain("confirmation_missing");
    expect(blocks[1]).toContain("accepted");
    expect(blocks[1]).toContain("32 of 32 declared fresh conditions");
    const trial = Array.from(container!.querySelectorAll(".decision-run")).map((d) => d.textContent?.replace(/\s+/g, " ") ?? "").find((t) => t.includes("Trial record")) ?? "";
    expect(trial).toContain("confirmed");
    expect(trial).toContain("67");
    expect(trial).toContain("trial.json");
  });

  it("expands the observation-age lane on request", async () => {
    await mount("");
    expect(container!.querySelectorAll(".lane").length).toBe(2);
    await act(async () => {
      (Array.from(container!.querySelectorAll(".lanes-more .quiet"))[0] as HTMLButtonElement).click();
    });
    expect(container!.querySelectorAll(".lane").length).toBe(4);
    const label = Array.from(container!.querySelectorAll(".lane")).at(-1)?.getAttribute("aria-label") ?? "";
    expect(label).toContain("declared maximum 1e-9 s");
    expect(label).toContain("0 rows exceed it");
  });
});

describe("interrupted transitions", () => {
  it("refuses an invalid same-run row received through browser history", async () => {
    await mount("");
    const search = new URLSearchParams(location.search);
    search.set("i", "9999");
    history.pushState(null, "", `?${search}`);
    await act(async () => window.dispatchEvent(new PopStateEvent("popstate")));
    await waitFor(() => container!.querySelector(".state-invalid") !== null);
    expect(text(".state-body")).toContain("row 9999 is outside");
    expect(container!.querySelector(".transport")).toBeNull();
  });

  it("switches to D05, exposes the exact 10423 reason and opens its paired execution", async () => {
    await mount("?evidence=fixtures/ui/recorded/D05-recurrent-carry/evidence.json&d=conditions");
    await waitFor(() => container!.querySelector(".cond-field") !== null);
    const target = container!.querySelector('button[aria-label^="seed-10423-prefix-10-21,"]') as HTMLButtonElement;
    expect(target).not.toBeNull();
    await act(async () => target.click());
    expect(text(".depth")).toContain("gain 0.002936 m is below the minimum 0.01");
    expect(text(".depth")).toContain("no sample locator");
    const inspect = Array.from(container!.querySelectorAll(".depth-actions button")).find((b) => b.textContent?.includes("confirmation-correction-10423")) as HTMLButtonElement;
    await act(async () => inspect.click());
    await waitFor(() => text(".depth-anchor").includes("confirmation-correction-10423") && text(".scene-caption").includes("confirmation-reference-10423"));
    expect(text(".transport-row")).toBe("row 0");
    expect(new URLSearchParams(location.search).get("b")).toBe("3c9ccd073556053f3900f240b85972b5f657138b1b1e8e62dda8d841959b2b0b");
    await act(async () => history.back());
    await waitFor(() => text(".depth-title") === "Conditions");
    expect(new URLSearchParams(location.search).get("k")).toBe("seed-10423-prefix-10-21");
  });

  it("keeps early links bound to the original D01 root", async () => {
    await mount("?g=0ee415adfbca09e60a090a2f545c4e9d1193cc8a057a7648b1486148207e93c7&i=344&p=after");
    expect(text(".transport-row")).toBe("row 344");
    expect(text(".transport-time")).toBe("17.25 s");
    expect(new URLSearchParams(location.search).get("evidence")).toBeNull();
  });
  it("settles on the last of several rapid run selections and never shows an intermediate run", async () => {
    await mount("");
    const buttons = Array.from(container!.querySelectorAll(".segment")) as HTMLButtonElement[];
    const byId = (id: string) => buttons.find((b) => b.textContent?.includes(id))!;
    await act(async () => {
      byId("reference-0").click();
      byId("correction-exploration-0").click();
      byId("reference-0").click();
      byId("regression-0").click();
      byId("correction-exploration-0").click();
    });
    await waitFor(() => {
      const s = (window as unknown as { __nisayon: { store: { getState(): { screen: { kind: string; pendingRun: unknown } } } } }).__nisayon.store.getState().screen;
      return s.kind === "ready" && s.pendingRun === null;
    });
    expect(new URLSearchParams(window.location.search).get("r")).toBe("correction-exploration-0");
    expect(text(".finding-status")).toContain("task completed");
    expect(text(".transport-row")).toBe("row 0");
  });

  it("keeps the selected moment through a ground change and a resize", async () => {
    await mount("?i=7&p=before");
    await press("t");
    expect(document.documentElement.getAttribute("data-ground")).toBe("paper");
    await act(async () => {
      window.dispatchEvent(new Event("resize"));
    });
    expect(text(".transport-row")).toBe("row 7");
    expect(new URLSearchParams(window.location.search).get("p")).toBe("before");
    await press("t");
    expect(document.documentElement.getAttribute("data-ground")).toBe("black");
  });
});


describe("recorded updates and selected readings", () => {
  it("discovers the current export while keeping the historical moment pinned", async () => {
    const pin = "0ee415adfbca09e60a090a2f545c4e9d1193cc8a057a7648b1486148207e93c7";
    const query = `?g=${pin}&c=development-ablation-001%2FD01-gripper-sign%2FB&b=373e33e88bd43538a56ce7cf111e5db10519a0afe4f9bc5ae46340e4502d856a&r=regression-0&i=344&p=before`;
    await mount(query);
    await act(async () => container!.querySelector<HTMLButtonElement>('[aria-label="Workspace controls"]')!.click());
    await waitFor(() => container!.querySelector(".export-update") !== null);
    const before = window.location.search;
    const store = (window as unknown as { __nisayon: { store: import("../src/state/store").InstrumentStore } }).__nisayon.store;
    await act(async () => { await store.refreshLibrary(); });
    expect(window.location.search).toBe(before);
    expect(text(".transport-row")).toBe("row 344");
    expect(text(".scene-caption .num")).toBe("before · 17.20 s");
    await act(async () => { (container!.querySelector(".export-update") as HTMLButtonElement).click(); });
    await waitFor(() => new URLSearchParams(location.search).get("g") !== pin);
    const published = await options.fetch("http://fixture.test/fixtures/ui/recorded/D01-gripper-sign/evidence.json").then(r => r.json()) as { manifest: { sha256: string } };
    expect(new URLSearchParams(location.search).get("g")).toBe(published.manifest.sha256);
    await act(async () => { history.back(); });
    await waitFor(() => text(".transport-row") === "row 344");
    expect(new URLSearchParams(location.search).get("g")).toBe(pin);
  });
  it("keeps action time and post-action reading time explicit as the selected row moves", async () => {
    await mount("");
    await press("ArrowRight");
    await press("ArrowRight");
    await press("p");
    const readings = Array.from(container!.querySelectorAll(".selected-readings > div")).map((node) => node.textContent);
    expect(readings[0]).toContain("0.10 s");
    expect(readings[2]).toContain("0.15 s");
    expect(text(".scene-caption .num")).toBe("before · 0.10 s");
  });
  it("uses the D03 age finding for the transport event shortcut", async () => {
    await mount("?evidence=fixtures%2Fui%2Frecorded%2FD03-observation-backlog%2Fevidence.json");
    await press("End");
    await press("m");
    expect(text(".transport-row")).toBe("row 1");
    expect(text(".finding-detail")).toContain("50 ms");
  });
});


describe("bounded dashboard records", () => {
  const visible = (element: Element): boolean => !element.closest("[hidden]");
  async function clickVisible(label: string): Promise<void> {
    const button = Array.from(container!.querySelectorAll<HTMLButtonElement>("button")).find((button) => visible(button) && (button.getAttribute("aria-label") === label || button.textContent?.trim() === label));
    expect(button, `visible button ${label}`).toBeDefined();
    await act(async () => button!.click());
  }

  it("retains every exact D10 finding in the fitted surface and full reading without moving the moment", async () => {
    await mount("?evidence=fixtures/ui/recorded/D10-opaque-policy-state/evidence.json&d=decision");
    const row = text(".transport-row");
    await clickVisible("Evaluator · 7");
    const reasons = Array.from(container!.querySelectorAll(".reason")).filter(visible);
    expect(reasons).toHaveLength(7);
    expect(container!.querySelectorAll('.flow-records[aria-label="Evaluator findings"]')).toHaveLength(1);
    const seen = reasons.map(reason => reason.textContent ?? "");
    const flow = reasons[0]!.closest(".evidence-flow")!;
    await act(async () => flow.querySelector<HTMLButtonElement>(".full-reading-link")!.click());
    expect(flow.getAttribute("data-full-reading")).toBe("true");
    expect(Array.from(flow.querySelectorAll(".reason")).map(reason => reason.textContent)).toEqual(seen);
    await act(async () => flow.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    expect(flow.getAttribute("data-full-reading")).toBe("false");
    expect(seen.join(" ")).toContain("reset_evidence_incomplete");
    expect(seen.join(" ")).toContain("0.8213408026614656");
    expect(seen.join(" ")).toContain("producer_validity_claim_ignored");
    expect(text(".transport-row")).toBe(row);
    await clickVisible("Confirmation");
    expect(Array.from(container!.querySelectorAll(".decision-block")).filter(visible)[0]!.textContent).toContain("No record referenced.");
  });

  it("keeps one inspector section visible and retains exact sources across section changes", async () => {
    await mount("");
    await press("ArrowRight");
    await press("i");
    const sections = () => Array.from(container!.querySelectorAll(".inspector-section")).filter(visible);
    expect(sections()).toHaveLength(1);
    expect(sections()[0]!.textContent).toContain("Selection");
    const select = container!.querySelector<HTMLSelectElement>('[aria-label="Inspector section"]')!;
    await act(async () => { select.value = "Sources"; select.dispatchEvent(new Event("change", { bubbles: true })); });
    expect(sections()).toHaveLength(1);
    expect(sections()[0]!.textContent).toContain("manifest");
    expect(sections()[0]!.textContent).toContain(new URLSearchParams(window.location.search).get("g"));
    expect(text(".transport-row")).toBe("row 1");
  });

  it("reads the actual diagnosis, costs and engine interface catalog without claiming a live worker", async () => {
    const disk = fetchFromDisk();
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation((url) => disk(new URL(String(url), "http://fixture.test").href));
    try {
      await mount("?evidence=fixtures/ui/recorded/D10-opaque-policy-state/evidence.json");
      await clickVisible("Engine");
      await clickVisible("Diagnosis");
      expect(text(".engine-panel")).toContain("transport gripper sign.working1");
      await clickVisible("Costs");
      expect(text(".engine-panel")).toContain("3.9059422919526696");
      await clickVisible("Interfaces");
      await waitFor(() => text(".engine-panel").includes("project_context"));
      expect(text(".engine-panel")).toContain("not connected to this public site");
      expect(spy).toHaveBeenCalledWith("/api/engine.json", expect.objectContaining({ cache: "no-cache" }));
      const endpoints = Array.from(container!.querySelectorAll<HTMLAnchorElement>(".endpoint-links a"));
      expect(endpoints.map((a) => a.getAttribute("href"))).toEqual(["/api/publication.json", "/fixtures/ui/study/evidence.json", "/api/engine.json", "/fixtures/ui/recorded/library.json"]);
      expect(text(".transport-row")).toBe("row 0");
    } finally { spy.mockRestore(); }
  });
});
