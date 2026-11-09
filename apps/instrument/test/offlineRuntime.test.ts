import { afterEach, expect, it, vi } from "vitest";

let stop: (() => void) | undefined;
afterEach(() => {
  stop?.();
  stop = undefined;
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

async function setup(controlled = true, failRegistration = false, pendingReady = false) {
  vi.resetModules();
  vi.useFakeTimers();
  vi.stubEnv("PROD", true);
  vi.stubGlobal("isSecureContext", true);
  vi.spyOn(document, "readyState", "get").mockReturnValue("complete");
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  const original = new EventTarget();
  const registration = Object.assign(new EventTarget(), {
    active: original as EventTarget | null,
    installing: null as (EventTarget & { state: string }) | null,
    waiting: null,
    update: vi.fn(async () => registration),
  });
  const serviceWorker = Object.assign(new EventTarget(), {
    controller: controlled ? original : null as EventTarget | null,
    register: vi.fn(async () => registration),
    ready: pendingReady ? new Promise<typeof registration>(() => {}) : Promise.resolve(registration),
  });
  if (failRegistration) serviceWorker.register.mockRejectedValueOnce(new Error("Connection lost"));
  vi.stubGlobal("navigator", { serviceWorker, onLine: true });
  const runtime = await import("../src/pwa/runtime");
  stop = runtime.startOfflineSupport();
  await vi.advanceTimersByTimeAsync(1200);
  return { runtime, registration, serviceWorker };
}

it("retries a failed first registration when connectivity returns", async () => {
  const { runtime, serviceWorker } = await setup(false, true);
  expect(runtime.offlineSnapshot().status).toBe("error");
  window.dispatchEvent(new Event("online"));
  await vi.advanceTimersByTimeAsync(0);
  expect(serviceWorker.register).toHaveBeenCalledTimes(2);
  expect(runtime.offlineSnapshot().status).toBe("ready");
});

it("allows one explicit retry after first-install failure even while ready is pending", async () => {
  const { runtime, registration } = await setup(false, false, true);
  registration.active = null;
  const worker = Object.assign(new EventTarget(), { state: "installing" });
  registration.installing = worker;
  registration.dispatchEvent(new Event("updatefound"));
  worker.state = "redundant";
  worker.dispatchEvent(new Event("statechange"));
  expect(runtime.offlineSnapshot().status).toBe("error");
  let finish!: () => void;
  registration.update.mockImplementationOnce(() => new Promise(resolve => { finish = () => resolve(registration); }));
  runtime.retryOfflineSupport();
  runtime.retryOfflineSupport();
  expect(registration.update).toHaveBeenCalledTimes(2);
  expect(runtime.offlineSnapshot().status).toBe("saving");
  finish();
  await vi.advanceTimersByTimeAsync(0);
});

it("does not retry a failed registration after cleanup", async () => {
  const { runtime, serviceWorker } = await setup(false, true);
  stop?.();
  window.dispatchEvent(new Event("online"));
  runtime.retryOfflineSupport();
  await vi.advanceTimersByTimeAsync(0);
  expect(serviceWorker.register).toHaveBeenCalledOnce();
});

it("does not duplicate a reconnect recovery with the periodic update check", async () => {
  const { registration } = await setup(false, false, true);
  registration.active = null;
  registration.installing = Object.assign(new EventTarget(), { state: "redundant" });
  registration.dispatchEvent(new Event("updatefound"));
  await vi.advanceTimersByTimeAsync(60_000);
  let finish!: () => void;
  registration.update.mockImplementationOnce(() => new Promise(resolve => {
    finish = () => resolve(registration);
  }));
  window.dispatchEvent(new Event("online"));
  expect(registration.update).toHaveBeenCalledTimes(2);
  finish();
  await vi.advanceTimersByTimeAsync(0);
});

it("registers the stable worker URL without HTTP-cache reuse and checks for updates", async () => {
  const { runtime, serviceWorker, registration } = await setup();
  expect(serviceWorker.register).toHaveBeenCalledWith(
    new URL("sw.js", document.baseURI).href,
    { scope: new URL("./", document.baseURI).href, updateViaCache: "none" },
  );
  expect(registration.update).toHaveBeenCalledOnce();
  expect(runtime.offlineSnapshot()).toEqual({ status: "ready", update: false });
});

it("keeps an update notice after activation without navigating or replacing the loaded document", async () => {
  const { runtime, serviceWorker } = await setup();
  const documentBefore = document.documentElement;
  const locationBefore = window.location.href;
  serviceWorker.controller = new EventTarget();
  serviceWorker.dispatchEvent(new Event("controllerchange"));
  expect(runtime.offlineSnapshot()).toEqual({ status: "ready", update: true });
  expect(document.documentElement).toBe(documentBefore);
  expect(window.location.href).toBe(locationBefore);
  stop?.();
  serviceWorker.controller = null;
  serviceWorker.dispatchEvent(new Event("controllerchange"));
  expect(runtime.offlineSnapshot()).toEqual({ status: "ready", update: true });
});

it("does not label a first installation as a replacement update", async () => {
  const { runtime, serviceWorker } = await setup(false);
  serviceWorker.controller = new EventTarget();
  serviceWorker.dispatchEvent(new Event("controllerchange"));
  expect(runtime.offlineSnapshot()).toEqual({ status: "ready", update: false });
});

it("checks a revisited tab at most once per minute and removes listeners on cleanup", async () => {
  const { registration } = await setup();
  document.dispatchEvent(new Event("visibilitychange"));
  window.dispatchEvent(new Event("online"));
  expect(registration.update).toHaveBeenCalledOnce();
  await vi.advanceTimersByTimeAsync(60_000);
  document.dispatchEvent(new Event("visibilitychange"));
  expect(registration.update).toHaveBeenCalledTimes(2);
  stop?.();
  await vi.advanceTimersByTimeAsync(60_000);
  document.dispatchEvent(new Event("visibilitychange"));
  window.dispatchEvent(new Event("online"));
  expect(registration.update).toHaveBeenCalledTimes(2);
});

it("keeps saved reading available when a background update check fails", async () => {
  const { runtime, registration } = await setup();
  registration.update.mockRejectedValueOnce(new Error("Offline"));
  await vi.advanceTimersByTimeAsync(60_000);
  window.dispatchEvent(new Event("online"));
  await Promise.resolve();
  expect(runtime.offlineSnapshot()).toEqual({ status: "ready", update: false });
});
