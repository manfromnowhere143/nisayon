// Execute the real worker in an isolated worker-like context. These checks
// qualify caching/lifecycle decisions, not installation in a device browser.
import { createHash, webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import { expect, it, vi } from "vitest";
import { PUBLIC_DIR } from "./fixture";

const worker = readFileSync(join(PUBLIC_DIR, "../src/pwa/worker.js"), "utf8");
const legacyWorker = readFileSync(join(PUBLIC_DIR, "../test/fixtures/offline/cache-first-worker.js"), "utf8");
const scope = "https://example.test/instrument/";
type Stored = Map<string, Map<string, Response>>;
function environment(version = "v1", saved: Stored = new Map(), corrupt = "", source = worker) {
  const records = {
    "index.html": `<html>${version}</html>`,
    [`assets/shell-${version.padEnd(8, "0")}.js`]: `shell-${version}`,
    [`assets/lab-${version.padEnd(8, "0")}.js`]: `deferred-lab-${version}`,
    [`research/${(version === "v1" ? "a" : "b").repeat(64)}/catalog.json`]: '{"exact":"catalog"}',
  };
  const precache = Object.entries(records).map(([path, bytes]) => ({
    path,
    sha256: createHash("sha256").update(bytes).digest("hex"),
  }));
  const network = new Map(
    Object.entries(records).map(([path, bytes]) => [
      new URL(path === "index.html" ? "./" : path, scope).href,
      bytes,
    ]),
  );
  const clients = [{ id: "existing-tab", url: scope }];
  const matchAll = vi.fn(async () => clients);
  const storage = { refuseLease: false };
  const pending: Promise<unknown>[] = [];
  const handlers = new Map<string, (event: unknown) => void>();
  const skipWaiting = vi.fn(),
    claim = vi.fn();
  const fetch = vi.fn(async (request: string | { url: string }, _options?: { cache?: string; signal?: AbortSignal }) => {
    const url = typeof request === "string" ? request : request.url;
    if (!network.has(url)) throw new Error("Network unavailable");
    return new Response(
      url.endsWith(corrupt) && corrupt ? "wrong bytes" : network.get(url),
    );
  });
  runInNewContext(
    `const RELEASE = ${JSON.stringify({ version, precache })};\n${source}`,
    {
      URL,
      Response,
      AbortController,
      setTimeout,
      clearTimeout,
      crypto: {
        subtle: {
          digest: (algorithm: string, bytes: ArrayBuffer) =>
            webcrypto.subtle.digest(
              algorithm,
              Buffer.from(new Uint8Array(bytes)),
            ),
        },
      },
      fetch,
      self: {
        registration: { scope },
        skipWaiting,
        clients: { claim, matchAll },
        addEventListener: (name: string, handler: (event: unknown) => void) =>
          handlers.set(name, handler),
      },
      caches: {
        keys: async () => [...saved.keys()],
        delete: async (name: string) => saved.delete(name),
        open: async (name: string) => {
          if (!saved.has(name)) saved.set(name, new Map());
          const cache = saved.get(name)!;
          return {
            put: async (key: string, response: Response) => {
              if (storage.refuseLease && key.endsWith("__nisayon_worker_lease__"))
                throw new Error("Storage quota");
              cache.set(key, response.clone());
            },
            match: async (key: string) => cache.get(key)?.clone(),
          };
        },
      },
    },
  );
  const event = async (type: string) => {
    let completion: Promise<unknown> | undefined;
    handlers.get(type)!({
      waitUntil: (promise: Promise<unknown>) => {
        completion = promise;
      },
    });
    await completion;
  };
  const request = (
    path: string,
    mode = "cors",
    method = "GET",
  ): Promise<Response> | null => {
    let response: Promise<Response> | null = null;
    handlers.get("fetch")!({
      waitUntil: (promise: Promise<unknown>) => pending.push(promise),
      request: { url: new URL(path, scope).href, mode, method },
      respondWith: (promise: Promise<Response>) => {
        response = promise;
      },
    });
    return response;
  };
  return { event, request, network, saved, fetch, skipWaiting, claim, clients, matchAll, storage, settle: () => Promise.all(pending.splice(0)) };
}

it("opens the canonical saved shell with its exact selection offline, at a nested scope", async () => {
  const env = environment();
  await env.event("install");
  env.network.clear();
  expect(
    await (await env.request(
      "./?evidence=original.json#view=research",
      "navigate",
    ))!.text(),
  ).toBe("<html>v1</html>");
  expect(await (await env.request("assets/shell-v1000000.js"))!.text()).toBe("shell-v1");
  expect(
    await (await env.request(
      `research/${"a".repeat(64)}/catalog.json`,
    ))!.text(),
  ).toBe('{"exact":"catalog"}');
  expect(env.fetch.mock.calls.map(([url]) => url)).not.toContain(
    scope + "index.html",
  );
});

it("refuses a corrupted offline package instead of installing a substituted catalog", async () => {
  const env = environment("v1", new Map(), "catalog.json");
  await expect(env.event("install")).rejects.toThrow("identity mismatch");
  expect(env.skipWaiting).not.toHaveBeenCalled();
  expect(env.claim).not.toHaveBeenCalled();
});

it("uses network-first navigation without overwriting the complete saved offline release", async () => {
  const env = environment("v1");
  await env.event("install");
  const url = scope + "?evidence=original.json";
  env.network.set(url, "<html>v2</html>");
  expect(await (await env.request("./?evidence=original.json", "navigate"))!.text()).toBe("<html>v2</html>");
  expect(env.fetch).toHaveBeenLastCalledWith(
    expect.objectContaining({ url }),
    expect.objectContaining({ cache: "no-cache", signal: expect.any(AbortSignal) }),
  );
  // The old verified shell is never overwritten with a newer shell whose
  // complete offline dependency graph belongs to another installation.
  expect(await [...env.saved.values()][0]!.get(scope)!.clone().text()).toBe("<html>v1</html>");
  expect(env.skipWaiting).toHaveBeenCalledOnce();
  expect(env.claim).not.toHaveBeenCalled();
});

it("preserves an explicit server error instead of silently presenting an older interface", async () => {
  const env = environment("v1");
  await env.event("install");
  env.fetch.mockResolvedValueOnce(new Response("Unavailable", { status: 503 }));
  const response = await env.request("./", "navigate");
  expect(response!.status).toBe(503);
  expect(await response!.text()).toBe("Unavailable");
});

it("bounds a stalled navigation and falls back to the complete verified offline release", async () => {
  vi.useFakeTimers();
  try {
    const env = environment("v1");
    await env.event("install");
    env.fetch.mockImplementationOnce((_request, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
    }));
    const response = env.request("./?evidence=original.json", "navigate")!;
    await vi.advanceTimersByTimeAsync(5000);
    expect(await (await response).text()).toBe("<html>v1</html>");
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    vi.useRealTimers();
  }
});

