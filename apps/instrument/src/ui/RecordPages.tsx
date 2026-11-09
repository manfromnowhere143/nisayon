import { Children, isValidElement, memo, useId, useState, type ReactNode } from "react";
import { EvidenceFlow } from "./EvidenceFlow";
import { Choice } from "./Choice";

// A single fitted surface owns navigation, including nested collections. The
// original record order and React keys survive window and text-size changes.
export function RecordPages({ label, children }: { label: string; children: ReactNode }) {
  const records = Children.toArray(children);
  const content = <div className="flow-records" role="list" aria-label={label}>{records.map((record, index) => <div key={isValidElement(record) ? record.key ?? index : index} role="listitem">{record}</div>)}</div>;
  return <EvidenceFlow label={label}>{content}</EvidenceFlow>;
}

export interface DeckSection { id: string; label: string; content: ReactNode; fit?: boolean }

// Keep local tab state, but do not reconcile hundreds of hidden signal marks
// at playback cadence. Returning to a panel immediately supplies current data.
const PanelContents = memo(({ children }: { children: ReactNode; active: boolean }) => <>{children}</>, (_previous, next) => !next.active);

export function PagedFacts({ label, children }: { label: string; children: ReactNode }) {
  return <EvidenceFlow label={label}><dl className="facts compact" aria-label={label}>{children}</dl></EvidenceFlow>;
}

export function SectionDeck({ label, sections, initial, selected: controlled, onSelect }: { label: string; sections: DeckSection[]; initial?: string; selected?: string; onSelect?: (id: string) => void }) {
  const [requested, setRequested] = useState(initial ?? sections[0]?.id);
  const wanted = controlled ?? requested;
  const selected = sections.some((section) => section.id === wanted) ? wanted : sections[0]?.id;
  const id = useId();
  return <div className="section-deck">
    <div className="section-compact"><Choice label={`${label} section`} value={selected ?? ""} options={sections.map(section => ({ value: section.id, label: section.label }))} onChange={id => { setRequested(id); onSelect?.(id); }} /></div>
    <nav className="section-tabs" aria-label={label}>
      {sections.map((section) => <button key={section.id} type="button" className={`section-tab${section.id === selected ? " is-selected" : ""}`} aria-pressed={section.id === selected} aria-controls={`${id}-${section.id}`} onClick={() => { setRequested(section.id); onSelect?.(section.id); }}>{section.label}</button>)}
    </nav>
    <div className="deck-content">
      {sections.map((section) => <div key={section.id} id={`${id}-${section.id}`} className="deck-panel" hidden={section.id !== selected}><PanelContents active={section.id === selected}>{section.fit === false ? section.content : <EvidenceFlow label={`${label} · ${section.label}`}>{section.content}</EvidenceFlow>}</PanelContents></div>)}
    </div>
  </div>;
}
