import { useState } from "react";
import { INITIAL_LOAD, staticShoulderStudy, type LoadStudy as Inputs } from "./ricci";

export function LoadStudy() {
  const [inputs, setInputs] = useState(INITIAL_LOAD);
  const result = staticShoulderStudy(inputs);
  const [showDerivation, setShowDerivation] = useState(false);
  const controls = [
    { key: "payloadKg", label: "Tray + payload", unit: "kg", min: 0, max: 4, step: .1 },
    { key: "reachM", label: "Horizontal reach", unit: "m", min: .15, max: .65, step: .01 },
    { key: "share", label: "Left-hand load share", unit: "%", min: .1, max: .9, step: .05 },
  ] as const;
  const set = (key: keyof Inputs, value: number) => setInputs(old => ({ ...old, [key]: value }));
  return <div className="load-study">
    <div className="concept-status">CONDITIONAL CALCULATION / STATIC</div>
    <h2>What does the shoulder carry?</h2>
    <p>Move the tray farther from the body. The moment rises, even when its mass stays the same.</p>
    <svg className="load-diagram" viewBox="0 0 640 370" role="img" aria-labelledby="load-diagram-title load-diagram-desc">
      <title id="load-diagram-title">Bimanual tray support, simplified side view</title>
      <desc id="load-diagram-desc">A horizontal arm supports an assigned share of the tray weight. Downward forces act at the arm centre of mass and the tray. This is a free-body diagram, not Ricci geometry.</desc>
      <defs><marker id="force-arrow" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto"><path d="M0 0 6 3 0 6" /></marker></defs>
      <path className="load-grid" d="M35 300H610M35 240H610M35 180H610M35 120H610M35 60H610M95 35V320M185 35V320M275 35V320M365 35V320M455 35V320M545 35V320" />
      <path className="load-body" d="M100 290V132Q100 115 118 115H146M146 115H430" />
      <circle className="load-joint" cx="146" cy="115" r="22" />
      <circle className="load-joint" cx="292" cy="115" r="12" />
      <path className="load-tray" d="M386 95H566V78M386 95V78H566M424 116H474" />
      <path className="load-force" d={`M478 100V${150 + inputs.payloadKg * 16}`} markerEnd="url(#force-arrow)" />
      <path className="load-force load-arm-force" d="M270 126V201" markerEnd="url(#force-arrow)" />
      <path className="load-dimension" d="M146 247H450M146 239V255M450 239V255M146 145V232M450 127V232" />
      <text x="298" y="275" textAnchor="middle">r = {inputs.reachM.toFixed(2)} m</text>
      <text x="490" y="150">{result.leftReactionN.toFixed(2)} N</text>
      <text x="279" y="215">39.24 N</text>
      <text x="65" y="325">Shoulder</text><text x="425" y="55">Support beneath tray</text>
      <path className="load-moment" d="M111 156A54 54 0 0 1 102 78" markerEnd="url(#force-arrow)" />
    </svg>
    <div className="load-results" aria-live="polite" aria-atomic="true">
      <div><span>Left shoulder</span><strong>{result.leftNm.toFixed(2)} <small>N·m</small></strong></div>
      <div><span>Right shoulder</span><strong>{result.rightNm.toFixed(2)} <small>N·m</small></strong></div>
    </div>
    <div className="load-controls">{controls.map(control => <label key={control.key}>
      <span>{control.label}<output>{control.key === "share" ? Math.round(inputs.share * 100) : inputs[control.key].toFixed(control.key === "reachM" ? 2 : 1)} {control.unit}</output></span>
      <input type="range" min={control.min} max={control.max} step={control.step} value={inputs[control.key]} aria-label={control.label} aria-valuetext={`${control.key === "share" ? Math.round(inputs.share * 100) : inputs[control.key]} ${control.unit}`} onChange={event => set(control.key, event.currentTarget.valueAsNumber)} />
    </label>)}</div>
    <p className="concept-fine">Schematic, not to scale. Assumed per arm: 4 kg, centre of mass 0.25 m from the shoulder. Horizontal, static arms; vertical supports; chosen load split. This does not establish an actuator rating, grasp feasibility or balance.</p>
    <button className="concept-text-button" aria-expanded={showDerivation} onClick={() => setShowDerivation(value => !value)}> {showDerivation ? "Hide" : "Inspect"} the calculation <span aria-hidden="true">↗</span></button>
    {showDerivation ? <div className="load-derivation">
      <p><code>τL = mₐ g rₐ + α mₚ g rₚ</code><br /><code>τR = mₐ g rₐ + (1 − α) mₚ g rₚ</code></p>
      <p>Each arm contributes {result.armMoment.toFixed(3)} N·m. The two vertical supports sum to {result.totalPayloadN.toFixed(2)} N. The selected load split is assumed; it is not solved from tray contact geometry.</p>
      <p>Acceleration, joint friction, transmissions, asymmetry in arm pose, torque–speed limits, heating and contact stability are outside this model. Motor selection needs those constraints and measurements.</p>
      <a href="/media/ricci/study-sources.txt" target="_blank" rel="noopener">Read the study inputs and source boundary ↗</a>
    </div> : null}
    <button className="concept-text-button" onClick={() => setInputs(INITIAL_LOAD)}>Reset study inputs</button>
  </div>;
}
