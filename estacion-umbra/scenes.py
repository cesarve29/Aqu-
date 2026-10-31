#!/usr/bin/env python3
"""
ESTACION UMBRA - escenas 3D construidas 100% por codigo con Blender (bpy) y
renderizadas con Cycles (path tracing) + OpenImageDenoise.

Uso:
    python3 scenes.py --shot 3                 -> renderiza todos los cuadros de la toma 3
    python3 scenes.py --shot 3 --still 6.5     -> un solo cuadro (segundo 6.5 de la toma)
    python3 scenes.py --all                    -> todas las tomas en orden
Variables de entorno: UMBRA_OUT (carpeta de cuadros), UMBRA_W/UMBRA_H, UMBRA_SAMPLES.
"""
import math
import os
import random
import sys
import time

import bpy  # noqa: I001  (bpy debe importarse antes que bmesh)
import bmesh
import numpy as np
from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("UMBRA_OUT", os.path.join(HERE, "build", "frames"))
FPS = int(os.environ.get("UMBRA_FPS", 15))
SHOT_FPS = {8: 30, 13: 30}  # jumpscares: mas cuadros nativos para el movimiento rapido
BASE_EXPOSURE = 0.7
THREADS = int(os.environ.get("UMBRA_THREADS", 0))
RES_W = int(os.environ.get("UMBRA_W", 960))
RES_H = int(os.environ.get("UMBRA_H", 540))
SAMPLES = int(os.environ.get("UMBRA_SAMPLES", 20))
ENGINE = os.environ.get("UMBRA_ENGINE", "CYCLES")
EEVEE_SAMPLES = int(os.environ.get("UMBRA_EEVEE_SAMPLES", 32))
FONT_TITLE = "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
HAND_PNG = os.path.join(HERE, "build", "handprint.png")


# =============================================================================
# utilidades generales
# =============================================================================
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def shake(t, amp, freq=9.0, seed=0.0):
    return Vector((noise.noise(Vector((t * freq, seed, 0.3))) * amp,
                   noise.noise(Vector((seed, t * freq, 1.7))) * amp,
                   noise.noise(Vector((2.1, seed, t * freq))) * amp))


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    if ENGINE == "EEVEE":
        sc.render.engine = "BLENDER_EEVEE"
        ee = sc.eevee
        ee.taa_render_samples = EEVEE_SAMPLES
        for k, v in (("use_raytracing", True), ("use_shadows", True), ("volumetric_tile_size", "4"),
                     ("volumetric_samples", 64), ("use_volumetric_shadows", True), ("shadow_ray_count", 2),
                     ("shadow_step_count", 8), ("use_fast_gi", True), ("volumetric_end", 120.0)):
            try:
                setattr(ee, k, v)
            except Exception as e:
                print("eevee opt", k, e)
        try:
            ee.ray_tracing_options.resolution_scale = "1"
            ee.ray_tracing_options.use_denoise = True
        except Exception as e:
            print("eevee rt", e)
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = SAMPLES
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.05
    cy.use_denoising = True
    try:
        cy.denoising_prefilter = os.environ.get("UMBRA_PREFILTER", "FAST")
    except Exception:
        pass
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.max_bounces = 4
    cy.diffuse_bounces = int(os.environ.get("UMBRA_DIFF", 1))
    cy.glossy_bounces = 1
    cy.transmission_bounces = 4
    if os.environ.get("UMBRA_FASTGI", "1") == "1":
        cy.use_fast_gi = True
        cy.ao_bounces_render = 1
    cy.volume_bounces = 0
    cy.transparent_max_bounces = 8
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 5.0
    cy.volume_step_rate = 3.0
    cy.volume_max_steps = 96
    sc.render.resolution_x = RES_W
    sc.render.resolution_y = RES_H
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.view_settings.exposure = BASE_EXPOSURE
    if THREADS:
        sc.render.threads_mode = "FIXED"
        sc.render.threads = THREADS
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.light_settings.distance = 4.0
    w.use_nodes = True
    return sc


def world_color(col, strength):
    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*col, 1)
    bg.inputs[1].default_value = strength
    return bg


def link_obj(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def shade_smooth(ob):
    me = ob.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()


def subsurf(ob, lv=2):
    m = ob.modifiers.new("sub", "SUBSURF")
    m.levels = lv
    m.render_levels = lv
    shade_smooth(ob)
    return ob


def prim(kind, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), mat=None, name=None, **kw):
    ops = {
        "cube": bpy.ops.mesh.primitive_cube_add,
        "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "cyl": bpy.ops.mesh.primitive_cylinder_add,
        "plane": bpy.ops.mesh.primitive_plane_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
        "ico": bpy.ops.mesh.primitive_ico_sphere_add,
        "grid": bpy.ops.mesh.primitive_grid_add,
    }
    ops[kind](location=loc, rotation=rot, **kw)
    ob = bpy.context.active_object
    ob.scale = scale
    if name:
        ob.name = name
    if mat:
        ob.data.materials.append(mat)
    return ob


def parent(child, par):
    child.parent = par
    return child


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    return link_obj(e)


def look_at(ob, target, roll=0.0):
    d = Vector(target) - ob.location
    q = d.to_track_quat("-Z", "Y")
    ob.rotation_euler = q.to_euler()
    if roll:
        ob.rotation_euler.rotate_axis("Z", roll)


def camera(lens=35, loc=(0, 0, 0), target=(0, 1, 0), fstop=None, focus=None):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.02
    cd.clip_end = 2000
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus or 2.0
    cam = link_obj(bpy.data.objects.new("cam", cd))
    cam.location = loc
    look_at(cam, target)
    bpy.context.scene.camera = cam
    return cam


def light(kind, loc, energy, color=(1, 1, 1), size=0.1, target=None, spot=45, blend=0.3, name="L"):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    if kind == "AREA":
        ld.size = size
    if kind == "SUN":
        ld.angle = math.radians(size)
    if kind == "SPOT":
        ld.spot_size = math.radians(spot)
        ld.spot_blend = blend
    ob = link_obj(bpy.data.objects.new(name, ld))
    ob.location = loc
    try:
        ob.visible_camera = False
    except Exception:
        pass
    if target is not None:
        look_at(ob, target)
    return ob


# =============================================================================
# materiales (nodos)
# =============================================================================
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    if b is None:
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(b.outputs[0], o.inputs[0])
    return m, nt, b


