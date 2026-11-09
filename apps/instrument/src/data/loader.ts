// Verified loading of a generation over static HTTP. Root first, children
// after; every child's bytes are checked against the manifest before parsing.
// A superseded load is abandoned through its AbortSignal and can never
// overwrite a newer selection.

import {
  DecodeError,
  SUPPORTED,
  UnsupportedSchemaError,
  decodeCase,
  decodeEvidence,
  decodeManifest,
  decodeModel,
  decodeSamples,
  isRecord,
  type Evidence,
} from "../model/decode";
import { V1, decodeCaseV1, decodeDecisionV1, decodeDiscoveryV1, decodeManifestV1, decodeModelV1, decodeSamplesV1 } from "../model/decodeV1";
import { decodeFramesOffThread } from "./frameDecoder";
import { sameRun, type CaseRecord, type FileRef, type Frames, type Generation, type ModelRecord, type RunKey, type RunRecord, type Samples } from "../model/types";

// Each wire schema has its own decoder; the schema string selects it.
function schemaOf(json: unknown): string {
  return isRecord(json) && typeof json.schema === "string" ? json.schema : "";
}

function decodeEvidenceAny(json: unknown): Evidence {
  return schemaOf(json) === V1.discovery ? decodeDiscoveryV1(json) : decodeEvidence(json);
}

function decodeManifestAny(json: unknown, sha256: string, url: string, rootUrl: string): Generation {
  const schema = schemaOf(json);
  if (schema === V1.generation) return decodeManifestV1(json, sha256, url, rootUrl);
  if ((SUPPORTED.generation as readonly string[]).includes(schema)) return decodeManifest(json, sha256, url);
  throw new UnsupportedSchemaError("manifest.schema", schema, [V1.generation, ...SUPPORTED.generation]);
}

function decodeCaseAny(json: unknown, generation: Generation): CaseRecord {
  const schema = schemaOf(json);
  if (schema === V1.case) return decodeCaseV1(json, generation);
  if ((SUPPORTED.case as readonly string[]).includes(schema)) return decodeCase(json);
  throw new UnsupportedSchemaError("case.schema", schema, [V1.case, ...SUPPORTED.case]);
}

function decodeSamplesAny(json: unknown, expectation: { run: RunKey; rowCount: number; actionDimension: number; record?: RunRecord }): Samples {
  const schema = schemaOf(json);
  if (schema === V1.samples) return decodeSamplesV1(json, expectation);
  if ((SUPPORTED.samples as readonly string[]).includes(schema)) return decodeSamples(json, expectation);
  throw new UnsupportedSchemaError("samples.schema", schema, [V1.samples, ...SUPPORTED.samples]);
}

function decodeModelAny(json: unknown): ModelRecord {
  const schema = schemaOf(json);
  if (schema === V1.model) return decodeModelV1(json);
  if ((SUPPORTED.model as readonly string[]).includes(schema)) return decodeModel(json);
  throw new UnsupportedSchemaError("model.schema", schema, [V1.model, ...SUPPORTED.model]);
}
import { sha256Hex } from "./digest";
import { strictParseJson } from "./strictJson";
import { transferBytes, TransferError, type TransferOptions, type TransferProgress } from "./transfer";

export type LoadStage = "evidence" | "manifest" | "case" | "run";
export type IssueKind = "absent" | "network" | "integrity" | "decode" | "unsupported-schema" | "aborted" | "digest-unavailable";

export interface LoadIssue {
  kind: IssueKind;
  url: string;
  message: string;
  expected: string | null;
  actual: string | null;
}

export class LoadError extends Error {
  readonly stage: LoadStage;
  readonly issue: LoadIssue;
  constructor(stage: LoadStage, issue: LoadIssue) {
    super(issue.message);
    this.name = "LoadError";
    this.stage = stage;
    this.issue = issue;
  }
}

export interface LoadedRun {
  record: RunRecord;
  samples: Samples;
  frames: Frames | null;
  framesIssue: LoadIssue | null;
  model: ModelRecord | null;
  modelIssue: LoadIssue | null;
}

