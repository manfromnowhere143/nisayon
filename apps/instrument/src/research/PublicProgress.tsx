import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { GlassCard } from "./GlassCard";
import { UpstreamLine } from "./UpstreamLine";
import { Pages } from "./WorkspaceControls";
import type { ResearchCatalog } from "./catalog";
import { createProgressClient, REFRESH_MS, SAVED_PROGRESS, STATUS_LABEL, type ProgressRecord, type ProgressSnapshot } from "./progress";
import seed from "./progressSeed.json";
import { EvidenceFlow } from "../ui/EvidenceFlow";

const software: ProgressRecord[] = [
  { id: "portable-review", title: "Portable review · carry the complete evidence", repository: "Nisayon SDK", status: "available", date: "2026-10-22", updatedAt: "2026-10-22T00:00:00Z", observedAt: seed.checkedAt, url: "/portable-review/", kind: "software" },
  { id: "native-qualification", title: "Native qualification · freeze, run and inspect", repository: "Nisayon SDK", status: "available", date: "2026-10-22", updatedAt: "2026-10-22T00:00:00Z", observedAt: seed.checkedAt, url: "/sdk/", kind: "software" },
];
let client: ReturnType<typeof createProgressClient> | undefined;
const shipped = (row: ProgressRecord) => ["merged", "released", "available"].includes(row.status);
const reviewing = (row: ProgressRecord) => row.status === "open" || row.status === "draft";
const readableTime = (value: string) => new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));

export function PublicProgress({ retained = [] }: { retained: ResearchCatalog["upstream"] }) {
  const [snapshot, setSnapshot] = useState<ProgressSnapshot>(() => client?.current() ?? SAVED_PROGRESS);
  const [opened, setOpened] = useState(false);
  useEffect(() => {
    let disposed = false;
    client ??= createProgressClient();
    const refresh = async () => {
      if (document.hidden) return;
      const value = await client!.refresh();
      if (!disposed) setSnapshot(value);
    };
    void refresh();
    document.addEventListener("visibilitychange", refresh);
    const interval = window.setInterval(refresh, REFRESH_MS);
    return () => { disposed = true; clearInterval(interval); document.removeEventListener("visibilitychange", refresh); };
  }, []);
  const records: ProgressRecord[] = [
    ...snapshot.records,
    ...software,
    ...retained.map(row => ({ ...row, id: row.url, repository: row.title.split(" · ")[0]!, updatedAt: `${row.date}T12:00:00Z`, observedAt: `${row.date}T12:00:00Z`, kind: "adoption" as const })),
  ].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return <>
    <UpstreamLine records={records} onOpen={() => setOpened(true)} />
    {opened ? <ProgressReading records={records} snapshot={snapshot} onClose={() => setOpened(false)} /> : null}
  </>;
}

function ProgressReading({ records: incoming, snapshot, onClose }: { records: ProgressRecord[]; snapshot: ProgressSnapshot; onClose: () => void }) {
  // Keep the page under inspection stable until it is reopened.
  const [records] = useState(incoming), [observed] = useState(snapshot);
  const [tab, setTab] = useState("All"), [requestedPage, setPage] = useState(0);
  const [perPage, setPerPage] = useState(2);
  const list = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (!list.current) return;
    const resize = () => {
      const height = list.current?.clientHeight ?? 0;
      if (height) setPerPage(Math.max(1, Math.min(4, Math.floor(height / 116))));
    };
    const observer = new ResizeObserver(resize); observer.observe(list.current); resize();
    return () => observer.disconnect();
  }, [tab]);
  const selected = records.filter(row => tab === "Available" ? shipped(row) : tab === "In review" ? reviewing(row) : true);
  const pages = Math.max(1, Math.ceil(selected.length / perPage)), page = Math.min(requestedPage, pages - 1);
  return <GlassCard title="Progress, with the evidence." eyebrow="NISAYON / PUBLIC WORK" onClose={onClose}>
    <div className="progress-reading">
      <nav className="workspace-tabs progress-tabs" aria-label="Progress filters">
        {["All", "Available", "In review", "Sources"].map(name => <button key={name} aria-pressed={name === tab} onClick={() => { setTab(name); setPage(0); }}>{name}{name !== "Sources" ? <span>{records.filter(row => name === "Available" ? shipped(row) : name === "In review" ? reviewing(row) : true).length}</span> : null}</button>)}
      </nav>
      {tab === "Sources" ? <EvidenceFlow label="Progress sources"><div className="progress-scope">
        <p>New public pull requests by Daniel in {seed.repositories.length} registered Nisayon repositories are discovered automatically. Open and draft work remains in review. Closed does not mean merged.</p>
        <p>GitHub status refreshes every 15 minutes while Library is visible. Search can be delayed or incomplete. Saved records remain available during an outage.</p>
        <p>Release and adoption examples retain their original evidence dates. Scientific results remain bound to their recorded source; a status update cannot change them.</p>
        <p className="progress-freshness">Last successful search: {readableTime(observed.checkedAt)}.{observed.partial ? " GitHub reported a partial result." : ""} {observed.connection !== "current" ? "Showing saved records." : ""}</p>
      </div></EvidenceFlow> : <>
        <div className="progress-list" ref={list}>
          {selected.slice(page * perPage, (page + 1) * perPage).map(row => <a className="progress-entry" key={row.id} href={row.url} target="_blank" rel="noopener noreferrer" title={row.title}>
            <span className="progress-entry-meta"><span>{row.repository}</span><time dateTime={row.date}>{row.date}</time></span>
            <strong>{row.title}</strong>
            <span className={`progress-entry-status progress-${row.status}`}>{STATUS_LABEL[row.status]} <span aria-hidden="true">↗</span></span>
          </a>)}
          {selected.length === 0 ? <p>No records in this selection.</p> : null}
        </div>
        <footer className="progress-footer"><span className="progress-freshness">{observed.connection === "current" ? "GitHub checked" : "Saved record"} · {readableTime(observed.checkedAt)}</span><Pages page={page} count={pages} onChange={setPage} label="progress records" /></footer>
      </>}
    </div>
  </GlassCard>;
}
