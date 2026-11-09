import { inspectReview, isCheckBundle } from "./checkBundle";
import { JsonNumber } from "./json";

self.onmessage = async (event: MessageEvent<{ buffer: ArrayBuffer; name: string }>) => {
  try {
    const result = await inspectReview(event.data.buffer, event.data.name, (done, total) => {
      if (done === total || done % 32 === 0) self.postMessage({ kind: "progress", done, total });
    });
    // All slices refer to the same original archive. Transfer it once, never
    // stringify the numeric records or copy every member into another buffer.
    // Structured clone preserves references, but not custom prototypes. Send
    // references to the parser's numeric nodes separately, so the UI restores
    // their type without parsing the archive again on the interaction thread.
    const numbers: JsonNumber[] = [], visited = new Set<object>();
    const walk = (value: unknown) => {
      if (!value || typeof value !== "object" || visited.has(value)) return;
      visited.add(value);
      if (value instanceof JsonNumber) numbers.push(value);
      else for (const child of Object.values(value)) walk(child);
    };
    if (isCheckBundle(result)) { walk(result.model); walk(result.execution); walk(result.applicability); walk(result.checks); }
    else walk(result.plan);
    walk(result.assessment);
    self.postMessage({ kind: "ready", bundle: result, numbers }, { transfer: [event.data.buffer] });
  } catch (error) {
    self.postMessage({ kind: "error", message: error instanceof Error ? error.message : "This review could not be opened." });
  }
};
