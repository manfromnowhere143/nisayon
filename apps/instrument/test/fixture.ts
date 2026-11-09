// Reads the committed development fixture from disk for node-side tests.
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
export const PUBLIC_DIR = join(here, "..", "public");
export const FIXTURE_DIR = join(PUBLIC_DIR, "dev-fixture");

export function readFixture(relative: string): Buffer {
  return readFileSync(join(FIXTURE_DIR, relative));
}

export function readJson(relative: string): unknown {
  return JSON.parse(readFixture(relative).toString("utf8"));
}

export function generationDir(): string {
  const evidence = readJson("evidence.json") as { current: { manifest_path: string } };
  return dirname(evidence.current.manifest_path);
}

export function listPublic(): string[] {
  return readdirSync(PUBLIC_DIR);
}

// A fetch over the public directory, rooted at http://fixture.test/.
export const REPO_ROOT = join(here, "..", "..", "..");
export const REAL_DIR = join(REPO_ROOT, "fixtures", "ui", "d01");

// Browser startup owns this DOM before React mounts. Tests use the shipped
// markup so an application handoff cannot silently reintroduce a second loader.
export function installOpening(): HTMLElement {
  document.getElementById("site-opening")?.remove();
  const page = new DOMParser().parseFromString(readFileSync(join(here, "..", "index.html"), "utf8"), "text/html");
  const opening = document.importNode(page.getElementById("site-opening")!, true);
  document.body.appendChild(opening);
  return opening;
}

export function readRealJson(relative: string): unknown {
  return JSON.parse(readFileSync(join(REAL_DIR, relative)).toString("utf8"));
}

// /fixtures/ui/** resolves to the repository's committed exports, everything
// else to the app's public directory, as the Vite middleware does.
export function fetchFromDisk(root = PUBLIC_DIR) {
  return async (input: string, init?: { signal?: AbortSignal }): Promise<Response> => {
    if (init?.signal?.aborted) throw new DOMException("aborted", "AbortError");
    const url = new URL(input);
    const pathname = decodeURIComponent(url.pathname);
    const path = pathname.startsWith("/fixtures/ui/") ? join(REPO_ROOT, pathname) : join(root, pathname);
    try {
      const bytes = readFileSync(path);
      return new Response(new Uint8Array(bytes), { status: 200 });
    } catch {
      return new Response("not found", { status: 404 });
    }
  };
}
