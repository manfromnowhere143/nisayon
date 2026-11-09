/** Lossless inspection of SDK records. Numeric spelling is evidence, not formatting. */
export class JsonNumber {
  constructor(readonly raw: string) {}
}
export type Json = null | boolean | string | JsonNumber | Json[] | { [key: string]: Json };
export type JsonObject = { [key: string]: Json };

export function parseRecord(source: string): Json {
  let at = 0, nodes = 0;
  const whitespace = () => { while (/[\x20\t\r\n]/.test(source[at] ?? "x")) at++; };
  const fail = (): never => { throw new Error(`Invalid JSON record at character ${at}.`); };
  const string = (): string => {
    const start = at++;
    while (at < source.length) {
      const char = source[at++];
      if (char === '"') {
        try { return JSON.parse(source.slice(start, at)) as string; } catch { return fail(); }
      }
      if (char === "\\") at++;
    }
    return fail();
  };
  const value = (depth: number): Json => {
    if (depth > 64 || ++nodes > 500_000) throw new Error("This record exceeds the supported inspection depth or size.");
    whitespace();
    const char = source[at];
    if (char === '"') return string();
    if (char === "{") {
      at++; whitespace();
      const result: JsonObject = Object.create(null);
      if (source[at] === "}") { at++; return result; }
      for (;;) {
        whitespace();
        if (source[at] !== '"') return fail();
        const key = string();
        if (Object.hasOwn(result, key)) throw new Error("This record contains a duplicate JSON field.");
        whitespace();
        if (source[at++] !== ":") return fail();
        result[key] = value(depth + 1); whitespace();
        const end = source[at++];
        if (end === "}") return result;
        if (end !== ",") return fail();
      }
    }
    if (char === "[") {
      at++; whitespace();
      const result: Json[] = [];
      if (source[at] === "]") { at++; return result; }
      for (;;) {
        result.push(value(depth + 1)); whitespace();
        const end = source[at++];
        if (end === "]") return result;
        if (end !== ",") return fail();
      }
    }
    for (const [literal, result] of [["true", true], ["false", false], ["null", null]] as const) {
      if (source.startsWith(literal, at)) { at += literal.length; return result; }
    }
    const numeric = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;
    numeric.lastIndex = at;
    const token = numeric.exec(source)?.[0];
    if (!token || token.length > 4096) return fail();
    at = numeric.lastIndex;
    return new JsonNumber(token);
  };
  const result = value(0); whitespace();
  if (at !== source.length) return fail();
  return result;
}

export function object(value: Json | undefined, name = "record"): JsonObject {
  if (value === null || typeof value !== "object" || Array.isArray(value) || value instanceof JsonNumber) throw new Error(`The ${name} must be an object.`);
  return value;
}
export function string(value: Json | undefined, name = "field"): string {
  if (typeof value !== "string") throw new Error(`The ${name} must be text.`);
  return value;
}
export function array(value: Json | undefined, name = "field"): Json[] {
  if (!Array.isArray(value)) throw new Error(`The ${name} must be a list.`);
  return value;
}
export function count(value: Json | undefined, max: number): number {
  if (!(value instanceof JsonNumber) || !/^(0|[1-9]\d*)$/.test(value.raw)) throw new Error("Invalid record length.");
  const result = Number(value.raw);
  if (!Number.isSafeInteger(result) || result > max) throw new Error("Record length exceeds the supported bound.");
  return result;
}
export function display(value: Json | undefined): string {
  if (value === undefined) return "Not retained";
  if (value instanceof JsonNumber) return value.raw;
  if (Array.isArray(value)) return `[${value.map(display).join(", ")}]`;
  if (value !== null && typeof value === "object") return `{${Object.entries(value).map(([k, v]) => `${JSON.stringify(k)}: ${display(v)}`).join(", ")}}`;
  return JSON.stringify(value);
}
export function atPointer(value: Json | undefined, pointer: string): Json | undefined {
  if (pointer === "") return value;
  if (!pointer.startsWith("/")) return undefined;
  let current = value;
  for (const part of pointer.slice(1).split("/")) {
    const key = part.replace(/~1/g, "/").replace(/~0/g, "~");
    if (current === null || typeof current !== "object" || current instanceof JsonNumber) return undefined;
    if (Array.isArray(current)) {
      if (!/^(0|[1-9]\d*)$/.test(key)) return undefined;
      current = current[Number(key)];
    } else current = Object.hasOwn(current, key) ? current[key] : undefined;
  }
  return current;
}
