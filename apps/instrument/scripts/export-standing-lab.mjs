// Offline geometry/source audit and bake input. This never starts a browser,
// includes a robot, or exports recorded experiment state.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { build } from 'esbuild';
import * as THREE from 'three';
const app = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(app, '../..');
if (!process.argv[2]) throw Error('Provide a new artifact directory; retained lighting packets are immutable.');
const output = resolve(process.argv[2]);
if (!output.startsWith(resolve(root,'artifacts')+'/')) throw Error('Output must be inside this worktree artifacts directory.');
const paths = ['src/scene/architecture.ts', 'src/scene/workstations.ts', 'src/scene/daylight.ts', 'src/scene/contactBench.ts', 'src/scene/laboratoryLayout.ts'];
const sources = await Promise.all(paths.map(async path => ({ path: 'apps/instrument/' + path, sha256: createHash('sha256').update(await readFile(resolve(app, path))).digest('hex') })));
const result = await build({ entryPoints: [resolve(app, paths[0])], bundle: true, platform: 'node', format: 'esm', external: ['three', 'three/*'], write: false });
const code = result.outputFiles[0].text.replace(/from "(three[^"]*)"/g, (_, specifier) => `from ${JSON.stringify(import.meta.resolve(specifier))}`);
const { createArchitecture } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const hall = createArchitecture(); hall.palette(false); hall.root.updateMatrixWorld(true);
const meshes = [], materials = new Map(), geometries = new Set(), materialSet = new Set();
let drawables = 0, triangles = 0, bufferBytes = 0;
hall.root.traverseVisible(mesh => {
  if (!mesh.isMesh && !mesh.isLineSegments) return;
  drawables++;
  if (!geometries.has(mesh.geometry)) {
    geometries.add(mesh.geometry);
    bufferBytes += Object.values(mesh.geometry.attributes).reduce((sum, attr) => sum + attr.array.byteLength, 0) + (mesh.geometry.index?.array.byteLength ?? 0);
  }
  materialSet.add(mesh.material);
  if (mesh.isMesh) triangles += (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3 * (mesh.isInstancedMesh ? mesh.count : 1);
  if (!mesh.isMesh || !mesh.material.isMeshStandardMaterial || mesh.material.transparent || mesh.userData.experimentVisual) return;
  const material = mesh.material;
  if (!materials.has(material.uuid)) materials.set(material.uuid, { id: `material-${materials.size}`, name: material.name, colour: material.color.toArray(), roughness: material.roughness, metalness: material.metalness });
  const geometry = mesh.geometry;
  const positions = Array.from(geometry.attributes.position.array);
  const transforms = [], matrix = new THREE.Matrix4();
  for (let i = 0; i < (mesh.isInstancedMesh ? mesh.count : 1); i++) {
    if (mesh.isInstancedMesh) { mesh.getMatrixAt(i, matrix); matrix.premultiply(mesh.matrixWorld); }
    else matrix.copy(mesh.matrixWorld);
    transforms.push(matrix.toArray());
  }
  meshes.push({ name: mesh.name, material: materials.get(material.uuid).id, positions,
    indices: geometry.index ? Array.from(geometry.index.array) : Array.from({ length: positions.length / 3 }, (_, i) => i),
    uv: geometry.attributes.uv ? Array.from(geometry.attributes.uv.array) : null, transforms });
});
await mkdir(output, { recursive: true });
const record = { schema: 'nisayon.presentation-lighting-source.v1', sources, units: 'metres', axes: 'three-y-up', materials: [...materials.values()], meshes };
await writeFile(resolve(output, 'architecture.json'), JSON.stringify(record), {flag:'wx'});
const inventory = { method: 'Static source geometry; not measured GPU memory, calls or frame time', sources, drawables, uniqueGeometries: geometries.size, uniqueMaterials: materialSet.size, triangleInstances: triangles, geometryBufferBytes: bufferBytes, workstation: hall.workstations.info };
await writeFile(resolve(output, 'geometry-inventory.json'), JSON.stringify(inventory, null, 2) + '\n', {flag:'wx'});
console.log(JSON.stringify(inventory, null, 2));
hall.dispose();
