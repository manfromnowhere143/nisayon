import { useState, type Ref } from "react";
import type { CaseId, ResearchCatalog } from "./catalog";
import { SystemDiagram } from "./Diagrams";
import { PublicProgress, ProgressReading } from "./PublicProgress";
import type { ProgressRecord, ProgressSnapshot } from "./progress";
import { LibraryReading } from "./LibraryReading";
import { EngineAtlas } from "./EngineAtlas";
import { Pages, useCompactWorkspace } from "./WorkspaceControls";

const STAGES = [
  {
    label: "Bind",
    title: "Start with the exact change.",
    text: "Bind the working deployment, changed deployment, policy, controller and reset state. An observation has a source and a clock; its shape alone cannot tell you its meaning.",
    evidence: "Inspect the observation convention",
    caseId: "transfer",
    scope: "Implemented · bounded deployment identities",
  },
  {
    label: "Execute",
    title: "A changed action needs a new future.",
    text: "Execute the intervention in closed loop. Recompute downstream state and observations, then retain what actually reached the controller. A recording from the old trajectory cannot answer the new question.",
    evidence: "Inspect the recorded robot lab",
    caseId: null,
    scope: "Implemented · pinned CPU Lift adapter",
  },
  {
    label: "Confirm",
    title: "Make the correction face fresh conditions.",
    text: "Freeze the candidate and its acceptance rule before the outcomes. Pair fresh initial conditions, keep task progress in view, and retain failures alongside successful repairs.",
    evidence: "Inspect the paired confirmation",
    caseId: "transfer",
    scope: "Implemented · finite confirmation obligation",
  },
  {
    label: "Account",
    title: "An improvement must survive its full cost.",
    text: "Count setup, failed attempts, execution, reset, confirmation, adoption and maintenance. Nested measurements count once. Missing effort stays unknown.",
    evidence: "Explore the cost boundary",
    caseId: "cost",
    scope: "Implemented accounting · economic advantage unproved",
  },
  {
    label: "Retain",
    title: "Keep the result that could change your mind.",
    text: "Bind the conclusion to its source and regression. Supported, rejected, blocked and unresolved have different meanings. Preserve the witness and the reason the next experiment is still needed.",
    evidence: "Inspect the current blocked baseline",
    caseId: "deployment",
    scope: "Implemented records · owner value and untouched reuse open",
  },
] as const;

