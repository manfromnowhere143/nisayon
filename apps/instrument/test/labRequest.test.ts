// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { labRequest } from "../src/lab/contactData";
afterEach(()=>vi.unstubAllGlobals());
it("shows the bounded native refusal instead of an opaque HTTP error",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({error:"validated identity changed; validate again before execution"}),{status:400})));
  await expect(labRequest("/api/lab/runs")).rejects.toThrow("validated identity changed");
});
it("does not interpret a failed transport as successful experimental data",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>new Response("<html>proxy unavailable</html>",{status:502})));
  await expect(labRequest("/api/lab/runs")).rejects.toThrow("HTTP 502");
});
