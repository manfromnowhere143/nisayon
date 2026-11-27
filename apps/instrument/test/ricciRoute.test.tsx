import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { Experience } from "../src/research/Experience";
import { startOfflineSupport } from "../src/pwa/runtime";

vi.mock("../src/concepts/ricciRenderer", () => ({ createRicciRenderer: vi.fn((_canvas, callbacks) => {
  callbacks.ready(); return { select: vi.fn(), dispose: vi.fn() };
}) }));

vi.mock("../src/pwa/runtime", async original => ({
  ...await original<typeof import("../src/pwa/runtime")>(),
  startOfflineSupport: vi.fn(() => () => {}),
}));

it("keeps a direct Ricci visit free of the full offline/media preload, and preserves offline setup elsewhere", async () => {
  vi.mocked(startOfflineSupport).mockClear();
  history.replaceState(null, "", "/#view=concepts");
  const catalogLoader = vi.fn();
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<Experience catalogLoader={catalogLoader} />));
    expect(startOfflineSupport).not.toHaveBeenCalled();
    expect(catalogLoader).not.toHaveBeenCalled();
    expect(host.querySelector("video, img")).toBeNull();
    await act(async () => window.dispatchEvent(new CustomEvent("nisayon:navigate", { detail: "develop" })));
    expect(startOfflineSupport).toHaveBeenCalledTimes(1);
  } finally {
    await act(async () => root.unmount()); host.remove();
  }
});

it("allows explicit device setup from Ricci without leaving its selection", async () => {
  vi.mocked(startOfflineSupport).mockClear();
  history.replaceState(null, "", "/#view=concepts&part=ankle_foot");
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host);
  try {
    await act(async () => { root.render(<Experience catalogLoader={vi.fn()} />); });
    await act(async () => vi.dynamicImportSettled());
    expect(startOfflineSupport).not.toHaveBeenCalled();
    await act(async () => window.dispatchEvent(new Event("nisayon:app-access")));
    expect(startOfflineSupport).toHaveBeenCalledTimes(1);
    expect(location.hash).toBe("#view=concepts&part=ankle_foot");
    expect(host.querySelector(".ricci-annotation")?.getAttribute("data-part")).toBe("ankle_foot");
  } finally {
    await act(async () => root.unmount()); host.remove();
  }
});
