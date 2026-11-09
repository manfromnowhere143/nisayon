// @vitest-environment node
import { generateKeyPairSync, verify } from "node:crypto";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import { afterAll, beforeAll, expect, it } from "vitest";
import { serveLocalFilm } from "../dev/film";
let directory: string, path: string;
const keys = generateKeyPairSync("rsa", { modulusLength: 2048 });
const playback = "localtestplayback01234567890123456789";
beforeAll(async () => {
  directory = await mkdtemp(join(tmpdir(), "nisayon-film-test-")); path = join(directory, "film.json");
  await writeFile(path, JSON.stringify({ playbackId: playback, keyId: "localtestkey01234567890123456789", privateKey: Buffer.from(keys.privateKey.export({ type: "pkcs8", format: "pem" })).toString("base64"), scope: "loopback-preview-only" }));
});
afterAll(async () => { await rm(directory, { recursive: true, force: true }); });
function request(extra: { host?: string; origin?: string; address?: string; method?: string } = {}, configPath = path) {
  const headers: Record<string, string> = { host: extra.host ?? "127.0.0.1:5201" };
  if (extra.origin) headers.origin = extra.origin;
  const responseHeaders: Record<string, string> = {};
  return new Promise<{ status: number; headers: Record<string, string>; body: string }>(resolve => {
    const response = { statusCode: 200, setHeader(key: string, value: string) { responseHeaders[key] = value; }, end(body: string) { resolve({ status: this.statusCode, headers: responseHeaders, body }); } };
    serveLocalFilm(configPath)({ url: "/__nisayon/film", method: extra.method ?? "GET", headers, socket: { remoteAddress: extra.address ?? "127.0.0.1" } } as IncomingMessage, response as unknown as ServerResponse, () => { throw new Error("Unexpected fallthrough"); });
  });
}
it("issues a ten-minute signed URL for exactly the configured film without returning the key", async () => {
  const result = await request(); expect(result.status).toBe(200); expect(result.headers["Cache-Control"]).toBe("no-store");
  const value = JSON.parse(result.body); const token = new URL(value.hls).searchParams.get("token")!;
  const parts = token.split("."); const claims = JSON.parse(Buffer.from(parts[1]!, "base64url").toString());
  expect(claims.sub).toBe(playback); expect(claims.aud).toBe("v"); expect(claims.exp - Math.floor(Date.now() / 1000)).toBeGreaterThan(595);
  expect(verify("RSA-SHA256", Buffer.from(`${parts[0]}.${parts[1]}`), keys.publicKey, Buffer.from(parts[2]!, "base64url"))).toBe(true);
  expect(result.body).not.toContain("privateKey"); expect(result.body).not.toContain("BEGIN PRIVATE");
});
it.each([{ host: "evil.example" }, { origin: "https://evil.example" }, { address: "10.0.0.9" }, { method: "POST" }])("refuses an unexpected caller: %j", async caller => { expect((await request(caller)).status).toBe(403); });
it("keeps a missing private configuration out of error responses", async () => { const r = await request({}, join(directory, "absent")); expect(r.status).toBe(503); expect(r.body).not.toContain(directory); });
