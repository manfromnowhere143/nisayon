import * as THREE from "three";
import { expect, it, vi } from "vitest";
import { createRicci, PELVIS_HEIGHT, ricciPick, SoleReveal } from "../src/concepts/ricciGeometry";
import { RICCI_CATALOG } from "../src/concepts/ricciCatalog";

it("binds every visible assembly to R01 and retains the right-handed floor/pelvis contract",()=>{
  const model=createRicci();
  try {
    expect(model.root.position.y).toBe(PELVIS_HEIGHT);
    const bounds=new THREE.Box3().setFromObject(model.root);
    expect(bounds.min.y).toBeCloseTo(.003,3); expect(bounds.max.y).toBeCloseTo(1.749,3);
    expect(model.meshes.length).toBeGreaterThan(100);
    expect(new Set(model.meshes.map(m=>m.name)).size).toBe(model.meshes.length);
    for(const part of RICCI_CATALOG){
      expect(model.parts.get(part.id)?.length).toBeGreaterThan(0);
      for(const instance of part.instances) expect(model.meshes.some(m=>m.userData.id===part.id&&m.userData.instance===instance)).toBe(true);
    }
    expect(model.soles.left.parent?.name).toBe("ankle_foot_left");
    expect(model.soles.left.parent?.parent?.name).toBe("leg_shank_left");
    expect(model.parts.get("arm_distal")![0]!.parent?.name).toBe("arm_upper_left");
    const left=new THREE.Vector3();model.soles.left.getWorldPosition(left);expect(left.x).toBeGreaterThan(0);
    for(const m of model.meshes) for(const number of m.geometry.getAttribute("position").array) expect(Number.isFinite(number)).toBe(true);
  }finally{model.dispose();}
});

it("raycasts the actual sole on both anatomical sides and refuses a miss",()=>{
  const model=createRicci();
  try {
    for(const [side,x] of [["left",.147],["right",-.147]] as const){
      const ray=new THREE.Raycaster(new THREE.Vector3(x,.012,3),new THREE.Vector3(0,0,-1));
      expect(ricciPick(ray,model)).toEqual({id:"ankle_foot",instance:`ankle_foot_${side}`,detail:"sole"});
    }
    const front=new THREE.Raycaster(new THREE.Vector3(0,1.365,3),new THREE.Vector3(0,0,-1));
    expect(ricciPick(front,model)?.id).toBe("torso_spine"); // rear compute cover cannot win through the chest
    const rear=new THREE.Raycaster(new THREE.Vector3(0,1.365,-3),new THREE.Vector3(0,0,1));
    expect(ricciPick(rear,model)?.id).toBe("compute_thermal");
    expect(ricciPick(new THREE.Raycaster(new THREE.Vector3(4,1,3),new THREE.Vector3(0,0,-1)),model)).toBeNull();
  }finally{model.dispose();}
});

it("retargets during a reveal, moves only the selected layer, and restores the assembly exactly",()=>{
  const model=createRicci(),reveal=new SoleReveal(model);
  const transforms=model.meshes.map(m=>m.matrix.clone());
  try {
    reveal.select("left");reveal.update(1/60);
    expect(model.soles.left.position.x).toBeGreaterThan(0);expect(model.soles.left.position.x).toBeLessThan(.16);
    expect(model.soles.right.position.x).toBe(0);
    reveal.select("right");for(let i=0;i<80;i++)reveal.update(1/60);
    expect(model.soles.left.position.x).toBe(0);expect(model.soles.right.position.x).toBe(-.16);
    reveal.select(null);for(let i=0;i<80;i++)reveal.update(1/60);
    expect(model.soles.left.position.x).toBe(0);expect(model.soles.right.position.x).toBe(0);
    expect(reveal.update(1/60)).toBe(false);
    model.meshes.forEach((m,i)=>expect(m.matrix.equals(transforms[i]!)).toBe(true));
  }finally{model.dispose();}
});

it("keeps every catalog assembly reachable by a ray against its visible geometry", () => {
  const model = createRicci(), reached = new Set<string>();
  try {
    for (const mesh of model.meshes) {
      if (reached.has(mesh.userData.id as string)) continue;
      const target = new THREE.Box3().setFromObject(mesh).getCenter(new THREE.Vector3());
      for (const direction of [new THREE.Vector3(0,0,-1), new THREE.Vector3(0,0,1), new THREE.Vector3(1,0,0), new THREE.Vector3(-1,0,0)]) {
        const origin = target.clone().addScaledVector(direction, -3);
        const pick = ricciPick(new THREE.Raycaster(origin, direction), model);
        if (pick) reached.add(pick.id);
      }
    }
    expect([...reached].sort()).toEqual(RICCI_CATALOG.map(part => part.id).sort());
  } finally { model.dispose(); }
});

it("makes reduced motion instantaneous and repeated selection stable, then releases every owned resource once",()=>{
  const model=createRicci(),reveal=new SoleReveal(model);
  const geometry=model.meshes.map(m=>vi.spyOn(m.geometry,"dispose")),materials=model.meshes.map(m=>vi.spyOn(m.material,"dispose"));
  reveal.select("left");expect(reveal.update(0,true)).toBe(false);expect(model.soles.left.position.x).toBe(.16);
  reveal.select("left");reveal.update(0,true);expect(model.soles.left.position.x).toBe(.16);
  reveal.select(null);reveal.update(0,true);expect(model.soles.left.position.x).toBe(0);
  model.dispose();model.dispose();
  for(const spy of [...geometry,...materials])expect(spy).toHaveBeenCalledTimes(1);
});
