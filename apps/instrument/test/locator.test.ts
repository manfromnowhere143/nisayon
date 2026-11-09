import { describe, expect, it } from "vitest";
import { DEFAULT_EVIDENCE, formatLocator, parseLocator } from "../src/state/locator";
import type { Moment } from "../src/model/types";

const moment: Moment = {
  generation_sha256: "a".repeat(64),
  case_key: "D01-gripper-sign-B.diagnostic",
  run: { bundle_sha256: "b".repeat(64), run_id: "regression-0" },
  row_index: 20,
  phase: "before",
  clock: "simulation",
};

describe("locator", () => {
  it("round-trips a pinned moment and depth", () => {
    const search = formatLocator(moment, "fork", DEFAULT_EVIDENCE);
    const parsed = parseLocator(search);
    expect(parsed.problems).toEqual([]);
    expect(parsed.generation).toBe(moment.generation_sha256);
    expect(parsed.caseKey).toBe(moment.case_key);
    expect(parsed.run).toEqual(moment.run);
    expect(parsed.row).toBe(20);
    expect(parsed.phase).toBe("before");
    expect(parsed.depth).toBe("fork");
    expect(parsed.evidence).toBeNull();
  });

  it("keeps a non-default evidence path", () => {
    const parsed = parseLocator(formatLocator(moment, "moment", "dev-fixture-corrupt-child/evidence.json"));
    expect(parsed.evidence).toBe("dev-fixture-corrupt-child/evidence.json");
  });

  it("reports invalid values instead of guessing", () => {
    const parsed = parseLocator("?g=nothex&i=-3&p=middle&d=tabs&b=zz&evidence=../x.json");
    expect(parsed.generation).toBeNull();
    expect(parsed.row).toBeNull();
    expect(parsed.phase).toBeNull();
    expect(parsed.depth).toBeNull();
    expect(parsed.run).toBeNull();
    expect(parsed.evidence).toBeNull();
    expect(parsed.problems.length).toBe(6);
  });

  it("requires both halves of a run key", () => {
    expect(parseLocator("?r=reference-0").problems).toEqual(["a run locator needs both b (bundle SHA-256) and r (run id)"]);
  });
});
