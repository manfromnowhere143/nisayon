import seed from "./progressSeed.json";
import { transferBytes } from "../data/transfer";
import { strictParseJson } from "../data/strictJson";

export type ProgressStatus = "merged" | "released" | "available" | "open" | "draft" | "closed";
export interface ProgressRecord {
  id: string; url: string; repository: string; title: string;
  status: ProgressStatus; date: string; updatedAt: string; observedAt: string;
  kind: "contribution" | "adoption" | "software";
}
export interface ProgressSnapshot {
  records: ProgressRecord[];
  checkedAt: string;
  partial: boolean;
  connection: "saved" | "current" | "unavailable";
}
export const REFRESH_MS = 15 * 60_000;
export const STATUS_LABEL: Record<ProgressStatus, string> = {
  merged: "Merged", released: "Released", available: "Available locally",
  open: "Open PR", draft: "Draft PR", closed: "Closed, not merged",
};
const repositories = new Map(seed.repositories.map(name => [name.toLowerCase(), name]));
const query = `is:pr author:${seed.account} created:>=${seed.since} ${seed.repositories.map(repo => `repo:${repo}`).join(" ")}`;
export const PROGRESS_URL = `https://api.github.com/search/issues?${new URLSearchParams({ q: query, sort: "updated", order: "desc", per_page: "100" })}`;
export const SAVED_PROGRESS: ProgressSnapshot = {
  records: seed.records.map(row => ({ ...row, observedAt: seed.checkedAt })) as ProgressRecord[],
  checkedAt: seed.checkedAt, partial: false, connection: "saved",
};
const record = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid public progress response");
  return value as Record<string, unknown>;
};
const timestamp = (value: unknown): string => {
  if (typeof value !== "string" || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(value) || !Number.isFinite(Date.parse(value))) throw new Error("Invalid public progress date");
  return value;
};

/** GitHub metadata is activity, never validation of the underlying correction.
 * A closed PR is not merged. Each merge requires an actual merged_at field. */
export function decodeProgress(value: unknown, observedAt: string): ProgressSnapshot {
  const root = record(value);
  if (!Array.isArray(root.items) || root.items.length > 100 || typeof root.incomplete_results !== "boolean" || !Number.isSafeInteger(root.total_count) || Number(root.total_count) < root.items.length) throw new Error("Incomplete public progress envelope");
  const records: ProgressRecord[] = [], seen = new Set<string>();
  for (const item of root.items) {
    const row = record(item);
    const user = record(row.user), pr = record(row.pull_request);
    const repo = typeof row.repository_url === "string" ? row.repository_url.replace("https://api.github.com/repos/", "") : "";
    const repository = repositories.get(repo.toLowerCase());
    if (!repository || user.login !== seed.account) continue;
    if (!Number.isSafeInteger(row.number) || Number(row.number) < 1) throw new Error("Invalid public contribution number");
    const url = `https://github.com/${repo}/pull/${row.number}`;
    if (row.repository_url !== `https://api.github.com/repos/${repo}` || row.html_url !== url || pr.html_url !== url || pr.url !== `https://api.github.com/repos/${repo}/pulls/${row.number}` || seen.has(url.toLowerCase())) throw new Error("Public contribution identity mismatch");
    if (row.state !== "open" && row.state !== "closed") throw new Error("Unknown contribution state");
    if (typeof row.draft !== "boolean" || typeof row.title !== "string" || !row.title.trim() || row.title.length > 512 || /[\u0000-\u001f]/.test(row.title)) throw new Error("Invalid contribution metadata");
    const updatedAt = timestamp(row.updated_at);
    // Missing merge metadata cannot silently become either a merge or a rejection.
    const mergedAt = pr.merged_at === null ? null : timestamp(pr.merged_at);
    if (mergedAt && (row.state !== "closed" || row.draft)) throw new Error("Conflicting merge state");
    const status: ProgressStatus = mergedAt ? "merged" : row.state === "closed" ? "closed" : row.draft ? "draft" : "open";
    seen.add(url.toLowerCase());
    records.push({ id: url, url, repository, title: row.title, status, updatedAt, observedAt, date: (mergedAt ?? updatedAt).slice(0, 10), kind: "contribution" });
  }
  return { records, checkedAt: observedAt, partial: root.incomplete_results || Number(root.total_count) > root.items.length, connection: "current" };
}