export type FetchLike = (input: string, init?: { signal?: AbortSignal }) => Promise<Response>;

export interface LoadProgress extends TransferProgress { url: string; stage: LoadStage }

export interface LoaderOptions {
  fetch: FetchLike;
  digest: (bytes: ArrayBuffer) => Promise<string>;
  maxBytes: number;
  stallTimeoutMs?: TransferOptions["stallTimeoutMs"];
  timeoutMs?: TransferOptions["timeoutMs"];
  onProgress?: ((progress: LoadProgress) => void) | undefined;
}

export const DEFAULT_MAX_BYTES = 64 * 1024 * 1024;

export function defaultOptions(): LoaderOptions {
  return { fetch: (input, init) => fetch(input, init), digest: sha256Hex, maxBytes: DEFAULT_MAX_BYTES };
}

function issue(kind: IssueKind, url: string, message: string, expected: string | null = null, actual: string | null = null): LoadIssue {
  return { kind, url, message, expected, actual };
}

function aborted(stage: LoadStage, url: string): LoadError {
  return new LoadError(stage, issue("aborted", url, "load superseded by a newer selection"));
}

export function absoluteUrl(url: string): string {
  const base = typeof location !== "undefined" ? location.href : undefined;
  return new URL(url, base).href;
}

export function directoryOf(url: string): string {
  const slash = url.lastIndexOf("/");
  return slash >= 0 ? url.slice(0, slash + 1) : url;
}

// Resolve a manifest-relative path and refuse anything that leaves the root.
export function resolveWithin(base: string, relative: string, stage: LoadStage): string {
  const resolved = new URL(relative, base).href;
  if (!resolved.startsWith(base)) {
    throw new LoadError(stage, issue("decode", resolved, `path "${relative}" resolves outside the generation root`));
  }
  return resolved;
}

async function fetchBytes(url: string, stage: LoadStage, signal: AbortSignal | undefined, options: LoaderOptions, expectedBytes?: number): Promise<ArrayBuffer> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await transferBytes(url, options.fetch, {
        signal, maxBytes: options.maxBytes, expectedBytes,
        stallTimeoutMs: options.stallTimeoutMs, timeoutMs: options.timeoutMs,
        onProgress: options.onProgress ? (progress) => options.onProgress!({ ...progress, url, stage }) : undefined,
      });
    } catch (error) {
      if (signal?.aborted) throw aborted(stage, url);
      // One fresh, independently verified attempt recovers a broken connection.
      // Missing, malformed or wrong-digest evidence is never silently retried.
      if (attempt === 0 && error instanceof TransferError && error.kind === "network") continue;
      throw new LoadError(stage, issue(error instanceof TransferError ? error.kind : "network", url, error instanceof Error ? error.message : String(error)));
    }
  }
}

function parseJson(bytes: ArrayBuffer, url: string, stage: LoadStage): unknown {
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new LoadError(stage, issue("decode", url, "bytes are not valid UTF-8"));
  }
  try {
    return strictParseJson(text);
  } catch (error) {
    throw new LoadError(stage, issue("decode", url, `invalid JSON: ${error instanceof Error ? error.message : String(error)}`));
  }
}

export interface Verified {
  json: unknown;
  sha256: string;
  byte_length: number;
}

export async function fetchVerified(
  url: string,
  expected: { sha256: string; byte_length?: number },
  stage: LoadStage,
  signal: AbortSignal | undefined,
  options: LoaderOptions,
): Promise<Verified> {
  const verified = await fetchVerifiedBytes(url, expected, stage, signal, options);
  return { json: parseJson(verified.bytes, url, stage), sha256: verified.sha256, byte_length: verified.byte_length };
}

