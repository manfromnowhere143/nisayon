// @vitest-environment node
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, expect, it } from "vitest";
import { serveExports } from "../dev/exports";

let directory: string;
let server: Server;
let origin: string;
const digest = "1".repeat(64);
beforeAll(async () => {
  directory = mkdtempSync(join(tmpdir(), "nisayon-export-route-"));
  const root = join(directory, "ui");
  mkdirSync(join(root, "objects"), { recursive: true });
  mkdirSync(join(directory, "ui-other"));
  writeFileSync(join(root, "objects", `${digest}.json`), '{"row":0}\n');
  writeFileSync(join(root, "evidence.json"), '{"version":1}');
  writeFileSync(join(root, "LICENSE.txt"), "Source terms\r\n");
  writeFileSync(join(directory, "ui-other", "private.json"), '{"private":true}');
  symlinkSync(join(directory, "ui-other", "private.json"), join(root, "link.json"));
  const serve = serveExports(root);
  server = createServer((req, res) => serve(req, res, () => { res.statusCode = 404; res.end("unhandled"); }));
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No local test listener");
  origin = `http://127.0.0.1:${address.port}`;
});
afterAll(async () => {
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  rmSync(directory, { recursive: true, force: true });
});
it("serves pinned bytes with immutable caching and HEAD support", async () => {
  const url = `${origin}/fixtures/ui/objects/${digest}.json`;
  const response = await fetch(url);
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toContain("immutable");
  expect(await response.text()).toBe('{"row":0}\n');
  const head = await fetch(url, { method: "HEAD" });
  expect(head.headers.get("content-length")).toBe("10");
  expect(await head.text()).toBe("");
});
it("keeps discovery revalidatable and terms as exact readable text", async () => {
  const discovery = await fetch(`${origin}/fixtures/ui/evidence.json`);
  expect(discovery.headers.get("cache-control")).toBe("no-cache");
  const terms = await fetch(`${origin}/fixtures/ui/LICENSE.txt`);
  expect(terms.headers.get("content-type")).toContain("text/plain");
  expect(await terms.text()).toBe("Source terms\r\n");
});
it.each(["%2e%2e%2fui-other%2fprivate.json", "link.json", "%5c..%5cprivate.json", "objects/", "missing.json"])("refuses traversal, symlink escapes and absent files: %s", async (path) => {
  const response = await fetch(`${origin}/fixtures/ui/${path}`);
  expect(response.status).toBe(404);
  expect(await response.text()).not.toContain("private");
});
it("reports malformed encoding and remains able to serve the next request", async () => {
  expect((await fetch(`${origin}/fixtures/ui/%xx`)).status).toBe(400);
  expect((await fetch(`${origin}/fixtures/ui/evidence.json`)).status).toBe(200);
});
