// @vitest-environment node
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { CONTACT_PREVIEW } from "../src/lab/contactPreview";
import { contactPair, decodeContactPacket } from "../src/lab/contactData";
import { sha256Hex } from "../src/data/digest";
import { cameraEase, renderPixelRatio } from "../src/scene/renderProfile";

const bytes = readFileSync(new URL("../public" + CONTACT_PREVIEW.path, import.meta.url));
const example = () => JSON.parse(bytes.toString());
it("binds the published inspection to the retained native result and exact measurement rows", async () => {
  expect(await sha256Hex(new Uint8Array(bytes).buffer)).toBe(CONTACT_PREVIEW.sha256);
  const packet = decodeContactPacket(example());
  expect(packet.result.qualification.verdict).toBe("rejected");
  expect(packet.result.qualification.deployment_decision).toBe("unresolved");
  const pair = contactPair({packet, condition:"high",index:60,forces:true});
  expect(pair.reference?.rows).toHaveLength(61);
  expect(pair.candidate?.rows[60]?.t_s).toBeCloseTo(.3,12);
});
it.each([
  (p:any) => p.traces.pop(),
  (p:any) => p.traces[0].rows.pop(),
  (p:any) => p.traces[0].rows[1].t_s = .006,
  (p:any) => p.traces[1].initial_state_sha256 = "0".repeat(64),
  (p:any) => p.traces[1] = structuredClone(p.traces[0]),
  (p:any) => p.traces[0].rows[0].normal_n = null,
  (p:any) => p.experiment.spec.parameters.duration_s = "0.3",
  (p:any) => p.result.qualification.deployment_decision = "adopt",
  (p:any) => p.result.status = "cancelled",
  (p:any) => p.analysis.estimates.candidate.status = "unresolved",
  (p:any) => p.experiment.spec.protocol.visualization.force_arrow_scale_m_per_n = .2,
])("refuses missing or scientifically incompatible display data (%#)", mutate => {
  const packet=example(); mutate(packet); expect(()=>decodeContactPacket(packet)).toThrow();
});
it("bounds rendering independently of experiment data and eases endpoints continuously", () => {
  for (const [w,h,dpr] of [[1728,1000,2],[390,844,3],[7680,4320,2]]) {
    const ratio = renderPixelRatio(w!,h!,dpr!,"interactive");
    expect(w!*h!*ratio**2).toBeLessThanOrEqual(3_000_001);
    expect(ratio).toBeLessThanOrEqual(1.5);
  }
  expect(cameraEase(0)).toBe(0); expect(cameraEase(1)).toBe(1);
  expect(cameraEase(.5)).toBe(.5);
  expect(cameraEase(.0001)/.0001).toBeLessThan(.00001);
});