async function fetchVerifiedBytes(url: string, expected: { sha256: string; byte_length?: number }, stage: LoadStage, signal: AbortSignal | undefined, options: LoaderOptions): Promise<{ bytes: ArrayBuffer; sha256: string; byte_length: number }> {
  if (expected.byte_length !== undefined && expected.byte_length > options.maxBytes) {
    throw new LoadError(stage, issue("decode", url, `declared size ${expected.byte_length} exceeds the ${options.maxBytes} byte bound`));
  }
  const bytes = await fetchBytes(url, stage, signal, options, expected.byte_length);
  if (expected.byte_length !== undefined && bytes.byteLength !== expected.byte_length) {
    throw new LoadError(
      stage,
      issue("integrity", url, `byte length ${bytes.byteLength} differs from the declared ${expected.byte_length}`, String(expected.byte_length), String(bytes.byteLength)),
    );
  }
  let actual: string;
  try {
    actual = await options.digest(bytes);
  } catch (error) {
    throw new LoadError(stage, issue("digest-unavailable", url, error instanceof Error ? error.message : String(error)));
  }
  if (signal?.aborted) throw aborted(stage, url);
  if (actual !== expected.sha256) {
    throw new LoadError(stage, issue("integrity", url, "SHA-256 of the fetched bytes differs from the manifest", expected.sha256, actual));
  }
  return { bytes, sha256: actual, byte_length: bytes.byteLength };
}

function decodeAt<T>(stage: LoadStage, url: string, fn: () => T): T {
  try {
    return fn();
  } catch (error) {
    if (error instanceof UnsupportedSchemaError) {
      throw new LoadError(stage, issue("unsupported-schema", url, error.message, error.supported.join(", "), error.schema));
    }
    if (error instanceof DecodeError) throw new LoadError(stage, issue("decode", url, error.message));
    throw error;
  }
}

// Decoded objects keyed by content digest. Bounded; a digest identifies bytes,
// so an entry can never be stale for its key.
export class ResourceCache {
  private readonly entries = new Map<string, unknown>();
  constructor(private readonly capacity = 16) {}
  get<T>(sha256: string): T | undefined {
    const value = this.entries.get(sha256);
    if (value !== undefined) {
      this.entries.delete(sha256);
      this.entries.set(sha256, value);
    }
    return value as T | undefined;
  }
  set(sha256: string, value: unknown): void {
    this.entries.delete(sha256);
    this.entries.set(sha256, value);
    while (this.entries.size > this.capacity) {
      const oldest = this.entries.keys().next().value;
      if (oldest === undefined) break;
      this.entries.delete(oldest);
    }
  }
  get size(): number {
    return this.entries.size;
  }
  clear(): void {
    this.entries.clear();
  }
}

export interface OpenedGeneration {
  evidence: Evidence;
  evidenceUrl: string;
  generation: Generation;
}

export async function readDiscovery(url: string, signal: AbortSignal | undefined, options: LoaderOptions): Promise<unknown> {
  return parseJson(await fetchBytes(url, "evidence", signal, { ...options, maxBytes: Math.min(options.maxBytes, 1024 * 1024) }), url, "evidence");
}

export async function openGeneration(evidenceUrl: string, signal: AbortSignal | undefined, options: LoaderOptions = defaultOptions(), pin: string | null = null): Promise<OpenedGeneration> {
  const url = absoluteUrl(evidenceUrl);
  const rootUrl = directoryOf(url);
  if (pin !== null) {
    if (!/^[0-9a-f]{64}$/.test(pin)) throw new LoadError("manifest", issue("decode", url, "invalid generation digest"));
    let manifestUrl = resolveWithin(rootUrl, `generations/${pin}.json`, "manifest");
    let verified: Verified;
    try {
      verified = await fetchVerified(manifestUrl, { sha256: pin }, "manifest", signal, options);
    } catch (error) {
      // The early development fixture has a different immutable path layout.
      // Only that explicit fixture may use it; never consult current discovery.
      if (!(error instanceof LoadError) || error.issue.kind !== "absent" || !/\/dev-fixture[^/]*\/$/.test(rootUrl)) throw error;
      manifestUrl = resolveWithin(rootUrl, `generations/${pin}/manifest.json`, "manifest");
      verified = await fetchVerified(manifestUrl, { sha256: pin }, "manifest", signal, options);
    }
    const generation = decodeAt("manifest", manifestUrl, () => decodeManifestAny(verified.json, pin, manifestUrl, rootUrl));
    return { evidenceUrl: url, generation, evidence: { schema: V1.discovery, label: generation.label, current: { generation_sha256: pin, manifest_path: manifestUrl.slice(rootUrl.length), byte_length: verified.byte_length } } };
  }
  const bytes = await fetchBytes(url, "evidence", signal, options);
  const evidence = decodeAt("evidence", url, () => decodeEvidenceAny(parseJson(bytes, url, "evidence")));
  const manifestUrl = resolveWithin(rootUrl, evidence.current.manifest_path, "manifest");
  const verified = await fetchVerified(
    manifestUrl,
    { sha256: evidence.current.generation_sha256, byte_length: evidence.current.byte_length },
    "manifest",
    signal,
    options,
  );
  const generation = decodeAt("manifest", manifestUrl, () => decodeManifestAny(verified.json, verified.sha256, manifestUrl, rootUrl));
  return { evidence, evidenceUrl: url, generation };
}

