// Inspect authored scientific SVGs without claiming a browser or GPU review.
// Run from apps/instrument. Requires the local rsvg-convert executable.
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";

const destination = process.argv[2];
if (!destination)
  throw new Error("Supply an output directory for the vector review.");
const out = resolve(destination);
mkdirSync(out, { recursive: true });
const server = await createServer({
  server: { middlewareMode: true },
  appType: "custom",
});
try {
  const { SystemDiagram, InvestigationDiagram } = await server.ssrLoadModule(
    "/src/research/Diagrams.tsx",
  );
  const { CATALOG_SHA } = await server.ssrLoadModule(
    "/src/research/catalogPin.ts",
  );
  const { readResearchRoute } = await server.ssrLoadModule(
    "/src/research/navigation.ts",
  );
  const catalog = JSON.parse(
    readFileSync(`public/research/${CATALOG_SHA}/catalog.json`, "utf8"),
  );
  const css =
    readFileSync("src/styles/research.css", "utf8") +
    readFileSync("src/styles/instrument.css", "utf8");
  const files = [];
  for (const theme of ["black", "paper"])
    for (const variant of ["original", "corrected"]) {
      const colors =
        theme === "black"
          ? {
              "--ground": "#050506",
              "--ink": "#ffffff",
              "--research-secondary": "#ffffff",
              "--research-muted": "#ffffff",
              "--research-rule": "#3b3c40",
              "--research-surface": "#0c0d0f",
              "--selected": "#242426",
              "--correction": "#8fb0d6",
              "--rejected": "#d0625d",
              "--unresolved": "#d1a24a",
            }
          : {
              "--ground": "#f4f2ec",
              "--ink": "#17171a",
              "--research-secondary": "#4b4d50",
              "--research-muted": "#626367",
              "--research-rule": "#c6c4c0",
              "--research-surface": "#eeece6",
              "--selected": "#dfddd8",
              "--correction": "#3f6087",
              "--rejected": "#a33a36",
              "--unresolved": "#8a6a1f",
            };
      const style = css.replace(/var\((--[\w-]+)\)/g, (_, key) =>
        key === "--mono" ? "Menlo, monospace" : colors[key] || "#888888",
      );
      const entries = [
        ["system", createElement(SystemDiagram, { active: 0 })],
        ...catalog.cases.map((entry) => [
          entry.id,
          createElement(InvestigationDiagram, {
            entry,
            route: { ...readResearchRoute("", false), variant },
            select: () => {},
          }),
        ]),
      ];
      for (const [name, element] of entries) {
        const document = new JSDOM(renderToStaticMarkup(element)).window
          .document;
        const svg = document.querySelector("svg");
        if (!svg) continue;
        const box = svg.getAttribute("viewBox").split(" ").map(Number);
        svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        svg.setAttribute("width", String(box[2]));
        svg.setAttribute("height", String(box[3]));
        svg.setAttribute("color", colors["--ink"]);
        svg.setAttribute(
          "style",
          `width:${box[2]}px;height:${box[3]}px;flex:none`,
        );
        svg.insertAdjacentHTML(
          "afterbegin",
          `<style>${style}svg{font-family:Helvetica,Arial,sans-serif}</style><rect width="100%" height="100%" fill="${colors["--ground"]}"/>`,
        );
        const stem = `${name}-${theme}-${variant}`,
          path = join(out, stem + ".svg");
        writeFileSync(path, svg.outerHTML);
        execFileSync("rsvg-convert", ["-o", join(out, stem + ".png"), path]);
        files.push(stem);
      }
    }
  writeFileSync(
    join(out, "manifest.json"),
    JSON.stringify(
      {
        renderer: "React static SVG + librsvg; not browser screenshots",
        catalog: CATALOG_SHA,
        files,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    `Rendered ${files.length} diagram states. These are not browser screenshots.`,
  );
} finally {
  await server.close();
}
