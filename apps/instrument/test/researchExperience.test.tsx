import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Experience } from "../src/research/Experience";
import {
  decodeResearchCatalog,
  type ResearchCatalog,
} from "../src/research/catalog";
import { CATALOG_SHA } from "../src/research/catalogPin";
import type { LoaderOptions } from "../src/data/loader";
import { fetchFromDisk, PUBLIC_DIR } from "./fixture";

vi.mock("../src/research/progress", async (original) => {
  const module = await original<typeof import("../src/research/progress")>();
  return { ...module, createProgressClient: () => ({ current: () => module.SAVED_PROGRESS, refresh: async () => module.SAVED_PROGRESS }) };
});

const catalog = decodeResearchCatalog(
  JSON.parse(
    readFileSync(
      join(PUBLIC_DIR, "research", CATALOG_SHA, "catalog.json"),
      "utf8",
    ),
  ),
);
const catalogLoader = vi.fn(async () => catalog);
const disk = fetchFromDisk();
const labLoader: LoaderOptions = {
  fetch: vi.fn(disk),
  digest: async (bytes) =>
    createHash("sha256").update(new Uint8Array(bytes)).digest("hex"),
  maxBytes: 64 * 1024 * 1024,
};
let root: Root | null = null,
  host: HTMLDivElement;
async function waitFor(predicate: () => boolean) {
  const end = Date.now() + 5000;
  while (!predicate()) {
    if (Date.now() > end)
      throw new Error("Research view did not reach the expected state");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });
  }
}
async function mount(
  hash = "#view=system",
  loader: (
    sha: string,
    signal: AbortSignal,
  ) => Promise<ResearchCatalog> = catalogLoader,
) {
  history.replaceState(null, "", `/${hash}`);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () =>
    root!.render(<Experience catalogLoader={loader} labLoader={labLoader} />),
  );
  await waitFor(
    () =>
      !!host.querySelector(
        ".system-workspace,.investigation-workspace,.research-error,.qualification-workspace,.develop-workspace",
      ),
  );
}
async function click(element: Element) {
  await act(async () =>
    element.dispatchEvent(new MouseEvent("click", { bubbles: true })),
  );
}
function button(text: string) {
  const found = [...host.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === text,
  );
  if (!found) throw new Error(`Missing button ${text}`);
  return found;
}
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  delete document.documentElement.dataset.ground;
});
afterEach(async () => {
  await act(async () => root?.unmount());
  host?.remove();
  root = null;
  vi.restoreAllMocks();
});

it("opens the verified system without starting a hidden robot scene", async () => {
  await mount();
  await waitFor(() => !!host.querySelector(".system-workspace"));
  await click(button("Evidence"));
  expect(host.querySelectorAll(".index-entry")).toHaveLength(9);
  await click(host.querySelector(".glass-card-close")!);
  expect(host.querySelector(".retained-lab")?.hasAttribute("inert")).toBe(true);
  expect(host.querySelector(".app")).toBeNull();
  expect(labLoader.fetch).not.toHaveBeenCalled();
  await click(host.querySelector('[aria-label="Switch to paper ground"]')!);
  expect(document.documentElement.dataset.ground).toBe("paper");
  expect(localStorage.getItem("nisayon.ground")).toBe("paper");
});

it("reserves the header center for the investigation switch without text underneath", async () => {
  await mount("#view=qualify");
  expect(host.querySelector('[aria-label="Investigation type"]')).not.toBeNull();
  expect(host.querySelector('.research-header .research-edition')).toBeNull();
  await click(button("Develop"));
  expect(host.querySelector('[aria-label="Investigation type"]')).toBeNull();
  expect(host.querySelector('.research-header .research-edition')?.textContent).toContain("EXPERIMENT ENGINE");
});

it("handles pointer focus in Library without a prior visit to the robot lab", async () => {
  await mount();
  const execute = [...host.querySelectorAll<HTMLButtonElement>(".method-stages button")].find(b => b.textContent?.includes("Execute"))!;
  await act(async () => {
    execute.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    execute.focus();
    execute.dispatchEvent(new MouseEvent("click", { bubbles: true, detail: 1 }));
  });
  expect(execute.getAttribute("aria-pressed")).toBe("true");
  expect(execute.dataset.pointerFocus).toBe("true");
  expect(document.activeElement).toBe(execute);
  expect(host.querySelector(".app")).toBeNull();
  await act(async () => execute.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true })));
  expect(execute.dataset.pointerFocus).toBeUndefined();
});

