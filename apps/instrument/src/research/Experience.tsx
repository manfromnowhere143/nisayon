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
import { AppAccess, AppAccessButton } from "../pwa/AppAccess";
import { useEvidenceMotion } from "./useEvidenceMotion";
import {
  loadResearchCatalog,
  type CaseId,
  type ResearchCatalog,
} from "./catalog";
import { InvestigationDiagram } from "./Diagrams";
import { SystemWorkspace } from "./SystemWorkspace";
import { GlassCard } from "./GlassCard";
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
const Concepts = lazy(() => import("../concepts/ConceptStudio").then(module => ({ default: module.ConceptStudio })));
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
  useEffect(() => {
    if (route.surface !== "home") setInstrumentEntered(true);
  }, [route.surface]);
  // Preserve the complete offline instrument, but do not download its deferred
  // scene merely because somebody visits the cinematic opening.
  useEffect(() => instrumentEntered ? startOfflineSupport() : undefined, [instrumentEntered]);
  const [labOpening, setLabOpening] = useState<OpeningStatus>({
    waiting: true,
    stage: "module",
    detail: "Opening the recorded robot lab",
  });
  const [transportHost, setTransportHost] = useState<HTMLDivElement | null>(
    null,
  );
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
  const [workspaceControls, setWorkspaceControls] = useState(false);
  useEffect(() => { setWorkspaceControls(false); }, [route.surface]);
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
  useEffect(() => {
    // The opening and local review do not need a research catalog request.
    if (!["system", "research", "lab"].includes(route.surface)) return;
    const controller = new AbortController();
    setCatalog({ kind: "loading", identity: route.catalog });
    catalogLoader(route.catalog, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted)
          setCatalog({ kind: "ready", value, identity: route.catalog });
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
  }, [route.catalog, route.surface, attempt, catalogLoader]);
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

  const headerTools = <>
    <AppAccessButton />
    <button
      onClick={copyLink}
      aria-label="Copy this investigation link"
      className="research-icon"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m9 15 6-6M7 10 5 12a4 4 0 0 0 6 6l2-2m-2-8 2-2a4 4 0 0 1 6 6l-2 2" />
      </svg>
    </button>
    <button
      className="research-icon"
      onClick={toggleGround}
      aria-label={`Switch to ${ground === "black" ? "paper" : "black"} ground`}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="7" />
        <path
          d="M12 5a7 7 0 0 1 0 14Z"
          fill="currentColor"
          stroke="none"
        />
      </svg>
    </button>
  </>;

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
          <p className="lab-loading-detail">{labOpening.detail}</p>
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
            <div className="research-header-tools">{headerTools}</div>
            {route.surface === "qualify" || route.surface === "checks" ? <button
              className="workspace-menu research-workspace-menu"
              aria-label="Workspace controls"
              aria-haspopup="dialog"
              onClick={() => setWorkspaceControls(true)}
            ><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2" /><circle cx="15" cy="17" r="2" /></svg></button> : null}
          </header>
          {(route.surface === "qualify" || route.surface === "checks") && workspaceControls ? <GlassCard
            title="Workspace controls"
            onClose={() => setWorkspaceControls(false)}
          ><div className="research-workspace-tools">{headerTools}</div></GlassCard> : null}
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
            ) : route.surface === "checks" ? <Suspense fallback={<p role="status">Opening recorded engine checks…</p>}><ProjectionReview heading={heading} selection={projection} setSelection={setProjection} archives={() => navigate({ surface: "qualify" })} /></Suspense> : route.surface === "concepts" ? <Suspense fallback={<p role="status">Opening the concept studio…</p>}><Concepts heading={heading} laboratory={lab} /></Suspense> : route.surface === "qualify" ? <Qualification active develop={() => navigate({ surface: "develop" })} bundle={review} setBundle={setReview} initialExample={requestedExample} onExampleConsumed={() => setRequestedExample(null)} /> : route.surface === "lab" || route.surface === "home" ? null : route.surface === "develop" ? <Develop review={() => navigate({ surface: "qualify" })} /> : catalog.kind === "error" ? (
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
                  Open the recorded lab ↗
                </button>
              </main>
            ) : catalog.kind === "loading" ? (
              <main className="research-error" aria-busy="true">
                <p className="research-micro">Nisayon / research</p>
                <h1 ref={heading} tabIndex={-1}>
                  Reading the evidence.
                </h1>
                <p role="status">
                  Verifying the exact catalog named by this selection.
                </p>
              </main>
            ) : route.surface === "system" ? (
              <SystemWorkspace
                catalog={catalog.value}
                heading={heading}
                choose={choose}
                lab={lab}
                study={study}
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
                <div className="investigation-composition">
                  <section
                    ref={visual}
                    className="research-visual"
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
                    <GlassCard
                      title={current.code + " · Retained evidence"}
                      eyebrow={current.kind}
                      wide
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
                    </GlassCard>
                  ) : null}
                  <ResearchReading
                    key={current.id}
                    entry={current}
                    catalog={route.catalog}
                    revision={catalog.value.sourceCommit}
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
      {!route.issue && ["lab", "qualify", "checks"].includes(route.surface) ? <nav className="investigate-mode" aria-label="Investigation type"><button aria-pressed={route.surface === "lab"} onClick={() => navigate({ surface: "lab" })}>Robot</button><button aria-pressed={route.surface === "qualify"} onClick={() => navigate({ surface: "qualify" })}>Software</button><button aria-pressed={route.surface === "checks"} onClick={() => navigate({ surface: "checks" })}>Records</button></nav> : null}
      {route.surface !== "home" || route.issue ? <InstrumentDock
        surface={
          showResearch && route.surface === "lab" ? "research" : route.surface
        }
        loading={labOpening.waiting}
        navigate={(surface) => navigate({ surface })}
        transportHost={setTransportHost}
      /> : null}
      <AppAccess onOpen={() => instrument.current?.pause()} />
    </div></FixedEvidenceLayout.Provider>
  );
}
