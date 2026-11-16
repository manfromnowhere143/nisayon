import { parseProjection, ProjectionError } from "./projection";
self.onmessage = async (event: MessageEvent<{ buffer: ArrayBuffer; expected?: string }>) => {
  try {
    const bytes = new Uint8Array(event.data.buffer);
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(b => b.toString(16).padStart(2, "0")).join("");
    if (event.data.expected && digest !== event.data.expected) throw new ProjectionError("invalid", "The example bytes differ from their retained file identity.");
    self.postMessage({ kind: "ready", value: parseProjection(bytes), sha256: digest });
  } catch (error) {
    self.postMessage({ kind: "error", errorKind: error instanceof ProjectionError ? error.kind : "invalid", message: error instanceof Error ? error.message : "This projection could not be read." });
  }
};
