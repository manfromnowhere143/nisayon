import { useEffect, useRef, useState, type RefObject } from "react";
import { CHAPTERS, RICCI_PARTS, readConceptChapter, type ConceptChapter, type RicciPart } from "./ricci";
import { LoadStudy } from "./LoadStudy";
import "../styles/concepts.css";

const COPY: Record<ConceptChapter, { label: string; title: string; text: string }> = {
  Form: { label: "01 / REFERENCE STUDY", title: "A form worth resolving.", text: "Sculpted shells. Exposed articulation. A calm presence in a place built for work. The original film is the visual starting point for Ricci." },
  Mechanism: { label: "02 / PACKAGING QUESTIONS", title: "Every surface needs a reason.", text: "Follow the silhouette into its mechanical questions. A shell must leave room for structure, motion, sensing and repair." },
  Motion: { label: "03 / PROPOSED FIRST TASK", title: "Carry. Place. Understand.", text: "Begin with a light tray carried on level ground. Hands, payload and balance belong to one physical problem." },
  Physics: { label: "04 / LOAD STUDY", title: "Make the assumptions visible.", text: "A small model is useful when its limits are clear. This first calculation exposes the effect of reach and load sharing." },
  Evidence: { label: "05 / SOURCE & STATUS", title: "A design you can question.", text: "Visual references, chosen dimensions and computed quantities each say something different. Keep the source close to the claim." },
  Build: { label: "06 / DEVELOPMENT PATH", title: "From an idea to an assembly.", text: "The concept is a beginning. Production requires drawings, tolerances, components, measured behaviour and a repeatable build." },
};

function ReferenceView({ carry, selected, onSelect }: { carry: boolean; selected: RicciPart | null; onSelect: (part: RicciPart) => void }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [carry]);
  return <figure className="concept-reference">
    <div className="concept-reference-heading"><span>{carry ? "CARRYING REFERENCE" : "FORM REFERENCE"}</span><span>{carry ? "V01 / 00:04" : "V00 / 00:03"}</span></div>
    <div className="concept-image-space">
      {failed ? <div className="concept-media-failure" role="status"><h2>Reference image unavailable</h2><p>The written observations and calculations remain available.</p><button onClick={() => setFailed(false)}>Retry reference image</button></div>
      : <div className="concept-image-plane">
        <img key={carry ? "carry" : "form"} src={`/media/ricci/${carry ? "carry" : "form"}-reference.webp`} width="1920" height="1080" alt={carry ? "Generated film reference: a humanoid supports a tray from below inside the architectural lab. This is an appearance and task reference, not a physical trial." : "Generated film reference: pale sculpted humanoid shells, exposed dark joints and shaped feet in a glazed vaulted hall. This is visual art direction, not built hardware."} onError={() => setFailed(true)} />
        {!carry ? <div className="concept-callouts" aria-label="Inspect a reference feature">{RICCI_PARTS.map((part, i) => <button key={part.id} style={{ left: `${part.x}%`, top: `${part.y}%` }} aria-label={`Inspect ${part.label.toLowerCase()}`} aria-pressed={selected === part.id} onClick={() => onSelect(part.id)}><span>{String(i + 1).padStart(2, "0")}</span><i aria-hidden="true" /></button>)}</div> : null}
      </div>}
    </div>
    <figcaption><span>Original Google / Veo film reference · generated imagery</span><a href="/media/ricci/sources.json" target="_blank" rel="noopener">Source identity ↗</a></figcaption>
  </figure>;
}

