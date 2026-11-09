// Execute the emitted frame/geometry workers against served recording bytes.
// Node worker_threads exercise decoding and transfers, not browser/GPU behavior.
import { createServer } from "vite";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Worker } from "node:worker_threads";

const origin = process.argv[2] ?? "http://127.0.0.1:5180";
const remoteRuntime = process.argv.includes("--served-runtime");
const started = performance.now();
const timings = [];
const release = JSON.parse(
  readFileSync("dist/sw.js", "utf8")
    .split("\n")[0]
    .slice("const RELEASE = ".length, -1),
);
const code = new Map();
for (const kind of ["frameWorker", "visualWorker"]) {
  const entry = release.precache.find((item) =>
    item.path.startsWith(`assets/${kind}-`),
  );
  if (!entry) throw Error(`Missing emitted ${kind}`);
  const bytes = remoteRuntime
    ? Buffer.from(
        await (
          await fetch(`${origin}/${entry.path}`, {
            signal: AbortSignal.timeout(30_000),
          })
        ).arrayBuffer(),
      )
    : readFileSync(`dist/${entry.path}`);
  if (createHash("sha256").update(bytes).digest("hex") !== entry.sha256)
    throw Error(`${kind} runtime mismatch`);
  code.set(kind, bytes.toString("utf8"));
}

class EmittedWorker {
  constructor(url) {
    const kind = url.href.includes("frameWorker")
      ? "frameWorker"
      : "visualWorker";
    const shim = `const {parentPort}=require('node:worker_threads');
      globalThis.self=globalThis;
      self.postMessage=(value,options)=>parentPort.postMessage(value,options?.transfer);
      parentPort.on('message',data=>self.onmessage({data}));`;
    this.thread = new Worker(shim + code.get(kind), {
      eval: true,
      execArgv: [],
    });
    this.thread.on("message", (data) => this.onmessage?.({ data }));
    this.thread.on("error", (error) => this.onerror?.(error));
    this.thread.on("messageerror", (error) => this.onmessageerror?.(error));
  }
  postMessage(value, transfer) {
    this.thread.postMessage(value, transfer);
  }
  terminate() {
    return this.thread.terminate();
  }
}

globalThis.Worker = EmittedWorker;
globalThis.location = { href: `${origin}/` };
const server = await createServer({
  server: { middlewareMode: true },
  appType: "custom",
});
try {
  const { defaultOptions, openGeneration, openCase, openRun, ResourceCache } =
    await server.ssrLoadModule("/src/data/loader.ts");
  const { loadVisualAsset } = await server.ssrLoadModule(
    "/src/scene/visualAssets.ts",
  );
  const options = {
    ...defaultOptions(),
    fetch: async (url, init) => {
      const start = performance.now();
      const response = await fetch(url, init);
      timings.push({
        path: new URL(url).pathname,
        status: response.status,
        headers_ms: Math.round(performance.now() - start),
      });
      return response;
    },
  };
  const cases = [];
  for (const id of ["D01-gripper-sign", "D06-stateless-inference"]) {
    const { generation } = await openGeneration(
      `${origin}/fixtures/ui/recorded/${id}/evidence.json`,
      undefined,
      options,
    );
    const cache = new ResourceCache();
    const record = await openCase(
      generation,
      generation.cases[0].case_key,
      undefined,
      options,
      cache,
    );
    const run = await openRun(
      generation,
      record,
      record.runs.find((r) => r.role === "regression").run,
      undefined,
      options,
      cache,
    );
    if (!run.frames || !run.model || run.framesIssue || run.modelIssue)
      throw Error(
        JSON.stringify({ frames: run.framesIssue, model: run.modelIssue }),
      );
    const asset = await loadVisualAsset(
      run.model,
      run.record.model.sha256,
      generation,
      options,
    );
    if (asset.meshes.length !== 53 || asset.parts.length !== 54)
      throw Error("Detailed Panda geometry differs");
    cases.push({
      id,
      generation: generation.sha256,
      run: run.record.run.run_id,
      rows: run.samples.rows.length,
      frames: run.frames.rows.length,
      meshes: asset.meshes.length,
      parts: asset.parts.length,
      model: run.record.model.sha256,
      geometry: asset.sha256,
      source_binding: "verified",
    });
  }
  console.log(
    JSON.stringify(
      {
        status: "passed",
        origin,
        runtime: remoteRuntime
          ? "served emitted workers"
          : "local emitted workers",
        elapsed_ms: Math.round(performance.now() - started),
        cases,
        timings,
        browser_gpu_acceptance: false,
      },
      null,
      2,
    ),
  );
} finally {
  await server.close();
}
