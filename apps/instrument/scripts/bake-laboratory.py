"""Author-only Cycles bake of the exact UI architecture. No evidence or robot.

Run export-laboratory.mjs, then Blender --background --python this-file.
Outputs are concept lighting assets, not a measured building or digital twin.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ARTIFACT = HERE.parents[2] / "artifacts/spatial-laboratory-ricci-2026-11-16/lighting"
PUBLIC = HERE.parent / "public/media/laboratory"
PUBLIC.mkdir(parents=True, exist_ok=True)
source_bytes = (ARTIFACT / "architecture.json").read_bytes()
source = json.loads(source_bytes)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.cycles.seed = 731
scene.render.threads_mode = "FIXED"
scene.render.threads = 6
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.58, .73, .83, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.25

materials = {}
for entry in source["materials"]:
    material = bpy.data.materials.new(entry["name"] or "Architecture")
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*entry["colour"], 1)
    shader.inputs["Roughness"].default_value = entry["roughness"]
    shader.inputs["Metallic"].default_value = entry["metalness"]
    materials[entry["id"]] = material

# Convert y-up to Blender z-up without changing handedness or scale.
convert = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
floor = None
for entry in source["meshes"]:
    positions = [Vector(entry["positions"][i:i+3]) for i in range(0, len(entry["positions"]), 3)]
    triangles = [entry["indices"][i:i+3] for i in range(0, len(entry["indices"]), 3)]
    vertices, faces = [], []
    for values in entry["transforms"]:
        matrix = convert @ Matrix([values[i::4] for i in range(4)])
        offset = len(vertices)
        vertices.extend(tuple(matrix @ vertex) for vertex in positions)
        faces.extend(tuple(index + offset for index in face) for face in triangles)
    mesh = bpy.data.meshes.new(entry["name"])
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(entry["name"], mesh)
    scene.collection.objects.link(obj)
    obj.data.materials.append(materials[entry["material"]])
    if entry["name"] == "Laboratory floor":
        floor = obj
        uv = mesh.uv_layers.new(name="BakeUV")
        for polygon in mesh.polygons:
            for loop in polygon.loop_indices:
                index = mesh.loops[loop].vertex_index
                uv.data[loop].uv = entry["uv"][2*index:2*index+2]

sun_data = bpy.data.lights.new("Architectural daylight", "SUN")
sun_data.energy = 3
sun_data.angle = math.radians(2)
sun_data.color = (1, .92, .81)
sun = bpy.data.objects.new("Architectural daylight", sun_data)
scene.collection.objects.link(sun)
sun.location = convert @ Vector((-8, 10, -6))
sun.rotation_euler = ((convert @ Vector((0, 0, -2))) - sun.location).to_track_quat("-Z", "Y").to_euler()

assert floor is not None
bpy.ops.object.select_all(action="DESELECT")
floor.select_set(True)
bpy.context.view_layer.objects.active = floor
lightmap = bpy.data.images.new("Static indirect floor irradiance", width=1024, height=1024, float_buffer=True)
node = floor.active_material.node_tree.nodes.new("ShaderNodeTexImage")
node.image = lightmap
floor.active_material.node_tree.nodes.active = node
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"INDIRECT"}, use_clear=True, margin=8)
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "16"
lightmap.save_render(str(ARTIFACT / "floor-indirect-master.png"), scene=scene)
# Indirect light varies slowly in space. Downsample the authored bake rather
# than deliver a multi-megabyte high-frequency Monte Carlo noise field.
lightmap.scale(512, 512)
scene.render.image_settings.color_depth = "8"
lightmap.save_render(str(PUBLIC / "floor-indirect.png"), scene=scene)
print("Indirect floor lighting saved", flush=True)

camera_data = bpy.data.cameras.new("Bay reflection probe")
camera_data.type = "PANO"
camera_data.panorama_type = "EQUIRECTANGULAR"
camera = bpy.data.objects.new("Bay reflection probe", camera_data)
scene.collection.objects.link(camera)
camera.location = convert @ Vector((0, 1.1, 0))
# Three's equirectangular u=.5 faces +X, with +Z to the image's right.
camera.rotation_euler = (math.pi/2, 0, -math.pi/2)
scene.camera = camera
scene.render.resolution_x = 1024
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "HDR"
scene.render.filepath = str(PUBLIC / "bay-radiance.hdr")
bpy.ops.render.render(write_still=True)
manifest = {
    "schema": "nisayon.presentation-lighting.v1",
    "status": "authored architectural concept; not a measured environment",
    "blender": bpy.app.version_string,
    "architecture_source_sha256": source["source_sha256"],
    "export_sha256": hashlib.sha256(source_bytes).hexdigest(),
    "method": "Cycles; 64 samples; 4 diffuse and glossy bounces; floor indirect diffuse only, reduced from 1024 to 512 pixels and encoded as 8-bit sRGB; denoised 1024x512 equirectangular radiance from the empty bay",
    "scope": "Static building geometry only. No recorded robot, task, physics, sensor or NVIDIA runtime.",
    "assets": {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in PUBLIC.iterdir() if p.suffix in (".png", ".hdr")},
}
(PUBLIC / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
bpy.ops.wm.save_as_mainfile(filepath=str(ARTIFACT / "laboratory-lighting.blend"))
print(json.dumps(manifest), flush=True)
