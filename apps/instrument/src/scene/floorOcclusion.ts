import { NoColorSpace, TextureLoader, type Texture } from "three";

// Cycles contact-occlusion bake of this standing hall and console only.
// Exact mesh export and bake receipt: artifacts/standing-laboratory-2026-11-26/lighting.
// It is authored presentation, not measured light or recorded robot geometry.
export const FLOOR_OCCLUSION = "/media/laboratory/standing-floor-ao-1b4019acd51d34bf.png";

/** The hall owns an adopted texture. Until adoption this loader owns it,
 * including load failure and leaving the exhibit before decoding completes. */
export function loadFloorOcclusion(hall: { setFloorOcclusion(texture: Texture): void }, invalidate: () => void,
  loader: Pick<TextureLoader, "load"> = new TextureLoader()) {
  let released = false, adopted = false;
  const texture = loader.load(FLOOR_OCCLUSION, loaded => {
    if (released) return;
    adopted = true;
    hall.setFloorOcclusion(loaded);
    invalidate();
  }, undefined, () => release());
  texture.colorSpace = NoColorSpace;
  texture.channel = 0; // The bake preserves the floor's original UV coordinates.
  function release() {
    if (released) return;
    released = true;
    if (!adopted) texture.dispose();
  }
  return release;
}
