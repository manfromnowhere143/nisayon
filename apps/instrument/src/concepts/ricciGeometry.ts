import * as THREE from "three";
import { RICCI_CATALOG, type RicciPartId } from "./ricciCatalog";

/** Display geometry, not engineering CAD. Source: Rev A D00–D04/R01/R02,
 * SHA256 cd8839dcd1a3811c782318eae444d1c5ed1df583f784f6eee31af43c37bfe97d.
 * Front sections follow the visible concept. Depth, back, reference pivots and
 * sole construction are proposed. No joint ranges or mechanism are implied. */
export const RICCI_GEOMETRY_REVISION = "ricci-front-a01";
export const PELVIS_HEIGHT = .98;
export type RicciSide = "left" | "right";
export interface RicciPick { id: RicciPartId; instance: string; detail: string }
export type Section = readonly [y: number, halfWidth: number, halfDepth: number, x?: number, z?: number];
type Point = readonly [number, number, number];
type Material = THREE.MeshStandardMaterial;

// Catmull-Rom interpolation of named section dimensions; never a remote mesh.
function cubic(a: number, b: number, c: number, d: number, t: number) {
  return b + .5 * t * (c - a + t * (2 * a - 5 * b + 4 * c - d + t * (3 * (b - c) + d - a)));
}
export function loft(sections: readonly Section[], { arc = Math.PI * 2, start = -Math.PI, cap = true, square = 1 }: { arc?: number; start?: number; cap?: boolean; square?: number } = {}) {
  const radial = 64, rows = (sections.length - 1) * 8;
  const vertices: number[] = [], indices: number[] = [];
  for (let j = 0; j <= rows; j++) {
    const step = j / rows * (sections.length - 1), i = Math.min(sections.length - 2, Math.floor(step)), t = step - i;
    const b = sections[i]!, c = sections[i + 1]!, a = sections[Math.max(0, i - 1)]!, d = sections[Math.min(sections.length - 1, i + 2)]!;
    const y = cubic(a[0], b[0], c[0], d[0], t);
    const value = (k: number) => cubic(a[k] ?? 0, b[k] ?? 0, c[k] ?? 0, d[k] ?? 0, t);
    const rx = Math.max(.0003, value(1)), rz = Math.max(.0003, value(2));
    for (let k = 0; k <= radial; k++) {
      const angle = start + arc * k / radial, sn = Math.sin(angle), cs = Math.cos(angle);
      vertices.push(value(3) + Math.sign(sn) * Math.abs(sn) ** square * rx, y, value(4) + Math.sign(cs) * Math.abs(cs) ** square * rz);
      if (j < rows && k < radial) { const n = j * (radial + 1) + k, m = n + radial + 1; indices.push(n, n + 1, m, n + 1, m + 1, m); }
    }
  }
  if (cap && arc >= Math.PI * 2 - .001) for (const top of [false, true]) {
    const s = sections[top ? sections.length - 1 : 0]!, center = vertices.length / 3, offset = top ? rows * (radial + 1) : 0;
    vertices.push(s[3] ?? 0, s[0], s[4] ?? 0);
    for (let k = 0; k < radial; k++) indices.push(center, offset + k + (top ? 0 : 1), offset + k + (top ? 1 : 0));
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setIndex(indices); geometry.computeVertexNormals(); geometry.computeBoundingSphere();
  return geometry;
}

export interface RicciAssembly {
  root: THREE.Group;
  meshes: THREE.Mesh<THREE.BufferGeometry, Material>[];
  parts: Map<RicciPartId, THREE.Group[]>;
  soles: Record<RicciSide, THREE.Group>;
  dispose: () => void;
}

export function createRicci(): RicciAssembly {
  const root = new THREE.Group(); root.name = "ricci_pelvis_root"; root.position.y = PELVIS_HEIGHT;
  root.userData = { revision: RICCI_GEOMETRY_REVISION, frame: "metres; +Y up; +Z forward; +X robot-left", proposedDepth: true };
  const parts = new Map<RicciPartId, THREE.Group[]>(RICCI_CATALOG.map(part => [part.id, []]));
  const meshes: RicciAssembly["meshes"] = [];
  const pearl = new THREE.MeshPhysicalMaterial({ color: 0xaeb1b8, metalness: .78, roughness: .36, clearcoat: .16, clearcoatRoughness: .34 });
  const titanium = new THREE.MeshStandardMaterial({ color: 0x5b5e63, metalness: .86, roughness: .29 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x15171a, metalness: .68, roughness: .35 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x17191c, metalness: .12, roughness: .77 });
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x040609, metalness: .34, roughness: .16, clearcoat: 1, clearcoatRoughness: .09 });
  const origins = new WeakMap<THREE.Group, THREE.Vector3>(); origins.set(root, new THREE.Vector3(0, PELVIS_HEIGHT, 0));
  const make = (id: RicciPartId, at: Point, parent = root, side?: RicciSide) => {
    const group = new THREE.Group(); group.name = side ? `${id}_${side}` : id;
    group.userData = { id, instance: group.name, proposedDepth: true };
    group.position.copy(new THREE.Vector3(...at).sub(origins.get(parent)!)); parent.add(group);
    origins.set(group, new THREE.Vector3(...at)); parts.get(id)!.push(group); return group;
  };
  const add = (parent: THREE.Group, name: string, geometry: THREE.BufferGeometry, material: Material) => {
    const m = new THREE.Mesh(geometry, material.clone()); m.name = `${parent.name}.${name}`;
    m.userData = { id: parent.userData.id, instance: parent.userData.instance, detail: name } satisfies RicciPick;
    m.castShadow = true; m.receiveShadow = true; parent.add(m); meshes.push(m); return m;
  };
  const skin = (parent: THREE.Group, name: string, sections: readonly Section[], material: Material = pearl, options: Parameters<typeof loft>[1] = {}) => {
    const geometry = loft(sections, options), o = origins.get(parent)!;
    geometry.translate(-o.x, -o.y, -o.z); return add(parent, name, geometry, material);
  };
  const ellipsoid = (parent: THREE.Group, name: string, p: Point, scale: Point, material: Material) => {
    const m = add(parent, name, new THREE.SphereGeometry(1, 40, 24), material);
    m.position.copy(new THREE.Vector3(...p).sub(origins.get(parent)!)); m.scale.set(...scale); return m;
  };
  const torus = (parent: THREE.Group, name: string, p: Point, radius: number, tube: number, material: Material, axis: "x" | "z" = "z") => {
    const m = add(parent, name, new THREE.TorusGeometry(radius, tube, 10, 56), material);
    m.position.copy(new THREE.Vector3(...p).sub(origins.get(parent)!)); if (axis === "x") m.rotation.y = Math.PI / 2; return m;
  };
  const line = (parent: THREE.Group, name: string, points: readonly Point[], radius: number, material: Material) => {
    const o = origins.get(parent)!, curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p).sub(o)));
    return add(parent, name, new THREE.TubeGeometry(curve, Math.max(12, points.length * 8), radius, 8, false), material);
  };

  const waist = make("waist_pelvis", [0, PELVIS_HEIGHT, 0]);
  skin(waist, "waist_core", [[1.00,.063,.058],[1.07,.055,.053],[1.16,.072,.062],[1.21,.09,.07]], dark);
  for (let i = 0; i < 4; i++) skin(waist, `abdominal_lamella_${i}`, [[1.025 + i * .032,.052 + i * .004,.059],[1.047 + i * .032,.057 + i * .004,.06]], titanium, { start: -1.45, arc: 2.9, cap: false });
  skin(waist, "pelvic_front", [[.895,.032,.052,0,.023],[.94,.066,.072,0,.014],[1.015,.12,.087],[1.05,.129,.075],[1.075,.105,.06]], pearl, { start: -1.65, arc: 3.3, cap: false });
  for (const s of [-1, 1]) line(waist, `waist_side_${s}`, [[s*.067,1.03,.03],[s*.086,1.085,.034],[s*.094,1.15,.035],[s*.108,1.19,.029]], .008, dark);

  const torso = make("torso_spine", [0,1.22,0], waist);
  skin(torso,"thorax",[[1.155,.045,.065,0,.015],[1.19,.077,.075],[1.25,.113,.085],[1.34,.147,.105],[1.40,.147,.091],[1.435,.12,.066],[1.455,.076,.05]], pearl);
  skin(torso,"sternum_lower",[[1.153,.043,.011,0,.079],[1.18,.065,.019,0,.074],[1.23,.08,.024,0,.071],[1.26,.073,.021,0,.082]], pearl, {start:-1.6,arc:3.2,cap:false});
  line(torso,"chest_seam",[[-.116,1.245,.064],[-.085,1.27,.09],[-.06,1.28,.103],[0,1.283,.109],[.06,1.28,.103],[.085,1.27,.09],[.116,1.245,.064]],.0013,dark);
  line(torso,"sternum_seam",[[0,1.43,.067],[0,1.39,.097],[0,1.32,.107],[0,1.285,.11]],.00065,titanium);
  for (const s of [-1,1]) {
    const slot = ellipsoid(torso,`clavicle_recess_${s}`,[s*.092,1.423,.057],[.031,.006,.012],dark); slot.rotation.z = -s * .2;
    for (const y of [1.32,1.35]) ellipsoid(torso,`panel_fastener_${s}_${y}`,[s*.109,y,.078],[.0015,.0015,.001],titanium);
  }
  const head = make("head_visor", [0,1.51,0], torso);
  skin(head,"neck",[[1.43,.035,.033],[1.46,.036,.033],[1.50,.028,.029],[1.53,.034,.032]],dark);
  for (const s of [-1,1]) for (let i=0;i<2;i++) line(head,`neck_tendon_${s}_${i}`,[[s*(.028-i*.009),1.448,.021],[s*(.026-i*.008),1.478,.03],[s*(.018-i*.004),1.514,.025]],.003,titanium);
  const cranialSections:Section[]=[[1.50,.019,.024,0,.02],[1.535,.039,.052,0,.003],[1.59,.065,.073],[1.65,.083,.085],[1.705,.074,.073],[1.735,.049,.052],[1.749,.013,.022]];
  skin(head,"cranial_shell",cranialSections,pearl);
  const visor=skin(head,"uninterrupted_visor",[[1.506,.014,.01],[1.525,.025,.03],[1.565,.047,.051],[1.62,.066,.07],[1.676,.069,.071],[1.699,.058,.052]],glass,{start:-Math.PI/2,arc:Math.PI,cap:false});
  // Conform the optical surface to the SAME smooth helmet envelope. Independent
  // intersecting ellipsoids would break the uninterrupted visor into islands.
  const envelope=loft(cranialSections), ep=envelope.getAttribute("position"), vp=visor.geometry.getAttribute("position");
  const sampleRows=(cranialSections.length-1)*8;
  for(let v=0;v<vp.count;v++){
    const y=vp.getY(v)+1.51, x=vp.getX(v); let r=0;
    while(r<sampleRows-1 && ep.getY((r+1)*65)<y)r++;
    const y0=ep.getY(r*65),y1=ep.getY((r+1)*65),t=THREE.MathUtils.clamp((y-y0)/(y1-y0),0,1);
    const rx=THREE.MathUtils.lerp(Math.abs(ep.getX(r*65+16)),Math.abs(ep.getX((r+1)*65+16)),t);
    const front=THREE.MathUtils.lerp(ep.getZ(r*65+32),ep.getZ((r+1)*65+32),t);
    const back=THREE.MathUtils.lerp(ep.getZ(r*65),ep.getZ((r+1)*65),t);
    vp.setZ(v,(front+back)/2+(front-back)/2*Math.sqrt(Math.max(0,1-(x/rx)**2))+.0018);
  }
  vp.needsUpdate=true; visor.geometry.computeVertexNormals();visor.geometry.computeBoundingSphere();envelope.dispose();
  for(const s of [-1,1]) {
    ellipsoid(head,`side_disc_${s}`,[s*.078,1.65,-.003],[.009,.038,.035],titanium);
    torus(head,`side_disc_rim_${s}`,[s*.084,1.65,-.003],.031,.0025,pearl,"x");
  }
  const crown=ellipsoid(head,"crown_inset",[0,1.744,-.004],[.028,.002,.015],dark); crown.rotation.x=-.1;

  const outer = make("outer_shell", [0,1.29,0], torso);
  for(const s of [-1,1]) skin(outer,`flank_guard_${s}`,[[1.17,.011,.024,s*.083,-.005],[1.23,.022,.047,s*.112,-.007],[1.29,.014,.057,s*.133,-.01]],pearl);

  const soles = {} as Record<RicciSide,THREE.Group>;
  for (const side of ["left","right"] as const) {
    const s = side === "left" ? 1 : -1, variant = side === "left" ? 1 : .97;
    const shoulderX=s*.184, elbowX=s*.255, wristX=s*.32;
    const arm=make("arm_upper",[shoulderX,1.395,0],torso,side);
    ellipsoid(arm,"shoulder_envelope",[s*.184,1.39,0],[.053,.044,.045],dark);
    for(const offset of [-.017,0,.017]) torus(arm,`shoulder_ring_${offset}`,[s*(.168+offset),1.39,0],.047,.004,titanium,"x");
    skin(arm,"shoulder_cover",[[1.31,.022,.03,s*.222,.005],[1.35,.038,.049,s*.221,0],[1.405,.039,.057,s*.215,0],[1.447,.023,.038,s*.208,0],[1.454,.004,.011,s*.198,0]],pearl);
    skin(arm,"upper_arm_shell",[[1.173,.031,.031,elbowX,0],[1.21,.038,.041,s*.246,-.002],[1.29,.04,.046,s*.224,0],[1.339,.033,.035,s*.207,0]],pearl);
    const forearm=make("arm_distal",[elbowX,1.148,0],arm,side);
    ellipsoid(forearm,"elbow_envelope",[elbowX,1.151,.005],[.036,.039,.036],dark);
    torus(forearm,"elbow_outer_ring",[elbowX,1.151,.027],.029,.0035,titanium);
    line(forearm,"elbow_bridge",[[elbowX-s*.015,1.173,.031],[elbowX-s*.009,1.151,.04],[elbowX+s*.004,1.128,.034]],.007,titanium);
    skin(forearm,"forearm_shell",[[.943,.024,.025,wristX,.006],[1.00,.029,.035,s*.303,0],[1.075,.037*variant,.041,s*.279,0],[1.118,.036*variant,.034,s*.264,0]],pearl);
    line(forearm,"forearm_seam",[[s*.327,.953,.017],[s*.312,1.008,.029],[s*.298,1.067,.031],[s*.284,1.108,.026]],.0008,titanium);
    ellipsoid(forearm,"wrist_joint",[wristX,.925,.007],[.025,.021,.024],dark);
    torus(forearm,"wrist_collar",[wristX,.928,.008],.022,.0035,titanium).rotation.x=Math.PI/2;
    skin(forearm,"palm",[[.846,.028,.014,s*.326,.016],[.868,.03,.017,s*.324,.014],[.907,.023,.02,wristX,.01]],pearl,{square:.7});
    // Relaxed reference pose only. Independent finger segments/knuckles,
    // without actuators, specified ranges, tendons or force claims.
    for(let finger=0;finger<4;finger++) {
      const fx=s*(.302+finger*.015), length=.078 - Math.abs(finger-1)*.008;
      const points: Point[]=[[fx,.853,.016],[fx+s*.003,.827,.026],[fx-s*.003,.802,.045],[fx-s*.017,.853-length,.057]];
      for(let segment=0;segment<3;segment++) {
        const a=points[segment]!,b=points[segment+1]!, start=new THREE.Vector3(...a).lerp(new THREE.Vector3(...b),.1),end=new THREE.Vector3(...a).lerp(new THREE.Vector3(...b),.9);
        line(forearm,`finger_${finger}_${segment}`,[start.toArray(),end.toArray()],.0062-segment*.0005,pearl);
        ellipsoid(forearm,`knuckle_${finger}_${segment}`,a,[.0068,.007,.007],dark);
      }
      ellipsoid(forearm,`fingertip_${finger}`,points[3]!,[.0055,.007,.006],pearl);
    }
    line(forearm,"thumb_proximal",[[s*.302,.879,.02],[s*.283,.853,.027]],.009,pearl);
    ellipsoid(forearm,"thumb_knuckle",[s*.283,.853,.027],[.009,.009,.009],dark);
    line(forearm,"thumb_distal",[[s*.283,.85,.027],[s*.281,.827,.044]],.007,pearl);

    const thigh=make("leg_upper",[s*.09,.975,0],waist,side);
    const hip=ellipsoid(thigh,"hip_surround",[s*.096,.965,.002],[.054,.084,.047],dark); hip.rotation.z=s*.4;
    for (const [index,z] of [.021,.027].entries()) {
      const hipRing=torus(thigh,`hip_ring_${index}`,[s*.098,.977,z],.051,.003,titanium);
      hipRing.scale.set(.68,1.35,1); hipRing.rotation.set(.55,0,s*.4);
    }
    const thighShell=skin(thigh,"thigh_shell",[[.647,.045,.044,s*.112,.005],[.72,.054,.061,s*.116,0],[.83,.066*variant,.073,s*.113,-.007],[.94,.064*variant,.068,s*.104,-.018],[.985,.045,.049,s*.102,-.021]],pearl);
    const thighVertices=thighShell.geometry.getAttribute("position");
    for(let v=0;v<thighVertices.count;v++){
      const wy=thighVertices.getY(v)+.975,wx=thighVertices.getX(v)+s*.09;
      thighVertices.setY(v,thighVertices.getY(v)+THREE.MathUtils.clamp((wy-.83)/.155,0,1)*s*(wx-s*.102)*1.1);
    }
    thighVertices.needsUpdate=true;thighShell.geometry.computeVertexNormals();thighShell.geometry.computeBoundingSphere();
    line(thigh,"thigh_seam",[[s*.145,.66,.024],[s*.152,.78,.047],[s*.146,.91,.04]],.0009,titanium);
    ellipsoid(thigh,"knee_envelope",[s*.114,.612,0],[.046,.045,.045],dark);
    torus(thigh,"knee_front_rim",[s*.114,.612,.037],.031,.004,titanium);
    ellipsoid(thigh,"knee_front_cap",[s*.114,.612,.041],[.027,.029,.008],pearl);
    ellipsoid(thigh,"knee_center",[s*.114,.612,.049],[.009,.009,.0015],dark);
    for(const v of [-1,1]) torus(thigh,`knee_side_ring_${v}`,[s*.114+v*.043,.612,0],.03,.003,titanium,"x");
    const shank=make("leg_shank",[s*.114,.612,0],thigh,side);
    skin(shank,"tapered_shin",[[.181,.026,.029,s*.142,-.003],[.245,.028,.034,s*.139,-.003],[.35,.041,.044,s*.133,-.005],[.455,.058*variant,.055,s*.126,-.011],[.535,.052,.048,s*.12,-.005],[.573,.037,.036,s*.116,.001]],pearl);
    line(shank,"shin_front_seam",[[s*.137,.192,.027],[s*.137,.31,.034],[s*.13,.445,.047],[s*.118,.547,.04]],.00065,titanium);
    const foot=make("ankle_foot",[s*.142,.155,0],shank,side);
    ellipsoid(foot,"ankle_envelope",[s*.142,.153,0],[.027,.03,.033],dark);
    skin(foot,"ankle_cuff",[[.094,.035,.04,s*.144,.004],[.132,.032,.034,s*.142,0],[.159,.023,.028,s*.142,0]],titanium);
    for(const v of [-1,1]) torus(foot,`ankle_side_ring_${v}`,[s*.142+v*.034,.126,.002],.025,.0035,pearl,"x");
    // D04 controls the front. Toe length/depth, rear and soles are proposed.
    skin(foot,"shaped_boot",[[.026,.051,.12,s*.147,.043],[.043,.052,.116,s*.147,.044],[.07,.046,.091,s*.145,.034],[.105,.033,.054,s*.143,.011],[.128,.028,.034,s*.142,.005]],pearl,{square:.72});
    line(foot,"toe_seam",[[s*.147-.045,.044,.119],[s*.147-.026,.053,.149],[s*.147,.057,.16],[s*.147+.026,.053,.149],[s*.147+.045,.044,.119]],.0009,titanium);
    const sole=new THREE.Group(); sole.name=`ankle_foot_${side}.sole_layer`; sole.userData={...foot.userData}; foot.add(sole); origins.set(sole,origins.get(foot)!);
    skin(sole,"sole",[[.003,.05,.118,s*.147,.043],[.012,.053,.122,s*.147,.043],[.023,.052,.12,s*.147,.043]],rubber,{square:.72});
    skin(sole,"sole_interface",[[.023,.051,.119,s*.147,.043],[.025,.05,.118,s*.147,.043]],titanium,{square:.72});
    soles[side]=sole;
  }

  // Unseen rear packaging: three deliberately simple schematic covers.
  // The labels/inspector carry uncertainty; there are no invented internals.
  for(const [id,y,w,h,d] of [["power_pack",1.215,.092,.105,.03],["compute_thermal",1.365,.073,.048,.014],["service_safety",1.07,.043,.035,.014]] as const) {
    const group=make(id,[0,y,-.075],torso);
    const panel=add(group,"schematic_rear_panel",new THREE.BoxGeometry(w*2,h*2,d),dark);
    panel.position.z=-.026; panel.userData.schematic=true;
    line(group,"panel_boundary",[[-w,y-h,-.118],[-w,y+h,-.118],[w,y+h,-.118],[w,y-h,-.118],[-w,y-h,-.118]],.0015,titanium);
  }
  root.updateMatrixWorld(true);
  pearl.dispose(); titanium.dispose(); dark.dispose(); rubber.dispose(); glass.dispose();
  let disposed=false;
  return {root,meshes,parts,soles,dispose:()=>{
    if(disposed)return; disposed=true;
    for(const mesh of meshes){mesh.geometry.dispose();mesh.material.dispose();}
    root.clear();
  }};
}

