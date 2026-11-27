import * as THREE from "three";
import {expect,it} from "vitest";
import {createRicci} from "../src/concepts/ricciGeometry";
import {createCarryPreview,RICCI_TRACE} from "../src/concepts/ricciTrace";
it("keeps authored stance soles on the floor, separates the intended cases, and restores the original body",()=>{
 const body=createRicci(),study=createCarryPreview(body),original=body.root.position.clone();
 const transforms=new Map<THREE.Object3D,THREE.Matrix4>();body.root.traverse(o=>transforms.set(o,o.matrix.clone()));
 try {
  expect(RICCI_TRACE.status).toBe("Authored motion preview");let loadX=0,slipZ=0;
  for(const variant of ["load","slip"] as const)for(const time of [0,3,5,6,7.2,9,12]){
   study.apply(time,variant,true);body.root.updateMatrixWorld(true);study.root.updateMatrixWorld(true);
   const right=new THREE.Box3().setFromObject(body.soles.right),left=new THREE.Box3().setFromObject(body.soles.left);
   expect(right.min.y).toBeCloseTo(.003,3);expect(left.min.y).toBeGreaterThanOrEqual(.0029);
   if(time===7.2){if(variant==="load")loadX=study.root.getObjectByName("illustrative_payload")!.position.x;else slipZ=right.getCenter(new THREE.Vector3()).z;}
  }
  expect(loadX).toBeGreaterThan(.12);expect(slipZ).toBeGreaterThan(.07);
  study.apply(0,"load",false);body.root.updateMatrixWorld(true);expect(body.root.position.equals(original)).toBe(true);
  transforms.forEach((matrix,o)=>expect(o.matrix.equals(matrix)).toBe(true));expect(study.root.visible).toBe(false);
 }finally{study.dispose();body.dispose();}
});
