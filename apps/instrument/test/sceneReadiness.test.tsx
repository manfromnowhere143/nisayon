// Lifecycle test with a renderer stand-in. It proves the reveal waits for the
// qualified frame callback, not that an actual GPU has rendered successfully.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { SceneCallbacks } from "../src/scene/renderer";
import type { FramePhase, ModelRecord } from "../src/model/types";
import { decodeVisualAsset, type VisualAsset } from "../src/scene/visualAssets";
import { VISUAL_ASSET } from "../src/scene/visualAssetPin";
import type { InstrumentStore } from "../src/state/store";
import { App } from "../src/App";
import { Experience } from "../src/research/Experience";
import { CATALOG_SHA } from "../src/research/catalogPin";
import { decodeResearchCatalog } from "../src/research/catalog";

vi.mock("../src/research/progress", async (original) => {
  const module = await original<typeof import("../src/research/progress")>();
  return { ...module, createProgressClient: () => ({ current: () => module.SAVED_PROGRESS, refresh: async () => module.SAVED_PROGRESS }) };
});
import {
  fetchFromDisk,
  installOpening,
  REPO_ROOT,
  PUBLIC_DIR,
} from "./fixture";

const controlled = vi.hoisted(() => ({
  callbacks: null as SceneCallbacks | null,
  model: null as ModelRecord | null,
  frame: null as FramePhase | null,
  ready: false,
  asset: null as VisualAsset | null,
  load: null as Promise<VisualAsset> | null,
  calls: [] as (VisualAsset | null)[],
  presentations: [] as {
    model: ModelRecord | null;
    frame: FramePhase | null;
  }[],
  spatial: vi.fn(),
  resize: vi.fn(),
}));
vi.mock("../src/scene/renderer", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/scene/renderer")>()),
  createSceneRenderer: (
    _canvas: unknown,
    _ground: unknown,
    callbacks: SceneCallbacks,
  ) => {
    controlled.callbacks = callbacks;
    return {
      setModel: (model: ModelRecord, asset: VisualAsset | null) => {
        controlled.model = model;
        controlled.asset = asset;
        controlled.calls.push(asset);
      },
      setPrimary: (frame: FramePhase | null) => {
        controlled.frame = frame;
      },
      present: () => {
        controlled.ready = true;
        controlled.presentations.push({
          model: controlled.model,
          frame: controlled.frame,
        });
      },
      setBounds: vi.fn(),
      setGhost: vi.fn(),
      setSpatial: (...args: unknown[]) => {
        controlled.spatial(...args);
      },
      setCollision: vi.fn(),
      setView: vi.fn(),
      setGround: vi.fn(),
      resize: controlled.resize,
      dispose: vi.fn(),
    };
  },
}));
vi.mock("../src/scene/visualAssets", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/scene/visualAssets")>()),
  loadVisualAsset: () => controlled.load!,
}));

let resolve: (asset: VisualAsset) => void, reject: (error: Error) => void;
const asset = decodeVisualAsset(
  JSON.parse(readFileSync(join(REPO_ROOT, VISUAL_ASSET.path), "utf8")),
  VISUAL_ASSET.sha256,
);
let root: Root | null = null,
  element: HTMLDivElement;
beforeEach(() => {
  controlled.ready = false;
  controlled.model = null;
  controlled.asset = null;
  controlled.calls = [];
  controlled.presentations = [];
  controlled.load = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
});
afterEach(async () => {
  await act(async () => {
    root?.unmount();
  });
  root = null;
  element?.remove();
  document.getElementById("site-opening")?.remove();
});
async function waitFor(predicate: () => boolean) {
  const deadline = Date.now() + 4000;
  while (!predicate()) {
    if (Date.now() > deadline) throw Error("scene did not settle");
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });
  }
}
async function mount() {
  element = document.createElement("div");
  document.body.appendChild(element);
  root = createRoot(element);
  installOpening();
  window.history.replaceState(
    null,
    "",
    "/?evidence=fixtures/ui/recorded/D03-observation-backlog/evidence.json",
  );
  await act(async () =>
    root!.render(
      <App
        loader={{
          fetch: fetchFromDisk(),
          digest: async (bytes) =>
            createHash("sha256")
              .update(Buffer.from(new Uint8Array(bytes)))
              .digest("hex"),
          maxBytes: 16 * 1024 * 1024,
        }}
      />,
    ),
  );
  await waitFor(() => element.querySelector(".transport") !== null);
}

