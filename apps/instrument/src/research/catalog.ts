import { sha256Hex } from "../data/digest";
import { strictParseJson } from "../data/strictJson";

export const CASE_IDS = [
  "transfer",
  "terminal",
  "processors",
  "decisions",
  "routing",
  "cost",
  "competence",
  "deployment",
  "attention",
  "promotion",
  "dispatch",
] as const;
export type CaseId = (typeof CASE_IDS)[number];
export interface Pair {
  seed: number;
  unchanged_success: boolean;
  corrected_success: boolean;
  unchanged_steps: number;
  corrected_steps: number;
}
interface Counts {
  passed: number;
  failed: number;
  error: number;
  skipped: number;
}
interface RoutingCase {
  pushes: {
    rid: number;
    envelope_hex: string[];
    key_hex: string;
    result: string;
  }[];
  pop_order: number[];
  passed: boolean;
}
interface IdentityCounts {
  inputs: number;
  unique_keys: number;
  additional_inputs_colliding: number;
  passed: boolean;
}
export interface DataMap {
  dispatch: {
    baseline: Counts;
    corrected: Counts;
    initial: Counts;
    controls: { name: string; before: string; after: string }[];
    nativeControls: number;
    newControls: number;
    sourceCommit: string;
    contributionCommit: string;
    draft: true;
    witness: {
      readyAt: number;
      dispatchAt: number;
      oldCommand: number;
      newCommand: number;
    };
  };
  promotion: {
    baseline: Counts;
    corrected: Counts;
    controls: { name: string; before: string; after: string }[];
    nativeControls: number;
    sourceCommit: string;
    contributionCommit: string;
    merged: false;
  };
  attention: {
    baseline: Counts;
    corrected: Counts;
    controls: { name: string; before: string; after: string }[];
    trainingState: number;
    originalState: number;
    correctedState: number;
    trainingAction: number;
    originalAction: number;
    correctedAction: number;
    values: number[];
    sourceCommit: string;
    contributionCommit: string;
    draft: boolean;
  };
  transfer: {
    pairs: Pair[];
    inputWitnesses: number;
    unchanged: number;
    corrected: number;
    required: number;
    weightsUnchanged: boolean;
    oldExpression: string;
    newExpression: string;
  };
  terminal: {
    baseline: Counts;
    corrected: Counts;
    invalid: Counts;
    witness: { start: number; terminal: number; reset: number };
    controls: { name: string; before: string; after: string }[];
  };
  processors: {
    baseline: number;
    corrected: number;
    total: number;
    currentState: number;
    staleState: number;
    relativeAction: number;
    actual: number;
    required: number;
    sourceCommit: string;
  };
  decisions: {
    labels: Record<string, string>;
    probes: {
      id: string;
      cost: number;
      predictions: Record<string, number[]>;
    }[];
    outcomes: { hypothesis: string; survivors: string[]; label: string }[];
    fullCost: number;
    decisionCost: number;
    nativeCost: number;
    controls: number;
  };
  routing: {
    original: IdentityCounts;
    corrected: IdentityCounts;
    before: RoutingCase;
    after: RoutingCase;
    sourceCommit: string;
  };
  cost: {
    saving: number;
    extraContexts: number;
    breakEven: number;
    unmeasured: string[];
  };
  competence: {
    successes: number;
    required: number;
    episodes: { seed: number; steps: number; outcome: string }[];
    criteria: Record<string, string>;
  };
  deployment: {
    planned: number;
    executed: number;
    sourceCommit: string;
    controls: Record<string, number>;
    numpy: string;
    rerunNumpy: string;
    lerobot: string;
    rerun: string;
  };
}
interface BaseCase {
  code: string;
  title: string;
  question: string;
  kind: string;
  status: "supported" | "rejected" | "blocked" | "exploratory";
  date: string;
  finding: string;
  mechanism: string;
  limit: string;
  sources: { path: string; sha256: string; bytes: number }[];
  links: { title: string; url: string }[];
}
export type ResearchCase = {
  [K in CaseId]: BaseCase & { id: K; data: DataMap[K] };
}[CaseId];
export interface EngineModule {
  name: string;
  package: string;
  description: string;
  entries: { name: string; kind: string; line: number }[];
  source: { path: string; sha256: string; bytes: number };
}
export interface ResearchCatalog {
  schema:
    | "nisayon.research-catalog.v1"
    | "nisayon.research-catalog.v2"
    | "nisayon.research-catalog.v3"
    | "nisayon.research-catalog.v4";
  asOf: string;
  sourceCommit: string;
  scope: string;
  cases: ResearchCase[];
  modules?: EngineModule[];
  upstream?: {
    title: string;
    status: "merged" | "released";
    date: string;
    url: string;
    source: { path: string; sha256: string; bytes: number };
  }[];
  adoption?: {
    date: string;
    title: string;
    revision: string;
    passed: number;
    unchangedJointOutputs: number;
    scope: string;
    url: string;
    source: { path: string; sha256: string; bytes: number };
  };
}