def N(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def L(nt, a, b):
    nt.links.new(a, b)


def setin(node, name, val):
    if name in node.inputs:
        node.inputs[name].default_value = val


def principled(name, base=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, emit=None, emit_str=0.0,
               sss=0.0, sss_rad=(1, 0.4, 0.2), trans=0.0, ior=1.45, sheen=0.0, coat=0.0, alpha=1.0):
    m, nt, b = new_mat(name)
    setin(b, "Base Color", (*base, 1))
    setin(b, "Roughness", rough)
    setin(b, "Metallic", metal)
    setin(b, "IOR", ior)
    if emit:
        setin(b, "Emission Color", (*emit, 1))
        setin(b, "Emission Strength", emit_str)
    if sss:
        setin(b, "Subsurface Weight", sss)
        setin(b, "Subsurface Radius", sss_rad)
    if trans:
        setin(b, "Transmission Weight", trans)
    if sheen:
        setin(b, "Sheen Weight", sheen)
    if coat:
        setin(b, "Coat Weight", coat)
    if alpha < 1:
        setin(b, "Alpha", alpha)
    return m


def add_bump(nt, b, scale=30.0, strength=0.2, detail=6.0, dist=0.02, kind="noise", coords=None):
    if kind == "noise":
        tex = N(nt, "ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = detail
        out = tex.outputs["Fac"]
    elif kind == "wave":
        tex = N(nt, "ShaderNodeTexWave")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Distortion"].default_value = 0.0
        out = tex.outputs["Fac"]
    else:
        tex = N(nt, "ShaderNodeTexVoronoi")
        tex.inputs["Scale"].default_value = scale
        out = tex.outputs["Distance"]
    if coords is not None:
        L(nt, coords, tex.inputs["Vector"])
    bump = N(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = dist
    L(nt, out, bump.inputs["Height"])
    L(nt, bump.outputs["Normal"], b.inputs["Normal"])
    return tex, bump


def mix_color_by_noise(nt, b, c1, c2, scale=5.0, lo=0.4, hi=0.6, detail=4.0, coords=None):
    tex = N(nt, "ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    if coords is not None:
        L(nt, coords, tex.inputs["Vector"])
    ramp = N(nt, "ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = lo
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].position = hi
    ramp.color_ramp.elements[1].color = (*c2, 1)
    L(nt, tex.outputs["Fac"], ramp.inputs["Fac"])
    L(nt, ramp.outputs["Color"], b.inputs["Base Color"])
    return ramp


def mat_snow():
    m = principled("snow", base=(0.82, 0.86, 0.95), rough=0.6)
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF") or [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"][0]
    add_bump(nt, b, scale=25, strength=0.25, detail=8)
    return m


def get_bsdf(m):
    return [n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"][0]


def mat_metal_wall():
    m = principled("corrugated", base=(0.22, 0.27, 0.3), rough=0.55, metal=0.6)
    nt = m.node_tree
    b = get_bsdf(m)
    mix_color_by_noise(nt, b, (0.2, 0.25, 0.28), (0.3, 0.13, 0.05), scale=3, lo=0.55, hi=0.75)
    add_bump(nt, b, scale=12, strength=0.6, kind="wave", dist=0.05)
    return m


def mat_fabric(col, name="parka", sheen=0.25):
    m = principled(name, base=col, rough=0.85, sheen=sheen)
    add_bump(m.node_tree, get_bsdf(m), scale=180, strength=0.15, detail=3)
    return m


def mat_wood():
    m, nt, b = new_mat("wood")
    setin(b, "Roughness", 0.6)
    tc = N(nt, "ShaderNodeTexCoord")
    mp = N(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 14.0, 1.0)
    L(nt, tc.outputs["Object"], mp.inputs["Vector"])
    mix_color_by_noise(nt, b, (0.07, 0.035, 0.02), (0.22, 0.12, 0.06), scale=4, lo=0.3, hi=0.7,
                       detail=8, coords=mp.outputs["Vector"])
    add_bump(nt, b, scale=4, strength=0.15, coords=mp.outputs["Vector"])
    return m


def mat_frost_wall():
    """Pared metalica pintada con escarcha que trepa por los bordes."""
    m, nt, b = new_mat("frostwall")
    setin(b, "Roughness", 0.5)
    tc = N(nt, "ShaderNodeTexCoord")
    tex = N(nt, "ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 9.0
    tex.inputs["Detail"].default_value = 12
    tex.inputs["Roughness"].default_value = 0.65
    L(nt, tc.outputs["Object"], tex.inputs["Vector"])
    ramp = N(nt, "ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.6
    ramp.color_ramp.elements[0].color = (0.13, 0.16, 0.15, 1)
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (0.55, 0.62, 0.7, 1)
    L(nt, tex.outputs["Fac"], ramp.inputs["Fac"])
    L(nt, ramp.outputs["Color"], b.inputs["Base Color"])
    add_bump(nt, b, scale=60, strength=0.3)
    return m


def mat_emit(col, strength, name="emit"):
    m, nt, b = new_mat(name)
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            nt.nodes.remove(n)
    e = N(nt, "ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1)
    e.inputs["Strength"].default_value = strength
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    L(nt, e.outputs[0], out.inputs[0])
    return m


def emit_node(m):
    return [n for n in m.node_tree.nodes if n.type == "EMISSION"][0]


def mat_volume(name, density=0.02, color=(0.7, 0.8, 1.0), aniso=0.4, noise_scale=None, noise_amt=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = N(nt, "ShaderNodeOutputMaterial")
    v = N(nt, "ShaderNodeVolumePrincipled")
    v.inputs["Color"].default_value = (*color, 1)
    v.inputs["Density"].default_value = density
    v.inputs["Anisotropy"].default_value = aniso
    L(nt, v.outputs[0], out.inputs["Volume"])
    if noise_scale:
        tex = N(nt, "ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = noise_scale
        tex.inputs["Detail"].default_value = 3
        mul = N(nt, "ShaderNodeMath", operation="MULTIPLY")
        mul.inputs[1].default_value = density * 2
        sub = N(nt, "ShaderNodeMath", operation="SUBTRACT")
        sub.inputs[1].default_value = 0.35
        L(nt, tex.outputs["Fac"], sub.inputs[0])
        L(nt, sub.outputs[0], mul.inputs[0])
        L(nt, mul.outputs[0], v.inputs["Density"])
    return m


def mat_breath():
    """Vaho: volumen con ruido y caida radial; densidad animable via nodo Value."""
    m = bpy.data.materials.new("breath")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = N(nt, "ShaderNodeOutputMaterial")
    v = N(nt, "ShaderNodeVolumePrincipled")
    v.inputs["Color"].default_value = (0.9, 0.93, 1.0, 1)
    v.inputs["Anisotropy"].default_value = 0.5
    tc = N(nt, "ShaderNodeTexCoord")
    tex = N(nt, "ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 3.0
    tex.inputs["Detail"].default_value = 6
    L(nt, tc.outputs["Object"], tex.inputs["Vector"])
    ln = N(nt, "ShaderNodeVectorMath", operation="LENGTH")
    L(nt, tc.outputs["Object"], ln.inputs[0])
    fall = N(nt, "ShaderNodeMapRange")
    fall.inputs["From Min"].default_value = 1.0
    fall.inputs["From Max"].default_value = 0.2
    L(nt, ln.outputs["Value"], fall.inputs["Value"])
    m1 = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, tex.outputs["Fac"], m1.inputs[0])
    L(nt, fall.outputs["Result"], m1.inputs[1])
    sub = N(nt, "ShaderNodeMath", operation="SUBTRACT")
    sub.inputs[1].default_value = 0.22
    L(nt, m1.outputs[0], sub.inputs[0])
    val = N(nt, "ShaderNodeValue")
    val.name = "dens"
    val.outputs[0].default_value = 0.0
    m2 = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, sub.outputs[0], m2.inputs[0])
    L(nt, val.outputs[0], m2.inputs[1])
    L(nt, m2.outputs[0], v.inputs["Density"])
    L(nt, v.outputs[0], out.inputs["Volume"])
    return m


def mat_frost_glass(hand=False):
    """Vidrio escarchado: transmision con rugosidad variable + cristales blancos.
    Si hand=True, una mascara (huella de mano) derrite la escarcha (nodo Value 'reveal')."""
    m = bpy.data.materials.new("frostglass")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = N(nt, "ShaderNodeOutputMaterial")
    glass = N(nt, "ShaderNodeBsdfPrincipled")
    glass.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1)
    glass.inputs["Transmission Weight"].default_value = 1.0
    glass.inputs["IOR"].default_value = 1.2
    frost = N(nt, "ShaderNodeBsdfPrincipled")
    frost.inputs["Base Color"].default_value = (0.8, 0.86, 0.95, 1)
    frost.inputs["Roughness"].default_value = 0.6
    frost.inputs["Subsurface Weight"].default_value = 0.0
    tc = N(nt, "ShaderNodeTexCoord")
    # mascara de escarcha: ruido fino * borde (mas escarcha en las orillas)
    vor = N(nt, "ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 35
    nz = N(nt, "ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 4
    nz.inputs["Detail"].default_value = 10
    L(nt, tc.outputs["UV"], vor.inputs["Vector"])
    L(nt, tc.outputs["UV"], nz.inputs["Vector"])
    # distancia al centro del UV
    sep = N(nt, "ShaderNodeVectorMath", operation="SUBTRACT")
    sep.inputs[1].default_value = (0.5, 0.5, 0.0)
    L(nt, tc.outputs["UV"], sep.inputs[0])
    ln = N(nt, "ShaderNodeVectorMath", operation="LENGTH")
    L(nt, sep.outputs[0], ln.inputs[0])
    edge = N(nt, "ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 0.15
    edge.inputs["From Max"].default_value = 0.65
    L(nt, ln.outputs["Value"], edge.inputs["Value"])
    add1 = N(nt, "ShaderNodeMath", operation="ADD")
    L(nt, edge.outputs["Result"], add1.inputs[0])
    L(nt, nz.outputs["Fac"], add1.inputs[1])
    mr = N(nt, "ShaderNodeMapRange")
    mr.name = "frostamt"
    mr.inputs["From Min"].default_value = 0.75
    mr.inputs["From Max"].default_value = 1.35
    L(nt, add1.outputs[0], mr.inputs["Value"])
    crystals = N(nt, "ShaderNodeMath", operation="MULTIPLY")
    L(nt, mr.outputs["Result"], crystals.inputs[0])
    vr = N(nt, "ShaderNodeMapRange")
    vr.inputs["From Min"].default_value = 0.0
    vr.inputs["From Max"].default_value = 0.5
    vr.inputs["To Min"].default_value = 0.6
    vr.inputs["To Max"].default_value = 1.0
    L(nt, vor.outputs["Distance"], vr.inputs["Value"])
    L(nt, vr.outputs["Result"], crystals.inputs[1])
    mask = crystals.outputs[0]
    if hand:
        img = bpy.data.images.load(HAND_PNG)
        it = N(nt, "ShaderNodeTexImage")
        it.image = img
        it.extension = "CLIP"
        L(nt, tc.outputs["UV"], it.inputs["Vector"])
        val = N(nt, "ShaderNodeValue")
        val.name = "reveal"
        val.outputs[0].default_value = 0.0
        hm = N(nt, "ShaderNodeMath", operation="MULTIPLY")
        L(nt, it.outputs["Color"], hm.inputs[0])
        L(nt, val.outputs[0], hm.inputs[1])
        inv = N(nt, "ShaderNodeMath", operation="SUBTRACT")
        inv.inputs[0].default_value = 1.0
        L(nt, hm.outputs[0], inv.inputs[1])
        mm = N(nt, "ShaderNodeMath", operation="MULTIPLY")
        L(nt, mask, mm.inputs[0])
        L(nt, inv.outputs[0], mm.inputs[1])
        mask = mm.outputs[0]
    # rugosidad del vidrio sube con la escarcha
    rr = N(nt, "ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.05
    rr.inputs["To Max"].default_value = 0.45
    L(nt, mask, rr.inputs["Value"])
    L(nt, rr.outputs["Result"], glass.inputs["Roughness"])
    bump = N(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    L(nt, vor.outputs["Distance"], bump.inputs["Height"])
    L(nt, bump.outputs["Normal"], frost.inputs["Normal"])
    mix = N(nt, "ShaderNodeMixShader")
    L(nt, mask, mix.inputs["Fac"])
    L(nt, glass.outputs[0], mix.inputs[1])
    L(nt, frost.outputs[0], mix.inputs[2])
    L(nt, mix.outputs[0], out.inputs["Surface"])
    return m


def mat_skin():
    m = principled("skin", base=(0.62, 0.6, 0.55), rough=0.42, sss=0.5, sss_rad=(1.0, 0.35, 0.25))
    nt = m.node_tree
    b = get_bsdf(m)
    mix_color_by_noise(nt, b, (0.45, 0.47, 0.44), (0.72, 0.68, 0.62), scale=6, lo=0.35, hi=0.7, detail=10)
    add_bump(nt, b, scale=40, strength=0.25, detail=10, dist=0.005)
    return m


def mat_paper():
    return principled("paper", base=(0.85, 0.82, 0.72), rough=0.8)


# =============================================================================
# nieve / polvo: nube de puntos animada (geometry nodes Mesh to Points)
# =============================================================================
class Particles:
    def __init__(self, n, lo, hi, vel, radius, mat, seed=1, turb=0.3, turb_freq=0.6, name="snow"):
        rng = np.random.default_rng(seed)
        self.lo = np.array(lo, dtype=np.float64)
        self.hi = np.array(hi, dtype=np.float64)
        self.size = self.hi - self.lo
        self.p0 = rng.uniform(self.lo, self.hi, (n, 3))
        self.vel = np.array(vel, dtype=np.float64) * rng.uniform(0.7, 1.3, (n, 1))
        self.phase = rng.uniform(0, 6.28, (n, 3))
        self.turb = turb
        self.tf = turb_freq
        me = bpy.data.meshes.new(name)
        me.vertices.add(n)
        me.vertices.foreach_set("co", self.p0.ravel())
        me.update()
        self.me = me
        self.ob = link_obj(bpy.data.objects.new(name, me))
        ng = bpy.data.node_groups.new(name + "GN", "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gi = ng.nodes.new("NodeGroupInput")
        go = ng.nodes.new("NodeGroupOutput")
        m2p = ng.nodes.new("GeometryNodeMeshToPoints")
        m2p.inputs["Radius"].default_value = radius
        sm = ng.nodes.new("GeometryNodeSetMaterial")
        sm.inputs["Material"].default_value = mat
        ng.links.new(gi.outputs[0], m2p.inputs["Mesh"])
        ng.links.new(m2p.outputs["Points"], sm.inputs["Geometry"])
        ng.links.new(sm.outputs["Geometry"], go.inputs[0])
        mod = self.ob.modifiers.new("pts", "NODES")
        mod.node_group = ng

    def update(self, t):
        p = self.p0 + self.vel * t + self.turb * np.sin(self.tf * t * 6.28 * 0.3 + self.phase)
        p = self.lo + np.mod(p - self.lo, self.size)
        self.me.vertices.foreach_set("co", p.ravel())
        self.me.update()


def snow_mat():
    return principled("snowflake", base=(0.95, 0.97, 1.0), rough=0.4)


# =============================================================================
# modelos
# =============================================================================
def terrain(size=700, res=220, seed=3, flat_r=30.0, base_h=0.0):
    ob = prim("grid", x_subdivisions=res, y_subdivisions=res, size=size, mat=mat_snow(), name="terrain")
    me = ob.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    off = Vector((seed * 13.1, seed * 7.7, 0))
    for i in range(len(co)):
        x, y = co[i, 0], co[i, 1]
        d = math.hypot(x, y)
        v = Vector((x / 160.0, y / 160.0, 0)) + off
        h = noise.hetero_terrain(v, 0.9, 2.1, 7, 0.4) * 38.0
        h += noise.ridged_multi_fractal(Vector((x / 90, y / 90, 0)) + off, 1.0, 2.0, 5, 0.8, 1.6) * 22
        f = smooth((d - flat_r) / 70.0) * (0.12 + 0.88 * smooth((y / max(d, 1.0) + 0.3) / 0.9))
        co[i, 2] = base_h + h * f + (d / 18.0) * f + noise.noise(Vector((x / 12, y / 12, 0))) * 0.6
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    shade_smooth(ob)
    return ob


def station_exterior(win_strength=40.0, hollow=False):
    """Estacion de investigacion: modulo de chapa corrugada, ventana calida, antena."""
    objs = {}
    wall = mat_metal_wall()
    snowm = mat_snow()
    body = prim("cube", loc=(0, 0, 1.6), scale=(5, 3, 1.6), mat=wall, name="body")
    bev = body.modifiers.new("bev", "BEVEL")
    bev.width = 0.08
    bev.segments = 3
    if hollow:
        sol = body.modifiers.new("sol", "SOLIDIFY")
        sol.thickness = 0.12
        cutter = prim("cube", loc=(-2.2, -3.0, 1.9), scale=(0.75, 0.4, 0.55), name="cutter")
        cutter.hide_render = True
        cutter.display_type = "WIRE"
        bo = body.modifiers.new("cut", "BOOLEAN")
        bo.operation = "DIFFERENCE"
        bo.object = cutter
        inner = principled("innerwall", base=(0.25, 0.22, 0.18), rough=0.8)
        prim("plane", loc=(-2.2, 1.0, 1.6), scale=(3, 1.6, 1), rot=(math.pi / 2, 0, 0), mat=inner)
    prim("cube", loc=(0, 0, 3.32), scale=(5.25, 3.25, 0.12), mat=wall)
    roof_snow = prim("cube", loc=(0, 0, 3.55), scale=(5.2, 3.2, 0.18), mat=snowm)
    subsurf(roof_snow, 2)
    # ventana calida (frente -Y)
    winm = mat_emit((1.0, 0.55, 0.22), win_strength, "window_glow")
    objs["win_mat"] = winm
    win = prim("cube", loc=(-2.2, -3.01, 1.9), scale=(0.75, 0.04, 0.55), mat=winm, name="win")
    frame = principled("frame", base=(0.05, 0.05, 0.05), rough=0.4, metal=0.8)
    for dx in (-0.8, 0.8):
        prim("cube", loc=(-2.2 + dx, -3.06, 1.9), scale=(0.06, 0.05, 0.62), mat=frame)
    for dz in (-0.6, 0.6):
        prim("cube", loc=(-2.2, -3.06, 1.9 + dz), scale=(0.86, 0.05, 0.06), mat=frame)
    prim("cube", loc=(-2.2, -3.06, 1.9), scale=(0.03, 0.05, 0.55), mat=frame)
    objs["win"] = win
    # puerta
    door = principled("door", base=(0.35, 0.08, 0.05), rough=0.5, metal=0.5)
    prim("cube", loc=(1.8, -3.02, 1.15), scale=(0.6, 0.06, 1.15), mat=door, name="door")
    prim("cube", loc=(1.8, -3.0, 0.02), scale=(0.62, 0.05, 0.02), mat=mat_emit((1.0, 0.5, 0.2), 25, "doorleak"))
    prim("cyl", loc=(2.25, -3.1, 1.1), scale=(0.04, 0.04, 0.12), rot=(math.pi / 2, 0, 0), mat=frame)
    # mastil de antena + luz roja
    mast = principled("mast", base=(0.5, 0.5, 0.52), rough=0.3, metal=1.0)
    prim("cyl", loc=(3.8, 1.5, 6.0), scale=(0.06, 0.06, 3.0), mat=mast)
    for z in (4.5, 6.0, 7.5):
        prim("cyl", loc=(3.8, 1.5, z), scale=(0.9, 0.025, 0.025), rot=(0, math.pi / 2, 0), mat=mast)
    redm = mat_emit((1.0, 0.05, 0.02), 60, "beacon")
    prim("sphere", loc=(3.8, 1.5, 9.05), scale=(0.09, 0.09, 0.09), mat=redm)
    objs["beacon"] = redm
    dish = prim("sphere", loc=(-3.5, 1.2, 4.0), scale=(0.7, 0.25, 0.7), mat=mast)
    dish.rotation_euler = (0.4, 0, 0.6)
    # deriva de nieve contra la pared
    for i, (x, s) in enumerate([(-4, 1.2), (-0.9, 0.8), (4.4, 1.0)]):
        d = prim("sphere", loc=(x, -3.3, 0.0), scale=(s * 1.6, s * 0.9, s * 0.55), mat=snowm)
        subsurf(d, 1)
    # luz real saliendo de la ventana
    objs["win_light"] = light("AREA", (-2.2, -3.3, 1.9), 180, (1.0, 0.55, 0.25), size=1.4,
                              target=(-2.2, -8, 0.8), name="winlight")
    objs["beacon_light"] = light("POINT", (3.8, 1.3, 9.05), 30, (1, 0.05, 0.02), size=0.1, name="beaconL")
    return objs


def creature_face(name="creature", scale=1.0, loc=(0, 0, 0), grin=1.0):
    """Cara demacrada: craneo alargado, cuencas profundas, sonrisa demasiado ancha."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=72, radius=1.0)
    eyes = [Vector((0.33, -0.83, 0.2)), Vector((-0.33, -0.83, 0.2))]
    cheeks = [Vector((0.5, -0.62, -0.22)), Vector((-0.5, -0.62, -0.22))]
    for v in bm.verts:
        p = v.co.copy()
        n = p.normalized()
        x, y, z = p
        # alargado y mandibula estrecha
        sx = 0.78 * (1 - 0.35 * max(0.0, -z - 0.2))
        q = Vector((x * sx, y * 0.86, z * 1.18))
        front = max(0.0, -y)
        for e in eyes:
            d = (p - e).length
            if d < 0.36:
                q -= n * 0.3 * (1 - smooth(d / 0.36))
            # arco superciliar
            bd = (p - (e + Vector((0, 0, 0.2)))).length
            if bd < 0.25:
                q += n * 0.06 * (1 - smooth(bd / 0.25))
        for c in cheeks:
            d = (p - c).length
            if d < 0.35:
                q -= n * 0.12 * (1 - smooth(d / 0.35))
        # nariz: casi inexistente, dos ranuras
        for sx_ in (0.06, -0.06):
            d = (p - Vector((sx_, -1.0, -0.06))).length
            if d < 0.07:
                q -= n * 0.06 * (1 - d / 0.07)
        # sonrisa: curva que sube hacia las mejillas
        if front > 0.25 and abs(x) < 0.78:
            zm = -0.44 + 0.42 * (x * x) * grin
            d = abs(z - zm)
            w = 0.035 + 0.04 * (1 - abs(x) / 0.78)
            if d < w:
                q -= n * 0.22 * (1 - smooth(d / w)) * smooth((0.78 - abs(x)) / 0.1)
        v.co = q
    bm.to_mesh(me)
    bm.free()
    ob = link_obj(bpy.data.objects.new(name, me))
    ob.data.materials.append(mat_skin())
    subsurf(ob, 1)
    ob.scale = (scale, scale, scale)
    ob.location = loc
    root = empty(name + "_root", loc)
    ob.location = (0, 0, 0)
    ob.parent = root
    black = principled("eyeblack", base=(0.0, 0.0, 0.0), rough=0.05, coat=1.0)
    for e in eyes:
        eb = prim("sphere", loc=(0, 0, 0), scale=(0.17, 0.12, 0.15), mat=black)
        eb.location = (e.x * 0.78 * 0.95, e.y * 0.86 + 0.13, e.z * 1.18)
        shade_smooth(eb)
        eb.parent = ob
    # interior de la boca + dientes
    dark = principled("mouth", base=(0.02, 0.0, 0.0), rough=0.6)
    teeth = principled("teeth", base=(0.75, 0.68, 0.5), rough=0.3, sss=0.2)
    mo = prim("sphere", loc=(0, -0.62, -0.42 * 1.18), scale=(0.55, 0.2, 0.09), mat=dark)
    mo.parent = ob
    for i in range(-11, 12):
        x = i * 0.055
        zm = (-0.44 + 0.42 * x * x * grin) * 1.18
        yy = -math.sqrt(max(0.0, 1 - x * x / 0.62 - (zm / 1.18) ** 2)) * 0.86 + 0.05
        for sgn in (1, -1):
            t = prim("sphere", loc=(x * 0.78, yy, zm + sgn * 0.028), scale=(0.022, 0.02, 0.035), mat=teeth,
                     segments=10, ring_count=6)
            t.parent = ob
    return root, ob


def figure(name, coat, seated=True, hood_face=None, height=1.0):
    """Figura humana con parka y capucha con borde de piel (silueta limpia, subdividida)."""
    root = empty(name)
    hz = 0.0 if seated else 0.36
    # torso: cilindro deformado (hombros anchos, cintura) + subdivision
    torso = prim("cyl", loc=(0, 0, 0.98 + hz), scale=(0.25, 0.17, 0.36), mat=coat, vertices=24)
    me = torso.data
    for v in me.vertices:
        z = v.co.z
        k = 1.0 + 0.32 * smooth((z + 0.2) / 1.0) - 0.08 * smooth((0.2 - z) / 0.8)
        v.co.x *= k
        v.co.y *= 1.0 + 0.15 * smooth((z + 0.4) / 1.2)
        if z > 0.9:
            v.co.x *= 0.55
            v.co.y *= 0.7
    subsurf(torso, 2)
    torso.parent = root
    # hombros redondeados
    for sx in (1, -1):
        sh = prim("sphere", loc=(0.26 * sx, 0, 1.27 + hz), scale=(0.12, 0.13, 0.11), mat=coat)
        shade_smooth(sh)
        sh.parent = root
    # capucha
    hood = prim("sphere", loc=(0, 0.03, 1.55 + hz), scale=(0.15, 0.165, 0.175), mat=coat)
    subsurf(hood, 1)
    hood.parent = root
    fur = mat_fabric((0.32, 0.27, 0.22), "fur")
    get_bsdf(fur).inputs["Roughness"].default_value = 1.0
    add_bump(fur.node_tree, get_bsdf(fur), scale=400, strength=0.8, detail=2)
    rim = prim("torus", loc=(0, -0.125, 1.53 + hz), rot=(math.pi / 2 + 0.12, 0, 0), mat=fur,
               major_radius=0.115, minor_radius=0.035, major_segments=40, minor_segments=12)
    rim.scale = (0.95, 1.2, 1.0)
    shade_smooth(rim)
    rim.parent = root
    void = principled("void", base=(0.0, 0.0, 0.0), rough=1.0)
    face = prim("sphere", loc=(0, -0.085, 1.52 + hz), scale=(0.1, 0.07, 0.13), mat=void)
    face.parent = root
    collar = prim("cyl", loc=(0, 0.0, 1.37 + hz), scale=(0.13, 0.12, 0.06), mat=coat)
    subsurf(collar, 1)
    collar.parent = root
    arms = []
    for s_ in (1, -1):
        piv = empty(f"{name}_sh{s_}", (0.3 * s_, 0, 1.27 + hz))
        piv.parent = root
        up = prim("cyl", loc=(0, 0, -0.17), scale=(0.075, 0.075, 0.18), mat=coat)
        subsurf(up, 1)
        up.parent = piv
        elb = empty(f"{name}_el{s_}", (0, 0, -0.34))
        elb.parent = piv
        lo = prim("cyl", loc=(0, 0, -0.15), scale=(0.065, 0.065, 0.16), mat=coat)
        subsurf(lo, 1)
        lo.parent = elb
        glove = prim("sphere", loc=(0, 0, -0.33), scale=(0.05, 0.045, 0.07), mat=principled("glove", base=(0.03, 0.03, 0.03), rough=0.6))
        glove.parent = elb
        arms.append(piv)
    if seated:
        for s_ in (1, -1):
            th = prim("cyl", loc=(0.12 * s_, -0.22, 0.56), rot=(math.pi / 2, 0, 0), scale=(0.09, 0.09, 0.24), mat=coat)
            subsurf(th, 1)
            th.parent = root
            sh_ = prim("cyl", loc=(0.12 * s_, -0.45, 0.28), scale=(0.075, 0.075, 0.27), mat=coat)
            subsurf(sh_, 1)
            sh_.parent = root
    else:
        hips = prim("cyl", loc=(0, 0, 0.82), scale=(0.24, 0.16, 0.14), mat=coat)
        subsurf(hips, 2)
        hips.parent = root
        for a in arms:
            a.location.x *= 0.88
            a.rotation_euler = (0, math.radians(6 if a.location.x > 0 else -6), 0)
        for s_ in (1, -1):
            leg = prim("cyl", loc=(0.11 * s_, 0, 0.47), scale=(0.1, 0.1, 0.47), mat=coat)
            subsurf(leg, 1)
            leg.parent = root
            boot = prim("sphere", loc=(0.12 * s_, -0.05, 0.05), scale=(0.08, 0.14, 0.06), mat=principled("boot", base=(0.03, 0.03, 0.03)))
            boot.parent = root
    root.scale = (height, height, height)
    return root, arms, face


# =============================================================================
# interior de la estacion (set comun)
# =============================================================================
def pose_desk(arms):
    for a in arms:
        a.rotation_euler = (math.radians(-35), 0, math.radians(-8 if a.location.x > 0 else 8))
        for ch in a.children:
            if ch.type == "EMPTY":
                ch.rotation_euler = (math.radians(-60), 0, 0)


def interior(night=True, bulb=True, window_frost=True, hand=False):
    """Habitacion: x de -3 a 3, y de -2.5 a 2.5, z de 0 a 2.6. Escritorio contra la pared +Y.
    Ventana en la pared -X. Puerta (hueco oscuro) en la pared -Y."""
    o = {}
    wallm = mat_frost_wall()
    prim("plane", loc=(0, 0, 0), scale=(3, 2.5, 1), mat=mat_wood(), name="floor")
    prim("plane", loc=(0, 0, 2.6), scale=(3, 2.5, 1), rot=(math.pi, 0, 0), mat=wallm)
    prim("plane", loc=(0, 2.5, 1.3), scale=(3, 1.3, 1), rot=(math.pi / 2, 0, 0), mat=wallm, name="wallN")
    prim("plane", loc=(3, 0, 1.3), scale=(1.3, 2.5, 1), rot=(0, -math.pi / 2, 0), mat=wallm)
    # pared -X con hueco de ventana (4 piezas)
    wx = -3.0
    for (yc, zc, sy, sz) in [(-1.7, 1.3, 0.8, 1.3), (1.7, 1.3, 0.8, 1.3), (0, 0.45, 0.9, 0.45), (0, 2.25, 0.9, 0.35)]:
        prim("plane", loc=(wx, yc, zc), scale=(sz, sy, 1), rot=(0, math.pi / 2, 0), mat=wallm)
    glass = mat_frost_glass(hand=hand)
    o["glass_mat"] = glass
    g = prim("plane", loc=(wx + 0.02, 0, 1.4), scale=(0.5, 0.9, 1), rot=(0, math.pi / 2, 0), mat=glass, name="glass")
    o["glass"] = g
    frame = principled("wframe", base=(0.08, 0.08, 0.08), rough=0.4, metal=0.7)
    for (yc, zc, sy, sz) in [(0, 0.88, 0.95, 0.04), (0, 1.92, 0.95, 0.04), (-0.92, 1.4, 0.04, 0.55), (0.92, 1.4, 0.04, 0.55), (0, 1.4, 0.025, 0.5)]:
        prim("cube", loc=(wx + 0.05, yc, zc), scale=(0.05, sy, sz), mat=frame)
    # pared -Y con puerta (hueco oscuro)
    wy = -2.5
    for (xc, zc, sx, sz) in [(-1.8, 1.3, 1.2, 1.3), (1.9, 1.3, 1.1, 1.3), (0.15, 2.4, 0.75, 0.2)]:
        prim("plane", loc=(xc, wy, zc), scale=(sx, sz, 1), rot=(-math.pi / 2, 0, 0), mat=wallm)
    voidm = principled("doorvoid", base=(0.0, 0.0, 0.0), rough=1.0)
    o["doorway"] = prim("plane", loc=(0.15, wy - 1.2, 1.1), scale=(0.9, 1.3, 1), rot=(-math.pi / 2, 0, 0), mat=voidm)
    for xc in (-0.6, 0.9):
        prim("cube", loc=(xc, wy, 1.1), scale=(0.05, 0.06, 1.1), mat=frame)
    # escritorio
    wood = mat_wood()
    prim("cube", loc=(0.3, 1.9, 0.76), scale=(1.4, 0.5, 0.03), mat=wood, name="desk")
    for xx in (-1.0, 1.6):
        prim("cube", loc=(xx, 1.9, 0.38), scale=(0.04, 0.45, 0.38), mat=wood)
    # radio de onda corta
    case = principled("radiocase", base=(0.12, 0.1, 0.08), rough=0.35, metal=0.3)
    prim("cube", loc=(0.3, 2.12, 1.02), scale=(0.42, 0.22, 0.23), mat=case, name="radio")
    dialm = mat_emit((0.35, 1.0, 0.45), 0.0, "dial")
    dn = dialm.node_tree
    wv = N(dn, "ShaderNodeTexWave")
    wv.inputs["Scale"].default_value = 18.0
    wv.inputs["Distortion"].default_value = 0.0
    tcd = N(dn, "ShaderNodeTexCoord")
    L(dn, tcd.outputs["Object"], wv.inputs["Vector"])
    rmp = N(dn, "ShaderNodeValToRGB")
    rmp.color_ramp.elements[0].position = 0.75
    rmp.color_ramp.elements[0].color = (0.2, 0.55, 0.25, 1)
    rmp.color_ramp.elements[1].position = 0.85
    rmp.color_ramp.elements[1].color = (0.02, 0.06, 0.02, 1)
    L(dn, wv.outputs["Fac"], rmp.inputs["Fac"])
    L(dn, rmp.outputs["Color"], emit_node(dialm).inputs["Color"])
    o["dial_mat"] = dialm
    prim("cube", loc=(0.18, 1.895, 1.1), scale=(0.2, 0.01, 0.06), mat=dialm)
    needle = prim("cube", loc=(0.05, 1.885, 1.1), scale=(0.004, 0.004, 0.055), mat=principled("needle", base=(0.9, 0.1, 0.05), rough=0.3))
    o["needle"] = needle
    grill = principled("grill", base=(0.03, 0.03, 0.03), rough=0.7, metal=0.4)
    gt, _ = add_bump(grill.node_tree, get_bsdf(grill), scale=60, strength=1.0, kind="wave")
    sp = prim("cyl", loc=(0.55, 1.895, 1.02), scale=(0.11, 0.11, 0.01), rot=(math.pi / 2, 0, 0), mat=grill, name="speaker")
    o["speaker"] = sp
    knob = principled("knob", base=(0.6, 0.55, 0.45), rough=0.25, metal=1.0)
    for i, x in enumerate((0.0, 0.18, 0.36)):
        prim("cyl", loc=(x, 1.88, 0.9), scale=(0.025, 0.025, 0.02), rot=(math.pi / 2, 0, 0), mat=knob)
    o["radio_light"] = light("POINT", (0.18, 1.75, 1.1), 0.0, (0.35, 1.0, 0.45), size=0.05, name="radioL")
    # impresora de teletipo
    prim("cube", loc=(-0.75, 2.05, 0.88), scale=(0.28, 0.25, 0.1), mat=case, name="printer")
    paper = prim("plane", loc=(-0.75, 1.92, 0.98), scale=(0.2, 0.15, 1), rot=(math.radians(80), 0, 0), mat=mat_paper(), name="paper")
    o["paper"] = paper
    # grabadora de carrete
    prim("cube", loc=(1.35, 2.0, 0.84), scale=(0.3, 0.22, 0.05), mat=case, name="taperec")
    reelm = principled("reel", base=(0.55, 0.55, 0.58), rough=0.2, metal=1.0)
    tapem = principled("tape", base=(0.03, 0.018, 0.01), rough=0.25)
    reels = []
    for x in (1.2, 1.5):
        r = empty("reel", (x, 2.0, 0.91))
        disc = prim("cyl", loc=(0, 0, 0), scale=(0.11, 0.11, 0.006), mat=reelm, vertices=48)
        disc.parent = r
        tp = prim("cyl", loc=(0, 0, 0.008), scale=(0.075, 0.075, 0.006), mat=tapem, vertices=48)
        tp.parent = r
        for k in range(3):
            a = k * 2 * math.pi / 3
            h = prim("cyl", loc=(math.cos(a) * 0.055, math.sin(a) * 0.055, 0.016), scale=(0.022, 0.022, 0.004), mat=principled("hole", base=(0, 0, 0)))
            h.parent = r
        reels.append(r)
    o["reels"] = reels
    # bitacora abierta
    prim("cube", loc=(0.2, 1.62, 0.8), scale=(0.22, 0.15, 0.01), mat=principled("cover", base=(0.15, 0.05, 0.03)))
    prim("plane", loc=(0.2, 1.62, 0.812), scale=(0.21, 0.145, 1), mat=mat_paper())
    # silla
    chair = principled("chair", base=(0.1, 0.1, 0.11), rough=0.4, metal=0.6)
    prim("cube", loc=(0.3, 0.95, 0.48), scale=(0.25, 0.25, 0.03), mat=chair, name="seat")
    prim("cube", loc=(0.3, 0.72, 0.8), scale=(0.25, 0.03, 0.3), mat=chair)
    # bombilla colgante
    if bulb:
        piv = empty("bulbpivot", (0.2, 0.9, 2.6))
        cord = prim("cyl", loc=(0, 0, -0.35), scale=(0.006, 0.006, 0.35), mat=principled("cord", base=(0.02, 0.02, 0.02)))
        cord.parent = piv
        bm = mat_emit((1.0, 0.62, 0.3), 30.0, "bulb")
        b = prim("sphere", loc=(0, 0, -0.75), scale=(0.045, 0.045, 0.06), mat=bm)
        b.parent = piv
        bl = light("POINT", (0, 0, 0), 60.0, (1.0, 0.62, 0.32), size=0.04, name="bulbL")
        bl.parent = piv
        bl.location = (0, 0, -0.8)
        o.update(bulb_piv=piv, bulb_mat=bm, bulb_light=bl)
    # exterior visto por la ventana: cielo nocturno + luz de luna fria
    sky = mat_emit((0.03, 0.06, 0.13) if night else (0.7, 0.8, 1.0), 0.35 if night else 2.5, "outside")
    o["outside"] = prim("plane", loc=(-6, 0, 1.4), scale=(4, 4, 1), rot=(0, math.pi / 2, 0), mat=sky)
    o["moon"] = light("AREA", (-4.5, 0, 1.6), 6 if night else 120, (0.5, 0.65, 1.0) if night else (0.85, 0.92, 1.0),
                      size=1.8, target=(1, 0, 0.6), name="moonwin")
    world_color((0.005, 0.007, 0.012), 1.0)
    return o


def breath_puff(loc, scale=0.25, name="breath"):
    m = mat_breath()
    ob = prim("cube", loc=loc, scale=(scale, scale, scale), mat=m, name=name)
    return ob, m.node_tree.nodes["dens"]


def breath_cycle(t, period=3.2, offset=0.0):
    """0..1 intensidad de una exhalacion."""
    ph = ((t + offset) % period) / period
    if ph < 0.35:
        return smooth(ph / 0.12) * (1 - smooth((ph - 0.12) / 0.23))
    return 0.0


def flicker(t, seed=0.0, depth=0.5, rate=13.0):
    n = noise.noise(Vector((t * rate, seed, 0.5)))
    return 1.0 - depth * clamp(-n * 2.5)


# =============================================================================
# tomas
# =============================================================================
SHOTS = {}


def shot(idx, dur):
    def deco(fn):
        SHOTS[idx] = (dur, fn)
        return fn
    return deco


@shot(1, 10.0)
def s01_aerial():
    sc = reset_scene()
    world_color((0.01, 0.015, 0.03), 1.0)
    terrain(flat_r=25)
    st = station_exterior(win_strength=60)
    world_color((0.03, 0.045, 0.09), 1.0)
    world_color((0.012, 0.018, 0.04), 1.0)
    sun = light("SUN", (0, 0, 50), 0.55, (0.55, 0.65, 1.0), size=2, name="moon")
    sun.rotation_euler = (math.radians(62), 0, math.radians(-35))
    sm = snow_mat()
    snow_big = Particles(9000, (-60, -60, -2), (60, 60, 60), (6.0, 2.0, -3.5), 0.05, sm, seed=2, turb=1.5)
    cam = camera(lens=28, loc=(-60, -120, 55), target=(0, 0, 2))

    def anim(t):
        u = ease(t / 10.0)
        p = vlerp((-34, -150, 40), (-9, -26, 6.5), u)
        cam.location = p + shake(t, 0.25, 2.0)
        look_at(cam, vlerp((0, 120, 30), (-1.5, 0, 2.6), ease(t / 8.5)))
        snow_big.lo[:] = (p.x - 35, p.y - 10, p.z - 30)
        snow_big.hi[:] = (p.x + 35, p.y + 60, p.z + 25)
        snow_big.size = snow_big.hi - snow_big.lo
        snow_big.update(t)
        blink = 1.0 if (t % 1.6) < 0.5 else 0.05
        emit_node(st["beacon"]).inputs["Strength"].default_value = 60 * blink
        st["beacon_light"].data.energy = 40 * blink
        emit_node(st["win_mat"]).inputs["Strength"].default_value = 60 * flicker(t, 3.0, 0.3, 7)
    return anim


@shot(2, 10.0)
def s02_interior():
    reset_scene()
    o = interior()
    coat = mat_fabric((0.32, 0.07, 0.04))
    fig, arms, _ = figure("man", coat, seated=True)
    fig.location = (0.3, 0.95, 0.0)
    fig.rotation_euler = (0, 0, math.pi)
    pose_desk(arms)
    sm = snow_mat()
    snow = Particles(1500, (-9, -3, -1), (-3.3, 3, 4), (0.0, 1.8, -1.6), 0.012, sm, seed=4, turb=0.4)
    dust = Particles(600, (-2, -1, 0.5), (2, 2.4, 2.5), (0.02, 0.0, -0.01), 0.0025,
                     principled("dust", base=(1, 0.9, 0.8), rough=0.6), seed=5, turb=0.05)
    cam = camera(lens=30, loc=(2.6, -2.1, 1.75), target=(0.2, 1.6, 1.0), fstop=2.8, focus=3.2)

    def anim(t):
        u = ease(t / 10)
        cam.location = vlerp((2.6, -2.1, 1.75), (1.7, -1.0, 1.55), u) + shake(t, 0.01, 1.5)
        look_at(cam, vlerp((0.0, 1.7, 1.0), (0.25, 1.7, 1.05), u))
        cam.data.dof.focus_distance = (cam.location - Vector((0.3, 1.0, 1.4))).length
        o["bulb_piv"].rotation_euler = (math.radians(9) * math.sin(t * 1.9), math.radians(5) * math.sin(t * 1.3 + 1), 0)
        f = flicker(t, 1.0, 0.25)
        o["bulb_light"].data.energy = 60 * f
        emit_node(o["bulb_mat"]).inputs["Strength"].default_value = 30 * f
        arms[0].rotation_euler = (math.radians(-35 + 3 * math.sin(t * 5)), 0, math.radians(-8 + 3 * math.sin(t * 3)))
        snow.update(t)
        dust.update(t)
    return anim


@shot(3, 11.0)
def s03_radio():
    reset_scene()
    o = interior()
    o["bulb_light"].data.energy = 18
    dust = Particles(900, (-0.6, 1.3, 0.85), (1.2, 1.95, 1.5), (0.01, 0.0, -0.006), 0.0018,
                     principled("dust", base=(1, 0.95, 0.9), rough=0.6), seed=7, turb=0.03)
    cam = camera(lens=45, loc=(0.95, 0.9, 1.25), target=(0.25, 1.9, 1.06), fstop=2.0, focus=1.0)

    def anim(t):
        u = ease(t / 11)
        cam.location = vlerp((1.0, 0.85, 1.28), (0.6, 1.2, 1.16), u) + shake(t, 0.004, 1.2)
        look_at(cam, (0.3, 1.9, 1.05))
        cam.data.dof.focus_distance = (cam.location - Vector((0.18, 1.89, 1.1))).length
        on = smooth((t - 6.0) / 0.4) * flicker(t, 2.0, 0.6 * (1 - smooth((t - 7.5) / 2)), 20)
        emit_node(o["dial_mat"]).inputs["Strength"].default_value = 2.2 * on
        o["radio_light"].data.energy = 5 * on
        drift = math.sin(t * 0.9) * 0.02 + noise.noise(Vector((t * 2, 0, 0))) * 0.03
        o["needle"].location.x = 0.05 + 0.12 * smooth((t - 6.0) / 3.0) + drift * on
        o["bulb_piv"].rotation_euler = (math.radians(5) * math.sin(t * 1.5), 0, 0)
        dust.update(t)
    return anim


@shot(4, 13.0)
def s04_voice():
    reset_scene()
    o = interior()
    o["bulb_light"].data.energy = 10
    emit_node(o["bulb_mat"]).inputs["Strength"].default_value = 6
    coat = mat_fabric((0.32, 0.07, 0.04))
    fig, arms, _ = figure("man", coat, seated=True)
    fig.location = (0.3, 0.95, 0.0)
    fig.rotation_euler = (0, 0, math.pi)
    pose_desk(arms)
    br, dens = breath_puff((0.3, 1.2, 1.5), 0.2)
    env = AUDIO_ENV.get("creature1", [])
    cam = camera(lens=38, loc=(0.6, 1.65, 1.05), target=(0.55, 1.9, 1.02), fstop=2.2, focus=0.3)

    def anim(t):
        a = 0.0
        if env and t < len(env) / 50.0 + 0.5:
            i = int((t - 0.5) * 50)
            a = env[i] if 0 <= i < len(env) else 0.0
        on = 0.6 + 2.5 * a
        emit_node(o["dial_mat"]).inputs["Strength"].default_value = 2.2 * on
        o["radio_light"].data.energy = 7 * on
        o["speaker"].scale = (0.11, 0.11, 0.01 + 0.01 * a)
        # dolly: del parlante hacia atras, la camara gira para revelar la figura de frente
        u = ease((t - 3.5) / 7.5)
        p1 = Vector((0.8, 1.3, 1.12))
        p2 = Vector((0.85, 1.82, 1.62))
        cam.location = p1.lerp(p2, u) + shake(t, 0.004, 1.5)
        tgt = vlerp((0.55, 1.9, 1.02), (0.3, 0.95, 1.48), u)
        look_at(cam, tgt)
        cam.data.dof.focus_distance = (cam.location - tgt).length
        dens.outputs[0].default_value = 12.0 * breath_cycle(t, 2.4, 0.3) * smooth((t - 4) / 2)
        br.scale = Vector((0.2, 0.2, 0.2)) * (1 + 0.4 * ((t % 2.4) / 2.4))
        br.location = (0.3, 1.12 + 0.2 * ((t + 0.3) % 2.4) / 2.4, 1.5)
    return anim


@shot(5, 9.0)
def s05_printer():
    reset_scene()
    o = interior()
    o["bulb_light"].data.energy = 12
    emit_node(o["dial_mat"]).inputs["Strength"].default_value = 5
    o["radio_light"].data.energy = 4
    paper = o["paper"]
    font = bpy.data.fonts.load(FONT_MONO)
    cu = bpy.data.curves.new("ptxt", "FONT")
    cu.body = "SEÑAL RECIBIDA  03:00\nFECHA: 01-NOV-1987\n...AYUDA...\nESTÁ ADENTRO"
    cu.font = font
    cu.size = 0.032
    cu.space_line = 1.3
    cu.align_x = "CENTER"
    txt = link_obj(bpy.data.objects.new("ptxt", cu))
    txt.data.materials.append(principled("ink", base=(0.02, 0.02, 0.03), rough=0.7))
    txt.parent = paper
    txt.scale = (1 / 0.2, 1 / 0.15, 1)
    txt.location = (0, 0.25, 0.002)
    spot = light("SPOT", (-0.4, 1.3, 1.6), 25, (1.0, 0.7, 0.45), size=0.05, target=(-0.75, 1.95, 1.0), spot=35, name="pspot")
    cam = camera(lens=45, loc=(-0.55, 1.2, 1.25), target=(-0.75, 1.92, 1.05), fstop=2.4, focus=0.8)

    def anim(t):
        u = smooth(t / 8.0)
        paper.location = (-0.75 + 0.004 * math.sin(t * 40) * (1 - u), 1.92 - 0.02 * u, 0.98 + 0.14 * u)
        paper.scale = (0.2, 0.15 + 0.12 * u, 1)
        txt.scale = (1 / 0.2, 1 / paper.scale.y, 1)
        cam.location = vlerp((-0.45, 1.15, 1.3), (-0.6, 1.4, 1.22), ease(t / 9)) + shake(t, 0.003, 1.0)
        tgt = Vector(paper.location) + Vector((0, 0, 0.05))
        look_at(cam, tgt)
        cam.data.dof.focus_distance = (cam.location - tgt).length
        o["bulb_piv"].rotation_euler = (math.radians(4) * math.sin(t * 1.5), 0, 0)
    return anim


def footprint_ground():
    """Suelo de nieve con huellas que llegan a la puerta y ninguna que se aleje."""
    ob = prim("grid", loc=(1.8, -9, 0), x_subdivisions=360, y_subdivisions=360, size=14, mat=mat_snow(), name="snowground")
    me = ob.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    steps = []
    for k in range(28):
        y = -6.6 + k * 0.42
        x = 0.0 + 0.13 * (1 if k % 2 else -1) + 0.15 * math.sin(k * 0.4)
        steps.append((x, y))
    for i in range(len(co)):
        x, y = co[i, 0], co[i, 1]
        h = noise.noise(Vector((x * 0.7, y * 0.7, 0))) * 0.06 + noise.noise(Vector((x * 4, y * 4, 1))) * 0.012
        for (fx, fy) in steps:
            dx, dy = (x - fx) / 0.07, (y - fy) / 0.15
            r = dx * dx + dy * dy
            if r < 1.6:
                h -= 0.09 * (1 - smooth(r / 1.0)) - 0.02 * smooth((r - 1.0) / 0.6) * (1 - smooth((r - 1.3) / 0.3))
        co[i, 2] = h
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    shade_smooth(ob)
    return ob


@shot(6, 12.0)
def s06_footprints():
    reset_scene()
    bpy.context.scene.cycles.volume_step_rate = 8.0
    world_color((0.01, 0.015, 0.03), 1.0)
    st = station_exterior(win_strength=40)
    footprint_ground()
    sun = light("SUN", (0, 0, 50), 0.25, (0.55, 0.65, 1.0), size=3, name="moon")
    sun.rotation_euler = (math.radians(60), 0, math.radians(20))
    prim("cube", loc=(1.8, -9, 3), scale=(14, 14, 5), mat=mat_volume("fog", 0.015, (0.75, 0.82, 1.0), 0.6, noise_scale=0.4))
    sm = snow_mat()
    snow = Particles(5000, (-4, -18, -0.2), (8, 0, 5), (2.0, 1.0, -2.6), 0.012, sm, seed=9, turb=0.6)
    torch = light("SPOT", (1.8, -16, 1.6), 380, (1.0, 0.92, 0.8), size=0.03, target=(1.8, -12, 0), spot=28, blend=0.4, name="torch")
    cam = camera(lens=32, loc=(1.6, -16.5, 1.55), target=(1.8, -10, 0.1), fstop=4.0, focus=4)

    def anim(t):
        u = ease(t / 12)
        cam.location = vlerp((1.45, -17.5, 1.85), (1.7, -7.5, 1.7), u) + shake(t, 0.03, 2.4)
        tgt = vlerp((1.8, -12.0, 0.0), (1.8, -3.0, 1.1), smooth((t - 1) / 10))
        look_at(cam, tgt)
        cam.data.dof.focus_distance = (cam.location - tgt).length
        torch.location = cam.location + Vector((0.25, 0, -0.25))
        sw = Vector((math.sin(t * 0.8) * 0.8, 0, 0)) + shake(t, 0.15, 3.0, 4)
        look_at(torch, tgt + sw)
        snow.update(t)
    return anim


@shot(7, 9.0)
def s07_window():
    reset_scene()
    o = interior(hand=False)
    o["bulb_light"].data.energy = 8
    emit_node(o["bulb_mat"]).inputs["Strength"].default_value = 5
    torch = light("SPOT", (0, 0, 1.5), 220, (1.0, 0.93, 0.82), size=0.02, spot=30, blend=0.5, name="torch")
    sm = snow_mat()
    snow = Particles(1200, (-9, -3, -1), (-3.3, 3, 4), (0.0, 1.5, -1.2), 0.012, sm, seed=4, turb=0.4)
    cam = camera(lens=35, loc=(1.5, 0.3, 1.5), target=(-3, 0, 1.4), fstop=2.8, focus=4.5)

    def anim(t):
        u = ease(t / 9.0)
        cam.location = vlerp((1.5, 0.2, 1.5), (-1.7, 0.0, 1.42), u) + shake(t, 0.006 + 0.01 * u, 6.0)
        look_at(cam, (-3, 0.0, 1.4))
        cam.data.dof.focus_distance = cam.location.x + 3
        torch.location = cam.location + Vector((0.0, 0.2, -0.2))
        look_at(torch, Vector((-3, 0, 1.4)) + shake(t, 0.08, 4.0, 2))
        torch.data.energy = 220 * flicker(t, 5, 0.3, 9)
        # golpe en la ventana (t=4): el vidrio vibra
        k = math.exp(-((t - 4.0) * 6) ** 2) if t > 3.9 else 0
        o["glass"].location.x = -2.98 + 0.004 * k * math.sin(t * 90)
        snow.update(t)
    return anim


@shot(8, 2.5)
def s08_jumpscare():
    reset_scene()
    o = interior(hand=False)
    o["bulb_light"].data.energy = 8
    root, face = creature_face("creature", scale=0.2)
    root.rotation_euler = (0, 0, math.pi / 2)
    torch = light("SPOT", (-1.6, 0.2, 1.3), 260, (1.0, 0.93, 0.82), size=0.02, spot=32, blend=0.5, name="torch")
    look_at(torch, (-3, 0, 1.4))
    rim = light("AREA", (-4.0, 0.0, 2.4), 40, (0.5, 0.65, 1.0), size=0.6, target=(-3.3, 0, 1.4), name="rim")
    key = light("SPOT", (-3.05, 0.5, 1.05), 0, (1.0, 0.93, 0.82), size=0.03, target=(-3.3, 0, 1.5), spot=60, name="facekey")
    o["glass_mat"].node_tree.nodes["frostamt"].inputs["From Min"].default_value = 0.95
    cam = camera(lens=35, loc=(-1.7, 0.0, 1.42), target=(-3, 0, 1.4), fstop=2.8, focus=1.3)

    def anim(t):
        tt = t - 0.25
        hit = smooth(tt / 0.12) if tt > 0 else 0.0
        root.location = Vector((-3.0 - 0.24 - 1.4 * (1 - hit), 0.3, 1.45))
        sh = shake(t, 0.035 * math.exp(-max(0, tt) * 2.5) if tt > 0 else 0.0, 30)
        cam.location = Vector((-1.7 + 0.12 * hit, 0, 1.42)) + sh
        look_at(cam, Vector((-3, 0, 1.42)) + sh * 0.5)
        root.rotation_euler = (0.05 * math.sin(t * 23), 0.0, math.pi / 2 + 0.06 * math.sin(t * 17))
        key.data.energy = 25 * hit
        torch.data.energy = 260 * (1.0 + 2.0 * math.exp(-max(0, tt) * 8) * (tt > 0))
        bpy.context.scene.view_settings.exposure = BASE_EXPOSURE + 0.6 * math.exp(-max(0, tt) * 6) if tt > 0 else BASE_EXPOSURE
    return anim


@shot(9, 12.5)
def s09_melted():
    reset_scene()
    o = interior(hand=True)
    o["bulb_light"].data.energy = 8
    reveal = o["glass_mat"].node_tree.nodes["reveal"]
    torch = light("SPOT", (-1.6, 0.2, 1.3), 200, (1.0, 0.93, 0.82), size=0.02, spot=30, blend=0.5, name="torch")
    cam = camera(lens=40, loc=(-2.3, 0.0, 1.42), target=(-3, 0, 1.4), fstop=2.8, focus=0.7)

    def anim(t):
        reveal.outputs[0].default_value = smooth((t - 1.0) / 5.0)
        u = ease(t / 12.5)
        cam.location = vlerp((-2.35, 0.05, 1.42), (-1.1, 0.4, 1.5), u) + shake(t, 0.005, 2.0)
        look_at(cam, (-3, 0.0, 1.4))
        cam.data.dof.focus_distance = (cam.location - Vector((-3, 0, 1.4))).length
        torch.location = cam.location + Vector((0.05, 0.2, -0.15))
        look_at(torch, Vector((-3, 0.0, 1.4)) + shake(t, 0.05, 3.0, 1))
    return anim


@shot(10, 13.0)
def s10_tape():
    reset_scene()
    o = interior()
    o["bulb_light"].data.energy = 30
    emit_node(o["dial_mat"]).inputs["Strength"].default_value = 4
    o["radio_light"].data.energy = 3
    lamp = light("SPOT", (1.0, 1.4, 1.7), 40, (1.0, 0.7, 0.4), size=0.08, target=(1.35, 2.0, 0.9), spot=50, name="desklamp")
    cam = camera(lens=45, loc=(1.6, 1.3, 1.35), target=(1.35, 2.0, 0.9), fstop=2.2, focus=0.9)

    def anim(t):
        sp = -12.0 * smooth(t / 1.5) if t < 6.5 else 4.0
        ang = sum([-12.0 * smooth(k / 24 / 1.5) if k / 24 < 6.5 else 4.0 for k in range(int(t * 24))]) / 24
        for i, r in enumerate(o["reels"]):
            r.rotation_euler = (0, 0, ang * (1.0 if i == 0 else 1.3))
        a = 0.3 + 0.9 * ease(t / 13)
        cam.location = Vector((1.35 + 0.75 * math.sin(a), 2.0 - 0.8 * math.cos(a), 1.45 - 0.15 * ease(t / 13))) + shake(t, 0.003, 1.0)
        look_at(cam, (1.35, 2.0, 0.9))
        o["bulb_piv"].rotation_euler = (math.radians(14) * math.sin(t * 1.4), math.radians(8) * math.sin(t * 0.9), 0)
    return anim


@shot(11, 13.0)
def s11_silhouette():
    reset_scene()
    o = interior()
    o["bulb_light"].data.energy = 35
    coat = mat_fabric((0.32, 0.07, 0.04))
    fig, arms, _ = figure("man", coat, seated=True)
    fig.location = (0.3, 0.95, 0.0)
    fig.rotation_euler = (0, 0, math.pi)
    pose_desk(arms)
    dark = mat_fabric((0.02, 0.02, 0.025), "shadowcoat", sheen=0.0)
    other, oarms, _ = figure("other", dark, seated=False, height=1.18)
    other.location = (0.15, -2.75, 0.0)
    for a in oarms:
        a.rotation_euler = (0, 0, 0)
    emit_node(o["dial_mat"]).inputs["Strength"].default_value = 5
    o["radio_light"].data.energy = 4
    cam = camera(lens=35, loc=(1.6, 2.1, 1.4), target=(0.3, 0.9, 1.3), fstop=2.0, focus=1.8)

    def anim(t):
        a = math.radians(40) + math.radians(110) * ease(t / 13)
        c = Vector((0.3, 1.0, 1.35))
        cam.location = c + Vector((math.sin(a) * 2.3, math.cos(a) * 2.3 - 0.3, 0.25 + 0.1 * math.sin(t * 0.3)))
        look_at(cam, c + Vector((0, 0, -0.05)))
        cam.data.dof.focus_distance = (cam.location - c).length
        # parpadeo de la bombilla con el susurro; tras el segundo apagon la figura ya no esta
        f = 1.0
        for (a0, a1) in ((6.6, 6.95), (9.4, 9.9)):
            if a0 < t < a1:
                f = 0.03
        f *= flicker(t, 8.0, 0.2)
        o["bulb_light"].data.energy = 35 * f
        emit_node(o["bulb_mat"]).inputs["Strength"].default_value = 30 * f
        other.location = (0.15, -2.75, 0.0) if t < 6.95 else ((0.2, -1.9, 0.0) if t < 9.9 else (50, 50, 0))
        o["bulb_piv"].rotation_euler = (math.radians(6) * math.sin(t * 1.4), 0, 0)
    return anim


@shot(12, 11.0)
def s12_breath():
    reset_scene()
    o = interior()
    o["bulb_light"].data.energy = 14
    coat = mat_fabric((0.32, 0.07, 0.04))
    fig, arms, _ = figure("man", coat, seated=True)
    fig.location = (0.3, 0.95, 0.0)
    fig.rotation_euler = (0, 0, math.pi)
    pose_desk(arms)
    b1, d1 = breath_puff((0.3, 1.3, 1.47), 0.16, "b1")
    b2, d2 = breath_puff((0.3, 0.62, 1.6), 0.16, "b2")
    rim = light("SPOT", (0.3, 2.3, 1.9), 30, (0.35, 1.0, 0.5), size=0.1, target=(0.3, 0.9, 1.5), spot=40, name="greenrim")
    cam = camera(lens=38, loc=(1.4, 1.0, 1.6), target=(0.3, 0.95, 1.5), fstop=2.0, focus=1.1)

    def anim(t):
        u = ease(t / 11)
        cam.location = vlerp((1.55, 1.05, 1.62), (1.15, 0.95, 1.56), u) + shake(t, 0.004 + 0.004 * u, 3.0)
        look_at(cam, (0.3, 0.98, 1.5))
        cam.data.dof.focus_distance = (cam.location - Vector((0.3, 0.95, 1.5))).length
        k1 = breath_cycle(t, 2.2, 0.0)
        k2 = breath_cycle(t, 2.2, 0.0) * smooth((t - 3.0) / 2.0)
        d1.outputs[0].default_value = 14.0 * k1
        d2.outputs[0].default_value = 14.0 * k2
        ph = (t % 2.2) / 2.2
        b1.location = (0.3, 1.2 + 0.25 * ph, 1.5)
        b2.location = (0.3 + 0.05 * ph, 0.68 - 0.08 * ph, 1.62)
        o["bulb_light"].data.energy = 14 * flicker(t, 3.0, 0.3 + 0.5 * smooth((t - 8) / 3), 15)
    return anim


@shot(13, 3.0)
def s13_jumpscare():
    reset_scene()
    o = interior()
    coat = mat_fabric((0.02, 0.02, 0.025), "shadowcoat", sheen=0.0)
    other, oarms, oface = figure("other", coat, seated=False, height=1.02)
    oface.hide_render = True
    other.location = (0.35, 0.05, 0.0)
    other.rotation_euler = (0, 0, math.pi)
    for a in oarms:
        a.rotation_euler = (math.radians(-80), 0, 0)
    root, face = creature_face("creature", scale=0.135, grin=1.15)
    root.parent = other
    root.location = (0, -0.12, 1.75)
    face.rotation_euler = (0, 0, 0)
    under = light("SPOT", (0.3, 0.75, 1.0), 14, (0.6, 0.75, 1.0), size=0.05, target=(0.35, 0.2, 1.85), spot=28, name="under")
    cam = camera(lens=24, loc=(0.3, 0.95, 1.45), target=(0.3, 2.0, 1.2), fstop=2.0, focus=0.9)

    def anim(t):
        turn = ease((t - 0.15) / 0.35)
        ang = math.pi * turn
        tgt = Vector((0.3, 0.95, 1.5)) + Vector((math.sin(ang) * 0.6, math.cos(ang), -0.1 + 0.42 * turn))
        lunge = smooth((t - 0.95) / 0.3)
        other.location = Vector((0.35, 0.05 + 0.65 * lunge, 0.0))
        sh = shake(t, 0.02 + 0.06 * lunge, 35)
        cam.location = Vector((0.3, 0.95, 1.45)) + sh
        look_at(cam, tgt + sh)
        cam.data.dof.focus_distance = max(0.15, (cam.location - Vector(other.location) - Vector((0, -0.12, 1.75))).length)
        # bombillas que estallan
        burst = 1.0
        if t > 1.15:
            burst = 25.0 * math.exp(-(t - 1.15) * 20) if t < 1.4 else 0.0
        fl = flicker(t, 7.0, 0.7, 25) if t < 1.15 else 1.0
        o["bulb_light"].data.energy = 45 * burst * fl
        emit_node(o["bulb_mat"]).inputs["Strength"].default_value = 30 * burst * fl
        under.location = (0.3, 0.75, 1.0)
        under.data.energy = 14 * (1.0 if t < 1.4 else 0.0) * fl
        o["moon"].data.energy = 25 if t < 1.4 else 3
        bpy.context.scene.view_settings.exposure = -6.0 if t > 1.9 else BASE_EXPOSURE
    return anim


@shot(14, 14.5)
def s14_rescue():
    reset_scene()
    bpy.context.scene.cycles.volume_step_rate = 8.0
    o = interior(night=False, bulb=False)
    world_color((0.4, 0.5, 0.65), 0.15)
    emit_node(o["dial_mat"]).inputs["Strength"].default_value = 6
    o["radio_light"].data.energy = 5
    # puerta abierta: luz de dia entrando
    o["doorway"].data.materials[0] = mat_emit((0.85, 0.92, 1.0), 3.0, "daydoor")
    light("AREA", (0.15, -4.2, 1.4), 220, (0.85, 0.92, 1.0), size=1.8, target=(0.2, 1, 0.5), name="doorlight")
    suit = mat_fabric((0.95, 0.35, 0.03), "rescue")
    figs = []
    for i, x in enumerate((-0.3, 0.6)):
        f, arms, _ = figure(f"res{i}", suit, seated=False, height=1.0)
        f.location = (x, -3.0, 0)
        figs.append(f)
    prim("cube", loc=(0, 0, 1.3), scale=(3, 2.5, 1.3), mat=mat_volume("haze", 0.025, (0.9, 0.95, 1.0), 0.5))
    cam = camera(lens=30, loc=(1.8, 2.0, 1.5), target=(0.2, -2.0, 1.1), fstop=1.6, focus=1.2)

    def anim(t):
        u = ease(t / 14.5)
        cam.location = vlerp((1.9, 2.15, 1.5), (1.3, 1.4, 1.45), u) + shake(t, 0.004, 1.0)
        look_at(cam, vlerp((0.2, -2.0, 1.1), (0.3, 1.9, 0.95), smooth((t - 6) / 6)))
        cam.data.dof.focus_distance = 1.2 + 0.4 * smooth((t - 6) / 6)
        for i, f in enumerate(figs):
            f.location.y = -3.3 + 0.7 * smooth((t - 1.5 - i * 0.6) / 4.0)
        a = 0.6 + 0.4 * flicker(t, 4.0, 0.6, 6)
        emit_node(o["dial_mat"]).inputs["Strength"].default_value = 6 * a
    return anim


@shot(15, 13.0)
def s15_final():
    reset_scene()
    bpy.context.scene.cycles.volume_step_rate = 8.0
    world_color((0.008, 0.012, 0.025), 1.0)
    st = station_exterior(win_strength=25, hollow=True)
    ground = prim("plane", loc=(0, -10, 0), scale=(30, 30, 1), mat=mat_snow())
    sun = light("SUN", (0, 0, 50), 0.2, (0.55, 0.65, 1.0), size=3, name="moon")
    sun.rotation_euler = (math.radians(60), 0, math.radians(20))
    # figura dentro de la ventana (a contraluz)
    dark = mat_fabric((0.01, 0.01, 0.012), "shadowcoat", sheen=0.0)
    fig, arms, hface = figure("waver", dark, seated=False, height=1.0)
    fig.location = (-2.2, -2.2, 0.35)
    backlight = light("AREA", (-2.2, -1.2, 1.9), 50, (1.0, 0.55, 0.25), size=1.2, target=(-2.2, -4, 1.7), name="backlit")
    root, face = creature_face("creature", scale=0.12, grin=1.2)
    root.parent = fig
    root.location = (0, -0.12, 1.83)
    face.hide_render = True
    for ch in face.children:
        ch.hide_render = True
    facelight = light("SPOT", (-2.2, -4.0, 2.2), 0, (0.8, 0.9, 1.0), size=0.05, target=(-2.2, -2.3, 2.2), spot=20, name="facelight")
    # la ventana deja de ser emisiva: vidrio con escarcha suave para ver la silueta
    st["win"].hide_render = True
    glass = mat_frost_glass()
    glass.node_tree.nodes["frostamt"].inputs["From Min"].default_value = 0.95
    glass.node_tree.nodes["frostamt"].inputs["From Max"].default_value = 1.6
    prim("plane", loc=(-2.2, -3.03, 1.9), scale=(0.75, 0.55, 1), rot=(math.pi / 2, 0, 0), mat=glass)
    sm = snow_mat()
    snow = Particles(4000, (-8, -12, -0.2), (4, -3.2, 5), (1.5, 0.8, -2.2), 0.01, sm, seed=11, turb=0.5)
    prim("cube", loc=(-2, -8, 3), scale=(10, 6, 5), mat=mat_volume("fog", 0.006, (0.75, 0.82, 1.0), 0.6))
    cam = camera(lens=40, loc=(-2.0, -9.0, 1.8), target=(-2.2, -3, 1.9), fstop=2.8, focus=6)

    def anim(t):
        u = ease(t / 13)
        cam.location = vlerp((-1.5, -11.5, 1.7), (-2.1, -6.6, 1.85), u) + shake(t, 0.01, 1.5)
        look_at(cam, (-2.2, -3, 1.85))
        cam.data.dof.focus_distance = (cam.location - Vector((-2.2, -2.3, 1.9))).length
        # saludo lento
        wave = smooth((t - 2.0) / 1.5) * (1 - smooth((t - 8.0) / 1.5))
        arms[0].rotation_euler = (0, math.radians(-150) * wave, math.radians(12) * math.sin(t * 2.2) * wave)
        # destello: la cara aparece un instante (t 9.5-10.3) y sonrie
        show = 9.6 < t < 10.4
        face.hide_render = not show
        for ch in face.children:
            ch.hide_render = not show
        facelight.data.energy = 150 if show else 0
        backlight.data.energy = 50 * flicker(t, 2.0, 0.4, 8) * (0.2 if show else 1.0)
        snow.update(t)
        bpy.context.scene.view_settings.exposure = BASE_EXPOSURE - 5.0 * smooth((t - 11.0) / 2.0)
    return anim


@shot(16, 10.0)
def s16_title():
    reset_scene()
    bpy.context.scene.cycles.volume_step_rate = 8.0
    world_color((0.0, 0.0, 0.0), 1.0)
    font = bpy.data.fonts.load(FONT_TITLE)
    cu = bpy.data.curves.new("title", "FONT")
    cu.body = "ESTACIÓN UMBRA"
    cu.font = font
    cu.size = 0.72
    cu.extrude = 0.08
    cu.bevel_depth = 0.012
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    title = link_obj(bpy.data.objects.new("title", cu))
    title.rotation_euler = (math.pi / 2, 0, 0)
    ice = principled("ice", base=(0.75, 0.85, 1.0), rough=0.15, trans=0.6, sss=0.3, sss_rad=(0.4, 0.6, 1.0), coat=0.5)
    add_bump(ice.node_tree, get_bsdf(ice), scale=30, strength=0.4, kind="voronoi")
    title.data.materials.append(ice)
    back = prim("plane", loc=(0, 1.5, 0), scale=(20, 10, 1), rot=(math.pi / 2, 0, 0), mat=principled("bk", base=(0.01, 0.012, 0.02), rough=0.9))
    sweep = light("SPOT", (-6, -3, 2), 1500, (0.6, 0.75, 1.0), size=0.2, target=(0, 0, 0), spot=25, blend=0.6, name="sweep")
    rimL = light("AREA", (0, 0.8, 0.0), 80, (1.0, 0.45, 0.2), size=6, target=(0, -2, 0), name="rim")
    sm = snow_mat()
    snow = Particles(2500, (-8, -4, -4), (8, 1.2, 4), (0.8, 0.2, -0.9), 0.012, sm, seed=13, turb=0.3)
    prim("cube", loc=(0, -1, 0), scale=(10, 3, 5), mat=mat_volume("fog", 0.02, (0.75, 0.82, 1.0), 0.7))
    cam = camera(lens=40, loc=(0, -9, 0.2), target=(0, 0, 0), fstop=4, focus=9)

    def anim(t):
        u = ease(t / 10)
        cam.location = Vector((0.3 * (1 - u), -9.5 + 1.3 * u, 0.25 - 0.15 * u))
        look_at(cam, (0, 0, 0))
        cam.data.dof.focus_distance = cam.location.length
        sweep.location = Vector((-7 + 14 * smooth((t - 1) / 6), -3, 2.5))
        look_at(sweep, (sweep.location.x * 0.3, 0, 0))
        f = smooth(t / 2.0) * (1 - smooth((t - 8.5) / 1.5))
        sweep.data.energy = 1500 * f
        rimL.data.energy = 80 * f
        snow.update(t)
    return anim


# =============================================================================
# envolvente de audio (para sincronizar luces con la voz de la radio)
# =============================================================================
AUDIO_ENV = {}


def load_env():
    p = os.path.join(HERE, "build", "env_creature1.npy")
    if os.path.exists(p):
        AUDIO_ENV["creature1"] = list(np.load(p))


def make_handprint():
    """Mascara PNG de una mano (palma + 5 dedos) para la escarcha derretida."""
    if os.path.exists(HAND_PNG):
        return
    from PIL import Image, ImageDraw, ImageFilter
    S = 512
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    cx, cy = 256, 300
    d.ellipse((cx - 70, cy - 60, cx + 70, cy + 90), fill=255)
    fingers = [(-60, -40, -95, -165), (-25, -60, -35, -215), (12, -62, 15, -225), (48, -55, 62, -200), (78, 10, 140, -40)]
    for (x0, y0, x1, y1) in fingers:
        steps = 30
        for k in range(steps + 1):
            u = k / steps
            x = cx + x0 + (x1 - x0) * u
            y = cy + y0 + (y1 - y0) * u
            r = 22 - 4 * u
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    # gotas
    for (x, y, l) in [(200, 380, 90), (300, 390, 70), (250, 395, 110)]:
        d.line((x, y, x, y + l), fill=200, width=8)
    im = im.filter(ImageFilter.GaussianBlur(4))
    os.makedirs(os.path.dirname(HAND_PNG), exist_ok=True)
    # el plano de la ventana tiene el UV rotado: transponer para que la mano quede vertical
    im.transpose(Image.Transpose.ROTATE_90).save(HAND_PNG)


# =============================================================================
# main
# =============================================================================
def render_shot(idx, still=None, every=1, frames=None):
    dur, fn = SHOTS[idx]
    anim = fn()
    sc = bpy.context.scene
    fps = SHOT_FPS.get(idx, FPS)
    n = int(round(dur * fps))
    outdir = os.path.join(OUT, f"shot{idx:02d}")
    os.makedirs(outdir, exist_ok=True)
    rng = range(0, n, every)
    if frames:
        rng = range(frames[0], min(frames[1], n))
    if still is not None:
        rng = [int(still * fps)]
    t0 = time.time()
    for k, f in enumerate(rng):
        path = os.path.join(outdir, f"f_{f:04d}.png") if still is None else os.path.join(OUT, f"still_{idx:02d}_{still:.2f}.png")
        if still is None and os.path.exists(path):
            continue
        sc.frame_set(f + 1)
        anim(f / fps)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        el = time.time() - t0
        print(f"[shot {idx}] frame {f + 1}/{n}  {el / (k + 1):.1f}s/frame", flush=True)


if __name__ == "__main__":
    argv = sys.argv[1:]
    make_handprint()
    load_env()
    still = None
    every = 1
    frames = None
    if "--still" in argv:
        still = float(argv[argv.index("--still") + 1])
    if "--every" in argv:
        every = int(argv[argv.index("--every") + 1])
    if "--frames" in argv:
        a, b = argv[argv.index("--frames") + 1].split("-")
        frames = (int(a), int(b))
    if "--all" in argv:
        for i in sorted(SHOTS):
            render_shot(i, every=every)
    else:
        idxs = [int(x) for x in argv[argv.index("--shot") + 1].split(",")]
        for i in idxs:
            render_shot(i, still=still, every=every, frames=frames)
