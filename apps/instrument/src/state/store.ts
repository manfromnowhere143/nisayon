// The instrument's selection controller. One persistent moment, contextual
// depth, verified loads with stale-load cancellation, browser history and
// discrete playback. Nothing here alters evidence.

import { LoadError, ResourceCache, defaultOptions, openCase, openGeneration, openRun, type LoadIssue, type LoadStage, type LoadedRun, type LoaderOptions, type OpenedGeneration } from "../data/loader";
import { alignedRow, contextualFinding, pairedRun, timeForPhase } from "../model/findings";
import { openLibrary, type LibraryCase } from "../data/library";
import { sameRun, type CaseRecord, type Depth, type Generation, type Moment, type Phase, type RunKey, type RunRecord, type SampleRow } from "../model/types";
import type { SceneView } from "../scene/renderer";
import { Metrics } from "../perf/metrics";
import { playbackRow } from "../model/playback";
import { DEFAULT_EVIDENCE, INITIAL_EVIDENCE, formatLocator, parseLocator, type Locator } from "./locator";
import { initialStudyRoute, studyRouteParams, type StudyRoute } from "./studyRoute";
import { applyGround, readGround, type Ground } from "./ground";

export { readGround, type Ground } from "./ground";

export type Screen =
  | { kind: "loading"; stage: LoadStage; detail: string }
  | { kind: "error"; error: LoadError }
  | { kind: "invalid-locator"; problems: string[]; suggestion: { moment: Moment; depth: Depth } | null; label: string | null }
  | {
      kind: "ready";
      generation: Generation;
      caseRecord: CaseRecord;
      moment: Moment;
      depth: Depth;
      run: LoadedRun;
      ghost: LoadedRun | null;
      ghostIssue: LoadIssue | null;
      pendingRun: RunKey | null;
      notice: LoadIssue | null;
      selectionNote?: string;
      condition: string | null;
    };

export interface State {
  library: LibraryCase[];
  libraryIssue: string | null;
  libraryCheckedAt: number | null;
  libraryChecking: boolean;
  screen: Screen;
  initializing: boolean;
  pendingSelection: { caseKey: string | null; stage: LoadStage; detail: string } | null;
  selectionIssue: LoadIssue | null;
  evidenceUrl: string;
  inspector: boolean;
  playing: boolean;
  ground: Ground;
  reducedMotion: boolean;
  view: SceneView;
  sceneFocus: "workspace" | "grasp" | "lab";
  diagnostics: boolean;
  textScale: number;
  copied: "idle" | "copied" | "manual";
  lanesExpanded: boolean;
  part: { name: string; model: string } | null;
  partNote: string;
  study: StudyRoute | null;
}

type Listener = () => void;

export function rowAt(run: LoadedRun, rowIndex: number): SampleRow | null {
  return run.samples.rows[rowIndex] ?? null;
}

export class InstrumentStore {
  private state: State;
  private readonly listeners = new Set<Listener>();
  private readonly cache = new ResourceCache(16);
  private readonly generations = new ResourceCache(4);
  private readonly options: LoaderOptions;
  readonly metrics = new Metrics();
  private loadToken = 0;
  private controller: AbortController | null = null;
  private ghostToken = 0;
  private ghostController: AbortController | null = null;
  private playback: { raf: number; startedAt: number; startRow: number } | null = null;
  private urlTimer: number | null = null;
  private libraryController: AbortController | null = null;

  constructor(options: LoaderOptions = defaultOptions()) {
    this.options = options;
    const params = typeof location !== "undefined" ? new URLSearchParams(location.search) : new URLSearchParams();
    const text = Number(params.get("text") ?? "100");
    this.state = {
      library: [],
      libraryIssue: null,
      libraryCheckedAt: null,
      libraryChecking: false,
      screen: { kind: "loading", stage: "evidence", detail: "reading evidence" },
      initializing: true,
      pendingSelection: null,
      selectionIssue: null,
      evidenceUrl: DEFAULT_EVIDENCE,
      inspector: false,
      playing: false,
      ground: readGround(),
      reducedMotion: typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches,
      view: "three-quarter",
      sceneFocus: typeof matchMedia === "function" && matchMedia("(min-width: 1024px)").matches ? "lab" : "workspace",
      diagnostics: params.get("diag") === "1",
      textScale: Number.isFinite(text) && text >= 50 && text <= 400 ? text : 100,
      copied: "idle",
      lanesExpanded: false,
      part: null,
      partNote: "",
      study: parseLocator(typeof location === "undefined" ? "" : location.search).study,
    };
  }

