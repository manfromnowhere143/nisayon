// Read-only transport check against the public API used by the instrument.
// This exercises application parsing and CORS headers, not browser rendering.
import { createServer } from "vite";
import assert from "node:assert/strict";
const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
try {
  const { createProgressClient } = await server.ssrLoadModule("/src/research/progress.ts");
  const requests = [];
  const client = createProgressClient(async (url, init) => {
    assert.equal(new URL(url).origin, "https://api.github.com");
    assert.equal(init.method, "GET"); assert.equal(init.credentials, "omit");
    const response = await fetch(url, init);
    requests.push({ status: response.status, cors: response.headers.get("access-control-allow-origin"), remaining: response.headers.get("x-ratelimit-remaining"), etag: response.headers.get("etag") });
    return response;
  });
  const value = await client.refresh();
  assert.equal(value.connection, "current", "The actual public API was decoded successfully");
  assert.equal(requests.length, 1); assert.equal(requests[0].cors, "*");
  assert(value.records.length >= 12);
  console.log(JSON.stringify({ status: "passed", checkedAt: value.checkedAt, partial: value.partial, records: value.records.map(({url, status, observedAt}) => ({url, status, observedAt})), requests, browser_rendered: false }, null, 2));
} finally { await server.close(); }