it("reports a navigation failure when neither a connection nor a verified saved shell is available", async () => {
  const env = environment();
  env.network.clear();
  await expect(env.request("./", "navigate")).rejects.toThrow("Network unavailable");
});

it("retains a deferred lab from the same release after the host removes the old module", async () => {
  const old = environment("v1");
  await old.event("install");
  const next = environment("v2", old.saved);
  await next.event("install");
  old.network.clear();
  expect(await (await old.request("assets/lab-v1000000.js"))!.text()).toBe(
    "deferred-lab-v1",
  );
  expect(await (await next.request("assets/lab-v2000000.js"))!.text()).toBe(
    "deferred-lab-v2",
  );
  old.network.set(scope + "assets/lab-v2000000.js", "deferred-lab-v2");
  expect(await (await old.request("assets/lab-v2000000.js"))!.text()).toBe("deferred-lab-v2");
});

it("never intercepts mutable discovery, recordings, unknown snapshots, external links or writes", async () => {
  const env = environment();
  await env.event("install");
  for (const path of [
    "api/engine.json",
    "api/publication.json",
    "fixtures/ui/study/evidence.json",
    "fixtures/ui/recorded/library.json",
    "fixtures/ui/visual/robot.json",
    "https://external.test/assets/shell-v1000000.js",
    "../",
    "about/",
  ])
    expect(env.request(path)).toBeNull();
  expect(env.request("assets/shell-v1000000.js", "cors", "POST")).toBeNull();
  expect(env.request("assets/shell-v1000000.js?different=true")).toBeNull();
});

