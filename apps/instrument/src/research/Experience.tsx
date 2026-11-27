import { RicciEntry } from "../concepts/RicciEntry";
import { prepareRicci } from "../concepts/loadRicci";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { InstrumentStore } from "../state/store";
import type { LoaderOptions } from "../data/loader";
import { applyGround, readGround } from "../state/ground";
import { BrandMark } from "../ui/BrandMark";
import type { OpeningStatus } from "../ui/States";
import { InstrumentDock } from "./InstrumentDock";
import { LabBoundary } from "./LabBoundary";
import { AppAccess } from "../pwa/AppAccess";
import { workspaceUtilities } from "../ui/WorkspaceActions";
import { useEvidenceMotion } from "./useEvidenceMotion";
import {
  loadResearchCatalog,
  type CaseId,
  type ResearchCatalog,
} from "./catalog";
import { InvestigationDiagram } from "./Diagrams";
import { SystemWorkspace } from "./SystemWorkspace";
import { LibraryReading } from "./LibraryReading";
import { ResearchReading } from "./ResearchReading";
import { FixedEvidenceLayout } from "../ui/useDocumentEvidence";
import { installFocusPresentation } from "../ui/focusPresentation";
import { Qualification } from "../qualification/Qualification";
import { Develop } from "../qualification/Develop";
import { Opening } from "./Opening";
import { startOfflineSupport } from "../pwa/runtime";
import type { ReviewBundle } from "../qualification/checkBundle";
import type { ProjectionSelection } from "../qualification/projectionClient";
import {
  readResearchRoute,
  researchHash,
  type ResearchRoute,
} from "./navigation";


const RecordedLab = lazy(() =>
  import("../App").then((module) => ({ default: module.App })),
);
// Start the existing route chunk when navigation intent is clear. This creates
// no hidden WebGL context and does not download robot imagery or models.
const prepareConcepts = prepareRicci;
const ProjectionReview = lazy(() => import("../qualification/ProjectionReview"));
const CASE_LABEL: Record<CaseId, string> = {
  transfer: "Transfer",
  terminal: "Episode",
  processors: "State",
  decisions: "Choice",
  routing: "Identity",
  cost: "Cost",
  competence: "Competence",
  deployment: "Deployment",
  attention: "Attention",
  promotion: "Promotion",
  dispatch: "Dispatch",
};

