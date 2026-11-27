import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import { Mesh, MeshStandardMaterial, NoColorSpace, Texture, TextureLoader } from "three";
import { createArchitecture } from "../src/scene/architecture";
import { FLOOR_OCCLUSION, loadFloorOcclusion } from "../src/scene/floorOcclusion";
import { REPO_ROOT } from "./fixture";

afterEach(() => vi.restoreAllMocks());
function pendingImage() {
  const texture = new Texture<HTMLImageElement>(), disposed = vi.spyOn(texture, "dispose");
  let loaded: (texture: Texture<HTMLImageElement>) => void = () => {}, failed: () => void = () => {};
  const load = vi.spyOn(TextureLoader.prototype, "load").mockImplementation((_url, onLoad, _progress, onError) => {
    loaded = onLoad!; failed = () => onError?.(new Error("image unavailable")); return texture;
  });
  return { texture, disposed, load, finish: () => loaded(texture), fail: () => failed() };
}

it("loads non-colour occlusion on the floor's original UVs and releases it with its hall", () => {
  const image = pendingImage(), hall = createArchitecture(), draw = vi.fn();
  const release = loadFloorOcclusion(hall, draw);
  expect(image.load.mock.calls[0]![0]).toBe(FLOOR_OCCLUSION);
  expect(image.texture.colorSpace).toBe(NoColorSpace); expect(image.texture.channel).toBe(0);
  expect(draw).not.toHaveBeenCalled();
  image.finish();
  const floor = hall.root.getObjectByName("Laboratory floor") as Mesh;
  expect((floor.material as MeshStandardMaterial).aoMap).toBe(image.texture);
  expect(draw).toHaveBeenCalledTimes(1);
  release(); expect(image.disposed).not.toHaveBeenCalled();
  hall.dispose(); expect(image.disposed).toHaveBeenCalledTimes(1);
});

it.each(["leave", "failure"])("keeps a %s during image loading from adopting or redrawing a disposed texture", mode => {
  const image = pendingImage(), hall = { setFloorOcclusion: vi.fn() }, draw = vi.fn();
  const release = loadFloorOcclusion(hall, draw);
  if (mode === "failure") image.fail(); else release();
  image.finish(); release();
  expect(image.disposed).toHaveBeenCalledTimes(1);
  expect(hall.setFloorOcclusion).not.toHaveBeenCalled(); expect(draw).not.toHaveBeenCalled();
});

it("binds the shipped 1024px bake to the exact revised hall sources", () => {
  const publicRoot = join(REPO_ROOT, "apps/instrument/public");
  const receipt = JSON.parse(readFileSync(join(publicRoot, FLOOR_OCCLUSION.slice(1).replace(/\.png$/, ".json")), "utf8"));
  const digest = (bytes: Buffer) => createHash("sha256").update(bytes).digest("hex");
  const bytes = readFileSync(join(publicRoot, receipt.asset));
  expect(`/${receipt.asset}`).toBe(FLOOR_OCCLUSION);
  expect(digest(bytes)).toBe(receipt.sha256); expect(bytes.length).toBe(receipt.bytes);
  expect(bytes.readUInt32BE(16)).toBe(1024); expect(bytes.readUInt32BE(20)).toBe(1024);
  for (const source of receipt.sources) {
    expect(digest(readFileSync(join(REPO_ROOT, source.path))), source.path).toBe(source.sha256);
  }
});