  getState = (): State => this.state;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private set(patch: Partial<State>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener();
  }

  private setScreen(screen: Screen): void {
    this.set({ screen, ...(screen.kind !== "loading" ? { initializing: false } : {}) });
  }

  private ready(): Extract<Screen, { kind: "ready" }> | null {
    return this.state.screen.kind === "ready" ? this.state.screen : null;
  }

  // ---- loading -----------------------------------------------------------

  private beginLoad(): { token: number; signal: AbortSignal } {
    this.controller?.abort();
    this.ghostController?.abort();
    this.ghostToken += 1;
    this.controller = new AbortController();
    this.loadToken += 1;
    const ready = this.ready();
    this.set({ pendingSelection: null, selectionIssue: null, ...(ready ? { screen: { ...ready, pendingRun: null } } : {}) });
    return { token: this.loadToken, signal: this.controller.signal };
  }

  private current(token: number): boolean {
    return token === this.loadToken;
  }

  start(): void {
    void this.refreshLibrary();
    const locator = parseLocator(location.search);
    void this.open(locator, "replace");
  }

  async refreshLibrary(): Promise<void> {
    if (this.libraryController) return;
    const controller = new AbortController();
    this.libraryController = controller;
    this.set({ libraryChecking: true });
    try {
      const library = await openLibrary(this.options, controller.signal);
      if (!controller.signal.aborted) this.set({ library, libraryIssue: null, libraryCheckedAt: Date.now() });
    } catch (error) {
      if (!controller.signal.aborted) this.set({ libraryIssue: error instanceof Error ? error.message : String(error) });
    } finally {
      if (this.libraryController === controller) { this.libraryController = null; this.set({ libraryChecking: false }); }
    }
  }

  retry(): void {
    const locator = parseLocator(location.search);
    void this.open(locator, "replace");
  }

  setEvidence(url: string): void {
    const locator = parseLocator("");
    locator.evidence = url;
    void this.open(locator, "push");
  }

