import { SceneDetail } from "../ui/SceneDetail";
import type { WorkstationReading } from "../model/workstation";
import "../styles/lab-console.css";

/** A spatial entry into existing instruments. No second experiment state. */
export function LaboratoryConsole({ reading, origin, onClose, onInspect, onCompare, onContact }: {
  reading: WorkstationReading | null; origin: HTMLElement | null;
  onClose: () => void; onInspect: () => void; onCompare: () => void; onContact: () => void;
}) {
  return <SceneDetail floating title="Experiment console" caption="Protocols · measurements · evidence" className="lab-console" returnFocus={origin} onClose={onClose}>
    <p className="lab-console-context">Panda Lift <span>Retained simulation</span></p>
    {reading ? <p className="lab-console-reading">{reading.caseLabel}<br/><span>{reading.runLabel} · {reading.signalTime == null ? "Sample unavailable" : `${reading.signalTime.toFixed(3)} s`}</span></p> : null}
    <nav aria-label="Laboratory operations">
      <button type="button" onClick={onInspect}><span>Inspect current recording<small>Commands, observations and task outcome</small></span><span aria-hidden="true">↗</span></button>
      <button type="button" onClick={onCompare}><span>Compare recorded runs<small>Baseline, regression and retained correction</small></span><span aria-hidden="true">↔</span></button>
      <button type="button" onClick={onContact}><span>Contact dynamics<small>Configure, execute locally and inspect evidence</small></span><span aria-hidden="true">↗</span></button>
    </nav>
    <p className="lab-console-note">Contact execution is available when the local adapter is connected. Recorded evidence remains inspectable without it.</p>
  </SceneDetail>;
}
