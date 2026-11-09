import { BufferAttribute, type BufferGeometry } from "three";
import { MeshBVH, type MeshBVHOptions } from "three-mesh-bvh";
import MeshWorker from "three-mesh-bvh/src/workers/generateMeshBVH.worker.js?worker";

// The vendor worker protocol is pinned by package-lock. Unlike its convenience
// wrapper, abort settles the promise as well as terminating the worker.
export function lightBvh(signal: AbortSignal) {
  const worker = new MeshWorker();
  let pending: ((reason: unknown) => void) | null = null;
  const dispose = () => { worker.terminate(); pending?.(new DOMException("Still cancelled", "AbortError")); pending = null; signal.removeEventListener("abort", dispose); };
  signal.addEventListener("abort", dispose, { once: true });
  return {
    dispose,
    generate(geometry: BufferGeometry, options: MeshBVHOptions = {}): Promise<MeshBVH> {
      if (signal.aborted) return Promise.reject(new DOMException("Still cancelled", "AbortError"));
      return new Promise((resolve, reject) => {
        if (pending) { reject(Error("A still build is already pending")); return; }
        pending = reject;
        worker.onerror = () => { pending = null; reject(Error("Geometry worker unavailable")); };
        worker.onmessage = event => {
          const data = event.data;
          if (data.error) { pending = null; reject(Error("Geometry worker failed")); }
          else if (data.serialized) {
            pending = null;
            geometry.setAttribute("position", new BufferAttribute(data.position, 3));
            if (data.serialized.index) geometry.setIndex(new BufferAttribute(data.serialized.index, 1));
            resolve(MeshBVH.deserialize(data.serialized, geometry, { setIndex: false }));
          }
        };
        const position = geometry.getAttribute("position").array, index = geometry.index?.array ?? null;
        worker.postMessage({ position, index, options: { ...options, onProgress: null, includedProgressCallback: false, groups: [...geometry.groups] } }, [position.buffer, ...(index ? [index.buffer] : [])] as ArrayBuffer[]);
      });
    },
  };
}
