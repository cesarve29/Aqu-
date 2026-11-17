"""Escena 3D estilo anime: luna sonriente + nubes 3D + pueblo 3D + cielo estrellado.

Requiere Blender 5.3 (Eevee).
Uso:  blender -b --factory-startup -P build_scene.py
Genera luna_sonriente.blend (renderizar con  blender -b luna_sonriente.blend -a).
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(sys.argv[sys.argv.index("-P") + 1]))
A = os.path.join(HERE, "assets")

FPS = 24
F_END = 504          # 21 segundos
S = 5.0              # radio de la luna en metros
rng = np.random.default_rng(11)

# ------------------------------------------------------------------ escena
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.name = "LunaSonriente"
scn.render.engine = "BLENDER_EEVEE"
scn.render.resolution_x = 1080
scn.render.resolution_y = 1920
scn.render.resolution_percentage = 100
scn.render.fps = FPS
scn.frame_start = 1
scn.frame_end = F_END
scn.eevee.taa_render_samples = 8
scn.view_settings.view_transform = "Standard"
scn.view_settings.look = "None"
scn.render.image_settings.file_format = "PNG"
scn.render.image_settings.color_mode = "RGB"
scn.render.filepath = "//frames/luna_"


# ------------------------------------------------------------------ utilidades
def img(name, colorspace="sRGB"):
    im = bpy.data.images.load(os.path.join(A, name), check_existing=True)
    im.colorspace_settings.name = colorspace
    return im


def new_mat(name, method="DITHERED"):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = method
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (1100, 0)
    return m, nt, out


def ramp(nt, stops, interp="LINEAR"):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
    for p, c in stops[1:]:
        e = el.new(p)
        e.color = (*c, 1)
    return r


def mix(nt, mode, a=None, b=None, fac=1.0):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    m.blend_type = mode
    m.inputs["Factor"].default_value = fac
    if a is not None:
        nt.links.new(a, m.inputs[6])
    if b is not None:
        nt.links.new(b, m.inputs[7])
    return m


def mesh_from_arrays(name, V, F, uv_fn=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", np.ascontiguousarray(V, np.float32).ravel())
    me.loops.add(F.size)
    me.loops.foreach_set("vertex_index", F.ravel())
    me.polygons.add(len(F))
    me.polygons.foreach_set("loop_start", np.arange(0, F.size, 3))
    me.update()
    me.validate()
    if uv_fn is not None:
        uv = me.uv_layers.new(name="UVMap")
        vi = np.empty(F.size, np.int32)
        me.loops.foreach_get("vertex_index", vi)
        uv.data.foreach_set("uv", uv_fn(V[vi]).astype(np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(F), bool))
    me.update()
    return me


def recalc_normals(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


def link(ob):
    scn.collection.objects.link(ob)
    return ob


def outline_mat(name, color):
    m, nt, out = new_mat(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = True
    return m


def add_outline(ob, mat, thickness):
    """Contorno anime por 'casco invertido' (Solidify con normales giradas)."""
    ob.data.materials.append(mat)
    mod = ob.modifiers.new("Contorno", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(ob.data.materials) - 1
    mod.use_quality_normals = True


def toon_mat(name, stops, rim_col=(0.4, 0.4, 0.3), rim_start=0.5, spec=0.0, albedo=None,
             bump_img=None, bump_strength=0.25, strength=1.0, rim_blend=0.35):
    """Sombreado cel: Diffuse -> Shader to RGB -> rampa de tonos, + borde de luz + brillo especular."""
    m, nt, out = new_mat(name)
    N = nt.nodes
    normal = None
    tc = N.new("ShaderNodeTexCoord")
    if bump_img is not None:
        tb = N.new("ShaderNodeTexImage"); tb.image = bump_img; tb.interpolation = "Cubic"
        nt.links.new(tc.outputs["UV"], tb.inputs["Vector"])
        bp = N.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump_strength
        bp.inputs["Distance"].default_value = 0.03
        nt.links.new(tb.outputs["Color"], bp.inputs["Height"])
        normal = bp.outputs["Normal"]
    diff = N.new("ShaderNodeBsdfDiffuse")
    if normal:
        nt.links.new(normal, diff.inputs["Normal"])
    s2r = N.new("ShaderNodeShaderToRGB")
    nt.links.new(diff.outputs[0], s2r.inputs[0])
    tone = ramp(nt, stops)
    nt.links.new(s2r.outputs["Color"], tone.inputs["Fac"])
    col = tone.outputs["Color"]
    if albedo is not None:
        ta = N.new("ShaderNodeTexImage"); ta.image = albedo; ta.interpolation = "Cubic"
        nt.links.new(tc.outputs["UV"], ta.inputs["Vector"])
        col = mix(nt, "MULTIPLY", ta.outputs["Color"], col).outputs[2]
    if spec > 0:
        gl = N.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.25
        if normal:
            nt.links.new(normal, gl.inputs["Normal"])
        s2 = N.new("ShaderNodeShaderToRGB")
        nt.links.new(gl.outputs[0], s2.inputs[0])
        sr = ramp(nt, [(0.0, (0, 0, 0)), (0.55, (0, 0, 0)), (0.62, (spec, spec, spec * 0.95))])
        nt.links.new(s2.outputs["Color"], sr.inputs["Fac"])
        col = mix(nt, "ADD", col, sr.outputs["Color"]).outputs[2]
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = rim_blend
    if normal:
        nt.links.new(normal, lw.inputs["Normal"])
    rr = ramp(nt, [(0.0, (0, 0, 0)), (rim_start, (0, 0, 0)), (min(rim_start + 0.08, 1.0), rim_col), (1.0, rim_col)])
    nt.links.new(lw.outputs["Facing"], rr.inputs["Fac"])
    col = mix(nt, "ADD", col, rr.outputs["Color"]).outputs[2]
    em = N.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(col, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def additive_mat(name, image, color, strength):
    m, nt, out = new_mat(name, "BLENDED")
    N = nt.nodes
    t = N.new("ShaderNodeTexImage"); t.image = image; t.extension = "CLIP"
    e = N.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    mm = N.new("ShaderNodeMath"); mm.operation = "MULTIPLY"
    mm.inputs[1].default_value = strength
    nt.links.new(t.outputs["Alpha"], mm.inputs[0])
    nt.links.new(mm.outputs[0], e.inputs["Strength"])
    tr = N.new("ShaderNodeBsdfTransparent")
    ad = N.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], ad.inputs[0]); nt.links.new(e.outputs[0], ad.inputs[1])
    nt.links.new(ad.outputs[0], out.inputs["Surface"])
    return m


def card(name, mat, loc, width, parent=None, rot=(math.radians(90), 0, 0)):
    me = bpy.data.meshes.new(name)
    h = 0.5
    me.from_pydata([(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = c
    me.materials.append(mat)
    ob = link(bpy.data.objects.new(name, me))
    ob.scale = (width, width, 1)
    ob.rotation_euler = rot
    if parent:
        ob.parent = parent
    ob.location = loc
    ob.visible_shadow = False
    return ob


# ------------------------------------------------------------------ luna 3D
data = np.load(os.path.join(A, "moon_mesh.npz"))
V, F, eye, L = data["V"], data["F"], data["eye"], float(data["L"][0])
moon_me = mesh_from_arrays("LunaMesh", V * S, F,
                           uv_fn=lambda P: (P[:, :2] / S + L) / (2 * L))

moon_anim = link(bpy.data.objects.new("Luna_Animacion", None))      # balanceo
moon_root = link(bpy.data.objects.new("Luna_Raiz", None))
moon_root.parent = moon_anim
moon_root.rotation_euler = (math.radians(90), 0, 0)                  # +Z local -> -Y mundo (cámara)
moon = link(bpy.data.objects.new("Luna", moon_me))
moon.parent = moon_root

moon_stops = [(0.0, (0.80, 0.68, 0.52)), (0.15, (0.83, 0.71, 0.54)), (0.22, (0.98, 0.94, 0.82)),
              (0.55, (1.0, 0.99, 0.95)), (1.0, (1.0, 1.0, 0.98))]
moon_mat = toon_mat("Luna_Toon", moon_stops, rim_col=(0.30, 0.28, 0.16), rim_start=0.6, spec=0.18,
                    albedo=img("moon_albedo.png"), bump_img=img("moon_bump.png", "Non-Color"),
                    bump_strength=0.2, strength=0.93)
moon_me.materials.append(moon_mat)
ink_moon = outline_mat("Contorno_Luna", (0.36, 0.22, 0.07))
add_outline(moon, ink_moon, 0.045)

# nariz (cono 3D)
nd = np.load(os.path.join(A, "nose_mesh.npz"))
nose_me = mesh_from_arrays("NarizMesh", nd["V"] * S, nd["F"],
                           uv_fn=lambda P: (P[:, :2] / S + L) / (2 * L))
recalc_normals(nose_me)
nose = link(bpy.data.objects.new("Nariz", nose_me))
nose.parent = moon_root
nose_stops = [(p, (c[0] * 1.0, c[1] * 0.985, c[2] * 0.93)) for p, c in moon_stops]
nose_mat = toon_mat("Nariz_Toon", nose_stops, rim_col=(0.30, 0.28, 0.16), rim_start=0.6, spec=0.22,
                    strength=0.92)
nose_me.materials.append(nose_mat)
add_outline(nose, ink_moon, 0.04)

# ojo (esfera de cristal en su cuenca)
ex, ey, er, eh = [float(v) for v in eye]
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=er * S)
eye_me = bpy.data.meshes.new("OjoMesh")
bm.to_mesh(eye_me)
bm.free()
eye_me.polygons.foreach_set("use_smooth", np.ones(len(eye_me.polygons), bool))
eye_ob = link(bpy.data.objects.new("Ojo", eye_me))
eye_ob.parent = moon_root
eye_z = eh * S - 0.40 * er * S
eye_ob.location = (ex * S, ey * S, eye_z)
m, nt, out = new_mat("Ojo_Cristal")
N = nt.nodes
pb = N.new("ShaderNodeBsdfPrincipled")
pb.inputs["Base Color"].default_value = (0.01, 0.06, 0.07, 1)
pb.inputs["Roughness"].default_value = 0.04
pb.inputs["Specular IOR Level"].default_value = 1.0
pb.inputs["Coat Weight"].default_value = 1.0
pb.inputs["Coat Roughness"].default_value = 0.02
lw = N.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
fr = ramp(nt, [(0.0, (0.004, 0.03, 0.04)), (0.55, (0.03, 0.16, 0.17)), (0.9, (0.18, 0.55, 0.50)),
               (1.0, (0.35, 0.75, 0.62))], "EASE")
nt.links.new(lw.outputs["Facing"], fr.inputs["Fac"])
tco = N.new("ShaderNodeTexCoord")
sep = N.new("ShaderNodeSeparateXYZ")
nt.links.new(tco.outputs["Object"], sep.inputs[0])
mr = N.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = 0.1 * er * S
mr.inputs["From Max"].default_value = -0.9 * er * S
nt.links.new(sep.outputs["Y"], mr.inputs["Value"])
gc = mix(nt, "ADD", fr.outputs["Color"])
nt.links.new(mr.outputs[0], gc.inputs["Factor"])
gc.inputs[7].default_value = (0.10, 0.32, 0.30, 1)
emo = N.new("ShaderNodeEmission")
nt.links.new(gc.outputs[2], emo.inputs["Color"])
addsh = N.new("ShaderNodeAddShader")
nt.links.new(pb.outputs[0], addsh.inputs[0]); nt.links.new(emo.outputs[0], addsh.inputs[1])
nt.links.new(addsh.outputs[0], out.inputs["Surface"])
eye_me.materials.append(m)
add_outline(eye_ob, outline_mat("Contorno_Ojo", (0.02, 0.07, 0.08)), 0.035)

# destellos del ojo
spark_img = img("sparkle.png")
spark_mat = additive_mat("Destello", spark_img, (1.0, 1.0, 0.95), 4.0)
glint = card("Destello_Ojo", spark_mat, (ex * S - 0.08 * er * S, ey * S + 0.12 * er * S, eye_z + er * S + 0.05),
             1.3, parent=moon_root, rot=(0, 0, 0))
glint2 = card("Destello_Ojo_Peq", spark_mat, (ex * S + 0.35 * er * S, ey * S - 0.40 * er * S, eye_z + er * S * 0.9),
              0.35, parent=moon_root, rot=(0, 0, math.radians(20)))

# halos
halo_img = img("halo.png")
card("Halo_Calido", additive_mat("Halo_Calido", halo_img, (1.0, 0.88, 0.5), 0.75), (0, 7, 0), 19)
card("Halo_Turquesa", additive_mat("Halo_Turquesa", halo_img, (0.10, 0.42, 0.50), 0.55), (0, 12, 0), 52)

# ------------------------------------------------------------------ nubes 3D
cloud_meshes = []
for i in range(5):
    cd = np.load(os.path.join(A, f"cloud3d_{i}.npz"))
    cme = mesh_from_arrays(f"Nube3D_{i}", cd["V"], cd["F"])
    recalc_normals(cme)
    cloud_meshes.append(cme)
cloud_mats = {}


def cloud_mat(bright):
    if bright not in cloud_mats:
        b = bright
        stops = [(0.0, (0.07 * b, 0.15 * b, 0.40 * b)), (0.12, (0.09 * b, 0.19 * b, 0.47 * b)),
                 (0.18, (0.17 * b, 0.38 * b, 0.78 * b)), (0.45, (0.22 * b, 0.46 * b, 0.86 * b)),
                 (0.55, (0.42 * b, 0.70 * b, 0.98 * b)), (1.0, (0.58 * b, 0.84 * b, 1.0 * b))]
        cloud_mats[bright] = toon_mat(f"Nube_Toon_{len(cloud_mats)}", stops,
                                      rim_col=(0.30 * b, 0.45 * b, 0.55 * b), rim_start=0.6, rim_blend=0.4)
    return cloud_mats[bright]


cloud_ink = outline_mat("Contorno_Nube", (0.05, 0.12, 0.30))


def cloud(name, idx, loc, width, bright=1.0, rotz=0.0, flip=False):
    me = cloud_meshes[idx]
    ob = link(bpy.data.objects.new(name, me))
    ob.location = loc
    s = width / 2.0
    ob.scale = (-s if flip else s, s * 0.9, s * 0.85)
    ob.rotation_euler = (0, 0, math.radians(rotz))
    return ob, cloud_mat(bright)


# los materiales se asignan por objeto (la malla se comparte entre varias nubes)
for me in cloud_meshes:
    me.materials.append(None)
    me.materials.append(cloud_ink)


def place_cloud(name, idx, loc, width, bright=1.0, rotz=0.0, flip=False):
    ob, mat = cloud(name, idx, loc, width, bright, rotz, flip)
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = mat
    mod = ob.modifiers.new("Contorno", "SOLIDIFY")
    mod.thickness = 0.06 * 2 / width * 1.0
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = 1
    return ob


clouds = [
    # alrededor de la luna
    (0, (-8.4, 8, 4.5), 9.5, 1.0, 10, False), (2, (-9.2, 11, -4.5), 12, 0.98, -15, True),
    (1, (8.8, 9, 6.0), 9.5, 1.0, -10, False), (3, (9.0, 7, -3.0), 10.5, 0.98, 20, True),
    (4, (8.0, 13, -9.5), 13, 1.0, 5, False), (0, (-7.8, 13, -10.5), 11, 1.0, -8, True),
    (1, (-5.5, 18, 11.0), 7, 0.95, 12, True), (2, (6.5, 18, 12.0), 7, 0.95, -12, False),
    (3, (3.8, -4.5, -8.6), 8, 0.98, 8, False),
    # medio camino
    (4, (-9.5, -24, -5), 12, 1.0, 15, False), (0, (10.5, -30, -9), 13, 1.0, -20, True),
    (2, (-12, -40, -21), 16, 0.95, 10, False), (1, (13, -42, -14), 14, 0.95, -15, True),
    (3, (-8, -36, 4), 12, 0.95, 25, True), (4, (9, -55, -2), 14, 0.95, -5, False),
    (1, (-7, -22, -21), 13, 0.95, 0, False), (4, (8, -12, -19), 12, 1.0, 15, True),
    (0, (1, -32, -31), 17, 0.9, -10, True),
    # capa que atraviesa la cámara
    (2, (-12.0, -53, -15.0), 20, 0.9, 10, False), (3, (3.5, -49.5, -13.5), 22, 0.92, 0, True),
    (0, (-10.0, -45, -5.0), 16, 0.95, -10, False),
    # sobre el pueblo
    (1, (-9, -63, -40), 18, 0.8, 5, False), (4, (11, -66, -37), 20, 0.8, -10, True),
    (2, (-20, -72, -47), 24, 0.75, 12, True), (3, (21, -74, -48), 22, 0.75, -12, False),
    (0, (2, -64, -53), 28, 0.72, 0, False),
]
cloud_objs = []
for i, (idx, loc, w, br, rz, fl) in enumerate(clouds):
    cloud_objs.append(place_cloud(f"Nube_{i:02d}", idx, loc, w, br, rz, fl))

# la capa que cruza la cámara se abre como un telón para revelar la luna
PART_START, PART_END = 196, 262
for i, dx in ((18, -24.0), (19, 25.0), (20, -22.0)):
    ob = cloud_objs[i]
    ob.keyframe_insert("location", frame=PART_START)
    ob.location.x += dx
    ob.keyframe_insert("location", frame=PART_END)

# ------------------------------------------------------------------ pueblo 3D
GROUND = -64.0
bm_b = bmesh.new()
bm_w = bmesh.new()


def box(bmx, x0, y0, z0, x1, y1, z1):
    vs = [bmx.verts.new(v) for v in [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                     (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]]
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bmx.faces.new([vs[i] for i in f])


def gable(bmx, x0, y0, x1, y1, z, h):
    o = 0.35
    vs = [bmx.verts.new(v) for v in [(x0 - o, y0 - o, z), (x1 + o, y0 - o, z), (x1 + o, y1 + o, z),
                                     (x0 - o, y1 + o, z), ((x0 + x1) / 2, y0 - o, z + h), ((x0 + x1) / 2, y1 + o, z + h)]]
    for f in [(0, 1, 4), (2, 3, 5), (1, 2, 5, 4), (3, 0, 4, 5), (0, 3, 2, 1)]:
        bmx.faces.new([vs[i] for i in f])


def spire(bmx, x0, y0, x1, y1, z, h):
    o = 0.3
    vs = [bmx.verts.new(v) for v in [(x0 - o, y0 - o, z), (x1 + o, y0 - o, z), (x1 + o, y1 + o, z),
                                     (x0 - o, y1 + o, z), ((x0 + x1) / 2, (y0 + y1) / 2, z + h)]]
    for f in [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 3, 2, 1)]:
        bmx.faces.new([vs[i] for i in f])


def windows(x0, x1, y_face, z0, z1, prob=0.22):
    for wz in np.arange(z0 + 1.6, z1 - 1.2, 2.2):
        for wx in np.arange(x0 + 0.9, x1 - 1.0, 1.6):
            if rng.random() < prob:
                vs = [bm_w.verts.new(v) for v in [(wx, y_face - 0.05, wz), (wx + 0.7, y_face - 0.05, wz),
                                                  (wx + 0.7, y_face - 0.05, wz + 1.0), (wx, y_face - 0.05, wz + 1.0)]]
                bm_w.faces.new(vs)


def building(x, y, w, d, h, roof):
    top = GROUND + h
    box(bm_b, x, y, GROUND, x + w, y + d, top)
    if roof == "gable":
        gable(bm_b, x, y, x + w, y + d, top, w * rng.uniform(0.35, 0.55))
    elif roof == "spire":
        spire(bm_b, x, y, x + w, y + d, top, w * rng.uniform(1.4, 2.2))
    if rng.random() < 0.4:
        cx = x + rng.uniform(0.2, 0.7) * w
        box(bm_b, cx, y + d * 0.4, top - 0.5, cx + 0.7, y + d * 0.4 + 0.7, top + rng.uniform(1.5, 3.0))
    windows(x, x + w, y, GROUND, top)


for row_y in [-102, -94, -86, -78, -70]:
    x = -46 + rng.uniform(0, 3)
    while x < 46:
        w = rng.uniform(4.0, 7.5)
        d = rng.uniform(5.0, 8.0)
        cen = abs(x + w / 2)
        h = rng.uniform(6, 13) * (0.8 + 0.5 * min(cen / 25, 1))
        if row_y <= -94 and cen < 8:
            h = min(h, 7.5)              # calle despejada frente a la cámara
        roof = rng.choice(["gable", "gable", "flat", "spire"], p=[0.45, 0.2, 0.2, 0.15])
        building(x, row_y + rng.uniform(-1, 1), w, d, h, roof)
        x += w + rng.uniform(0.3, 1.5)
# torre del reloj
box(bm_b, -14, -95, GROUND, -10, -91, GROUND + 30)
spire(bm_b, -14, -95, -10, -91, GROUND + 30, 9)
clock = [bm_w.verts.new((-12 + 1.1 * math.cos(a), -95.06, GROUND + 26 + 1.1 * math.sin(a)))
         for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
bm_w.faces.new(clock[::-1])

town_me = bpy.data.meshes.new("PuebloMesh")
bm_b.to_mesh(town_me)
bm_b.free()
town = link(bpy.data.objects.new("Pueblo", town_me))
town_mat = toon_mat("Pueblo_Toon", [(0.0, (0.02, 0.035, 0.08)), (0.2, (0.03, 0.05, 0.11)), (0.3, (0.05, 0.08, 0.17)),
                                    (1.0, (0.07, 0.11, 0.22))],
                    rim_col=(0.10, 0.17, 0.32), rim_start=0.75, rim_blend=0.2)
town_me.materials.append(town_mat)
add_outline(town, outline_mat("Contorno_Pueblo", (0.01, 0.015, 0.04)), 0.08)
win_me = bpy.data.meshes.new("VentanasMesh")
bm_w.to_mesh(win_me)
bm_w.free()
wins = link(bpy.data.objects.new("Ventanas", win_me))
m, nt, out = new_mat("Ventanas_Luz")
e = nt.nodes.new("ShaderNodeEmission")
e.inputs["Color"].default_value = (1.0, 0.78, 0.38, 1)
e.inputs["Strength"].default_value = 1.6
nt.links.new(e.outputs[0], out.inputs["Surface"])
win_me.materials.append(m)
# suelo
gme = bpy.data.meshes.new("SueloMesh")
gme.from_pydata([(-200, -200, GROUND), (200, -200, GROUND), (200, -40, GROUND), (-200, -40, GROUND)], [], [(0, 1, 2, 3)])
ground = link(bpy.data.objects.new("Suelo", gme))
m, nt, out = new_mat("Suelo")
e = nt.nodes.new("ShaderNodeEmission")
e.inputs["Color"].default_value = (0.02, 0.035, 0.08, 1)
nt.links.new(e.outputs[0], out.inputs["Surface"])
gme.materials.append(m)

# estrellas brillantes con destello
star_mat = additive_mat("Estrella", spark_img, (0.85, 0.95, 1.0), 2.5)
stars = []
for i in range(18):
    az = rng.uniform(-0.55, 0.55)
    el = rng.uniform(0.05, 0.75)
    d = rng.uniform(140, 200)
    loc = (d * math.sin(az) * math.cos(el), d * math.cos(az) * math.cos(el) - 115, d * math.sin(el) - 50)
    if abs(loc[0]) < 9 and abs(loc[2]) < 9:
        continue
    stars.append(card(f"Estrella_{i:02d}", star_mat, loc, rng.uniform(1.2, 2.6)))

# ------------------------------------------------------------------ mundo (cielo + estrellas)
world = bpy.data.worlds.new("Cielo")
scn.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
W = wn.nodes
wo = W.new("ShaderNodeOutputWorld")
wtc = W.new("ShaderNodeTexCoord")
wsep = W.new("ShaderNodeSeparateXYZ")
wn.links.new(wtc.outputs["Generated"], wsep.inputs[0])
sky = ramp(wn, [(0.0, (0.07, 0.16, 0.30)), (0.42, (0.045, 0.12, 0.26)), (0.52, (0.035, 0.10, 0.23)),
                (0.75, (0.018, 0.05, 0.13)), (1.0, (0.008, 0.02, 0.06))])
wmr = W.new("ShaderNodeMapRange")
wmr.inputs["From Min"].default_value = -1.0
wmr.inputs["From Max"].default_value = 1.0
wn.links.new(wsep.outputs["Z"], wmr.inputs["Value"])
wn.links.new(wmr.outputs[0], sky.inputs["Fac"])


def star_layer(scale, radius, sparse):
    vor = W.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "3D"
    vor.inputs["Scale"].default_value = scale
    wn.links.new(wtc.outputs["Generated"], vor.inputs["Vector"])
    m1 = W.new("ShaderNodeMath"); m1.operation = "DIVIDE"
    wn.links.new(vor.outputs["Distance"], m1.inputs[0]); m1.inputs[1].default_value = radius
    m2 = W.new("ShaderNodeMath"); m2.operation = "SUBTRACT"; m2.use_clamp = True
    m2.inputs[0].default_value = 1.0; wn.links.new(m1.outputs[0], m2.inputs[1])
    m3 = W.new("ShaderNodeMath"); m3.operation = "POWER"
    wn.links.new(m2.outputs[0], m3.inputs[0]); m3.inputs[1].default_value = 2.0
    sc = W.new("ShaderNodeSeparateColor")
    wn.links.new(vor.outputs["Color"], sc.inputs[0])
    gt = W.new("ShaderNodeMapRange")
    gt.inputs["From Min"].default_value = sparse
    gt.inputs["From Max"].default_value = 1.0
    wn.links.new(sc.outputs[0], gt.inputs["Value"])
    m4 = W.new("ShaderNodeMath"); m4.operation = "MULTIPLY"
    wn.links.new(m3.outputs[0], m4.inputs[0]); wn.links.new(gt.outputs[0], m4.inputs[1])
    return m4, sc


s1, sc1 = star_layer(260, 0.16, 0.55)
s2, _ = star_layer(70, 0.07, 0.85)
tw = W.new("ShaderNodeTexNoise")
tw.noise_dimensions = "4D"
tw.inputs["Scale"].default_value = 90
wn.links.new(wtc.outputs["Generated"], tw.inputs["Vector"])
tw.inputs["W"].default_value = 0.0
tw.inputs["W"].keyframe_insert("default_value", frame=1)
tw.inputs["W"].default_value = 18.0
tw.inputs["W"].keyframe_insert("default_value", frame=F_END)
twr = W.new("ShaderNodeMapRange")
twr.inputs["From Min"].default_value = 0.3; twr.inputs["From Max"].default_value = 0.7
twr.inputs["To Min"].default_value = 0.25; twr.inputs["To Max"].default_value = 1.6
wn.links.new(tw.outputs["Fac"], twr.inputs["Value"])
s2b = W.new("ShaderNodeMath"); s2b.operation = "MULTIPLY"
wn.links.new(s2.outputs[0], s2b.inputs[0]); s2b.inputs[1].default_value = 2.5
sum_s = W.new("ShaderNodeMath"); sum_s.operation = "ADD"
wn.links.new(s1.outputs[0], sum_s.inputs[0]); wn.links.new(s2b.outputs[0], sum_s.inputs[1])
tw_m = W.new("ShaderNodeMath"); tw_m.operation = "MULTIPLY"
wn.links.new(sum_s.outputs[0], tw_m.inputs[0]); wn.links.new(twr.outputs[0], tw_m.inputs[1])
hz = W.new("ShaderNodeMapRange")
hz.inputs["From Min"].default_value = -0.12; hz.inputs["From Max"].default_value = 0.05
wn.links.new(wsep.outputs["Z"], hz.inputs["Value"])
tw_h = W.new("ShaderNodeMath"); tw_h.operation = "MULTIPLY"
wn.links.new(tw_m.outputs[0], tw_h.inputs[0]); wn.links.new(hz.outputs[0], tw_h.inputs[1])
star_col = mix(wn, "MIX")
wn.links.new(sc1.outputs[2], star_col.inputs["Factor"])
star_col.inputs[6].default_value = (1.0, 1.0, 1.0, 1)
star_col.inputs[7].default_value = (0.55, 0.85, 1.0, 1)
cvt = W.new("ShaderNodeCombineColor")
for i in range(3):
    wn.links.new(tw_h.outputs[0], cvt.inputs[i])
sc_m = mix(wn, "MULTIPLY", star_col.outputs[2], cvt.outputs[0])
sky_add = mix(wn, "ADD", sky.outputs["Color"], sc_m.outputs[2])
bg = W.new("ShaderNodeBackground")
wn.links.new(sky_add.outputs[2], bg.inputs["Color"])
wn.links.new(bg.outputs[0], wo.inputs["Surface"])

# ------------------------------------------------------------------ luces
sun_d = bpy.data.lights.new("Sol", "SUN")
sun_d.energy = 3.0
sun_d.angle = math.radians(3)
sun_d.use_shadow = False      # sombreado cel limpio (sin ruido de sombras)
sun = link(bpy.data.objects.new("Sol", sun_d))
sun.rotation_euler = Vector((-0.55, -1.0, 0.65)).to_track_quat("Z", "Y").to_euler()
# la luna ilumina nubes y tejados (luz puntual sin sombras en su centro)
ml_d = bpy.data.lights.new("Luz_Luna", "POINT")
ml_d.energy = 18000
ml_d.color = (1.0, 0.95, 0.75)
ml_d.use_shadow = False
ml_d.shadow_soft_size = 5.0
ml = link(bpy.data.objects.new("Luz_Luna", ml_d))
ml.parent = moon_anim

# ------------------------------------------------------------------ cámara
cam_d = bpy.data.cameras.new("Camara")
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.05
cam_d.clip_end = 2000
cam = link(bpy.data.objects.new("Camara", cam_d))
scn.camera = cam
target = link(bpy.data.objects.new("Objetivo_Camara", None))
tr = cam.constraints.new("TRACK_TO")
tr.target = target
tr.track_axis = "TRACK_NEGATIVE_Z"
tr.up_axis = "UP_Y"


def key(obj, path, frame):
    obj.keyframe_insert(data_path=path, frame=frame)


cam_keys = [  # frame, posición, objetivo, focal
    (1,   (0.0, -118, -53.0),  (0, 0, -40.0), 24),
    (48,  (0.0, -115, -51.5),  (0, 0, -37.0), 24),
    (190, (1.6, -76, -27.0),   (0, 0, -11.0), 27),
    (300, (-1.0, -44, -10.0),  (0, 0, -2.0),  31),
    (420, (3.0, -23.5, -2.4),  (-0.3, 0, -0.5), 34),
    (504, (-1.6, -19.8, -1.6), (-0.5, 0, -0.4), 36),
]
for f, p, t, fl in cam_keys:
    cam.location = p
    key(cam, "location", f)
    target.location = t
    key(target, "location", f)
    cam_d.lens = fl
    cam_d.keyframe_insert("lens", frame=f)

# ------------------------------------------------------------------ animación de la luna
for f in range(1, F_END + 1, 24):
    t = f / FPS
    moon_anim.location = (0.0, 0.0, 0.2 * math.sin(t * 2 * math.pi / 6.0))
    moon_anim.rotation_euler = (math.radians(3.0 * math.sin(t * 2 * math.pi / 7.0)),
                                math.radians(4.0 * math.sin(t * 2 * math.pi / 9.0 + 1.0)),
                                math.radians(7.0 * math.sin(t * 2 * math.pi / 10.0 + 0.5)))
    key(moon_anim, "location", f)
    key(moon_anim, "rotation_euler", f)

for f in range(1, F_END + 1, 4):
    t = f / FPS
    base = 1.0 + 0.25 * math.sin(t * 5.0)
    if f > 430:
        base += 0.9 * math.exp(-((f - 455) / 14.0) ** 2)
    glint.scale = (1.3 * base, 1.3 * base, 1)
    glint.rotation_euler = (0, 0, 0.15 * math.sin(t * 1.3))
    key(glint, "scale", f)
    key(glint, "rotation_euler", f)
    b2 = 0.35 * (1.0 + 0.4 * math.sin(t * 3.7 + 1.0))
    glint2.scale = (b2, b2, 1)
    key(glint2, "scale", f)
for st in stars:
    s0 = st.scale.x
    ph = rng.uniform(0, 6.28)
    sp = rng.uniform(1.5, 3.5)
    for f in range(1, F_END + 1, 6):
        k = s0 * (0.55 + 0.45 * math.sin(f / FPS * sp + ph))
        st.scale = (k, k, 1)
        key(st, "scale", f)

# ------------------------------------------------------------------ composición (bloom + viñeta)
cg = bpy.data.node_groups.new("Composicion", "CompositorNodeTree")
cg.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
scn.compositing_node_group = cg
C = cg.nodes
rl = C.new("CompositorNodeRLayers")
gl1 = C.new("CompositorNodeGlare")
gl1.inputs["Type"].default_value = "Fog Glow"
gl1.inputs["Quality"].default_value = "High"
gl1.inputs["Threshold"].default_value = 0.92
gl1.inputs["Strength"].default_value = 0.4
cg.links.new(rl.outputs["Image"], gl1.inputs["Image"])
ell = C.new("CompositorNodeEllipseMask")
ell.inputs["Size"].default_value = (1.25, 1.1)
blur = C.new("CompositorNodeBlur")
blur.inputs["Size"].default_value = (300, 300)
cg.links.new(ell.outputs["Mask"], blur.inputs["Image"])
vig = mix(cg, "MULTIPLY", gl1.outputs["Image"], blur.outputs["Image"], fac=0.4)
go = C.new("NodeGroupOutput")
cg.links.new(vig.outputs[2], go.inputs[0])

# ------------------------------------------------------------------ guardar
blend = os.path.join(HERE, "luna_sonriente.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
print("Guardado", blend)
