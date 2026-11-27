import { useLayoutEffect, useRef, useState } from "react";
import { GlassCard } from "../research/GlassCard";
import { SectionDeck } from "../ui/RecordPages";
import { CommandBlock } from "./CommandBlock";

const commands = [
  { name: "Install", detail: "Python 3.12 · macOS or Linux · a new environment. Dependencies are pinned with hashes.", command: "python3.12 -m venv .venv\n.venv/bin/python -m pip install --require-hashes -r https://github.com/manfromnowhere143/nisayon/releases/download/v0.2.0/requirements-install.txt" },
  { name: "Example", detail: "Create the inspectable example. No Git, model or simulator download is needed.", command: ".venv/bin/nisayon-qualify example owner-project" },
  { name: "Run", detail: "Freeze first, then execute six native calls and inspect the software decision.", command: ".venv/bin/nisayon-qualify plan owner-project/case.json --project owner-project --out run-001 --plan plan-001.json\n.venv/bin/nisayon-qualify run plan-001.json\n.venv/bin/nisayon-qualify inspect run-001" },
  { name: "Review", detail: "Export the original records, recompute the assessment, then open the file here.", command: ".venv/bin/nisayon-qualify export run-001 --out review-001.nisayon.zip\n.venv/bin/nisayon-qualify review review-001.nisayon.zip" },
];
export function Develop({ review }: { review: () => void }) {
  const [step, setStep] = useState(0), [copyLabel, setCopyLabel] = useState("Copy"), [detail, setDetail] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  const current = commands[step]!;
  const copy = async () => {
    try { if (!navigator.clipboard) throw new Error("Clipboard unavailable"); await navigator.clipboard.writeText(current.command); setCopyLabel("Copied"); }
    catch { setCopyLabel("Copy unavailable"); }
  };
  return <main className="develop-workspace" aria-label="Develop with Nisayon"><div className="develop-intro"><p className="research-micro">NISAYON SDK / PYTHON</p><h1 ref={heading} tabIndex={-1}>The experiment stays<br />in your environment.</h1><p>Freeze a change. Test it natively.<br />Carry the evidence into a decision.</p></div>
    <section className="develop-terminal" aria-label="Qualification workflow"><nav aria-label="SDK steps">{commands.map((item, i) => <button key={item.name} aria-pressed={step === i} onClick={() => { setStep(i); setCopyLabel("Copy"); }}><span>{String(i + 1).padStart(2, "0")}</span>{item.name}</button>)}</nav><div className="terminal-body"><div className="terminal-meta"><span>YOUR TERMINAL</span><button onClick={() => void copy()} aria-label="Copy SDK command" aria-live="polite">{copyLabel}</button></div><CommandBlock key={step} command={current.command} /><p className="review-note command-description">{current.detail}</p></div></section>
    <div className="develop-actions"><button className="research-action" onClick={review}>Open a review</button><button className="research-text-action" onClick={() => setDetail(true)}>Python & scope</button><span>Local execution · read-only review</span></div>
    {detail ? <GlassCard title="Start with a declared change" eyebrow="SDK 0.2.0 / DEVELOPER PREVIEW" onClose={() => setDetail(false)}><SectionDeck label="SDK guide" sections={[
      { id: "setup", label: "Python", content: <><h3>Import the same engine</h3><p>The installed example includes the complete Python workflow. After creating it, run:</p><pre><code>.venv/bin/python owner-project/sdk_example.py --out python-result-001</code></pre><p>It imports <code>CaseSpec</code>, <code>ExecutionContext</code>, <code>plan_change</code>, <code>run_plan</code>, <code>assess_change</code>, <code>export_run</code> and <code>inspect_bundle</code> from <code>nisayon.qualification</code>.</p><p><a href="/sdk/" target="_blank" rel="noopener">Installation, Python example & run contents</a></p><p><a href="https://github.com/manfromnowhere143/nisayon/blob/main/docs/CAPABILITIES.md" target="_blank" rel="noopener">Full capability map</a></p></> },
      { id: "laboratory", label: "Laboratory", content: <><h3>Run a bounded physical comparison</h3><p>The laboratory adds a local contact-dynamics instrument in research preview. Its Python API, CLI and browser workbench use the same execution and qualification functions.</p><p>The public lab includes verified retained PandaLift, contact and G1 readings. New contact executions require the current source checkout with its locked native profile; the SDK 0.2.0 wheel does not include this preview.</p><p><a href="https://github.com/manfromnowhere143/nisayon/blob/main/docs/LABORATORY.txt" target="_blank" rel="noopener">Local setup, API and reproduction</a></p><p>Actuation, metrology and morphology instruments are not available. Ricci remains an embodiment research program.</p></> },
      { id: "boundary", label: "Scope", content: <><h3>A bounded software decision</h3><p>Declare a reference, candidate, negative control, probes, native call witnesses and an exact or numerical relation.</p><p>This adapter checks synchronous Python functions. Software adoption on those probes leaves deployment acceptance unresolved.</p><p>Checkpoint loading alone does not establish state completeness or correct continuation.</p></> },
      { id: "review", label: "Review", content: <><h3>Carry original evidence</h3><p>Export preserves complete records, including logs and local paths. It does not redact them. Keep the source store sealed; write the review outside it.</p><p>Python review recomputes the assessment. The instrument checks transport bytes and displays the saved assessment. Files opened here stay in browser memory and are not uploaded.</p></> },
    ]} /></GlassCard> : null}
  </main>;
}
