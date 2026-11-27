import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { PandaPartInspection } from "../src/ui/PandaPartInspection";
import type { BodyAnnotation } from "../src/scene/bodyAnnotation";

it("never exposes a provisional position or the previous part's anchor while a selection is being bound", async () => {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host);
  const base = { pose: { position: [1, 2, 3] as [number, number, number], quaternion: [1, 0, 0, 0] as [number, number, number, number] }, time: 1.5, phase: "before" as const, expanded: false, onExpanded: vi.fn(), onClose: vi.fn(), children: null };
  const anchor: BodyAnnotation = { bodyId: 4, x: 600, y: 350, width: 1024, height: 768, visible: true, body: [] };
  async function render(body: number, target: BodyAnnotation | null, unavailable = false) {
    await act(async () => root.render(<PandaPartInspection {...base} name={`robot0_link${body}`} body={body} anchor={target} unavailable={unavailable} />));
  }
  try {
    await render(4, null);
    expect(host.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
    expect(host.firstElementChild?.hasAttribute("inert")).toBe(true);
    expect(document.activeElement).not.toBe(host.querySelector("h2"));
    await render(4, anchor);
    expect(host.firstElementChild?.getAttribute("aria-hidden")).toBe("false");
    expect(document.activeElement).toBe(host.querySelector("h2"));
    const card = host.querySelector("dialog");
    await render(5, anchor);
    expect(host.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
    await render(5, { ...anchor, bodyId: 5, x: 650 });
    expect(host.firstElementChild?.getAttribute("aria-hidden")).toBe("false");
    expect(host.querySelector("dialog")).toBe(card);
    expect(host.querySelector("h2")?.textContent).toBe("Arm link 5");
    // A declared graphics failure still permits reading the retained values.
    await render(5, null, true);
    expect(host.firstElementChild?.getAttribute("aria-hidden")).toBe("false");
    expect(host.querySelector(".panda-part-leader")).toBeNull();
  } finally { await act(async () => root.unmount()); host.remove(); }
});
