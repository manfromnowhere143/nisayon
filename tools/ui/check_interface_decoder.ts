// Cross-lane readback of the real interface decoder against every recorded row.
// This is a Node data check. It does not exercise a browser, fetch loader or GPU.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  decodeCaseV1,
  decodeDiscoveryV1,
  decodeManifestV1,
  decodeModelV1,
  decodeReconstructionV1,
  decodeSamplesV1,
} from "../../apps/instrument/src/model/decodeV1";
import { strictParseJson } from "../../apps/instrument/src/data/strictJson";
import { firstActionMismatch, pairedRun } from "../../apps/instrument/src/model/findings";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const hash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");
const readJson = (path: string) => JSON.parse(readFileSync(path, "utf8"));
const library = readJson(resolve(root, "fixtures/ui/recorded/library.json"));
const output = process.argv[2] ?? "docs/ui/qualification/interface-decoder-current.json";
const report: Record<string, any> = {
  schema: "nisayon.ui-interface-decoder-readback.v1",
  original_interface_commit: "340519973164cc9fb89e7d772bf4af3a00f7a557",
  decoder_source_sha256: hash(readFileSync(resolve(root, "apps/instrument/src/model/decodeV1.ts"))),
  checked_head: execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim(),
  node: process.version,
  script_sha256: hash(readFileSync(fileURLToPath(import.meta.url))),
  strict_json_source_sha256: hash(readFileSync(resolve(root, "apps/instrument/src/data/strictJson.ts"))),
  scope: "Committed interface decoders and findings, called directly in Node; no fetch loader, browser, renderer, interaction or performance acceptance.",
  cases: [],
  findings: [],
  trial_source_probes: [],
};
const started = performance.now();
let totalRows = 0;
let totalFrames = 0;
for (const entry of library.cases) {
  const base = resolve(root, "fixtures/ui/recorded", entry.case_id);
  const checked: Record<string, any> = { case_id: entry.case_id, runs: 0, rows: 0, frames: 0 };
  report.cases.push(checked);
  try {
    const discovery = readJson(resolve(base, "evidence.json"));
    const evidence = decodeDiscoveryV1(discovery);
    const readObject = (ref: { path: string; sha256: string; byte_length: number }) => {
      const bytes = readFileSync(resolve(base, ref.path));
      assert.equal(bytes.byteLength, ref.byte_length);
      assert.equal(hash(bytes), ref.sha256);
      return strictParseJson(bytes.toString("utf8")) as any;
    };
    const manifest = readObject(discovery.manifest);
    const generation = decodeManifestV1(manifest, evidence.current.generation_sha256,
      `http://fixture.test/${discovery.manifest.path}`, "http://fixture.test/");
    const rawCase = readObject(manifest.cases[0].object);
    const caseRecord = decodeCaseV1(rawCase, generation);
    assert.equal(caseRecord.runs.length, rawCase.runs.length);
    assert.deepEqual(caseRecord.trial, rawCase.trial);
    assert.deepEqual(caseRecord.confirmation, rawCase.confirmation);
    if (rawCase.trial?.source) {
      const bound = manifest.sources.find((s: any) => s.id === rawCase.trial.source.source_id);
      const displayed = caseRecord.decisions.trial;
      report.trial_source_probes.push({ case_id: entry.case_id,
        bound: { sha256: bound.sha256, byte_length: bound.byte_length, label: bound.label },
        decoded: { sha256: displayed?.sha256, byte_length: displayed?.byte_length, path: displayed?.path },
        exact_source_identity: bound.sha256 === displayed?.sha256 && bound.byte_length === displayed?.byte_length });
    }
    checked.generation_sha256 = generation.sha256;
    checked.trial_status = caseRecord.trial?.status ?? null;
    checked.confirmation_status = caseRecord.confirmation?.status ?? null;
    for (let runIndex = 0; runIndex < rawCase.runs.length; runIndex += 1) {
      const sourceRun = rawCase.runs[runIndex];
      const record = caseRecord.runs[runIndex]!;
      assert.deepEqual(record.run, sourceRun.key);
      for (const key of ["role", "stage", "condition_id", "process_status", "measurement_status", "task_outcome"] as const) {
        assert.equal(record[key], sourceRun[key]);
      }
      const rawSamples = readObject(sourceRun.samples);
      const expectation = { run: record.run, rowCount: record.row_count, actionDimension: caseRecord.predicates.action_dimension, record };
      const samples = decodeSamplesV1(rawSamples, expectation);
      const rawModel = readObject(sourceRun.model);
      const model = decodeModelV1(rawModel);
      const rawFrames = readObject(sourceRun.reconstruction);
      const frames = decodeReconstructionV1(rawFrames, expectation, model);
      for (let i = 0; i < samples.rows.length; i += 1) {
        const source = rawSamples.rows[i];
        const row = samples.rows[i]!;
        for (const field of ["row_index", "step", "action_sim_time_s", "next_sim_time_s", "observation_sim_time_s", "observation_age_s"] as const) {
          assert.equal(row[field], source[field]);
        }
        for (const field of ["intended_action", "executed_action", "cube_height_m", "task_success"] as const) {
          assert.deepEqual(row[field], source.original[field]);
        }
        assert.equal(row.locators.pointer, source.source.pointer);
        assert.equal(row.locators.source_id, source.source.source_id);
        assert.equal(row.locators.raw_source_id, source.raw_source.source_id);
        assert.equal(row.locators.raw_line, source.raw_source.line);
        assert.equal(row.policy.before, source.memory.before);
        assert.equal(row.policy.after, source.memory.after);
        assert.equal(row.policy.state_before_sha256, source.memory.before_sha256);
        assert.equal(row.policy.state_after_sha256, source.memory.after_sha256);
        for (const phase of ["before", "after"] as const) {
          const original = rawFrames.frames[2 * i + (phase === "after" ? 1 : 0)];
          const frame = frames.rows[i]![phase];
          assert.equal(frame.sim_time_s, original.stored_time_s);
          assert.equal(frame.state_sha256, original.state_sha256);
          assert.deepEqual([...frame.xpos], original.bodies.flatMap((p: number[]) => p.slice(0, 3)));
          assert.deepEqual([...frame.xquat], original.bodies.flatMap((p: number[]) => p.slice(3)));
          assert.deepEqual([...frame.sites], original.sites.flat());
          assert.deepEqual([...frame.geoms!], original.geoms.flat());
          checked.frames += 1;
        }
        checked.rows += 1;
      }
      checked.runs += 1;
      if (record.stage === "diagnostic") {
        const mismatch = firstActionMismatch(samples.rows);
        report.findings.push({ case_id: entry.case_id, run: record.run, exact_action_difference: mismatch,
          export_findings: rawCase.findings.filter((f: any) => f.run.bundle_sha256 === record.run.bundle_sha256 && f.run.run_id === record.run.run_id) });
      }
      if (entry.case_id === "D05-recurrent-carry" && record.run.run_id === "confirmation-correction-10423") {
        const paired = pairedRun(caseRecord, record);
        report.d05_pairing_probe = { selected: record.run, selected_condition: record.condition_id,
          paired: paired?.run, paired_condition: paired?.condition_id,
          same_condition: record.condition_id === paired?.condition_id };
      }
    }
    checked.status = "exact_readback_passed";
    totalRows += checked.rows;
    totalFrames += checked.frames;
  } catch (error) {
    checked.status = "failed";
    checked.message = error instanceof Error ? error.message : String(error);
  }
}
report.total_rows_checked = totalRows;
report.total_frames_checked = totalFrames;
report.command_wall_seconds = (performance.now() - started) / 1000;
writeFileSync(resolve(root, output), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify({ cases: report.cases, d05_pairing_probe: report.d05_pairing_probe,
  total_rows_checked: totalRows, total_frames_checked: totalFrames, command_wall_seconds: report.command_wall_seconds }, null, 2));
if (report.cases.some((c: any) => c.status === "failed")) process.exitCode = 1;
