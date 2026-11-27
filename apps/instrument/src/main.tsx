import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Experience } from "./research/Experience";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/dashboard.css";
import "./styles/spatial.css";
import "./styles/inspection.css";
import "./styles/choice.css";
import "./styles/study.css";
import "./styles/mechanisms.css";
import "./styles/evidence.css";
import "./styles/research.css";
import "./styles/instrument.css";
import "./styles/observatory.css";
import "./styles/cards.css";
import "./styles/focus.css";
import "./styles/legibility.css";
import "./styles/opening.css";
import "./styles/mobile.css";
import "./styles/laboratory.css";
import "./styles/floating-lab.css";
import "./styles/library.css";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");
createRoot(root).render(
  <StrictMode>
    <Experience />
  </StrictMode>,
);
