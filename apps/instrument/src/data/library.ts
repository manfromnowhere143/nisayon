import { absoluteUrl, directoryOf, readDiscovery, resolveWithin, type LoaderOptions } from "./loader";
import { arr, DecodeError, fileRef, rec, str } from "../model/decode";

export const LIBRARY_URL = "fixtures/ui/recorded/library.json";
export interface LibraryCase { caseKey: string; caseId: string; evidence: string; generation: string }

export async function openLibrary(options: LoaderOptions, signal?: AbortSignal, libraryUrl = LIBRARY_URL): Promise<LibraryCase[]> {
  const url = absoluteUrl(libraryUrl);
  const doc = rec(await readDiscovery(url, signal, options), "library");
  if (doc.schema !== "nisayon.ui-library.v1") throw new DecodeError("library.schema", "unsupported library");
  const seen = new Set<string>();
  return arr(doc.cases, "library.cases", 128).map((value, i) => {
    const path = `library.cases[${i}]`;
    const item = rec(value, path);
    const directory = str(item.directory, `${path}.directory`);
    if (!/^[A-Za-z0-9_-]+$/.test(directory)) throw new DecodeError(path, "invalid case directory");
    const caseKey = str(item.case_key, `${path}.case_key`);
    if (seen.has(caseKey)) throw new DecodeError(path, "duplicate case key");
    seen.add(caseKey);
    const manifest = fileRef(item.manifest, `${path}.manifest`);
    if (manifest.path !== `generations/${manifest.sha256}.json`) throw new DecodeError(path, "manifest path must identify its digest");
    resolveWithin(directoryOf(url), `${directory}/evidence.json`, "evidence");
    return { caseKey, caseId: str(item.case_id, `${path}.case_id`), evidence: `fixtures/ui/recorded/${directory}/evidence.json`, generation: manifest.sha256 };
  });
}
