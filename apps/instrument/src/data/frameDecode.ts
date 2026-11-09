import { DecodeError, SUPPORTED, UnsupportedSchemaError, decodeFrames, isRecord } from "../model/decode";
import { V1, decodeReconstructionV1 } from "../model/decodeV1";
import type { Frames, ModelRecord, RunKey, RunRecord } from "../model/types";
import { strictParseJson } from "./strictJson";

export interface FrameDecodeRequest { bytes: ArrayBuffer; expectation: { run: RunKey; rowCount: number; record?: RunRecord }; model: ModelRecord }
export function decodeFrameBytes({ bytes, expectation, model }: FrameDecodeRequest): Frames {
  let json: unknown;
  try { json = strictParseJson(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch (error) { throw new DecodeError("reconstruction", `Invalid JSON: ${error instanceof Error ? error.message : String(error)}`); }
  const schema = isRecord(json) && typeof json.schema === "string" ? json.schema : "";
  if (schema === V1.reconstruction) return decodeReconstructionV1(json, expectation, model);
  if ((SUPPORTED.frames as readonly string[]).includes(schema)) return decodeFrames(json, expectation, model);
  throw new UnsupportedSchemaError("frames.schema", schema, [V1.reconstruction, ...SUPPORTED.frames]);
}
export function frameBuffers(frames: Frames): ArrayBuffer[] {
  const buffers = new Set<ArrayBuffer>();
  for (const row of frames.rows) for (const phase of [row.before, row.after]) for (const array of [phase.xpos, phase.xquat, phase.sites, phase.geoms]) buffers.add(array.buffer as ArrayBuffer);
  return [...buffers];
}
