// @vitest-environment node
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { createHash, webcrypto } from "node:crypto";
import { describe, expect, it, vi } from "vitest";
import { inspectReview, isCheckBundle } from "../src/qualification/checkBundle";
import { readRecord, readStoredZip } from "../src/qualification/bundle";
import { array, display, object } from "../src/qualification/json";

vi.stubGlobal("crypto", webcrypto);
const fixture = (name: string) => new Uint8Array(readFileSync(new URL(`./fixtures/checks/${name}.nisayon.zip`, import.meta.url))).buffer;
function alter(name: string, edit: (files: Map<string, Uint8Array>, prefix: string) => void, rehash = true) {
  const files = readStoredZip(fixture(name));
  const prefix = `evidence/${object(readRecord(files, "assessment.json")).execution_path}`;
  edit(files, prefix);
  const index = JSON.parse(new TextDecoder().decode(files.get("bundle.json")));
  if (rehash) index.files = Object.fromEntries([...files].filter(([n]) => n !== "bundle.json").map(([n, bytes]) => [n, { bytes: bytes.byteLength, sha256: createHash("sha256").update(bytes).digest("hex") }]));
  files.set("bundle.json", new TextEncoder().encode(JSON.stringify(index)));
  const directory = mkdtempSync(join(tmpdir(), "nisayon-check-zip-"));
  try {
    const input = join(directory, "in.json"), output = join(directory, "out.zip");
    writeFileSync(input, JSON.stringify([...files].map(([n, v]) => [n, Buffer.from(v).toString("base64")])));
    execFileSync("python3", ["-c", "import sys,json,zipfile,base64,stat\nwith open(sys.argv[1]) as f:r=json.load(f)\nwith zipfile.ZipFile(sys.argv[2],'w') as z:\n for n,v in r:\n  i=zipfile.ZipInfo(n);i.create_system=3;i.external_attr=(stat.S_IFREG|0o600)<<16;z.writestr(i,base64.b64decode(v))", input, output], { timeout: 10_000 });
    return new Uint8Array(readFileSync(output)).buffer;
  } finally { rmSync(directory, { recursive: true, force: true }); }
}
function edit(files: Map<string, Uint8Array>, path: string, mutate: (record: any) => void) {
  const value = JSON.parse(new TextDecoder().decode(files.get(path))); mutate(value);
  files.set(path, new TextEncoder().encode(JSON.stringify(value)));
}

