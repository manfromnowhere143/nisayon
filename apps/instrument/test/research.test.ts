import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import {
  CASE_IDS,
  decodeResearchCatalog,
  loadResearchCatalog,
} from "../src/research/catalog";
import { CATALOG_SHA } from "../src/research/catalogPin";
import { readResearchRoute, researchHash } from "../src/research/navigation";
import { PUBLIC_DIR } from "./fixture";

const raw = readFileSync(
  join(PUBLIC_DIR, "research", CATALOG_SHA, "catalog.json"),
);
export const catalog = decodeResearchCatalog(JSON.parse(raw.toString("utf8")));
const digest = async (bytes: ArrayBuffer) =>
  createHash("sha256").update(new Uint8Array(bytes)).digest("hex");
const signal = () => new AbortController().signal;

it("retains the dispatch setup amendment, exact witness and unchanged native controls", () => {
  const entry = catalog.cases.find((c) => c.id === "dispatch")!;
  expect(entry.data.initial.passed).toBe(67);
  expect(entry.data.baseline.passed).toBe(69);
  expect(entry.data.corrected.passed).toBe(76);
  expect(entry.data.nativeControls).toBe(59);
  expect(entry.data.witness).toEqual({
    readyAt: 0.5,
    dispatchAt: 1,
    oldCommand: 11,
    newCommand: 100,
  });
  const changed = structuredClone(catalog);
  changed.cases.find((c) => c.id === "dispatch")!.data.corrected.passed = 152;
  expect(() => decodeResearchCatalog(changed)).toThrow(
    "dispatch control totals disagree",
  );
});

it("keeps promotion controls and accepted upstream statuses distinct from proposed contributions", () => {
  const promotion = catalog.cases.find((c) => c.id === "promotion")!;
  expect(promotion.data.baseline.passed).toBe(17);
  expect(promotion.data.corrected.passed).toBe(28);
  expect(promotion.data.nativeControls).toBe(9);
  expect(promotion.data.merged).toBe(false);
  expect(catalog.upstream?.map((entry) => entry.status)).toEqual([
    "merged",
    "released",
  ]);
  const changed = structuredClone(catalog);
  changed.cases.find((c) => c.id === "promotion")!.data.corrected.passed = 56;
  expect(() => decodeResearchCatalog(changed)).toThrow(
    "promotion control totals disagree",
  );
  const pending = structuredClone(catalog) as unknown as {
    upstream: { status: string }[];
  };
  pending.upstream[0]!.status = "open";
  expect(() => decodeResearchCatalog(pending)).toThrow(
    "unaccepted upstream change",
  );
});

describe("a pinned research projection", () => {
  it("verifies the shipped bytes and preserves failures, invalid attempts and unrun tests", async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response(raw));
    const result = await loadResearchCatalog(
      CATALOG_SHA,
      signal(),
      fetcher,
      digest,
    );
    expect(result.cases.map((c) => c.id)).toEqual([...CASE_IDS]);
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `research/${CATALOG_SHA}/catalog.json`,
    );
    const transfer = result.cases.find((c) => c.id === "transfer")!;
    expect(
      transfer.data.pairs
        .filter((p) => !p.corrected_success)
        .map((p) => p.seed),
    ).toEqual([180104]);
    expect(result.cases.find((c) => c.id === "terminal")!.data.invalid).toEqual(
      { passed: 32, failed: 16, error: 0, skipped: 0 },
    );
    expect(result.cases.find((c) => c.id === "competence")!.status).toBe(
      "rejected",
    );
    expect(result.cases.find((c) => c.id === "deployment")!.data.executed).toBe(
      0,
    );
    expect(result.adoption?.unchangedJointOutputs).toBe(6);
    expect(result.modules?.some((m) => m.name === "confirmation_service")).toBe(
      true,
    );
  });

  it("rejects substituted evidence before displaying its values", async () => {
    const changed = raw
      .toString("utf8")
      .replace('"corrected": 9', '"corrected": 10');
    await expect(
      loadResearchCatalog(
        CATALOG_SHA,
        signal(),
        async () => new Response(changed),
        digest,
      ),
    ).rejects.toThrow("digest does not match");
  });

  it("rejects duplicate JSON keys even when the content hash is correct", async () => {
    const changed = raw
      .toString("utf8")
      .replace('"schema":', '"schema":"unexpected", "schema":');
    const hash = createHash("sha256").update(changed).digest("hex");
    await expect(
      loadResearchCatalog(
        hash,
        signal(),
        async () => new Response(changed),
        digest,
      ),
    ).rejects.toThrow(/duplicate/i);
  });

  it("does not read a missing response or an oversized declared catalog", async () => {
    await expect(
      loadResearchCatalog(
        CATALOG_SHA,
        signal(),
        async () => new Response("", { status: 404 }),
        digest,
      ),
    ).rejects.toThrow("HTTP 404");
    await expect(
      loadResearchCatalog(
        CATALOG_SHA,
        signal(),
        async () =>
          new Response(raw, {
            headers: { "Content-Length": "1000001" },
          }),
        digest,
      ),
    ).rejects.toThrow("read limit");
  });

  it("cancels an oversized stream before hashing or decoding it", async () => {
    const cancel = vi.fn(),
      hash = vi.fn(digest);
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(1_000_001));
      },
      cancel,
    });
    await expect(
      loadResearchCatalog(
        CATALOG_SHA,
        signal(),
        async () => new Response(body),
        hash,
      ),
    ).rejects.toThrow("read limit");
    expect(cancel).toHaveBeenCalledOnce();
    expect(hash).not.toHaveBeenCalled();
  });

  it.each([
    "paired total",
    "native controls",
    "competence",
    "routing identities",
    "decision labels",
  ])("rejects contradictory %s", (kind) => {
    const changed = structuredClone(catalog);
    if (kind === "paired total")
      changed.cases.find((c) => c.id === "transfer")!.data.corrected = 10;
    if (kind === "native controls")
      changed.cases.find((c) => c.id === "terminal")!.data.corrected.skipped =
        1;
    if (kind === "competence")
      changed.cases.find((c) => c.id === "competence")!.data.successes = 2;
    if (kind === "routing identities")
      changed.cases.find((c) => c.id === "routing")!.data.original.unique_keys =
        1464;
    if (kind === "decision labels")
      changed.cases.find((c) => c.id === "decisions")!.data.outcomes[0]!.label =
        "restore_B:confirm_B";
    expect(() => decodeResearchCatalog(changed)).toThrow(/disagree/);
  });

  it("rejects an incomplete catalog and an unsafe source link", () => {
    const missing = structuredClone(catalog);
    missing.cases.pop();
    expect(() => decodeResearchCatalog(missing)).toThrow("incomplete");
    const unsafe = structuredClone(catalog);
    unsafe.cases[0]!.links[0]!.url = "javascript:alert(1)";
    expect(() => decodeResearchCatalog(unsafe)).toThrow("unsafe source URL");
  });
});

