// @vitest-environment node
import { beforeAll, expect, it, vi } from "vitest";
import { sha256Hex } from "../src/data/digest";
import { ResourceCache, openCase, openGeneration, openRun } from "../src/data/loader";
import { workstationReading, workstationSeries } from "../src/model/workstation";
import { createCanvasDisplay } from "../src/scene/canvasDisplay";
import type { Moment } from "../src/model/types";
import { fetchFromDisk } from "./fixture";

async function load() {
  const options = { fetch: fetchFromDisk(), digest: sha256Hex, maxBytes: 16 * 1024 * 1024 }, cache = new ResourceCache();
  const { generation } = await openGeneration("http://fixture.test/fixtures/ui/recorded/D03-observation-backlog/evidence.json", undefined, options);
  const record = await openCase(generation, generation.cases[0]!.case_key, undefined, options, cache);
  const run = await openRun(generation, record, record.runs.find(r => r.role === "regression")!.run, undefined, options, cache);
  const moment: Moment = { generation_sha256: generation.sha256, case_key: record.case_key, run: run.record.run, row_index: 30, phase: "before", clock: "simulation" };
  return { generation, record, run, moment };
}
let data: Awaited<ReturnType<typeof load>>;
beforeAll(async () => { data = await load(); });

it("binds the desk to the recorded moment and distinguishes action time from the robot's after configuration", () => {
  const { generation, record, run, moment } = data, series = workstationSeries(record, run);
  const before = workstationReading(generation, record, run, moment, series, false);
  const after = workstationReading(generation, record, run, { ...moment, phase: "after" }, series, false);
  expect(series.kind).toBe("age");
  expect(before.value).toBe(run.samples.rows[30]!.observation_age_s! * 1000);
  expect(before.comparison).toBe(record.predicates.max_observation_age_s * 1000);
  expect(before.time).toBe(run.frames!.rows[30]!.before.sim_time_s);
  expect(after.time).toBe(run.frames!.rows[30]!.after.sim_time_s);
  expect(after.signalTime).toBe(before.signalTime);
  expect(after.value).toBe(before.value);
  expect(after.identity).not.toBe(before.identity);
  expect(workstationReading(generation, record, run, moment, series, true)).toMatchObject({ status: "loading", runLabel: before.runLabel, value: before.value });
});

it("refuses mismatched generation, case, bundle, sample identity and missing rows without inventing zero values", () => {
  const { generation, record, run, moment } = data, series = workstationSeries(record, run);
  for (const wrong of [
    { ...moment, generation_sha256: "other" }, { ...moment, case_key: "other" },
    { ...moment, run: { ...moment.run, bundle_sha256: "other" } }, { ...moment, row_index: run.samples.rows.length },
  ]) expect(workstationReading(generation, record, run, wrong, series, false)).toMatchObject({ status: "unavailable", value: null, comparison: null, time: null, signalTime: null });
  const wrongSamples = { ...run, samples: { ...run.samples, run: { ...moment.run, run_id: "other" } } };
  expect(workstationReading(generation, record, wrongSamples, moment, series, false)).toMatchObject({ status: "unavailable", value: null });
  const rows = [...run.samples.rows]; rows[30] = { ...rows[30]!, observation_age_s: null };
  expect(workstationReading(generation, record, { ...run, samples: { ...run.samples, rows } }, moment, series, false).value).toBeNull();
});

it("preserves a one-row spike and a missing-data gap when long traces are reduced for the monitor", () => {
  const { record, run } = data;
  const rows = Array.from({ length: 1000 }, (_, row_index) => ({ ...run.samples.rows[0]!, row_index, step: row_index,
    action_sim_time_s: row_index * .05, next_sim_time_s: (row_index + 1) * .05,
    observation_age_s: row_index === 501 ? 2 : row_index === 502 ? null : 0 }));
  const series = workstationSeries(record, { ...run, samples: { ...run.samples, rows } });
  expect(series.columns.length).toBeLessThanOrEqual(192);
  const spike = series.columns.find(column => column.max === 2000)!;
  expect(spike).toMatchObject({ min: 0, max: 2000, gap: true });
  expect(series.max).toBe(2000);
});

it("coalesces desk updates into the owner's draw, stays idle, restores the selected identity and releases GPU resources", () => {
  const canvas = { width: 0, height: 0, getContext: () => ({}) } as unknown as HTMLCanvasElement;
  const draw = vi.fn(), display = createCanvasDisplay(canvas, 512, "test", draw, (a: { id: string }, b) => a.id === b.id, value => value.id)!;
  const texture = display.material.map!, textureDispose = vi.spyOn(texture, "dispose"), materialDispose = vi.spyOn(display.material, "dispose");
  display.set({ id: "row-1" }); display.set({ id: "row-2" });
  expect(draw).not.toHaveBeenCalled();
  expect(display.flush()).toBe(true); expect(draw.mock.calls[0]![1]).toEqual({ id: "row-2" });
  const version = texture.version;
  for (let i = 0; i < 100; i++) expect(display.flush()).toBe(false);
  expect(texture.version).toBe(version); expect(display.set({ id: "row-2" })).toBe(false);
  display.restore(); expect(display.flush()).toBe(true);
  expect(display.info()).toMatchObject({ uploads: 2, textureBytes: 655360, identity: "row-2", pending: false });
  display.dispose(); display.dispose();
  expect(textureDispose).toHaveBeenCalledTimes(1); expect(materialDispose).toHaveBeenCalledTimes(1);
  expect(display.flush()).toBe(false); expect(display.set({ id: "row-3" })).toBe(false);
});
