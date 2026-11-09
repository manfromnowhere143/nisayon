// Measured, not claimed: first useful view and control response are recorded
// from real events and read back from the diagnostics panel or the console.

export interface InputSample {
  label: string;
  ms: number;
}

export class Metrics {
  firstUsefulViewMs: number | null = null;
  readonly inputs: InputSample[] = [];
  private pending: { label: string; t0: number } | null = null;
  private events = new Map<number, number>();
  private longTasks: number[] = [];
  private eventSupport = false;
  private taskSupport = false;

  observeBrowser(): () => void {
    if (typeof PerformanceObserver === "undefined") return () => {};
    const observers: PerformanceObserver[] = [];
    const supported = PerformanceObserver.supportedEntryTypes ?? [];
    if (supported.includes("event")) {
      const observer = new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          const id = (entry as PerformanceEntry & { interactionId?: number }).interactionId;
          if (!id || !Number.isFinite(entry.duration)) continue;
          this.events.set(id, Math.max(this.events.get(id) ?? 0, entry.duration));
          if (this.events.size > 2000) this.events.delete(this.events.keys().next().value!);
        }
      });
      try { observer.observe({ type: "event", buffered: true, durationThreshold: 16 } as PerformanceObserverInit); this.eventSupport = true; observers.push(observer); } catch { observer.disconnect(); }
    }
    if (supported.includes("longtask")) {
      const observer = new PerformanceObserver(list => { for (const entry of list.getEntries()) this.longTasks.push(entry.duration); if (this.longTasks.length > 2000) this.longTasks.splice(0, this.longTasks.length - 2000); });
      try { observer.observe({ type: "longtask", buffered: true }); this.taskSupport = true; observers.push(observer); } catch { observer.disconnect(); }
    }
    return () => { for (const observer of observers) observer.disconnect(); };
  }

  markInput(label: string): void {
    this.pending = { label, t0: performance.now() };
  }

  // Called after the DOM has committed the change that followed the input.
  commitInput(): void {
    if (!this.pending) return;
    const ms = performance.now() - this.pending.t0;
    this.inputs.push({ label: this.pending.label, ms });
    if (this.inputs.length > 2000) this.inputs.splice(0, this.inputs.length - 2000);
    this.pending = null;
  }

  markFirstUsefulView(): void {
    if (this.firstUsefulViewMs !== null) return;
    this.firstUsefulViewMs = performance.now();
    if (typeof performance.mark === "function") performance.mark("nisayon:first-useful-view");
  }

  summary() {
    const sorted = this.inputs.map((s) => s.ms).sort((a, b) => a - b);
    const at = (q: number): number | null => (sorted.length ? (sorted[Math.min(sorted.length - 1, Math.floor(q * (sorted.length - 1)))] as number) : null);
    const events = [...this.events.values()].sort((a, b) => a - b);
    return { firstUsefulViewMs: this.firstUsefulViewMs, n: sorted.length, p50: at(0.5), p95: at(0.95), max: sorted.length ? (sorted[sorted.length - 1] as number) : null,
      browserEvents: { supported: this.eventSupport, count: events.length, p95: events.length ? events[Math.floor((events.length - 1) * .95)]! : null, max: events.at(-1) ?? null },
      longTasks: { supported: this.taskSupport, count: this.longTasks.length, totalMs: this.longTasks.reduce((a, b) => a + b, 0), maxMs: this.longTasks.length ? Math.max(...this.longTasks) : null } };
  }
}
