import { dirname, join, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";
import { serveExports } from "./dev/exports";
import { offlinePlugin } from "./dev/offline";
import { guidesPlugin } from "./dev/guides";
import { localFilmPlugin } from "./dev/film";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..");

// Serve the data lane's committed exports (fixtures/ui/**) from the repository
// root under the same origin, in dev and preview. Files only; no listing.
function exportsPlugin(): Plugin {
  const serve = serveExports(join(repoRoot, "fixtures", "ui"));
  return {
    name: "nisayon-exports",
    configureServer(server) {
      server.middlewares.use(serve);
    },
    configurePreviewServer(server) {
      server.middlewares.use(serve);
    },
  };
}

// Explicit retained SDK packages for this loopback development preview only.
// Test records (including original local paths) never enter the public build.
function localReviewPlugin(): Plugin {
  return { name: "nisayon-local-reviews", configureServer(server) {
    server.middlewares.use((request, response, next) => {
      const match = /^\/local-reviews\/(merged|restored-defect)\.nisayon\.zip$/.exec(request.url ?? "");
      if (!match || request.method !== "GET") { next(); return; }
      void readFile(join(here, "test/fixtures/qualification", `${match[1]}.nisayon.zip`)).then(bytes => {
        response.setHeader("Content-Type", "application/zip"); response.setHeader("Cache-Control", "no-store");
        response.end(bytes);
      }).catch(() => { response.statusCode = 404; response.end(); });
    });
  } };
}

// The instrument is a static application. It reads a verified generation over
// plain HTTP. The loopback-only film issuer is not part of that static build;
// portable reviews have no server execution or upload path.
export default defineConfig({
  plugins: [react(), exportsPlugin(), guidesPlugin(), localReviewPlugin(), localFilmPlugin(), offlinePlugin(here)],
  base: "./",
  server: { port: 5173, host: "127.0.0.1" },
  preview: { port: 4173, host: "127.0.0.1" },
  build: {
    // Open previews can still request a previous release's lazy lab. Keep
    // content-named assets available across local rebuilds; deployment also
    // retains the previous published runtime's immutable assets.
    emptyOutDir: false,
    target: "es2022",
    sourcemap: false,
    // three.js is the bulk of the bundle; keep it apart from the shell so the
    // verified readings can appear before the scene code arrives.
    rollupOptions: { output: { manualChunks: { three: ["three"] } } },
  },
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.ts", "test/**/*.test.tsx"],
    setupFiles: ["test/setup.ts"],
  },
});