it("activates a replacement of the actual cache-first worker while its tab remains open", async () => {
  const old = environment("v1", new Map(), "", legacyWorker);
  await old.event("install");
  await old.event("activate");
  old.network.set(scope, "<html>v2</html>");
  // Retained failure: the actual shipped legacy worker still serves v1 online.
  expect(await (await old.request("./", "navigate"))!.text()).toBe("<html>v1</html>");
  const next = environment("v2", old.saved);
  await next.event("install");
  // Model the lifecycle gate explicitly: with the original tab still open,
  // only a completed installation requesting skipWaiting can replace it.
  expect(next.clients).toHaveLength(1);
  expect(next.skipWaiting).toHaveBeenCalledOnce();
  await next.event("activate");
  expect(next.claim).not.toHaveBeenCalled();
  expect(await (await next.request("./", "navigate"))!.text()).toBe("<html>v2</html>");
  await next.settle();
  next.network.clear();
  expect(await (await next.request("assets/lab-v1000000.js"))!.text()).toBe("deferred-lab-v1");
  expect(await (await next.request(`research/${"a".repeat(64)}/catalog.json`))!.text()).toBe('{"exact":"catalog"}');
  expect(await (await next.request("./", "navigate"))!.text()).toBe("<html>v2</html>");
});

it("preserves the old release when a replacement fails integrity verification", async () => {
  const old = environment("v1", new Map(), "", legacyWorker);
  await old.event("install");
  const next = environment("v2", old.saved, "catalog.json");
  await expect(next.event("install")).rejects.toThrow("identity mismatch");
  expect(next.skipWaiting).not.toHaveBeenCalled();
  old.network.clear();
  expect(await (await old.request("./", "navigate"))!.text()).toBe("<html>v1</html>");
  expect(await (await old.request("assets/lab-v1000000.js"))!.text()).toBe("deferred-lab-v1");
});

it("keeps legacy assets across worker restarts and retires them only after the original clients leave", async () => {
  const old = environment("v1", new Map(), "", legacyWorker);
  await old.event("install");
  old.saved.set("another-app", new Map());
  old.saved.set("nisayon:/other/:research:v1", new Map());
  const next = environment("v2", old.saved);
  await next.event("install");
  await next.event("activate");
  const resumed = environment("v2", next.saved);
  resumed.network.clear();
  expect(await (await resumed.request("assets/lab-v1000000.js"))!.text()).toBe("deferred-lab-v1");
  // A newer installation must not be deleted by this worker's retirement pass.
  resumed.saved.set("nisayon:/instrument/:research:v3", new Map());
  resumed.clients.splice(0, 1, { id: "new-tab", url: scope });
  await resumed.request("./", "navigate");
  await resumed.settle();
  expect([...resumed.saved.keys()].sort()).toEqual([
    "another-app", "nisayon:/instrument/:research:v2",
    "nisayon:/instrument/:research:v3", "nisayon:/other/:research:v1",
  ]);
  await expect(resumed.request("assets/lab-v1000000.js")).rejects.toThrow("Network unavailable");
});