type RecordValue = Record<string, unknown>;
function check(value: unknown, message: string): asserts value {
  if (!value) throw new Error(`Research evidence: ${message}`);
}
function record(v: unknown): RecordValue {
  check(
    v !== null && typeof v === "object" && !Array.isArray(v),
    "expected an object",
  );
  return v as RecordValue;
}
function list(v: unknown): unknown[] {
  check(Array.isArray(v), "expected an array");
  return v;
}
function strings(v: unknown): void {
  check(
    list(v).every((x) => typeof x === "string"),
    "expected text entries",
  );
}
function textFields(v: RecordValue, keys: string[]): void {
  keys.forEach((k) =>
    check(
      typeof v[k] === "string" && (v[k] as string).length > 0,
      `missing ${k}`,
    ),
  );
}
function numbers(v: RecordValue, keys: string[]): void {
  keys.forEach((k) =>
    check(
      typeof v[k] === "number" &&
        Number.isFinite(v[k]) &&
        (v[k] as number) >= 0,
      `invalid ${k}`,
    ),
  );
}
function integers(v: RecordValue, keys: string[]): void {
  numbers(v, keys);
  keys.forEach((k) => check(Number.isSafeInteger(v[k]), `non-integer ${k}`));
}
function counts(v: unknown): void {
  const o = record(v);
  integers(o, ["passed", "failed", "error", "skipped"]);
}
const SHA = /^[a-f0-9]{64}$/;
function sourceBinding(value: unknown): void {
  const source = record(value);
  textFields(source, ["path", "sha256"]);
  integers(source, ["bytes"]);
  const path = String(source.path);
  check(
    SHA.test(String(source.sha256)) &&
      !path.split("/").some((p) => p === ".." || p === "." || p === "") &&
      !path.includes("\\") &&
      !path.includes("\0"),
    "invalid source binding",
  );
}
function dateValue(value: unknown): void {
  check(
    typeof value === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(value) &&
      new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10) === value,
    "invalid evidence date",
  );
}

