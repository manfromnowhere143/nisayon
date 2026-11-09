// Derive fault cases from the committed fixture. No simulator or private raw
// store is needed to run the frontend's failure-path tests from a clean tree.
import { cpSync, readFileSync, writeFileSync, rmSync, renameSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const publicDir = join(dirname(fileURLToPath(import.meta.url)), "../public");
const source = join(publicDir, "dev-fixture");
const original = JSON.parse(readFileSync(join(source, "evidence.json"), "utf8"));
const manifestPath = original.current.manifest_path;
const generationDir = dirname(manifestPath);
const variants = {
  "corrupt-child": (target) => {
    const path = join(target, generationDir, "runs/reference-0.samples.json");
    const data = readFileSync(path, "utf8");
    const corrupt = data.replace('"cube_height_m":0.82', '"cube_height_m":0.92');
    if (data === corrupt) throw new Error("corruption target absent");
    writeFileSync(path, corrupt);
  },
  "wrong-root": (target) => {
    const evidence = structuredClone(original);
    evidence.current.generation_sha256 = "0".repeat(64);
    writeFileSync(join(target, "evidence.json"), JSON.stringify(evidence));
  },
  "missing-frames": (target) => rmSync(join(target, generationDir, "runs/reference-0.frames.json")),
  "unknown-schema": (target) => {
    const manifest = JSON.parse(readFileSync(join(target, manifestPath), "utf8"));
    manifest.schema = "nisayon.ui.dev-generation.v9";
    const data = JSON.stringify(manifest);
    const sha = createHash("sha256").update(data).digest("hex");
    writeFileSync(join(target, manifestPath), data);
    renameSync(join(target, generationDir), join(target, "generations", sha));
    const evidence = structuredClone(original);
    evidence.current = { generation_sha256: sha, manifest_path: `generations/${sha}/manifest.json`, byte_length: Buffer.byteLength(data) };
    writeFileSync(join(target, "evidence.json"), JSON.stringify(evidence));
  },
};
for (const [name, mutate] of Object.entries(variants)) {
  const target = join(publicDir, `dev-fixture-${name}`);
  rmSync(target, { recursive: true, force: true });
  cpSync(source, target, { recursive: true });
  mutate(target);
}
