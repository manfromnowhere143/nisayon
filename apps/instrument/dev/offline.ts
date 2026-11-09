import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Plugin } from "vite";
import { CATALOG_SHA } from "../src/research/catalogPin";

/** A release-specific, integrity-bound research shell. Recordings, mutable
 * indexes, API responses and external source links never enter this cache. */
export function offlinePlugin(root: string): Plugin {
  return {
    name: "nisayon-offline-research",
    apply: "build",
    enforce: "post",
    generateBundle: {
      order: "post",
      handler(_options, bundle) {
        const files = new Map<string, string | Uint8Array>();
        for (const item of Object.values(bundle)) {
          // Save the complete release, including deferred lab modules and
          // workers. Caching does not execute them: the scene remains lazy.
          // A cached shell must never outlive the code it imports later.
          if (item.type === "chunk") files.set(item.fileName, item.code);
          if (
            item.type === "asset" &&
            (item.fileName === "index.html" ||
              /\.(?:css|js)$/.test(item.fileName))
          )
            files.set(item.fileName, item.source);
        }
        if (!files.has("index.html"))
          throw new Error("Offline shell has no entry document");
        for (const file of [
          "site.webmanifest",
          "favicon.svg",
          "favicon.ico",
          "favicon-96.png",
          "favicon-192.png",
          "favicon-512.png",
          "icon-maskable-512.png",
          "apple-touch-icon.png",
          "media/cinematic/hall-960.webp",
          "media/cinematic/hall-1600.webp",
          `research/${CATALOG_SHA}/catalog.json`,
        ]) {
          files.set(file, readFileSync(join(root, "public", file)));
        }
        const precache = [...files]
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([path, bytes]) => ({
            path,
            sha256: createHash("sha256").update(bytes).digest("hex"),
          }));
        if (
          precache.find(
            (item) => item.path === `research/${CATALOG_SHA}/catalog.json`,
          )?.sha256 !== CATALOG_SHA
        )
          throw new Error("Offline catalog does not match its pinned identity");
        const source = readFileSync(join(root, "src/pwa/worker.js"), "utf8");
        // A worker-policy change also needs its own cache and client leases.
        const version = createHash("sha256")
          .update(source)
          .update("\0")
          .update(JSON.stringify(precache))
          .digest("hex");
        this.emitFile({
          type: "asset",
          fileName: "sw.js",
          source: `const RELEASE = ${JSON.stringify({ version, precache })};\n${source}`,
        });
      },
    },
  };
}
