// Exercise the actual emitted worker, structured clone and browser-client
// adapter in Node. This checks transport, not browser layout or GPU behavior.
import { createServer } from "vite";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { Worker } from "node:worker_threads";
import { File } from "node:buffer";
import assert from "node:assert/strict";

const release = JSON.parse(readFileSync("dist/sw.js", "utf8").split("\n")[0].slice("const RELEASE = ".length, -1));
const entry = release.precache.find(row => row.path.startsWith("assets/review.worker-"));
assert(entry, "Review worker is present in the release cache");
const code = readFileSync(`dist/${entry.path}`);
assert.equal(createHash("sha256").update(code).digest("hex"), entry.sha256);
let active = 0;
class EmittedWorker {
  constructor() {
    active++;
    this.thread = new Worker(`const {parentPort}=require('node:worker_threads');
      globalThis.self=globalThis;
      self.postMessage=(value,options)=>parentPort.postMessage(value,options?.transfer);
      parentPort.on('message',data=>self.onmessage({data}));\n${code.toString("utf8")}`, { eval: true, execArgv: [] });
    this.thread.on("message", data => this.onmessage?.({ data }));
    this.thread.on("error", error => this.onerror?.(error));
  }
  postMessage(value, transfer) { this.thread.postMessage(value, transfer); }
  terminate() { active--; return this.thread.terminate(); }
}
globalThis.Worker = EmittedWorker;
globalThis.window = { setTimeout, clearTimeout };
const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
try {
  const { openReview } = await server.ssrLoadModule("/src/qualification/client.ts");
  const { JsonNumber, parseRecord } = await server.ssrLoadModule("/src/qualification/json.ts");
  const numbers = value => {
    if (value instanceof JsonNumber) return [value.raw];
    if (!value || typeof value !== "object") return [];
    return Object.values(value).flatMap(numbers);
  };
  const results = [];
  for (const [name, decision, differences] of [["merged", "adopt", 0], ["restored-defect", "reject", 13]]) {
    const bytes = readFileSync(`test/fixtures/qualification/${name}.nisayon.zip`);
    const progress = [], started = performance.now();
    const bundle = await openReview(new File([bytes], `${name}.nisayon.zip`), new AbortController().signal, message => progress.push(message));
    assert.equal(bundle.assessment.software_decision, decision);
    assert.equal(bundle.assessment.deployment_decision, "unresolved");
    assert.equal(bundle.files.size, 402);
    assert.equal(bundle.comparisons.length, 22);
    assert.equal(bundle.comparisons.filter(row => row.candidate_difference !== null).length, differences);
    assert.equal(bundle.case, bundle.plan.case);
    assert.equal(bundle.comparisons[0], bundle.assessment.comparisons[0]);
    for (const [value, file] of [[bundle.plan, "evidence/plan.json"], [bundle.assessment, "assessment.json"]]) {
      const original = parseRecord(new TextDecoder().decode(bundle.files.get(file)));
      assert(numbers(original).length > 0);
      assert.deepEqual(numbers(value), numbers(original), "Every numeric lexeme survives worker transfer");
    }
    assert(progress.some(message => message.includes("401 / 401")));
    assert.equal(active, 0);
    results.push({ name, decision, comparisons: 22, differences, deployment: "unresolved", archive: bundle.sha256, numeric_transport: "exact", worker_ms: Math.round(performance.now() - started) });
  }
  await assert.rejects(openReview(new File(["damaged"], "damaged.zip"), new AbortController().signal, () => {}));
  const controller = new AbortController(); controller.abort();
  await assert.rejects(openReview(new File(["cancelled"], "cancelled.zip"), controller.signal, () => {}), { name: "AbortError" });
  assert.equal(active, 0);
  console.log(JSON.stringify({ status: "passed", runtime_worker: entry, cases: results, damaged: "rejected", cancellation: "terminated", browser_rendered: false }, null, 2));
} finally { await server.close(); }
