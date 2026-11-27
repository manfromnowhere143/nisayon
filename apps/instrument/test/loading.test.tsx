import { act, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createHash } from "node:crypto";
import { expect, it, vi } from "vitest";
import { App } from "../src/App";
import type { InstrumentStore } from "../src/state/store";
import { fetchFromDisk, installOpening } from "./fixture";

it("shows the site opening once, then reveals verified data without a staged visual sequence", async () => {
  const schemas = ["nisayon.ui-discovery.v1", "nisayon.ui-case.v1", "nisayon.ui-samples.v1"];
  const releases: (() => void)[] = [];
  const gates = schemas.map(() => new Promise<void>((resolve) => releases.push(resolve)));
  const disk = fetchFromDisk();
  const element = document.createElement("div");
  document.body.appendChild(element);
  window.history.replaceState(null, "", "/");
  const root = createRoot(element);
  const opening = installOpening();
  const signature = opening.querySelector(".boot-signature")!;
  const wordmark = opening.querySelector(".boot-wordmark")!;
  const mark = opening.querySelector(".boot-mark")!;
  const initialSignature = signature.innerHTML;
  const waitFor = async (predicate: () => boolean) => {
    const deadline = Date.now() + 4000;
    while (!predicate()) {
      if (Date.now() > deadline) throw new Error("Loading did not reach the expected evidence stage");
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });
    }
  };
  try {
    await act(async () => root.render(<StrictMode><App loader={{
      fetch: async (url, init) => {
        const response = await disk(url, init);
        const json = await response.clone().json() as { schema?: string };
        const stage = schemas.indexOf(json.schema ?? "");
        if (stage !== -1) await gates[stage];
        return response;
      },
      digest: async (bytes) => createHash("sha256").update(Buffer.from(new Uint8Array(bytes))).digest("hex"),
      maxBytes: 64 * 1024 * 1024,
    }} /></StrictMode>));
    for (const [index, stage] of ["evidence", "case", "run"].entries()) {
      await waitFor(() => opening.getAttribute("data-load-stage") === stage);
      expect(element.querySelector(".boot-stages")).toBeNull();
      expect(opening.getAttribute("aria-busy")).toBe("true");
      expect(document.querySelector(".boot-screen")).toBe(opening);
      expect(opening.querySelector(".boot-wordmark")).toBe(wordmark);
      expect(opening.querySelector(".boot-mark")).toBe(mark);
      expect(signature.innerHTML).toBe(initialSignature);
      expect(element.querySelector(".scene-playback")).toBeNull();
      await act(async () => releases[index]!());
    }
    await waitFor(() => element.querySelector(".scene-playback") !== null);
    expect(opening.getAttribute("data-revealed")).toBe("true");
    expect(signature.innerHTML).toBe(initialSignature);
    // A transparent opening would paint its wordmark over the ready scene.
    // It must already be removed in the commit that presents the instrument.
    expect(document.querySelector(".boot-screen")).toBeNull();
    expect(element.querySelector(".reading")).toBeNull();
    expect(element.querySelector(".scene-heading")).toBeNull();
    expect(element.querySelector(".scene-area > h1.sr-only")).not.toBeNull();
    await act(async () => element.querySelector<HTMLButtonElement>(".scene-evidence-control")!.click());
    expect(element.querySelector(".case-brief h3")?.textContent).toBe("Gripper command reversed at step 0.");
  } finally {
    releases.forEach((release) => release());
    await act(async () => root.unmount());
    element.remove();
    opening.remove();
  }
});

it.each([false, true])("releases the original opening on an integrity error, including reduced motion (%s)", async (reducedMotion) => {
  const original = window.matchMedia;
  const media = vi.spyOn(window, "matchMedia").mockImplementation((query) => ({ ...original(query), matches: reducedMotion && query === "(prefers-reduced-motion: reduce)" }));
  const element = document.createElement("div"); document.body.appendChild(element);
  const root = createRoot(element), opening = installOpening();
  window.history.replaceState(null, "", "/");
  try {
    await act(async () => root.render(<App loader={{ fetch: fetchFromDisk(), digest: async () => "0".repeat(64), maxBytes: 16 * 1024 * 1024 }} />));
    const deadline = Date.now() + 2500;
    while (!element.querySelector(".state-error")) {
      if (Date.now() > deadline) throw Error("Integrity error did not resolve");
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });
    }
    expect(opening.dataset.revealed).toBe("true");
    expect(opening.isConnected).toBe(false);
    expect(element.querySelector(".state-error")).not.toBeNull();
  } finally {
    await act(async () => root.unmount());
    opening.remove(); element.remove(); media.mockRestore();
  }
});