export function ricciPick(raycaster: THREE.Raycaster, assembly: RicciAssembly): RicciPick | null {
  assembly.root.updateMatrixWorld(true);
  // Sorted intersections of actual visible surfaces. Never select through the
  // nearer body, add hidden hit planes or confuse screen side with anatomy.
  const hit=raycaster.intersectObjects(assembly.meshes,false).find(item=>item.object.visible);
  return hit ? {id:hit.object.userData.id as RicciPartId,instance:hit.object.userData.instance as string,detail:hit.object.userData.detail as string} : null;
}

export class SoleReveal {
  private amounts: Record<RicciSide,number>={left:0,right:0};
  private target: RicciSide|null=null;
  constructor(private assembly: RicciAssembly) {}
  select(side:RicciSide|null){this.target=side;}
  update(seconds:number,instant=false){
    let active=false;
    for(const side of ["left","right"] as const){
      const target=this.target===side?1:0,current=this.amounts[side];
      const next=instant?target:THREE.MathUtils.damp(current,target,16,Math.min(.05,seconds));
      this.amounts[side]=Math.abs(next-target)<.0005?target:next;
      // Display separation on the sole's own lateral X axis; floor stays y=0.
      this.assembly.soles[side].position.x=this.amounts[side]===0?0:this.amounts[side]*(side==="left"?1:-1)*.16;
      active ||= this.amounts[side]!==target;
    }
    return active;
  }
}
