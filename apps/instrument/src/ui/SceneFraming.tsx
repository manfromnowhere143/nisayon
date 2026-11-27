import { useEffect, useRef, useState } from "react";
import { useOutsideTap } from "./useOutsideTap";
import "../styles/scene-selector.css";
export type SceneFocus = "lab" | "workspace" | "grasp";
const choices = [{ id: "lab", label: "Hall" }, { id: "workspace", label: "Bay" }, { id: "grasp", label: "Grasp" }] as const;
/** A small spatial drawing identifies the camera's scale before its label. */
export function SceneFramingIcon({ focus }: { focus: SceneFocus }) {
  return <svg viewBox="0 0 64 48" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {focus === "lab" ? <><path d="M9 41V24a23 20 0 0 1 46 0v17M17 39V24a15 13 0 0 1 30 0v15M9 41l15-7h16l15 7M24 34V23a8 7 0 0 1 16 0v11"/><path d="M29 34v-5l5-4 3 4" opacity=".6"/></> : focus === "workspace" ? <><path d="M9 39h46M15 39V13M49 39V13M23 39V25h28v14M22 23l8-8 10 5"/><circle cx="30" cy="15" r="3"/><path d="M40 20v7m-3-1v5m6-5v5M12 10h6M46 10h6"/></> : <><path d="M25 8h14v10l7 8v11h-8v-8l-6-5-6 5v8h-8V26l7-8ZM29 8V3m6 5V3"/><path d="m29 35 3-2 3 2v5l-3 2-3-2Z"/><path d="M10 19v-6h6m32 0h6v6M10 37v6h6m32 0h6v-6" opacity=".4"/></>}
  </svg>;
}
export function SceneFraming({ value, onChange, source, onSource, onTools, onWorkstation, onContact }: {
  value: SceneFocus; onChange: (focus: SceneFocus) => void;
  source: boolean; onSource: () => void; onTools: (origin: HTMLButtonElement | null) => void;
  onWorkstation?: (origin: HTMLButtonElement) => void;
  onContact?: (origin: HTMLButtonElement) => void;
}) {
  const [open, setOpen] = useState(false), trigger = useRef<HTMLButtonElement>(null);
  useOutsideTap(open, "[data-scene-framing]", () => setOpen(false));
  useEffect(() => {
    if (!open) return;
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.current?.focus({ preventScroll: true }); } };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open]);
  const current = choices.find(choice => choice.id === value)!;
  return <div className="scene-framing" data-scene-framing data-open={open}>
    <button ref={trigger} type="button" className="scene-framing-current" aria-label={`Scene ${current.label}`} title={`Scene ${current.label}`} aria-expanded={open} onClick={() => setOpen(v => !v)}><SceneFramingIcon focus={value}/></button>
    {open ? <>
      <div className="scene-framing-options" role="group" aria-label="Scene framing">{choices.filter(choice => choice.id !== value).map(choice => <button key={choice.id} type="button" onClick={() => { onChange(choice.id); setOpen(false); trigger.current?.focus({ preventScroll: true }); }}><SceneFramingIcon focus={choice.id}/><span>{choice.label}</span></button>)}</div>
      <div className="scene-framing-secondary">
        {onContact ? <button type="button" onClick={() => { setOpen(false); if (trigger.current) onContact(trigger.current); }}>Contact dynamics<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M2 14h16M6 14V8h6v6M8 4h8m-3-3 3 3-3 3"/></svg></button> : null}
        {onWorkstation ? <button type="button" onClick={() => { setOpen(false); if (trigger.current) onWorkstation(trigger.current); }}>Experiment console<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 3h14v10H3zM10 13v4m-4 0h8"/></svg></button> : null}
        <button type="button" aria-pressed={source} onClick={onSource}>Source room<span aria-hidden="true">{source ? "●" : "○"}</span></button>
        <button type="button" onClick={() => { setOpen(false); onTools(trigger.current); }}>Adjust view<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 6h12M4 14h12M8 3v6m5 2v6"/></svg></button>
      </div>
    </> : null}
  </div>;
}
