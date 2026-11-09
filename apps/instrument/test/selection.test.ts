import { createHash } from "node:crypto";
import { expect, it } from "vitest";
import { InstrumentStore } from "../src/state/store";
import { parseLocator } from "../src/state/locator";
import { fetchFromDisk } from "./fixture";

const digest = async (bytes: ArrayBuffer) => createHash("sha256").update(Buffer.from(new Uint8Array(bytes))).digest("hex");
async function waitFor(predicate: () => boolean) {
  const deadline = performance.now() + 4000;
  while (!predicate()) { if (performance.now() > deadline) throw Error("Selection did not settle"); await new Promise((resolve) => setTimeout(resolve, 10)); }
}

it("reuses only verified pinned generations on return and still rejects a new invalid pin", async () => {
  const requests: string[] = [], disk = fetchFromDisk();
  const store = new InstrumentStore({ fetch: async (url, init) => { requests.push(url); return disk(url, init); }, digest, maxBytes: 64 * 1024 * 1024 });
  try {
    await store.refreshLibrary();
    const a = store.getState().library.find((entry) => entry.caseId === "D01-gripper-sign")!;
    const b = store.getState().library.find((entry) => entry.caseId === "D10-opaque-policy-state")!;
    store.selectLibraryCase(a.caseKey);
    await waitFor(() => store.getState().screen.kind === "ready" && !store.getState().pendingSelection);
    const countA = requests.filter((url) => url.includes(a.generation)).length;
    expect(countA).toBe(1);
    store.selectLibraryCase(b.caseKey);
    await waitFor(() => !store.getState().pendingSelection);
    store.selectLibraryCase(a.caseKey);
    await waitFor(() => !store.getState().pendingSelection);
    expect(requests.filter((url) => url.includes(a.generation))).toHaveLength(countA);
    const screen = store.getState().screen;
    expect(screen.kind === "ready" && screen.caseRecord.case_key).toBe(a.caseKey);
    await store.open(parseLocator(`?evidence=${encodeURIComponent(a.evidence)}&g=${"0".repeat(64)}`), "push");
    expect(store.getState().selectionIssue).not.toBeNull();
    expect(store.getState().screen).toMatchObject({ kind: "ready", caseRecord: { case_key: a.caseKey } });
  } finally { store.dispose(); }
});

it("lets the latest case win and cancels a pending case when the current choice is selected", async () => {
  const disk = fetchFromDisk();
  let delayed = false, release = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const store = new InstrumentStore({ fetch: async (url, init) => { if (url.includes("D10-opaque-policy-state/generations/")) { delayed = true; await gate; } return disk(url, init); }, digest, maxBytes: 64 * 1024 * 1024 });
  try {
    await store.refreshLibrary();
    const a = store.getState().library.find((entry) => entry.caseId === "D01-gripper-sign")!;
    const b = store.getState().library.find((entry) => entry.caseId === "D10-opaque-policy-state")!;
    const c = store.getState().library.find((entry) => entry.caseId === "D03-observation-backlog")!;
    store.selectLibraryCase(a.caseKey);
    await waitFor(() => store.getState().screen.kind === "ready" && !store.getState().pendingSelection);
    store.selectLibraryCase(b.caseKey); await waitFor(() => delayed);
    expect(store.getState().pendingSelection?.caseKey).toBe(b.caseKey);
    store.selectLibraryCase(a.caseKey);
    expect(store.getState().pendingSelection).toBeNull();
    expect(store.getState().screen).toMatchObject({ kind: "ready", caseRecord: { case_key: a.caseKey } });
    store.selectLibraryCase(b.caseKey); store.selectLibraryCase(c.caseKey);
    await waitFor(() => !store.getState().pendingSelection);
    release(); await new Promise((resolve) => setTimeout(resolve, 30));
    expect(store.getState().screen).toMatchObject({ kind: "ready", caseRecord: { case_key: c.caseKey } });
  } finally { release(); store.dispose(); }
});
