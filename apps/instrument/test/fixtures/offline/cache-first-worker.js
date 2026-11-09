/* RELEASE is inserted by the build from the exact emitted bytes. The worker
   has no execution connection and never supplies a substitute evidence root. */
const base = new URL(self.registration.scope);
const prefix = `nisayon:${base.pathname}:research:`;
const cacheName = prefix + RELEASE.version;
// The production host redirects /index.html to /. Fetch the canonical document
// directly so installing never follows a redirect to an unexpected shell.
const entries = RELEASE.precache.map((entry) => ({
  ...entry,
  url: new URL(entry.path === "index.html" ? "./" : entry.path, base).href,
}));
const allowed = new Set(entries.map((entry) => entry.url));
const shell = base.href;

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(cacheName);
      // Sequential downloads avoid competing with a first robot reconstruction.
      // A partial or wrong-byte package never becomes an installed worker.
      for (const entry of entries) {
        const response = await fetch(entry.url, {
          cache: "reload",
          credentials: "same-origin",
          redirect: "error",
        });
        if (!response.ok || response.type === "opaque")
          throw new Error("Offline resource unavailable");
        const digest = await crypto.subtle.digest(
          "SHA-256",
          await response.clone().arrayBuffer(),
        );
        const hex = Array.from(new Uint8Array(digest), (byte) =>
          byte.toString(16).padStart(2, "0"),
        ).join("");
        if (hex !== entry.sha256)
          throw new Error("Offline resource identity mismatch");
        await cache.put(entry.url, response);
      }
    })(),
  );
  // No skipWaiting: an update must not replace the code of an open experiment.
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key.startsWith(prefix) && key !== cacheName)
          await caches.delete(key);
      }
    })(),
  );
  // No clients.claim: the document that installed us keeps its own version.
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== base.origin) return;
  const navigation =
    request.mode === "navigate" &&
    (url.pathname === base.pathname ||
      url.pathname === new URL("index.html", base).pathname);
  if (!navigation && !allowed.has(url.href)) return;
  event.respondWith(
    (async () => {
      const cache = await caches.open(cacheName);
      const saved = await cache.match(navigation ? shell : url.href);
      // If browser storage was evicted, fail through to the original request.
      // Never replace a missing catalog, library or recording with another one.
      return saved || fetch(request);
    })(),
  );
});
