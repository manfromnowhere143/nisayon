// Presentation architecture, in Three's y-up metres. This group has no bodies,
// collisions, controls or recorded state. It never participates in picking.
import * as THREE from "three";

export type LabSetting = "architecture" | "source";
export type LabDestination = "lab" | "workspace" | "grasp";

export function createArchitecture() {
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
  const concrete = material(new THREE.MeshStandardMaterial({ name: "Chalk mineral plaster", color: 0xc3bcae, roughness: .83, bumpMap: grain, bumpScale: .0007 }));
  const stone = material(new THREE.MeshStandardMaterial({ name: "Honed limestone", color: 0x8d9187, roughness: .36, metalness: 0 }));
  const steel = material(new THREE.MeshStandardMaterial({ name: "Brushed graphite aluminium", color: 0x303b3a, roughness: .34, metalness: .82 }));
  const timber = material(new THREE.MeshStandardMaterial({ name: "Warm ash acoustic lining", color: 0xb1a186, roughness: .76, side: THREE.DoubleSide }));
  const garden = material(new THREE.MeshStandardMaterial({ name: "Garden ground", color: 0x758167, roughness: 1 }));
  const glass = material(new THREE.MeshStandardMaterial({ name: "Architectural glazing", color: 0xb8d0ca, roughness: .1, metalness: .1, transparent: true, opacity: .065, depthWrite: false, side: THREE.DoubleSide }));
  const light = material(new THREE.MeshBasicMaterial({ color: 0xd8e9e4 }));
  const backdrop = material(new THREE.MeshBasicMaterial({ name: "Distant garden atmosphere", color: 0xa4b7b3, side: THREE.DoubleSide }));
  const leaf = material(new THREE.MeshStandardMaterial({ color: 0x3b4d43, roughness: 1, side: THREE.DoubleSide }));
  const trunk = material(new THREE.MeshStandardMaterial({ color: 0x4d5149, roughness: 1 }));
  const line = material(new THREE.LineBasicMaterial({ color: 0x4c534b, transparent: true, opacity: .2 }));
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
  for (const z of [-10, -6, -2, 2, 6, 10]) {
    const rib = new THREE.Mesh(archGeometry, concrete); rib.name = "Vault rib"; rib.position.z = z;
    rib.castShadow = rib.receiveShadow = true; root.add(rib);
    for (const x of [-5.59, 5.59]) box(x, 1.15, z + .21, .24, 2.3, .5, concrete);
  }
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
    roof.castShadow = roof.receiveShadow = true; root.add(roof);
    // Real, fine longitudinal battens give the vault a human construction scale.
    for (let i = 0; i < 42; i++) {
      const a = .15 + (Math.PI / 2 - .3) * i / 41;
      const list = boxMatrices.get(timber) ?? [];
      list.push(new THREE.Matrix4().compose(new THREE.Vector3(side * 5.73 * Math.cos(a), 2.3 + 4.42 * Math.sin(a), .225),
        new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), -side * a), new THREE.Vector3(.035, .06, 20.45)));
      boxMatrices.set(timber, list);
    }
  }

  const floorGeometry = geometry(new THREE.PlaneGeometry(15, 24));
  const floorGrain = grain.clone(); floorGrain.repeat.set(45, 72); floorGrain.needsUpdate = true; textures.add(floorGrain);
  stone.bumpMap = floorGrain; stone.bumpScale = .00035;
  const floor = new THREE.Mesh(floorGeometry, stone);
  floor.name = "Laboratory floor"; floor.rotation.x = -Math.PI / 2; floor.position.y = -.016;
  floor.receiveShadow = true; root.add(floor);
  const gardenFloor = new THREE.Mesh(geometry(new THREE.PlaneGeometry(32, 44)), garden);
  gardenFloor.name = "Garden ground"; gardenFloor.rotation.x = -Math.PI / 2; gardenFloor.position.y = -.027;
  gardenFloor.receiveShadow = true; root.add(gardenFloor);
  // Floor joints and the active bay footprint are graphic orientation cues.
  const joints: number[] = [];
  for (let x = -7; x <= 7; x += 2) joints.push(x, -.011, -12, x, -.011, 12);
  for (let z = -12; z <= 12; z += 2) joints.push(-7, -.011, z, 7, -.011, z);
  const floorLines = geometry(new THREE.BufferGeometry()); floorLines.setAttribute("position", new THREE.Float32BufferAttribute(joints, 3));
  root.add(new THREE.LineSegments(floorLines, line));
  for (const x of [-1.55, 1.3]) box(x, .006, 0, .012, .006, 2.4, light);
  for (const z of [-1.2, 1.2]) box(-.125, .006, z, 2.86, .006, .012, light);

  // Glazed garden and rear elevation, with real mullion depth.
  box(-6.1, 2.75, 0, .035, 5.5, 23, glass);
  box(0, 2.75, -10.3, 12.2, 5.5, .035, glass);
  box(-14, 4, 0, .1, 10, 38, backdrop);
  box(0, 4, -18, 30, 10, .1, backdrop);
  for (let z = -10; z <= 10; z += 1.4) box(-6.08, 2.75, z, .07, 5.5, .045, steel);
  for (let x = -5.6; x <= 5.6; x += 1.4) box(x, 2.75, -10.25, .045, 5.5, .07, steel);
  for (const y of [0.08, 2.8, 5.4]) { box(-6.05, y, 0, .09, .06, 22, steel); box(0, y, -10.2, 12, .06, .09, steel); }

  // Quiet gallery: furniture only. No decorative robots suggesting live work.
  box(4.72, 2.85, -3.5, 2.2, .22, 12.5, concrete);
  box(4.72, 3.34, -3.5, 2.2, .7, 12.5, glass);
  box(3.59, 3.76, -3.5, .05, .04, 12.5, steel);
  box(3.61, 2.7, -3.5, .025, .025, 12.3, light);
  for (const z of [-9, -6, -3, 0, 2.6]) {
    box(3.6, 3.34, z, .035, .84, .035, steel);
    box(4.95, 1.31, z, .13, 2.62, .13, steel);
  }
  for (const z of [-7, -3, 1]) {
    box(4.7, .85, z, 1.65, .08, 1.5, concrete);
    box(5.23, .4, z, .5, .8, 1.25, steel);
    box(4.65, 1.19, z - .35, .6, .42, .035, steel);
    box(4.65, .91, z - .16, .35, .025, .13, steel);
    box(4.2, .47, z + .55, .52, .06, .49, timber);
    box(4.2, .72, z + .79, .52, .48, .04, timber);
    for (const x of [4, 4.4]) for (const offset of [.36, .74]) box(x, .22, z + offset, .025, .44, .025, steel);
  }
  // The gallery has a stair route rather than a floating slab.
  // These are spatial design elements, not a certified building design.
  for (let i = 0; i < 18; i++) {
    const h = (i + 1) * 2.96 / 18;
    box(4.72, h / 2, 7.8 - i * .29, 1.24, h, .29, concrete);
  }
  box(4.72, 2.98, -3.5, 2.2, .025, 12.5, timber);
  box(3.8, 2.99, -3.5, .33, .25, 11.7, steel);

  // Folded leaves on connected branch systems, with deterministic local
  // colour variation. Three instanced draws; no alpha cards or idle animation.
  const leafGeometry = geometry(new THREE.BufferGeometry());
  leafGeometry.setAttribute("position", new THREE.Float32BufferAttribute([0,-.11,0, -.055,-.025,0, 0,.015,.018, .055,-.025,0, 0,.14,-.005, -.04,.075,0, .04,.075,0], 3));
  leafGeometry.setIndex([0,1,2,0,2,3,1,5,2,3,2,6,5,4,2,2,4,6]); leafGeometry.computeVertexNormals();
  const trunkGeometry = geometry(new THREE.CylinderGeometry(.035, .085, 1, 9));
  const branchGeometry = geometry(new THREE.CylinderGeometry(.004, .022, 1, 5));
  const treeCount = 24, branchesPerTree = 18, leavesPerBranch = 22;
  const foliage = new THREE.InstancedMesh(leafGeometry, leaf, treeCount * branchesPerTree * leavesPerBranch + 14 * 70);
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
        foliage.setMatrixAt(leafIndex, transform.matrix); foliage.setColorAt(leafIndex++, leafColour.setHSL(.23 + random(seed) * .04, .2 + random(seed + 1) * .15, .45 + random(seed + 2) * .22));
      }
    }
  }
  for (let i = 0; i < 14; i++) {
    for (let j = 0; j < 70; j++) {
      const seed = i * 80 + j;
      transform.position.set(3.65 + (random(seed) - .5) * .45, 2.87 - random(seed + 2) * .9, -9 + i * .8 + (random(seed + 1) - .5) * .6);
      transform.rotation.set(random(seed + 4) * 3, random(seed + 5) * 6, random(seed + 3) * 3); transform.scale.setScalar(.8); transform.updateMatrix(); foliage.setMatrixAt(leafIndex, transform.matrix); foliage.setColorAt(leafIndex++, leafColour.setHSL(.26, .3, .58));
    }
  }
  foliage.castShadow = foliage.receiveShadow = trunks.castShadow = branches.castShadow = true;
  root.add(foliage, trunks, branches);
  instances.push(foliage, trunks, branches);
  for (const [m, matrices] of boxMatrices) {
    const mesh = new THREE.InstancedMesh(boxGeometry, m, matrices.length);
    matrices.forEach((matrix, index) => mesh.setMatrixAt(index, matrix));
    mesh.name = m.name || "Architecture details";
    mesh.receiveShadow = true; mesh.castShadow = m !== glass && m !== backdrop && m !== light;
    root.add(mesh); instances.push(mesh);
  }

  return {
    root,
    cutaway(active: boolean) {
      if (sectioned === active) return;
      sectioned = active;
      // An overhead camera sections only the presentation building. Recorded
      // robot and collision materials are owned by another, untouched group.
      for (const m of [concrete, timber, steel, glass, light]) { m.clippingPlanes = active ? [section] : null; m.needsUpdate = true; }
    },
    setFloorLightMap(texture: THREE.Texture) {
      if (stone.lightMap) { textures.delete(stone.lightMap); stone.lightMap.dispose(); }
      textures.add(texture); stone.lightMap = texture; stone.lightMapIntensity = 1; stone.needsUpdate = true;
    },
    palette(paper: boolean) {
      concrete.color.set(paper ? 0xd0c7b6 : 0xc6bfb0);
      stone.color.set(paper ? 0xadb0a5 : 0x9aa397);
      backdrop.color.set(0xb3c4b8);
      leaf.color.set(0x71815d);
      light.color.set(paper ? 0xe1ece0 : 0x9abfbe);
    },
    dispose() { root.removeFromParent(); geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose()); instances.forEach(mesh => mesh.dispose()); },
  };
}
