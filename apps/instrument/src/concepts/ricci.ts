// A design study, not an engine result or a hardware specification.
// Retained arithmetic assumptions: humanoid-audit/prior-assumptions.json,
// Nisayon-Humanoid-Balance-Codex-Handoff-2026-11-15.md.
export const CHAPTERS = ["Form", "Mechanism", "Motion", "Physics", "Evidence", "Build"] as const;
export type ConceptChapter = typeof CHAPTERS[number];
export const RICCI_PARTS = [
  { id: "head", label: "Head & perception", x: 70, y: 10, observation: "A tapered shell, dark face and circular side housings.", question: "Sensor fields of view, neck travel and cooling need a common packaging study." },
  { id: "torso", label: "Torso & waist", x: 69, y: 25, observation: "A broad chest narrows into an exposed, articulated waist.", question: "The load path, battery position, heat rejection and cable routing remain to be defined." },
  { id: "hand", label: "Hand & contact", x: 76, y: 31, observation: "Long segmented fingers, an opposed thumb and visible joint gaps.", question: "Joint axes, transmission, tactile sensing and collision clearance need authored geometry." },
  { id: "ankle", label: "Ankle & sole", x: 69, y: 79, observation: "A narrow ankle joins a shaped heel, toe and sole.", question: "Bearing support, actuator envelope, foot contact and service access must fit within the silhouette." },
] as const;
export type RicciPart = typeof RICCI_PARTS[number]["id"];
export const INITIAL_LOAD = { payloadKg: 2, reachM: .55, armKg: 4, armComM: .25, share: .5 };
export type LoadStudy = typeof INITIAL_LOAD;

export function staticShoulderStudy(input: LoadStudy) {
  const { payloadKg, reachM, armKg, armComM, share } = input;
  if (![payloadKg, reachM, armKg, armComM, share].every(Number.isFinite) || payloadKg < 0 || reachM < 0 || armKg < 0 || armComM < 0 || share < 0 || share > 1) throw new Error("The study requires finite, non-negative quantities and a load share from zero to one.");
  const gravity = 9.81;
  const armMoment = armKg * gravity * armComM;
  const leftReactionN = payloadKg * gravity * share;
  const rightReactionN = payloadKg * gravity * (1 - share);
  return { gravity, armMoment, leftReactionN, rightReactionN,
    leftNm: armMoment + leftReactionN * reachM,
    rightNm: armMoment + rightReactionN * reachM,
    totalPayloadN: payloadKg * gravity };
}

export function readConceptChapter(hash: string): ConceptChapter {
  const value = new URLSearchParams(hash.replace(/^#/, "")).get("chapter");
  return CHAPTERS.find(chapter => chapter.toLowerCase() === value) ?? "Form";
}
