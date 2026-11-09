// The concise, source-derived finding for the selected run, with the four
// status words kept separate and the depth affordances beside it.

import { recordingEnd, type LoadedRun } from "../data/loader";
import { contextualFinding, statusWords } from "../model/findings";
import type { CaseRecord, Depth, Moment } from "../model/types";
import { useStore } from "../state/useStore";
import { Icon } from "./Icon";

interface Props {
  caseRecord: CaseRecord;
  run: LoadedRun;
  moment: Moment;
  depth: Depth;
  onInspect?: (origin: HTMLElement) => void;
}

export function Finding({ caseRecord, run, moment, depth, onInspect }: Props) {
  const store = useStore();
  const described = contextualFinding(caseRecord, run.record, run.samples.rows);
  const words = statusWords(run.record);
  const atFinding = described.row !== null && described.row === moment.row_index;

  return (
    <section className="finding" aria-labelledby="finding-headline">
      <h1 id="finding-headline" className="finding-headline">
        {described.headline}
      </h1>
      <p className="finding-detail num">{described.detail}</p>
      <p className="finding-status">
        <span>process {words.process}</span>
        <span>measurement {words.measurement}</span>
        <span>task {words.task}</span>
        <span className="num">
          {run.record.row_count} rows · ends {recordingEnd(run).toFixed(2)} s
        </span>
      </p>
      <div className="finding-actions">
        {onInspect ? <button type="button" className="quiet" onClick={(event) => onInspect(event.currentTarget)}>Inspect this moment</button> : null}
        {!atFinding && described.row !== null ? (
          <button type="button" className="quiet" onClick={() => store.setRow(described.row!, "push")}>
            Go to step {described.step}
          </button>
        ) : null}
        {depth === "moment" ? (
          <>
            <button type="button" className="quiet depth-open" onClick={() => store.setDepth("fork")}>
              Fork <Icon name="open" />
            </button>
            <button type="button" className="quiet depth-open" onClick={() => store.setDepth("decision")}>
              Decision <Icon name="open" />
            </button>
          </>
        ) : null}
      </div>
    </section>
  );
}