it("never reveals the transient schematic while detailed geometry is pending, including after decode but before paint", async () => {
  await mount();
  expect(
    document.querySelector(".boot-screen")?.getAttribute("data-load-stage"),
  ).toBe("reconstruction");
  expect(
    element.querySelector<HTMLCanvasElement>(".scene-canvas")?.style.visibility,
  ).toBe("hidden");
  expect(controlled.ready).toBe(false);
  await act(async () => resolve(asset));
  expect(controlled.ready).toBe(true);
  expect(
    element.querySelector<HTMLCanvasElement>(".scene-canvas")?.style.visibility,
  ).toBe("hidden");
  expect(
    document.querySelector(".boot-screen")?.getAttribute("data-revealed"),
  ).toBe("false");
  await act(async () => controlled.callbacks!.onFirstFrame());
  expect(
    element.querySelector<HTMLCanvasElement>(".scene-canvas")?.style.visibility,
  ).toBe("visible");
  expect(document.querySelector(".boot-screen")).toBeNull();
});

it("keeps the detailed scene intact on failure and retries without substituting a schematic", async () => {
  await mount();
  await act(async () => reject(new Error("Detailed geometry hash mismatch")));
  expect(controlled.asset).toBeNull();
  expect(controlled.ready).toBe(false);
  expect(controlled.calls).toEqual([]);
  expect(element.querySelector<HTMLCanvasElement>(".scene-canvas")?.style.visibility).toBe("hidden");
  expect(element.querySelector(".scene-model-kind")?.textContent).toBe("detailed scene unavailable");
  expect(element.querySelector(".scene-recovery")?.textContent).toContain("hash mismatch");
  expect(element.querySelector(".scene-fallback")).toBeNull();
  expect(document.querySelector(".boot-screen")).toBeNull();
  const store = (window as unknown as { __nisayon: { store: InstrumentStore } }).__nisayon.store;
  const before = store.currentUrl();
  controlled.load = new Promise((yes, no) => { resolve = yes; reject = no; });
  await act(async () => element.querySelector<HTMLButtonElement>(".scene-recovery button")!.click());
  expect(element.querySelector(".scene-recovery")).toBeNull();
  await act(async () => resolve(asset));
  await act(async () => controlled.callbacks!.onFirstFrame());
  expect(controlled.asset).toBe(asset);
  expect(controlled.calls.every(value => value === asset)).toBe(true);
  expect(element.querySelector(".scene-model-kind")?.textContent).toBe("source geometry");
  expect(element.querySelector<HTMLCanvasElement>(".scene-canvas")?.style.visibility).toBe("visible");
  expect(store.currentUrl()).toBe(before);
});

it("presents each selected pose in the same commit as its clock, without waiting for another animation frame", async () => {
  await mount();
  await act(async () => resolve(asset));
  await act(async () => controlled.callbacks!.onFirstFrame());
  const store = (window as unknown as { __nisayon: { store: InstrumentStore } })
    .__nisayon.store;
  for (const [row, phase] of [
    [64, "after"],
    [64, "before"],
    [399, "after"],
  ] as const) {
    const count = controlled.presentations.length;
    await act(async () => store.selectSample(row, phase));
    const screen = store.getState().screen;
    if (screen.kind !== "ready") throw Error("case not ready");
    expect(controlled.presentations.length).toBeGreaterThan(count);
    const selected = screen.moment.row_index;
    expect(controlled.presentations.at(-1)).toEqual({
      model: screen.run.model,
      frame: screen.run.frames!.rows[selected]![phase],
    });
    expect(element.querySelector(".transport")!.textContent).toContain(
      `row ${selected}`,
    );
  }
  await act(async () => {
    store.selectSample(64, "before");
    store.play();
    store.setPhase("after");
  });
  expect(store.getState().playing).toBe(false);
});

