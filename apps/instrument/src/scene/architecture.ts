// Presentation architecture, in Three's y-up metres. This group has no bodies,
// collisions or simulation state. Displays have a separate presentation hit
// identity; visible furniture can occlude a pick without becoming a body.
import * as THREE from "three";
import { Reflector } from "three/addons/objects/Reflector.js";
import { createWorkstations } from "./workstations";
import { createContactBench } from "./contactBench";

export type LabSetting = "architecture" | "source";
export type LabDestination = "lab" | "workspace" | "grasp";

export function createArchitecture({ compact = false, planarReflection = false } = {}) {
  const root = new THREE.Group();
  root.name = "Conceptual laboratory architecture";
  root.userData.presentationOnly = true;
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const geometry = <T extends THREE.BufferGeometry>(g: T) => { geometries.add(g); return g; };
  const material = <T extends THREE.Material>(m: T) => { materials.add(m); return m; };
  // Fine mineral grain is authored texture, not a photograph or a measured
  // surface. Keep the relief below a millimetre; scale carries the material.
  const grainBytes = new Uint8Array(128 * 128 * 4);
  let seed = 731;
  for (let i = 0; i < 128 * 128; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const value = 170 + (seed >>> 26);
    grainBytes.set([value, value, value, 255], i * 4);
  }
  const grain = new THREE.DataTexture(grainBytes, 128, 128);
  grain.wrapS = grain.wrapT = THREE.RepeatWrapping;
  grain.minFilter = THREE.LinearMipmapLinearFilter; grain.magFilter = THREE.LinearFilter;
  grain.generateMipmaps = true; grain.repeat.set(3, 3); grain.needsUpdate = true; textures.add(grain);
  const concrete = material(new THREE.MeshStandardMaterial({ name: "Chalk mineral plaster", color: 0xb9babc, roughness: .83, bumpMap: grain, bumpScale: .0007 }));
  const stone = material(new THREE.MeshStandardMaterial({ name: "Dark honed mineral floor", color: 0x24292d, roughness: .78, metalness: 0, envMapIntensity: .32 }));
  const steel = material(new THREE.MeshStandardMaterial({ name: "Brushed graphite aluminium", color: 0x25282c, roughness: .34, metalness: .82 }));
  const timber = material(new THREE.MeshStandardMaterial({ name: "Continuous pale vault", color: 0xb4b5b8, roughness: .78, side: THREE.DoubleSide }));
  const garden = material(new THREE.MeshStandardMaterial({ name: "Garden ground", color: 0x555a58, roughness: 1 }));
  const glass = material(new THREE.MeshStandardMaterial({ name: "Architectural glazing", color: 0xb8d0ca, roughness: .1, metalness: .1, transparent: true, opacity: .065, depthWrite: false, side: THREE.DoubleSide }));
  const backdrop = material(new THREE.MeshBasicMaterial({ name: "Distant garden atmosphere", color: 0xa4b7b3, side: THREE.DoubleSide }));
  const leaf = material(new THREE.MeshStandardMaterial({ color: 0x4b514e, roughness: 1, side: THREE.DoubleSide }));
  const trunk = material(new THREE.MeshStandardMaterial({ color: 0x454846, roughness: 1 }));
  const line = material(new THREE.LineBasicMaterial({ color: 0x4c534b, transparent: true, opacity: .09 }));
  const section = new THREE.Plane(new THREE.Vector3(0, -1, 0), 3);
  let sectioned = false;
  const boxGeometry = geometry(new THREE.BoxGeometry(1, 1, 1));
  const boxMatrices = new Map<THREE.Material, THREE.Matrix4[]>();
  const instances: THREE.InstancedMesh[] = [];
  const boxTransform = new THREE.Object3D();
  function box(x: number, y: number, z: number, w: number, h: number, d: number, m: THREE.Material) {
    boxTransform.position.set(x, y, z); boxTransform.scale.set(w, h, d); boxTransform.updateMatrix();
    const list = boxMatrices.get(m) ?? []; list.push(boxTransform.matrix.clone()); boxMatrices.set(m, list);
  }

  // A long, vaulted nave. Each rib is an actual extruded arch, not a screen
  // image; the side galleries remain open from all useful bay viewpoints.
  const arch = new THREE.Shape();
  const segments = 72;
  for (let i = 0; i <= segments; i++) {
    const a = Math.PI * i / segments;
    const x = 5.7 * Math.cos(a), y = 2.3 + 4.4 * Math.sin(a);
    if (!i) arch.moveTo(x, y); else arch.lineTo(x, y);
  }
  for (let i = segments; i >= 0; i--) {
    const a = Math.PI * i / segments;
    arch.lineTo(5.48 * Math.cos(a), 2.3 + 4.16 * Math.sin(a));
  }
  arch.closePath();
  const archGeometry = geometry(new THREE.ExtrudeGeometry(arch, { depth: .42, bevelEnabled: true, bevelSize: .035, bevelThickness: .025, bevelSegments: 2, steps: 1, curveSegments: 64 }));
  const ribPositions = [-10, -6, -2, 2, 6, 10];
  const ribs = new THREE.InstancedMesh(archGeometry, concrete, ribPositions.length);
  ribs.name = "Vault ribs";
  for (const [index,z] of ribPositions.entries()) {
    ribs.setMatrixAt(index,new THREE.Matrix4().makeTranslation(0,0,z));
    for (const x of [-5.59, 5.59]) box(x, 1.15, z + .21, .24, 2.3, .5, concrete);
  }
  root.add(ribs); instances.push(ribs);
  // The upper shell deliberately leaves a narrow, continuous clerestory.
  for (const side of [-1, 1]) {
    const positions: number[] = [], indices: number[] = [];
    for (let i = 0; i <= 36; i++) {
      const a = .13 + (Math.PI / 2 - .28) * i / 36;
      for (const z of [-10, 10.45]) positions.push(side * 5.77 * Math.cos(a), 2.3 + 4.47 * Math.sin(a), z);
      if (i < 36) { const n = i * 2; indices.push(n, n + 1, n + 2, n + 2, n + 1, n + 3); }
    }
    const g = geometry(new THREE.BufferGeometry());
    g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3)); g.setIndex(indices); g.computeVertexNormals();
    const roof = new THREE.Mesh(g, timber); roof.name = "Vault acoustic shell";
    root.add(roof);

  }

  const floorGeometry = geometry(new THREE.PlaneGeometry(15, 24));
  const floorGrain = grain.clone(); floorGrain.repeat.set(45, 72); floorGrain.needsUpdate = true; textures.add(floorGrain);
  stone.bumpMap = floorGrain; stone.bumpScale = .00035;
  const floor = new THREE.Mesh(floorGeometry, stone);
  floor.name = "Laboratory floor"; floor.rotation.x = -Math.PI / 2; floor.position.y = -.016;
  floor.receiveShadow = true; root.add(floor);
  // One bounded planar reflection, rendered from actual scene geometry. It is
  // a low-opacity material pass, not an image backdrop or a task collision.
  const reflection = new Reflector(floorGeometry, { color:0x3a424a, textureWidth:compact ? 384 : 768, textureHeight:compact ? 384 : 768, multisample:compact ? 0 : 2 });
  reflection.name="Honed floor reflection";reflection.rotation.x=-Math.PI/2;reflection.position.y=-.014;
  reflection.userData.ignorePick = true;
  const reflectionMaterial=reflection.material as THREE.ShaderMaterial;
  reflectionMaterial.fragmentShader=reflectionMaterial.fragmentShader.replace("color ), 1.0", "color ), 0.045");
  reflectionMaterial.fragmentShader=reflectionMaterial.fragmentShader.replace("vec4 base = texture2DProj( tDiffuse, vUv );", `
    vec2 uv=vUv.xy/vUv.w; vec4 base=vec4(0.0);
    for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)base+=texture2D(tDiffuse,uv+vec2(float(x),float(y))*.0025)/9.0;
  `);
  reflectionMaterial.transparent=true;reflectionMaterial.depthWrite=false;root.add(reflection);
  reflection.visible = planarReflection;
  const gardenFloor = new THREE.Mesh(geometry(new THREE.PlaneGeometry(32, 44)), garden);
  gardenFloor.name = "Garden ground"; gardenFloor.rotation.x = -Math.PI / 2; gardenFloor.position.y = -.027;
  gardenFloor.receiveShadow = true; root.add(gardenFloor);
  // Subtle floor joints belong to the presentation architecture.
  const joints: number[] = [];
  for (let x = -7; x <= 7; x += 2) joints.push(x, -.011, -12, x, -.011, 12);
  for (let z = -12; z <= 12; z += 2) joints.push(-7, -.011, z, 7, -.011, z);
  const floorLines = geometry(new THREE.BufferGeometry()); floorLines.setAttribute("position", new THREE.Float32BufferAttribute(joints, 3));
  root.add(new THREE.LineSegments(floorLines, line));

  // Glazed garden and rear elevation, with real mullion depth.
  box(-6.1, 2.75, 0, .035, 5.5, 23, glass);
  box(0, 2.75, -10.3, 12.2, 5.5, .035, glass);
  box(-14, 4, 0, .1, 10, 38, backdrop);
  box(0, 4, -18, 30, 10, .1, backdrop);
  for (let z = -10; z <= 10; z += 1.4) box(-6.08, 2.75, z, .07, 5.5, .045, steel);
  for (let x = -5.6; x <= 5.6; x += 1.4) box(x, 2.75, -10.25, .045, 5.5, .07, steel);
  for (const y of [0.08, 2.8, 5.4]) { box(-6.05, y, 0, .09, .06, 22, steel); box(0, y, -10.2, 12, .06, .09, steel); }

  // One working bay: the unchanged Panda source, adjacent operator console,
  // and a narrow contact instrument. Circulation stays on the continuous floor.
  const workstations = createWorkstations(); root.add(workstations.root);
  const contact = createContactBench(); root.add(contact.root);

  // Folded leaves on connected branch systems, with deterministic local
  // colour variation. Three instanced draws; no alpha cards or idle animation.
  const leafGeometry = geometry(new THREE.BufferGeometry());
  leafGeometry.setAttribute("position", new THREE.Float32BufferAttribute([0,-.11,0, -.055,-.025,0, 0,.015,.018, .055,-.025,0, 0,.14,-.005, -.04,.075,0, .04,.075,0], 3));
  leafGeometry.setIndex([0,1,2,0,2,3,1,5,2,3,2,6,5,4,2,2,4,6]); leafGeometry.computeVertexNormals();
  const trunkGeometry = geometry(new THREE.CylinderGeometry(.035, .085, 1, 9));
  const branchGeometry = geometry(new THREE.CylinderGeometry(.004, .022, 1, 5));
  const treeCount = 24, branchesPerTree = 18, leavesPerBranch = 22;
  const foliage = new THREE.InstancedMesh(leafGeometry, leaf, treeCount * branchesPerTree * leavesPerBranch);
  const trunks = new THREE.InstancedMesh(trunkGeometry, trunk, treeCount);
  const branches = new THREE.InstancedMesh(branchGeometry, trunk, treeCount * branchesPerTree);
  foliage.name = "Garden foliage"; trunks.name = "Garden trunks"; branches.name = "Garden branches";
  const transform = new THREE.Object3D();
  let leafIndex = 0;
  const random = (n: number) => { const value = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return value - Math.floor(value); };
  const leafColour = new THREE.Color(), stem = new THREE.Vector3(), end = new THREE.Vector3(), direction = new THREE.Vector3();
  for (let i = 0; i < treeCount; i++) {
    const rear = i >= 12, k = i % 12, height = 3.4 + Math.sin(i * 2.3) * 1.15;
    const x = rear ? -8 + k * 1.45 : -7.5 - (i % 3) * .65;
    const z = rear ? -12.2 - (i % 3) * 1.1 : -10 + k * 1.9;
    transform.position.set(x, height / 2, z); transform.rotation.set(0, 0, 0); transform.scale.set(1, height, 1); transform.updateMatrix(); trunks.setMatrixAt(i, transform.matrix);
    for (let j = 0; j < branchesPerTree; j++) {
      const key = i * 1000 + j * 31, azimuth = j * 2.399 + i, radius = .7 + random(key) * .7;
      stem.set(x, height * (.38 + j / branchesPerTree * .6), z);
      end.set(x + Math.cos(azimuth) * radius, stem.y + .5 + random(key + 1) * .7, z + Math.sin(azimuth) * radius);
      direction.subVectors(end, stem);
      transform.position.copy(stem).addScaledVector(direction, .5); transform.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), direction.clone().normalize());
      transform.scale.setScalar(1); transform.scale.y = direction.length(); transform.updateMatrix(); branches.setMatrixAt(i * branchesPerTree + j, transform.matrix);
      for (let k = 0; k < leavesPerBranch; k++) {
        const seed = key + k * 7, t = .35 + .65 * random(seed + 3);
        transform.position.copy(stem).lerp(end, t).add(new THREE.Vector3((random(seed + 2) - .5) * .55, (random(seed + 4) - .5) * .45, (random(seed + 5) - .5) * .55));
        transform.rotation.set(random(seed + 6) * 2, azimuth, random(seed + 7) * 2); transform.scale.setScalar(1 + random(seed + 8) * .65); transform.updateMatrix();
        foliage.setMatrixAt(leafIndex, transform.matrix); foliage.setColorAt(leafIndex++, leafColour.setHSL(.27, .04, .35 + random(seed + 2) * .18));
      }
    }
  }
  // The bounded real-time shadow map belongs to the subject, not the whole
  // twenty-metre building. Distant architecture uses the shared diffuse light;
  // clipping it into the subject map produces false polygonal floor shadows.
  foliage.receiveShadow = trunks.castShadow = branches.castShadow = false;
  foliage.castShadow = false;
  root.add(foliage, trunks, branches);
  instances.push(foliage, trunks, branches);
  for (const [m, matrices] of boxMatrices) {
    const mesh = new THREE.InstancedMesh(boxGeometry, m, matrices.length);
    matrices.forEach((matrix, index) => mesh.setMatrixAt(index, matrix));
    mesh.name = m.name || "Architecture details";
    mesh.receiveShadow = mesh.castShadow = false;
    root.add(mesh); instances.push(mesh);
  }

  return {
    root,
    workstations,
    contact,
    setReflection(enabled: boolean) { reflection.visible = enabled; },
    cutaway(active: boolean) {
      if (sectioned === active) return;
      sectioned = active;
      // An overhead camera sections only the presentation building. Recorded
      // robot and collision materials are owned by another, untouched group.
      for (const m of [concrete, timber, steel, glass]) { m.clippingPlanes = active ? [section] : null; m.needsUpdate = true; }
    },
    setFloorLightMap(texture: THREE.Texture) {
      if (stone.lightMap) { textures.delete(stone.lightMap); stone.lightMap.dispose(); }
      textures.add(texture); stone.lightMap = texture; stone.lightMapIntensity = 1; stone.needsUpdate = true;
    },
    setFloorOcclusion(texture: THREE.Texture) {
      if (stone.aoMap) { textures.delete(stone.aoMap); stone.aoMap.dispose(); }
      textures.add(texture); stone.aoMap = texture; stone.aoMapIntensity = .78; stone.needsUpdate = true;
    },
    palette(paper: boolean) {
      concrete.color.set(paper ? 0xc8c9cc : 0xb9babc);
      stone.color.set(paper ? 0x373c40 : 0x24292d);
      backdrop.color.set(0x969e9f);
      leaf.color.set(0x616764);
    },
    dispose() { contact.dispose(); workstations.dispose(); reflection.dispose(); root.removeFromParent(); geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose()); instances.forEach(mesh => mesh.dispose()); },
  };
}