  async open(locator: Locator, historyMode: "push" | "replace"): Promise<void> {
    const retained = this.ready();
    const { token, signal } = this.beginLoad();
    this.pause();
    const evidenceUrl = locator.evidence ?? (locator.generation ? DEFAULT_EVIDENCE : INITIAL_EVIDENCE);
    // A new selection loads beside the verified selection. Commit its source,
    // identity, readings and URL together; never relabel the retained scene.
    if (!retained) this.set({ evidenceUrl });
    const loading = (stage: LoadStage, detail: string): void => {
      if (retained && this.ready()) this.set({ pendingSelection: { caseKey: locator.caseKey, stage, detail } });
      else this.setScreen({ kind: "loading", stage, detail });
    };
    if (locator.problems.length > 0) {
      this.setScreen({ kind: "invalid-locator", problems: locator.problems, suggestion: null, label: null });
    } else {
      loading("evidence", "reading evidence");
    }
    try {
      const generationKey = (sha: string) => `${new URL(evidenceUrl, location.href).href}#${sha}`;
      // Only an already verified immutable pin can skip another manifest fetch.
      // Unpinned discovery and new catalog generations still take the full path.
      const opened = (locator.generation ? this.generations.get<OpenedGeneration>(generationKey(locator.generation)) : undefined) ?? await openGeneration(evidenceUrl, signal, this.options, locator.generation);
      if (!this.current(token)) return;
      const { generation } = opened;
      this.generations.set(generationKey(generation.sha256), opened);
      const problems = [...locator.problems];
      if (locator.generation !== null && locator.generation !== generation.sha256) {
        problems.push(`the link pins generation ${locator.generation.slice(0, 8)}…; the current evidence resolves to ${generation.sha256.slice(0, 8)}…`);
      }
      loading("case", "verifying case record");
      const caseKey = locator.caseKey ?? generation.cases[0]!.case_key;
      let caseRecord: CaseRecord;
      try {
        caseRecord = await openCase(generation, caseKey, signal, this.options, this.cache);
      } catch (error) {
        if (!this.current(token)) return;
        if (error instanceof LoadError && error.issue.kind === "absent" && locator.caseKey !== null) {
          problems.push(error.issue.message);
          caseRecord = await openCase(generation, generation.cases[0]!.case_key, signal, this.options, this.cache);
        } else throw error;
      }
      if (!this.current(token)) return;
      const defaultRun = caseRecord.runs.find((r) => r.role === "regression") ?? caseRecord.runs[0]!;
      let runRecord: RunRecord = defaultRun;
      if (locator.run !== null) {
        const found = caseRecord.runs.find((r) => sameRun(r.run, locator.run!));
        if (found) runRecord = found;
        else problems.push(`run "${locator.run.run_id}" of bundle ${locator.run.bundle_sha256.slice(0, 8)}… is not in case "${caseRecord.case_key}"`);
      }
      loading("run", `verifying ${runRecord.run.run_id}`);
      const transfers = new Map<string, { loaded: number; total: number | null }>();
      let reported = 0;
      const run = await openRun(generation, caseRecord, runRecord.run, signal, {
        ...this.options,
        onProgress: (progress) => {
          this.options.onProgress?.(progress);
          if (!this.current(token)) return;
          transfers.set(progress.url, progress);
          const now = performance.now();
          if (now - reported < 100 && progress.loaded !== progress.total) return;
          reported = now;
          const loaded = [...transfers.values()].reduce((sum, item) => sum + item.loaded, 0);
          const total = runRecord.samples.byte_length + (runRecord.model?.byte_length ?? 0) + (runRecord.frames?.byte_length ?? 0);
          loading("run", loaded < total
            ? `Loading ${runRecord.run.run_id} · ${Math.min(99, Math.floor(100 * loaded / total))}%`
            : `Verifying ${runRecord.run.run_id}`);
        },
      }, this.cache);
      if (!this.current(token)) return;
      const finding = contextualFinding(caseRecord, run.record, run.samples.rows);
      const defaultRow = finding.row ?? 0;
      const suggestion: Moment = {
        generation_sha256: generation.sha256,
        case_key: caseRecord.case_key,
        run: runRecord.run,
        row_index: defaultRow,
        phase: "after",
        clock: "simulation",
      };
      let row = defaultRow;
      if (locator.row !== null) {
        if (locator.row < runRecord.row_count) row = locator.row;
        else problems.push(`row ${locator.row} is outside ${runRecord.run.run_id}, which has rows 0 to ${runRecord.row_count - 1}`);
      }
      if (problems.length > 0) {
        this.set({ evidenceUrl, pendingSelection: null });
        this.setScreen({ kind: "invalid-locator", problems, suggestion: { moment: suggestion, depth: "moment" }, label: generation.label });
        return;
      }
      const moment: Moment = { ...suggestion, row_index: row, phase: locator.phase ?? "after" };
      const depth = locator.depth ?? "moment";
      // Playback may have been resumed on the retained view while this loaded.
      // Its clock and row limit belong to that recording, not the incoming one.
      this.pause();
      this.set({ evidenceUrl, study: locator.study, pendingSelection: null, selectionIssue: null, initializing: false, ...this.resolvePart(locator.part, locator.partModel, run), screen: { kind: "ready", generation, caseRecord, moment, depth, run, ghost: null, ghostIssue: null, pendingRun: null, notice: null, condition: locator.condition } });
      this.syncUrl(historyMode);
      if (depth === "fork") this.ensureGhost();
    } catch (error) {
      if (!this.current(token)) return;
      const failure = error instanceof LoadError ? error : new LoadError("evidence", { kind: "network", url: evidenceUrl, message: error instanceof Error ? error.message : String(error), expected: null, actual: null });
      if (failure.issue.kind === "aborted") return;
      if (retained && this.ready()) {
        this.set({ pendingSelection: null, selectionIssue: failure.issue });
        if (historyMode === "replace") this.syncUrl("replace");
      } else {
        this.set({ pendingSelection: null });
        this.setScreen({ kind: "error", error: failure });
      }
    }
  }

  clearSelectionIssue(): void {
    this.set({ selectionIssue: null });
  }

  openSuggestion(): void {
    const screen = this.state.screen;
    if (screen.kind !== "invalid-locator" || !screen.suggestion) return;
    const { moment, depth } = screen.suggestion;
    const locator = parseLocator(formatLocator(moment, depth, this.state.evidenceUrl));
    void this.open(locator, "push");
  }

