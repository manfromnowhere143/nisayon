// Verification and geometry decode stay off the interaction thread. Only
// validated typed arrays cross back, transferring their buffers without a copy.
import { defaultOptions, fetchVerified } from "../data/loader";
import { VISUAL_ASSET } from "./visualAssetPin";
import { decodeVisualAsset } from "./visualCodec";

self.onmessage = async (event: MessageEvent<{ url: string }>) => {
  try {
    let reported = 0;
    const verified = await fetchVerified(event.data.url, VISUAL_ASSET, "run", undefined, {
      ...defaultOptions(), maxBytes: 16 * 1024 * 1024,
      onProgress: (progress) => {
        const now = performance.now();
        if (now - reported >= 100 || progress.loaded === 0 || progress.loaded === progress.total) {
          reported = now;
          self.postMessage({ progress });
        }
      },
    });
    const asset = decodeVisualAsset(verified.json, verified.sha256);
    const buffers = asset.meshes.flatMap((mesh) => [mesh.positions.buffer, mesh.normals.buffer, mesh.indices.buffer]);
    self.postMessage({ asset }, { transfer: buffers });
  } catch (error) {
    self.postMessage({ error: error instanceof Error ? error.message : "Detailed geometry unavailable" });
  }
};
