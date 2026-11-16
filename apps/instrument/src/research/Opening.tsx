import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BrandMark } from "../ui/BrandMark";
import { Film } from "./Film";
import { useHeroMotion } from "./heroMotion";
import type { ResearchRoute } from "./navigation";
import evidence from "./opening-evidence.json";
export const OPENING_MEDIA = { poster: "/media/cinematic/hall-1600.webp", smallPoster: "/media/cinematic/hall-960.webp" };
const Chevron = () => <svg className="opening-chevron" viewBox="0 0 10 12" aria-hidden="true" focusable="false"><path d="m3 2 4 4-4 4" /></svg>;
export function Opening({ navigate, inspectExample }: {
  navigate: (surface: ResearchRoute["surface"]) => void; inspectExample: () => void;
}) {
  const [film, setFilm] = useState(() => new URLSearchParams(location.hash.slice(1)).get("film") === "vision");
  const [playRequested, setPlayRequested] = useState(false), [posterError, setPosterError] = useState(false);
  const [posterReady, setPosterReady] = useState(false);
  const motion = useHeroMotion(!film, posterReady);
  const heading = useRef<HTMLHeadingElement>(null), filmOpen = useRef(film), historyClosing = useRef(false);
  useLayoutEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  useEffect(() => {
    const sync = () => { historyClosing.current = false; filmOpen.current = new URLSearchParams(location.hash.slice(1)).get("film") === "vision"; setFilm(filmOpen.current); setPlayRequested(false); };
    window.addEventListener("popstate", sync); window.addEventListener("hashchange", sync);
    return () => { window.removeEventListener("popstate", sync); window.removeEventListener("hashchange", sync); };
  }, []);
  const openFilm = () => {
    if (filmOpen.current || historyClosing.current) return;
    filmOpen.current = true;
    const params = new URLSearchParams(location.hash.slice(1)); params.set("view", "home"); params.set("film", "vision");
    history.pushState({ ...history.state, nisayonFilm: true }, "", `${location.pathname}${location.search}#${params}`);
    setPlayRequested(true); setFilm(true);
  };
  const closeFilm = () => {
    filmOpen.current = false; setFilm(false); setPlayRequested(false);
    if (history.state?.nisayonFilm) { historyClosing.current = true; history.back(); }
    else { const params = new URLSearchParams(location.hash.slice(1)); params.delete("film"); history.replaceState(history.state, "", `${location.pathname}${location.search}#${params}`); }
  };
  return <div className="opening">
    <a className="opening-skip" href="#opening-title" onClick={event => { event.preventDefault(); heading.current?.focus(); }}>Skip to content</a>
    <main ref={motion.stage} className="opening-stage" aria-labelledby="opening-title">
      <div className="opening-image">{!posterError ? <img src={OPENING_MEDIA.poster} srcSet={`${OPENING_MEDIA.smallPoster} 960w, ${OPENING_MEDIA.poster} 1600w`} sizes="(max-width: 700px) 120vw, 100vw" width="1600" height="900" fetchPriority="high" onLoad={() => setPosterReady(true)} onError={() => { setPosterError(true); setPosterReady(true); }} alt="Concept scenes of humanoids, robot arms and mobile carriers in a sunlit hall. A future vision, not current Nisayon hardware." /> : null}<video ref={motion.video} className="opening-motion" data-visible={motion.hasFrame} muted playsInline loop preload="none" aria-hidden="true" tabIndex={-1} disablePictureInPicture /></div>
      <header className="opening-header"><button className="opening-brand" onClick={() => navigate("home")} aria-label="Nisayon home"><BrandMark size={30} /><span>Nisayon</span></button><div className="opening-utility"><button className="opening-concepts" onClick={() => navigate("concepts")}>Ricci 01 <span aria-hidden="true">↗</span></button><span>Developer preview</span></div></header>
      <div className="opening-copy"><p className="opening-kicker">PHYSICAL AI / EXPERIMENT ENGINE</p><h1 id="opening-title" ref={heading} tabIndex={-1}>Every change.<br />Put to the test.</h1><p className="opening-intro">Bounded experiments.<br />Evidence behind every decision.</p><button className="opening-instrument" onClick={() => navigate("lab")} aria-label="Open Nisayon"><span>Open Nisayon</span><Chevron /></button></div>
      <div className="opening-caption-row"><div className="opening-caption">{posterError && !motion.hasFrame ? "Scene unavailable. The instrument remains available." : "A future vision for robotics."}</div><button className="opening-motion-control" onClick={motion.toggle} aria-label={motion.requested ? "Pause background motion" : "Play background motion"}><span>{motion.requested ? "Pause motion" : "Play motion"}</span><svg viewBox="0 0 16 16" aria-hidden="true">{motion.requested ? <path d="M6 4v8M10 4v8" /> : <path d="m6 4 6 4-6 4Z" />}</svg></button></div>
      <footer className="opening-base"><button className="opening-evidence-access" onClick={inspectExample} aria-label="Inspect the retained rejected software change"><span className="opening-evidence-label">Retained software example <time dateTime={evidence.source_date}>25.10.26</time></span><span className="opening-evidence-answer">A change rejected.<Chevron /></span><span className="opening-evidence-scope">Valid execution · deployment unresolved</span></button><button className="opening-film-access" onClick={openFilm} aria-label="Watch Nisayon intro"><span className="opening-film-meta"><span>Watch intro</span><span>01:20</span></span><span className="opening-play-mark"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 11 7-11 7Z" /></svg></span></button></footer>
    </main>
    {film ? <Film poster={OPENING_MEDIA.poster} playRequested={playRequested} onClose={closeFilm} /> : null}
  </div>;
}
