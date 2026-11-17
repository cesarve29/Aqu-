"""Construye la escena de Blender: luna sonriente anime + cielo nocturno + cámara.

Uso:  blender -b --factory-startup -P build_scene.py
Genera luna_sonriente.blend (listo para renderizar con  blender -b luna_sonriente.blend -a).
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(bpy.data.filepath or __file__))
if not os.path.exists(os.path.join(HERE, "assets")):
    HERE = os.path.dirname(os.path.abspath(sys.argv[sys.argv.index("-P") + 1]))
A = os.path.join(HERE, "assets")

FPS = 24
F_END = 504          # 21 segundos
S = 5.0              # radio de la luna en metros

# ------------------------------------------------------------------ escena limpia
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.name = "LunaSonriente"
scn.render.engine = "BLENDER_EEVEE_NEXT"
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
    out.location = (900, 0)
    return m, nt, out


def ramp(nt, stops, interp="EASE"):
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


def key(obj, path, frame, value, index=-1):
    if index >= 0:
        getattr(obj, path)[index] = value
    else:
        setattr(obj, path, value)
    obj.keyframe_insert(data_path=path, frame=frame, index=index)


# ------------------------------------------------------------------ luna (malla)
data = np.load(os.path.join(A, "moon_mesh.npz"))
V, F, eye, L = data["V"], data["F"], data["eye"], float(data["L"][0])
me = bpy.data.meshes.new("LunaMesh")
me.vertices.add(len(V))
me.vertices.foreach_set("co", (V * S).ravel())
me.loops.add(F.size)
me.loops.foreach_set("vertex_index", F.ravel())
me.polygons.add(len(F))
me.polygons.foreach_set("loop_start", np.arange(0, F.size, 3))
me.update()
me.validate()
uv = me.uv_layers.new(name="UVMap")
vi = np.empty(F.size, np.int32)
me.loops.foreach_get("vertex_index", vi)
uvs = np.empty((F.size, 2), np.float32)
uvs[:, 0] = (V[vi, 0] + L) / (2 * L)
uvs[:, 1] = (V[vi, 1] + L) / (2 * L)
uv.data.foreach_set("uv", uvs.ravel())
me.polygons.foreach_set("use_smooth", np.ones(len(F), bool))
me.update()

moon_root = bpy.data.objects.new("Luna_Raiz", None)
scn.collection.objects.link(moon_root)
moon_root.rotation_euler = (math.radians(90), 0, 0)   # +Z local mira hacia -Y (cámara)
moon = bpy.data.objects.new("Luna", me)
scn.collection.objects.link(moon)
moon.parent = moon_root

# material toon de la luna
m, nt, out = new_mat("Luna_Toon")
N = nt.nodes
tc = N.new("ShaderNodeTexCoord"); tc.location = (-1400, 0)
t_alb = N.new("ShaderNodeTexImage"); t_alb.image = img("moon_albedo.png"); t_alb.location = (-1100, 300)
t_bmp = N.new("ShaderNodeTexImage"); t_bmp.image = img("moon_bump.png", "Non-Color"); t_bmp.location = (-1100, -100)
for t in (t_alb, t_bmp):
    t.interpolation = "Cubic"
    nt.links.new(tc.outputs["UV"], t.inputs["Vector"])
bump = N.new("ShaderNodeBump"); bump.location = (-800, -100)
bump.inputs["Strength"].default_value = 0.25
bump.inputs["Distance"].default_value = 0.03
nt.links.new(t_bmp.outputs["Color"], bump.inputs["Height"])
diff = N.new("ShaderNodeBsdfDiffuse"); diff.location = (-600, 100)
nt.links.new(bump.outputs["Normal"], diff.inputs["Normal"])
s2r = N.new("ShaderNodeShaderToRGB"); s2r.location = (-400, 100)
nt.links.new(diff.outputs[0], s2r.inputs[0])
toon = ramp(nt, [(0.0, (0.68, 0.57, 0.42)), (0.14, (0.83, 0.72, 0.55)), (0.36, (0.97, 0.93, 0.82)),
                 (0.62, (1.0, 0.99, 0.96))])
toon.location = (-200, 100)
nt.links.new(s2r.outputs["Color"], toon.inputs["Fac"])
mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.location = (100, 200)
mul.inputs["Factor"].default_value = 1.0
nt.links.new(t_alb.outputs["Color"], mul.inputs[6])
nt.links.new(toon.outputs["Color"], mul.inputs[7])
# brillo especular anime
gl = N.new("ShaderNodeBsdfGlossy"); gl.location = (-600, -250)
gl.inputs["Roughness"].default_value = 0.35
nt.links.new(bump.outputs["Normal"], gl.inputs["Normal"])
s2r2 = N.new("ShaderNodeShaderToRGB"); s2r2.location = (-400, -250)
nt.links.new(gl.outputs[0], s2r2.inputs[0])
spec = ramp(nt, [(0.0, (0, 0, 0)), (0.35, (0, 0, 0)), (0.6, (0.22, 0.2, 0.15))])
spec.location = (-200, -250)
nt.links.new(s2r2.outputs["Color"], spec.inputs["Fac"])
# borde luminoso
lw = N.new("ShaderNodeLayerWeight"); lw.location = (-600, -500)
lw.inputs["Blend"].default_value = 0.35
nt.links.new(bump.outputs["Normal"], lw.inputs["Normal"])
rim = ramp(nt, [(0.0, (0, 0, 0)), (0.45, (0, 0, 0)), (1.0, (0.42, 0.42, 0.28))])
rim.location = (-200, -500)
nt.links.new(lw.outputs["Facing"], rim.inputs["Fac"])
add1 = N.new("ShaderNodeMix"); add1.data_type = "RGBA"; add1.blend_type = "ADD"; add1.location = (350, 100)
add1.inputs["Factor"].default_value = 1.0
nt.links.new(mul.outputs[2], add1.inputs[6]); nt.links.new(spec.outputs["Color"], add1.inputs[7])
add2 = N.new("ShaderNodeMix"); add2.data_type = "RGBA"; add2.blend_type = "ADD"; add2.location = (550, 0)
add2.inputs["Factor"].default_value = 1.0
nt.links.new(add1.outputs[2], add2.inputs[6]); nt.links.new(rim.outputs["Color"], add2.inputs[7])
em = N.new("ShaderNodeEmission"); em.location = (720, 0)
em.inputs["Strength"].default_value = 1.08
nt.links.new(add2.outputs[2], em.inputs["Color"])
nt.links.new(em.outputs[0], out.inputs["Surface"])
moon.data.materials.append(m)

# ------------------------------------------------------------------ ojo
ex, ey, er, eh = [float(v) for v in eye]
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=er * S,
                                     location=(0, 0, 0))
eye_ob = bpy.context.active_object
eye_ob.name = "Ojo"
bpy.ops.object.shade_smooth()
eye_ob.parent = moon_root
eye_z = eh * S - 0.42 * er * S
eye_ob.location = (ex * S, ey * S, eye_z)
m, nt, out = new_mat("Ojo_Cristal")
N = nt.nodes
pb = N.new("ShaderNodeBsdfPrincipled"); pb.location = (0, 300)
pb.inputs["Base Color"].default_value = (0.01, 0.06, 0.07, 1)
pb.inputs["Roughness"].default_value = 0.04
pb.inputs["Specular IOR Level"].default_value = 1.0
pb.inputs["Coat Weight"].default_value = 1.0
pb.inputs["Coat Roughness"].default_value = 0.02
lw = N.new("ShaderNodeLayerWeight"); lw.location = (-500, -100)
lw.inputs["Blend"].default_value = 0.5
fr = ramp(nt, [(0.0, (0.004, 0.03, 0.04)), (0.55, (0.03, 0.16, 0.17)), (0.9, (0.18, 0.55, 0.50)),
               (1.0, (0.35, 0.75, 0.62))])
fr.location = (-300, -100)
nt.links.new(lw.outputs["Facing"], fr.inputs["Fac"])
tco = N.new("ShaderNodeTexCoord"); tco.location = (-700, -350)
sep = N.new("ShaderNodeSeparateXYZ"); sep.location = (-500, -350)
nt.links.new(tco.outputs["Object"], sep.inputs[0])
mr = N.new("ShaderNodeMapRange"); mr.location = (-300, -350)
mr.inputs["From Min"].default_value = 0.1 * er * S
mr.inputs["From Max"].default_value = -0.9 * er * S
mr.inputs["To Min"].default_value = 0.0
mr.inputs["To Max"].default_value = 1.0
nt.links.new(sep.outputs["Y"], mr.inputs["Value"])
glowc = N.new("ShaderNodeMix"); glowc.data_type = "RGBA"; glowc.blend_type = "ADD"; glowc.location = (-50, -200)
nt.links.new(mr.outputs[0], glowc.inputs["Factor"])
nt.links.new(fr.outputs["Color"], glowc.inputs[6])
glowc.inputs[7].default_value = (0.10, 0.32, 0.30, 1)
emo = N.new("ShaderNodeEmission"); emo.location = (200, -200)
nt.links.new(glowc.outputs[2], emo.inputs["Color"])
addsh = N.new("ShaderNodeAddShader"); addsh.location = (500, 0)
nt.links.new(pb.outputs[0], addsh.inputs[0]); nt.links.new(emo.outputs[0], addsh.inputs[1])
nt.links.new(addsh.outputs[0], out.inputs["Surface"])
eye_ob.data.materials.append(m)

# ------------------------------------------------------------------ materiales aditivos / tarjetas
def additive_mat(name, image, color, strength):
    m, nt, out = new_mat(name, "BLENDED")
    N = nt.nodes
    t = N.new("ShaderNodeTexImage"); t.image = image; t.location = (-600, 0)
    t.extension = "CLIP"
    e = N.new("ShaderNodeEmission"); e.location = (-200, 0)
    e.inputs["Color"].default_value = (*color, 1)
    mathn = N.new("ShaderNodeMath"); mathn.operation = "MULTIPLY"; mathn.location = (-400, -150)
    mathn.inputs[1].default_value = strength
    nt.links.new(t.outputs["Alpha"], mathn.inputs[0])
    nt.links.new(mathn.outputs[0], e.inputs["Strength"])
    tr = N.new("ShaderNodeBsdfTransparent"); tr.location = (-200, 150)
    ad = N.new("ShaderNodeAddShader"); ad.location = (200, 0)
    nt.links.new(tr.outputs[0], ad.inputs[0]); nt.links.new(e.outputs[0], ad.inputs[1])
    nt.links.new(ad.outputs[0], out.inputs["Surface"])
    m.use_backface_culling = False
    return m


def card_mat(name, image, tint=(1, 1, 1), strength=1.0):
    m, nt, out = new_mat(name, "BLENDED")
    N = nt.nodes
    t = N.new("ShaderNodeTexImage"); t.image = image; t.location = (-600, 0)
    t.extension = "CLIP"
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.location = (-350, 0)
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(t.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (*tint, 1)
    e = N.new("ShaderNodeEmission"); e.location = (-150, 0)
    e.inputs["Strength"].default_value = strength
    nt.links.new(mix.outputs[2], e.inputs["Color"])
    tr = N.new("ShaderNodeBsdfTransparent"); tr.location = (-150, 150)
    ms = N.new("ShaderNodeMixShader"); ms.location = (200, 0)
    nt.links.new(t.outputs["Alpha"], ms.inputs["Fac"])
    nt.links.new(tr.outputs[0], ms.inputs[1]); nt.links.new(e.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs["Surface"])
    return m


def card(name, mat, loc, width, aspect, parent=None, facing_rot=(math.radians(90), 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (width, width * aspect, 1)
    ob.rotation_euler = facing_rot
    ob.data.materials.append(mat)
    if parent:
        ob.parent = parent
        ob.location = loc
    ob.visible_shadow = False
    return ob


# halos de la luna
halo_img = img("halo.png")
card("Halo_Calido", additive_mat("Halo_Calido", halo_img, (1.0, 0.88, 0.5), 0.8), (0, 1.5, 0), 17, 1)
card("Halo_Turquesa", additive_mat("Halo_Turquesa", halo_img, (0.10, 0.42, 0.50), 0.55), (0, 6, 0), 48, 1)

# destello del ojo (hijo de la luna, coordenadas locales)
spark_img = img("sparkle.png")
spark_mat = additive_mat("Destello", spark_img, (1.0, 1.0, 0.95), 4.0)
glint = card("Destello_Ojo", spark_mat, (ex * S - 0.08 * er * S, ey * S + 0.12 * er * S, eye_z + er * S + 0.05),
             1.3, 1, parent=moon_root, facing_rot=(0, 0, 0))
glint2 = card("Destello_Ojo_Peq", spark_mat, (ex * S + 0.35 * er * S, ey * S - 0.40 * er * S, eye_z + er * S * 0.85),
              0.35, 1, parent=moon_root, facing_rot=(0, 0, math.radians(20)))

# ------------------------------------------------------------------ nubes
cloud_imgs = [img(f"cloud_{i}.png") for i in range(5)]
cloud_mats = {}


def cloud(name, idx, loc, width, tint=(1, 1, 1), strength=1.0, flip=False):
    keyc = (idx, tint, strength)
    if keyc not in cloud_mats:
        cloud_mats[keyc] = card_mat(f"Nube_{len(cloud_mats)}", cloud_imgs[idx], tint, strength)
    ob = card(name, cloud_mats[keyc], loc, width, 0.5)
    if flip:
        ob.scale.x *= -1
    return ob


near_moon = (1.08, 1.12, 1.1)
clouds = [
    # alrededor de la luna (como la referencia)
    (0, (-8.2, 8, 4.5), 9.5, near_moon, False), (2, (-9.0, 10, -4.5), 12, near_moon, True),
    (1, (8.6, 9, 6.0), 9.5, near_moon, False), (3, (8.8, 7, -3.0), 10.5, near_moon, True),
    (4, (7.8, 12, -9.5), 13, (1, 1, 1), False), (0, (-7.5, 12, -10.5), 11, (1, 1, 1), True),
    (1, (-5.5, 16, 11.0), 7, (0.9, 0.95, 1), True), (2, (6.5, 16, 12.0), 7, (0.9, 0.95, 1), False),
    (3, (3.8, -3.5, -8.4), 8, (1.05, 1.08, 1.1), False),
    # medio camino
    (4, (-9.5, -24, -5), 12, (0.95, 0.97, 1), False), (0, (10.5, -30, -9), 13, (0.95, 0.97, 1), True),
    (2, (-12, -40, -21), 16, (0.9, 0.93, 1), False), (1, (13, -42, -14), 14, (0.9, 0.93, 1), True),
    (3, (-8, -36, 4), 12, (0.9, 0.93, 1), True), (4, (9, -55, -2), 14, (0.9, 0.93, 1), False),
    # capa que atraviesa la cámara
    (2, (-12.0, -53, -15.0), 20, (0.85, 0.9, 1), False), (3, (4.0, -49.5, -12.0), 24, (0.9, 0.94, 1), True),
    (0, (-10.0, -45, -5.0), 16, (0.95, 0.97, 1), False),
    # bajo la luna (rellenan la parte inferior del encuadre a mitad de camino)
    (1, (-7, -22, -21), 13, (0.9, 0.93, 1), False), (4, (8, -12, -19), 12, (0.92, 0.95, 1), True),
    (0, (1, -32, -31), 17, (0.85, 0.9, 1), True),
    # cerca del pueblo
    (1, (-7, -63, -38), 18, (0.8, 0.85, 0.95), False), (4, (10, -66, -36), 20, (0.8, 0.85, 0.95), True),
    (2, (-17, -70, -45), 24, (0.75, 0.8, 0.92), True), (3, (19, -72, -47), 22, (0.75, 0.8, 0.92), False),
    (0, (2, -66, -52), 28, (0.7, 0.75, 0.9), False),
]
for i, (idx, loc, w, tint, flip) in enumerate(clouds):
    cloud(f"Nube_{i:02d}", idx, loc, w, tint, 1.0, flip)

# pueblo
town_img = img("town.png")
card("Pueblo", card_mat("Pueblo", town_img), (0, -88, -55), 64, 0.5)

# estrellas brillantes con destello
rng = np.random.default_rng(11)
star_mat = additive_mat("Estrella", spark_img, (0.85, 0.95, 1.0), 2.5)
stars = []
for i in range(16):
    az = rng.uniform(-0.55, 0.55)
    el = rng.uniform(0.0, 0.75)
    d = rng.uniform(140, 200)
    loc = (d * math.sin(az) * math.cos(el), d * math.cos(az) * math.cos(el) - 115, d * math.sin(el) - 50)
    if abs(loc[0]) < 9 and abs(loc[2]) < 9:
        continue
    st = card(f"Estrella_{i:02d}", star_mat, loc, rng.uniform(1.2, 2.6), 1)
    stars.append(st)

# ------------------------------------------------------------------ mundo (cielo + estrellas)
world = bpy.data.worlds.new("Cielo")
scn.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
W = wn.nodes
wo = W.new("ShaderNodeOutputWorld"); wo.location = (1200, 0)
wtc = W.new("ShaderNodeTexCoord"); wtc.location = (-1200, 0)
wsep = W.new("ShaderNodeSeparateXYZ"); wsep.location = (-1000, 300)
wn.links.new(wtc.outputs["Generated"], wsep.inputs[0])
sky = ramp(wn, [(0.0, (0.07, 0.16, 0.30)), (0.42, (0.045, 0.12, 0.26)), (0.52, (0.035, 0.10, 0.23)),
                (0.75, (0.018, 0.05, 0.13)), (1.0, (0.008, 0.02, 0.06))], "LINEAR")
sky.location = (-600, 300)
wmr = W.new("ShaderNodeMapRange"); wmr.location = (-800, 300)
wmr.inputs["From Min"].default_value = -1.0
wmr.inputs["From Max"].default_value = 1.0
wn.links.new(wsep.outputs["Z"], wmr.inputs["Value"])
wn.links.new(wmr.outputs[0], sky.inputs["Fac"])


def star_layer(scale, radius, bright, sparse, y):
    vor = W.new("ShaderNodeTexVoronoi"); vor.location = (-800, y)
    vor.voronoi_dimensions = "3D"
    vor.inputs["Scale"].default_value = scale
    vor.inputs["Randomness"].default_value = 1.0
    wn.links.new(wtc.outputs["Generated"], vor.inputs["Vector"])
    # tamaño: 1 - dist/radius
    m1 = W.new("ShaderNodeMath"); m1.operation = "DIVIDE"; m1.location = (-600, y)
    wn.links.new(vor.outputs["Distance"], m1.inputs[0]); m1.inputs[1].default_value = radius
    m2 = W.new("ShaderNodeMath"); m2.operation = "SUBTRACT"; m2.use_clamp = True; m2.location = (-450, y)
    m2.inputs[0].default_value = 1.0; wn.links.new(m1.outputs[0], m2.inputs[1])
    m3 = W.new("ShaderNodeMath"); m3.operation = "POWER"; m3.location = (-300, y)
    wn.links.new(m2.outputs[0], m3.inputs[0]); m3.inputs[1].default_value = 2.0
    # brillo aleatorio por celda (solo algunas celdas)
    sc = W.new("ShaderNodeSeparateColor"); sc.location = (-600, y - 200)
    wn.links.new(vor.outputs["Color"], sc.inputs[0])
    gt = W.new("ShaderNodeMapRange"); gt.location = (-450, y - 200)
    gt.inputs["From Min"].default_value = sparse
    gt.inputs["From Max"].default_value = 1.0
    wn.links.new(sc.outputs[0], gt.inputs["Value"])
    m4 = W.new("ShaderNodeMath"); m4.operation = "MULTIPLY"; m4.location = (-150, y)
    wn.links.new(m3.outputs[0], m4.inputs[0]); wn.links.new(gt.outputs[0], m4.inputs[1])
    return m4, sc


s1, sc1 = star_layer(260, 0.16, 1.0, 0.55, -100)
s2, sc2 = star_layer(70, 0.07, 1.0, 0.85, -500)
# parpadeo
tw = W.new("ShaderNodeTexNoise"); tw.location = (-400, -900)
tw.noise_dimensions = "4D"
tw.inputs["Scale"].default_value = 90
wn.links.new(wtc.outputs["Generated"], tw.inputs["Vector"])
tw.inputs["W"].default_value = 0.0
tw.inputs["W"].keyframe_insert("default_value", frame=1)
tw.inputs["W"].default_value = 18.0
tw.inputs["W"].keyframe_insert("default_value", frame=F_END)
twr = W.new("ShaderNodeMapRange"); twr.location = (-200, -900)
twr.inputs["From Min"].default_value = 0.3; twr.inputs["From Max"].default_value = 0.7
twr.inputs["To Min"].default_value = 0.25; twr.inputs["To Max"].default_value = 1.6
wn.links.new(tw.outputs["Fac"], twr.inputs["Value"])
sum_s = W.new("ShaderNodeMath"); sum_s.operation = "ADD"; sum_s.location = (0, -300)
wn.links.new(s1.outputs[0], sum_s.inputs[0])
s2b = W.new("ShaderNodeMath"); s2b.operation = "MULTIPLY"; s2b.location = (-50, -500)
wn.links.new(s2.outputs[0], s2b.inputs[0]); s2b.inputs[1].default_value = 2.5
wn.links.new(s2b.outputs[0], sum_s.inputs[1])
tw_m = W.new("ShaderNodeMath"); tw_m.operation = "MULTIPLY"; tw_m.location = (150, -400)
wn.links.new(sum_s.outputs[0], tw_m.inputs[0]); wn.links.new(twr.outputs[0], tw_m.inputs[1])
# solo sobre el horizonte
hz = W.new("ShaderNodeMapRange"); hz.location = (-600, 650)
hz.inputs["From Min"].default_value = -0.12; hz.inputs["From Max"].default_value = 0.05
wn.links.new(wsep.outputs["Z"], hz.inputs["Value"])
tw_h = W.new("ShaderNodeMath"); tw_h.operation = "MULTIPLY"; tw_h.location = (350, -300)
wn.links.new(tw_m.outputs[0], tw_h.inputs[0]); wn.links.new(hz.outputs[0], tw_h.inputs[1])
star_col = W.new("ShaderNodeMix"); star_col.data_type = "RGBA"; star_col.location = (350, -600)
wn.links.new(sc1.outputs[2], star_col.inputs["Factor"])
star_col.inputs[6].default_value = (1.0, 1.0, 1.0, 1)
star_col.inputs[7].default_value = (0.55, 0.85, 1.0, 1)
sc_m = W.new("ShaderNodeMix"); sc_m.data_type = "RGBA"; sc_m.blend_type = "MULTIPLY"; sc_m.location = (550, -400)
sc_m.inputs["Factor"].default_value = 1.0
wn.links.new(star_col.outputs[2], sc_m.inputs[6])
cvt = W.new("ShaderNodeCombineColor"); cvt.location = (500, -250)
for i in range(3):
    wn.links.new(tw_h.outputs[0], cvt.inputs[i])
wn.links.new(cvt.outputs[0], sc_m.inputs[7])
sky_add = W.new("ShaderNodeMix"); sky_add.data_type = "RGBA"; sky_add.blend_type = "ADD"; sky_add.location = (800, 100)
sky_add.inputs["Factor"].default_value = 1.0
wn.links.new(sky.outputs["Color"], sky_add.inputs[6])
wn.links.new(sc_m.outputs[2], sky_add.inputs[7])
bg = W.new("ShaderNodeBackground"); bg.location = (1000, 0)
wn.links.new(sky_add.outputs[2], bg.inputs["Color"])
wn.links.new(bg.outputs[0], wo.inputs["Surface"])

# ------------------------------------------------------------------ luz (para el sombreado toon)
sun_d = bpy.data.lights.new("Sol", "SUN")
sun_d.energy = 3.0
sun_d.angle = math.radians(3)
sun = bpy.data.objects.new("Sol", sun_d)
scn.collection.objects.link(sun)
sun.rotation_euler = Vector((-0.55, -1.0, 0.65)).to_track_quat("Z", "Y").to_euler()

# ------------------------------------------------------------------ cámara
cam_d = bpy.data.cameras.new("Camara")
cam_d.sensor_fit = "AUTO"
cam_d.sensor_width = 36
cam_d.clip_start = 0.05
cam_d.clip_end = 2000
cam = bpy.data.objects.new("Camara", cam_d)
scn.collection.objects.link(cam)
scn.camera = cam
target = bpy.data.objects.new("Objetivo_Camara", None)
scn.collection.objects.link(target)
tr = cam.constraints.new("TRACK_TO")
tr.target = target
tr.track_axis = "TRACK_NEGATIVE_Z"
tr.up_axis = "UP_Y"

cam_keys = [  # frame, posición, objetivo, focal
    (1,   (0.0, -115, -50.0), (0, 0, -44.0), 24),
    (48,  (0.0, -112, -48.5), (0, 0, -40.0), 24),
    (190, (1.6, -76, -27.0),  (0, 0, -11.0), 27),
    (300, (-1.0, -44, -10.0), (0, 0, -2.0),  31),
    (420, (-0.3, -21, -0.9),  (-0.4, 0, -0.5), 34),
    (504, (-0.6, -17.6, -0.5), (-0.6, 0, -0.45), 36),
]
for f, p, t, fl in cam_keys:
    key(cam, "location", f, Vector(p))
    key(target, "location", f, Vector(t))
    cam_d.lens = fl
    cam_d.keyframe_insert("lens", frame=f)

# ------------------------------------------------------------------ animación de la luna
for f in range(1, F_END + 1, 24):
    t = f / FPS
    moon_root.location = (0.0, 0.0, 0.18 * math.sin(t * 2 * math.pi / 6.0))
    moon_root.keyframe_insert("location", frame=f)
    moon_root.rotation_euler = (math.radians(90 + 1.5 * math.sin(t * 2 * math.pi / 7.0)),
                                math.radians(2.5 * math.sin(t * 2 * math.pi / 9.0 + 1.0)),
                                math.radians(1.5 * math.sin(t * 2 * math.pi / 8.0 + 2.0)))
    moon_root.keyframe_insert("rotation_euler", frame=f)

# destellos que laten
for f in range(1, F_END + 1, 4):
    t = f / FPS
    base = 1.0 + 0.25 * math.sin(t * 5.0)
    if f > 430:   # gran destello al acercarse
        base += 0.9 * math.exp(-((f - 455) / 14.0) ** 2)
    glint.scale = (1.3 * base, 1.3 * base, 1)
    glint.rotation_euler = (0, 0, 0.15 * math.sin(t * 1.3))
    glint.keyframe_insert("scale", frame=f)
    glint.keyframe_insert("rotation_euler", frame=f)
    b2 = 0.35 * (1.0 + 0.4 * math.sin(t * 3.7 + 1.0))
    glint2.scale = (b2, b2, 1)
    glint2.keyframe_insert("scale", frame=f)
for i, st in enumerate(stars):
    s0 = st.scale.x
    ph = rng.uniform(0, 6.28)
    sp = rng.uniform(1.5, 3.5)
    for f in range(1, F_END + 1, 6):
        k = s0 * (0.55 + 0.45 * math.sin(f / FPS * sp + ph))
        st.scale = (k, k, 1)
        st.keyframe_insert("scale", frame=f)

# ------------------------------------------------------------------ composición (bloom + viñeta)
scn.use_nodes = True
ct = scn.node_tree
ct.nodes.clear()
C = ct.nodes
rl = C.new("CompositorNodeRLayers"); rl.location = (-600, 0)
gl1 = C.new("CompositorNodeGlare"); gl1.location = (-350, 0)
gl1.glare_type = "FOG_GLOW"
gl1.quality = "HIGH"
gl1.size = 9
gl1.threshold = 0.82
gl1.mix = -0.35
ct.links.new(rl.outputs["Image"], gl1.inputs["Image"])
ell = C.new("CompositorNodeEllipseMask"); ell.location = (-350, -300)
ell.width = 1.25; ell.height = 1.1
blur = C.new("CompositorNodeBlur"); blur.location = (-150, -300)
blur.filter_type = "FAST_GAUSS"; blur.use_relative = True
blur.factor_x = 25; blur.factor_y = 25
ct.links.new(ell.outputs["Mask"], blur.inputs["Image"])
vig = C.new("CompositorNodeMixRGB"); vig.location = (100, 0)
vig.blend_type = "MULTIPLY"
vig.inputs["Fac"].default_value = 0.4
ct.links.new(gl1.outputs["Image"], vig.inputs[1])
ct.links.new(blur.outputs["Image"], vig.inputs[2])
cb = C.new("CompositorNodeColorBalance"); cb.location = (300, 0)
cb.correction_method = "LIFT_GAMMA_GAIN"
cb.lift = (1.0, 1.01, 1.03)
cb.gain = (1.02, 1.01, 1.0)
ct.links.new(vig.outputs["Image"], cb.inputs["Image"])
comp = C.new("CompositorNodeComposite"); comp.location = (550, 0)
ct.links.new(cb.outputs["Image"], comp.inputs["Image"])

# ------------------------------------------------------------------ guardar
blend = os.path.join(HERE, "luna_sonriente.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
print("Guardado", blend)