it("keeps the dashboard mounted across delayed case changes, browser history and failed selections", async () => {
  const disk = fetchFromDisk();
  let release = () => {};
  const delayed = new Promise<void>((resolve) => { release = resolve; });
  let requested = false;
  const element = document.createElement("div");
  document.body.appendChild(element);
  window.history.replaceState(null, "", "/");
  const root = createRoot(element);
  const opening = installOpening();
  const waitFor = async (predicate: () => boolean) => {
    const deadline = Date.now() + 4000;
    while (!predicate()) {
      if (Date.now() > deadline) throw new Error("Selection did not settle");
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)); });
    }
  };
  const store = () => (window as unknown as { __nisayon: { store: InstrumentStore } }).__nisayon.store;
  try {
    await act(async () => root.render(<App loader={{
      fetch: async (url, init) => {
        if (url.includes("D10-opaque-policy-state")) { requested = true; await delayed; }
        if (url.includes("missing-selection")) return new Response("missing", { status: 404 });
        return disk(url, init);
      },
      digest: async (bytes) => createHash("sha256").update(Buffer.from(new Uint8Array(bytes))).digest("hex"),
      maxBytes: 64 * 1024 * 1024,
    }} />));
    await waitFor(() => element.querySelector(".scene-playback") !== null && document.querySelector(".boot-screen") === null);
    const originalScene = element.querySelector(".scene-box");
    const originalTransport = element.querySelector(".scene-playback");
    const originalUrl = store().currentUrl();
    const next = store().getState().library.find((entry) => entry.caseId === "D10-opaque-policy-state")!;
    let replayedOpening = false;
    const observer = new MutationObserver(() => { replayedOpening ||= document.querySelector(".boot-screen") !== null; });
    observer.observe(document.body, { childList: true, subtree: true });
    await act(async () => store().selectLibraryCase(next.caseKey));
    await waitFor(() => requested);
    expect(store().getState().pendingSelection).not.toBeNull();
    expect(element.querySelector(".choice-pending")?.textContent).toContain("Opening D10-opaque-policy-state");
    expect(element.querySelector('[aria-label="Recorded experiment"]')?.textContent).toContain("D01-gripper-sign");
    expect(element.querySelector(".scene-box")).toBe(originalScene);
    expect(element.querySelector(".scene-playback")).toBe(originalTransport);
    expect(element.querySelector(".identity-case")?.textContent).toContain("D01-gripper-sign");
    expect(store().currentUrl()).toBe(originalUrl);
    expect(document.querySelector(".boot-screen")).toBeNull();
    await act(async () => store().play());
    expect(store().getState().playing).toBe(true);
    await act(async () => release());
    await waitFor(() => element.querySelector(".identity-case")?.textContent?.includes("D10-opaque-policy-state") === true);
    expect(element.querySelector(".scene-box")).toBe(originalScene);
    expect(element.querySelector(".scene-playback")).toBe(originalTransport);
    expect(store().getState().playing).toBe(false);
    await act(async () => { history.back(); });
    await waitFor(() => element.querySelector(".identity-case")?.textContent?.includes("D01-gripper-sign") === true);
    await act(async () => store().setDepth("decision"));
    await act(async () => element.querySelector<HTMLAnchorElement>(".identity-brand")!.click());
    expect(store().getState().screen.kind).toBe("ready");
    const beforeFailure = store().currentUrl();
    await act(async () => store().setEvidence("missing-selection/evidence.json"));
    await waitFor(() => element.querySelector(".selection-notice") !== null);
    expect(element.querySelector(".scene-box")).toBe(originalScene);
    expect(element.querySelector(".scene-playback")).toBe(originalTransport);
    expect(store().currentUrl()).toBe(beforeFailure);
    expect(element.querySelector(".selection-notice")?.textContent).toContain("previous verified experiment remains displayed");
    expect(replayedOpening).toBe(false);
    observer.disconnect();
  } finally {
    release();
    await act(async () => root.unmount());
    element.remove();
    opening.remove();
  }
});
