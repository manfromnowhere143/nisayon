export interface OfflineState {
  status: "unavailable" | "saving" | "ready" | "error";
  update: boolean;
}
let state: OfflineState = { status: "unavailable", update: false };
const listeners = new Set<() => void>();
export const offlineSnapshot = () => state;
export const retryOfflineSupport = () => window.dispatchEvent(new Event("nisayon:retry-offline"));
export const subscribeOffline = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
function publish(next: OfflineState) {
  if (state.status === next.status && state.update === next.update) return;
  state = next;
  listeners.forEach((listener) => listener());
}

/** Install after the document loads. Worker updates change fetch routing while
 * keeping the loaded document and private review intact. Never force a reload. */
export function startOfflineSupport(): () => void {
  if (
    !import.meta.env.PROD ||
    !window.isSecureContext ||
    !("serviceWorker" in navigator)
  )
    return () => {};
  let stopped = false,
    idle: number | undefined,
    timer: number | undefined;
  const cleanups: (() => void)[] = [];
  const initialController = navigator.serviceWorker.controller;
  let updateReady = false;
  let currentRegistration: ServiceWorkerRegistration | undefined;
  let registering = false;
  let retrying = false;
  const register = async () => {
    if (stopped || registering) return;
    registering = true;
    publish({ status: "saving", update: false });
    try {
      const registration = await navigator.serviceWorker.register(
        new URL("sw.js", document.baseURI).href,
        { scope: new URL("./", document.baseURI).href, updateViaCache: "none" },
      );
      if (stopped) return;
      currentRegistration = registration;
      const update = () => {
        if (stopped) return;
        const failed = registration.installing?.state === "redundant";
        publish({
          status: registration.active ? "ready" : failed ? "error" : "saving",
          update: updateReady || !!registration.waiting,
        });
      };
      const watch = () => {
        const worker = registration.installing;
        if (worker) {
          const changed = () => {
            if (
              worker.state === "redundant" &&
              !registration.active &&
              !stopped
            )
              publish({ status: "error", update: false });
            else update();
          };
          worker.addEventListener("statechange", changed);
          cleanups.push(() =>
            worker.removeEventListener("statechange", changed),
          );
        }
        update();
      };
      registration.addEventListener("updatefound", watch);
      cleanups.push(() =>
        registration.removeEventListener("updatefound", watch),
      );
      const controlled = () => {
        if (initialController && navigator.serviceWorker.controller !== initialController)
          updateReady = true;
        update();
      };
      navigator.serviceWorker.addEventListener("controllerchange", controlled);
      cleanups.push(() =>
        navigator.serviceWorker.removeEventListener("controllerchange", controlled),
      );
      // Long-lived tabs check again when revisited, without reloading a review.
      // Bound checks so switching windows cannot create an update request loop.
      let lastCheck = 0;
      const check = () => {
        if (stopped || retrying || document.visibilityState !== "visible" || !navigator.onLine)
          return;
        const now = Date.now();
        if (now - lastCheck < 60_000) return;
        lastCheck = now;
        void registration.update().catch(() => {});
      };
      document.addEventListener("visibilitychange", check);
      window.addEventListener("online", check);
      cleanups.push(() => {
        document.removeEventListener("visibilitychange", check);
        window.removeEventListener("online", check);
      });
      watch();
      controlled();
      check();
      // ready can remain pending after an unsuccessful first installation.
      // Release this guard so an explicit retry can call registration.update().
      registering = false;
      await navigator.serviceWorker.ready;
      update();
    } catch {
      if (!stopped) publish({ status: "error", update: false });
    } finally {
      registering = false;
    }
  };
  const retry = async () => {
    if (stopped || registering || retrying || !navigator.onLine) return;
    if (!currentRegistration) { await register(); return; }
    retrying = true;
    publish({ status: currentRegistration.active ? "ready" : "saving", update: state.update });
    try {
      await currentRegistration.update();
    } catch {
      if (!stopped) publish({ status: currentRegistration.active ? "ready" : "error", update: state.update });
    } finally { retrying = false; }
  };
  // Install these before the first registration, so an offline first visit
  // recovers without reloading or discarding a private review.
  const reconnected = () => { if (state.status === "error") void retry(); };
  const requested = () => { void retry(); };
  window.addEventListener("online", reconnected);
  window.addEventListener("nisayon:retry-offline", requested);
  cleanups.push(() => {
    window.removeEventListener("online", reconnected);
    window.removeEventListener("nisayon:retry-offline", requested);
  });
  const schedule = () => {
    if (typeof window.requestIdleCallback === "function")
      idle = window.requestIdleCallback(
        () => {
          void register();
        },
        { timeout: 4000 },
      );
    else
      timer = window.setTimeout(() => {
        void register();
      }, 1200);
  };
  if (document.readyState === "complete") schedule();
  else window.addEventListener("load", schedule, { once: true });
  return () => {
    stopped = true;
    window.removeEventListener("load", schedule);
    if (idle !== undefined) window.cancelIdleCallback(idle);
    if (timer !== undefined) window.clearTimeout(timer);
    cleanups.forEach((cleanup) => cleanup());
  };
}
