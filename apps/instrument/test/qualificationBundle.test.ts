// @vitest-environment node
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFileSync } from "node:child_process";
import { createHash, webcrypto } from "node:crypto";
import { describe, expect, it, vi } from "vitest";
import { inspectBundle, readStoredZip } from "../src/qualification/bundle";
import { atPointer, display, parseRecord } from "../src/qualification/json";

vi.stubGlobal("crypto", webcrypto);
const original = (name: string) => new Uint8Array(readFileSync(new URL(`./fixtures/qualification/${name}.nisayon.zip`, import.meta.url))).buffer;
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const encoder = new TextEncoder();
// Independent ZIP writer: controls do not use the reader's serialization.
function pack(files: Map<string, Uint8Array>, reindex = false, extra?: [string, Uint8Array]) {
  if (reindex) {
    const index = JSON.parse(new TextDecoder().decode(files.get("bundle.json")));
    index.files = Object.fromEntries([...files].filter(([name]) => name !== "bundle.json").map(([name, bytes]) => [name, { bytes: bytes.byteLength, sha256: hash(bytes) }]));
    files.set("bundle.json", encoder.encode(JSON.stringify(index)));
  }
  const rows = [...files, ...(extra ? [extra] : [])].map(([name, bytes]) => [name, Buffer.from(bytes).toString("base64")]);
  // Large simultaneous stdin/stdout pipes stalled a local synchronous child.
  // Bound the independent writer and exchange fixtures through private files.
  const directory = mkdtempSync(join(tmpdir(), "nisayon-zip-control-"));
  try {
    const input = join(directory, "input.json"), output = join(directory, "control.zip");
    writeFileSync(input, JSON.stringify(rows));
    execFileSync("python3", ["-c", "import sys,json,base64,zipfile,stat\nwith open(sys.argv[1]) as f: rows=json.load(f)\nwith zipfile.ZipFile(sys.argv[2],'w') as z:\n for n,v in rows:\n  i=zipfile.ZipInfo(n);i.create_system=3;i.external_attr=(stat.S_IFREG|0o600)<<16;z.writestr(i,base64.b64decode(v))", input, output], { timeout: 10_000, stdio: ["ignore", "ignore", "pipe"] });
    return new Uint8Array(readFileSync(output)).buffer;
  } finally { rmSync(directory, { recursive: true, force: true }); }
}
function changeAssessment(files: Map<string, Uint8Array>, update: Record<string, unknown>) {
  const record = JSON.parse(new TextDecoder().decode(files.get("assessment.json")));
  files.set("assessment.json", encoder.encode(JSON.stringify({ ...record, ...update })));
}

