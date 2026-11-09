import { expect, it, vi } from "vitest";
import { createHash } from "node:crypto";
import { InstrumentStore } from "../src/state/store";
import { parseLocator } from "../src/state/locator";
import { initialStudyRoute, parseStudyRoute, studyRouteParams } from "../src/state/studyRoute";
import { discoverStudy, loadStudy, loadStudyTrial } from "../src/data/study";
import { openLibrary } from "../src/data/library";
import { diagnosticSceneLink, loadStudyScenes, studySceneLink } from "../src/data/studyScenes";
import { decisivePair } from "../src/ui/StudyObligations";
import { fetchFromDisk } from "./fixture";

const options = { fetch: fetchFromDisk(), digest: async (bytes: ArrayBuffer) => createHash("sha256").update(new Uint8Array(bytes)).digest("hex"), maxBytes: 16 * 1024 * 1024 };

it("preserves the full investigation in shared links, including the closed study on a robot replay", () => {
  const route = { ...initialStudyRoute("development-ablation-001/D05-recurrent-carry/A"), open: false, pin: { sha256: "a".repeat(64), byte_length: 12000, path: `generations/${"a".repeat(64)}.json`, media_type: null, kind: null }, pair: "b".repeat(64), execution: "confirmation-correction-10423", section: "pairs" as const };
  const problems: string[] = [];
  expect(parseStudyRoute(new URLSearchParams(studyRouteParams(route)), problems)).toEqual(route);
  expect(problems).toEqual([]);
  expect(parseLocator("?study=bad&study_bytes=4&study_section=unknown&pair=partial").problems).toHaveLength(3);
});

it("joins every available B confirmation scene by retained identities and refuses namesakes and mutated evidence", async () => {
  const study = await loadStudy(await discoverStudy(undefined, options), undefined, options), library = await openLibrary(options);
  let links = 0;
  for (const entry of study.trials.filter(t => t.arm === "B")) {
    const trial = await loadStudyTrial(entry, undefined, options);
    const scenes = await loadStudyScenes(entry.key, library, new AbortController().signal, options);
    if (!scenes || !trial.confirmation) continue;
    expect(diagnosticSceneLink(scenes, trial)).not.toBeNull();
    for (const record of trial.confirmation.observations) {
      const link = studySceneLink(scenes, trial, record);
      if (!link) continue;
      links++;
      expect(parseLocator(new URL(link.url, location.href).search).run?.run_id).toBe(record.run_id);
      expect(studySceneLink(scenes, { ...trial, arm: "A" }, record)).toBeNull();
      expect(studySceneLink(scenes, trial, { ...record, configuration_sha256: "0".repeat(64) })).toBeNull();
      expect(studySceneLink(scenes, trial, { ...record, artifacts: [] })).toBeNull();
    }
  }
  expect(links).toBe(268);
});

it("opens D05's actual decisive condition without treating matched binary outcomes as sufficient progress", async () => {
  const study = await loadStudy(await discoverStudy(undefined, options), undefined, options);
  const trial = await loadStudyTrial(study.trials.find(t => t.case_id === "D05-recurrent-carry" && t.arm === "A")!, undefined, options);
  const pair = decisivePair(trial);
  expect(pair?.candidate.run_id).toBe("confirmation-correction-10423");
  expect(trial.historical_decision?.decision).toBe("rejected");
});

it("retains the study pin and pair across scene navigation, return, reload and browser history", async () => {
  const store = new InstrumentStore(options);
  try {
    await store.open(parseLocator("?evidence=fixtures/ui/recorded/D03-observation-backlog/evidence.json&i=30&p=before"), "replace");
    const pin = await discoverStudy(undefined, options);
    const route = { ...initialStudyRoute("development-ablation-001/D03-observation-backlog/B"), pin, pair: "b".repeat(64), section: "pairs" as const };
    store.setStudy(route);
    const url = store.currentUrl();
    store.closeStudy();
    expect(store.getState().study).toEqual({ ...route, open: false });
    store.openStudy(); expect(store.getState().study).toEqual(route);
    const study = await loadStudy(pin, undefined, options);
    const trial = await loadStudyTrial(study.trials.find(t => t.key === route.trial)!, undefined, options);
    const scenes = await loadStudyScenes(route.trial, await openLibrary(options), new AbortController().signal, options);
    const link = trial.confirmation!.observations.map(record => studySceneLink(scenes, trial, record)).find(Boolean)!;
    const destination = parseLocator(new URL(link.url, location.href).search);
    store.openStudyScene(link.url);
    await vi.waitFor(() => {
      const replay = store.getState().screen;
      expect(replay.kind === "ready" && replay.run.record.run.run_id).toBe(destination.run!.run_id);
    });
    expect(store.getState().study).toEqual({ ...route, open: false });
    expect(parseLocator(new URL(store.currentUrl()).search).study).toEqual({ ...route, open: false });
    store.openStudy(); expect(store.getState().study).toEqual(route);
    history.replaceState(null, "", url); store.handlePopState();
    await vi.waitFor(() => {
      const returned = store.getState().screen;
      expect(returned.kind === "ready" && returned.moment.row_index).toBe(30);
    });
    expect(store.getState().study).toEqual(route);
    expect(parseLocator(new URL(store.currentUrl()).search).study).toEqual(route);
    const screen = store.getState().screen;
    expect(screen.kind === "ready" && screen.moment.row_index).toBe(30);
  } finally { store.dispose(); }
});