it("opens all retained progress with separate available and review states", async () => {
  await mount();
  const open = host.querySelector<HTMLButtonElement>('[aria-label="View all 16 progress records"]')!;
  open.focus(); await click(open);
  expect(host.querySelector("dialog")?.textContent).toContain("Progress, with the evidence.");
  await click([...host.querySelectorAll(".progress-tabs button")].find(b => b.textContent?.startsWith("Available"))!);
  expect(host.querySelectorAll(".progress-entry")).toHaveLength(2);
  expect(host.querySelector("dialog")?.textContent).toContain("Available locally");
  await click(host.querySelector('[aria-label="Next progress records"]')!);
  expect(host.querySelector("dialog")?.textContent).toContain("Merged");
  expect(host.querySelector("dialog")?.textContent).toContain("Released");
  await click([...host.querySelectorAll(".progress-tabs button")].find(b => b.textContent?.startsWith("In review"))!);
  expect(host.querySelector("dialog")?.textContent).toContain("Draft PR");
  expect(host.querySelector("dialog")?.textContent).toContain("Open PR");
  await click(host.querySelector(".glass-card-close")!);
  expect(document.activeElement).toBe(open);
});

it("shows every current investigation with its own scope and verified source bindings", async () => {
  await mount("#view=research");
  await waitFor(() => !!host.querySelector(".investigation-workspace"));
  for (const entry of catalog.cases) {
    await click(
      [...host.querySelectorAll(".investigation-rail button")].find((b) =>
        b.textContent?.startsWith(entry.code),
      )!,
    );
    expect(host.querySelector("h1")?.textContent).toBe(entry.title);
    expect(document.activeElement).toBe(host.querySelector("h1"));
    await click(host.querySelectorAll(".reading-actions button")[1]!);
    expect(host.querySelector("dialog")?.textContent).toContain(entry.limit);
    await click(button("Sources"));
    for (let i = 0; i < entry.sources.length; i++) {
      expect(host.querySelector(".research-sources dt")?.textContent).toBe(
        entry.sources[i]!.path,
      );
      expect(host.querySelector(".research-sources dd")?.textContent).toContain(
        entry.sources[i]!.sha256,
      );
      if (i < entry.sources.length - 1)
        await click(host.querySelector('[aria-label="Next source record"]')!);
    }
    await click(host.querySelector(".glass-card-close")!);
  }
  expect(host.querySelector(".control-summary")?.textContent).toContain(
    "76/76",
  );
});

it("retains the failed pair in a shared selection and changes only the requested source variant", async () => {
  await mount("#view=research&case=transfer&sample=4&variant=corrected");
  await waitFor(() => !!host.querySelector(".selected-witness"));
  expect(host.querySelector(".selected-witness")?.textContent).toContain(
    "180104",
  );
  expect(host.querySelector(".selected-witness")?.textContent).toContain(
    "Task failed",
  );
  await click(button("Unchanged"));
  expect(location.hash).toContain("sample=4");
  expect(location.hash).toContain("variant=original");
  expect(host.querySelector(".selected-witness")?.textContent).toContain(
    "Unchanged · 400",
  );
});

it("restores hypothetical cost values from the link and never describes them as measured", async () => {
  await mount("#view=research&case=cost&context=0.28&work=1.2");
  await waitFor(() => !!host.querySelector(".cost-headroom"));
  const sliders = [
    ...host.querySelectorAll<HTMLInputElement>('input[type="range"]'),
  ];
  expect(sliders.map((s) => s.value)).toEqual(["0.28", "1.2"]);
  expect(host.querySelector(".selected-witness")?.textContent).toContain(
    "Saving erased",
  );
  expect(host.querySelector(".diagram-note")?.textContent).toContain(
    "Actual costs are unknown",
  );
});

it("keeps a corrupt catalog unavailable and verifies again when asked to retry", async () => {
  let fail = true;
  const loader = vi.fn(async () => {
    if (fail) throw new Error("catalog digest does not match");
    return catalog;
  });
  await mount("#view=research", loader);
  await waitFor(() => !!host.querySelector('[role="alert"]'));
  expect(host.querySelector(".investigation-workspace")).toBeNull();
  expect(host.textContent).toContain("could not be verified");
  fail = false;
  await click(button("Retry verification"));
  await waitFor(() => !!host.querySelector(".investigation-workspace"));
  expect(loader).toHaveBeenCalledTimes(2);
});

