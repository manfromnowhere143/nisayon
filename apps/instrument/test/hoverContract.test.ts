import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import postcss, { type AnyNode } from "postcss";
import { expect, it } from "vitest";

it("requires capability and actual-input guards on every hover selector, including lazy routes", () => {
  const violations: string[] = [];
  const directory = resolve("src");
  for (const file of readdirSync(directory, { recursive: true, encoding: "utf8" }).filter(name => name.endsWith(".css"))) {
    const root = postcss.parse(readFileSync(resolve(directory, file), "utf8"));
    root.walkRules(rule => {
      for (const selector of rule.selectors.filter(s => s.includes(":hover"))) {
        let capability = false;
        for (let parent: AnyNode | undefined = rule.parent; parent; parent = parent.parent) {
          if (parent.type === "atrule" && parent.name === "media" && /\(hover:\s*hover\)/.test(parent.params) && /\(pointer:\s*fine\)/.test(parent.params)) capability = true;
        }
        if (!capability || !selector.includes(':root:not([data-pointer-type="touch"])')) violations.push(`${file}:${rule.source?.start?.line} ${selector}`);
      }
    });
  }
  expect(violations).toEqual([]);
});