async function loadFile<T>(
  generation: Generation,
  ref: FileRef,
  stage: LoadStage,
  signal: AbortSignal | undefined,
  options: LoaderOptions,
  cache: ResourceCache,
  decode: (json: unknown, url: string) => T,
): Promise<T> {
  const url = resolveWithin(generation.baseUrl, ref.path, stage);
  const key = `bytes:${ref.sha256}:${ref.byte_length}`;
  const verified = cache.get<Verified>(key) ?? await fetchVerified(url, ref, stage, signal, options);
  if (signal?.aborted) throw aborted(stage, url);
  const value = decodeAt(stage, url, () => decode(verified.json, url));
  cache.set(key, verified);
  return value;
}

export async function openCase(
  generation: Generation,
  caseKey: string,
  signal: AbortSignal | undefined,
  options: LoaderOptions,
  cache: ResourceCache,
): Promise<CaseRecord> {
  const ref = generation.cases.find((c) => c.case_key === caseKey);
  if (!ref) throw new LoadError("case", issue("absent", generation.manifestUrl, `case "${caseKey}" is not in this generation`));
  const record = await loadFile(generation, ref, "case", signal, options, cache, (json, url) => {
    const decoded = decodeCaseAny(json, generation);
    if (decoded.case_key !== caseKey) throw new LoadError("case", issue("decode", url, `case file declares "${decoded.case_key}", not "${caseKey}"`));
    return decoded;
  });
  // Decision objects are required, verified separately and attached verbatim.
  for (const decisionRef of record.decisionRefs) {
    const key = `${decisionRef.sha256}`;
    if (Object.values(record.decisions).some((d) => d !== null && d.sha256 === key)) continue;
    const decision = await loadFile(generation, decisionRef, "case", signal, options, cache, (json) => decodeDecisionV1(json, generation));
    record.decisions[`${decision.stage}_decision`] = { path: decisionRef.path, sha256: decisionRef.sha256, byte_length: decisionRef.byte_length, content: decision.raw, omitted_reason: null };
  }
  if (signal?.aborted) throw aborted("case", generation.manifestUrl);
  return record;
}

