import { afterEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { lightSnapshot } from "../src/scene/lightSnapshot";
import { refinementSession, refinementSize, REFINEMENT_LIMITS } from "../src/scene/refinement";
afterEach(() => { vi.useRealTimers(); });

it("freezes actual world transforms and separates ghost figures and evidence from physical illumination", () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera();
  const body = new THREE.Group(); body.position.set(1, 2, 3); body.rotation.z = .6;
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(.1, .2, .3), new THREE.MeshStandardMaterial({ emissive: 0xffffff }));
  mesh.position.set(.2, 0, -.1); body.add(mesh); scene.add(body);
  const ghost = body.clone(); ghost.userData.recordingOverlay = true; ghost.position.x = 5; scene.add(ghost);
  const marker = new THREE.Mesh(new THREE.SphereGeometry(.02), new THREE.MeshBasicMaterial()); scene.add(marker);
  scene.updateMatrixWorld(true); const expected = mesh.matrixWorld.clone();
  const frozen = lightSnapshot(scene, camera);
  expect(frozen.physical.children).toHaveLength(1);
  expect(frozen.overlays.children).toHaveLength(2);
  const copy = frozen.physical.children[0] as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
  expect(copy.matrix.elements).toEqual(expected.elements);
  expect(copy.geometry.attributes.position!.array).toEqual(mesh.geometry.attributes.position!.array);
  expect(copy.geometry.attributes.position!.array).not.toBe(mesh.geometry.attributes.position!.array);
  expect(copy.material.emissive.getHex()).toBe(0);
  mesh.position.set(100, 100, 100); scene.updateMatrixWorld(true);
  expect(copy.matrix.elements).toEqual(expected.elements);
  const originalDispose = vi.fn(); mesh.geometry.addEventListener("dispose", originalDispose);
  frozen.dispose(); expect(originalDispose).not.toHaveBeenCalled();
  mesh.geometry.dispose(); mesh.material.dispose(); marker.geometry.dispose(); marker.material.dispose();
});

it("keeps invisible walls out of the still and bounds pixel work on large and narrow displays", () => {
  const scene = new THREE.Scene();
  const wall = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial()); wall.visible = false; scene.add(wall);
  const snapshot = lightSnapshot(scene, new THREE.PerspectiveCamera());
  expect(snapshot.physical.children).toHaveLength(0); snapshot.dispose(); wall.geometry.dispose(); wall.material.dispose();
  for (const [w, h] of [[7680, 4320], [390, 600], [2, 9000], [1, 1]]) {
    const size = refinementSize(w!, h!);
    expect(size.width * size.height).toBeLessThanOrEqual(REFINEMENT_LIMITS.pixels);
    expect(Math.max(size.width, size.height)).toBeLessThanOrEqual(REFINEMENT_LIMITS.edge);
  }
});

it("preserves cutaway shadow flags per mesh even when materials are shared", () => {
  const scene = new THREE.Scene(), geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial();
  const wall = new THREE.Mesh(geometry, material), robot = new THREE.Mesh(geometry, material);
  wall.name = "cutaway wall"; wall.castShadow = false;
  robot.name = "arm"; robot.castShadow = true;
  scene.add(wall, robot);
  const snapshot = lightSnapshot(scene, new THREE.PerspectiveCamera());
  const copies = snapshot.physical.children as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial & { castShadow: boolean }>[];
  expect(copies.map(m => [m.name, m.material.castShadow])).toEqual([["cutaway wall", false], ["arm", true]]);
  expect(copies[0]!.material).not.toBe(copies[1]!.material);
  expect("castShadow" in material).toBe(false);
  snapshot.dispose(); geometry.dispose(); material.dispose();
});

it("cancels late imports, workers and status from older moments without replacing a newer still", async () => {
  const statuses: string[] = [], aborted: boolean[] = [];
  const session = refinementSession(s => statuses.push(s.phase));
  let release!: () => void;
  session.start(async (signal, update) => {
    await new Promise<void>(resolve => { release = resolve; });
    aborted.push(signal.aborted); update({ phase: "complete", samples: 64 });
  });
  session.cancel();
  session.start(async (_signal, update) => { update({ phase: "sampling", samples: 8 }); });
  release(); await Promise.resolve(); await Promise.resolve();
  expect(aborted).toEqual([true]); expect(session.state()).toMatchObject({ phase: "sampling", samples: 8 });
  expect(statuses).not.toContain("complete"); session.cancel(); expect(session.state().phase).toBe("idle");
});

it("cleans up a failed renderer and preserves an explicit unavailable state", async () => {
  const session = refinementSession(() => {}); let aborted = false;
  session.start(async signal => { signal.addEventListener("abort", () => { aborted = true; }); throw Error("no float targets"); });
  await Promise.resolve(); await Promise.resolve();
  expect(aborted).toBe(true); expect(session.state().phase).toBe("unavailable");
  session.cancel(); // A routine redraw must not disguise a failure as idle.
  expect(session.state().phase).toBe("unavailable");
});

it("bounds the entire attempt even if an import or worker never resolves, retaining the last progress after failure", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
  const session = refinementSession(() => {}); let stopped = false;
  session.start(async (signal, update) => {
    signal.addEventListener("abort", () => { stopped = true; });
    update({ phase: "sampling", samples: 19, width: 800, height: 600 });
    await new Promise(() => {});
  });
  vi.advanceTimersByTime(REFINEMENT_LIMITS.milliseconds);
  expect(stopped).toBe(true);
  expect(session.state()).toMatchObject({ phase: "unavailable", samples: 19, width: 800, elapsedMs: 20000 });
  expect(session.state().reason).toContain("20 s");
  session.cancel(); expect(session.state().phase).toBe("unavailable");
  expect(session.history().at(-1)?.samples).toBe(19);
  expect(vi.getTimerCount()).toBe(0);
});

it("clears the deadline on success, records cancellation reasons and bounds diagnostic history", async () => {
  vi.useFakeTimers();
  const session = refinementSession(() => {});
  session.start(async (_signal, update) => {
    for (let i = 0; i < 140; i++) update({ phase: "sampling", samples: i / 3 });
    update({ phase: "complete", samples: REFINEMENT_LIMITS.samples });
  });
  vi.advanceTimersByTime(30000);
  expect(session.state().phase).toBe("complete"); expect(vi.getTimerCount()).toBe(0);
  expect(session.history()).toHaveLength(128);
  session.cancel();
  session.start(async () => { await new Promise(() => {}); });
  session.cancel("View changed · lighting cancelled.");
  expect(session.state()).toMatchObject({ phase: "idle", reason: "View changed · lighting cancelled." });
  expect(vi.getTimerCount()).toBe(0);
});