it("does not redraw a paused scene when the automatic catalog refresh changes only discovery metadata", async () => {
  await mount();
  await act(async () => resolve(asset));
  await act(async () => controlled.callbacks!.onFirstFrame());
  const store = (window as unknown as { __nisayon: { store: InstrumentStore } })
    .__nisayon.store;
  const updates = controlled.spatial.mock.calls.length;
  const presentations = controlled.presentations.length;
  // This is the same operation App schedules every 15 seconds. A new object
  // for identical spatial props must not request another scene render.
  await act(async () => store.refreshLibrary());
  expect(controlled.spatial.mock.calls.length).toBe(updates);
  expect(controlled.presentations.length).toBe(presentations);
  await act(async () => store.selectSample(1, "before"));
  expect(controlled.spatial.mock.calls.length).toBeGreaterThan(updates);
});

it("requalifies and keeps the native mesh visible across case and paired-view changes, presenting each replacement with its own pose", async () => {
  await mount();
  await act(async () => resolve(asset));
  await act(async () => controlled.callbacks!.onFirstFrame());
  await waitFor(() => document.querySelector(".boot-screen") === null);
  const store = (window as unknown as { __nisayon: { store: InstrumentStore } })
    .__nisayon.store;
  const canvas = element.querySelector<HTMLCanvasElement>(".scene-canvas")!;
  let hidden = false,
    opening = false;
  const observer = new MutationObserver(() => {
    hidden ||= canvas.style.visibility !== "visible";
    opening ||= document.querySelector(".boot-screen") !== null;
  });
  observer.observe(document.body, {
    attributes: true,
    subtree: true,
    childList: true,
  });
  try {
    for (const id of [
      "D10-opaque-policy-state",
      "D01-gripper-sign",
      "D03-observation-backlog",
    ]) {
      const entry = store
        .getState()
        .library.find((entry) => entry.caseId === id)!;
      await act(async () => store.selectLibraryCase(entry.caseKey));
      await waitFor(
        () =>
          element.querySelector(".identity-case")?.textContent?.includes(id) ===
          true,
      );
      const screen = store.getState().screen;
      if (screen.kind !== "ready") throw Error("case not ready");
      expect(controlled.presentations.at(-1)).toEqual({
        model: screen.run.model,
        frame:
          screen.run.frames!.rows[screen.moment.row_index]![
            screen.moment.phase
          ],
      });
      expect(canvas.style.visibility).toBe("visible");
      expect(element.querySelector(".scene-model-kind")?.textContent).toBe(
        "source geometry",
      );
    }
    await act(async () => store.setDepth("fork"));
    await waitFor(() => {
      const screen = store.getState().screen;
      return screen.kind === "ready" && screen.ghost !== null;
    });
    await act(async () => store.setDepth("moment"));
    expect(hidden).toBe(false);
    expect(opening).toBe(false);
    expect(controlled.calls.every((value) => value === asset)).toBe(true);
  } finally {
    observer.disconnect();
  }
});

it("keeps hidden lab dimensions out of camera fitting and resizes the same renderer on return", async () => {
  const observers = new Map<Element, () => void>();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(private callback: () => void) {}
      observe(element: Element) {
        observers.set(element, this.callback);
      }
      unobserve(element: Element) {
        observers.delete(element);
      }
      disconnect() {}
    },
  );
  try {
    await mount();
    await act(async () => resolve(asset));
    const canvas = element.querySelector(".scene-canvas");
    const box = element.querySelector<HTMLElement>(".scene-box")!;
    let visible = true;
    Object.defineProperties(box, {
      clientWidth: { get: () => (visible ? 640 : 0) },
      clientHeight: { get: () => (visible ? 480 : 0) },
    });
    controlled.resize.mockClear();
    await act(async () => observers.get(box)!());
    expect(controlled.resize).toHaveBeenCalledTimes(1);
    visible = false;
    await act(async () => observers.get(box)!());
    expect(controlled.resize).toHaveBeenCalledTimes(1);
    visible = true;
    await act(async () => observers.get(box)!());
    expect(controlled.resize).toHaveBeenCalledTimes(2);
    expect(element.querySelector(".scene-canvas")).toBe(canvas);
  } finally {
    vi.unstubAllGlobals();
  }
});