  private ensureGhost(): void {
    const screen = this.ready();
    if (!screen) return;
    const paired = pairedRun(screen.caseRecord, screen.run.record);
    if (!paired) {
      this.setScreen({ ...screen, ghost: null, ghostIssue: { kind: "absent", url: screen.generation.manifestUrl, message: "no paired run in this case", expected: null, actual: null } });
      return;
    }
    if (screen.ghost && sameRun(screen.ghost.record.run, paired.run)) return;
    this.ghostController?.abort();
    this.ghostController = new AbortController();
    this.ghostToken += 1;
    const token = this.ghostToken;
    const { generation, caseRecord } = screen;
    void openRun(generation, caseRecord, paired.run, this.ghostController.signal, this.options, this.cache)
      .then((ghost) => {
        const now = this.ready();
        if (token !== this.ghostToken || !now || now.generation !== generation || !sameRun(now.moment.run, screen.moment.run)) return;
        this.setScreen({ ...now, ghost, ghostIssue: null });
      })
      .catch((error: unknown) => {
        const now = this.ready();
        if (token !== this.ghostToken || !now) return;
        if (error instanceof LoadError && error.issue.kind !== "aborted") this.setScreen({ ...now, ghost: null, ghostIssue: error.issue });
      });
  }

  // ---- selection ---------------------------------------------------------

  private resolvePart(name: string | null, model: string | null, run: LoadedRun): Pick<State, "part" | "partNote"> {
    if (name === null) return { part: null, partNote: "" };
    if (!run.model || !run.record.model || (model !== null && model !== run.record.model.sha256) || !run.model.bodies.some((body) => body.name === name)) {
      return { part: null, partNote: `Part selection cleared: ${name} is not bound to this model.` };
    }
    return { part: { name, model: run.record.model.sha256 }, partNote: "" };
  }

  selectPart(name: string | null, depth?: Depth): void {
    const screen = this.ready();
    if (!screen) return;
    this.pause();
    this.set({ ...this.resolvePart(name, screen.run.record.model?.sha256 ?? null, screen.run), screen: { ...screen, depth: depth ?? screen.depth } });
    this.syncUrl("push");
  }

  private updateMoment(patch: Partial<Moment>, historyMode: "push" | "replace" | "coalesce" | "none"): void {
    const screen = this.ready();
    if (!screen) return;
    this.setScreen({ ...screen, selectionNote: "", moment: { ...screen.moment, ...patch } });
    if (historyMode !== "none") this.syncUrl(historyMode);
  }

  setRow(rowIndex: number, historyMode: "push" | "replace" | "coalesce" | "none" = "coalesce"): void {
    const screen = this.ready();
    if (!screen) return;
    const last = screen.run.record.row_count - 1;
    const next = Math.max(0, Math.min(last, Math.round(rowIndex)));
    if (next === screen.moment.row_index) return;
    this.metrics.markInput("row");
    this.updateMoment({ row_index: next }, historyMode);
  }

  stepRow(delta: number): void {
    const screen = this.ready();
    if (!screen) return;
    this.pause();
    const last = screen.run.record.row_count - 1;
    const from = Math.min(screen.moment.row_index, last);
    this.setRow(from + delta, "replace");
  }

  // A signal selection commits its sample and physical phase together. Keeping
  // these separate can briefly expose a value with the previous frame/URL.
  selectSample(rowIndex: number, phase: Phase): void {
    const screen = this.ready();
    if (!screen || !Number.isFinite(rowIndex)) return;
    this.pause();
    const row = Math.max(0, Math.min(screen.run.record.row_count - 1, Math.round(rowIndex)));
    this.metrics.markInput("row");
    this.updateMoment({ row_index: row, phase }, "replace");
  }

  goToLastRow(): void {
    const screen = this.ready();
    if (!screen) return;
    this.setRow(screen.run.record.row_count - 1, "replace");
  }

  setPhase(phase: Phase): void {
    const screen = this.ready();
    if (!screen || screen.moment.phase === phase) return;
    this.pause();
    this.metrics.markInput("phase");
    this.updateMoment({ phase }, "replace");
  }

