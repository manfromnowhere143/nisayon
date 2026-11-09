// Measured numbers only. Opens with ?diag=1 or the D key.

import { EvidenceFlow } from "./EvidenceFlow";
import { useEffect, useState } from "react";
import type { SceneHandle } from "../scene/renderer";
import { DEFAULT_EVIDENCE } from "../state/locator";
import { useInstrumentState, useStore } from "../state/useStore";

interface Props {
  scene: SceneHandle | null;
}

const VARIANTS = [
  ["default", DEFAULT_EVIDENCE],
  ["corrupt child", "dev-fixture-corrupt-child/evidence.json"],
  ["wrong root", "dev-fixture-wrong-root/evidence.json"],
  ["missing frames", "dev-fixture-missing-frames/evidence.json"],
  ["unknown schema", "dev-fixture-unknown-schema/evidence.json"],
  ["absent", "dev-fixture-absent/evidence.json"],
] as const;

export function Diagnostics({ scene }: Props) {
  const store = useStore();
  const state = useInstrumentState();
  const [tick, setTick] = useState(0);
  const [switching, setSwitching] = useState<string | null>(null);
  useEffect(() => {
    if (!state.diagnostics) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [state.diagnostics]);
  if (!state.diagnostics) return null;
  const m = store.metrics.summary();
  const memory = (performance as unknown as { memory?: { usedJSHeapSize: number; totalJSHeapSize: number } }).memory;
  const info = scene?.info() ?? null;
  const saveMeasurements = () => {
    const record = {
      schema: "nisayon.browser-measurements.v1", measured_at: new Date().toISOString(),
      url: location.href, browser: navigator.userAgent,
      viewport: { width: innerWidth, height: innerHeight, device_pixel_ratio: devicePixelRatio },
      standalone: matchMedia("(display-mode: standalone)").matches,
      reduced_motion: state.reducedMotion, measurements: store.metrics.summary(), graphics: scene?.info() ?? null,
      scope: "Local session samples. Renderer GPU time excludes display presentation. This is not a controlled benchmark or a field INP score.",
      execution_connected: false,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2) + "\n"], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "nisayon-browser-measurements.json";
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const runSwitches = async (): Promise<void> => {
    const screen = state.screen;
    if (screen.kind !== "ready") return;
    const runs = screen.caseRecord.runs;
    const before = memory?.usedJSHeapSize ?? null;
    setSwitching("running 20 switches…");
    for (let i = 1; i <= 20; i += 1) {
      const next = runs[i % runs.length]!;
      store.selectRun(next.run);
      // Wait until the store reports that run as selected.
      await new Promise<void>((resolve) => {
        const check = (): void => {
          const s = store.getState().screen;
          if (s.kind === "ready" && s.moment.run.run_id === next.run.run_id && s.pendingRun === null) resolve();
          else setTimeout(check, 16);
        };
        check();
      });
    }
    const after = memory?.usedJSHeapSize ?? null;
    setSwitching(`20 switches done · heap ${fmtMb(before)} → ${fmtMb(after)} · cache ${store.cacheSize()} entries · ${info ? `${scene?.info().geometries} geometries` : "no scene"}`);
  };

  return (
    <section className="diag" aria-label="Diagnostics" data-tick={tick}>
      <div className="diag-heading"><h2 className="diag-title">Diagnostics · measured</h2><button type="button" className="ibtn" aria-label="Close diagnostics" onClick={() => store.toggleDiagnostics()}>×</button></div>
      <EvidenceFlow label="Device measurements">
      <dl className="facts compact">
        <div>
          <dt>first useful view</dt>
          <dd className="num">{m.firstUsefulViewMs === null ? "pending" : `${m.firstUsefulViewMs.toFixed(0)} ms after navigation start`}</dd>
        </div>
        <div>
          <dt>input → commit</dt>
          <dd className="num">
            n {m.n} · p50 {fmtMs(m.p50)} · p95 {fmtMs(m.p95)} · max {fmtMs(m.max)}
          </dd>
        </div>
        <div>
          <dt>heap (Chrome only)</dt>
          <dd className="num">{memory ? `${fmtMb(memory.usedJSHeapSize)} used of ${fmtMb(memory.totalJSHeapSize)}` : "not exposed by this browser"}</dd>
        </div>
        <div><dt>input → next paint</dt><dd className="num">{m.browserEvents.supported ? `Event Timing ≥16 ms · n ${m.browserEvents.count} · p95 ${fmtMs(m.browserEvents.p95)} · max ${fmtMs(m.browserEvents.max)}` : "Event Timing not exposed by this browser"}</dd></div>
        <div><dt>long tasks</dt><dd className="num">{m.longTasks.supported ? `${m.longTasks.count} tasks · total ${fmtMs(m.longTasks.totalMs)} · max ${fmtMs(m.longTasks.maxMs)}` : "Long Task API not exposed by this browser"}</dd></div>
        <div><dt>render submission / GPU</dt><dd className="num">{info ? `CPU n ${info.timing.cpu.count} · p95 ${fmtMs(info.timing.cpu.p95)}; GPU ${info.timing.gpu.supported ? `n ${info.timing.gpu.count} · p95 ${fmtMs(info.timing.gpu.p95)}` : "timer unavailable"}` : "No WebGL handle"}</dd></div>
        <div>
          <dt>renderer</dt>
          <dd className="num">{info ? `${info.geometries} geometries · ${info.textures} textures · ${info.calls} draw calls · ${info.frames} frames` : "no WebGL handle"}</dd>
        </div>
        <div>
          <dt>device pixel ratio</dt>
          <dd className="num">{window.devicePixelRatio}</dd>
        </div>
        <div>
          <dt>reduced motion</dt>
          <dd>{String(state.reducedMotion)}</dd>
        </div>
      </dl>
      <p className="fine">Local session samples, not a field INP score. Event Timing is browser-reported and rounded. GPU time excludes display presentation; disjoint timer results are discarded.</p>
      <div className="diag-actions">
        <button type="button" className="quiet" onClick={saveMeasurements}>Save device measurements</button>
        <button type="button" className="quiet" onClick={() => scene?.simulateContextLoss()} disabled={!scene}>
          Simulate GPU context loss
        </button>
        <button type="button" className="quiet" onClick={() => void runSwitches()} disabled={switching === "running 20 switches…"}>
          Run 20 run switches
        </button>
        {(import.meta.env.DEV ? VARIANTS : []).map(([label, url]) => (
          <button key={url} type="button" className="quiet" aria-pressed={state.evidenceUrl === url} onClick={() => store.setEvidence(url)}>
            evidence: {label}
          </button>
        ))}
      </div>
      {switching ? <p className="fine num">{switching}</p> : null}
      </EvidenceFlow>
    </section>
  );
}

function fmtMs(v: number | null): string {
  return v === null ? "—" : `${v.toFixed(1)} ms`;
}

function fmtMb(v: number | null): string {
  return v === null ? "—" : `${(v / 1048576).toFixed(1)} MB`;
}
