import { useState } from "react";
import { Choice } from "./Choice";

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object";
const escape = (key: string) => key.replaceAll("~", "~0").replaceAll("/", "~1");
export const fieldPointer = (path: readonly string[]) => path.length ? `/${path.map(escape).join("/")}` : "";

// One admitted object at a time, one selected child. An array with thousands
// of entries does not recursively mount thousands of hidden disclosure trees.
// Property names and array indices form exact JSON pointers, including / and ~.
export function FieldNavigator({ value, path: sourcePath = [] }: { value: unknown; path?: readonly string[] }) {
  const [path, setPath] = useState<string[]>([]);
  const [requested, setRequested] = useState("");
  let current = value, missing = false;
  for (const key of path) {
    if (!object(current) || !Object.hasOwn(current, key)) { missing = true; break; }
    current = current[key];
  }
  const keys = !missing && object(current) ? Object.keys(current) : [];
  const selected = keys.includes(requested) ? requested : keys[0];
  const child = selected !== undefined && object(current) ? current[selected] : current;
  const pointer = fieldPointer([...sourcePath, ...path, ...(selected === undefined ? [] : [selected])]);
  return <div className="field-navigator">
    <div className="field-navigation"><button type="button" className="quiet" disabled={!path.length} onClick={() => { setRequested(path.at(-1) ?? ""); setPath(path.slice(0, -1)); }}>← Parent</button><span className="fine">{missing ? "Field absent from this record" : `${keys.length} ${Array.isArray(current) ? "entries" : "fields"}`}</span></div>
    {!missing && keys.length ? <Choice label={`Retained field ${fieldPointer([...sourcePath, ...path]) || "/"}`} value={selected!} options={keys.map(key => ({ value: key, label: Array.isArray(current) ? `[${key}]` : key }))} onChange={setRequested} /> : null}
    <code className="field-pointer">{pointer || "/"}</code>
    {missing ? <p className="fine">Return to the parent to inspect the retained fields.</p> : object(child) && selected !== undefined ? <button type="button" className="field-descend" onClick={() => { setPath([...path, selected]); setRequested(""); }}>Open {Array.isArray(child) ? `${child.length} entries` : `${Object.keys(child).length} fields`} <span aria-hidden="true">→</span></button> : <pre className="field-value">{JSON.stringify(child) ?? "Not recorded"}</pre>}
  </div>;
}
