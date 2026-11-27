import * as THREE from "three";

/** One bounded display texture. Its owner supplies the data and render clock. */
export function createCanvasDisplay<T>(canvas: HTMLCanvasElement, width: 512 | 768, name: string,
  draw: (context: CanvasRenderingContext2D, value: T | null) => void,
  same: (a: T, b: T) => boolean,
  identity: (value: T) => string,
) {
  canvas.width = width; canvas.height = width * 5 / 8;
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) return null;
  const texture = new THREE.CanvasTexture(canvas);
  texture.name = name; texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  const material = new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, fog: false });
  let selected: T | null = null, dirty = true, disposed = false, uploads = 0;
  return {
    material,
    set(value: T | null) {
      if (disposed || value === selected || (value !== null && selected !== null && same(value, selected))) return false;
      selected = value; dirty = true; return true;
    },
    flush() {
      if (!dirty || disposed) return false;
      draw(context, selected); texture.needsUpdate = true; dirty = false; uploads++;
      return true;
    },
    restore() { if (!disposed) dirty = true; },
    info() { return { uploads, textureBytes: canvas.width * canvas.height * 4, identity: selected === null ? null : identity(selected), pending: dirty && !disposed }; },
    dispose() { if (disposed) return; disposed = true; selected = null; texture.dispose(); material.dispose(); canvas.width = canvas.height = 1; },
  };
}
