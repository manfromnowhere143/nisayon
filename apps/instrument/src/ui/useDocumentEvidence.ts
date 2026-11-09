import { createContext, useContext, useSyncExternalStore } from "react";

export const FixedEvidenceLayout = createContext(false);

// Keep this query aligned with the compact workspace rules in evidence.css.
// Narrow or short workspaces use one native document, not nested paginators.
export const DOCUMENT_EVIDENCE_QUERY = "(max-width: 1023px), (max-height: 620px)";
const snapshot = () => typeof matchMedia === "function" && matchMedia(DOCUMENT_EVIDENCE_QUERY).matches;
const subscribe = (notify: () => void) => {
  if (typeof matchMedia !== "function") return () => {};
  const media = matchMedia(DOCUMENT_EVIDENCE_QUERY);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};

export function useDocumentEvidence() {
  const fixed = useContext(FixedEvidenceLayout);
  const compact = useSyncExternalStore(subscribe, snapshot, () => false);
  return !fixed && compact;
}
