import { absoluteUrl, defaultOptions, fetchVerified, type LoaderOptions } from "../data/loader";
import type { Generation, ModelRecord } from "../model/types";
import type { Quat, Vec3 } from "../model/pose";
import { COLLISION_ASSET } from "./collisionAssetPin";

export interface CollisionPart { name: string; body: number; type: "mesh" | "box" | "cylinder"; size: Vec3; position: Vec3; quaternion: Quat; mesh: string | null }
export interface CollisionView { sha256: string; parts: CollisionPart[]; meshes: Map<string, { positions: Float32Array; indices: Uint32Array }> }
const object = (v: unknown): Record<string, unknown> => { if (!v || typeof v !== "object" || Array.isArray(v)) throw new Error("Malformed collision object"); return v as Record<string, unknown>; };
const list = (v: unknown, max: number): unknown[] => { if (!Array.isArray(v) || v.length > max) throw new Error("Collision array exceeds its bound"); return v; };
const numbers = (v: unknown, size: number): number[] => { const a = list(v, size); if (a.length !== size || a.some(n => typeof n !== "number" || !Number.isFinite(n))) throw new Error("Invalid collision coordinates"); return a as number[]; };
const hash = (v: unknown): string => { if (typeof v !== "string" || !/^[a-f0-9]{64}$/.test(v)) throw new Error("Invalid collision digest"); return v; };

export function decodeCollisionView(value: unknown, model: ModelRecord, modelSha: string, generation: Generation): CollisionView {
  const raw = object(value);
  if (raw.schema !== "nisayon.ui-collision.v1" || raw.mujoco_version !== "3.2.7" || raw.convention !== "metres-z-up-wxyz") throw new Error("Unsupported collision convention");
  const source = model.meshes.source_id;
  if (typeof source !== "string" || !generation.source_bindings.some(b => b.binding.split(" · ")[0] === source && b.sha256 === source.slice(6))) throw new Error("Collision model source is absent");
  const bound = object(object(raw.models)[source]);
  if (!list(bound.model_shas, 256).map(hash).includes(modelSha)) throw new Error("Collision geometry is not qualified for this model");
  const bodies = list(raw.bodies, 256).map(object);
  if (bodies.length !== model.bodies.length || model.bodies.some((b, i) => b.name !== bodies[i]!.name || b.index !== bodies[i]!.index || b.parent !== bodies[i]!.parent)) throw new Error("Collision body order differs from the recording");
  const meshes: CollisionView["meshes"] = new Map();
  const assets = new Set(generation.source_bindings.filter(b => b.kind === "asset").map(b => b.sha256));
  const parts = list(bound.parts, 256).map((v): CollisionPart => {
    const p = object(v);
    if (typeof p.name !== "string" || p.name.length > 256 || !Number.isSafeInteger(p.body) || (p.body as number) < 0 || (p.body as number) >= bodies.length || !["mesh", "box", "cylinder"].includes(String(p.type))) throw new Error("Invalid collision part");
    const quaternion = numbers(p.quaternion_wxyz, 4) as Quat;
    if (Math.abs(Math.hypot(...quaternion) - 1) > 1e-10) throw new Error("Collision orientation is not unit length");
    const size = numbers(p.size, 3) as Vec3;
    if (size.some(n => n < 0)) throw new Error("Negative collision dimensions");
    const mesh = p.type === "mesh" ? hash(p.mesh) : null;
    if (mesh && !meshes.has(mesh)) {
      const m = object(object(raw.meshes)[mesh]);
      if (!assets.has(hash(m.source_sha256))) throw new Error("Collision source asset is not bound by this recording");
      const positions = list(m.positions, 300_000), indices = list(m.indices, 600_000);
      if (!positions.length || positions.length % 3 || !indices.length || indices.length % 3 || positions.some(n => typeof n !== "number" || !Number.isFinite(n)) || indices.some(n => !Number.isSafeInteger(n) || (n as number) < 0 || (n as number) >= positions.length / 3)) throw new Error("Malformed collision hull");
      meshes.set(mesh, { positions: new Float32Array(positions as number[]), indices: new Uint32Array(indices as number[]) });
    }
    return { name: p.name, body: p.body as number, type: p.type as CollisionPart["type"], position: numbers(p.position, 3) as Vec3, quaternion, size, mesh };
  });
  if (new Set(parts.map(p => p.name)).size !== parts.length) throw new Error("Duplicate collision identity");
  return { sha256: COLLISION_ASSET.sha256, parts, meshes };
}

let cached: Promise<unknown> | null = null;
export async function loadCollisionView(model: ModelRecord, modelSha: string, generation: Generation, options: LoaderOptions = defaultOptions()): Promise<CollisionView> {
  cached ??= fetchVerified(absoluteUrl(COLLISION_ASSET.path), COLLISION_ASSET, "run", undefined, { ...options, maxBytes: 2 * 1024 * 1024 }).then(v => v.json).catch(e => { cached = null; throw e; });
  return decodeCollisionView(await cached, model, modelSha, generation);
}
