// One catalog for list, vector index, inspector and future named meshes.
// IDs and study packages reconciled with Rev A R01/R02 on 23 November 2026.
// Design proposals and packaging targets are never hardware measurements.
export const RICCI_CATALOG = [
  {
    id: "head_visor", label: "Head & visor", shortLabel: "Head / visor", group: "Perception",
    instances: ["head_visor"],
    purpose: "Observe the space ahead and the objects involved in a task.",
    proposal: "Forward depth behind the visor is the baseline. Compare head-only sensing with one downward chest view or a wrist view during carry and set-down.",
    observation: "With a matched sensor and time budget, record when the hands, tray and destination remain observable as the arms and payload move.",
    limit: "Side and rear views could extend horizontal awareness toward 360°. Arms and a tray can still occlude targets. This is neither full-sphere coverage nor validated safety.",
  },
  {
    id: "torso_spine", label: "Torso & spine", shortLabel: "Torso / spine", group: "Structure",
    instances: ["torso_spine"],
    purpose: "Connect the upper body to the pelvis and carry loads between them.",
    proposal: "Resolve the structural path together with space for cables, sensing and heat rejection. Internal packaging remains schematic.",
    observation: "Measured deflection and interface loads under a declared carrying case would test whether the structure preserves the required alignment.",
    limit: "An exterior surface does not establish a hidden mechanism, material or stiffness.",
  },
  {
    id: "waist_pelvis", label: "Waist & pelvis", shortLabel: "Waist / pelvis", group: "Structure",
    instances: ["waist_pelvis"],
    purpose: "Join the legs and torso while providing a common reference for the body.",
    proposal: "Use the pelvis as the model root. Treat waist articulation, mass distribution and balance during carrying as linked design questions.",
    observation: "Measured body motion, foot contact and payload state during carry and set-down would distinguish a useful adjustment from a loss of support.",
    limit: "A balanced-looking pose is not evidence of dynamic balance.",
  },
  {
    id: "arm_upper", label: "Shoulder & upper arm", shortLabel: "Upper arm", group: "Articulation",
    instances: ["arm_upper_left", "arm_upper_right"],
    purpose: "Position the arm so the hand can approach and support an object.",
    proposal: "Consider three shoulder axes. Resolve clearance and load paths before choosing a transmission or joint range.",
    observation: "A measured reach and load study with the declared payload would test clearance, deflection and the ability to maintain support.",
    limit: "A round housing is not a powered ball joint. ABENICS is a specific candidate mechanism, not an assumed implementation.",
  },
  {
    id: "arm_distal", label: "Forearm, wrist & hand", shortLabel: "Wrist / hand", group: "Contact",
    instances: ["arm_distal_left", "arm_distal_right"],
    purpose: "Orient the hand and establish contact with the carried object.",
    proposal: "Consider a hinge-like elbow and separate forearm rotation. Evaluate wrist load sensing alongside, and separately from, any wrist camera.",
    observation: "Synchronized hand motion and independent wrist loads would test whether contact changes can be distinguished from a shifting payload.",
    limit: "Finger appearance establishes neither dexterity nor force. Transmission and tactile placement remain unresolved.",
  },
  {
    id: "leg_upper", label: "Hip & upper leg", shortLabel: "Hip / thigh", group: "Articulation",
    instances: ["leg_upper_left", "leg_upper_right"],
    purpose: "Place the leg relative to the pelvis and transfer body loads.",
    proposal: "Consider three hip axes together with body clearance and the carrying posture. Keep actuation choices open.",
    observation: "Measured motion and loads through a declared set of support transitions would test clearance and task progress.",
    limit: "No joint range, torque rating or walking capability is established here.",
  },
  {
    id: "leg_shank", label: "Knee & shank", shortLabel: "Knee / shank", group: "Articulation",
    instances: ["leg_shank_left", "leg_shank_right"],
    purpose: "Connect knee and ankle while moving the lower leg through a task.",
    proposal: "Start with a hinge-like knee. Compare packaging choices by their clearance, service access and contribution to distal inertia.",
    observation: "Measured mass distribution, motion and contact response would test whether a packaging choice improves the intended task.",
    limit: "A tapered exterior alone does not demonstrate low inertia or an actuator layout.",
  },
  {
    id: "ankle_foot", label: "Ankle & sole", shortLabel: "Ankle / sole", group: "Contact",
    instances: ["ankle_foot_left", "ankle_foot_right"],
    purpose: "Support the body at the floor and make changes in contact observable.",
    proposal: "Consider ankle pitch and roll with a serviceable sole layer. Compare contact sensing and compliance choices before fixing the internal layout.",
    observation: "Independent foot and load measurements during carry and set-down should distinguish slip from a shifting payload. Compare matched sensor and time budgets, a common-response null and held-out trials.",
    limit: "The removable layer and lateral separation are proposed for inspection. D04 establishes the visible boot front, not sole construction, force or measured motion.",
  },
  {
    id: "outer_shell", label: "Outer shell", shortLabel: "Outer shell", group: "Packaging",
    instances: ["outer_shell"],
    purpose: "Define the exterior while allowing articulation, cooling and access.",
    proposal: "Resolve panel boundaries against the design plates and the assemblies they need to protect or expose.",
    observation: "Clearance and service trials on an authored assembly would test whether panels can be removed without disrupting adjacent parts.",
    limit: "Side and rear depths are proposed. The two visible front contours are authored separately; mirrored depth construction remains an assumption.",
  },
  {
    id: "power_pack", label: "Power pack", shortLabel: "Power pack", group: "Packaging",
    instances: ["power_pack"],
    purpose: "Supply energy for the intended task and permit isolation for service.",
    proposal: "Treat placement, replacement access and thermal separation as packaging options. The internal panel is schematic.",
    observation: "Measured energy demand, temperature and replacement procedure under a declared task would justify an allocation.",
    limit: "Cell layout, capacity, runtime, mass and chemistry are not specified.",
  },
  {
    id: "compute_thermal", label: "Compute & thermal", shortLabel: "Compute / heat", group: "Packaging",
    instances: ["compute_thermal"],
    purpose: "Process observations and reject the heat generated by that work.",
    proposal: "Compare serviceable compute and cooling arrangements against sensing and latency needs. Internal placement remains schematic.",
    observation: "Measured latency, power and temperature during a sustained representative workload would test the proposed envelope.",
    limit: "No processor, cooling capacity or real-time guarantee is implied.",
  },
  {
    id: "service_safety", label: "Service & safety", shortLabel: "Service / safety", group: "Access",
    instances: ["service_safety"],
    purpose: "Make inspection, isolation and maintenance deliberate and accessible.",
    proposal: "Consider replaceable extremities, accessible isolation and clear service boundaries alongside each assembly.",
    observation: "Documented maintenance tasks and fault-response tests would identify what is accessible, what fails and what remains untested.",
    limit: "These are design questions. A label, animation or stop control does not establish safety coverage or a repaired task.",
  },
] as const;

