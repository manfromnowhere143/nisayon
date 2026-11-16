import { PROJECTION_BYTES, ProjectionError, type CheckSummary, type DependencyExplanation, type MeasurementReview, type Projection } from "./projection";
export interface Imported<T extends Projection = Projection> { value: T; sha256: string; name: string }
export interface ProjectionSelection { summary: Imported<CheckSummary>; measurement: Imported<MeasurementReview> | null; explanation: Imported<DependencyExplanation> | null; example: string | null }

export async function readExampleBytes(response: Response): Promise<Uint8Array<ArrayBuffer>> {
  const stream = response.body?.getReader();
  if (!stream) throw new Error("The example response has no readable body.");
  const chunks: Uint8Array[] = []; let size = 0;
  try {
    for (;;) {
      const next = await stream.read(); if (next.done) break;
      size += next.value.byteLength;
      if (size > PROJECTION_BYTES) throw new ProjectionError("capacity", "This example exceeds the 2 MiB browser limit.");
      chunks.push(next.value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return bytes;
  } finally { await stream.cancel().catch(() => {}); stream.releaseLock(); }
}

export function openProjection(file: File, signal: AbortSignal, expected?: string): Promise<Imported> {
  if (file.size > PROJECTION_BYTES) return Promise.reject(new ProjectionError("capacity", "This file exceeds the 2 MiB browser limit. Inspect it with the compatible CLI."));
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Import cancelled", "AbortError")); return; }
    const worker = new Worker(new URL("./projection.worker.ts", import.meta.url), { type: "module" });
    let finished = false;
    const done = (error?: Error, value?: Imported) => {
      if (finished) return; finished = true; worker.terminate(); clearTimeout(timeout); signal.removeEventListener("abort", abort);
      if (error) reject(error); else resolve(value!);
    };
    const abort = () => done(new DOMException("Import cancelled", "AbortError"));
    const timeout = setTimeout(() => done(new ProjectionError("capacity", "This import exceeded the eight-second browser budget. Inspect it with the compatible CLI.")), 8000);
    signal.addEventListener("abort", abort, { once: true });
    worker.onerror = () => done(new Error("The local record reader stopped. Retry the import."));
    worker.onmessage = event => {
      const message = event.data;
      if (message.kind === "error") done(new ProjectionError(message.errorKind, message.message));
      if (message.kind === "ready") done(undefined, { value: message.value, sha256: message.sha256, name: file.name });
    };
    void file.arrayBuffer().then(buffer => { if (!finished) worker.postMessage({ buffer, ...(expected ? { expected } : {}) }, [buffer]); }).catch(error => done(error instanceof Error ? error : new Error("Could not read the local file.")));
  });
}
