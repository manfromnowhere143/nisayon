import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { GlassCard } from "../research/GlassCard";
import { offlineSnapshot, retryOfflineSupport, subscribeOffline } from "./runtime";

interface InstallPrompt extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}
function isInstalled() {
  return (
    matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}
export function AppAccessButton() {
  return (
    <button
      type="button"
      className="ibtn research-icon app-access-button"
      aria-label="Nisayon on this device"
      aria-haspopup="dialog"
      onClick={() => window.dispatchEvent(new Event("nisayon:app-access"))}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="5" y="3" width="14" height="18" rx="4" />
        <path d="M10 17h4M12 7v6m-3-3 3 3 3-3" />
      </svg>
    </button>
  );
}
export function AppAccess({ onOpen }: { onOpen: () => void }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("device");
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [installed, setInstalled] = useState(isInstalled);
  const [online, setOnline] = useState(() => navigator.onLine);
  const [notice, setNotice] = useState("");
  const [installing, setInstalling] = useState(false);
  const installPending = useRef(false);
  const offline = useSyncExternalStore(
    subscribeOffline,
    offlineSnapshot,
    offlineSnapshot,
  );
  useEffect(() => {
    const show = () => {
      onOpen();
      setOpen(true);
    };
    const offered = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
    };
    const completed = () => {
      setInstalled(true);
      setPrompt(null);
    };
    const connection = () => setOnline(navigator.onLine);
    const display = matchMedia("(display-mode: standalone)");
    const changed = () => setInstalled(isInstalled());
    window.addEventListener("nisayon:app-access", show);
    window.addEventListener("beforeinstallprompt", offered);
    window.addEventListener("appinstalled", completed);
    window.addEventListener("online", connection);
    window.addEventListener("offline", connection);
    display.addEventListener("change", changed);
    return () => {
      window.removeEventListener("nisayon:app-access", show);
      window.removeEventListener("beforeinstallprompt", offered);
      window.removeEventListener("appinstalled", completed);
      window.removeEventListener("online", connection);
      window.removeEventListener("offline", connection);
      display.removeEventListener("change", changed);
    };
  }, [onOpen]);
  const install = async () => {
    if (!prompt || installPending.current) return;
    installPending.current = true;
    setInstalling(true);
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      setNotice(
        choice.outcome === "accepted"
          ? "Installation requested. Your browser will complete it."
          : "You can install later from your browser menu.",
      );
    } catch {
      setNotice("Use your browser menu to install Nisayon.");
    }
    setPrompt(null);
    setInstalling(false);
    installPending.current = false;
  };
  if (!open) return null;
  return (
    <GlassCard
      title="Nisayon on this device"
      eyebrow={online ? "Connected" : "Offline"}
      onClose={() => setOpen(false)}
    >
      <nav className="workspace-tabs" aria-label="App access">
        <button
          aria-pressed={tab === "device"}
          onClick={() => setTab("device")}
        >
          On this device
        </button>
        <button
          aria-pressed={tab === "offline"}
          onClick={() => setTab("offline")}
        >
          Offline & updates
        </button>
      </nav>
      <div className="app-access-reading">
        {tab === "device" ? (
          <>
            <h3>
              {installed
                ? "Your own instrument window."
                : "One place for the whole instrument."}
            </h3>
            <p>
              {installed
                ? "Nisayon is running as an app. Investigate, Library and Develop stay connected through the navigation below."
                : "Keep Nisayon in your Dock or on your Home Screen. It opens in its own window, with the same saved theme and exact experiment links."}
            </p>
            {!installed && prompt ? (
              <button
                className="research-action"
                disabled={installing}
                onClick={() => void install()}
              >
                {installing ? "Opening installation…" : "Install Nisayon ↗"}
              </button>
            ) : null}
            {!installed && !prompt ? (
              <dl className="app-install-paths">
                <div>
                  <dt>iPhone & iPad</dt>
                  <dd>Share → Add to Home Screen → Open as Web App.</dd>
                </div>
                <div>
                  <dt>Safari on Mac</dt>
                  <dd>File → Add to Dock.</dd>
                </div>
                <div>
                  <dt>Chrome & Edge</dt>
                  <dd>
                    Choose Install Nisayon in the browser menu when offered.
                  </dd>
                </div>
              </dl>
            ) : null}
            {notice ? <p role="status">{notice}</p> : null}
          </>
        ) : (
          <>
            <h3>
              {offline.status === "ready"
                ? "Research, available offline."
                : offline.status === "saving"
                  ? "Saving the research workspace."
                  : "Connected reading is available."}
            </h3>
            <p>
              {offline.status === "ready"
                ? "The saved research workspace can open without a connection. Each investigation still identifies the exact evidence snapshot it displays."
                : offline.status === "saving"
                  ? "The app is checking and saving its research files in the background. Keep this window open until saving completes."
                  : "Offline storage is not available yet in this browser. The instrument continues to work with a connection."}
            </p>
            <p>
              Robot recordings, historical catalogs and external source links
              need a connection, as do the intro and background video. A recording
              already open remains usable while it is held in this window.
            </p>
            {offline.status === "error" ? <button className="research-action" disabled={!online} onClick={retryOfflineSupport}>
              {online ? "Retry offline setup" : "Reconnect to retry setup"}
            </button> : null}
            {offline.status === "ready" ? <p><a href="#view=research" onClick={() => setOpen(false)}>Open saved research</a></p> : null}
            <p>Private review files stay in this window; they are never uploaded or saved by the offline cache. Keep the original file to reopen it. Your browser may remove offline storage when space is needed.</p>
            <div className="app-update-state">
              <span className="research-micro">
                {offline.update ? "Update ready" : "Updates"}
              </span>
              <p>
                {offline.update
                  ? "The updated workspace is ready. Reload when you are ready to use it. Keep any private review file so you can reopen it."
                  : "Updates are prepared in the background. Reloads open the current online release; the verified saved copy is available offline. Open recordings stay on their selected moment."}
              </p>
            </div>
          </>
        )}
      </div>
    </GlassCard>
  );
}
