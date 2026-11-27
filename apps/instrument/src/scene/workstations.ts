// Authored furniture in metres. Rounded edges and joints describe construction;
// none of these meshes is a robot body, sensor, collider or measured apparatus.
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { LAB_LAYOUT } from "./laboratoryLayout";

export function createWorkstations() {
  const root = new THREE.Group(); root.name = "Recording workstations"; root.userData.presentationOnly = true;
  const finishes = {
    ceramic: new THREE.MeshStandardMaterial({ name: "Honed ceramic worktop", color: 0xb8bfc1, roughness: .48, metalness: .03 }),
    metal: new THREE.MeshStandardMaterial({ name: "Satin aluminium instrument frames", color: 0x818c94, roughness: .29, metalness: .78 }),
    graphite: new THREE.MeshStandardMaterial({ name: "Graphite housings", color: 0x20282e, roughness: .42, metalness: .46 }),
    polymer: new THREE.MeshStandardMaterial({ name: "Matte keys and cable jackets", color: 0x151c21, roughness: .76 }),
    glass: new THREE.MeshStandardMaterial({ name: "Inactive display glass", color: 0x080e12, roughness: .2, metalness: .15 }),
  };
  const batches = new Map<THREE.Material, THREE.BufferGeometry[]>();
  const ownedGeometry = new Set<THREE.BufferGeometry>();
  const pieces: { name: string; geometry: THREE.BufferGeometry; matrix: THREE.Matrix4 }[] = [];
  const transform = new THREE.Object3D();
  function add(name: string, g: THREE.BufferGeometry, m: THREE.Material, position: [number, number, number], rotation: [number, number, number] = [0, 0, 0]) {
    transform.position.set(...position); transform.rotation.set(...rotation); transform.updateMatrix();
    const source = g.index ? g.toNonIndexed() : g;
    if (source !== g) g.dispose();
    source.applyMatrix4(transform.matrix);
    const parts = batches.get(m) ?? []; parts.push(source); batches.set(m, parts);
    pieces.push({ name, geometry: source, matrix: transform.matrix.clone() });
  }
  function rounded(name: string, position: [number, number, number], size: [number, number, number], radius: number, m: THREE.Material, rotation?: [number, number, number]) {
    add(name, new RoundedBoxGeometry(...size, 1, radius), m, position, rotation);
  }
  function cylinder(name: string, position: [number, number, number], radius: number, length: number, m: THREE.Material, rotation?: [number, number, number]) {
    add(name, new THREE.CylinderGeometry(radius, radius, length, 12), m, position, rotation);
  }
  // A thin, supported worktop: ceramic, recessed chassis, removable service
  // tray, two sled legs and four adjustable feet. No floating solids.
  rounded("Ceramic top, 4 mm eased edge", [0, 1.02, 0], [1.66, .042, .94], .004, finishes.ceramic);
  rounded("Recessed chassis", [0, .988, 0], [1.59, .025, .87], .003, finishes.graphite);
  rounded("Service tray", [0, .945, -.29], [1.35, .055, .19], .007, finishes.graphite);
  for (const x of [-.68, .68]) {
    rounded("Sled upright", [x, .513, -.21], [.045, .93, .075], .006, finishes.metal);
    rounded("Sled rail", [x, .043, .015], [.055, .035, .75], .008, finishes.metal);
    rounded("Worktop support", [x, .967, .015], [.045, .025, .78], .004, finishes.metal);
    for (const z of [-.29, .32]) cylinder("Leveling foot", [x, .017, z], .028, .034, finishes.polymer);
  }
  // Monitor arm, two hinge barrels, rear ventilation and a continuous bezel.
  rounded("Monitor base", [0, 1.05, -.22], [.34, .018, .22], .006, finishes.metal);
  rounded("Monitor arm", [0, 1.235, -.27], [.044, .36, .052], .007, finishes.metal, [-.12, 0, 0]);
  cylinder("Monitor hinge", [0, 1.423, -.247], .031, .12, finishes.graphite, [0, 0, Math.PI / 2]);
  rounded("Monitor rear shell", [0, 1.455, -.21], [.81, .525, .042], .012, finishes.metal);
  rounded("Monitor inset bezel", [0, 1.455, -.185], [.798, .513, .012], .008, finishes.graphite);
  for (let i = 0; i < 9; i++) rounded("Rear ventilation", [-.12 + i * .03, 1.608, -.234], [.012, .036, .002], .0008, finishes.polymer);
  for (const x of [-.315, .315]) for (const y of [1.26, 1.65]) cylinder("Rear fastener", [x, y, -.234], .004, .003, finishes.graphite, [Math.PI / 2, 0, 0]);
  // Compact keyboard with visible key spacing, a single track surface and a
  // deliberate cable route down the arm into the under-desk service tray.
  rounded("Keyboard chassis", [-.09, 1.053, .23], [.44, .018, .155], .006, finishes.metal);
  for (let row = 0; row < 4; row++) for (let col = 0; col < 13; col++) {
    add("Keycap", new THREE.BoxGeometry(.026, .006, .026), finishes.polymer, [-.279 + col * .031, 1.066, .175 + row * .032]);
  }
  rounded("Track surface", [.274, 1.048, .23], [.14, .009, .15], .004, finishes.graphite);
  const cable = new THREE.CatmullRomCurve3([[.028, 1.44, -.24], [.038, 1.31, -.29], [.038, 1.11, -.3], [.045, .98, -.35]].map(p => new THREE.Vector3(...p as [number, number, number])));
  add("Contained signal cable", new THREE.TubeGeometry(cable, 16, .0035, 5, false), finishes.polymer, [0, 0, 0]);
  transform.position.set(...LAB_LAYOUT.console.position);
  transform.rotation.set(0, LAB_LAYOUT.console.yaw, 0); transform.updateMatrix();
  const stationMatrices = [transform.matrix.clone()];
  const instances: THREE.InstancedMesh[] = [];
  for (const [m, batch] of batches) {
    const g = mergeGeometries(batch)!; batch.forEach(piece => piece.dispose()); ownedGeometry.add(g);
    const mesh = new THREE.InstancedMesh(g, m, stationMatrices.length);
    mesh.name = m.name; stationMatrices.forEach((matrix, i) => mesh.setMatrixAt(i, matrix));
    mesh.castShadow = mesh.receiveShadow = false; root.add(mesh); instances.push(mesh);
  }
  // One standing console earns its place through one actual reading. No
  // duplicated inactive desks, seating or decorative telemetry.
  const face = new THREE.PlaneGeometry(.774, .48375); ownedGeometry.add(face);
  const screens = stationMatrices.map((matrix, i) => {
    const screen = new THREE.Mesh<THREE.PlaneGeometry, THREE.Material>(face, finishes.glass);
    screen.name = `Recording display ${i + 1}`;
    screen.position.set(0, 1.455, -.1775); screen.applyMatrix4(matrix);
    root.add(screen); return screen;
  });
  return {
    root, screens,
    bindDisplay(display: THREE.Material | null, identity: "recording" | "study" = "recording") {
      for (const screen of screens) {
        screen.material = display ?? finishes.glass;
        if (display) screen.userData.workstation = identity; else delete screen.userData.workstation;
      }
    },
    info: { piecesPerStation: pieces.length, stations: stationMatrices.length },
    dispose() { root.removeFromParent(); instances.forEach(mesh => mesh.dispose()); ownedGeometry.forEach(g => g.dispose()); Object.values(finishes).forEach(m => m.dispose()); },
  };
}
