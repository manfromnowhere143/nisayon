import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { contactPair, type ContactView } from "../lab/contactData";
import { CONTACT_TRAVEL_M, LAB_LAYOUT } from "./laboratoryLayout";

/** One visual binding to the registered slider model. Furniture is presentation only. */
export function createContactBench() {
  const root = new THREE.Group(); root.name = "Contact dynamics bench";
  root.position.set(...LAB_LAYOUT.contact.position);
  root.rotation.y = LAB_LAYOUT.contact.yaw;
  root.userData.presentationOnly = true;
  const geometries: THREE.BufferGeometry[] = [], materials: THREE.Material[] = [];
  const material = (m: THREE.Material) => { materials.push(m); return m; };
  const metal = material(new THREE.MeshStandardMaterial({ name: "Satin contact instrument chassis", color: 0x697680, roughness: .36, metalness: .78 }));
  const ceramic = material(new THREE.MeshStandardMaterial({ name: "Contact study surface", color: 0xb8bfc1, roughness: .58, metalness: .03 }));
  const candidateMaterial = material(new THREE.MeshStandardMaterial({ color: 0xd9b784, roughness: .36, metalness: .7 }));
  const referenceMaterial = material(new THREE.MeshBasicMaterial({ color: 0x93bdd4, wireframe: true, transparent: true, opacity: .85 }));
  const box = (name: string, size: [number, number, number], position: [number, number, number], m: THREE.Material) => {
    const g = new RoundedBoxGeometry(...size, 1, .001); geometries.push(g);
    const mesh = new THREE.Mesh(g, m); mesh.name = name; mesh.position.set(...position);
    mesh.castShadow = mesh.receiveShadow = true; mesh.userData.instrument = "contact"; root.add(mesh); return mesh;
  };
  // A narrow instrument track instead of a second general-purpose table.
  // The datum and SI divisions explain the travel; they are visual references,
  // not an invented encoder or hardware measurement. No decorative actuator.
  const batches = new Map<THREE.Material, THREE.BufferGeometry[]>();
  const piece = (size: [number, number, number], position: [number, number, number], m: THREE.Material) => {
    const g = new RoundedBoxGeometry(...size, 1, .002);
    g.translate(...position);
    const list = batches.get(m) ?? []; list.push(g); batches.set(m, list);
  };
  piece([CONTACT_TRAVEL_M + .26,.06,.32], [.75,-.042,0], metal);
  piece([CONTACT_TRAVEL_M + .2,.012,.24], [.75,-.006,0], ceramic);
  for (const x of [.18, 1.32]) {
    piece([.05,.94,.065], [x,-.52,0], metal);
    piece([.10,.04,.46], [x,-1,0], metal);
    piece([.08,.025,.27], [x,-.084,0], metal);
  }
  for (const [m, parts] of batches) {
    const g = mergeGeometries(parts)!; parts.forEach(p => p.dispose()); geometries.push(g);
    const mesh = new THREE.Mesh(g,m); mesh.name = m === ceramic ? "Visible contact plane" : "Presentation track support";
    mesh.castShadow = mesh.receiveShadow = true; mesh.userData.instrument = "contact"; root.add(mesh);
  }
  const scaleMaterial = material(new THREE.LineBasicMaterial({ color: 0x52606a, transparent: true, opacity: .8 }));
  const scalePoints: number[] = [];
  for (let i = 0; i <= 15; i++) {
    const x = i / 10, major = i % 5 === 0;
    scalePoints.push(x,.0008,.118,x,.0008,major ? .073 : .095);
  }
  const scaleGeometry = new THREE.BufferGeometry();
  scaleGeometry.setAttribute("position", new THREE.Float32BufferAttribute(scalePoints,3)); geometries.push(scaleGeometry);
  const scale = new THREE.LineSegments(scaleGeometry,scaleMaterial); scale.name = "Presentation scale, 0.1 m divisions"; root.add(scale);
  const candidate = box("Candidate simulated slider", [.08,.04,.06], [0,.02,0], candidateMaterial);
  const reference = box("Reference simulated slider", [.08,.04,.06], [0,.02,0], referenceMaterial);
  candidate.visible = reference.visible = false;
  candidate.userData.experimentVisual = reference.userData.experimentVisual = true;
  reference.castShadow = reference.receiveShadow = false;
  const axes = new THREE.AxesHelper(.18); root.add(axes); axes.visible = false;
  // Up to eight retained contacts plus one motor vector in one bounded draw.
  const vectorGeometry = new THREE.BufferGeometry(); geometries.push(vectorGeometry);
  const vectorPositions = new THREE.Float32BufferAttribute(new Float32Array(9 * 18),3);
  vectorPositions.setUsage(THREE.DynamicDrawUsage);
  const vectorColours = new THREE.Float32BufferAttribute(new Float32Array(9 * 18),3);
  vectorGeometry.setAttribute("position",vectorPositions); vectorGeometry.setAttribute("color",vectorColours);
  vectorGeometry.setDrawRange(0,0);
  const vectorMaterial = material(new THREE.LineBasicMaterial({ vertexColors: true }));
  const vectors = new THREE.LineSegments(vectorGeometry,vectorMaterial); vectors.name = "Retained simulated force vectors";
  vectors.frustumCulled = false; root.add(vectors);
  const blue = new THREE.Color(0x9ac7dc), sand = new THREE.Color(0xd9b784);
  const tip = new THREE.Vector3(), wing = new THREE.Vector3(), neck = new THREE.Vector3();
  let vectorCount = 0;
  const arrow = (origin: THREE.Vector3, force: THREE.Vector3, colour: THREE.Color) => {
    const length = force.length() * .02;
    if (length <= 1e-9 || vectorCount === 9) return;
    const direction = force.normalize(); tip.copy(origin).addScaledVector(direction,length);
    wing.crossVectors(direction,Math.abs(direction.z) < .9 ? new THREE.Vector3(0,0,1) : new THREE.Vector3(0,1,0)).normalize().multiplyScalar(Math.min(.012,length*.15));
    neck.copy(tip).addScaledVector(direction,-Math.min(.025,length*.3));
    const points = [origin,tip,tip,neck.clone().add(wing),tip,neck.clone().sub(wing)];
    points.forEach((p,i) => { const j = vectorCount*6+i; vectorPositions.setXYZ(j,p.x,p.y,p.z); vectorColours.setXYZ(j,colour.r,colour.g,colour.b); });
    vectorCount++;
  };
  const lineMaterials = [new THREE.LineBasicMaterial({ color: 0x93bdd4, transparent: true, opacity: .5 }), new THREE.LineBasicMaterial({ color: 0xd9b784, transparent: true, opacity: .5 })];
  materials.push(...lineMaterials);
  const paths = lineMaterials.map(m => {
    const g = new THREE.BufferGeometry(); geometries.push(g);
    const line = new THREE.Line(g,m); root.add(line); return line;
  });
  let traceIdentity = "";
  return { root, update(view: ContactView | null, inspecting = true) {
    candidate.visible = reference.visible = !!view;
    axes.visible = inspecting && !!view?.forces;
    vectorCount = 0; vectorGeometry.setDrawRange(0,0); vectors.visible = inspecting && !!view?.forces;
    paths.forEach(p => p.visible = inspecting && !!view);
    if (!view) return;
    const pair = contactPair(view), row = pair.candidate?.rows[view.index];
    const ref = pair.reference?.rows[view.index];
    candidate.visible = !!row; reference.visible = inspecting && !!ref;
    if (row) candidate.position.set(row.x_m,row.z_m,0);
    if (ref) reference.position.set(ref.x_m,ref.z_m,0);
    const identity = `${view.packet.packet_sha256}:${view.condition}`;
    if (identity !== traceIdentity) {
      traceIdentity = identity;
      [pair.reference,pair.candidate].forEach((trace,i) => {
        // Retiring the old attributes also releases their GPU buffers when a
        // newly executed protocol has a different number of retained rows.
        paths[i]!.geometry.dispose();
        paths[i]!.geometry.setFromPoints(trace?.rows.map(r => new THREE.Vector3(r.x_m,.002,0)) ?? []);
      });
    }
    if (view.forces && row) {
      row.contacts.forEach(contact => {
        const [x,y,z] = contact.position_m, [fx,fy,fz] = contact.force_on_slider_world_n;
        arrow(new THREE.Vector3(x,z,-y),new THREE.Vector3(fx,fz,-fy),blue);
      });
      arrow(new THREE.Vector3(row.x_m,row.z_m+.04,0),new THREE.Vector3(row.applied_n,0,0),sand);
      vectorGeometry.setDrawRange(0,vectorCount*6); vectorPositions.needsUpdate = vectorColours.needsUpdate = true;
    }
  }, dispose() {
    root.removeFromParent(); geometries.forEach(g=>g.dispose()); materials.forEach(m=>m.dispose());
    axes.dispose();
  } };
}
