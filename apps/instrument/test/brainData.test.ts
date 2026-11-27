// @vitest-environment node
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { BRAIN_PREVIEW } from "../src/concepts/brainPreview";
import { brainRow, decodeBrainInspection } from "../src/concepts/brainData";
import { sha256Hex } from "../src/data/digest";

const bytes = readFileSync(new URL("../public" + BRAIN_PREVIEW.path,import.meta.url));
const example = () => JSON.parse(bytes.toString());
it("binds the G1 inspection to verified source and preserves the failed comparison",async()=>{
  expect(await sha256Hex(new Uint8Array(bytes).buffer)).toBe(BRAIN_PREVIEW.sha256);
  const p=decodeBrainInspection(example());
  const baseline=p.traces.find(t=>t.role==="baseline")!, candidate=p.traces.find(t=>t.role==="candidate")!, diagnostic=p.traces.find(t=>t.role==="privileged")!;
  expect(baseline.outcome.completed).toBe(false); expect(candidate.outcome.completed).toBe(false);
  expect(diagnostic.outcome.completed).toBe(true);
  expect([baseline.rows.length,candidate.rows.length,diagnostic.rows.length]).toEqual([372,372,650]);
  expect(brainRow(baseline,372)).toBeNull(); expect(brainRow(diagnostic,372)).not.toBeNull();
  expect(brainRow(baseline,1.5)).toBeNull(); expect(brainRow(baseline,-1)).toBeNull();
});
it.each([
  (p:any)=>p.traces.pop(),
  (p:any)=>p.traces[1].role="baseline",
  (p:any)=>p.traces[0].rows[1].t_s=.021,
  (p:any)=>p.traces[0].rows[1].applied_nm+=.1,
  (p:any)=>p.traces[0].rows[1].after.t_s=.02,
  (p:any)=>p.traces[0].rows[10].observation.delivered_s=100,
  (p:any)=>p.traces[0].rows[10].belief.calibrated_probabilities=true,
  (p:any)=>p.traces[0].rows[10].guard.safe_stop_established=true,
  (p:any)=>p.traces[0].outcome.censored=null,
  (p:any)=>p.traces[0].model_sha256="unknown",
])("refuses scientifically incompatible timing or authority (%#)",mutate=>{
  const packet=example(); mutate(packet); expect(()=>decodeBrainInspection(packet)).toThrow();
});