it("keeps robot selection, theme and playback isolated while moving through research", async () => {
  await mount();
  await waitFor(() => !!host.querySelector(".system-workspace"));
  await click(button("Investigate"));
  await waitFor(() => !!host.querySelector(".transport"));
  await act(async () =>
    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
    ),
  );
  const moment = location.search;
  await act(async () => window.dispatchEvent(new CustomEvent("nisayon:navigate", { detail: "research" })));
  await waitFor(() => !!host.querySelector(".investigation-workspace"));
  await act(async () =>
    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
    ),
  );
  expect(location.search).toBe(moment);
  await click(button("Investigate"));
  expect(location.search).toBe(moment);
  expect(host.querySelector(".retained-lab")?.hasAttribute("inert")).toBe(
    false,
  );
  expect(host.querySelector(".transport-row")?.textContent).toContain("1");
  await click(host.querySelector('.workspace-actions button')!);
  expect(host.querySelector('dialog[open]')?.textContent).toContain("Experiment evidence");
  await click(host.querySelector('.glass-card-close')!);
  expect(host.querySelector('.reading')).toBeNull();
  expect(location.search).toBe(moment);
});

it("leaves an invalid view explicit instead of showing a different investigation", async () => {
  await mount("#view=research&case=does-not-exist");
  expect(host.textContent).toContain("not substituted another result");
  expect(host.querySelector(".investigation-workspace")).toBeNull();
  expect(document.documentElement.dataset.surface).toBe("research");
});

it("returns from the lab logo to the opening and preserves the recorded moment through history", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  await mount();
  await click(button("Investigate"));
  await waitFor(() => !!host.querySelector(".transport"));
  await act(async () => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
  const moment = location.search;
  const app = host.querySelector(".app");
  await act(async () => host.querySelector<HTMLAnchorElement>(".identity-brand")!.click());
  expect(host.querySelector(".opening")).not.toBeNull();
  expect(new URLSearchParams(location.hash.slice(1)).get("view")).toBe("home");
  expect(location.search).toBe(moment);
  expect(host.querySelector(".retained-lab")?.hasAttribute("inert")).toBe(true);
  expect(host.querySelector(".app")).toBe(app);
  expect(document.activeElement).toBe(host.querySelector(".opening h1"));
  await act(async () => history.back());
  await waitFor(() => !host.querySelector(".opening"));
  expect(location.search).toBe(moment);
  expect(host.querySelector(".retained-lab")?.hasAttribute("inert")).toBe(false);
  await act(async () => history.forward());
  await waitFor(() => !!host.querySelector(".opening"));
  await click(button("Open Nisayon"));
  expect(host.querySelector(".opening")).toBeNull();
  expect(host.querySelector(".app")).toBe(app);
  expect(location.search).toBe(moment);
  expect(host.querySelector(".transport-row")?.textContent).toContain("1");
});