describe("real portable SDK records", () => {
  it.each([["merged", "adopt", 22, "ebaa6035ef64ae19900f139662ef94a8368fbc09f5e079bd39f60bec4ea7305c"], ["restored-defect", "reject", 9, "48908d2094c0ea00c8642e09473e6b8c12d2636b8117a42024d4529175470ee2"]] as const)("reads %s without changing any original byte", async (name, decision, agreements, sha) => {
    const buffer = original(name), before = Buffer.from(buffer).toString("base64");
    const result = await inspectBundle(buffer, `${name}.nisayon.zip`);
    expect(result.sha256).toBe(sha); expect(result.files.size).toBe(402);
    expect(result.assessment.software_decision).toBe(decision);
    expect(result.assessment.deployment_decision).toBe("unresolved");
    expect(result.assessment.execution_validity).toBe("valid");
    expect(result.comparisons.filter(c => c.candidate_difference === null)).toHaveLength(agreements);
    expect(result.files.has("evidence/candidate-single6-ee-obs-vector/observation.json")).toBe(true);
    expect(Buffer.from(buffer).toString("base64")).toBe(before);
  });
  it("does not promote a rehashed saved verdict into a new Python assessment", async () => {
    const files = readStoredZip(original("restored-defect")); changeAssessment(files, { software_decision: "adopt" });
    const result = await inspectBundle(pack(files, true), "rewritten.zip");
    // A browser reader exposes what was saved. Only SDK review can reassess.
    expect(result.assessment.software_decision).toBe("adopt");
    expect(result).not.toHaveProperty("review_status");
    expect(result).not.toHaveProperty("assessment_agrees");
    expect(result.comparisons.filter(c => c.candidate_difference !== null)).toHaveLength(13);
  });
  it.each(["invalid", "incomplete", "not_executed"])("preserves a saved %s experiment instead of hiding it", async validity => {
    const files = readStoredZip(original("merged")); changeAssessment(files, { software_decision: "unresolved", execution_validity: validity, comparisons: [], costs: { engineering_seconds: null } });
    const result = await inspectBundle(pack(files, true), "unfinished.zip");
    expect(result.assessment.execution_validity).toBe(validity); expect(display(result.assessment.costs)).toContain("null");
    expect(result.probes).toHaveLength(22);
  });
  it("rejects changed bytes even when the ZIP CRC is rewritten", async () => {
    const files = readStoredZip(original("merged")); changeAssessment(files, { software_decision: "reject" });
    await expect(inspectBundle(pack(files), "changed.zip")).rejects.toThrow("cannot verify assessment.json");
  });
  it("rejects missing members, duplicated names and hidden wrapper bytes", async () => {
    const files = readStoredZip(original("merged")); files.delete("evidence/seal.json");
    await expect(inspectBundle(pack(files), "omitted.zip")).rejects.toThrow("membership");
    expect(() => readStoredZip(pack(files, false, ["assessment.json", files.get("assessment.json")!]))).toThrow("duplicate");
    const wrapped = new Uint8Array(original("merged").byteLength + 1); wrapped.set(new Uint8Array(original("merged")), 1);
    expect(() => readStoredZip(wrapped.buffer)).toThrow();
  });
  it.each(["../source.json", "Evidence/extra.json", "evidence/CON.txt", "evidence/plan.json/child.json"])("rejects ambiguous or unsafe path %s", path => {
    const files = readStoredZip(original("merged")); files.set(path, encoder.encode("{}"));
    expect(() => readStoredZip(pack(files, true))).toThrow();
  });
  it("refuses contradictory plan identities and malformed assignments", async () => {
    const files = readStoredZip(original("merged")); changeAssessment(files, { plan_sha256: "0".repeat(64) });
    await expect(inspectBundle(pack(files, true), "other-plan.zip")).rejects.toThrow("same supported experiment");
    const clean = readStoredZip(original("merged")); const plan = JSON.parse(new TextDecoder().decode(clean.get("evidence/plan.json")));
    plan.assignments[0].id = "../unexpected"; clean.set("evidence/plan.json", encoder.encode(JSON.stringify(plan)));
    await expect(inspectBundle(pack(clean, true), "assignment.zip")).rejects.toThrow("assignments");
  });
});

describe("lossless record inspection", () => {
  it("keeps signed zero, numeric spelling, large integers and pointer escapes", () => {
    const record = parseRecord('{"a/b":{"~": [9007199254740993,-0.0,1.0,1e-07]},"__proto__":42}');
    expect(display(atPointer(record, "/a~1b/~0/0"))).toBe("9007199254740993");
    expect(display(atPointer(record, "/a~1b/~0/1"))).toBe("-0.0");
    expect(display(atPointer(record, "/a~1b/~0/2"))).toBe("1.0");
    expect(display(atPointer(record, "/a~1b/~0/3"))).toBe("1e-07");
    expect(display(atPointer(record, "/__proto__"))).toBe("42");
  });
  it.each(['{"a":1,"a":2}', '[1,]', '{"x":NaN}', '01', '"unterminated', 'truefalse'])("rejects unsupported JSON %s", source => expect(() => parseRecord(source)).toThrow());
});
