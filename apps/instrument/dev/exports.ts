import { createReadStream, realpathSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { extname, isAbsolute, join, relative, sep } from "node:path";

// Local dev/preview serves only the admitted export directory. Resolve symlinks
// and path segments before opening a file; sibling names are not descendants.
export function serveExports(directory: string) {
  const root = realpathSync(directory);
  return (req: IncomingMessage, res: ServerResponse, next: () => void): void => {
    const prefix = "/fixtures/ui/";
    if (!req.url?.startsWith(prefix)) return next();
    const fail = (status = 404) => { res.statusCode = status; res.end(status === 400 ? "invalid path" : "not found"); };
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.setHeader("Allow", "GET, HEAD");
      res.statusCode = 405; res.end("method not allowed"); return;
    }
    let name: string;
    try { name = decodeURIComponent(req.url.split("?")[0]!).slice(prefix.length); }
    catch { fail(400); return; }
    if (name.includes("\\") || name.includes("\0") || name.split("/").some((part) => !part || part === "." || part === "..")) { fail(); return; }
    let target: string;
    let size: number;
    try {
      target = realpathSync(join(root, name));
      const within = relative(root, target);
      if (!within || isAbsolute(within) || within === ".." || within.startsWith(`..${sep}`)) { fail(); return; }
      const stat = statSync(target);
      if (!stat.isFile()) { fail(); return; }
      size = stat.size;
    } catch { fail(); return; }
    const extension = extname(target);
    res.setHeader("Content-Type", extension === ".json" ? "application/json; charset=utf-8" : extension === ".txt" ? "text/plain; charset=utf-8" : "application/octet-stream");
    res.setHeader("Content-Length", size);
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Cache-Control", /(?:^|\/)(?:objects|generations)\/[0-9a-f]{64}\.json$/.test(name) ? "public, max-age=31536000, immutable" : "no-cache");
    if (req.method === "HEAD") { res.end(); return; }
    const stream = createReadStream(target);
    stream.on("error", () => { if (res.headersSent) res.destroy(); else { res.removeHeader("Content-Length"); fail(); } });
    res.on("close", () => stream.destroy());
    stream.pipe(res);
  };
}
