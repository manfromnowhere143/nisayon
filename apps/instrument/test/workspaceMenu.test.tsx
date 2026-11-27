import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { WorkspaceMenu } from "../src/ui/WorkspaceMenu";
import { WorkspaceNavigation } from "../src/ui/WorkspaceNavigation";
import { workspaceUtilities } from "../src/ui/WorkspaceActions";
import { InstrumentSymbol } from "../src/ui/InstrumentSymbol";

it("reserves the adjacent slot for appearance and replaces navigation with tools on the same rail", async () => {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host), select = vi.fn(), navigate = vi.fn();
  const names = ["Study", "Sources", "Copy link", "Device"];
  try {
    await act(async () => root.render(<WorkspaceMenu label="Workspace" navigation={<WorkspaceNavigation current="lab" navigate={navigate} />} actions={[
      { id: "appearance", label: "Appearance", icon: <InstrumentSymbol name="workspace" />, onSelect: () => select("Appearance") },
      ...names.map(label => ({ id: label, label, icon: <InstrumentSymbol name="workspace" />, onSelect: () => select(label) })),
      { id: "recording", label: "Recorded experiment", icon: <InstrumentSymbol name="recording" />, content: <select aria-label="Recording"><option>Retained run</option></select> },
    ]} />));
    const adjacent = host.querySelector(".workspace-tool-rail")!;
    expect([...adjacent.children].map(node => node.getAttribute("aria-label"))).toEqual(["Appearance"]);
    expect(host.querySelectorAll(".workspace-destinations button")).toHaveLength(4);
    const main = host.querySelector<HTMLElement>(".workspace-popover-rail")!;
    const primary = host.querySelector<HTMLElement>(".workspace-rail-list")!;
    const tools = host.querySelector<HTMLElement>(".workspace-tools-list")!;
    const toggle = host.querySelector<HTMLButtonElement>('[aria-label="Tools"]')!;
    const back = host.querySelector<HTMLButtonElement>('[aria-label="Back to navigation"]')!;
    expect(tools.hidden).toBe(true);
    toggle.focus();
    await act(async () => toggle.click());
    expect(primary.hidden).toBe(true);
    expect(primary.hasAttribute("inert")).toBe(true);
    expect(tools.hidden).toBe(false);
    expect(tools.hasAttribute("inert")).toBe(false);
    expect(document.activeElement).toBe(back);
    expect(main.getAttribute("aria-label")).toBe("Workspace tools");
    for (const name of names) {
      const controls = tools.querySelectorAll<HTMLButtonElement>(`button[aria-label="${name}"]`);
      expect(controls).toHaveLength(1);
      await act(async () => controls[0]!.click());
    }
    expect(select.mock.calls.flat()).toEqual(names);
    expect(tools.querySelectorAll('button[aria-label="Recorded experiment"]')).toHaveLength(1);
    expect(tools.querySelector('select[aria-label="Recording"]')).not.toBeNull();
    await act(async () => back.click());
    expect(primary.hidden).toBe(false);
    expect(tools.hidden).toBe(true);
    expect(document.activeElement).toBe(toggle);
    expect(main.getAttribute("aria-label")).toBe("Workspace");
    await act(async () => toggle.click());
    const closed = new Event("toggle");
    Object.defineProperty(closed, "newState", { value: "closed" });
    await act(async () => main.dispatchEvent(closed));
    expect(primary.hidden).toBe(false);
    expect(tools.hidden).toBe(true);
  } finally {
    await act(async () => root.unmount()); host.remove();
  }
});

it("keeps the appearance action reversible and separate from contextual tools", async () => {
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host), toggleGround = vi.fn();
  try {
    for (const ground of ["black", "paper"] as const) {
      await act(async () => root.render(<WorkspaceMenu navigation={<WorkspaceNavigation current="system" navigate={() => {}} />} actions={workspaceUtilities({ ground, toggleGround, copyLink: () => {}, copyLabel: "Copy link" })} />));
      const appearance = host.querySelector<HTMLButtonElement>(".workspace-tool-rail > button")!;
      expect(appearance.getAttribute("aria-label")).toBe(`Switch to ${ground === "black" ? "paper" : "black"} ground`);
      expect(host.querySelectorAll(".workspace-appearance")).toHaveLength(1);
      expect(host.querySelector(".workspace-tools-list .workspace-appearance")).toBeNull();
      await act(async () => appearance.click());
    }
    expect(toggleGround).toHaveBeenCalledTimes(2);
  } finally {
    await act(async () => root.unmount()); host.remove();
  }
});