  togglePhase(): void {
    const screen = this.ready();
    if (!screen) return;
    this.setPhase(screen.moment.phase === "before" ? "after" : "before");
  }

  jumpToFinding(): void {
    const screen = this.ready();
    if (!screen) return;
    const finding = contextualFinding(screen.caseRecord, screen.run.record, screen.run.samples.rows);
    if (finding.row === null) return;
    this.pause();
    this.metrics.markInput("mismatch");
    this.updateMoment({ row_index: finding.row }, "push");
  }

  selectRun(runKey: RunKey, fromCondition = false): void {
    const screen = this.ready();
    if (!screen || sameRun(screen.moment.run, runKey)) return;
    const record = screen.caseRecord.runs.find((r) => sameRun(r.run, runKey));
    if (!record) return;
    this.pause();
    this.metrics.markInput("run");
    const { token, signal } = this.beginLoad();
    this.setScreen({ ...screen, pendingRun: runKey, notice: null });
    void openRun(screen.generation, screen.caseRecord, runKey, signal, this.options, this.cache)
      .then((run) => {
        const now = this.ready();
        if (!this.current(token) || !now) return;
        const selected = rowAt(now.run, now.moment.row_index);
        const aligned = fromCondition ? run.samples.rows[0] : alignedRow(selected, run.samples.rows, now.moment.phase);
        const time = selected ? timeForPhase(selected, now.moment.phase) : 0;
        const fallback = run.samples.rows.filter((row) => timeForPhase(row, now.moment.phase) <= time).at(-1) ?? run.samples.rows[0]!;
        const next = aligned ?? fallback;
        const selectionNote = aligned ? "" : `No sample at ${time.toFixed(2)} s in ${runKey.run_id}. Showing its recorded sample at ${timeForPhase(next, now.moment.phase).toFixed(2)} s.`;
        this.set({ ...this.resolvePart(this.state.part?.name ?? null, this.state.part?.model ?? null, run), screen: { ...now, run, moment: { ...now.moment, run: runKey, row_index: next.row_index }, selectionNote, depth: fromCondition ? "fork" : now.depth, pendingRun: null, notice: null, ghost: null } });
        this.syncUrl("push");
        if (fromCondition || now.depth === "fork") this.ensureGhost();
      })
      .catch((error: unknown) => {
        const now = this.ready();
        if (!this.current(token) || !now) return;
        if (error instanceof LoadError && error.issue.kind !== "aborted") this.setScreen({ ...now, pendingRun: null, notice: error.issue });
      });
  }

  cycleRun(): void {
    const screen = this.ready();
    if (!screen) return;
    const runs = screen.caseRecord.runs;
    const index = runs.findIndex((r) => sameRun(r.run, screen.moment.run));
    const next = runs[(index + 1) % runs.length];
    if (next) this.selectRun(next.run);
  }

  setDepth(depth: Depth): void {
    const screen = this.ready();
    if (!screen || screen.depth === depth) return;
    this.pause();
    this.metrics.markInput("depth");
    this.setScreen({ ...screen, depth, condition: depth === "conditions" ? screen.condition : null });
    this.syncUrl("push");
    if (depth === "fork") this.ensureGhost();
  }

  // An explicit condition selection is a selection change with its own history
  // entry; Back returns to the field with the same moment.
  selectCondition(condition: string | null): void {
    const screen = this.ready();
    if (!screen || screen.condition === condition) return;
    this.metrics.markInput("condition");
    this.setScreen({ ...screen, condition });
    this.syncUrl("push");
  }

  // Another case in the same generation: a new default moment, pinned like any other.
  selectCase(caseKey: string): void {
    const screen = this.ready();
    if (!screen || screen.caseRecord.case_key === caseKey) return;
    if (!screen.generation.cases.some((c) => c.case_key === caseKey)) return;
    this.metrics.markInput("case");
    const locator = parseLocator("");
    locator.evidence = this.state.evidenceUrl;
    locator.caseKey = caseKey;
    void this.open(locator, "push");
  }

  selectLibraryCase(caseKey: string): void {
    const entry = this.state.library.find((c) => c.caseKey === caseKey);
    if (!entry) return;
    const current = this.ready();
    if (current?.caseRecord.case_key === caseKey && current.generation.sha256 === entry.generation) {
      if (this.state.pendingSelection) { this.beginLoad(); if (current.depth === "fork") this.ensureGhost(); }
      return;
    }
    this.metrics.markInput("case");
    const locator = parseLocator("");
    locator.evidence = entry.evidence;
    locator.caseKey = entry.caseKey;
    locator.generation = entry.generation;
    void this.open(locator, "push");
  }