/** Search can omit indexed records. Absence never erases a retained result. */
export function mergeProgress(previous: ProgressSnapshot, current: ProgressSnapshot): ProgressSnapshot {
  const rows = new Map(previous.records.map(row => [row.id.toLowerCase(), row]));
  for (const row of current.records) {
    const old = rows.get(row.id.toLowerCase());
    if (!old || row.updatedAt >= old.updatedAt) rows.set(row.id.toLowerCase(), row);
  }
  return { ...current, records: [...rows.values()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, 200) };
}

/** One public GET per visible interval. No credentials, private review bytes,
 * background polling, or requests to URLs supplied by a remote response. */
export function createProgressClient(fetcher: typeof fetch = fetch, now = () => Date.now()) {
  let snapshot = SAVED_PROGRESS;
  let nextRead = 0, etag = "", pending: Promise<ProgressSnapshot> | null = null;
  const storageKey = `nisayon:progress:${seed.source.registrySha256}:${seed.source.readbackSha256}`;
  // Store the raw bounded search envelope so every cached entry is revalidated.
  let savedBody = "";
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw && raw.length < 600_000) {
      const saved = record(JSON.parse(raw));
      if (typeof saved.body === "string" && typeof saved.at === "number" && saved.at <= now() && now() - saved.at < REFRESH_MS) {
        snapshot = mergeProgress(snapshot, decodeProgress(strictParseJson(saved.body), new Date(saved.at).toISOString()));
        nextRead = saved.at + REFRESH_MS; savedBody = saved.body;
        if (typeof saved.etag === "string" && saved.etag.length < 200) etag = saved.etag;
      }
    }
  } catch { /* Storage can be unavailable; the compiled public snapshot remains. */ }
  return {
    current: () => snapshot,
    refresh(): Promise<ProgressSnapshot> {
      if (pending) return pending;
      if (now() < nextRead) return Promise.resolve(snapshot);
      nextRead = now() + REFRESH_MS;
      pending = (async () => {
        let unchanged = false, nextEtag = "";
        try {
          const bytes = await transferBytes(PROGRESS_URL, async (url, { signal }) => {
            const headers: Record<string, string> = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10" };
            if (etag) headers["If-None-Match"] = etag;
            const response = await fetcher(url, { method: "GET", signal, headers, credentials: "omit", referrerPolicy: "no-referrer", redirect: "error", cache: "no-store" });
            if (response.status === 304 && savedBody) { unchanged = true; return new Response("{}"); }
            if (response.status === 403 || response.status === 429) {
              const retry = Number(response.headers.get("Retry-After")), reset = Number(response.headers.get("X-RateLimit-Reset"));
              nextRead = Math.max(nextRead, Number.isFinite(retry) ? now() + Math.min(retry, 86400) * 1000 : 0, Number.isFinite(reset) ? Math.min(reset * 1000, now() + 86400_000) : 0);
            }
            nextEtag = response.headers.get("ETag") ?? "";
            return response;
          }, { maxBytes: 512_000, timeoutMs: 10_000, stallTimeoutMs: 8_000 });
          const body = unchanged ? savedBody : new TextDecoder("utf-8", { fatal: true }).decode(bytes);
          const observed = now();
          snapshot = mergeProgress(snapshot, decodeProgress(strictParseJson(body), new Date(observed).toISOString()));
          savedBody = body;
          if (!unchanged) etag = nextEtag.length < 200 ? nextEtag : "";
          try { sessionStorage.setItem(storageKey, JSON.stringify({ at: observed, body, etag })); } catch { /* optional */ }
        } catch {
          snapshot = { ...snapshot, connection: "unavailable" };
        }
        return snapshot;
      })().finally(() => { pending = null; });
      return pending;
    },
  };
}
