"""Bake static contact occlusion from the exported standing lab, without robots.

Blender --background --python scripts/bake-standing-lab.py
The dimensionless mask is non-colour data; direct robot shadows stay dynamic.
"""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

APP = Path(__file__).resolve().parent.parent
if "--" not in sys.argv or len(sys.argv) <= sys.argv.index("--") + 1:
    raise ValueError("Provide the new source artifact directory after --")
ARTIFACT = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
if (ARTIFACT / "occlusion-receipt.json").exists():
    raise ValueError("Retained lighting packets are immutable; export to a new directory")
PUBLIC = APP / "public/media/laboratory"
source_bytes = (ARTIFACT / "architecture.json").read_bytes()
source = json.loads(source_bytes)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 32
scene.cycles.seed = 731
scene.render.threads_mode = "FIXED"
scene.render.threads = 6
scene.view_settings.view_transform = "Raw"
convert = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
floor = None
for entry in source["meshes"]:
    points = [Vector(entry["positions"][i:i+3]) for i in range(0, len(entry["positions"]), 3)]
    triangles = [entry["indices"][i:i+3] for i in range(0, len(entry["indices"]), 3)]
    vertices, faces = [], []
    for values in entry["transforms"]:
        transform = convert @ Matrix([values[i::4] for i in range(4)])
        offset = len(vertices)
        vertices.extend(tuple(transform @ point) for point in points)
        faces.extend(tuple(index + offset for index in face) for face in triangles)
    mesh = bpy.data.meshes.new(entry["name"])
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(entry["name"], mesh)
    scene.collection.objects.link(obj)
    if entry["name"] == "Laboratory floor":
        floor = obj
        uv = mesh.uv_layers.new(name="FloorUV")
        for polygon in mesh.polygons:
            for loop in polygon.loop_indices:
                index = mesh.loops[loop].vertex_index
                uv.data[loop].uv = entry["uv"][2*index:2*index+2]
assert floor is not None
material = bpy.data.materials.new("Floor contact occlusion")
material.use_nodes = True
nodes = material.node_tree.nodes
nodes.clear()
ao = nodes.new("ShaderNodeAmbientOcclusion")
ao.inputs["Distance"].default_value = 1.2
ao.samples = 16
emission = nodes.new("ShaderNodeEmission")
output = nodes.new("ShaderNodeOutputMaterial")
material.node_tree.links.new(ao.outputs["AO"], emission.inputs["Color"])
material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
floor.data.materials.append(material)
image = bpy.data.images.new("Standing laboratory floor occlusion", width=1024, height=1024, float_buffer=False)
image.colorspace_settings.name = "Non-Color"
destination = nodes.new("ShaderNodeTexImage")
destination.image = image
nodes.active = destination
bpy.ops.object.select_all(action="DESELECT")
floor.select_set(True)
bpy.context.view_layer.objects.active = floor
bpy.ops.object.bake(type="EMIT", use_clear=True, margin=4)
image.file_format = "PNG"
image.filepath_raw = str(ARTIFACT / "floor-occlusion.png")
image.save()
payload = Path(image.filepath_raw).read_bytes()
digest = hashlib.sha256(payload).hexdigest()
name = f"standing-floor-ao-{digest[:16]}.png"
PUBLIC.mkdir(parents=True, exist_ok=True)
(PUBLIC / name).write_bytes(payload)
receipt = {
    "schema": "nisayon.presentation-occlusion.v1", "status": "authored static architecture, not measured light",
    "sources": source["sources"], "export_sha256": hashlib.sha256(source_bytes).hexdigest(),
    "blender": bpy.app.version_string, "method": "Cycles emission bake of AO; 1.2 m radius; 16 AO samples; 32 render samples; 1024 square; non-colour PNG",
    "scope": "Static building, operator console and contact support. No recorded robot, specimen, physics, outcome or sensor data.",
    "bake_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "asset": "media/laboratory/" + name, "sha256": digest, "bytes": len(payload),
}
(ARTIFACT / "occlusion-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
(PUBLIC / Path(name).with_suffix(".json")).write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2), flush=True)
