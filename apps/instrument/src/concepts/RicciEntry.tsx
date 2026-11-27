import { useEffect, useState, type RefObject } from "react";
import { loadRicci, preparedRicci } from "./loadRicci";

/** A prepared route can commit immediately. Loading code explicitly avoids a
 * new Suspense fallback's minimum display interval on a short navigation. */
export function RicciEntry(props: {
  heading: RefObject<HTMLHeadingElement | null>;
  laboratory: () => void;
}) {
  const [Studio, setStudio] = useState(preparedRicci);
  const [failed, setFailed] = useState(false);
  const [attempt, retry] = useState(0);
  useEffect(() => {
    if (Studio) return;
    let active = true;
    setFailed(false);
    void loadRicci().then(
      (module) => {
        if (active) setStudio(() => module.ConceptStudio);
      },
      () => {
        if (active) setFailed(true);
      },
    );
    return () => {
      active = false;
    };
  }, [Studio, attempt]);
  if (Studio) return <Studio {...props} />;
  return (
    <main className="ricci-entry-state" aria-busy={!failed}>
      <h1 ref={props.heading} tabIndex={-1}>
        Ricci
      </h1>
      <p role="status">
        {failed ? "Ricci could not load." : "Preparing the exhibit"}
      </p>
      {failed ? (
        <button type="button" onClick={() => retry((value) => value + 1)}>
          Try again
        </button>
      ) : null}
    </main>
  );
}
