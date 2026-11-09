import { DecodeError, UnsupportedSchemaError } from "../model/decode";
import type { Frames } from "../model/types";
import { decodeFrameBytes, type FrameDecodeRequest } from "./frameDecode";

export async function decodeFramesOffThread(request: FrameDecodeRequest, signal?: AbortSignal): Promise<Frames> {
  if (signal?.aborted) throw new DOMException("Reconstruction superseded", "AbortError");
  if (typeof Worker === "undefined") return decodeFrameBytes(request);
  let worker: Worker;
  try { worker = new Worker(new URL("./frameWorker.ts", import.meta.url), { type: "module" }); }
  catch { return decodeFrameBytes(request); }
  return new Promise((resolve, reject) => {
    const finish = () => { clearTimeout(timeout); signal?.removeEventListener("abort", abort); worker.terminate(); };
    const abort = () => { finish(); reject(new DOMException("Reconstruction superseded", "AbortError")); };
    const timeout = setTimeout(() => { finish(); reject(new DecodeError("reconstruction", "Reconstruction worker timed out")); }, 30_000);
    signal?.addEventListener("abort", abort, { once: true });
    worker.onmessage = (event: MessageEvent<{ frames?: Frames; error?: string; schema?: string; supported?: string[] }>) => {
      finish();
      if (event.data.frames) resolve(event.data.frames);
      else if (event.data.schema !== undefined && event.data.supported) reject(new UnsupportedSchemaError("frames.schema", event.data.schema, event.data.supported));
      else reject(new DecodeError("reconstruction", event.data.error ?? "Reconstruction worker failed"));
    };
    worker.onerror = () => { finish(); reject(new DecodeError("reconstruction", "Reconstruction worker unavailable")); };
    try { worker.postMessage(request, [request.bytes]); }
    catch (error) { finish(); reject(new DecodeError("reconstruction", error instanceof Error ? error.message : "Reconstruction transfer failed")); }
  });
}