export function decodeResearchCatalog(value: unknown): ResearchCatalog {
  const root = record(value);
  check(
    root.schema === "nisayon.research-catalog.v1" ||
      root.schema === "nisayon.research-catalog.v2" ||
      root.schema === "nisayon.research-catalog.v3" ||
      root.schema === "nisayon.research-catalog.v4",
    "unsupported catalog schema",
  );
  textFields(root, ["asOf", "sourceCommit", "scope"]);
  check(
    /^[a-f0-9]{40}$/.test(String(root.sourceCommit)),
    "invalid source revision",
  );
  dateValue(root.asOf);
  const ids = new Set<string>();
  for (const raw of list(root.cases)) {
    const c = record(raw);
    textFields(c, [
      "id",
      "code",
      "title",
      "question",
      "kind",
      "status",
      "date",
      "finding",
      "mechanism",
      "limit",
    ]);
    check(
      CASE_IDS.includes(c.id as CaseId) && !ids.has(String(c.id)),
      "unknown or duplicate investigation",
    );
    ids.add(String(c.id));
    check(
      ["supported", "rejected", "blocked", "exploratory"].includes(
        String(c.status),
      ),
      "invalid result status",
    );
    dateValue(c.date);
    check(list(c.sources).length > 0, "missing source binding");
    for (const rawSource of list(c.sources)) {
      sourceBinding(rawSource);
    }
    for (const rawLink of list(c.links)) {
      const link = record(rawLink);
      textFields(link, ["title", "url"]);
      check(
        new URL(String(link.url)).protocol === "https:",
        "unsafe source URL",
      );
    }
    const d = record(c.data);
    switch (c.id) {
      case "dispatch":
      case "promotion": {
        counts(d.baseline);
        counts(d.corrected);
        textFields(d, ["sourceCommit", "contributionCommit"]);
        const dispatch = c.id === "dispatch";
        const total = dispatch ? 76 : 28;
        check(
          dispatch
            ? d.draft === true &&
                d.nativeControls === 59 &&
                d.newControls === 17
            : d.merged === false && d.nativeControls === 9,
          `${c.id} scope changed`,
        );
        if (dispatch) {
          counts(d.initial);
          const initial = record(d.initial);
          check(
            initial.passed === 67 &&
              initial.failed === 9 &&
              initial.error === 0 &&
              initial.skipped === 0,
            "dispatch initial attempt changed",
          );
          const witness = record(d.witness);
          numbers(witness, [
            "readyAt",
            "dispatchAt",
            "oldCommand",
            "newCommand",
          ]);
          check(
            witness.readyAt === 0.5 &&
              witness.dispatchAt === 1 &&
              witness.oldCommand === 11 &&
              witness.newCommand === 100,
            "dispatch witness changed",
          );
        }
        const controls = list(d.controls).map(record);
        check(
          controls.length === total &&
            new Set(controls.map((c) => c.name)).size === total,
          `${c.id} denominator changed`,
        );
        for (const control of controls) {
          textFields(control, ["name", "before", "after"]);
          check(
            ["passed", "failed"].includes(String(control.before)) &&
              ["passed", "failed"].includes(String(control.after)),
            `invalid ${c.id} outcome`,
          );
        }
        for (const [key, variant] of [
          ["baseline", "before"],
          ["corrected", "after"],
        ] as const) {
          const summary = record(d[key]);
          check(
            controls.filter((c) => c[variant] === "passed").length ===
              summary.passed &&
              controls.filter((c) => c[variant] === "failed").length ===
                summary.failed &&
              summary.error === 0 &&
              summary.skipped === 0,
            `${c.id} control totals disagree`,
          );
        }
        break;
      }
      case "attention": {
        counts(d.baseline);
        counts(d.corrected);
        numbers(d, [
          "trainingState",
          "originalState",
          "correctedState",
          "trainingAction",
          "originalAction",
          "correctedAction",
        ]);
        textFields(d, ["sourceCommit", "contributionCommit"]);
        check(d.draft === true, "contribution status changed");
        check(
          list(d.values).length === 4 &&
            list(d.values).every(
              (v) => typeof v === "number" && Number.isFinite(v),
            ),
          "attention fixture changed",
        );
        check(
          list(d.values).reduce<number>((sum, v) => sum + Number(v), 0) / 4 ===
            d.originalState &&
            list(d.values)[3] === d.trainingState &&
            d.correctedState === d.trainingState &&
            d.correctedAction === d.trainingAction,
          "attention witnesses disagree",
        );
        const controls = list(d.controls).map(record);
        check(controls.length === 26, "attention denominator changed");
        for (const [key, variant] of [
          ["baseline", "before"],
          ["corrected", "after"],
        ] as const) {
          const summary = record(d[key]);
          check(
            controls.filter((x) => x[variant] === "passed").length ===
              summary.passed &&
              controls.filter((x) => x[variant] === "failed").length ===
                summary.failed &&
              summary.error === 0 &&
              summary.skipped === 0,
            "attention control totals disagree",
          );
        }
        for (const control of controls)
          textFields(control, ["name", "before", "after"]);
        break;
      }
      case "transfer": {
        integers(d, ["inputWitnesses", "unchanged", "corrected", "required"]);
        textFields(d, ["oldExpression", "newExpression"]);
        check(
          typeof d.weightsUnchanged === "boolean",
          "missing weight comparison",
        );
        const pairs = list(d.pairs).map(record);
        check(pairs.length === 10, "transfer denominator changed");
        for (const p of pairs) {
          integers(p, ["seed", "unchanged_steps", "corrected_steps"]);
          check(
            typeof p.unchanged_success === "boolean" &&
              typeof p.corrected_success === "boolean",
            "missing paired outcome",
          );
          check(
            Number(p.unchanged_steps) <= 400 &&
              Number(p.corrected_steps) <= 400,
            "control horizon changed",
          );
        }
        check(
          Number(d.required) <= pairs.length,
          "acceptance threshold exceeds denominator",
        );
        check(
          new Set(pairs.map((p) => p.seed)).size === pairs.length,
          "duplicate paired condition",
        );
        check(
          pairs.filter((p) => p.corrected_success).length === d.corrected &&
            pairs.filter((p) => p.unchanged_success).length === d.unchanged,
          "paired totals disagree",
        );
        break;
      }
      case "terminal": {
        counts(d.baseline);
        counts(d.corrected);
        counts(d.invalid);
        numbers(record(d.witness), ["start", "terminal", "reset"]);
        const controls = list(d.controls).map(record);
        for (const x of controls) {
          textFields(x, ["name", "before", "after"]);
          check(
            ["passed", "failed"].includes(String(x.before)) &&
              ["passed", "failed"].includes(String(x.after)),
            "unsupported control outcome",
          );
        }
        check(
          new Set(controls.map((x) => x.name)).size === controls.length,
          "duplicate control",
        );
        for (const [key, variant] of [
          ["baseline", "before"],
          ["corrected", "after"],
        ] as const) {
          const summary = record(d[key]);
          check(
            controls.filter((x) => x[variant] === "passed").length ===
              summary.passed &&
              controls.filter((x) => x[variant] === "failed").length ===
                summary.failed &&
              summary.error === 0 &&
              summary.skipped === 0,
            "control totals disagree",
          );
        }
        break;
      }
      case "processors":
        integers(d, ["baseline", "corrected", "total"]);
        numbers(d, [
          "currentState",
          "staleState",
          "relativeAction",
          "actual",
          "required",
        ]);
        textFields(d, ["sourceCommit"]);
        check(
          Number(d.baseline) <= Number(d.total) &&
            Number(d.corrected) <= Number(d.total),
          "processor totals disagree",
        );
        break;
      case "decisions":
        numbers(d, ["fullCost", "decisionCost", "nativeCost", "controls"]);
        check(
          Object.values(record(d.labels)).every((x) => typeof x === "string"),
          "invalid decision labels",
        );
        for (const rawProbe of list(d.probes)) {
          const p = record(rawProbe);
          textFields(p, ["id"]);
          numbers(p, ["cost"]);
          check(
            Object.values(record(p.predictions)).every((v) =>
              list(v).every((n) => typeof n === "number" && Number.isFinite(n)),
            ),
            "invalid prediction",
          );
        }
        for (const rawOutcome of list(d.outcomes)) {
          const o = record(rawOutcome);
          textFields(o, ["hypothesis", "label"]);
          strings(o.survivors);
          check(
            list(o.survivors).length > 0 &&
              list(o.survivors).every(
                (h) => record(d.labels)[String(h)] === o.label,
              ) &&
              record(d.labels)[String(o.hypothesis)] === o.label,
            "decision labels disagree",
          );
        }
        check(list(d.outcomes).length > 0, "missing constructed outcomes");
        break;
      case "routing":
        for (const key of ["original", "corrected"]) {
          const c = record(d[key]);
          integers(c, ["inputs", "unique_keys", "additional_inputs_colliding"]);
          check(
            Number(c.unique_keys) + Number(c.additional_inputs_colliding) ===
              c.inputs,
            "identity totals disagree",
          );
        }
        for (const key of ["before", "after"]) {
          const run = record(d[key]);
          check(
            list(run.pop_order).every((n) => Number.isSafeInteger(n)),
            "invalid queue order",
          );
          for (const rawPush of list(run.pushes)) {
            const p = record(rawPush);
            numbers(p, ["rid"]);
            textFields(p, ["key_hex", "result"]);
            strings(p.envelope_hex);
          }
        }
        textFields(d, ["sourceCommit"]);
        break;
      case "cost":
        numbers(d, ["saving", "extraContexts", "breakEven"]);
        strings(d.unmeasured);
        break;
      case "competence":
        integers(d, ["successes", "required"]);
        check(
          Object.values(record(d.criteria)).every((x) => x === "pass"),
          "runtime qualification changed",
        );
        for (const rawEpisode of list(d.episodes)) {
          const e = record(rawEpisode);
          integers(e, ["seed", "steps"]);
          check(
            ["success", "task_failure"].includes(String(e.outcome)),
            "unsupported task outcome",
          );
        }
        check(list(d.episodes).length === 10, "competence denominator changed");
        check(
          list(d.episodes).filter((e) => record(e).outcome === "success")
            .length === d.successes && Number(d.required) <= 10,
          "competence totals disagree",
        );
        break;
      case "deployment":
        integers(d, ["planned", "executed"]);
        check(
          Number(d.executed) <= Number(d.planned),
          "executed tests exceed planned tests",
        );
        textFields(d, [
          "sourceCommit",
          "numpy",
          "rerunNumpy",
          "lerobot",
          "rerun",
        ]);
        check(
          Object.values(record(d.controls)).every((x) => x === 0 || x === 1),
          "invalid resolver exit",
        );
        break;
    }
  }
  const required =
    root.schema === "nisayon.research-catalog.v1"
      ? CASE_IDS.filter(
          (id) => !["attention", "promotion", "dispatch"].includes(id),
        )
      : root.schema === "nisayon.research-catalog.v2"
        ? CASE_IDS.filter((id) => !["promotion", "dispatch"].includes(id))
        : root.schema === "nisayon.research-catalog.v3"
          ? CASE_IDS.filter((id) => id !== "dispatch")
          : CASE_IDS;
  check(
    ids.size === required.length && required.every((id) => ids.has(id)),
    "incomplete catalog",
  );
  if (root.modules !== undefined)
    for (const rawModule of list(root.modules)) {
      const m = record(rawModule);
      textFields(m, ["name", "package", "description"]);
      sourceBinding(m.source);
      for (const rawEntry of list(m.entries)) {
        const e = record(rawEntry);
        textFields(e, ["name", "kind"]);
        integers(e, ["line"]);
      }
    }
  if (root.adoption !== undefined) {
    const a = record(root.adoption);
    textFields(a, ["date", "title", "revision", "scope", "url"]);
    integers(a, ["passed", "unchangedJointOutputs"]);
    dateValue(a.date);
    check(new URL(String(a.url)).protocol === "https:", "unsafe adoption URL");
    sourceBinding(a.source);
  }
  if (root.upstream !== undefined) {
    check(list(root.upstream).length <= 8, "too many upstream records");
    for (const raw of list(root.upstream)) {
      const item = record(raw);
      textFields(item, ["title", "status", "date", "url"]);
      check(
        ["merged", "released"].includes(String(item.status)),
        "unaccepted upstream change",
      );
      dateValue(item.date);
      sourceBinding(item.source);
      check(
        new URL(String(item.url)).protocol === "https:",
        "unsafe upstream URL",
      );
    }
  }
  return value as ResearchCatalog;
}

