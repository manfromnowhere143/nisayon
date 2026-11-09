import { absoluteUrl, defaultOptions, fetchVerified, type LoaderOptions, type LoadProgress } from "../data/loader";
import type { Generation, ModelRecord } from "../model/types";
import { VISUAL_ASSET } from "./visualAssetPin";
import { checkVisualBinding, decodeVisualAsset, type VisualAsset } from "./visualCodec";
export { checkVisualBinding, decodeVisualAsset, type VisualAsset } from "./visualCodec";

let cached: Promise<VisualAsset> | null = null;
let latestProgress: LoadProgress | null = null;
const listeners = new Set<(progress: LoadProgress) => void>();
function report(progress: LoadProgress): void {
  latestProgress = progress;
  for (const listener of listeners) listener(progress);
}
function loadInWorker(): Promise<VisualAsset> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./visualWorker.ts", import.meta.url), { type: "module" });
    // The network reports real progress. Watch for a stalled worker separately
    // from the bounded download, then give decoding its own quiet interval.
    let idle: ReturnType<typeof setTimeout>;
    const finish = () => { clearTimeout(idle); clearTimeout(deadline); worker.terminate(); };
    const timeout = () => { finish(); reject(new Error("Detailed geometry did not finish loading. Please retry.")); };
    const watchdog = () => { clearTimeout(idle); idle = setTimeout(timeout, 35_000); };
    const deadline = setTimeout(timeout, 270_000);
    watchdog();
    worker.onmessage = (event: MessageEvent<{ asset?: VisualAsset; error?: string; progress?: LoadProgress }>) => {
      if (event.data.progress) { watchdog(); report(event.data.progress); return; }
      finish();
      if (event.data.asset) resolve(event.data.asset);
      else reject(new Error(event.data.error ?? "Detailed geometry could not be verified"));
    };
    worker.onerror = () => { finish(); reject(new Error("Detailed geometry worker is unavailable")); };
    worker.onmessageerror = () => { finish(); reject(new Error("Detailed geometry could not be transferred. Please retry.")); };
    try { worker.postMessage({ url: absoluteUrl(VISUAL_ASSET.path) }); }
    catch (error) { finish(); reject(error); }
  });
}
export async function loadVisualAsset(model: ModelRecord, modelSha: string, generation: Generation, options: LoaderOptions = defaultOptions()): Promise<VisualAsset> {
  if (!cached) latestProgress = null;
  if (options.onProgress) { listeners.add(options.onProgress); if (latestProgress) options.onProgress(latestProgress); }
  if (!cached) {
    const task = typeof Worker !== "undefined" ? loadInWorker() : fetchVerified(absoluteUrl(VISUAL_ASSET.path), VISUAL_ASSET, "run", undefined, { ...options, maxBytes: 16 * 1024 * 1024 })
      .then((verified) => decodeVisualAsset(verified.json, verified.sha256));
    cached = task.catch((error: unknown) => { cached = null; throw error; });
  }
  try {
    const asset = await cached;
    checkVisualBinding(asset, model, modelSha, generation);
    return asset;
  } finally { if (options.onProgress) listeners.delete(options.onProgress); }
}
