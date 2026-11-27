import { useState } from "react";
import { catalogUrl, type ResearchCase } from "./catalog";
import { LibraryReading } from "./LibraryReading";
import { Pages } from "./WorkspaceControls";

export function ResearchReading({
  entry,
  catalog,
  revision,
  section,
  setSection,
  suppressed = false,
}: {
  entry: ResearchCase;
  catalog: string;
  revision: string;
  section: string | null;
  setSection: (section: string | null) => void;
  suppressed?: boolean;
}) {
  const [source, setSource] = useState(0);
  const [sourceView, setSourceView] = useState("records");
  const record = entry.sources[source]!;
  return (
    <aside className="research-reading" hidden={suppressed} inert={suppressed}>
      <div className="reading-summary" hidden={section !== null}>
        <p className={`research-status status-${entry.status}`}>
          {entry.status}
          <span> · within this scope</span>
        </p>
        <h2>{entry.finding}</h2>
        <p className="reading-scope">{entry.kind}</p>
        <nav className="reading-actions" aria-label="Inspect the explanation">
          <button onClick={() => setSection("mechanism")}>
            <span>What changed</span>

          </button>
          <button onClick={() => setSection("limit")}>
            <span>What remains open</span>

          </button>
          <button onClick={() => setSection("sources")}>
            <span>
              Inspect sources <small>{entry.sources.length}</small>
            </span>

          </button>
        </nav>
      </div>
      {section ? (
        <LibraryReading
          title={entry.code + " · " + entry.title}
          eyebrow="EVIDENCE / EXPLANATION"
          onClose={() => setSection(null)}
        >
          <nav
            className="workspace-tabs reading-tabs"
            aria-label="Investigation explanation"
          >
            {[
              ["finding", "Finding"],
              ["mechanism", "Change"],
              ["limit", "Limits"],
              ["sources", "Sources"],
            ].map(([id, label]) => (
              <button
                key={id}
                aria-pressed={section === id}
                onClick={() => setSection(id!)}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="reading-page" key={section}>
            <p className={`research-status status-${entry.status}`}>
              {entry.status}
              <span> · within this scope</span>
            </p>
            {section === "finding" ? (
              <>
                <span className="research-micro">Observed result</span>
                <h2>{entry.finding}</h2>
                <p className="reading-scope">{entry.kind}</p>
                <button
                  className="research-text-action"
                  onClick={() => setSection("limit")}
                >
                  Read the boundary →
                </button>
              </>
            ) : null}
            {section === "mechanism" ? (
              <>
                <h2>What changed</h2>
                <p>{entry.mechanism}</p>
              </>
            ) : null}
            {section === "limit" ? (
              <>
                <h2>What remains open</h2>
                <p>{entry.limit}</p>
              </>
            ) : null}
            {section === "sources" ? (
              <section
                className="research-sources"
                aria-label="Bound source records"
              >
                <nav
                  className="workspace-tabs source-views"
                  aria-label="Source details"
                >
                  <button
                    aria-pressed={sourceView === "records"}
                    onClick={() => setSourceView("records")}
                  >
                    Bound records
                  </button>
                  <button
                    aria-pressed={sourceView === "catalog"}
                    onClick={() => setSourceView("catalog")}
                  >
                    Catalog & links
                  </button>
                </nav>
                {sourceView === "records" ? (
                  <>
                    <p>
                      Exact source bytes. Integrity does not establish physical
                      truth.
                    </p>
                    <dl>
                      <div>
                        <dt>{record.path}</dt>
                        <dd>
                          <code>{record.sha256}</code>
                          <span>{record.bytes.toLocaleString("en")} bytes</span>
                        </dd>
                      </div>
                    </dl>
                    <Pages
                      page={source}
                      count={entry.sources.length}
                      onChange={setSource}
                      label="source record"
                    />
                  </>
                ) : (
                  <>
                    <p className="source-revision">
                      Research revision <code>{revision}</code>
                    </p>
                    <a
                      href={catalogUrl(catalog)}
                      download="nisayon-research-catalog.json"
                    >
                      Download pinned catalog
                    </a>
                    {entry.links.map((link) => (
                      <a
                        key={link.url}
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {link.title}
                      </a>
                    ))}
                  </>
                )}
              </section>
            ) : null}
          </div>
        </LibraryReading>
      ) : null}
    </aside>
  );
}
