import { array, count, object, parseRecord, string, type Json, type JsonObject } from "./json";

const MIB = 1024 * 1024;
export const MAX_BUNDLE_BYTES = 68 * MIB;
const decoder = new TextDecoder("utf-8", { fatal: true });
const digest = async (bytes: Uint8Array) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes as Uint8Array<ArrayBuffer>))].map(b => b.toString(16).padStart(2, "0")).join("");
const problem = (message: string): never => { throw new Error(message); };
const reserved = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i;
function memberName(name: string) {
  if (name.length > 512 || !name.split("/").every(p => /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,159}$/.test(p) && !p.endsWith(".") && !reserved.test(p))) problem("This package contains an unsupported file name.");
}
function crc32(bytes: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/** Only the SDK's bounded, uncompressed ZIP v1. Never inflates or executes a member. */
export function readStoredZip(buffer: ArrayBuffer): Map<string, Uint8Array> {
  if (buffer.byteLength < 22 || buffer.byteLength > MAX_BUNDLE_BYTES) return problem("Choose a Nisayon review file smaller than 68 MiB.");
  const bytes = new Uint8Array(buffer), view = new DataView(buffer), end = buffer.byteLength - 22;
  if (view.getUint32(end, true) !== 0x06054b50 || view.getUint16(end + 20, true) !== 0) return problem("This is not a supported Nisayon review file.");
  const members = view.getUint16(end + 10, true), start = view.getUint32(end + 16, true), size = view.getUint32(end + 12, true);
  if (view.getUint16(end + 4, true) || view.getUint16(end + 6, true) || view.getUint16(end + 8, true) !== members || !members || members > 4096 || start + size !== end) return problem("The review file has an invalid directory.");
  const files = new Map<string, Uint8Array>(), names = new Map<string, string>(), intervals: [number, number][] = [];
  let at = start, total = 0;
  for (let i = 0; i < members; i++) {
    if (at + 46 > end || view.getUint32(at, true) !== 0x02014b50) return problem("The review directory is incomplete.");
    const flags = view.getUint16(at + 8, true), method = view.getUint16(at + 10, true), crc = view.getUint32(at + 16, true);
    const packed = view.getUint32(at + 20, true), length = view.getUint32(at + 24, true), nameLength = view.getUint16(at + 28, true);
    const extra = view.getUint16(at + 30, true), comment = view.getUint16(at + 32, true), offset = view.getUint32(at + 42, true), mode = view.getUint32(at + 38, true) >>> 16;
    if (flags || method || packed !== length || extra || comment || view.getUint16(at + 34, true) || (mode & 0xf000) !== 0x8000 || at + 46 + nameLength > end) return problem("This package uses an unsupported ZIP feature.");
    const name = decoder.decode(bytes.subarray(at + 46, at + 46 + nameLength)); memberName(name);
    if (files.has(name)) return problem("This package contains a duplicate member.");
    const parts = name.split("/");
    for (let j = 1; j <= parts.length; j++) {
      const prefix = parts.slice(0, j).join("/"), alias = prefix.toLowerCase(), previous = names.get(alias);
      if (previous && previous !== prefix) return problem("This package contains ambiguous file names.");
      names.set(alias, prefix);
    }
    if (length > (name === "bundle.json" ? MIB : 16 * MIB)) return problem("A review member is too large.");
    if (name !== "bundle.json") total += length;
    if (total > 64 * MIB || offset + 30 > start || view.getUint32(offset, true) !== 0x04034b50) return problem("This package exceeds its supported bounds.");
    const localNameLength = view.getUint16(offset + 26, true), localExtra = view.getUint16(offset + 28, true), begin = offset + 30 + localNameLength;
    if (view.getUint16(offset + 6, true) !== flags || view.getUint16(offset + 8, true) !== method || view.getUint32(offset + 14, true) !== crc || view.getUint32(offset + 18, true) !== length || view.getUint32(offset + 22, true) !== length || localExtra || begin + length > start || decoder.decode(bytes.subarray(offset + 30, begin)) !== name) return problem("The review file headers disagree.");
    const payload = bytes.subarray(begin, begin + length);
    if (crc32(payload) !== crc) return problem(`The bytes of ${name} have changed.`);
    files.set(name, payload); intervals.push([offset, begin + length]);
    at += 46 + nameLength;
  }
  intervals.sort((a, b) => a[0] - b[0]);
  let previous = 0;
  for (const [begin, finish] of intervals) { if (begin !== previous) return problem("The package contains hidden or overlapping bytes."); previous = finish; }
  if (previous !== start || at !== end) return problem("The package directory does not cover its bytes.");
  for (const name of files.keys()) {
    const parts = name.split("/");
    for (let i = 1; i < parts.length; i++) if (files.has(parts.slice(0, i).join("/"))) return problem("A package member is also a directory.");
  }
  return files;
}

export interface QualificationBundle {
  sha256: string;
  planSha256: string;
  fileName: string;
  files: Map<string, Uint8Array>;
  plan: JsonObject;
  case: JsonObject;
  assessment: JsonObject;
  comparisons: JsonObject[];
  probes: JsonObject[];
}
export function readRecord(files: Map<string, Uint8Array>, path: string): Json | undefined {
  const bytes = files.get(path);
  return bytes ? parseRecord(decoder.decode(bytes)) : undefined;
}
export async function verifyArchive(buffer: ArrayBuffer, progress?: (done: number, total: number) => void) {
  const files = readStoredZip(buffer);
  const index = object(readRecord(files, "bundle.json"), "package index");
  const members = object(index.files, "member index");
  if (Object.keys(members).length !== files.size - 1 || Object.hasOwn(members, "bundle.json")) return problem("The package membership differs from its index.");
  let done = 0;
  for (const [name, row] of Object.entries(members)) {
    const entry = object(row, "member identity"), bytes = files.get(name);
    if (Object.keys(entry).sort().join() !== "bytes,sha256" || !bytes || count(entry.bytes, 16 * MIB) !== bytes.byteLength || string(entry.sha256) !== await digest(bytes)) return problem(`The package cannot verify ${name}.`);
    progress?.(++done, files.size - 1);
  }
  return { files, index, sha256: await digest(new Uint8Array(buffer)) };
}
export function comparisonArchive(archive: Awaited<ReturnType<typeof verifyArchive>>, fileName: string): QualificationBundle {
  const { files, index, sha256 } = archive;
  if (index.schema !== "nisayon.qualification.bundle.v1" || Object.keys(index).sort().join() !== "files,plan_sha256,schema") return problem("This package format is not supported yet.");
  return hydrateBundle(files, sha256, fileName, string(index.plan_sha256, "plan identity"));
}
export async function inspectBundle(buffer: ArrayBuffer, fileName: string, progress?: (done: number, total: number) => void): Promise<QualificationBundle> {
  return comparisonArchive(await verifyArchive(buffer, progress), fileName);
}

/** Read the saved semantics after the transport bytes have been checked. */
export function hydrateBundle(files: Map<string, Uint8Array>, sha256: string, fileName: string, planSha256: string): QualificationBundle {
  if (!/^[a-f0-9]{64}$/.test(planSha256)) return problem("The package plan identity is invalid.");
  const plan = object(readRecord(files, "evidence/plan.json"), "plan"), assessment = object(readRecord(files, "assessment.json"), "assessment");
  if (!["nisayon.qualification.plan.v1", "nisayon.qualification.plan.v2"].includes(string(plan.schema)) || assessment.schema !== "nisayon.qualification.assessment.v1" || assessment.plan_sha256 !== planSha256) return problem("The plan and saved assessment do not identify the same supported experiment.");
  if (plan.schema === "nisayon.qualification.plan.v2" && plan.read_policy !== "cpython_owner_reads_v1") return problem("This plan's read observation policy is not supported yet.");
  const case_ = object(plan.case, "case");
  if (case_.schema !== "nisayon.qualification.case.v1") return problem("This case format is not supported yet.");
  string(case_.question, "question");
  if (!["adopt", "reject", "unresolved"].includes(string(assessment.software_decision)) || assessment.deployment_decision !== "unresolved" || !["valid", "invalid", "incomplete", "not_executed"].includes(string(assessment.execution_validity))) return problem("The saved assessment contains unsupported decision semantics.");
  const probes = array(case_.probes, "probes").map(p => object(p, "probe"));
  if (probes.length < 1 || probes.length > 32) return problem("This case has an unsupported number of probes.");
  const ids = probes.map(p => string(p.id));
  if (new Set(ids).size !== ids.length || ids.some(id => !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(id))) return problem("The probe identities are ambiguous.");
  const comparisons = array(assessment.comparisons, "comparisons").map(p => object(p, "comparison"));
  if (comparisons.length > 32 || new Set(comparisons.map(p => p.probe)).size !== comparisons.length || comparisons.some(p => !ids.includes(string(p.probe)))) return problem("The saved comparison identities are ambiguous.");
  for (const comparison of comparisons) for (const key of ["candidate_difference", "negative_control_difference", "reference_oracle_difference"]) {
    if (comparison[key] === null) continue;
    const difference = object(comparison[key], "saved difference");
    const pointer = string(difference.path, "difference path");
    if ((pointer !== "" && !pointer.startsWith("/")) || /~(?:[^01]|$)/.test(pointer) || !Object.hasOwn(difference, "reference") || !Object.hasOwn(difference, "candidate")) return problem("The saved difference cannot be inspected unambiguously.");
    string(difference.reason, "difference reason");
  }
  const assignments = array(plan.assignments, "assignments").map(a => object(a, "assignment"));
  if (assignments.length > 96 || new Set(assignments.map(a => a.id)).size !== assignments.length || assignments.some(a => !["reference", "negative_control", "candidate"].includes(string(a.role)) || !ids.includes(string(a.probe)) || a.id !== `${a.role}-${a.probe}`)) return problem("The attempt assignments are ambiguous.");
  return { sha256, planSha256, fileName, files, plan, case: case_, assessment, comparisons, probes };
}