describe("portable executable-check records", () => {
  it.each([["rescored", "reject"], ["historical", "supported"], ["rejected", "rejected"], ["unknown", undefined], ["failed", undefined]])("reads SDK %s with saved claims and no browser adjudication", async (name, claim) => {
    const raw = fixture(name!), before = Buffer.from(raw).toString("base64");
    const result = await inspectReview(raw, `${name}.zip`);
    expect(isCheckBundle(result)).toBe(true);
    if (!isCheckBundle(result)) throw new Error("wrong format");
    expect(result.checks).toHaveLength(4);
    expect(result.claims[0]?.value).toBe(claim);
    expect(result.execution.deployment_decision).toBe("unresolved");
    expect(result).not.toHaveProperty("review_status");
    expect(Buffer.from(raw).toString("base64")).toBe(before);
  });
  it("preserves reused observations and historical confirmation scope", async () => {
    const rescored = await inspectReview(fixture("rescored"), "reuse.zip");
    const historic = await inspectReview(fixture("historical"), "historic.zip");
    if (!isCheckBundle(rescored) || !isCheckBundle(historic)) throw new Error("wrong format");
    expect(rescored.checks.find(c => c.id === "observe")?.selection.action).toBe("reuse");
    expect(object(historic.checks.find(c => c.id === "confirm")?.result).new_simulator_execution).toBe(false);
    expect(historic.model.scope).toContain("Unconverged");
  });
  it("continues to open the existing native-comparison packages", async () => {
    const raw = new Uint8Array(readFileSync(new URL("./fixtures/qualification/sdk-v2-accepted.nisayon.zip", import.meta.url))).buffer;
    expect(isCheckBundle(await inspectReview(raw, "existing.zip"))).toBe(false);
  });
  it("rejects modified bytes without a new index", async () => {
    const raw = alter("historical", (files, prefix) => edit(files, `${prefix}/execution.json`, r => { r.status = "unresolved"; }), false);
    await expect(inspectReview(raw, "bad.zip")).rejects.toThrow("cannot verify");
  });
  it.each(["authority", "missing_attempt", "cycle", "cached_confirmation", "result", "identity", "path", "version"])("refuses rehashed contradictory %s records", async kind => {
    const raw = alter("historical", (files, prefix) => {
      if (kind === "authority") edit(files, `${prefix}/execution.json`, r => { r.deployment_decision = "adopt"; });
      if (kind === "missing_attempt") edit(files, `${prefix}/execution.json`, r => { r.attempts.pop(); });
      if (kind === "cycle") edit(files, `${prefix}/model.json`, r => { r.checks.observe.depends_on = ["observe"]; });
      if (kind === "cached_confirmation") edit(files, `${prefix}/model.json`, r => { r.checks.confirm.refresh = "on_change"; });
      if (kind === "result") edit(files, "assessment.json", r => { r.review.artifacts.review.verdict = "rejected"; });
      if (kind === "identity") edit(files, "assessment.json", r => { r.model_sha256 = "0".repeat(64); });
      if (kind === "path") edit(files, "assessment.json", r => { r.execution_path = "../escape"; });
      if (kind === "version") edit(files, `${prefix}/execution.json`, r => { r.schema = "future"; });
    });
    await expect(inspectReview(raw, "bad.zip")).rejects.toThrow();
  });
  it("does not round large values in original supplementary records", async () => {
    const raw = alter("historical", (files, prefix) => { files.set(`${prefix}/note.json`, new TextEncoder().encode('{"value":9007199254740993,"zero":-0.0}')); });
    const result = await inspectReview(raw, "note.zip");
    if (!isCheckBundle(result)) throw new Error("wrong format");
    const note = object(readRecord(result.files, `${result.prefix}/note.json`));
    expect(display(note.value)).toBe("9007199254740993");
    expect(display(note.zero)).toBe("-0.0");
  });
  it.each(["reuse_required_fresh", "selection_kind", "completed_error"])("refuses a rehashed %s contradiction", async kind => {
    const raw = alter("historical", (files, prefix) => {
      if (kind === "completed_error") edit(files, `${prefix}/execution.json`, r => { r.errors = ["confirmation failed"]; });
      if (kind === "selection_kind") edit(files, `${prefix}/applicability.json`, r => { r.checks.confirm.kind = "observation"; });
      if (kind === "reuse_required_fresh") {
        edit(files, `${prefix}/applicability.json`, r => { r.checks.confirm.action = "reuse"; });
        edit(files, `${prefix}/execution.json`, r => { r.attempts.find((a: any) => a.check === "confirm").action = "reuse"; });
        for (const name of ["intent", "completion"]) edit(files, `${prefix}/checks/confirm/${name}.json`, r => { r.action = "reuse"; });
      }
    });
    await expect(inspectReview(raw, "contradiction.zip")).rejects.toThrow();
  });
  const inspectRecords = JSON.parse(readFileSync(new URL("./fixtures/inspect-checks/provenance.json", import.meta.url), "utf8")).records as { name: string; file: string; sha256: string; selections: Record<string, string> }[];
  it.each(inspectRecords)("preserves retained Inspect $name records through the instrument reader", async record => {
    const bytes = readFileSync(new URL(`./fixtures/inspect-checks/${record.file}`, import.meta.url));
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(record.sha256);
    const bundle = await inspectReview(new Uint8Array(bytes).buffer, record.file);
    if (!isCheckBundle(bundle)) throw new Error("wrong format");
    expect(Object.fromEntries(bundle.checks.map(check => [check.id, check.selection.action]))).toEqual(record.selections);
    expect(bundle.execution.deployment_decision).toBe("unresolved");
    expect(bundle.execution.costs && object(bundle.execution.costs).complete_cost).toBeNull();
    expect(bundle.model.scope).toContain("Inspect Robots #572");
    if (record.name === "admission") {
      const results = array(object(bundle.checks[0]!.result).results);
      expect(results).toHaveLength(15);
      const counts: Record<string, number> = {};
      for (const result of results) { const decision = object(result).decision as string; counts[decision] = (counts[decision] ?? 0) + 1; }
      expect(counts).toEqual({ supported: 2, rejected: 4, unknown: 3, invalid: 6 });
      expect(bundle.claims).toHaveLength(0); // The batch is not one blanket acceptance.
    } else {
      const observation = object(bundle.checks.find(c => c.id === "observe")!.result);
      expect(display(observation.acquisition_count)).toBe(record.name === "data_bytes" ? "1" : "0");
      expect(bundle.claims.map(c => c.value)).toEqual(["supported"]);
      if (record.name === "data_bytes") {
        const initial = object(object(bundle.checks.find(c => c.id === "score")!.result).initial);
        expect(initial.decision).toBe("invalid");
        expect(initial.reason).toBe("mismatched_fixture_sha256");
      }
    }
  });
  it("compares structured records independently of object field order", async () => {
    const raw = alter("historical", (files, prefix) => edit(files, `${prefix}/execution.json`, r => { r.state = Object.fromEntries(Object.entries(r.state).reverse()); }));
    expect(isCheckBundle(await inspectReview(raw, "reordered.zip"))).toBe(true);
  });
  it.each([["9007199254740992", "9007199254740993"], ["0.0", "-0.0"]])("retains numeric spelling in result consistency checks: %s / %s", async (original, saved) => {
    const raw = alter("historical", (files, prefix) => {
      const path = `${prefix}/checks/review/result.json`;
      const content = new TextDecoder().decode(files.get(path));
      files.set(path, new TextEncoder().encode(content.replace("{", `{"numeric_probe":${original},`)));
      edit(files, "assessment.json", r => { r.review.artifacts.review.numeric_probe = "NUMERIC_PROBE"; });
      const assessment = new TextDecoder().decode(files.get("assessment.json"));
      files.set("assessment.json", new TextEncoder().encode(assessment.replace('"NUMERIC_PROBE"', saved)));
    });
    await expect(inspectReview(raw, "numeric.zip")).rejects.toThrow("differs from its original result");
  });
});
