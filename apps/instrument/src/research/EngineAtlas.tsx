import { useMemo, useState } from "react";
import type { EngineModule } from "./catalog";
import { Pages, TextReading, useCompactWorkspace } from "./WorkspaceControls";

export function EngineAtlas({
  modules,
  revision,
  onStudy,
}: {
  modules: EngineModule[];
  revision: string;
  onStudy: () => void;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("engine.confirmation_service");
  const [page, setPage] = useState(0);
  const [section, setSection] = useState("Summary");
  const [entryPage, setEntryPage] = useState(0);
  const compact = useCompactWorkspace();
  const shown = useMemo(
    () =>
      modules.filter((m) =>
        `${m.package}.${m.name} ${m.description} ${m.entries.map((e) => e.name).join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase().trim()),
      ),
    [modules, query],
  );
  const active = modules.find((m) => `${m.package}.${m.name}` === selected)!;
  const perPage = 7;
  const entriesPerPage = compact ? 3 : 5;
  const select = (key: string) => {
    setSelected(key);
    setEntryPage(0);
  };
  return (
    <section className="engine-atlas" aria-label="Engine source atlas">
      <div className="engine-atlas-toolbar">
        <label className="engine-atlas-search">
          <span className="sr-only">Find a module or entry point</span>
          <input
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder="Find a module or entry point"
          />
        </label>
        <span className="research-micro">
          {shown.length} / {modules.length} modules
        </span>
      </div>
      <div className="engine-atlas-body">
        <div className="engine-module-directory">
          <div
            className="engine-module-map"
            role="group"
            aria-label="Implementation modules"
          >
            {shown.slice(page * perPage, (page + 1) * perPage).map((m) => (
              <button
                key={`${m.package}.${m.name}`}
                onClick={() => select(`${m.package}.${m.name}`)}
                aria-pressed={selected === `${m.package}.${m.name}`}
              >
                <span>{m.package === "qualification" ? "Q" : m.package === "engine" ? "E" : "A"}</span>
                {m.name.replaceAll("_", " ")}
              </button>
            ))}
          </div>
          {shown.length === 0 ? (
            <p>No matching modules.</p>
          ) : (
            <Pages
              page={page}
              count={Math.ceil(shown.length / perPage)}
              onChange={setPage}
              label="module directory"
            />
          )}
        </div>
        <label className="engine-module-picker">
          <span className="sr-only">Source module</span>
          <select
            value={
              shown.some((m) => `${m.package}.${m.name}` === selected)
                ? selected
                : ""
            }
            onChange={(e) => select(e.target.value)}
          >
            <option value="" disabled>
              {shown.length
                ? "Select a matching module"
                : "No matching modules"}
            </option>
            {shown.map((m) => (
              <option
                key={`${m.package}.${m.name}`}
                value={`${m.package}.${m.name}`}
              >
                {m.package}.{m.name}
              </option>
            ))}
          </select>
        </label>
        <div className="engine-module-reading" key={selected}>
          <header>
            <p className="research-micro">nisayon.{active.package}</p>
            <h2>{active.name.replaceAll("_", " ")}</h2>
          </header>
          <nav className="workspace-tabs" aria-label="Module details">
            {["Summary", "Entry points", "Identity"].map((s) => (
              <button
                key={s}
                aria-pressed={section === s}
                onClick={() => setSection(s)}
              >
                {s}
              </button>
            ))}
          </nav>
          <div className="module-detail">
            {section === "Summary" ? (
              <TextReading
                text={active.description || "No module docstring retained."}
                label="module description"
              />
            ) : null}
            {section === "Entry points" ? (
              <>
                <ul>
                  {active.entries
                    .slice(
                      entryPage * entriesPerPage,
                      (entryPage + 1) * entriesPerPage,
                    )
                    .map((e) => (
                      <li key={e.name}>
                        <code>{e.name}</code>
                        <span>
                          {e.kind} · line {e.line}
                        </span>
                      </li>
                    ))}
                </ul>
                {active.entries.length ? (
                  <Pages
                    page={entryPage}
                    count={Math.ceil(active.entries.length / entriesPerPage)}
                    onChange={setEntryPage}
                    label="entry points"
                  />
                ) : (
                  <p>No public top-level entry points.</p>
                )}
              </>
            ) : null}
            {section === "Identity" ? (
              <div className="module-source">
                <code>{active.source.path}</code>
                <p>SHA256</p>
                <code>{active.source.sha256}</code>
                <p>
                  {active.source.bytes.toLocaleString("en")} bytes · revision
                </p>
                <code>{revision}</code>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <footer className="engine-study-link">
        <p>
          A source module is not a validated capability. Tests and retained
          outcomes set that boundary.
        </p>
        <button className="research-text-action" onClick={onStudy}>
          Open retained Study ↗
        </button>
      </footer>
    </section>
  );
}
