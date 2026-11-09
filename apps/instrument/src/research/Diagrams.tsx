import type { DiagramProps } from "./diagrams/shared";
import { Transfer } from "./diagrams/Transfer";
import { Terminal } from "./diagrams/Terminal";
import { Processors } from "./diagrams/Processors";
import { Decisions } from "./diagrams/Decisions";
import { Routing } from "./diagrams/Routing";
import { Cost } from "./diagrams/Cost";
import { Competence } from "./diagrams/Competence";
import { Deployment } from "./diagrams/Deployment";
import { Attention } from "./diagrams/Attention";
import { Promotion } from "./diagrams/Promotion";
import { Dispatch } from "./diagrams/Dispatch";
export { SystemDiagram } from "./diagrams/SystemDiagram";

export function InvestigationDiagram({ entry, route, select }: DiagramProps) {
  switch (entry.id) {
    case "dispatch":
      return <Dispatch data={entry.data} route={route} select={select} />;
    case "promotion":
      return <Promotion data={entry.data} route={route} select={select} />;
    case "attention":
      return <Attention data={entry.data} route={route} select={select} />;
    case "transfer":
      return <Transfer data={entry.data} route={route} select={select} />;
    case "terminal":
      return <Terminal data={entry.data} route={route} select={select} />;
    case "processors":
      return <Processors data={entry.data} route={route} select={select} />;
    case "decisions":
      return <Decisions data={entry.data} route={route} select={select} />;
    case "routing":
      return <Routing data={entry.data} route={route} select={select} />;
    case "cost":
      return <Cost data={entry.data} route={route} select={select} />;
    case "competence":
      return <Competence data={entry.data} route={route} select={select} />;
    case "deployment":
      return <Deployment data={entry.data} />;
  }
}