describe("research selections and legacy robot links", () => {
  it("opens a new visit on the cinematic home and preserves pre-existing robot links", () => {
    expect(readResearchRoute("", false).surface).toBe("home");
    expect(readResearchRoute("", true).surface).toBe("lab");
    expect(readResearchRoute("#research-content", true).surface).toBe("lab");
  });
  it("round-trips the selected evidence, source variant, failed pair and hypothetical costs", () => {
    const selected = {
      ...readResearchRoute("", false),
      surface: "research" as const,
      caseId: "cost" as const,
      variant: "original" as const,
      sample: 4,
      contextCost: 0.28,
      otherCost: 1.2,
    };
    expect(readResearchRoute(researchHash(selected), true)).toEqual(selected);
    const lab = { ...selected, surface: "lab" as const };
    expect(readResearchRoute(researchHash(lab), true)).toEqual(lab);
  });
  it.each([
    "view=other",
    "view=research&case=unknown",
    "view=research&sample=-1",
    "view=research&variant=best",
    "view=research&catalog=latest",
    "view=research&context=0.51",
    "view=research&work=1.23",
    "view=research&case=terminal&case=transfer",
  ])("keeps an invalid selection explicit: %s", (hash) => {
    expect(readResearchRoute(`#${hash}`, false).issue).not.toBeNull();
  });
});

it("retains the earlier eight-case catalog without silently adding newer evidence", () => {
  const old = decodeResearchCatalog(
    JSON.parse(
      readFileSync(
        join(
          PUBLIC_DIR,
          "research",
          "2729b55de088f12dc26f139d28e8f5b27aceeb207696495fa4da42e36cdf886c",
          "catalog.json",
        ),
        "utf8",
      ),
    ),
  );
  expect(old.schema).toBe("nisayon.research-catalog.v1");
  expect(old.cases).toHaveLength(8);
  expect(old.cases.some((c) => c.id === "attention")).toBe(false);
});

it("preserves the exact attention witnesses and counts one set of 26 exposed fixtures", () => {
  const attention = catalog.cases.find((c) => c.id === "attention")!;
  expect(attention.data.baseline).toEqual({
    passed: 4,
    failed: 22,
    error: 0,
    skipped: 0,
  });
  expect(attention.data.corrected.passed).toBe(26);
  expect(attention.data.originalState).toBe(1.5);
  expect(attention.data.correctedState).toBe(6);
  expect(attention.data.originalAction).toBe(1.125);
  expect(attention.data.trainingAction).toBe(2.25);
  expect(attention.data.draft).toBe(true);
  const changed = structuredClone(catalog);
  changed.cases.find((c) => c.id === "attention")!.data.corrected.passed = 52;
  expect(() => decodeResearchCatalog(changed)).toThrow(
    "attention control totals disagree",
  );
});
