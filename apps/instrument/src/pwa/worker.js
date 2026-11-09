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
// Private worker bookkeeping; never a route or an evidence response. Older
// release caches remain leased to the clients present during activation.
const leaseKey = new URL("__nisayon_worker_lease__", base).href;
let retentionJob;

async function scopedClients() {
  return (await self.clients.matchAll({ includeUncontrolled: true, type: "all" })).filter(
    (client) => client.url.startsWith(base.href),
  );
}

function retainedCaches() {
  if (retentionJob) return retentionJob;
  retentionJob = (async () => {
    const cache = await caches.open(cacheName);
    const saved = await cache.match(leaseKey);
    // An evicted lease cannot justify deleting a possibly needed old release.
    if (!saved)
      return (await caches.keys()).filter(
        (key) => key.startsWith(prefix) && key !== cacheName,
      );
    const lease = await saved.json();
    const keys = lease.caches.filter(
      (key) => typeof key === "string" && key.startsWith(prefix) && key !== cacheName,
    );
    if (!keys.length) return [];
    const live = await scopedClients();
    if (live.some((client) => lease.clients.includes(client.id))) return keys;
    // Delete only the generations captured at activation, never another
    // worker's in-progress installation or a different application's cache.
    for (const key of keys) await caches.delete(key);
    await cache.put(leaseKey, new Response(JSON.stringify({ caches: [], clients: [] })));
    return [];
  })().finally(() => { retentionJob = undefined; });
  return retentionJob;
}

function immutableResource(url) {
  if (url.search || !url.href.startsWith(base.href)) return false;
  const path = url.pathname.slice(base.pathname.length);
  return /^assets\/[^/]+-[\w-]{8,}\.(?:js|css)$/.test(path) ||
    /^research\/[a-f0-9]{64}\/catalog\.json$/.test(path);
}

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
      // Activate only after the complete release has passed integrity checks.
      // This replaces fetch routing, not the loaded document or its review.
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = (await caches.keys()).filter(
        (key) => key.startsWith(prefix) && key !== cacheName,
      );
      const clients = await scopedClients();
      const cache = await caches.open(cacheName);
      await cache.put(leaseKey, new Response(JSON.stringify({
        caches: keys, clients: clients.map((client) => client.id),
      })));
      await retainedCaches();
    })().catch(() => {
      // Cache retirement is optional. If bookkeeping storage fails, retain
      // old assets and keep the verified replacement available for navigation.
    }),
  );
  // skipWaiting updates existing controlled clients. No clients.claim or
  // client.navigate: an uncontrolled document and every loaded review stay put.
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
  const current = allowed.has(url.href);
  const immutable = immutableResource(url);
  if (!navigation && !current && !immutable) return;
  if (navigation) event.waitUntil(retainedCaches().catch(() => {}));
  event.respondWith(
    (async () => {
      const cache = await caches.open(cacheName);
      const saved = (navigation || current)
        ? await cache.match(navigation ? shell : url.href)
        : undefined;
      if (navigation) {
        // A normal opening or reload must reach the current online interface,
        // even while another tab keeps an older offline worker active. Emitted
        // code has immutable URLs, so open pages keep their own code and state.
        const controller = new AbortController();
        const deadline = setTimeout(() => controller.abort(), 5000);
        try {
          return await fetch(request, {
            cache: "no-cache",
            signal: controller.signal,
          });
        } catch (error) {
          // Only connectivity failures use the verified offline release.
          // Explicit HTTP errors remain visible instead of disguising an
          // unsuccessful server response as an older successful page.
          if (saved) return saved;
          throw error;
        } finally {
          clearTimeout(deadline);
        }
      }
      if (!saved && immutable) {
        // A tab loaded before activation may import its lazy scene afterwards.
        // Only its exact immutable URL is eligible, never a newer substitute.
        for (const key of await retainedCaches()) {
          const prior = await (await caches.open(key)).match(url.href);
          if (prior) return prior;
        }
      }
      // If browser storage was evicted, fail through to the original request.
      // Never replace a missing catalog, library or recording with another one.
      return saved || fetch(request);
    })(),
  );
});
