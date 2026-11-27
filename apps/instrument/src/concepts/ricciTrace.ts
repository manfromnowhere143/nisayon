import * as THREE from "three";
import type { RicciAssembly, RicciSide } from "./ricciGeometry";

/** Authored key poses, not a simulator run or a controller trace. The time
 * base belongs to the viewer; no latent state is offered as a sensor input. */
export const RICCI_TRACE = {
  schema: "nisayon.ricci.authored-motion.v1", revision: "2026-11-23.1", duration: 12,
  status: "Authored motion preview",
  phases: [
    { at: 0, label: "Approach", contact: "Tray on stand", part: "arm_distal" },
    { at: 3, label: "Lift", contact: "Proposed hand–tray contact", part: "arm_distal" },
    { at: 6, label: "Step", contact: "Proposed right stance / left swing", part: "ankle_foot" },
    { at: 9, label: "Set down", contact: "Tray returns to stand", part: "arm_distal" },
    { at: 12, label: "Release", contact: "Preview ends; no task verdict", part: "arm_distal" },
  ] as const,
  observations: "Foot contact and wrist load would be independently measured. No sensor values are available in this preview.",
  comparison: "Shifted tray load versus slipping stance foot. Compare matched observation windows and a competent common response on held-out trials; distinguish completion from controlled abort. Early overlap and recovery benefit remain untested.",
} as const;
export type TraceCase = "load" | "slip";
const blend = (t: number, a: number, b: number) => { const v = THREE.MathUtils.clamp((t-a)/(b-a),0,1); return v*v*(3-2*v); };
export function tracePose(time: number, variant: TraceCase) {
  const t = THREE.MathUtils.clamp(time,0,RICCI_TRACE.duration);
  const reach = blend(t,0,2)*(1-blend(t,10,12)), lift = blend(t,2,4)*(1-blend(t,8,10));
  const step = blend(t,5,7), swing = t>5&&t<7 ? Math.sin(Math.PI*(t-5)/2)*.065 : 0;
  return { t, reach, lift, rootZ: step*.11, leftZ: step*.23, leftY: swing,
    perturbation: blend(t,6.2,7.2), variant,
    phase: [...RICCI_TRACE.phases].reverse().find(p=>t>=p.at) ?? RICCI_TRACE.phases[0] };
}

export function createCarryPreview(model: RicciAssembly) {
  const root = new THREE.Group(); root.name="ricci_authored_carry_study"; root.userData.presentationOnly=true;
  const metal=new THREE.MeshStandardMaterial({color:0x90969f,metalness:.75,roughness:.3});
  const dark=new THREE.MeshStandardMaterial({color:0x22262c,metalness:.45,roughness:.42});
  const loadMaterial=new THREE.MeshStandardMaterial({color:0xe1e3e8,roughness:.4,metalness:.15});
  const geometries:THREE.BufferGeometry[]=[];
  const box=(parent:THREE.Group,name:string,size:number[],position:number[],material:THREE.Material)=>{
    const geometry=new THREE.BoxGeometry(size[0],size[1],size[2]);geometries.push(geometry);
    const mesh=new THREE.Mesh(geometry,material);mesh.name=name;mesh.position.set(position[0]!,position[1]!,position[2]!);mesh.castShadow=mesh.receiveShadow=true;parent.add(mesh);return mesh;
  };
  const stand=new THREE.Group();stand.name="proposed_tray_stand";root.add(stand);
  box(stand,"stand_top",[.72,.025,.34],[0,.975,.37],dark);
  for(const x of [-.31,.31])for(const z of [.24,.5])box(stand,"stand_leg",[.025,.96,.025],[x,.48,z],dark);
  const tray=new THREE.Group();tray.name="light_tray_proposed";root.add(tray);
  box(tray,"tray_base",[.66,.012,.3],[0,0,0],metal);
  for(const z of [-.15,.15])box(tray,"tray_rim",[.66,.028,.01],[0,.014,z],metal);
  for(const x of [-.33,.33])box(tray,"tray_handle",[.01,.028,.3],[x,.014,0],metal);
  const load=box(tray,"illustrative_payload",[.1,.055,.09],[0,.033,0],loadMaterial);
  const origins=new Map<THREE.Group,{position:THREE.Vector3;rotation:THREE.Euler}>();
  model.parts.forEach(groups=>groups.forEach(g=>origins.set(g,{position:g.position.clone(),rotation:g.rotation.clone()})));
  const pelvis=model.root.position.clone();
  const group=(id:"arm_upper"|"arm_distal"|"leg_upper"|"leg_shank"|"ankle_foot",side:RicciSide)=>model.parts.get(id)!.find(g=>g.name.endsWith(side))!;
  const restore=()=>{model.root.position.copy(pelvis);origins.forEach((v,g)=>{g.position.copy(v.position);g.rotation.copy(v.rotation);});};
  return { root, apply(time:number,variant:TraceCase,enabled:boolean) {
    root.visible=enabled;restore();if(!enabled)return;
    const p=tracePose(time,variant);model.root.position.z=p.rootZ;
    // Display-only two-link pose fitting. This is not inverse dynamics or a
    // balance policy. Feet remain on authored paths; contact is not measured.
    model.root.position.y=pelvis.y-.018*Math.sin(Math.PI*Math.min(1,p.t/12))-.014;
    const trayY=1+.12*p.lift;
    // Fit the authored palm target to the tray throughout the step. These
    // two-link poses constrain presentation geometry, not force or balance.
    const armDy=1.395+(model.root.position.y-pelvis.y)-(trayY+.005), armDz=.35-p.rootZ;
    const upper=.247, distal=.275, reach=Math.min(upper+distal-.0001,Math.hypot(armDy,armDz));
    const elbow=Math.PI-Math.acos(THREE.MathUtils.clamp((upper*upper+distal*distal-reach*reach)/(2*upper*distal),-1,1));
    const shoulder=-Math.atan2(armDz,armDy)+Math.atan2(distal*Math.sin(elbow),upper+distal*Math.cos(elbow));
    for(const side of ["left","right"] as const){
      group("arm_upper",side).rotation.x=shoulder*p.reach;
      group("arm_distal",side).rotation.x=-elbow*p.reach;
      const footZ=side==="left"?p.leftZ:variant==="slip"?p.perturbation*.045:0;
      const dy=.82+(model.root.position.y-pelvis.y)-(side==="left"?p.leftY:0), dz=footZ-p.rootZ;
      const a=.363,b=.457,d=Math.min(a+b-.0001,Math.hypot(dy,dz));
      const knee=Math.PI-Math.acos(THREE.MathUtils.clamp((a*a+b*b-d*d)/(2*a*b),-1,1));
      const hip=-Math.atan2(dz,dy)-Math.atan2(b*Math.sin(knee),a+b*Math.cos(knee));
      group("leg_upper",side).rotation.x=hip;group("leg_shank",side).rotation.x=knee;group("ankle_foot",side).rotation.x=-hip-knee;
    }
    tray.position.set(0,trayY,.37); // Stand stays fixed; reach changes with the step.
    load.position.x=variant==="load"?p.perturbation*.13:0;
  },dispose(){restore();root.removeFromParent();geometries.forEach(g=>g.dispose());metal.dispose();dark.dispose();loadMaterial.dispose();} };
}
