import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BrandMark } from "../ui/BrandMark";
import { Film, FILM_POSTER } from "./Film";
import { useHeroMotion } from "./heroMotion";
import type { ResearchRoute } from "./navigation";
import { InstrumentSymbol } from "../ui/InstrumentSymbol";
export const OPENING_MEDIA = {
  poster: "/media/cinematic/hall-1600.webp",
  smallPoster: "/media/cinematic/hall-960.webp",
};
export function Opening({
  navigate,
}: {
  navigate: (surface: ResearchRoute["surface"]) => void;
  inspectExample?: () => void;
}) {
  const [film, setFilm] = useState(
    () => new URLSearchParams(location.hash.slice(1)).get("film") === "vision",
  );
  const [playRequested, setPlayRequested] = useState(false),
    [posterError, setPosterError] = useState(false);
  const [posterReady, setPosterReady] = useState(false);
  const motion = useHeroMotion(!film, posterReady);
  const heading = useRef<HTMLHeadingElement>(null),
    filmOpen = useRef(film),
    historyClosing = useRef(false);
  useLayoutEffect(() => {
    heading.current?.focus({ preventScroll: true });
  }, []);
  useEffect(() => {
    const sync = () => {
      historyClosing.current = false;
      filmOpen.current =
        new URLSearchParams(location.hash.slice(1)).get("film") === "vision";
      setFilm(filmOpen.current);
      setPlayRequested(false);
    };
    window.addEventListener("popstate", sync);
    window.addEventListener("hashchange", sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener("hashchange", sync);
    };
  }, []);
  const openFilm = () => {
    if (filmOpen.current || historyClosing.current) return;
    filmOpen.current = true;
    const params = new URLSearchParams(location.hash.slice(1));
    params.set("view", "home");
    params.set("film", "vision");
    history.pushState(
      { ...history.state, nisayonFilm: true },
      "",
      `${location.pathname}${location.search}#${params}`,
    );
    setPlayRequested(true);
    setFilm(true);
  };
  const closeFilm = () => {
    filmOpen.current = false;
    setFilm(false);
    setPlayRequested(false);
    if (history.state?.nisayonFilm) {
      historyClosing.current = true;
      history.back();
    } else {
      const params = new URLSearchParams(location.hash.slice(1));
      params.delete("film");
      history.replaceState(
        history.state,
        "",
        `${location.pathname}${location.search}#${params}`,
      );
    }
  };
  return (
    <div className="opening">
      <a
        className="opening-skip"
        href="#opening-title"
        onClick={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
      >
        Skip to content
      </a>
      <main
        ref={motion.stage}
        className="opening-stage"
        aria-labelledby="opening-title"
      >
        <div className="opening-image">
          {!posterError ? (
            <img
              src={OPENING_MEDIA.poster}
              srcSet={`${OPENING_MEDIA.smallPoster} 960w, ${OPENING_MEDIA.poster} 1600w`}
              sizes="(max-width: 700px) 120vw, 100vw"
              width="1600"
              height="900"
              fetchPriority="high"
              onLoad={() => setPosterReady(true)}
              onError={() => {
                setPosterError(true);
                setPosterReady(true);
              }}
              alt="Concept scenes of humanoids, robot arms and mobile carriers in a sunlit hall. A future vision, not current Nisayon hardware."
            />
          ) : null}
          <video
            ref={motion.video}
            className="opening-motion"
            data-visible={motion.hasFrame}
            muted
            playsInline
            loop
            preload="none"
            aria-hidden="true"
            tabIndex={-1}
            disablePictureInPicture
          />
        </div>
        <div className="opening-composition">
          <h1 id="opening-title" ref={heading} tabIndex={-1}>
            <BrandMark size={64} />
            <span>Nisayon</span>
          </h1>
          <p className="opening-description">Experiment engine for robotics</p>
          <button
            className="opening-instrument"
            aria-label="Open Nisayon"
            onClick={() => navigate("lab")}
          >
            Open Nisayon
          </button>
        </div>
        {posterError && !motion.hasFrame ? (
          <p className="opening-unavailable">
            Scene unavailable. The instrument remains available.
          </p>
        ) : null}
        <button
          className="opening-motion-control"
          onClick={motion.toggle}
          aria-label={
            motion.requested
              ? "Pause background motion"
              : "Play background motion"
          }
        >
          <span>{motion.requested ? "Pause motion" : "Play motion"}</span>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            {motion.requested ? (
              <path d="M6 4v8M10 4v8" />
            ) : (
              <path d="m6 4 6 4-6 4Z" />
            )}
          </svg>
        </button>
        <button
          className="opening-film-access"
          onClick={openFilm}
          aria-label="Watch Nisayon intro"
        >
          <InstrumentSymbol name="film" />
          <span className="opening-film-meta">
            <span>Watch the film</span>
            <span>01:25</span>
          </span>
        </button>
      </main>
      {film ? (
        <Film
          poster={FILM_POSTER}
          playRequested={playRequested}
          onClose={closeFilm}
        />
      ) : null}
    </div>
  );
}
