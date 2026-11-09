// @vitest-environment node
import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import { expect, it, vi } from "vitest";
import { hydrateBundle, inspectBundle } from "../src/qualification/bundle";

vi.stubGlobal("crypto", webcrypto);
const bytes = (outcome: string) => new Uint8Array(readFileSync(new URL(`./fixtures/qualification/sdk-v2-${outcome}.nisayon.zip`, import.meta.url))).buffer;

it.each([["accepted", "adopt"], ["rejected", "reject"]])("opens the installed current SDK's actual %s result", async (name, decision) => {
  const result = await inspectBundle(bytes(name!), `${name}.nisayon.zip`);
  expect(result.plan.schema).toBe("nisayon.qualification.plan.v2");
  expect(result.plan.read_policy).toBe("cpython_owner_reads_v1");
  expect(result.assessment.software_decision).toBe(decision);
  expect(result.assessment.deployment_decision).toBe("unresolved");
  expect(result.comparisons).toHaveLength(2);
});

it.each(["future_reader", null])("refuses an unsupported version-2 read policy %s", async policy => {
  const result = await inspectBundle(bytes("accepted"), "accepted.nisayon.zip");
  const files = new Map(result.files);
  const plan = JSON.parse(new TextDecoder().decode(files.get("evidence/plan.json")));
  plan.read_policy = policy;
  files.set("evidence/plan.json", new TextEncoder().encode(JSON.stringify(plan)));
  expect(() => hydrateBundle(files, result.sha256, result.fileName, result.planSha256)).toThrow("read observation policy");
});
