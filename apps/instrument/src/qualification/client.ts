import { MAX_BUNDLE_BYTES } from "./bundle";
import type { ReviewBundle } from "./checkBundle";
import { JsonNumber } from "./json";

export function openReview(file: File, signal: AbortSignal, progress: (message: string) => void): Promise<ReviewBundle> {
  if (file.size > MAX_BUNDLE_BYTES) return Promise.reject(new Error("Choose a review file smaller than 68 MiB."));
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./review.worker.ts", import.meta.url), { type: "module" });
    let finished = false;
    const finish = (error?: Error, result?: ReviewBundle) => {
      if (finished) return;
      finished = true; worker.terminate(); clearTimeout(timeout); signal.removeEventListener("abort", abort);
      if (error) reject(error); else resolve(result!);
    };
    const abort = () => finish(new DOMException("Review cancelled", "AbortError"));
    const timeout = window.setTimeout(() => finish(new Error("Review verification timed out. The previous selection is unchanged.")), 60_000);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) { abort(); return; }
    worker.onerror = () => finish(new Error("The review worker could not finish. Try opening the file again."));
    worker.onmessage = event => {
      const message = event.data;
      if (message.kind === "progress") progress(`Checking records · ${message.done} / ${message.total}`);
      if (message.kind === "error") finish(new Error(message.message));
      if (message.kind === "ready") {
        try { for (const number of message.numbers) Object.setPrototypeOf(number, JsonNumber.prototype); finish(undefined, message.bundle); }
        catch (error) { finish(error instanceof Error ? error : new Error("Unsupported review records.")); }
      }
    };
    progress("Reading local review");
    file.arrayBuffer().then(buffer => { if (!finished) worker.postMessage({ buffer, name: file.name }, [buffer]); }).catch(error => finish(error));
  });
}