export type RicciPartId = typeof RICCI_CATALOG[number]["id"];
export type RicciPart = typeof RICCI_CATALOG[number];
// R01 study envelopes. No cost data is imported into the public component.
export const RICCI_PACKAGES: Record<RicciPartId, { envelope: string; material: string }> = {
  head_visor: { envelope: "185–220 H · 160–190 W · 175–215 D mm", material: "Optical polycarbonate; aluminium carrier" },
  torso_spine: { envelope: "375–430 W · 180–235 D mm", material: "6061 aluminium; 7075 where justified" },
  waist_pelvis: { envelope: "280–340 W · 160–210 D mm", material: "Aluminium housing; steel bearing interfaces" },
  arm_upper: { envelope: "275–320 mm · shoulder to elbow pivots", material: "Aluminium link; hardened-steel wear surfaces" },
  arm_distal: { envelope: "230–275 mm · elbow to wrist; 170–200 mm hand", material: "Aluminium baseline; titanium link candidate; grip pads" },
  leg_upper: { envelope: "390–440 mm · hip to knee pivots", material: "6061 / 7075 candidates; steel running surfaces" },
  leg_shank: { envelope: "380–430 mm · knee to ankle pivots", material: "Aluminium baseline; composites only after testing" },
  ankle_foot: { envelope: "250–285 L · 100–125 W mm · sole plan", material: "Aluminium / steel; selective titanium; traction rubber" },
  outer_shell: { envelope: "Wall thickness unresolved", material: "Replaceable tough polymer; selective composite" },
  power_pack: { envelope: "260–320 W · 160–220 H · 110–155 D mm bay", material: "Supplier pack; aluminium carrier and isolation" },
  compute_thermal: { envelope: "150–210 W · 95–140 H · 45–80 D mm bay", material: "Aluminium spreader; isolated mounts" },
  service_safety: { envelope: "Routing envelope unresolved", material: "Protected harness; independent stop channel" },
};
export function isRicciPartId(value: unknown): value is RicciPartId {
  return RICCI_CATALOG.some(part => part.id === value);
}
export interface RicciSelection { id: RicciPartId | null; issue: string | null; instance?: string }
export function readRicciSelection(hash: string): RicciSelection {
  const values = new URLSearchParams(hash.replace(/^#/, "")).getAll("part");
  if (!values.length) return { id: null, issue: null };
  if (values.length !== 1) return { id: null, issue: "This link contains conflicting part selections." };
  if (!isRicciPartId(values[0])) return { id: null, issue: "This link names a section that is not in the Ricci catalog." };
  const instances = new URLSearchParams(hash.replace(/^#/, "")).getAll("instance");
  const part = RICCI_CATALOG.find(part => part.id === values[0])!;
  if (instances.length > 1 || (instances.length === 1 && !(part.instances as readonly string[]).includes(instances[0]!)))
    return { id: null, issue: "This link names an instance outside the selected part." };
  return { id: values[0], issue: null, ...(instances[0] ? { instance: instances[0] } : {}) };
}
export function ricciSelectionHash(hash: string, id: RicciPartId | null, instance?: string): string {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  params.set("view", "concepts"); params.delete("chapter"); params.delete("part"); params.delete("instance");
  if (id) params.set("part", id);
  if (id && instance) params.set("instance", instance);
  return `#${params}`;
}