it("hides a previous catalog immediately and ignores a superseded load", async () => {
  let resolveOld!: (value: ResearchCatalog) => void;
  const pending = new Promise<ResearchCatalog>((resolve) => {
    resolveOld = resolve;
  });
  const loader = vi.fn(async (sha: string) =>
    sha === CATALOG_SHA ? catalog : pending,
  );
  await mount("#view=research", loader);
  await waitFor(() => !!host.querySelector(".investigation-workspace"));
  await act(async () => {
    history.pushState(null, "", `/#view=research&catalog=${"a".repeat(64)}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  expect(host.querySelector(".investigation-workspace")).toBeNull();
  expect(host.textContent).toContain("Reading the evidence.");
  await act(async () => {
    history.pushState(
      null,
      "",
      `/#view=research&catalog=${CATALOG_SHA}&case=deployment`,
    );
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await waitFor(
    () =>
      host.querySelector("h1")?.textContent ===
      "The experiment has not started.",
  );
  await act(async () => resolveOld({ ...catalog, cases: [] }));
  expect(host.querySelector("h1")?.textContent).toBe(
    "The experiment has not started.",
  );
  expect(host.querySelector(".outcome-summary")?.textContent).toContain("0/44");
});

it("switches the actual attention fixture while keeping task claims outside its scope", async () => {
  await mount("#view=research&case=attention");
  await waitFor(() => !!host.querySelector(".attention-drawing"));
  expect(host.querySelector(".control-summary")?.textContent).toContain(
    "26/26",
  );
  await click(button("Unchanged"));
  expect(
    host.querySelector(".attention-drawing")?.getAttribute("aria-label"),
  ).toContain("State output 1.5; required 6");
  expect(host.querySelector(".outcome-summary")?.textContent).toContain(
    "1.125",
  );
  expect(host.querySelector(".control-summary")?.textContent).toContain("4/26");
  await click(host.querySelectorAll(".reading-actions button")[1]!);
  expect(host.querySelector(".reading-page")?.textContent).toContain(
    "not adopted",
  );
  expect(host.querySelector(".diagram-note")?.textContent).toContain(
    "not a learned model",
  );
});

it("explains the unlisted sidecar before/after and retains all 28 promotion controls", async () => {
  await mount("#view=research&case=promotion&sample=17");
  await waitFor(() => !!host.querySelector(".promotion-drawing"));
  expect(host.querySelector(".promotion-decision")?.textContent).toBe("BLOCK");
  expect(host.querySelector(".control-summary")?.textContent).toContain(
    "28/28",
  );
  await click(button("Unchanged"));
  expect(host.querySelector(".promotion-decision")?.textContent).toBe(
    "PROMOTE",
  );
  expect(host.querySelector(".control-summary")?.textContent).toContain(
    "17/28",
  );
  await click(button("Retained evidence"));
  expect(host.querySelectorAll("dialog .test-field button")).toHaveLength(28);
  expect(host.querySelector("dialog .control-reading")?.textContent).toContain(
    "unlisted sidecar cannot override embedded failure",
  );
  expect(host.querySelector("dialog .control-reading")?.textContent).toContain(
    "failed",
  );
});

it("opens a centered evidence card, retains the selected condition, and restores its opener", async () => {
  await mount("#view=research&case=terminal&sample=7&variant=original");
  await waitFor(() => !!host.querySelector(".episode-drawing"));
  const opener = button("Retained evidence");
  opener.focus();
  await click(opener);
  expect(host.querySelector("dialog")?.hasAttribute("open")).toBe(true);
  expect(document.activeElement).toBe(
    host.querySelector(".glass-card-header h2"),
  );
  const field = host.querySelector("dialog .test-field")!;
  expect(
    field.querySelector('[aria-pressed="true"]')?.getAttribute("aria-label"),
  ).toContain("Control 8:");
  await click(field.querySelectorAll("button")[17]!);
  expect(location.hash).toContain("sample=17");
  await click(host.querySelector(".glass-card-close")!);
  expect(host.querySelector("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
  await click(opener);
  expect(host.querySelector("dialog .control-reading")?.textContent).toContain(
    "Control 18 / 48",
  );
  await act(async () =>
    host
      .querySelector("dialog")!
      .dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })),
  );
  expect(host.querySelector("dialog")).toBeNull();
  expect(location.hash).toContain("variant=original");
});

it("keeps all controls and investigations reachable on a compact workspace", async () => {
  const original = window.matchMedia;
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
    ...original(query),
    matches: query === "(max-width: 760px)",
  }));
  await mount();
  await waitFor(() => !!host.querySelector(".system-workspace"));
  await click(host.querySelector(".method-peek")!);
  expect(host.querySelector(".stage-card-reading")?.textContent).toContain(
    "working deployment",
  );
  await click(host.querySelector(".glass-card-close")!);
  await click(button("Evidence"));
  const titles: string[] = [];
  for (let i = 0; i < Math.ceil(catalog.cases.length / 3); i++) {
    titles.push(
      ...[...host.querySelectorAll(".index-entry b")].map(
        (n) => n.textContent!,
      ),
    );
    if (i < Math.ceil(catalog.cases.length / 3) - 1)
      await click(host.querySelector('[aria-label="Next investigations"]')!);
  }
  expect(titles).toEqual(catalog.cases.map((c) => c.title));
  await click(host.querySelector(".glass-card-close")!);
  await act(async () => window.dispatchEvent(new CustomEvent("nisayon:navigate", { detail: "research" })));
  await click(
    [...host.querySelectorAll(".investigation-rail button")].find((b) =>
      b.textContent?.startsWith("N031"),
    )!,
  );
  await click(button("Retained evidence"));
  const controls: string[] = [];
  for (let i = 0; i < 4; i++) {
    controls.push(
      ...[...host.querySelectorAll("dialog .test-field button")].map(
        (n) => n.getAttribute("aria-label")!,
      ),
    );
    if (i < 3)
      await click(
        host.querySelector('dialog [aria-label="Next control group"]')!,
      );
  }
  expect(new Set(controls).size).toBe(48);
  expect(controls[47]).toContain("Control 48:");
});

