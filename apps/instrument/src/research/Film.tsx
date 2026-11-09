import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type Hls from "hls.js";
import { BrandMark } from "../ui/BrandMark";

export async function filmSource(signal: AbortSignal): Promise<{ hls: string; mp4: string }> {
  const response = await fetch("/__nisayon/film", { signal, cache: "no-store", credentials: "same-origin" });
  if (!response.ok) throw new Error("Film unavailable");
  const data: unknown = await response.json();
  if (!data || typeof data !== "object") throw new Error("Invalid film source");
  const { hls, mp4 } = data as Record<string, unknown>;
  for (const url of [hls, mp4]) {
    if (typeof url !== "string") throw new Error("Invalid film source");
    const parsed = new URL(url);
    if (parsed.origin !== "https://stream.mux.com" || parsed.username || parsed.password) throw new Error("Invalid film origin");
  }
  return { hls: hls as string, mp4: mp4 as string };
}

export function Film({ poster, playRequested, onClose, source = filmSource }: {
  poster: string; playRequested: boolean; onClose: () => void; source?: typeof filmSource;
}) {
  const dialog = useRef<HTMLDialogElement>(null), close = useRef<HTMLButtonElement>(null);
  const video = useRef<HTMLVideoElement>(null), stream = useRef<Hls | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  useLayoutEffect(() => {
    const origin = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const node = dialog.current!;
    if (node.showModal) node.showModal(); else node.setAttribute("open", "");
    close.current?.focus({ preventScroll: true });
    return () => { node.close?.(); if (origin?.isConnected) origin.focus({ preventScroll: true }); };
  }, []);
  useEffect(() => {
    const controller = new AbortController(), element = video.current!;
    setState("loading");
    const play = () => {
      if ((playRequested || attempt > 0) && !controller.signal.aborted && !document.hidden) {
        stream.current?.startLoad(-1);
        void element.play().catch(() => { /* Native play remains available when autoplay is denied. */ });
      }
    };
    const begin = () => stream.current?.startLoad(-1);
    const hidden = () => { if (document.hidden) { element.pause(); stream.current?.stopLoad(); } };
    const failed = () => { if (!controller.signal.aborted) { element.pause(); stream.current?.stopLoad(); setState("error"); } };
    element.addEventListener("play", begin); element.addEventListener("error", failed);
    document.addEventListener("visibilitychange", hidden);
    void source(controller.signal).then(async urls => {
      if (controller.signal.aborted) return;
      const { default: HlsPlayer } = await import("hls.js");
      if (controller.signal.aborted) return;
      // Chromium can advertise native HLS while failing this separate-audio
      // ladder. Prefer the tested MSE engine; native HLS remains the fallback
      // on platforms without supported MediaSource / ManagedMediaSource.
      if (!HlsPlayer.isSupported()) {
        element.src = element.canPlayType("application/vnd.apple.mpegurl") ? urls.hls : urls.mp4;
        setState("ready"); play(); return;
      }
      const hls = new HlsPlayer({ capLevelToPlayerSize: true, startLevel: -1, maxBufferLength: 20, maxMaxBufferLength: 30, backBufferLength: 10, autoStartLoad: false });
      stream.current = hls;
      hls.on(HlsPlayer.Events.MEDIA_ATTACHED, () => { if (!controller.signal.aborted) hls.loadSource(urls.hls); });
      hls.on(HlsPlayer.Events.MANIFEST_PARSED, () => { if (!controller.signal.aborted) { setState("ready"); play(); } });
      hls.on(HlsPlayer.Events.ERROR, (_event, data) => { if (data.fatal) failed(); });
      hls.attachMedia(element);
    }).catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => {
      controller.abort(); element.pause(); stream.current?.destroy(); stream.current = null;
      element.removeEventListener("play", begin); element.removeEventListener("error", failed);
      document.removeEventListener("visibilitychange", hidden); element.removeAttribute("src");
    };
  }, [source, playRequested, attempt]);
  return <dialog ref={dialog} className="film-screen" aria-label="Nisayon film" onCancel={event => { event.preventDefault(); onClose(); }}>
    <div className="film-picture">
      <video ref={video} controls playsInline preload="none" poster={poster} aria-label="Nisayon multi-robot film, 1 minute 20 seconds" aria-describedby="film-description">
        <track kind="captions" src="/media/cinematic/v3-captions.vtt" srcLang="en" label="English" />
      </video>
      {state === "loading" ? <p className="film-status" role="status">Opening film</p> : null}
      {state === "error" ? <div className="film-status film-error" role="alert"><p>The film could not load.</p><button onClick={() => setAttempt(n => n + 1)}>Try again <span aria-hidden="true">↗</span></button></div> : null}
    </div>
    <header className="film-header">
      <span className="film-signature"><BrandMark size={25} /><span>Nisayon</span></span>
      <div className="film-actions">
        <details className="film-information" id="film-description">
          <summary>About the film</summary>
          <div>
            <p>A silver humanoid crosses a robotics hall. A mechanical apparatus introduces Nisayon as an experiment engine for physical AI.</p>
            <p>A historical input-convention correction changes three signs in a ten-value observation block. With fixed policy weights, nine of ten fresh paired simulator tasks complete after correction, versus zero of ten before. One condition still fails.</p>
            <p>A separate authored coordinate example compares nine exposed samples and shows matching and wrong-sign software decisions. Subsequent diagrams propose selecting experiments and testing applicability. These remain research ambitions.</p>
            <p>The ending brings a humanoid, a moving carrier and a workstation arm into the same hall. These generated robot scenes illustrate the vision, not current Nisayon hardware, telemetry or general autonomous improvement.</p>
            <p>Instrumental music accompanies the film; there is no spoken narration.</p>
          </div>
        </details>
        <button ref={close} className="film-close" aria-label="Close film" onClick={onClose}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg></button>
      </div>
    </header>
  </dialog>;
}