const VIEWS = ["Overview", "Evidence", "Engine", "Open question"] as const;
export function SystemWorkspace({
  catalog,
  heading,
  choose,
  lab,
  study,
  records,
}: {
  catalog: ResearchCatalog;
  heading: Ref<HTMLHeadingElement>;
  choose: (id: CaseId) => void;
  lab: () => void;
  study: () => void;
  records?: () => void;
}) {
  const [view, setView] = useState<(typeof VIEWS)[number] | "Stage" | "Progress">("Overview");
  const [progress, setProgress] = useState<{ records: ProgressRecord[]; snapshot: ProgressSnapshot } | null>(null);
  const [stage, setStage] = useState(0);
  const [page, setPage] = useState(0);
  const [boundaryPage, setBoundaryPage] = useState(0);
  const compact = useCompactWorkspace();
  const perPage = compact ? 3 : 9;
  const pageCount = Math.ceil(catalog.cases.length / perPage);
  const currentPage = Math.min(page, pageCount - 1);
  const stageInfo = STAGES[stage]!;
  return (
    <main id="research-content" className="system-workspace">
      <header className="system-intro">
        <p className="research-micro">LIBRARY / THE EXPERIMENT ENGINE</p>
        <h1 ref={heading} tabIndex={-1}>From a failed task to a correction <span>that holds.</span></h1>
      </header>
      <div className="system-panel">
        <div className="system-overview" hidden={view !== "Overview"}>
          <div className="system-anatomy"><SystemDiagram active={stage} /></div>
          <section className="system-method" aria-label="Inspect the experiment mechanism">
            <button className="method-peek" onClick={() => setView("Stage")} aria-label={`Read ${stageInfo.label}: ${stageInfo.title}`}>
              <span>{stageInfo.title}</span>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
            </button>
            <span className="method-scope">{stageInfo.scope}</span>
          </section>
        </div>
        {view === "Stage" ? <LibraryReading key="stage" title={stageInfo.title} eyebrow={`0${stage + 1} / ${stageInfo.label}`} onClose={() => setView("Overview")}>
          <div className="stage-card-reading">
            <p>{stageInfo.text}</p>
            <p className="method-scope">{stageInfo.scope}</p>
            <button className="research-text-action" onClick={() => stageInfo.caseId ? choose(stageInfo.caseId) : lab()}>{stageInfo.evidence}</button>
          </div>
        </LibraryReading> : null}
        {view === "Progress" && progress ? <ProgressReading floating records={progress.records} snapshot={progress.snapshot} onClose={() => setView("Overview")} /> : null}
        {view !== "Overview" && view !== "Stage" && view !== "Progress" ? (
          <LibraryReading
            key={view}
            title={
              view === "Evidence"
                ? "Evidence"
                : view === "Engine"
                  ? "Inside the engine"
                  : "What remains open"
            }
            eyebrow="LIBRARY"
            onClose={() => setView("Overview")}
          >
            {view === "Evidence" ? (
              <section
                className="research-index"
                aria-label="Selected investigations"
              >
                <div className="research-index-heading">

                  <span className="research-micro">
                    {catalog.cases.length} investigations
                  </span>
                </div>
                <div className="investigation-index">
                  {catalog.cases
                    .slice(currentPage * perPage, (currentPage + 1) * perPage)
                    .map((c, i) => (
                      <button
                        className="index-entry"
                        key={c.id}
                        onClick={() => choose(c.id)}
                      >
                        <span className="index-number">
                          {String(currentPage * perPage + i + 1).padStart(
                            2,
                            "0",
                          )}{" "}
                          / {c.code}
                        </span>
                        <b>{c.title}</b>
                        <small>{c.kind}</small>
                        <span className={`research-status status-${c.status}`}>
                          {c.status}
                        </span>
                        <span className="index-entry-arrow" aria-hidden="true">

                        </span>
                      </button>
                    ))}
                </div>
                {pageCount > 1 ? (
                  <Pages
                    page={currentPage}
                    count={pageCount}
                    onChange={setPage}
                    label="investigations"
                  />
                ) : null}
                <p className="library-catalog-identity">Recorded {catalog.asOf} · <code title={`Source revision ${catalog.sourceCommit}`}>{catalog.sourceCommit.slice(0, 7)}</code></p>
              </section>
            ) : null}
            {view === "Engine" && catalog.modules ? (
              <>
                {records ? <button className="research-text-action library-records" onClick={records}>Engine records</button> : null}
                <EngineAtlas modules={catalog.modules} revision={catalog.sourceCommit} onStudy={study} />
              </>
            ) : null}
            {view === "Engine" && !catalog.modules ? (
              <p>
                This source atlas is absent from the selected historical
                catalog.
              </p>
            ) : null}
            {view === "Open question" ? (
              <div className="system-boundaries" data-boundary={boundaryPage}>
                <nav
                  className="workspace-tabs mobile-boundary-tabs"
                  aria-label="Research boundary"
                >
                  <button
                    aria-pressed={boundaryPage === 0}
                    onClick={() => setBoundaryPage(0)}
                  >
                    Open question
                  </button>
                  <button
                    aria-pressed={boundaryPage === 1}
                    onClick={() => setBoundaryPage(1)}
                  >
                    Upstream adoption
                  </button>
                </nav>
                <section className="system-boundary">
                  <p className="research-micro">THE OPEN QUESTION</p>
                  <h2>Does it help an engineer make a better decision?</h2>
                  <p>
                    The bounded engine and retained corrections exist. A
                    consequential independently owned incident, a fair
                    comparison of complete effort, and separate untouched reuse
                    are still needed. A general compiler and adaptive selector
                    remain proposed.
                  </p>
                  <button
                    className="research-text-action"
                    onClick={() => choose("cost")}
                  >
                    Inspect the cost boundary
                  </button>
                </section>
                {catalog.adoption ? (
                  <section className="research-adoption">
                    <span className="research-micro">
                      UPSTREAM / {catalog.adoption.date}
                    </span>
                    <h3>{catalog.adoption.title}</h3>
                    <div>
                      <strong>
                        {catalog.adoption.passed}
                        <span> exposed CPU controls pass</span>
                      </strong>
                      <strong>
                        {catalog.adoption.unchangedJointOutputs}
                        <span> joint outputs unchanged</span>
                      </strong>
                    </div>
                    <p>
                      {catalog.adoption.scope} Owner savings and untouched reuse
                      remain unestablished.
                    </p>
                    <a
                      href={catalog.adoption.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Inspect merged correction{" "}
                      {catalog.adoption.revision.slice(0, 7)}
                    </a>
                  </section>
                ) : null}
              </div>
            ) : null}
          </LibraryReading>
        ) : null}
      </div>
      <footer className="library-controls">
        <nav className="method-stages" aria-label="Experiment stages">
          {STAGES.map((s, i) => <button key={s.label} aria-pressed={stage === i} onClick={() => { setStage(i); setView("Overview"); }}>
            <span>0{i + 1}</span>{s.label}<i aria-hidden="true" />
          </button>)}
        </nav>
        <nav className="workspace-tabs library-views" aria-label="System views">
          {VIEWS.map(v => <button key={v} aria-pressed={v === view} onClick={() => setView(v)}>{v}</button>)}
        </nav>
        <PublicProgress retained={catalog.upstream} onOpen={(records, snapshot) => { setProgress({ records, snapshot }); setView("Progress"); }} />
      </footer>
    </main>
  );
}
