// Shared presentation state. Importing this module never starts the robot lab.
export type Ground = "black" | "paper";
const GROUND_KEY = "nisayon.ground";

export function readGround(): Ground {
  try {
    const stored = localStorage.getItem(GROUND_KEY);
    if (stored === "paper" || stored === "black") return stored;
  } catch {
    /* Presentation remains usable without storage. */
  }
  return typeof matchMedia === "function" &&
    matchMedia("(prefers-color-scheme: light)").matches
    ? "paper"
    : "black";
}

export function applyGround(ground: Ground): void {
  try {
    localStorage.setItem(GROUND_KEY, ground);
  } catch {
    /* View state only. */
  }
  document.documentElement.dataset.ground = ground;
  const theme = document.querySelector<HTMLMetaElement>(
    'meta[name="theme-color"]',
  );
  if (theme) theme.content = ground === "paper" ? "#f4f2ec" : "#050506";
}