  toggleLanes(): void {
    this.metrics.markInput("lanes");
    this.set({ lanesExpanded: !this.state.lanesExpanded });
  }

  // Back returns to the parent depth, keeping the same moment. Escape closes
  // the inspector first.
  back(): void {
    const screen = this.ready();
    if (!screen) return;
    if (this.state.inspector) {
      this.toggleInspector(false);
      return;
    }
    if (screen.depth !== "moment") history.back();
  }

  handlePopState(): void {
    const locator = parseLocator(location.search);
    this.set({ study: locator.study });
    const screen = this.ready();
    if (screen && (locator.evidence ?? DEFAULT_EVIDENCE) === this.state.evidenceUrl && locator.problems.length === 0 && locator.generation === screen.generation.sha256 && locator.caseKey === screen.caseRecord.case_key && locator.run !== null) {
      const sameRunSelected = sameRun(locator.run, screen.moment.run);
      const row = locator.row ?? screen.moment.row_index;
      const target = screen.caseRecord.runs.find((r) => sameRun(r.run, locator.run!));
      if (!target || row >= target.row_count) {
        void this.open(locator, "replace");
        return;
      }
      const phase = locator.phase ?? screen.moment.phase;
      const depth = locator.depth ?? "moment";
      this.pause();
      if (sameRunSelected) {
        this.beginLoad();
        this.set({ ...this.resolvePart(locator.part, locator.partModel, screen.run), screen: { ...screen, pendingRun: null, moment: { ...screen.moment, row_index: row, phase }, depth, condition: locator.condition } });
        if (depth === "fork") this.ensureGhost();
        return;
      }
      const runKey = locator.run;
      const { token, signal } = this.beginLoad();
      this.setScreen({ ...screen, pendingRun: runKey, depth });
      void openRun(screen.generation, screen.caseRecord, runKey, signal, this.options, this.cache)
        .then((run) => {
          const now = this.ready();
          if (!this.current(token) || !now) return;
          this.set({ ...this.resolvePart(locator.part, locator.partModel, run), screen: { ...now, run, moment: { ...now.moment, run: runKey, row_index: row, phase }, pendingRun: null, ghost: null, condition: locator.condition } });
          if (depth === "fork") this.ensureGhost();
        })
        .catch((error: unknown) => {
          const now = this.ready();
          if (!this.current(token) || !now) return;
          if (error instanceof LoadError && error.issue.kind !== "aborted") this.setScreen({ ...now, pendingRun: null, notice: error.issue });
        });
      return;
    }
    void this.open(locator, "replace");
  }

  private urlExtra(): Record<string, string> {
    const extra: Record<string, string> = studyRouteParams(this.state.study);
    if (this.state.diagnostics) extra.diag = "1";
    if (this.state.textScale !== 100) extra.text = String(this.state.textScale);
    if (this.state.part) { extra.part = this.state.part.name; extra.pm = this.state.part.model; }
    return extra;
  }

  // "push" records a history entry (depth, run, explicit jumps); "replace"
  // rewrites the current entry at once; "coalesce" rewrites it after a short
  // pause so scrubbing and playback do not thrash the address bar.
  private syncUrl(mode: "push" | "replace" | "coalesce"): void {
    const screen = this.ready();
    if (!screen) return;
    if (this.urlTimer !== null) {
      clearTimeout(this.urlTimer);
      this.urlTimer = null;
    }
    const write = (): void => {
      const now = this.ready();
      if (!now) return;
      const url = formatLocator(now.moment, now.depth, this.state.evidenceUrl, this.urlExtra(), now.condition) + location.hash;
      if (mode === "push") history.pushState({ nisayon: true }, "", url);
      else history.replaceState({ nisayon: true }, "", url);
    };
    if (mode === "coalesce") {
      this.urlTimer = window.setTimeout(() => {
        this.urlTimer = null;
        write();
      }, 120);
    } else {
      write();
    }
  }