const date = (value: string) =>
  new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T12:00:00Z`));
type CatalogState = (
  | { kind: "loading" }
  | { kind: "ready"; value: ResearchCatalog }
  | { kind: "error"; message: string }
) & { identity: string };

export function Experience({
  catalogLoader = loadResearchCatalog,
  labLoader,
}: {
  catalogLoader?: typeof loadResearchCatalog;
  labLoader?: LoaderOptions;
} = {}) {
  useEffect(() => installFocusPresentation(document), []);
  const [route, setRoute] = useState(() =>
    readResearchRoute(location.hash, location.search.length > 0),
  );
  const [labVisited, setLabVisited] = useState(route.surface === "lab");
  const [instrumentEntered, setInstrumentEntered] = useState(route.surface !== "home");
  const [offlineOptedIn, setOfflineOptedIn] = useState(false);
  useEffect(() => {
    if (route.surface !== "home") setInstrumentEntered(true);
  }, [route.surface]);
  // Preserve the complete offline instrument, but do not download its deferred
  // scene merely because somebody visits the cinematic opening.
  // Ricci inspection must not initiate the full instrument's cinematic/media
  // precache. Entering an evidence surface retains the existing offline flow.
  const offlineRequested = instrumentEntered && (route.surface !== "concepts" || offlineOptedIn);
  useEffect(() => offlineRequested ? startOfflineSupport() : undefined, [offlineRequested]);
  const [labOpening, setLabOpening] = useState<OpeningStatus>({
    waiting: true,
    stage: "module",
    detail: "Opening the recorded robot lab",
  });
  const [transportHost, setTransportHost] = useState<HTMLDivElement | null>(
    null,
  );
  // One resource-byte denominator spans recording and geometry. Once bytes
  // arrive the line remains full while qualification/first paint completes.
  const loadPercent = labOpening.progress === undefined ? undefined : Math.floor(labOpening.progress * 100);
  const loadAnnouncement = loadPercent === undefined ? labOpening.detail : loadPercent < 100 ? `${loadPercent}% transferred · ${labOpening.stage}` : "Preparing the first frame";
  const labReady = useRef(false);
  const [catalogState, setCatalog] = useState<CatalogState>({
    kind: "loading",
    identity: route.catalog,
  });
  // A new URL must never borrow the previous catalog, even for one paint.
  const catalog: CatalogState =
    catalogState.identity === route.catalog
      ? catalogState
      : { kind: "loading", identity: route.catalog };
  const [attempt, setAttempt] = useState(0);
  const [ground, setGround] = useState(readGround);
  const [copied, setCopied] = useState("");
  const [review, setReview] = useState<ReviewBundle | null>(null);
  const [projection, setProjection] = useState<ProjectionSelection | null>(null);
  const [requestedExample, setRequestedExample] = useState<"rejected" | null>(null);
  const [visualPage, setVisualPage] = useState("mechanism");
  const [mobilePanel, setMobilePanel] = useState("visual");
  const heading = useRef<HTMLHeadingElement>(null);
  const visual = useRef<HTMLElement>(null);
  const origin = useRef<HTMLElement | null>(null),
    pendingFocus = useRef(false);
  const instrument = useRef<InstrumentStore | null>(null);
  const labRegion = useRef<HTMLDivElement>(null),
    pendingStudy = useRef(false),
    unsubscribeStudy = useRef<(() => void) | null>(null);
  const connectStore = useCallback((value: InstrumentStore | null) => {
    unsubscribeStudy.current?.();
    instrument.current = value;
    const openPending = () => {
      if (!value) return;
      if (
        labReady.current &&
        pendingStudy.current &&
        value.getState().screen.kind === "ready"
      ) {
        pendingStudy.current = false;
        value.openStudy();
      }
    };
    unsubscribeStudy.current = value?.subscribe(openPending) ?? null;
    openPending();
  }, []);
  const onReadiness = useCallback((status: OpeningStatus) => {
    labReady.current = !status.waiting;
    setLabOpening(status);
    if (
      !status.waiting &&
      pendingStudy.current &&
      instrument.current?.getState().screen.kind === "ready"
    ) {
      pendingStudy.current = false;
      instrument.current.openStudy();
    }
  }, []);
  const routeRef = useRef(route);
  routeRef.current = route;
  const navigate = useCallback(
    (patch: Partial<ResearchRoute>, replace = false) => {
      const next = { ...routeRef.current, ...patch, issue: null };
      routeRef.current = next;
      if (next.surface !== "lab") {
        instrument.current?.pause();
        pendingStudy.current = false;
      }
      history[replace ? "replaceState" : "pushState"](
        { nisayon: true },
        "",
        `${location.pathname}${location.search}${researchHash(next)}`,
      );
      pendingFocus.current =
        patch.surface !== undefined || patch.caseId !== undefined;
      setRoute(next);
    },
    [],
  );
  useLayoutEffect(() => {
    // React now owns both the initial opening and later lab transitions. The
    // original critical-HTML signature is replaced in this same paint.
    document.getElementById("site-opening")?.remove();
    if (!location.hash && !location.search)
      history.replaceState(
        { nisayon: true },
        "",
        researchHash(routeRef.current),
      );
  }, []);
  useEffect(() => {
    const read = () => {
      pendingFocus.current = true;
      setRoute(readResearchRoute(location.hash, location.search.length > 0));
    };
    const open = (event: Event) => {
      origin.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      const surface = (event as CustomEvent<string>).detail;
      navigate({ surface: ["home", "system", "lab", "qualify", "develop", "concepts", "checks"].includes(surface) ? surface as ResearchRoute["surface"] : "research" });
    };
    window.addEventListener("popstate", read);
    window.addEventListener("hashchange", read);
    window.addEventListener("nisayon:navigate", open);
    return () => {
      window.removeEventListener("popstate", read);
      window.removeEventListener("hashchange", read);
      window.removeEventListener("nisayon:navigate", open);
    };
  }, [navigate]);
  useLayoutEffect(() => {
    document.documentElement.dataset.surface = route.issue
      ? "research"
      : route.surface;
    if (route.surface === "lab" && !route.issue) setLabVisited(true);
    else {
      instrument.current?.pause();
      pendingStudy.current = false;
    }
    const currentGround = readGround();
    applyGround(currentGround);
    setGround(currentGround);
    if (pendingFocus.current) {
      pendingFocus.current = false;
      if (route.surface === "lab" && !route.issue)
        (origin.current?.isConnected
          ? origin.current
          : labRegion.current
        )?.focus({ preventScroll: true });
      else heading.current?.focus({ preventScroll: true });
    }
    return () => {
      delete document.documentElement.dataset.surface;
    };
  }, [route.surface, route.caseId, route.issue]);
  useLayoutEffect(() => {
    if (
      catalog.kind === "ready" &&
      route.surface !== "lab" &&
      document.activeElement === document.body
    )
      heading.current?.focus({ preventScroll: true });
  }, [catalog.kind, route.surface]);
  useLayoutEffect(() => {
    setVisualPage("mechanism");
    setMobilePanel("visual");
  }, [route.surface, route.caseId]);
  const needsCatalog = ["system", "research", "lab"].includes(route.surface);
  const catalogRead = useRef<{ identity: string; attempt: number; loader: typeof catalogLoader; value?: ResearchCatalog }>({ identity: "", attempt: -1, loader: catalogLoader });
  useEffect(() => {
    // Navigation does not invalidate an already verified catalog. Only exact
    // identity, explicit retry or loader replacement starts verification.
    if (!needsCatalog) return;
    const read = catalogRead.current;
    if (read.identity === route.catalog && read.attempt === attempt && read.loader === catalogLoader && read.value) {
      setCatalog({ kind: "ready", identity: route.catalog, value: read.value }); return;
    }
    const controller = new AbortController();
    setCatalog({ kind: "loading", identity: route.catalog });
    catalogLoader(route.catalog, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) {
          catalogRead.current = { identity: route.catalog, attempt, loader: catalogLoader, value };
          setCatalog({ kind: "ready", value, identity: route.catalog });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setCatalog({
            kind: "error",
            identity: route.catalog,
            message:
              error instanceof Error ? error.message : "Evidence unavailable",
          });
      });
    return () => controller.abort();
  }, [route.catalog, needsCatalog, attempt, catalogLoader]);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(""), 3000);
    return () => clearTimeout(timer);
  }, [copied]);
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      setCopied("Selection link copied");
    } catch {
      setCopied("Copy this selection from the address bar");
    }
  };
  const toggleGround = () => {
    const next = ground === "black" ? "paper" : "black";
    if (instrument.current) instrument.current.setGround(next);
    else applyGround(next);
    setGround(next);
  };
  const choose = (id: CaseId) =>
    navigate({
      surface: "research",
      caseId: id,
      sample: 0,
      variant: "corrected",
    });
  const lab = () => navigate({ surface: "lab" });
  const study = () => {
    pendingStudy.current = true;
    lab();
    const value = instrument.current;
    if (labReady.current && value?.getState().screen.kind === "ready") {
      pendingStudy.current = false;
      value.openStudy();
    }
  };
  const current =
    catalog.kind === "ready"
      ? catalog.value.cases.find((c) => c.id === route.caseId)
      : undefined;
  const index =
    catalog.kind === "ready"
      ? catalog.value.cases.findIndex((c) => c.id === route.caseId)
      : 0;
  const showResearch = route.surface !== "lab" || route.issue !== null;
  useEvidenceMotion(
    visual,
    showResearch && route.surface === "research" && catalog.kind === "ready"
      ? `${route.caseId}:${route.variant}:${route.caseId === "decisions" ? route.sample : ""}:${mobilePanel}`
      : "",
  );

  const headerTools = workspaceUtilities({
    ground,
    toggleGround: route.surface === "concepts" ? undefined : toggleGround,
    copyLink: () => { void copyLink(); },
    copyLabel: "Copy this investigation link",
  });

  return (
    <FixedEvidenceLayout.Provider value={true}><div className="instrument-root">
      {route.surface === "home" && !route.issue ? <Opening
        navigate={(surface) => navigate({ surface })}
        inspectExample={() => { setRequestedExample("rejected"); navigate({ surface: "qualify" }); }}
      /> : null}
      <div
        className="retained-lab"
        ref={labRegion}
        tabIndex={-1}
        aria-label="Recorded robot lab"
        inert={showResearch || labOpening.waiting}
        aria-hidden={showResearch || labOpening.waiting}
        data-ready={!labOpening.waiting}
        style={
          showResearch || labOpening.waiting
            ? { visibility: "hidden" }
            : undefined
        }
      >
        {labVisited || !showResearch ? (
          <LabBoundary
            onUnavailable={() =>
              onReadiness({
                waiting: false,
                stage: "unavailable",
                detail: "The lab could not open",
              })
            }
          >
            <Suspense fallback={null}>
              <RecordedLab
                active={!showResearch}
                onStore={connectStore}
                onReadiness={onReadiness}
                transportHost={transportHost}
                {...(labLoader ? { loader: labLoader } : {})}
              />
            </Suspense>
          </LabBoundary>
        ) : null}
      </div>
      {!showResearch && labOpening.waiting ? (
        <div
          className="lab-loading"
          role="status"
          aria-busy="true"
          data-load-stage={labOpening.stage}
        >
          <div className="boot-signature">
            <BrandMark className="boot-mark" size={64} />
            <p className="boot-wordmark">Nisayon</p>
          </div>
          <div className="lab-loading-progress">
            <progress max={100} value={loadPercent} aria-label="Laboratory loading" aria-valuetext={loadAnnouncement} />
            {loadPercent !== undefined && loadPercent < 100 ? <output aria-hidden="true">{loadPercent}%</output> : null}
          </div>
          <span className="sr-only">{loadAnnouncement}</span>
        </div>
      ) : null}
      {(
        <div
          className="research-workspace"
          hidden={!showResearch || route.surface === "home" && !route.issue}
          inert={!showResearch || route.surface === "home" && !route.issue}
          data-research-open="true"
          data-view={route.surface}
        >
          <a
            className="research-skip"
            href="#research-content"
            onClick={(e) => {
              e.preventDefault();
              heading.current?.focus();
            }}
          >
            Skip to investigation
          </a>
          <header className="research-header">
            <button
              className="research-brand"
              onClick={() => navigate({ surface: "home" })}
              aria-label="Nisayon home"
            >
              <BrandMark />
              <span>Nisayon</span>
            </button>
            {route.surface !== "qualify" && route.surface !== "checks" ? <span className="research-edition">
              EXPERIMENT ENGINE / PHYSICAL AI
            </span> : null}
          </header>

          {copied ? (
            <span className="research-toast" role="status">
              {copied}
            </span>
          ) : null}
          <div className="research-body">
            {route.issue ? (
              <main className="research-error">
                <p className="research-micro">Selection unavailable</p>
                <h1 ref={heading} tabIndex={-1}>
                  {route.issue}
                </h1>
                <p>The instrument has not substituted another result.</p>
                <button
                  className="research-action"
                  onClick={() =>
                    navigate({
                      surface: "system",
                      caseId: "transfer",
                      sample: 0,
                      variant: "corrected",
                    })
                  }
                >
                  Open the system
                </button>
              </main>
            ) : route.surface === "checks" ? <Suspense fallback={<p role="status">Opening recorded engine checks…</p>}><ProjectionReview heading={heading} selection={projection} setSelection={setProjection} archives={() => navigate({ surface: "system" })} /></Suspense> : route.surface === "concepts" ? <RicciEntry heading={heading} laboratory={lab} /> : route.surface === "qualify" ? <Qualification active develop={() => navigate({ surface: "develop" })} bundle={review} setBundle={setReview} initialExample={requestedExample} onExampleConsumed={() => setRequestedExample(null)} /> : route.surface === "lab" || route.surface === "home" ? null : route.surface === "develop" ? <Develop review={() => navigate({ surface: "qualify" })} /> : catalog.kind === "error" ? (
              <main className="research-error">
                <p className="research-micro">Evidence unavailable</p>
                <h1 ref={heading} tabIndex={-1}>
                  This catalog could not be verified.
                </h1>
                <p role="alert">{catalog.message}</p>
                <button
                  className="research-action"
                  onClick={() => setAttempt((n) => n + 1)}
                >
                  Retry verification
                </button>
                <button className="research-text-action" onClick={lab}>
                  Open the recorded lab
                </button>
              </main>
            ) : catalog.kind === "loading" ? (
              <main className="library-loading" aria-busy="true" aria-label="Loading Library">
                <span className="sr-only" role="status">Verifying the selected evidence catalog.</span>
                <div aria-hidden="true" className="library-loading-rule" />
              </main>
            ) : route.surface === "system" ? (
              <SystemWorkspace
                catalog={catalog.value}
                heading={heading}
                choose={choose}
                lab={lab}
                study={study}
                records={() => navigate({ surface: "checks" })}
              />
            ) : current ? (
              <main
                id="research-content"
                className="investigation-workspace"
                data-mobile-panel={mobilePanel}
              >
                <nav
                  className="investigation-rail"
                  aria-label="Research investigations"
                >
                  {catalog.value.cases.map((c) => (
                    <button
                      key={c.id}
                      aria-current={c.id === current.id ? "page" : undefined}
                      onClick={() => choose(c.id)}
                    >
                      <span>{c.code}</span>
                      {CASE_LABEL[c.id]}
                    </button>
                  ))}
                </nav>
                <label className="investigation-picker">
                  <span className="sr-only">Investigation</span>
                  <select
                    value={current.id}
                    onChange={(event) => choose(event.target.value as CaseId)}
                  >
                    {catalog.value.cases.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code} · {CASE_LABEL[c.id]}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="investigation-title">
                  <div className="research-micro">
                    <span>
                      {current.code} / {current.kind}
                    </span>
                    <span>{date(current.date)}</span>
                  </div>
                  <h1 ref={heading} tabIndex={-1}>
                    {current.title}
                  </h1>
                  <p>{current.question}</p>
                </div>
                <nav
                  className="workspace-tabs mobile-research-panels"
                  aria-label="Investigation workspace"
                >
                  <button
                    aria-pressed={mobilePanel === "visual"}
                    onClick={() => setMobilePanel("visual")}
                  >
                    Experiment
                  </button>
                  <button
                    aria-pressed={mobilePanel === "reading"}
                    onClick={() => setMobilePanel("reading")}
                  >
                    Explanation & sources
                  </button>
                </nav>
                <div className="investigation-composition" data-reading={visualPage !== "mechanism" || undefined}>
                  <section
                    ref={visual}
                    className="research-visual"
                    inert={visualPage !== "mechanism"}
                    aria-label="Interactive evidence"
                    data-visual-page="mechanism"
                    data-case={current.id}
                  >
                    {[
                      "transfer",
                      "terminal",
                      "attention",
                      "promotion",
                      "dispatch",
                      "competence",
                      "deployment",
                    ].includes(current.id) ? (
                      <nav
                        className="workspace-tabs visual-tabs"
                        aria-label="Evidence view"
                      >
                        <button
                          aria-pressed={true}
                          onClick={() => setVisualPage("mechanism")}
                        >
                          Mechanism
                        </button>
                        <button
                          aria-pressed={visualPage === "evidence"}
                          onClick={() => setVisualPage("evidence")}
                        >
                          Retained evidence
                        </button>
                      </nav>
                    ) : null}
                    <InvestigationDiagram
                      key={current.id}
                      entry={current}
                      route={route}
                      select={navigate}
                    />
                  </section>
                  {visualPage === "evidence" ? (
                    <LibraryReading
                      title={current.code + " · Retained evidence"}
                      eyebrow={current.kind}
                      onClose={() => setVisualPage("mechanism")}
                    >
                      <section
                        className="research-visual evidence-card-visual"
                        aria-label="Retained experimental controls"
                        data-visual-page="evidence"
                        data-case={current.id}
                      >
                        <InvestigationDiagram
                          entry={current}
                          route={route}
                          select={navigate}
                        />
                      </section>
                    </LibraryReading>
                  ) : null}
                  <ResearchReading
                    key={current.id}
                    entry={current}
                    catalog={route.catalog}
                    revision={catalog.value.sourceCommit}
                    section={visualPage.startsWith("read:") ? visualPage.slice(5) : null}
                    setSection={section => setVisualPage(section ? `read:${section}` : "mechanism")}
                    suppressed={visualPage === "evidence"}
                  />
                </div>
                <div className="investigation-next">
                  <span className="research-micro">
                    {String(index + 1).padStart(2, "0")} /{" "}
                    {String(catalog.value.cases.length).padStart(2, "0")}{" "}
                    INVESTIGATIONS
                  </span>
                  <button
                    className="research-text-action"
                    onClick={() =>
                      choose(
                        catalog.value.cases[
                          (index + 1) % catalog.value.cases.length
                        ]!.id,
                      )
                    }
                  >
                    Next:{" "}
                    {
                      catalog.value.cases[
                        (index + 1) % catalog.value.cases.length
                      ]!.title
                    }{" "}
                    →
                  </button>
                </div>
              </main>
            ) : (
              <main className="research-error">
                <p className="research-micro">Historical catalog</p>
                <h1 ref={heading} tabIndex={-1}>
                  This investigation is absent from the selected catalog.
                </h1>
                <p>
                  The original catalog remains pinned. Select an investigation
                  it contains.
                </p>
                <button
                  className="research-action"
                  onClick={() => choose(catalog.value.cases[0]!.id)}
                >
                  Open the first retained investigation
                </button>
              </main>
            )}
          </div>
          <footer className="research-footer">
            <a href="/about/" target="_blank" rel="noopener">We let experiments overturn our explanations.</a>
            <span>{route.surface === "concepts" ? "Research concept · no hardware validation" : "Recorded evidence · no execution connection"}</span>
          </footer>
        </div>
      )}
      {route.surface !== "home" || route.issue ? <InstrumentDock
        surface={
          showResearch && route.surface === "lab" ? "research" : route.surface
        }
        loading={labOpening.waiting}
        navigate={(surface) => navigate({ surface })}
        transportHost={setTransportHost}
        prepareConcepts={prepareConcepts}
        utilities={headerTools}
      /> : null}
      <AppAccess onOpen={() => { instrument.current?.pause(); setOfflineOptedIn(true); }} />
    </div></FixedEvidenceLayout.Provider>
  );
}