it("retires old caches on activation when no in-scope clients remain", async () => {
  const old = environment("v1");
  await old.event("install");
  const next = environment("v2", old.saved);
  next.clients.splice(0, 1, { id: "other-app", url: "https://example.test/other/" });
  await next.event("install");
  await next.event("activate");
  expect([...next.saved.keys()]).toEqual(["nisayon:/instrument/:research:v2"]);
});

it("preserves old assets when optional retirement bookkeeping cannot be stored", async () => {
  const old = environment("v1", new Map(), "", legacyWorker);
  await old.event("install");
  const next = environment("v2", old.saved);
  await next.event("install");
  next.storage.refuseLease = true;
  await next.event("activate");
  expect(await (await next.request("./", "navigate"))!.text()).toBe("<html>v2</html>");
  next.network.clear();
  expect(await (await next.request("assets/lab-v1000000.js"))!.text()).toBe("deferred-lab-v1");
  expect(next.saved.has("nisayon:/instrument/:research:v1")).toBe(true);
});

it("retains every older generation through consecutive updates until the last original client leaves", async () => {
  const old = environment("v1", new Map(), "", legacyWorker);
  await old.event("install");
  const second = environment("v2", old.saved);
  await second.event("install");
  await second.event("activate");
  const third = environment("v3", second.saved);
  third.clients.push({ id: "second-tab", url: scope });
  await third.event("install");
  await third.event("activate");
  third.clients.splice(1, 1);
  third.network.clear();
  expect(await (await third.request("assets/lab-v1000000.js"))!.text()).toBe("deferred-lab-v1");
  expect(await (await third.request("assets/lab-v2000000.js"))!.text()).toBe("deferred-lab-v2");
  third.clients.splice(0, 1);
  await third.request("./", "navigate");
  await third.settle();
  expect([...third.saved.keys()]).toEqual(["nisayon:/instrument/:research:v3"]);
});

it("does not substitute cached evidence or another scope's similarly named asset", async () => {
  const env = environment();
  await env.event("install");
  await env.event("activate");
  env.saved.set("another-app", new Map([[scope + "assets/other-12345678.js", new Response("other app")]]));
  env.network.clear();
  await expect(env.request("assets/other-12345678.js")).rejects.toThrow("Network unavailable");
  await expect(env.request(`research/${"c".repeat(64)}/catalog.json`)).rejects.toThrow("Network unavailable");
  expect(env.request("__nisayon_worker_lease__")).toBeNull();
});

it("falls through to the actual network request when storage is evicted", async () => {
  const env = environment();
  await env.event("install");
  env.saved.clear();
  expect(await (await env.request("assets/shell-v1000000.js"))!.text()).toBe("shell-v1");
  env.network.clear();
  await expect(env.request("assets/shell-v1000000.js")).rejects.toThrow(
    "Network unavailable",
  );
});

it("keeps manifest identity, icons and all three shortcuts within the installed scope", () => {
  const manifest = JSON.parse(
    readFileSync(join(PUBLIC_DIR, "site.webmanifest"), "utf8"),
  );
  expect(new URL(manifest.id, scope).href).toBe(scope);
  expect(new URL(manifest.scope, scope).href).toBe(scope);
  expect(new URL(manifest.start_url, scope).hash).toBe("#view=system");
  expect(
    manifest.shortcuts.map(
      (shortcut: { name: string; url: string }) => [shortcut.name, new URL(shortcut.url, scope).hash],
    ),
  ).toEqual([["Lab", "#view=lab"], ["Ricci", "#view=concepts"], ["Develop", "#view=develop"]]);
  for (const icon of manifest.icons) {
    const bytes = readFileSync(join(PUBLIC_DIR, icon.src));
    expect(`${bytes.readUInt32BE(16)}x${bytes.readUInt32BE(20)}`).toBe(
      icon.sizes,
    );
    expect(new URL(icon.src, scope).href.startsWith(scope)).toBe(true);
  }
});