  currentUrl(): string {
    const screen = this.ready();
    if (!screen) return location.href;
    const extra = { ...studyRouteParams(this.state.study), ...(this.state.part ? { part: this.state.part.name, pm: this.state.part.model } : {}) };
    return new URL(formatLocator(screen.moment, screen.depth, this.state.evidenceUrl, extra, screen.condition), location.href).href;
  }

  async copyLink(): Promise<void> {
    const url = this.currentUrl();
    try {
      await navigator.clipboard.writeText(url);
      this.set({ copied: "copied" });
    } catch {
      this.set({ copied: "manual" });
    }
    window.setTimeout(() => this.set({ copied: "idle" }), 2400);
  }

  setStudy(route: StudyRoute, mode: "push" | "replace" = "push"): void {
    this.pause();
    this.set({ study: route });
    this.syncUrl(mode);
  }

  openStudy(): void {
    this.setStudy({ ...(this.state.study ?? initialStudyRoute(this.ready()?.caseRecord.case_key)), open: true });
  }

  closeStudy(): void {
    if (this.state.study) this.setStudy({ ...this.state.study, open: false });
  }

  openStudyScene(url: string): void {
    const locator = parseLocator(new URL(url, location.href).search);
    locator.study = this.state.study ? { ...this.state.study, open: false } : null;
    void this.open(locator, "push");
  }

  // ---- playback ------------------------------------------------------------

  play(): void {
    const screen = this.ready();
    if (!screen || this.playback) return;
    const last = screen.run.record.row_count - 1;
    if (screen.moment.row_index >= last) return;
    this.metrics.markInput("play");
    const phase = screen.moment.phase;
    const rows = screen.run.samples.rows;
    const startedAt = performance.now();
    const startRow = screen.moment.row_index;
    const tick = (): void => {
      const now = this.ready();
      if (!now || !this.playback) return;
      const elapsed = (performance.now() - this.playback.startedAt) / 1000;
      const target = playbackRow(rows, phase, this.playback.startRow, elapsed);
      if (target !== now.moment.row_index) this.updateMoment({ row_index: target }, "none");
      if (target >= last) {
        this.pause();
        return;
      }
      this.playback.raf = requestAnimationFrame(tick);
    };
    this.playback = { raf: requestAnimationFrame(tick), startedAt, startRow };
    this.set({ playing: true });
  }

  pause(): void {
    if (!this.playback) return;
    cancelAnimationFrame(this.playback.raf);
    this.playback = null;
    this.set({ playing: false });
    this.syncUrl("replace");
  }

  togglePlay(): void {
    if (this.playback) this.pause();
    else this.play();
  }

  // ---- view state ----------------------------------------------------------

  toggleInspector(open?: boolean): void {
    const next = open ?? !this.state.inspector;
    if (next === this.state.inspector) return;
    this.metrics.markInput("inspector");
    this.set({ inspector: next });
  }

  setGround(ground: Ground): void {
    if (ground === this.state.ground) return;
    this.metrics.markInput("ground");
    applyGround(ground);
    this.set({ ground });
  }

  toggleGround(): void {
    this.setGround(this.state.ground === "black" ? "paper" : "black");
  }

  setReducedMotion(reducedMotion: boolean): void {
    if (reducedMotion !== this.state.reducedMotion) this.set({ reducedMotion });
  }

  setView(view: SceneView): void {
    if (view === this.state.view) return;
    this.metrics.markInput("view");
    this.set({ view });
  }

  setSceneFocus(sceneFocus: "workspace" | "grasp" | "lab"): void {
    if (sceneFocus === this.state.sceneFocus) return;
    this.metrics.markInput("scene-focus");
    this.set({ sceneFocus });
  }

  toggleDiagnostics(): void {
    this.set({ diagnostics: !this.state.diagnostics });
  }

  clearNotice(): void {
    const screen = this.ready();
    if (screen && screen.notice) this.setScreen({ ...screen, notice: null });
  }

  cacheSize(): number {
    return this.cache.size;
  }

  dispose(): void {
    this.pause();
    this.controller?.abort();
    this.ghostController?.abort();
    this.loadToken += 1;
    this.ghostToken += 1;
    if (this.urlTimer !== null) window.clearTimeout(this.urlTimer);
    this.urlTimer = null;
    this.libraryController?.abort();
    this.libraryController = null;
    this.cache.clear();
    this.generations.clear();
  }
}