export const catalogUrl = (sha: string): string =>
  `research/${sha}/catalog.json`;
export async function loadResearchCatalog(
  sha: string,
  signal: AbortSignal,
  fetcher = fetch,
  digest = sha256Hex,
): Promise<ResearchCatalog> {
  check(SHA.test(sha), "invalid catalog identity");
  const response = await fetcher(catalogUrl(sha), {
    signal,
    cache: "force-cache",
  });
  check(response.ok, `catalog unavailable (HTTP ${response.status})`);
  const declared = Number(response.headers.get("content-length") ?? 0);
  check(
    Number.isFinite(declared) && declared <= 1_000_000,
    "catalog exceeds the read limit",
  );
  const reader = response.body?.getReader();
  let bytes: ArrayBuffer;
  if (reader) {
    const chunks: Uint8Array[] = [];
    let total = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        total += value.byteLength;
        if (total > 1_000_000) {
          await reader.cancel();
          check(false, "catalog exceeds the read limit");
        }
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    const joined = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      joined.set(chunk, offset);
      offset += chunk.byteLength;
    }
    bytes = joined.buffer;
  } else bytes = await response.arrayBuffer();
  check(bytes.byteLength <= 1_000_000, "catalog exceeds the read limit");
  check(
    (await digest(bytes)) === sha,
    "catalog digest does not match this pinned selection",
  );
  return decodeResearchCatalog(
    strictParseJson(new TextDecoder("utf-8", { fatal: true }).decode(bytes)),
  );
}
