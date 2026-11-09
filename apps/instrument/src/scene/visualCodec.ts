import type { Generation, ModelBody, ModelRecord } from "../model/types";

type Vec3 = [number, number, number];
type Quat = [number, number, number, number];
export interface VisualMesh {
  name: string;
  source_sha256: string;
  positions: Float32Array;
  normals: Float32Array;
  indices: Uint32Array;
  bounds: { min: Vec3; max: Vec3 };
}
export interface VisualPart {
  name: string;
  body: number;
  mesh: string;
  position: Vec3;
  quaternion_wxyz: Quat;
  rgba: Quat;
}
export interface VisualAsset {
  sha256: string;
  modelBindings: Record<string, string[]>;
  bodies: ModelBody[];
  meshes: VisualMesh[];
  parts: VisualPart[];
  licenseUrl: string;
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Visual object is malformed");
  return value as Record<string, unknown>;
}
function string(value: unknown): string {
  if (typeof value !== "string" || value.length > 4096) throw new Error("Visual string is malformed");
  return value;
}
function hash(value: unknown): string {
  const result = string(value);
  if (!/^[a-f0-9]{64}$/.test(result)) throw new Error("Visual source digest is malformed");
  return result;
}
function count(value: unknown, bound: number): number {
  if (!Number.isSafeInteger(value) || (value as number) < 0 || (value as number) > bound) throw new Error("Visual count is outside its bound");
  return value as number;
}
function list(value: unknown, bound: number): unknown[] {
  if (!Array.isArray(value) || value.length > bound) throw new Error("Visual list is outside its bound");
  return value;
}
function vector(value: unknown, size: 3): Vec3;
function vector(value: unknown, size: 4): Quat;
function vector(value: unknown, size: number): number[] {
  const result = list(value, size);
  if (result.length !== size || result.some((x) => typeof x !== "number" || !Number.isFinite(x))) throw new Error("Visual coordinate is malformed");
  return result as number[];
}
function binary(value: unknown, length: number): DataView {
  if (typeof value !== "string" || value.length !== 4 * Math.ceil(length / 3) || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) throw new Error("Visual binary length is malformed");
  const native = (Uint8Array as typeof Uint8Array & { fromBase64?: (text: string, options: { lastChunkHandling: "strict" }) => Uint8Array<ArrayBuffer> }).fromBase64;
  let bytes: Uint8Array<ArrayBuffer>;
  if (native) bytes = native(value, { lastChunkHandling: "strict" });
  else {
    const decoded = atob(value);
    bytes = new Uint8Array(decoded.length);
    for (let i = 0; i < decoded.length; i++) bytes[i] = decoded.charCodeAt(i);
  }
  if (bytes.byteLength !== length) throw new Error("Visual binary length differs from its declaration");
  return new DataView(bytes.buffer);
}
function floats(value: unknown, length: number): Float32Array {
  const data = binary(value, length * 4);
  const result = new Float32Array(length);
  for (let i = 0; i < length; i++) {
    result[i] = data.getFloat32(i * 4, true);
    if (!Number.isFinite(result[i])) throw new Error("Visual surface contains a non-finite coordinate");
  }
  return result;
}

