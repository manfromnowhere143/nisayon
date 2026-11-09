import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CheckReview } from "../src/qualification/CheckReview";
import { NativeTaskResult } from "../src/qualification/NativeTaskResult";
import { inspectReview, isCheckBundle, type CheckBundle } from "../src/qualification/checkBundle";
import { array, object } from "../src/qualification/json";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  vi.stubGlobal("crypto", { subtle: { digest: async (_: string, bytes: Uint8Array) => new Uint8Array(createHash("sha256").update(bytes).digest()).buffer } });
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function bundle(): Promise<CheckBundle> {
  const raw = readFileSync("test/fixtures/native-task/n100-spatial.nisayon.zip");
  const provenance = JSON.parse(readFileSync("test/fixtures/native-task/provenance.json", "utf8"));
  expect(createHash("sha256").update(raw).digest("hex")).toBe(provenance.export.bundle_sha256);
  const result = await inspectReview(new Uint8Array(raw).buffer, "n100-spatial.nisayon.zip");
  if (!isCheckBundle(result)) throw new Error("Wrong fixture format");
  return result;
}
async function result() { return object((await bundle()).checks.find(check => check.id === "reconstruct")!.result); }
async function click(label: string) {
  const button = [...host.querySelectorAll<HTMLButtonElement>("button")].find(button => button.textContent?.trim() === label);
  expect(button).toBeDefined(); await act(async () => button!.click());
}

it("imports the actual native SDK export and opens its five pairs through the existing review", async () => {
  await act(async () => root.render(<CheckReview active bundle={await bundle()} />));
  await click("Task outcomes ↗");
  const dialog = host.querySelector("dialog")!;
  expect(dialog.querySelectorAll("tbody tr")).toHaveLength(5);
  expect(dialog.textContent).toContain("No regression observed in 5 recorded pairs");
  expect(dialog.textContent).toContain("Measurement adequacy: unresolved");
  expect(dialog.textContent).toContain("no new robot execution");
  expect(dialog.textContent).toContain("74 steps");
  expect(dialog.textContent).toContain("70 steps");
  expect(host.querySelector(".is-unresolved")?.textContent).toBe("Unresolved");
});

it("shows a recorded regression without turning it into invalid data", async () => {
  const value = await result();
  const row = object(array(value.pairs)[2]);
  row.candidate_success = false; row.transition = "regression";
  value.verdict = "rejected"; value.recorded_outcome = "observed_regression";
  await act(async () => root.render(<NativeTaskResult value={value} />));
  expect(host.textContent).toContain("1 recorded regression in 5 pairs");
  expect(host.querySelectorAll("tbody tr")).toHaveLength(5);
  expect(host.textContent).toContain("Failure");
});

it("keeps invalid records distinct from failed tasks", async () => {
  const value = await result();
  value.status = "invalid"; value.verdict = "unresolved"; value.recorded_outcome = "unresolved";
  value.pairs = []; value.errors = ["candidate:unfinished_episode"];
  await act(async () => root.render(<NativeTaskResult value={value} />));
  expect(host.querySelector("table")).toBeNull();
  expect(host.textContent).toContain("records are invalid");
  expect(host.textContent).toContain("unfinished_episode");
});

it.each(["authority", "fresh_execution", "string_success", "contradictory_transition", "duplicate_pair", "contradictory_verdict"])("refuses to summarize a %s contradiction", async fault => {
  const value = await result();
  const rows = array(value.pairs), first = object(rows[0]);
  if (fault === "authority") value.measurement_adequacy = "supported";
  if (fault === "fresh_execution") value.new_native_execution = true;
  if (fault === "string_success") first.candidate_success = "false";
  if (fault === "contradictory_transition") first.transition = "improvement";
  if (fault === "duplicate_pair") rows.push(first);
  if (fault === "contradictory_verdict") value.verdict = "rejected";
  await act(async () => root.render(<NativeTaskResult value={value} />));
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("unsupported or inconsistent");
  expect(host.querySelector("table")).toBeNull();
});

it("renders task text without interpreting markup", async () => {
  const value = await result(); value.scope = '<img src=x onerror="alert(1)">';
  await act(async () => root.render(<NativeTaskResult value={value} />));
  expect(host.querySelector("img")).toBeNull();
  expect(host.textContent).toContain("<img");
});
