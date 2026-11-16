// Export the actual presentation geometry for the offline Cycles light bake.
// No robot, evidence, author media, physics or local archive is exported.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import ts from 'typescript';
import * as THREE from 'three';
const here = dirname(fileURLToPath(import.meta.url));
const output = resolve(here, '../../../artifacts/spatial-laboratory-ricci-2026-11-16/lighting');
const source = await readFile(resolve(here, '../src/scene/architecture.ts'), 'utf8');
const module = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  .replace('from "three"', `from ${JSON.stringify(import.meta.resolve('three'))}`);
const { createArchitecture } = await import(`data:text/javascript;base64,${Buffer.from(module).toString('base64')}`);
const hall = createArchitecture();
hall.root.updateMatrixWorld(true);
const meshes = [], materials = new Map();
hall.root.traverse(mesh => {
  // Exclude drawing annotations, atmosphere boards and glazing from the bake.
  if (!mesh.isMesh || !mesh.material.isMeshStandardMaterial || mesh.material.transparent) return;
  const material = mesh.material;
  if (!materials.has(material.uuid)) materials.set(material.uuid, { id: `material-${materials.size}`, name: material.name, colour: material.color.toArray(), roughness: material.roughness, metalness: material.metalness });
  const geometry = mesh.geometry;
  const positions = Array.from(geometry.attributes.position.array), indices = geometry.index ? Array.from(geometry.index.array) : Array.from({ length: positions.length / 3 }, (_, i) => i);
  const transforms = [], matrix = new THREE.Matrix4();
  for (let i = 0; i < (mesh.isInstancedMesh ? mesh.count : 1); i++) {
    if (mesh.isInstancedMesh) { mesh.getMatrixAt(i, matrix); matrix.premultiply(mesh.matrixWorld); }
    else matrix.copy(mesh.matrixWorld);
    transforms.push(matrix.toArray());
  }
  meshes.push({ name: mesh.name, material: materials.get(material.uuid).id, positions, indices, uv: geometry.attributes.uv ? Array.from(geometry.attributes.uv.array) : null, transforms });
});
await mkdir(output, { recursive: true });
await writeFile(resolve(output, 'architecture.json'), JSON.stringify({ schema: 'nisayon.presentation-lighting-source.v1', source_sha256: createHash('sha256').update(source).digest('hex'), units: 'metres', axes: 'three-y-up', materials: [...materials.values()], meshes }));
hall.dispose();
console.log(JSON.stringify({ output, meshes: meshes.length, instances: meshes.reduce((n, m) => n + m.transforms.length, 0), source_sha256: createHash('sha256').update(source).digest('hex') }));