export function decodeVisualAsset(json: unknown, sha256: string): VisualAsset {
  const value = record(json);
  const convention = record(value.convention);
  if (value.schema !== "nisayon.ui-visual.v1" || value.mujoco_version !== "3.2.7" || convention.up !== "Z" || convention.units !== "metres" || convention.quaternion !== "wxyz" || convention.handedness !== "right") throw new Error("Unsupported visual convention");
  const modelBindings: Record<string, string[]> = {};
  const bindings = Object.entries(record(value.model_bindings));
  if (!bindings.length || bindings.length > 512) throw new Error("Visual model binding count is invalid");
  for (const [key, digest] of bindings) {
    if (!/^model:[a-f0-9]{64}$/.test(key)) throw new Error("Visual model identity is malformed");
    modelBindings[key] = [hash(digest)];
  }
  for (const alias of list(value.model_binding_aliases ?? [], 1024)) {
    const a = record(alias), source = string(a.source_id);
    if (!modelBindings[source]) throw new Error("Visual alias has no qualified source");
    modelBindings[source]!.push(hash(a.sha256));
  }
  const bodies = list(value.bodies, 256).map((body, i) => {
    const b = record(body);
    if (b.index !== i) throw new Error("Visual body order is not contiguous");
    return { index: i, name: string(b.name), parent: count(b.parent, i) };
  });
  let totalVertices = 0;
  const meshes = list(value.meshes, 128).map((mesh): VisualMesh => {
    const m = record(mesh);
    const vertices = count(m.vertex_count, 500_000);
    const triangles = count(m.triangle_count, 500_000);
    totalVertices += vertices;
    if (!vertices || !triangles || totalVertices > 1_000_000) throw new Error("Visual geometry exceeds its bound");
    const positions = floats(m.positions_f32_le, vertices * 3);
    const normals = floats(m.normals_f32_le, vertices * 3);
    const bytes = binary(m.indices_u32_le, triangles * 3 * 4);
    const indices = new Uint32Array(triangles * 3);
    for (let i = 0; i < indices.length; i++) {
      indices[i] = bytes.getUint32(i * 4, true);
      if (indices[i]! >= vertices) throw new Error("Visual triangle references an absent vertex");
    }
    const declared = record(m.bounds);
    const bounds = { min: vector(declared.min, 3), max: vector(declared.max, 3) };
    for (let axis = 0; axis < 3; axis++) {
      let min = Infinity, max = -Infinity;
      for (let i = axis; i < positions.length; i += 3) { min = Math.min(min, positions[i]!); max = Math.max(max, positions[i]!); }
      if (bounds.min[axis] !== min || bounds.max[axis] !== max) throw new Error("Visual bounds differ from the surface");
    }
    return { name: string(m.name), source_sha256: hash(m.source_sha256), positions, normals, indices, bounds };
  });
  const names = new Set(meshes.map((mesh) => mesh.name));
  if (names.size !== meshes.length) throw new Error("Duplicate visual mesh identity");
  const parts = list(value.parts, 256).map((part): VisualPart => {
    const p = record(part);
    const mesh = string(p.mesh);
    if (!names.has(mesh)) throw new Error("Visual part references an absent mesh");
    const quat = vector(p.quaternion_wxyz, 4);
    if (Math.abs(Math.hypot(...quat) - 1) > 1e-10) throw new Error("Visual rotation is not unit length");
    const rgba = vector(p.rgba, 4);
    if (rgba.some((x) => x < 0 || x > 1)) throw new Error("Visual colour is outside its range");
    return { name: string(p.name), body: count(p.body, bodies.length - 1), mesh, position: vector(p.position, 3), quaternion_wxyz: quat, rgba };
  });
  if (new Set(parts.map((p) => p.name)).size !== parts.length) throw new Error("Duplicate visual part identity");
  return { sha256, modelBindings, bodies, meshes, parts, licenseUrl: "/fixtures/ui/visual/ROBOSUITE-LICENSE.txt" };
}

export function checkVisualBinding(asset: VisualAsset, model: ModelRecord, modelSha: string, generation: Generation): void {
  const sourceId = model.meshes.source_id;
  if (typeof sourceId !== "string" || !asset.modelBindings[sourceId]?.includes(modelSha)) throw new Error("Detailed geometry is not qualified for this retained model");
  const source = generation.source_bindings.find((binding) => binding.binding.split(" · ")[0] === sourceId);
  if (!source || source.sha256 !== sourceId.slice(6)) throw new Error("Retained model source binding is absent");
  if (model.bodies.length !== asset.bodies.length || model.bodies.some((b, i) => b.index !== asset.bodies[i]!.index || b.name !== asset.bodies[i]!.name || b.parent !== asset.bodies[i]!.parent)) throw new Error("Detailed geometry body order differs from the recording");
  const assets = new Set(generation.source_bindings.filter((binding) => binding.kind === "asset").map((binding) => binding.sha256));
  if (asset.meshes.some((mesh) => !assets.has(mesh.source_sha256))) throw new Error("Detailed geometry source asset is not bound by the recording");
}
