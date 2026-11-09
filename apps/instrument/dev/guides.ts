import type { Plugin, ViteDevServer } from "vite";

// Mirror production's explicit document routes. Vite's SPA fallback otherwise
// returns the instrument shell for a directory in public/, hiding the guide.
export function guidesPlugin(): Plugin {
  const install = (server: Pick<ViteDevServer, "middlewares">) => {
    server.middlewares.use((request, response, next) => {
      const [path, query] = (request.url ?? "").split("?", 2);
      const redirect = /^\/(about|sdk|portable-review)(?:\/index\.html)?$/.exec(path!);
      if (redirect) {
        response.statusCode = 308;
        response.setHeader("Location", `/${redirect[1]}/`);
        response.end(); return;
      }
      const guide = /^\/(about|sdk|portable-review)\/$/.exec(path!);
      if (guide) request.url = `/${guide[1]}/index.html${query ? `?${query}` : ""}`;
      next();
    });
  };
  return { name: "nisayon-public-guides", configureServer: install, configurePreviewServer: install };
}