export function ConceptStudio({ heading, laboratory }: { heading: RefObject<HTMLHeadingElement | null>; laboratory: () => void }) {
  const [chapter, setChapter] = useState<ConceptChapter>(() => readConceptChapter(location.hash));
  const [selected, setSelected] = useState<RicciPart | null>(null);
  const content = useRef<HTMLDivElement>(null);
  const part = RICCI_PARTS.find(p => p.id === selected);
  const copy = COPY[chapter];
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [heading]);
  useEffect(() => {
    const read = () => setChapter(readConceptChapter(location.hash));
    window.addEventListener("popstate", read); window.addEventListener("hashchange", read);
    return () => { window.removeEventListener("popstate", read); window.removeEventListener("hashchange", read); };
  }, []);
  const choose = (next: ConceptChapter) => {
    const hash = new URLSearchParams(location.hash.slice(1)); hash.set("view", "concepts"); hash.set("chapter", next.toLowerCase());
    history.pushState({ nisayon: true }, "", `${location.pathname}${location.search}#${hash}`);
    setChapter(next); content.current?.scrollTo?.({ top: 0 });
  };
  return <main className="concept-studio" id="research-content" data-chapter={chapter.toLowerCase()}>
    <header className="concept-title">
      <div><p className="concept-status">NISAYON / ROBOT CONCEPTS</p><h1 ref={heading} tabIndex={-1}>Ricci <span>01</span></h1></div>
      <div className="concept-revision"><span className="concept-dot" />Concept study<span>R01 · 16 NOV 2026</span></div>
    </header>
    <nav className="concept-chapters" aria-label="Concept chapters">{CHAPTERS.map((name, index) => <button key={name} aria-pressed={chapter === name} onClick={() => choose(name)}><span>{String(index + 1).padStart(2, "0")}</span>{name}</button>)}</nav>
    <div className="concept-body" ref={content}>
      <aside className="concept-reading">
        <p className="concept-status">{copy.label}</p><h2>{copy.title}</h2><p>{copy.text}</p>
        {chapter === "Form" || chapter === "Mechanism" ? <>
          <div className="concept-parts" role="group" aria-label="Reference features">{RICCI_PARTS.map((p, i) => <button key={p.id} aria-pressed={selected === p.id} onClick={() => setSelected(p.id)}><span>{String(i + 1).padStart(2, "0")}</span>{p.label}<span aria-hidden="true">↗</span></button>)}</div>
          <div className="concept-inspection" aria-live="polite"><span className="concept-status">{part ? "SELECTED REFERENCE FEATURE" : "REFERENCE BOUNDARY"}</span><h3>{part?.label ?? "Appearance precedes mechanism."}</h3><p>{part?.observation ?? "These frames guide the silhouette. They do not supply a consistent CAD assembly, calibrated dimensions or hidden mechanisms."}</p>{part ? <p className="concept-question">{part.question}</p> : null}</div>
        </> : chapter === "Motion" ? <dl className="concept-assumptions"><div><dt>Task direction</dt><dd>Bimanual carrying & placement</dd></div><div><dt>Study payload</dt><dd>2 kg <small>assumed</small></dd></div><div><dt>Study speed</dt><dd>0.5 m/s <small>target</small></dd></div><div><dt>Contact</dt><dd>Support beneath the tray</dd></div></dl> : chapter === "Physics" ? <div className="concept-inspection"><h3>One load case, two shoulders.</h3><p>The slider changes a static free-body model. It does not replay a robot or predict a successful carry.</p><p className="concept-question">The illustrated moment arms are independent study inputs, not measured Ricci anatomy.</p></div> : <div className="concept-inspection"><h3>Research concept</h3><p>There is no manufacturing release or validated Ricci hardware result in this study.</p><button className="concept-text-button" onClick={laboratory}>Inspect Nisayon’s recorded experiment ↗</button></div>}
        <p className="concept-fine concept-name">Ricci takes its working name from the Ricci tensor. The name makes no claim about a curvature-based controller.</p>
      </aside>
      <section className="concept-stage" aria-label={`${chapter} study`}>
        {chapter === "Form" || chapter === "Mechanism" ? <ReferenceView carry={false} selected={selected} onSelect={setSelected} />
        : chapter === "Motion" ? <div className="concept-motion"><ReferenceView carry selected={null} onSelect={setSelected} /><div className="concept-motion-note"><h3>Motion must be recomputed.</h3><p>Changing mass, contact or control invalidates an old trajectory as a prediction. A floating-base model needs coupled dynamics, contact constraints, actuator limits and fresh tests.</p><code>M(q) v̇ + h(q,v) = Sᵀτ + Jcᵀλ + Jextᵀfext</code><p className="concept-fine">Model structure only. No Ricci dynamics are solved here. <a href="https://underactuated.mit.edu/humanoids.html" target="_blank" rel="noopener">Read the dynamics reference ↗</a></p></div></div>
        : chapter === "Physics" ? <LoadStudy />
        : chapter === "Evidence" ? <div className="concept-document">
          <p className="concept-status">STUDY RECORD / R01</p><h2>What the record supports.</h2>
          <div className="concept-evidence-row"><span>Visual observation</span><div><h3>Five original generated clips</h3><p>Source hashes were checked against the retained manifest. The studio shows V00 at 3 s and V01 at 4 s. Perspective, seams and hidden surfaces remain ambiguous.</p><a href="/media/ricci/sources.json" target="_blank" rel="noopener">Inspect frame and source hashes ↗</a></div></div>
          <div className="concept-evidence-row"><span>Chosen assumptions</span><div><h3>Dimensions & allocations</h3><p>1.75 m height. 43 candidate actuators including the hands. 62 kg allocated, plus a 15% allowance: 71.3 kg. These are study inputs; component fit, mass and actuation are not closed.</p></div></div>
          <div className="concept-evidence-row"><span>Conditional arithmetic</span><div><h3>A static load screen</h3><p>The Physics view computes shoulder moments from explicit masses, horizontal moment arms and a chosen load split. It does not establish dynamic stability or select motors.</p><button className="concept-text-button" onClick={() => choose("Physics")}>Inspect the calculation ↗</button></div></div>
          <div className="concept-evidence-row"><span>Still to establish</span><div><h3>Physical & production evidence</h3><p>Consistent engineering geometry; measured mass and inertia; joint and actuator specifications; contact and thermal models; simulation correlation; component and integrated tests.</p></div></div>
          <a className="concept-source-link" href="/media/ricci/study-sources.txt" target="_blank" rel="noopener">Read the study sources and external research ↗</a>
        </div>
        : <div className="concept-document concept-build"><p className="concept-status">PROPOSED DEVELOPMENT SEQUENCE</p><h2>Resolve the design.<br />Then earn the result.</h2>
          {[
            ["01", "Reference & requirements", "In study", "Resolve orthographic views, conflicting seams, unseen geometry, carrying task and measurable acceptance conditions."],
            ["02", "Mechanics & packaging", "Open", "Define part identities, load paths, bearings, actuation, wiring, sensing, thermal paths and service access in CAD."],
            ["03", "Analysis & verification", "Open", "Bind mass and inertia to a revision. Check kinematics, collisions, contact and actuator constraints. Retain failed cases."],
            ["04", "Prototype & correlation", "Open", "Measure components and assemblies. Compare predicted and observed behaviour before integrated task trials."],
            ["05", "Manufacturing & service", "Open", "Release drawings, tolerances, material/process choices, BOM, assembly sequence, inspection and change control."],
          ].map(([index, name, status, text]) => <div className="concept-build-step" key={index}><span>{index}</span><div><h3>{name}</h3><p>{text}</p></div><small>{status}</small></div>)}
          <p className="concept-fine">No production date, cost or certification is established. This sequence is a development plan, not completed engineering.</p>
        </div>}
      </section>
    </div>
  </main>;
}
