import { createPrivateKey, sign } from "node:crypto";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

const localConfig = join(homedir(), ".local/share/nisayon/cinematic-media/v3-2026-11-09/film.json");
const loopback = new Set(["127.0.0.1", "::1", "::ffff:127.0.0.1"]);
const identifier = /^[a-zA-Z0-9]{20,128}$/;

/** The private film has no public playback ID. This issuer runs only in the
 * loopback dev/preview server. Nothing here enters the static application,
 * accepts a file, runs an experiment or reads a portable review. */
export function serveLocalFilm(configPath = localConfig) {
  return (request: IncomingMessage, response: ServerResponse, next: () => void) => {
    if (request.url?.split("?")[0] !== "/__nisayon/film") { next(); return; }
    const host = request.headers.host ?? "";
    const origin = request.headers.origin;
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Content-Type", "application/json");
    response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
    if (request.method !== "GET" || !loopback.has(request.socket.remoteAddress ?? "") ||
      !/^(127\.0\.0\.1|localhost|\[::1\])(?::\d+)?$/.test(host) ||
      (origin !== undefined && origin !== `http://${host}`) || request.headers["sec-fetch-site"] === "cross-site") {
      response.statusCode = 403; response.end('{"error":"Unavailable"}'); return;
    }
    void readFile(configPath, "utf8").then(text => {
      const config: unknown = JSON.parse(text);
      if (!config || typeof config !== "object") throw new Error("No configuration");
      const value = config as Record<string, unknown>;
      if (typeof value.playbackId !== "string" || !identifier.test(value.playbackId) ||
          typeof value.keyId !== "string" || !identifier.test(value.keyId) ||
          typeof value.privateKey !== "string" || value.scope !== "loopback-preview-only") throw new Error("Invalid configuration");
      const expiresAt = Math.floor(Date.now() / 1000) + 600;
      const encode = (data: object) => Buffer.from(JSON.stringify(data)).toString("base64url");
      const body = `${encode({ alg: "RS256", typ: "JWT", kid: value.keyId })}.${encode({ sub: value.playbackId, aud: "v", exp: expiresAt })}`;
      const key = createPrivateKey(Buffer.from(value.privateKey, "base64"));
      const token = `${body}.${sign("RSA-SHA256", Buffer.from(body), key).toString("base64url")}`;
      const stream = `https://stream.mux.com/${value.playbackId}`;
      response.end(JSON.stringify({ hls: `${stream}.m3u8?token=${token}`, mp4: `${stream}/highest.mp4?token=${token}`, expiresAt }));
    }).catch(() => { response.statusCode = 503; response.end('{"error":"Film temporarily unavailable"}'); });
  };
}

export function localFilmPlugin(): Plugin {
  return { name: "nisayon-local-film", configureServer(server) { server.middlewares.use(serveLocalFilm()); },
    configurePreviewServer(server) { server.middlewares.use(serveLocalFilm()); } };
}
