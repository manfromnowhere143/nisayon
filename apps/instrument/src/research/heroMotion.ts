import { useEffect, useRef, useState } from "react";

export const HERO_MEDIA = {
  // One short, silent sequence, encoded by Mux Premium. A bounded native
  // rendition keeps the opening independent of the full film's HLS runtime.
  wide: "https://stream.mux.com/Qqp4Ub85Cg01R02i02xXTP02OaeXluxXTvt01fVB02GkMpXBs/720p.mp4",
  small: "https://stream.mux.com/Qqp4Ub85Cg01R02i02xXTP02OaeXluxXTvt01fVB02GkMpXBs/540p.mp4",
};
const preferenceKey = "nisayon.hero.motion";
type Intent = "auto" | "play" | "pause";
type Connection = EventTarget & { saveData?: boolean; effectiveType?: string };
const connection = () => (navigator as Navigator & { connection?: Connection }).connection;
function initialIntent(): Intent {
  try { return localStorage.getItem(preferenceKey) === "paused" ? "pause" : "auto"; }
  catch { return "auto"; }
}
function wantsStill() {
  const network = connection();
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
    || Boolean(network?.saveData) || /^(slow-)?2g$/.test(network?.effectiveType ?? "");
}

/** One native decoder. The poster owns first paint; the film and instrument stay independent. */
export function useHeroMotion(active: boolean, posterReady: boolean) {
  const stage = useRef<HTMLElement>(null), video = useRef<HTMLVideoElement>(null);
  const [intent, setIntent] = useState<Intent>(initialIntent);
  const [still, setStill] = useState(wantsStill);
  const [visible, setVisible] = useState(() => document.visibilityState !== "hidden");
  const [inView, setInView] = useState(true), [painted, setPainted] = useState(false);
  const [blocked, setBlocked] = useState(false), [hasFrame, setHasFrame] = useState(false);
  const requested = intent === "play" || (intent === "auto" && !still);
  const suspended = !active || !visible || !inView || (still && intent !== "play");
  const run = requested && !blocked && !suspended && (painted || intent === "play");

  useEffect(() => {
    if (!posterReady) return;
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => setPainted(true)); });
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); };
  }, [posterReady]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)"), network = connection();
    const visibility = () => setVisible(document.visibilityState !== "hidden");
    const preferences = () => {
      setStill(wantsStill());
      // A new reduced-motion preference stops an earlier explicit playback choice too.
      if (media.matches) setIntent(value => value === "play" ? "auto" : value);
    };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pageshow", visibility);
    media.addEventListener("change", preferences);
    network?.addEventListener("change", preferences);
    const observer = typeof IntersectionObserver === "function"
      ? new IntersectionObserver(entries => setInView(entries.some(entry => entry.isIntersecting)), { threshold: 0 }) : null;
    if (stage.current) observer?.observe(stage.current);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pageshow", visibility);
      media.removeEventListener("change", preferences);
      network?.removeEventListener("change", preferences);
      observer?.disconnect();
    };
  }, []);

  useEffect(() => {
    const element = video.current;
    if (!element) return;
    let cancelled = false, frame = 0;
    if (!run) {
      element.pause();
      // Release the network/decoder when covered or hidden; a manual pause keeps its frame.
      if (suspended && element.hasAttribute("src")) {
        element.removeAttribute("src"); element.load(); setHasFrame(false);
      }
      return;
    }
    const reveal = () => { if (!cancelled) setHasFrame(true); };
    const failed = () => { if (!cancelled) { setBlocked(true); setHasFrame(false); } };
    const playing = () => {
      if (typeof element.requestVideoFrameCallback === "function") {
        frame = element.requestVideoFrameCallback(reveal);
      } else reveal();
    };
    element.addEventListener("playing", playing);
    element.addEventListener("error", failed);
    element.muted = true;
    if (!element.hasAttribute("src")) {
      const small = window.matchMedia("(max-width: 700px)").matches || connection()?.effectiveType === "3g";
      element.src = small ? HERO_MEDIA.small : HERO_MEDIA.wide;
    }
    void element.play().catch(failed);
    return () => {
      cancelled = true;
      if (frame) element.cancelVideoFrameCallback(frame);
      element.removeEventListener("playing", playing);
      element.removeEventListener("error", failed);
      element.pause();
    };
  }, [run, suspended]);

  useEffect(() => {
    const element = video.current;
    return () => {
      if (element?.hasAttribute("src")) { element.pause(); element.removeAttribute("src"); element.load(); }
    };
  }, []);

  const toggle = () => {
    const pause = requested && !blocked;
    if (blocked && video.current) {
      video.current.removeAttribute("src"); video.current.load();
    }
    setBlocked(false); setIntent(pause ? "pause" : "play");
    try {
      if (pause) localStorage.setItem(preferenceKey, "paused");
      else localStorage.removeItem(preferenceKey);
    } catch { /* Playback remains usable when preference storage is unavailable. */ }
  };
  return { stage, video, hasFrame, requested: requested && !blocked, toggle };
}