export async function openRun(
  generation: Generation,
  caseRecord: CaseRecord,
  runKey: RunKey,
  signal: AbortSignal | undefined,
  options: LoaderOptions,
  cache: ResourceCache,
): Promise<LoadedRun> {
  const record = caseRecord.runs.find((r) => sameRun(r.run, runKey));
  if (!record) {
    throw new LoadError("run", issue("absent", generation.manifestUrl, `run "${runKey.run_id}" of bundle ${runKey.bundle_sha256.slice(0, 8)} is not in case "${caseRecord.case_key}"`));
  }
  const expectation = { run: record.run, rowCount: record.row_count, actionDimension: caseRecord.predicates.action_dimension, record };
  const frameKey = `frames:${record.frames?.sha256}:${record.frames?.byte_length}:${record.model?.sha256}:${record.model?.byte_length}:${record.raw_source_id}:${record.run.bundle_sha256}:${record.run.run_id}:${record.row_count}`;
  const cachedFrames = record.frames && record.model ? cache.get<Frames>(frameKey) : undefined;
  // Transfer independently bound objects together. Admission is still ordered:
  // frames require the decoded model and must agree with the original samples.
  // Settling every branch also consumes failures after cancellation.
  const [sampleResult, modelResult, frameResult] = await Promise.allSettled([
    loadFile(generation, record.samples, "run", signal, options, cache, (json) => decodeSamplesAny(json, expectation)),
    record.model ? loadFile(generation, record.model, "run", signal, options, cache, (json) => {
      const value = decodeModelAny(json);
      if (generation.schema === V1.generation && !generation.source_bindings.some((source) => (source.id ?? source.binding.split(" · ")[0]) === value.meshes.source_id && source.kind === "mjcf")) throw new DecodeError("model.source_id", "model source is not bound by this generation");
      return value;
    }) : Promise.resolve(null),
    (async () => record.frames && record.model && !cachedFrames ? fetchVerifiedBytes(resolveWithin(generation.baseUrl, record.frames.path, "run"), record.frames, "run", signal, options) : null)(),
  ]);
  if (signal?.aborted) throw aborted("run", generation.manifestUrl);
  if (sampleResult.status === "rejected") throw sampleResult.reason;
  const samples = sampleResult.value;

  let model: ModelRecord | null = null;
  let modelIssue: LoadIssue | null = null;
  if (record.model) {
    try {
      if (modelResult.status === "rejected") throw modelResult.reason;
      model = modelResult.value;
    } catch (error) {
      if (error instanceof LoadError && error.issue.kind !== "aborted") modelIssue = error.issue;
      else throw error;
    }
  } else {
    modelIssue = issue("absent", generation.manifestUrl, "this run publishes no model record");
  }

  let frames: Frames | null = null;
  let framesIssue: LoadIssue | null = null;
  if (record.frames && model) {
    try {
      // Frames are keyed by the model's declaration order, so the model decodes first.
      if (cachedFrames) frames = cachedFrames;
      else {
        const url = resolveWithin(generation.baseUrl, record.frames.path, "run");
        if (frameResult.status === "rejected") throw frameResult.reason;
        if (!frameResult.value) throw new DecodeError("reconstruction", "verified frame object unavailable");
        try { frames = await decodeFramesOffThread({ bytes: frameResult.value.bytes, expectation, model }, signal); }
        catch (error) { if (signal?.aborted) throw aborted("run", url); decodeAt("run", url, () => { throw error; }); }
      }
      if (generation.schema === V1.generation) decodeAt("run", resolveWithin(generation.baseUrl, record.frames.path, "run"), () => {
        for (const row of samples.rows) for (const phase of ["before", "after"] as const) {
          const frame = frames!.rows[row.row_index]![phase];
          if (frame.sim_time_s !== (phase === "before" ? row.action_sim_time_s : row.next_sim_time_s)) throw new DecodeError(`reconstruction.rows[${row.row_index}].${phase}`, "frame time differs from original sample");
          if (frame.state_sha256 !== row.digests[`state_${phase}_sha256`]) throw new DecodeError(`reconstruction.rows[${row.row_index}].${phase}`, "frame state digest differs from original sample");
        }
      });
      cache.set(frameKey, frames);
    } catch (error) {
      frames = null;
      if (error instanceof LoadError && error.issue.kind !== "aborted") framesIssue = error.issue;
      else throw error;
    }
  } else {
    framesIssue = issue("absent", generation.manifestUrl, record.frames ? "reconstruction requires a verified model" : "this run publishes no reconstruction frames");
  }
  if (signal?.aborted) throw aborted("run", generation.manifestUrl);
  const last = samples.rows[samples.rows.length - 1];
  const recordWithEnd: RunRecord =
    record.recording.last_next_sim_time_s === null && last ? { ...record, recording: { ...record.recording, last_next_sim_time_s: last.next_sim_time_s } } : record;
  return { record: recordWithEnd, samples, frames, framesIssue, model, modelIssue };
}

export function recordingEnd(run: LoadedRun): number {
  return run.record.recording.last_next_sim_time_s ?? run.samples.rows[run.samples.rows.length - 1]?.next_sim_time_s ?? 0;
}
