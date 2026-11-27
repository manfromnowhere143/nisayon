import { PerspectiveCamera, Vector3 } from "three";
import { confineLabCamera } from "../scene/labCamera";

export interface RicciFrame {
  left: number;
  top: number;
  width: number;
  height: number;
}
export interface RicciCameraPose {
  yaw: number;
  pitch: number;
  scale: number;
}

/** Fit the approved robot within its interaction area, then extend the same
 * projection across the viewport. The room fills the screen without moving
 * the robot, resetting its orbit, or creating a second graphics context. */
export function frameRicciCamera(
  camera: PerspectiveCamera,
  viewport: { width: number; height: number },
  frame: RicciFrame,
  { yaw, pitch, scale }: RicciCameraPose,
  laboratory = false,
) {
  camera.fov = 26;
  const aspect = frame.width / frame.height;
  const vertical = Math.max(2.05, 1.02 / aspect) / scale;
  const distance = vertical / (2 * Math.tan((camera.fov * Math.PI) / 360));
  camera.position.set(
    Math.sin(yaw) * Math.cos(pitch) * distance,
    0.86 + Math.sin(pitch) * distance,
    Math.cos(yaw) * Math.cos(pitch) * distance,
  );
  const target = new Vector3(0, .86, 0);
  if (laboratory) {
    confineLabCamera(camera.position, target);
    // Preserve the fitted subject size when an aisle limits camera distance.
    // This projection adjustment belongs only to the presentation camera.
    camera.fov = 2 * Math.atan(Math.tan(26 * Math.PI / 360) * distance / camera.position.distanceTo(target)) * 180 / Math.PI;
  }
  camera.lookAt(target);
  camera.setViewOffset(
    frame.width,
    frame.height,
    -frame.left,
    -frame.top,
    viewport.width,
    viewport.height,
  );
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
}

export function ricciFramePoint(
  point: { x: number; y: number },
  viewport: { width: number; height: number },
  frame: RicciFrame,
) {
  return {
    x: ((point.x + 1) * viewport.width) / 2 - frame.left,
    y: ((1 - point.y) * viewport.height) / 2 - frame.top,
  };
}
