// JSON.parse silently keeps the last duplicate key and accepts overflowing
// numbers. Audit those wire ambiguities before using its native parser.
export function strictParseJson(text: string): unknown {
  const containers: (Set<string> | null)[] = [];
  const numeric = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;
  let i = 0;
  while (i < text.length) {
    const code = text.charCodeAt(i);
    if (code === 34) {
      const start = i;
      // indexOf skips long base64/string payloads without a recursive regexp.
      for (;;) {
        i = text.indexOf('"', i + 1);
        if (i < 0) throw new SyntaxError("Unterminated JSON string");
        let slashes = 0;
        for (let p = i - 1; p >= start && text.charCodeAt(p) === 92; p--) slashes++;
        if (slashes % 2 === 0) break;
      }
      i++;
      let next = i;
      while ([9, 10, 13, 32].includes(text.charCodeAt(next))) next++;
      if (text.charCodeAt(next) === 58) {
        const keys = containers[containers.length - 1];
        if (!keys) throw new SyntaxError("JSON key outside an object");
        const key: string = JSON.parse(text.slice(start, i));
        if (keys.has(key)) throw new SyntaxError(`Duplicate JSON key ${JSON.stringify(key)}`);
        keys.add(key);
      }
    } else if (code === 123 || code === 91) {
      if (containers.length >= 64) throw new SyntaxError("JSON nesting exceeds 64 containers");
      containers.push(code === 123 ? new Set() : null);
      i++;
    } else if (code === 125 || code === 93) {
      containers.pop();
      i++;
    } else if (code === 45 || (code >= 48 && code <= 57)) {
      numeric.lastIndex = i;
      const token = numeric.exec(text)?.[0];
      if (!token) throw new SyntaxError("Invalid JSON number");
      const value = Number(token);
      if (!Number.isFinite(value)) throw new SyntaxError("Non-finite JSON number");
      if (!/[.eE]/.test(token) && !Number.isSafeInteger(value)) throw new SyntaxError("Unsafe JSON integer");
      i = numeric.lastIndex;
    } else i++;
  }
  return JSON.parse(text);
}