const catalog = decodeResearchCatalog(
  JSON.parse(
    readFileSync(
      join(PUBLIC_DIR, "research", CATALOG_SHA, "catalog.json"),
      "utf8",
    ),
  ),
);
async function mountExperience(view = "system") {
  element = document.createElement("div");
  document.body.appendChild(element);
  root = createRoot(element);
  installOpening();
  window.history.replaceState(
    null,
    "",
    `/?evidence=fixtures/ui/recorded/D03-observation-backlog/evidence.json#view=${view}`,
  );
  await act(async () =>
    root!.render(
      <Experience
        catalogLoader={async () => catalog}
        labLoader={{
          fetch: fetchFromDisk(),
          digest: async (bytes) =>
            createHash("sha256")
              .update(Buffer.from(new Uint8Array(bytes)))
              .digest("hex"),
          maxBytes: 16 * 1024 * 1024,
        }}
      />,
    ),
  );
}
async function navigate(label: string) {
  const button = [
    ...element.querySelectorAll<HTMLButtonElement>(".research-dock button"),
  ].find((button) => button.textContent?.trim() === label)!;
  await act(async () => button.click());
}

it("keeps the shared opening until first paint, with one persistent navigation and a retained playback portal", async () => {
  await mountExperience();
  const dock = element.querySelector(".research-dock");
  await navigate("Investigate");
  await waitFor(() => !!element.querySelector(".transport"));
  const store = (window as unknown as { __nisayon: { store: InstrumentStore } })
    .__nisayon.store;
  expect(store.getState().initializing).toBe(false);
  expect(element.querySelector(".lab-loading")).not.toBeNull();
  expect(element.querySelector(".retained-lab")!.hasAttribute("inert")).toBe(
    true,
  );
  expect(document.getElementById("site-opening")).toBeNull();
  expect(
    element.querySelectorAll('[aria-label="Instrument navigation"]'),
  ).toHaveLength(1);
  expect(
    element.querySelector(".instrument-playback .transport"),
  ).not.toBeNull();
  await act(async () => resolve(asset));
  expect(element.querySelector(".lab-loading")).not.toBeNull();
  await act(async () => controlled.callbacks!.onFirstFrame());
  expect(element.querySelector(".lab-loading")).toBeNull();
  expect(element.querySelector(".retained-lab")!.hasAttribute("inert")).toBe(
    false,
  );
  const canvas = element.querySelector(".scene-canvas"),
    transport = element.querySelector(".transport");
  await act(async () => store.selectSample(24, "after"));
  await navigate("Library");
  expect(
    element.querySelector(".instrument-playback")!.hasAttribute("hidden"),
  ).toBe(true);
  await navigate("Investigate");
  expect(element.querySelector(".research-dock")).toBe(dock);
  expect(element.querySelector(".scene-canvas")).toBe(canvas);
  expect(element.querySelector(".transport")).toBe(transport);
  expect(element.querySelector(".lab-loading")).toBeNull();
  expect(transport!.textContent).toContain("row 24");
});

it("releases a direct lab opening into an explicit recovery state without a fallback robot", async () => {
  await mountExperience("lab");
  await waitFor(() => !!element.querySelector(".transport"));
  expect(document.getElementById("site-opening")).toBeNull();
  expect(element.querySelectorAll(".lab-loading")).toHaveLength(1);
  await act(async () => reject(new Error("Detailed geometry hash mismatch")));
  expect(element.querySelector(".lab-loading")).toBeNull();
  expect(controlled.calls).toEqual([]);
  expect(element.querySelector(".scene-recovery")).not.toBeNull();
  expect(element.querySelector(".scene-fallback")).toBeNull();
  await navigate("Library");
  expect(element.querySelector(".system-workspace")).not.toBeNull();
});

it("allows leaving a cold lab and completing its first frame without stealing the new view", async () => {
  await mountExperience("lab");
  await waitFor(() => !!element.querySelector(".transport"));
  await navigate("Library");
  await act(async () => resolve(asset));
  await act(async () => controlled.callbacks!.onFirstFrame());
  expect(element.querySelector(".system-workspace")).not.toBeNull();
  expect(element.querySelector(".lab-loading")).toBeNull();
  expect(element.querySelector(".retained-lab")!.hasAttribute("inert")).toBe(
    true,
  );
  await navigate("Investigate");
  expect(element.querySelector(".lab-loading")).toBeNull();
});