it("preserves the system stage while opening the full source atlas", async () => {
  await mount();
  await waitFor(() => !!host.querySelector(".system-workspace"));
  const stage = host.querySelectorAll(".method-stages button")[3]!;
  await click(stage);
  await click(button("Engine"));
  expect(host.querySelector(".engine-module-reading h2")?.textContent).toBe(
    "confirmation service",
  );
  await click(button("Identity"));
  expect(host.querySelector(".module-source")?.textContent).toContain(
    catalog.sourceCommit,
  );
  await click(host.querySelector('[aria-label="Next module directory"]')!);
  await click(host.querySelector(".engine-module-map button")!);
  expect(host.querySelector(".module-source code")?.textContent).toContain(
    ".py",
  );
  await click(host.querySelector(".glass-card-close")!);
  expect(stage.getAttribute("aria-pressed")).toBe("true");
  expect(host.querySelectorAll(".system-plate.is-active")).toHaveLength(1);
});

it("makes every word of a long engine description reachable without enlarging its card", async () => {
  await mount();
  await waitFor(() => !!host.querySelector(".system-workspace"));
  await click(button("Engine"));
  const module = catalog.modules!.find(
    (m) => m.name === "a1_runtime_assessor",
  )!;
  // Choose the same exposed source via the compact native selector.
  const selector = host.querySelector<HTMLSelectElement>(
    ".engine-module-picker select",
  )!;
  await act(async () => {
    selector.value = `${module.package}.${module.name}`;
    selector.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const paragraphs: string[] = [];
  for (let i = 0; i < 20; i++) {
    paragraphs.push(host.querySelector(".text-reading > p")!.textContent!);
    const next = host.querySelector<HTMLButtonElement>(
      '[aria-label="Next module description"]',
    );
    if (!next || next.disabled) break;
    await click(next);
  }
  expect(paragraphs.join(" ").replace(/\s+/g, " ").trim()).toBe(
    module.description.replace(/\s+/g, " ").trim(),
  );
  expect(paragraphs.length).toBeGreaterThan(1);
});


it("closes the lab modal on route change while retaining the exact recorded moment", async () => {
  await mount();
  await click(button("Investigate"));
  await waitFor(() => !!host.querySelector(".transport"));
  const moment = location.search;
  await click(host.querySelector('.workspace-actions button')!);
  expect(host.querySelector('dialog[open]')).not.toBeNull();
  await act(async () => window.dispatchEvent(new CustomEvent("nisayon:navigate", { detail: "develop" })));
  expect(host.querySelector('.develop-workspace')).not.toBeNull();
  expect(host.querySelector('dialog[open]')).toBeNull();
  expect(document.activeElement?.textContent).toContain("The experiment stays");
  await click(button("Investigate"));
  expect(location.search).toBe(moment);
  expect(host.querySelector('dialog[open]')).toBeNull();
});


it("keeps device access and theme reachable in the compact software workspace, with focus return", async () => {
  await mount("#view=qualify");
  const controls = host.querySelector<HTMLButtonElement>(".research-workspace-menu")!;
  controls.focus();
  await click(controls);
  const menu = host.querySelector("dialog")!;
  const device = menu.querySelector<HTMLButtonElement>('[aria-label="Nisayon on this device"]')!;
  device.focus();
  await click(device);
  expect(host.querySelectorAll("dialog")).toHaveLength(2);
  await click(host.querySelector('[aria-label="Close Nisayon on this device"]')!);
  expect(document.activeElement).toBe(device);
  await click(menu.querySelector('[aria-label="Switch to paper ground"]')!);
  expect(document.documentElement.dataset.ground).toBe("paper");
  await act(async () => menu.dispatchEvent(new Event("cancel", { cancelable: true })));
  expect(host.querySelector("dialog")).toBeNull();
  expect(document.activeElement).toBe(controls);
  await click(controls);
  await act(async () => {
    history.replaceState(null, "", "/#view=system");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  expect(host.querySelector("dialog")).toBeNull();
});
