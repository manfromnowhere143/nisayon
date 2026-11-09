import { decodeFrameBytes, frameBuffers, type FrameDecodeRequest } from "./frameDecode";
import { UnsupportedSchemaError } from "../model/decode";

self.onmessage = (event: MessageEvent<FrameDecodeRequest>) => {
  try { const frames = decodeFrameBytes(event.data); self.postMessage({ frames }, { transfer: frameBuffers(frames) }); }
  catch (error) { self.postMessage({ error: error instanceof Error ? error.message : "Reconstruction decode failed", ...(error instanceof UnsupportedSchemaError ? { schema: error.schema, supported: error.supported } : {}) }); }
};
