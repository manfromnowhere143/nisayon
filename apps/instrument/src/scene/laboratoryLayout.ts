// Authored presentation coordinates in metres, Three y-up. These positions
// never enter a physical model, experiment identity or recorded trajectory.
// Keep the two instruments and operator console in one working bay. The
// longitudinal contact track leaves the entrance and Panda inspection open.
export const LAB_LAYOUT = {
  console: { position: [1.95, 0, -.35] as const, yaw: -Math.PI / 8 },
  contact: { position: [-1.65, 1.02, .15] as const, yaw: Math.PI / 2 },
  contactInspection: { target: [-1.65, 1.08, -.5] as const, eye: [-.55, 2.2, 1.8] as const },
};

// Matches the registered adapter's maximum admitted displacement. The visible
// plane is only a crop of its infinite simulated plane; it adds no end stops.
export const CONTACT_TRAVEL_M = 1.5;
