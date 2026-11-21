"""
NEON RUSH — procedural cinematic short for Blender 5.3
=======================================================

Builds the whole scene from code: a rainy cyberpunk megacity, an original
racing-courier drone, flying traffic, neon signage, holograms, eight
cinematic camera shots and a compositor (fog, bloom, chromatic aberration).

Usage (headless):
    blender -b --factory-startup -P build_scene.py -- --out neon_rush.blend

Timeline: 24 fps, frames 0..1487 (62 s) of rendered animation.
"""

import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Quaternion, Matrix, Euler, noise

# ----------------------------------------------------------------------------
# Global settings
# ----------------------------------------------------------------------------
FPS = 24
F_START, F_END = 0, 1487
RNG = random.Random(2087)
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_DISPLAY = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"

NEON = {
    "magenta": (1.00, 0.05, 0.45),
    "cyan":    (0.05, 0.80, 1.00),
    "orange":  (1.00, 0.33, 0.02),
    "violet":  (0.55, 0.12, 1.00),
    "green":   (0.12, 1.00, 0.45),
    "red":     (1.00, 0.03, 0.05),
    "warm":    (1.00, 0.68, 0.38),
    "blue":    (0.10, 0.28, 1.00),
}
NEON_KEYS = list(NEON.keys())

WORDS = ["RAMEN", "HOTEL", "NOVA", "PULSE", "ZEN", "BAR", "OHM", "SYNC", "DATA",
         "CLUB", "LOTUS", "KAIRO", "VOLT", "ECHO", "RYU", "SAKE", "NEXUS", "AURA",
         "TAXI", "LAB", "BYTE", "VIBE", "HALO", "ION", "NEO", "FLUX", "ORBIT",
         "DRIFT", "KOI", "MOTEL", "SUSHI", "CHROME", "GRID", "LUX", "TOKI", "ARC"]


def smoothstep(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def smootherstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * t * (t * (t * 6 - 15) + 10)


def bump(a, b, x):
    """sin^2 window, 0 outside [a,b], 1 at the middle."""
    if x <= a or x >= b:
        return 0.0
    return math.sin(math.pi * (x - a) / (b - a)) ** 2


def lerp(a, b, t):
    return a + (b - a) * t


# ----------------------------------------------------------------------------
# Scene reset
# ----------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "NeonRush"
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = F_START, F_END
    return sc


# ----------------------------------------------------------------------------
# Node helpers
# ----------------------------------------------------------------------------
def sock(node, identifier, out=False):
    coll = node.outputs if out else node.inputs
    for s in coll:
        if s.identifier == identifier:
            return s
    for s in coll:
        if s.name == identifier and not getattr(s, "is_unavailable", False):
            return s
    raise KeyError(f"{node.bl_idname}: socket {identifier}")


class NB:
    """Tiny node-building DSL for shader trees."""

    def __init__(self, nt):
        self.nt = nt

    def new(self, t, **kw):
        n = self.nt.nodes.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def link_or_set(self, s, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, s)
        elif v is not None:
            if isinstance(v, (tuple, list)) and len(v) == 3 and s.type == "RGBA":
                v = (*v, 1.0)
            s.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        m = self.new("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.link_or_set(m.inputs[0], a)
        if b is not None:
            self.link_or_set(m.inputs[1], b)
        if c is not None:
            self.link_or_set(m.inputs[2], c)
        return m.outputs[0]

    def vmath(self, op, a, b=None):
        m = self.new("ShaderNodeVectorMath", operation=op)
        self.link_or_set(m.inputs[0], a)
        if b is not None:
            self.link_or_set(m.inputs[1], b)
        return m.outputs[0] if op not in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else m.outputs[1]

    def mix(self, fac, a, b):
        m = self.new("ShaderNodeMix", data_type="RGBA")
        self.link_or_set(sock(m, "Factor_Float"), fac)
        self.link_or_set(sock(m, "A_Color"), a)
        self.link_or_set(sock(m, "B_Color"), b)
        return sock(m, "Result_Color", out=True)

    def mixf(self, fac, a, b):
        m = self.new("ShaderNodeMix", data_type="FLOAT")
        self.link_or_set(sock(m, "Factor_Float"), fac)
        self.link_or_set(sock(m, "A_Float"), a)
        self.link_or_set(sock(m, "B_Float"), b)
        return sock(m, "Result_Float", out=True)

    def sep(self, v):
        s = self.new("ShaderNodeSeparateXYZ")
        self.link_or_set(s.inputs[0], v)
        return s.outputs

    def comb(self, x, y, z):
        c = self.new("ShaderNodeCombineXYZ")
        self.link_or_set(c.inputs[0], x)
        self.link_or_set(c.inputs[1], y)
        self.link_or_set(c.inputs[2], z)
        return c.outputs[0]

    def ramp(self, fac, stops, interp="LINEAR"):
        r = self.new("ShaderNodeValToRGB")
        r.color_ramp.interpolation = interp
        els = r.color_ramp.elements
        while len(els) > 1:
            els.remove(els[-1])
        els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1)
        for pos, col in stops[1:]:
            e = els.new(pos)
            e.color = (*col, 1)
        self.link_or_set(r.inputs[0], fac)
        return r.outputs[0]

    def time_value(self):
        """A Value node driven by scene time in seconds (simple expression driver)."""
        v = self.new("ShaderNodeValue")
        fc = v.outputs[0].driver_add("default_value")
        fc.driver.type = "SCRIPTED"
        fc.driver.expression = "frame/24"
        return v.outputs[0]


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def set_emission_sampling(m, mode):
    for target in (m, getattr(m, "cycles", None)):
        if target is not None and hasattr(target, "emission_sampling"):
            try:
                target.emission_sampling = mode
            except Exception:
                pass


def emission_material(name, color, strength):
    m, nt, out = new_material(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    m["emit_node"] = e.name
    return m


def principled_material(name, base, rough=0.5, metal=0.0, coat=0.0, emis=None, emis_str=0.0):
    m, nt, out = new_material(name)
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*base, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    p.inputs["Coat Weight"].default_value = coat
    if emis:
        p.inputs["Emission Color"].default_value = (*emis, 1)
        p.inputs["Emission Strength"].default_value = emis_str
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    return m


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
MATS = {}


def build_materials():
    # --- Buildings: procedural windows, storefronts, wet roofs ------------------
    m, nt, out = new_material("Building")
    b = NB(nt)
    geo = b.new("ShaderNodeNewGeometry")
    attr = b.new("ShaderNodeAttribute", attribute_name="rnd", attribute_type="GEOMETRY")
    rnd = attr.outputs["Fac"]
    sattr = b.new("ShaderNodeAttribute", attribute_name="style", attribute_type="GEOMETRY")
    style = sattr.outputs["Fac"]
    px, py, pz = b.sep(geo.outputs["Position"])
    nx, ny, nz = b.sep(geo.outputs["Normal"])
    facade = b.math("LESS_THAN", b.math("ABSOLUTE", nz), 0.5)
    h = b.math("ADD", px, py)
    # facade style parameters (5 styles): grid, ribbon, vertical slits, glass curtain, small apartments
    # R: window pitch/10, G: floor height/10, B: x-mask margin, A: z-mask margin
    prm = b.new("ShaderNodeValToRGB")
    prm.color_ramp.interpolation = "CONSTANT"
    els = prm.color_ramp.elements
    specs = [(0.0, (0.26, 0.36, 0.18, 0.30)), (0.2, (0.60, 0.38, 0.0, 0.32)), (0.4, (0.17, 0.40, 0.36, 0.0)),
             (0.6, (0.80, 0.42, 0.0, 0.0)), (0.8, (0.15, 0.30, 0.20, 0.28))]
    els[0].position, els[0].color = specs[0][0], specs[0][1]
    for pos, col in specs[1:]:
        e = els.new(pos)
        e.color = col
    b.link_or_set(prm.inputs[0], style)
    pr, pg, pb = b.sep(prm.outputs["Color"])
    pa = prm.outputs["Alpha"]
    # R: lit ratio, G: brightness, B: glassiness
    prm2 = b.ramp(style, [(0.0, (0.16, 0.9, 0.0)), (0.2, (0.24, 1.1, 0.0)), (0.4, (0.20, 1.3, 0.2)),
                          (0.6, (0.12, 0.65, 1.0)), (0.8, (0.30, 0.85, 0.0))], "CONSTANT")
    q_ratio, q_bright, q_glass = b.sep(prm2)
    wsize = b.math("MULTIPLY", b.math("MULTIPLY", pr, 10.0), b.math("MULTIPLY_ADD", rnd, 0.3, 0.85))
    fh = b.math("MULTIPLY", pg, 10.0)
    cx = b.math("DIVIDE", h, wsize)
    cz = b.math("DIVIDE", pz, fh)
    fx = b.math("FRACT", cx)
    fz = b.math("FRACT", cz)
    mx = b.math("MULTIPLY", b.math("GREATER_THAN", fx, pb), b.math("LESS_THAN", fx, b.math("SUBTRACT", 1.0, pb)))
    mz = b.math("MULTIPLY", b.math("GREATER_THAN", fz, pa),
                b.math("LESS_THAN", fz, b.math("SUBTRACT", 1.0, b.math("MULTIPLY", pa, 0.6))))
    win = b.math("MULTIPLY", b.math("MULTIPLY", mx, mz), facade)
    win = b.math("MAXIMUM", win, b.math("MULTIPLY", q_glass, facade))      # curtain wall = all glass
    cell = b.comb(b.math("FLOOR", cx), b.math("FLOOR", cz), b.math("MULTIPLY", rnd, 137.0))
    wn = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    b.link_or_set(wn.inputs["Vector"], cell)
    lit_ratio = b.math("MULTIPLY", q_ratio, b.math("MULTIPLY_ADD", rnd, 0.9, 0.6))
    lit = b.math("GREATER_THAN", wn.outputs["Value"], b.math("SUBTRACT", 1.0, lit_ratio))
    lit = b.math("MULTIPLY", lit, b.math("MULTIPLY", b.math("MULTIPLY", mx, mz), facade))
    wn2 = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="4D")
    b.link_or_set(wn2.inputs["Vector"], cell)
    wn2.inputs["W"].default_value = 3.7
    cbias = b.math("MULTIPLY", b.math("FRACT", b.math("MULTIPLY", rnd, 3.3)), 0.45)
    wcol = b.ramp(b.math("MULTIPLY_ADD", wn2.outputs["Value"], 0.55, cbias), [
        (0.00, (1.0, 0.58, 0.28)), (0.30, (1.0, 0.80, 0.58)), (0.52, (0.92, 0.92, 1.0)), (0.66, (0.62, 0.80, 1.0)),
        (0.80, (0.40, 0.95, 1.0)), (0.90, (1.0, 0.25, 0.65)), (0.95, (0.65, 0.35, 1.0))], "CONSTANT")
    # storefront band at street level
    shop = b.math("MULTIPLY", b.math("LESS_THAN", pz, 4.6), facade)
    shop = b.math("MULTIPLY", shop, b.math("GREATER_THAN", pz, 0.4))
    scx = b.math("FLOOR", b.math("DIVIDE", h, 6.5))
    wn3 = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="2D")
    b.link_or_set(wn3.inputs["Vector"], b.comb(scx, b.math("MULTIPLY", rnd, 91.0), 0.0))
    shop_on = b.math("GREATER_THAN", wn3.outputs["Value"], 0.3)
    shop_frac = b.math("FRACT", b.math("DIVIDE", h, 6.5))
    shop_pane = b.math("MULTIPLY", b.math("GREATER_THAN", shop_frac, 0.06), b.math("LESS_THAN", shop_frac, 0.94))
    shop_m = b.math("MULTIPLY", b.math("MULTIPLY", shop, shop_on), shop_pane)
    shop_col = b.ramp(wn3.outputs["Value"], [
        (0.0, (1.0, 0.55, 0.25)), (0.45, (1.0, 0.2, 0.55)), (0.65, (0.2, 0.9, 1.0)),
        (0.82, (1.0, 0.8, 0.5)), (0.92, (0.6, 0.3, 1.0))], "CONSTANT")
    wvar = b.math("MULTIPLY_ADD", wn.outputs["Value"], 1.6, 0.25)
    emis_w = b.math("MULTIPLY", lit, b.math("MULTIPLY", wvar, b.math("MULTIPLY", q_bright, b.math("MULTIPLY_ADD", rnd, 0.8, 0.6))))
    emis_s = b.math("MULTIPLY", shop_m, 1.7)
    emis_strength = b.math("ADD", emis_w, emis_s)
    emis_col = b.mix(shop_m, wcol, shop_col)
    # base surfaces: varied concrete tints / dark glass / wet roof
    nzpos = b.new("ShaderNodeTexNoise")
    b.link_or_set(nzpos.inputs["Vector"], geo.outputs["Position"])
    nzpos.inputs["Scale"].default_value = 0.35
    nzpos.inputs["Detail"].default_value = 1.5
    wall_col = b.ramp(b.math("FRACT", b.math("MULTIPLY", rnd, 7.13)), [
        (0.0, (0.020, 0.020, 0.026)), (0.2, (0.055, 0.045, 0.040)), (0.4, (0.030, 0.038, 0.055)),
        (0.6, (0.070, 0.068, 0.072)), (0.8, (0.012, 0.012, 0.016))], "CONSTANT")
    wall_col = b.mix(b.math("MULTIPLY", nzpos.outputs["Fac"], 0.6), wall_col, (0.01, 0.01, 0.014))
    glass_col = b.mix(q_glass, (0.008, 0.012, 0.02), (0.02, 0.035, 0.06))
    base = b.mix(win, wall_col, glass_col)
    puddle = b.math("GREATER_THAN", nzpos.outputs["Fac"], 0.52)
    roof_rough = b.mixf(puddle, 0.45, 0.04)
    rough = b.mixf(facade, roof_rough, b.mixf(win, 0.55, b.mixf(q_glass, 0.06, 0.03)))
    p = b.new("ShaderNodeBsdfPrincipled")
    b.link_or_set(p.inputs["Base Color"], base)
    b.link_or_set(p.inputs["Roughness"], rough)
    b.link_or_set(p.inputs["Metallic"], b.math("MULTIPLY", q_glass, b.math("MULTIPLY", win, 0.6)))
    b.link_or_set(p.inputs["Emission Color"], emis_col)
    b.link_or_set(p.inputs["Emission Strength"], emis_strength)
    p.inputs["Specular IOR Level"].default_value = 0.6
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    MATS["building"] = m

    # --- Wet street ---------------------------------------------------------------
    m, nt, out = new_material("WetStreet")
    b = NB(nt)
    geo = b.new("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    px, py, pz = b.sep(pos)
    n1 = b.new("ShaderNodeTexNoise")
    b.link_or_set(n1.inputs["Vector"], pos)
    n1.inputs["Scale"].default_value = 0.09
    n1.inputs["Detail"].default_value = 3
    n1.inputs["Roughness"].default_value = 0.6
    puddle = b.math("SMOOTH_MAX", 0.0, b.math("MULTIPLY", b.math("SUBTRACT", n1.outputs["Fac"], 0.47), 12.0), 0.0)
    puddle = b.math("MINIMUM", puddle, 1.0)
    # rain ripples on puddles (animated)
    t = b.time_value()
    rip = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
    b.link_or_set(rip.inputs["Vector"], pos)
    b.link_or_set(rip.inputs["W"], b.math("MULTIPLY", t, 2.5))
    rip.inputs["Scale"].default_value = 3.0
    rip.inputs["Detail"].default_value = 0
    bump_n = b.new("ShaderNodeBump")
    bump_n.inputs["Strength"].default_value = 0.12
    b.link_or_set(bump_n.inputs["Height"], rip.outputs["Fac"])
    # lane markings (avenue only)
    ax = b.math("ABSOLUTE", px)
    lane_d = b.math("ABSOLUTE", b.math("SUBTRACT", b.math("FRACT", b.math("DIVIDE", b.math("ADD", ax, 2.0), 4.0)), 0.5))
    lane = b.math("LESS_THAN", lane_d, 0.025)
    lane = b.math("MULTIPLY", lane, b.math("LESS_THAN", ax, 10.5))
    lane = b.math("MULTIPLY", lane, b.math("GREATER_THAN", ax, 1.0))
    dash = b.math("LESS_THAN", b.math("FRACT", b.math("DIVIDE", py, 12.0)), 0.45)
    lane = b.math("MULTIPLY", lane, dash)
    center = b.math("MULTIPLY", b.math("LESS_THAN", ax, 0.18), b.math("GREATER_THAN", ax, 0.05))
    mark = b.math("MAXIMUM", lane, center)
    asphalt = b.mix(b.math("MULTIPLY", n1.outputs["Fac"], 1.0), (0.012, 0.012, 0.014), (0.03, 0.03, 0.034))
    base = b.mix(mark, asphalt, (0.35, 0.33, 0.28))
    base = b.mix(puddle, base, (0.004, 0.004, 0.006))
    rough = b.mixf(puddle, 0.32, 0.015)
    rough = b.mixf(mark, rough, 0.45)
    p = b.new("ShaderNodeBsdfPrincipled")
    b.link_or_set(p.inputs["Base Color"], base)
    b.link_or_set(p.inputs["Roughness"], rough)
    nt.links.new(bump_n.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    MATS["street"] = m

    MATS["sidewalk"] = principled_material("Sidewalk", (0.04, 0.04, 0.045), rough=0.18)
    MATS["metal"] = principled_material("DarkMetal", (0.05, 0.05, 0.06), rough=0.35, metal=1.0)
    MATS["signbody"] = principled_material("SignBody", (0.015, 0.015, 0.02), rough=0.25)

    # --- Neon palette ---------------------------------------------------------------
    for k, c in NEON.items():
        MATS["neon_" + k] = emission_material("Neon_" + k, c, 12.0)
        MATS["text_" + k] = emission_material("Text_" + k, c, 9.0)
        set_emission_sampling(MATS["text_" + k], "NONE")
    # flickering variants
    for k in ("magenta", "cyan", "orange", "warm"):
        mt = emission_material("Flicker_" + k, NEON[k], 9.0)
        set_emission_sampling(mt, "NONE")
        node = mt.node_tree.nodes[mt["emit_node"]]
        s = node.inputs["Strength"]
        rng = random.Random(hash(k) & 0xffff)
        f = 0
        while f < F_END + 10:
            s.default_value = 9.0
            s.keyframe_insert("default_value", frame=f)
            f += rng.randint(20, 90)
            for _ in range(rng.randint(1, 3)):
                s.default_value = rng.choice([0.0, 0.4, 1.5])
                s.keyframe_insert("default_value", frame=f)
                f += rng.randint(1, 3)
                s.default_value = 9.0
                s.keyframe_insert("default_value", frame=f)
                f += rng.randint(1, 3)
        MATS["flicker_" + k] = mt
    set_constant_interp(bpy.data.materials)

    # aircraft warning lights (blink)
    mt = emission_material("BlinkRed", NEON["red"], 0.0)
    s = mt.node_tree.nodes[mt["emit_node"]].inputs["Strength"]
    for f in range(0, F_END + 60, 36):
        s.default_value = 0.0
        s.keyframe_insert("default_value", frame=f)
        s.default_value = 40.0
        s.keyframe_insert("default_value", frame=f + 2)
        s.default_value = 0.0
        s.keyframe_insert("default_value", frame=f + 8)
    MATS["blink"] = mt
    set_constant_interp([mt])

    MATS["lamp"] = emission_material("StreetLamp", (0.75, 0.85, 1.0), 14.0)

    # --- Holographic screens (animated) ----------------------------------------
    for idx, (c1, c2) in enumerate([("magenta", "cyan"), ("violet", "orange"), ("cyan", "green"), ("red", "violet")]):
        m, nt, out = new_material(f"HoloScreen{idx}")
        b = NB(nt)
        tc = b.new("ShaderNodeTexCoord")
        t = b.time_value()
        gx, gy, gz = b.sep(tc.outputs["Generated"])
        wave = b.new("ShaderNodeTexWave", wave_type="BANDS")
        b.link_or_set(wave.inputs["Vector"], b.comb(gx, b.math("ADD", gz, b.math("MULTIPLY", t, 0.25 + 0.1 * idx)), gy))
        wave.inputs["Scale"].default_value = 3.0 + idx
        wave.inputs["Distortion"].default_value = 6.0
        wave.inputs["Detail"].default_value = 3
        nz = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
        b.link_or_set(nz.inputs["Vector"], tc.outputs["Generated"])
        b.link_or_set(nz.inputs["W"], b.math("MULTIPLY", t, 0.3))
        nz.inputs["Scale"].default_value = 2.5
        fac = b.math("ADD", b.math("MULTIPLY", wave.outputs["Fac"], 0.6), b.math("MULTIPLY", nz.outputs["Fac"], 0.6))
        col = b.ramp(fac, [(0.15, (0.0, 0.0, 0.0)), (0.45, NEON[c1]), (0.75, NEON[c2]), (1.0, (1, 1, 1))])
        scan = b.math("MULTIPLY_ADD", b.math("SINE", b.math("MULTIPLY", gz, 260.0)), 0.15, 0.85)
        e = b.new("ShaderNodeEmission")
        b.link_or_set(e.inputs["Color"], col)
        b.link_or_set(e.inputs["Strength"], b.math("MULTIPLY", scan, 4.0))
        nt.links.new(e.outputs[0], out.inputs["Surface"])
        set_emission_sampling(m, "NONE")
        MATS[f"holo{idx}"] = m

    # --- Rain -------------------------------------------------------------------
    m, nt, out = new_material("Rain")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.7, 0.8, 1.0, 1)
    em.inputs["Strength"].default_value = 0.42
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    MATS["rain"] = m

    # --- Clouds ceiling ----------------------------------------------------------
    m, nt, out = new_material("CloudCeiling")
    b = NB(nt)
    geo = b.new("ShaderNodeNewGeometry")
    n = b.new("ShaderNodeTexNoise")
    b.link_or_set(n.inputs["Vector"], geo.outputs["Position"])
    n.inputs["Scale"].default_value = 0.0025
    n.inputs["Detail"].default_value = 10
    n.inputs["Roughness"].default_value = 0.62
    col = b.ramp(n.outputs["Fac"], [(0.35, (0.0, 0.0, 0.0)), (0.55, (0.10, 0.03, 0.10)), (0.75, (0.35, 0.10, 0.22))])
    e = b.new("ShaderNodeEmission")
    b.link_or_set(e.inputs["Color"], col)
    e.inputs["Strength"].default_value = 0.9
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    MATS["clouds"] = m

    # --- Hover cars ---------------------------------------------------------------
    MATS["car_body"] = principled_material("CarBody", (0.03, 0.03, 0.035), rough=0.2, metal=0.8, coat=1.0)
    MATS["car_head"] = emission_material("CarHead", (0.85, 0.92, 1.0), 25.0)
    MATS["car_tail"] = emission_material("CarTail", (1.0, 0.02, 0.04), 18.0)
    for k in ("magenta", "cyan", "violet"):
        MATS["car_glow_" + k] = emission_material("CarGlow_" + k, NEON[k], 8.0)
    for k in ("car_head", "car_tail", "car_glow_magenta", "car_glow_cyan", "car_glow_violet"):
        set_emission_sampling(MATS[k], "NONE")

    # --- Drone ----------------------------------------------------------------------
    MATS["carbon"] = carbon_material()
    MATS["gunmetal"] = principled_material("Gunmetal", (0.12, 0.12, 0.13), rough=0.28, metal=1.0)
    MATS["canopy"] = principled_material("Canopy", (0.005, 0.006, 0.01), rough=0.04, coat=1.0)
    MATS["prop"] = principled_material("Prop", (0.02, 0.02, 0.02), rough=0.4)
    MATS["led_cyan"] = emission_material("DroneLED_Cyan", NEON["cyan"], 0.0)
    MATS["led_red"] = emission_material("DroneLED_Red", NEON["red"], 0.0)
    MATS["led_white"] = emission_material("DroneLED_White", (0.9, 0.95, 1.0), 0.0)
    m, nt, out = new_material("PropDisc")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
    p.inputs["Roughness"].default_value = 0.3
    p.inputs["Alpha"].default_value = 0.0
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    MATS["propdisc"] = m


def carbon_material():
    m, nt, out = new_material("CarbonFiber")
    b = NB(nt)
    tc = b.new("ShaderNodeTexCoord")
    ck = b.new("ShaderNodeTexChecker")
    b.link_or_set(ck.inputs["Vector"], tc.outputs["Object"])
    ck.inputs["Scale"].default_value = 90.0
    ck.inputs["Color1"].default_value = (0.012, 0.012, 0.014, 1)
    ck.inputs["Color2"].default_value = (0.03, 0.03, 0.035, 1)
    p = b.new("ShaderNodeBsdfPrincipled")
    nt.links.new(ck.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.22
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.03
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    return m


def set_constant_interp(materials):
    for mt in materials:
        nt = getattr(mt, "node_tree", None)
        ad = nt.animation_data if nt else None
        if not ad or not ad.action:
            continue
        for fc in iter_fcurves(ad.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def iter_fcurves(action):
    """Works for both legacy and layered (slotted) actions."""
    try:
        for fc in action.fcurves:
            yield fc
        return
    except Exception:
        pass
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                for fc in cb.fcurves:
                    yield fc


# ----------------------------------------------------------------------------
# Mesh helpers
# ----------------------------------------------------------------------------
class MeshBuilder:
    def __init__(self):
        self.v, self.f, self.rnd, self.mat, self.style = [], [], [], [], []

    def box(self, x0, x1, y0, y1, z0, z1, rnd=0.0, mat=0, top=True, bottom=False, style=0.0):
        b = len(self.v)
        self.v += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        if top:
            faces.append((4, 5, 6, 7))
        if bottom:
            faces.append((0, 3, 2, 1))
        for fc in faces:
            self.f.append(tuple(b + i for i in fc))
            self.rnd.append(rnd)
            self.mat.append(mat)
            self.style.append(style)

    def cbox(self, c, size, rnd=0.0, mat=0, bottom=True):
        x, y, z = c
        sx, sy, sz = size
        self.box(x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2, z - sz / 2, z + sz / 2, rnd, mat, True, bottom)

    def build(self, name, mats, collection=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        a = me.attributes.new("rnd", "FLOAT", "FACE")
        a.data.foreach_set("value", self.rnd)
        a2 = me.attributes.new("style", "FLOAT", "FACE")
        a2.data.foreach_set("value", self.style)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.mat)
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        return ob


def new_collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def add_text(body, size, mat, loc, rot, coll, font, extrude=0.06, align="CENTER", spacing=1.0):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = body
    cu.font = font
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_line = spacing
    cu.materials.append(mat)
    ob = bpy.data.objects.new("Txt_" + body.replace("\n", "")[:10], cu)
    ob.location = loc
    ob.rotation_euler = rot
    coll.objects.link(ob)
    return ob


# ----------------------------------------------------------------------------
# City
# ----------------------------------------------------------------------------
AVE_HALF = 12.0       # road half width
FACADE_X = 16.0       # building line along the avenue
BRIDGE_Y = 600.0
GATE_Y0, GATE_Y1 = 990.0, 1030.0
GATE_HALF_W, GATE_OPEN_HALF, GATE_OPEN_TOP, GATE_H = 58.0, 12.0, 76.0, 330.0
HERO = (16.0, 40.0, 40.0, 63.0, 48.0)  # x0,x1,y0,y1,height of the launch rooftop
DRONE_REST = Vector((18.6, 55.0, 48.0))


def build_city(fonts):
    city = new_collection("City")
    signs = new_collection("Signage")
    bmb = MeshBuilder()          # buildings (building material)
    det = MeshBuilder()          # dark metal details (AC units, antennas, poles)
    neon = MeshBuilder()         # emissive strips; mat index = palette idx
    blink = MeshBuilder()
    lamps = MeshBuilder()
    signbody = MeshBuilder()
    pal = NEON_KEYS
    flick_keys = ["magenta", "cyan", "orange", "warm"]

    xs_e = [(16, 66), (80, 130), (144, 196), (210, 262), (276, 330), (344, 400), (414, 470)]
    xcols = xs_e + [(-b, -a) for a, b in xs_e]
    rows = [(70 * k + 7, 70 * k + 63) for k in range(-8, 26)]

    def avenue_side(x0, x1):
        return x0 == 16 or x1 == -16

    word_i = 0
    for (x0, x1) in xcols:
        for (y0, y1) in rows:
            # gate tower occupies the blocks around the avenue at that row
            if y0 <= GATE_Y0 <= y1 and min(abs(x0), abs(x1)) < GATE_HALF_W + 5:
                continue
            # subdivide block into lots along y
            ys = [y0]
            while ys[-1] < y1 - 12:
                ys.append(min(y1, ys[-1] + RNG.uniform(13, 28)))
            ys[-1] = y1
            near = min(abs(x0), abs(x1)) < 70
            depth_split = RNG.random() < 0.6
            xsplits = [(x0, x1)]
            if depth_split:
                xm = (x0 + x1) / 2 + RNG.uniform(-6, 6)
                xsplits = [(x0, xm), (xm, x1)]
            for i in range(len(ys) - 1):
                ly0, ly1 = ys[i], ys[i + 1]
                for (lx0, lx1) in xsplits:
                    hero = (lx0 <= HERO[0] + 0.01 and lx1 > HERO[0] and ly0 < HERO[3] and ly1 > HERO[2] and y0 == 7)
                    if hero:
                        continue
                    gap = RNG.uniform(0.4, 1.6)
                    bx0, bx1, by0, by1 = lx0 + gap, lx1 - gap, ly0 + gap, ly1 - gap
                    if bx1 - bx0 < 6 or by1 - by0 < 6:
                        continue
                    front = avenue_side(lx0, lx1) and (lx0 == 16 or lx1 == -16)
                    if front:  # keep the building line on the avenue crisp
                        if lx0 == 16:
                            bx0 = FACADE_X
                        else:
                            bx1 = -FACADE_X
                    r = RNG.random()
                    if near:
                        hgt = RNG.uniform(30, 120) if RNG.random() < 0.8 else RNG.uniform(120, 190)
                    else:
                        hgt = RNG.uniform(20, 110) if RNG.random() < 0.75 else RNG.uniform(110, 260)
                    # nothing directly around the hero roof may be too low/high weirdly
                    if y0 == 7 and lx0 >= 16 and lx0 < 70:
                        hgt = max(hgt, 70)
                    if not near and RNG.random() < 0.05:
                        hgt = RNG.uniform(240, 310)
                    add_tower(bmb, det, blink, neon, bx0, bx1, by0, by1, hgt, r, front)
                    if front:
                        word_i = add_signage(fonts, signs, signbody, neon, bx0, bx1, by0, by1, hgt, lx0 == 16, word_i)

    # --- hero rooftop building ---------------------------------------------------
    x0, x1, y0, y1, hh = HERO
    bmb.box(x0, x1, y0, y1, 0, hh, 0.37)
    for (a0, a1, b0, b1) in [(x0, x1, y0, y0 + 0.3), (x0, x1, y1 - 0.3, y1), (x1 - 0.3, x1, y0, y1),
                             (x0, x0 + 0.3, y0, y1)]:
        det.box(a0, a1, b0, b1, hh, hh + 0.35, 0.0)
    det.box(30, 33, 43, 46, hh, hh + 1.6, 0.0)            # AC units
    det.box(34, 36.5, 43, 45, hh, hh + 1.2, 0.0)
    det.box(27, 29, 58, 61, hh, hh + 3.5, 0.0)            # water tank
    det.box(36.5, 36.8, 58.5, 58.8, hh, hh + 9.0, 0.0)    # antenna
    blink.cbox((36.65, 58.65, hh + 9.15), (0.35, 0.35, 0.35))
    neon.box(x0 - 0.05, x0 + 0.05, y0, y1, hh - 0.25, hh - 0.12, 0.0, pal.index("cyan"), bottom=True)
    # rooftop neon sign behind the drone (seen in the macro shot)
    signbody.box(34, 34.4, 49, 57, hh, hh + 3.4, 0.0, bottom=True)
    add_text("KAIRO", 1.9, MATS["flicker_magenta"], (33.75, 53, hh + 1.7),
             (math.radians(90), 0, math.radians(-90)), signs, fonts["bold"])
    # hero building facade sign
    signbody.box(12.6, FACADE_X, 47.8, 48.2, 22, 44, 0.0, bottom=True)
    neon.box(12.55, FACADE_X, 47.75, 48.25, 21.8, 22.0, 0.0, pal.index("orange"), bottom=True)
    neon.box(12.55, FACADE_X, 47.75, 48.25, 44.0, 44.2, 0.0, pal.index("orange"), bottom=True)
    for side, ry in ((-1, 0), (1, math.pi)):
        add_text("N\nO\nV\nA", 2.6, MATS["text_orange"], (14.3, 48 + side * 0.22, 33),
                 (math.radians(90), 0, ry), signs, fonts["bold"], spacing=0.95)

    # --- skybridge ----------------------------------------------------------------
    bmb.box(-FACADE_X, FACADE_X, BRIDGE_Y - 5, BRIDGE_Y + 5, 17.0, 23.0, 0.81, bottom=True)
    for xx in (-6, 6):
        neon.box(xx - 0.1, xx + 0.1, BRIDGE_Y - 5, BRIDGE_Y + 5, 16.92, 17.0, 0.0, pal.index("cyan"), bottom=True)
    neon.box(-FACADE_X, FACADE_X, BRIDGE_Y - 5.08, BRIDGE_Y - 5.0, 22.9, 23.1, 0.0, pal.index("magenta"), bottom=True)
    neon.box(-FACADE_X, FACADE_X, BRIDGE_Y - 5.08, BRIDGE_Y - 5.0, 16.9, 17.1, 0.0, pal.index("magenta"), bottom=True)
    add_text("KAIRO  LINE  7", 2.2, MATS["text_cyan"], (0, BRIDGE_Y - 5.15, 20.0),
             (math.radians(90), 0, 0), signs, fonts["bold"])

    # --- the gate tower (finale) ---------------------------------------------------
    gw, go, gt = GATE_HALF_W, GATE_OPEN_HALF, GATE_OPEN_TOP
    bmb.box(-gw, -go, GATE_Y0, GATE_Y1, 0, gt, 0.91, top=False, style=0.1)
    bmb.box(go, gw, GATE_Y0, GATE_Y1, 0, gt, 0.93, top=False, style=0.1)
    bmb.box(-gw, gw, GATE_Y0, GATE_Y1, gt, GATE_H, 0.95, bottom=True, style=0.7)
    bmb.box(-gw + 10, gw - 10, GATE_Y0 + 6, GATE_Y1 - 6, GATE_H, GATE_H + 30, 0.97, style=0.7)
    det.box(-0.4, 0.4, GATE_Y0 + 18, GATE_Y0 + 19, GATE_H + 30, GATE_H + 75, 0.0)
    blink.cbox((0, GATE_Y0 + 18.5, GATE_H + 75.5), (1.2, 1.2, 1.2))
    cy = GATE_Y0 - 0.15
    ci = pal.index("cyan")
    mi = pal.index("magenta")
    for xx in (-gw, gw):
        neon.box(xx - 0.3, xx + 0.3, cy - 0.3, cy, 0, GATE_H, 0.0, mi, bottom=True)
    for xx in (-go, go):
        neon.box(xx - 0.25, xx + 0.25, cy - 0.3, cy, 0, gt, 0.0, ci, bottom=True)
    neon.box(-go, go, cy - 0.3, cy, gt - 0.25, gt + 0.25, 0.0, ci, bottom=True)
    neon.box(-gw, gw, cy - 0.3, cy, GATE_H - 0.4, GATE_H, 0.0, mi, bottom=True)
    # inner gate tunnel strips
    for zz in (20, 40, 60):
        neon.box(-go, -go + 0.2, GATE_Y0, GATE_Y1, zz, zz + 0.3, 0.0, ci, bottom=True)
        neon.box(go - 0.2, go, GATE_Y0, GATE_Y1, zz, zz + 0.3, 0.0, ci, bottom=True)

    # --- streets, sidewalks, lamps ------------------------------------------------
    street = bpy.data.meshes.new("Street")
    s = 2400
    street.from_pydata([(-s, -900, 0), (s, -900, 0), (s, 2600, 0), (-s, 2600, 0)], [], [(0, 1, 2, 3)])
    street.materials.append(MATS["street"])
    so = bpy.data.objects.new("Street", street)
    city.objects.link(so)
    walk = MeshBuilder()
    for side in (-1, 1):
        xa, xb = sorted((side * AVE_HALF, side * FACADE_X))
        walk.box(xa, xb, -900, GATE_Y0, 0, 0.18, 0.0)
        for y in range(-600, 980, 30):
            lx = side * 13.6
            lamps_pole(det, lamps, lx, y, side)
    walk.build("Sidewalks", [MATS["sidewalk"]], city)

    bo = bmb.build("Buildings", [MATS["building"]], city)
    det.build("Details", [MATS["metal"]], city)
    neon.build("NeonStrips", [MATS["neon_" + k] for k in pal], city)
    blink.build("AircraftLights", [MATS["blink"]], city)
    lamps.build("LampHeads", [MATS["lamp"]], city)
    signbody.build("SignBodies", [MATS["signbody"]], signs)
    build_rooftop_holos(signs)

    # cloud ceiling
    cl = bpy.data.meshes.new("Clouds")
    s = 9000
    cl.from_pydata([(-s, -s, 340), (s, -s, 340), (s, s, 340), (-s, s, 340)], [], [(0, 3, 2, 1)])
    cl.materials.append(MATS["clouds"])
    co = bpy.data.objects.new("CloudCeiling", cl)
    city.objects.link(co)
    for attr in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
        setattr(co, attr, False)
    return city


def lamps_pole(det, lamps, x, y, side):
    det.box(x - 0.12, x + 0.12, y - 0.12, y + 0.12, 0, 7.2, 0.0)
    det.box(min(x, x - side * 2.2), max(x, x - side * 2.2), y - 0.08, y + 0.08, 7.0, 7.2, 0.0)
    hx = x - side * 2.0
    lamps.box(hx - 0.6, hx + 0.6, y - 0.18, y + 0.18, 6.85, 7.0, 0.0, bottom=True)


HOLO_SPECS = []   # rooftop billboards created after the city mesh


def stepped(bmb, x0, x1, y0, y1, z0, h, r, style):
    tiers = 1 + (h - z0 > 60) + (h - z0 > 130)
    cx0, cx1, cy0, cy1 = x0, x1, y0, y1
    for t in range(tiers):
        zt = h if t == tiers - 1 else z0 + (h - z0) * RNG.uniform(0.45, 0.7)
        bmb.box(cx0, cx1, cy0, cy1, z0, zt, (r + 0.13 * t) % 1.0, style=style)
        z0 = zt
        ins = RNG.uniform(1.5, 4.5)
        if cx1 - cx0 > 2 * ins + 6 and cy1 - cy0 > 2 * ins + 6:
            cx0, cx1, cy0, cy1 = cx0 + ins, cx1 - ins, cy0 + ins, cy1 - ins
    return cx0, cx1, cy0, cy1


def add_fins(det, x0, x1, y0, y1, z0, z1, pitch):
    """Vertical fins on all four facades (adds relief and breaks repetition)."""
    n = int((x1 - x0) / pitch)
    for i in range(1, n):
        x = x0 + i * (x1 - x0) / n
        det.box(x - 0.15, x + 0.15, y0 - 0.7, y0, z0, z1, 0.0)
        det.box(x - 0.15, x + 0.15, y1, y1 + 0.7, z0, z1, 0.0)
    n = int((y1 - y0) / pitch)
    for i in range(1, n):
        y = y0 + i * (y1 - y0) / n
        det.box(x0 - 0.7, x0, y - 0.15, y + 0.15, z0, z1, 0.0)
        det.box(x1, x1 + 0.7, y - 0.15, y + 0.15, z0, z1, 0.0)


def add_tower(bmb, det, blink, neon, x0, x1, y0, y1, h, r, front=False):
    style = RNG.random()
    kind = RNG.random()
    w, d = x1 - x0, y1 - y0
    tops = []
    if kind < 0.38 or h < 40:                                   # stepped tiers
        tops.append((*stepped(bmb, x0, x1, y0, y1, 0.0, h, r, style), h))
        if RNG.random() < 0.3 and w > 14 and d > 14:
            add_fins(det, x0, x1, y0, y1, 4.5, min(h, h * 0.6 if h > 60 else h), RNG.uniform(3.5, 6.0))
    elif kind < 0.6 and not front and min(w, d) > 18:         # podium + slender tower
        ph = RNG.uniform(10, 24)
        bmb.box(x0, x1, y0, y1, 0, ph, r, style=RNG.random())
        ins = min(w, d) * RNG.uniform(0.18, 0.3)
        t0 = (x0 + ins, x1 - ins, y0 + ins, y1 - ins)
        tops.append((*stepped(bmb, *t0, ph, h, (r + 0.31) % 1, style), h))
        if RNG.random() < 0.4:
            add_fins(det, *t0, ph + 2, h - 2, RNG.uniform(3.0, 5.0))
    elif kind < 0.8 and max(w, d) > 22:                         # twin towers + skybridge
        h2 = h * RNG.uniform(0.7, 0.95)
        g = RNG.uniform(4, 7)
        if d >= w:
            ym = (y0 + y1) / 2
            a, bb = (x0, x1, y0, ym - g / 2), (x0, x1, ym + g / 2, y1)
            br = (x0 + 2, x1 - 2, ym - g / 2, ym + g / 2)
        else:
            xm = (x0 + x1) / 2
            a, bb = (x0, xm - g / 2, y0, y1), (xm + g / 2, x1, y0, y1)
            br = (xm - g / 2, xm + g / 2, y0 + 2, y1 - 2)
        tops.append((*stepped(bmb, *a, 0.0, h, r, style), h))
        tops.append((*stepped(bmb, *bb, 0.0, h2, (r + 0.5) % 1, style), h2))
        zb = min(h, h2) * RNG.uniform(0.45, 0.75)
        bmb.box(*br, zb, zb + 4.0, (r + 0.2) % 1, bottom=True, style=0.65)
        neon.box(br[0], br[1], br[2], br[3], zb - 0.15, zb, 0.0, RNG.randrange(len(NEON_KEYS)), bottom=True)
    else:                                                       # slab with a glass crown
        zc = h * RNG.uniform(0.86, 0.93)
        bmb.box(x0, x1, y0, y1, 0, zc, r, style=style)
        bmb.box(x0 + 1.2, x1 - 1.2, y0 + 1.2, y1 - 1.2, zc, h, (r + 0.4) % 1, style=0.7)
        k = RNG.randrange(len(NEON_KEYS))
        for zz in (zc - 0.1, h - 0.3):
            neon.box(x0 - 0.1, x1 + 0.1, y0 - 0.1, y0, zz, zz + 0.25, 0.0, k, bottom=True)
            neon.box(x0 - 0.1, x1 + 0.1, y1, y1 + 0.1, zz, zz + 0.25, 0.0, k, bottom=True)
            neon.box(x0 - 0.1, x0, y0, y1, zz, zz + 0.25, 0.0, k, bottom=True)
            neon.box(x1, x1 + 0.1, y0, y1, zz, zz + 0.25, 0.0, k, bottom=True)
        tops.append((x0 + 1.2, x1 - 1.2, y0 + 1.2, y1 - 1.2, h))
    for (cx0, cx1, cy0, cy1, th) in tops:
        # rooftop clutter
        for _ in range(RNG.randint(0, 3)):
            ww, dd = RNG.uniform(1.5, 4), RNG.uniform(1.5, 4)
            if cx1 - cx0 > ww + 2 and cy1 - cy0 > dd + 2:
                ax = RNG.uniform(cx0 + 1, cx1 - 1 - ww)
                ay = RNG.uniform(cy0 + 1, cy1 - 1 - dd)
                det.box(ax, ax + ww, ay, ay + dd, th, th + RNG.uniform(1, 3), 0.0)
        if th > 90:
            ax, ay = (cx0 + cx1) / 2, (cy0 + cy1) / 2
            ah = RNG.uniform(6, 22)
            det.box(ax - 0.2, ax + 0.2, ay - 0.2, ay + 0.2, th, th + ah, 0.0)
            blink.cbox((ax, ay, th + ah + 0.3), (0.6, 0.6, 0.6))
        # LED crown band or roof outline
        if RNG.random() < 0.25:
            k = RNG.randrange(len(NEON_KEYS))
            zz = th - RNG.choice((0.4, 2.5, 4.0))
            neon.box(cx0 - 0.1, cx1 + 0.1, cy0 - 0.1, cy0, zz, zz + 0.3, 0.0, k, bottom=True)
            neon.box(cx0 - 0.1, cx1 + 0.1, cy1, cy1 + 0.1, zz, zz + 0.3, 0.0, k, bottom=True)
            neon.box(cx0 - 0.1, cx0, cy0, cy1, zz, zz + 0.3, 0.0, k, bottom=True)
            neon.box(cx1, cx1 + 0.1, cy0, cy1, zz, zz + 0.3, 0.0, k, bottom=True)
        # rooftop holographic billboard
        if 25 < th < 140 and RNG.random() < 0.09 and cx1 - cx0 > 12 and cy1 - cy0 > 12:
            HOLO_SPECS.append(((cx0 + cx1) / 2, (cy0 + cy1) / 2, th, RNG.randrange(4), RNG.uniform(12, 20)))
            det.box((cx0 + cx1) / 2 - 0.3, (cx0 + cx1) / 2 + 0.3, (cy0 + cy1) / 2 - 0.3, (cy0 + cy1) / 2 + 0.3,
                    th, th + 4, 0.0)


def build_rooftop_holos(coll):
    for (x, y, z, face, w) in HOLO_SPECS:
        hh = w * 0.56
        z0 = z + 4.0
        ang = face * math.pi / 2
        dx, dy = math.cos(ang) * w / 2, math.sin(ang) * w / 2
        me = bpy.data.meshes.new("RoofHolo")
        me.from_pydata([(x - dx, y - dy, z0), (x + dx, y + dy, z0), (x + dx, y + dy, z0 + hh), (x - dx, y - dy, z0 + hh)],
                       [], [(0, 1, 2, 3)])
        me.materials.append(MATS[f"holo{RNG.randrange(4)}"])
        ob = bpy.data.objects.new("RoofHolo", me)
        coll.objects.link(ob)
    print("rooftop billboards:", len(HOLO_SPECS))


def add_signage(fonts, coll, signbody, neon, x0, x1, y0, y1, h, east, word_i):
    """Signs on avenue-facing facades. east=True -> facade at x=+16 facing -X."""
    fx = FACADE_X if east else -FACADE_X
    out = -1 if east else 1        # direction toward the avenue
    pal = NEON_KEYS
    # vertical blade signs
    nblades = 1 + (y1 - y0 > 22) + (RNG.random() < 0.3)
    used = []
    for _ in range(nblades):
        by = RNG.uniform(y0 + 2, y1 - 2)
        if any(abs(by - u) < 5 for u in used) or abs(by - BRIDGE_Y) < 8:
            continue
        used.append(by)
        word = WORDS[word_i % len(WORDS)]
        word_i += 1
        nlet = len(word)
        lsize = RNG.uniform(1.5, 2.1)
        H = nlet * lsize * 1.05 + 1.6
        zb = RNG.uniform(5.5, max(6.0, min(h - H - 4, 48)))
        if zb + H > h - 1:
            continue
        depth = RNG.uniform(2.6, 3.6)
        xa, xb = sorted((fx, fx + out * depth))
        signbody.box(xa, xb, by - 0.2, by + 0.2, zb, zb + H, 0.0, bottom=True)
        ck = RNG.choice(pal)
        k = pal.index(ck)
        for (za, zb2) in ((zb - 0.12, zb), (zb + H, zb + H + 0.12)):
            neon.box(xa, xb, by - 0.24, by + 0.24, za, zb2, 0.0, k, bottom=True)
        xo = fx + out * depth
        xa2, xb2 = sorted((xo, xo + out * 0.12))
        neon.box(xa2, xb2, by - 0.24, by + 0.24, zb - 0.12, zb + H + 0.12, 0.0, k, bottom=True)
        tk = RNG.choice(pal)
        mat = MATS["flicker_" + tk] if (tk in ("magenta", "cyan", "orange", "warm") and RNG.random() < 0.25) else MATS["text_" + tk]
        cx = fx + out * depth / 2
        for side, rz in ((-1, 0.0), (1, math.pi)):
            add_text("\n".join(word), lsize, mat, (cx, by + side * 0.23, zb + H / 2),
                     (math.radians(90), 0, rz), coll, fonts["bold"], spacing=0.92)
    # flat wall sign high on the facade (readable from the avenue)
    if RNG.random() < 0.55 and h > 30:
        word = WORDS[word_i % len(WORDS)]
        word_i += 1
        zc = RNG.uniform(18, min(h - 6, 70))
        yc = (y0 + y1) / 2
        rz = math.radians(-90) if east else math.radians(90)
        tk = RNG.choice(pal)
        add_text(word, RNG.uniform(2.5, 4.0), MATS["text_" + tk], (fx + out * 0.12, yc, zc),
                 (math.radians(90), 0, rz), coll, fonts["bold"])
    # holographic screen panel
    if RNG.random() < 0.3 and h > 40:
        w = min(y1 - y0 - 3, RNG.uniform(8, 16))
        hh = w * RNG.uniform(0.55, 0.9)
        zc = RNG.uniform(14, min(h - hh / 2 - 3, 60))
        yc = (y0 + y1) / 2
        me = bpy.data.meshes.new("Holo")
        xx = fx + out * 0.2
        me.from_pydata([(xx, yc - w / 2, zc - hh / 2), (xx, yc + w / 2, zc - hh / 2),
                        (xx, yc + w / 2, zc + hh / 2), (xx, yc - w / 2, zc + hh / 2)], [], [(0, 1, 2, 3)])
        me.materials.append(MATS[f"holo{RNG.randrange(4)}"])
        ob = bpy.data.objects.new("HoloScreen", me)
        coll.objects.link(ob)
    # vertical corner neon line
    if RNG.random() < 0.5:
        k = RNG.randrange(len(pal))
        yy = y0 if RNG.random() < 0.5 else y1
        xa, xb = sorted((fx, fx + out * 0.15))
        neon.box(xa, xb, yy - 0.12, yy + 0.12, 4.8, h * RNG.uniform(0.5, 0.95), 0.0, k, bottom=True)
    return word_i


# ----------------------------------------------------------------------------
# Hero sign on the gate tower
# ----------------------------------------------------------------------------
SIGN_ON = (1262, 1300)


SIGN_TEXT, SIGN_SPLIT = "AISTUDIO3D", 8      # characters >= SIGN_SPLIT use the accent colour
SIGN_Z, SIGN_WIDTH = 168.0, 98.0


def build_gate_sign(fonts):
    coll = new_collection("GateSign")
    m_main = emission_material("Hero_Main", NEON["magenta"], 0.0)
    m_acc = emission_material("Hero_Accent", NEON["cyan"], 0.0)
    t = add_text(SIGN_TEXT, 20.0, m_main, (0, GATE_Y0 - 1.2, SIGN_Z), (math.radians(90), 0, 0), coll,
                 fonts["display"], extrude=0.5)
    cu = t.data
    cu.materials.append(m_acc)
    for i in range(SIGN_SPLIT, len(SIGN_TEXT)):
        cu.body_format[i].material_index = 1
    bpy.context.view_layer.update()
    width = t.dimensions.x
    cu.size = 20.0 * SIGN_WIDTH / max(1e-3, width)
    bpy.context.view_layer.update()
    cap = t.dimensions.y
    print("sign size", round(cu.size, 2), "dims", tuple(round(v, 1) for v in t.dimensions))
    # frame
    fr = MeshBuilder()
    half = SIGN_WIDTH / 2 + 5
    for zz in (SIGN_Z - cap / 2 - 7, SIGN_Z + cap / 2 + 7):
        fr.box(-half, half, GATE_Y0 - 0.9, GATE_Y0 - 0.6, zz, zz + 0.5, 0.0, bottom=True)
    fm = emission_material("Hero_Frame", NEON["violet"], 0.0)
    fr.build("HeroFrame", [fm], coll)
    mats = [m_main, m_acc, fm]
    # power-on flicker
    rng = random.Random(5)
    for m, peak in zip(mats, (22.0, 22.0, 10.0)):
        s = m.node_tree.nodes[m["emit_node"]].inputs["Strength"]
        s.default_value = 0.0
        s.keyframe_insert("default_value", frame=0)
        f = SIGN_ON[0] + rng.randint(0, 6)
        while f < SIGN_ON[1]:
            s.default_value = peak * rng.choice([0.0, 0.3, 1.0, 0.6])
            s.keyframe_insert("default_value", frame=f)
            f += rng.randint(1, 4)
        s.default_value = peak
        s.keyframe_insert("default_value", frame=SIGN_ON[1])
        s.keyframe_insert("default_value", frame=F_END + 5)
    set_constant_interp(mats)


# ----------------------------------------------------------------------------
# Hover cars (traffic driven by scene["tau"] so slow-motion affects them)
# ----------------------------------------------------------------------------
def car_mesh(glow_key):
    bm = bmesh.new()
    def cube(c, s):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
        return r
    cube((0, 0, 0), (2.1, 4.6, 0.8))
    cube((0, -0.3, 0.6), (1.7, 2.2, 0.55))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.12, segments=2, affect="EDGES")
    for f in bm.faces:
        f.material_index = 0
    def light(c, s, idx):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
        for f in {fc for v in r["verts"] for fc in v.link_faces}:
            f.material_index = idx
    light((0, 2.33, 0.05), (1.8, 0.06, 0.14), 1)
    light((0, -2.33, 0.1), (1.9, 0.06, 0.16), 2)
    light((0, 0, -0.43), (1.6, 3.6, 0.04), 3)
    me = bpy.data.meshes.new("Car_" + glow_key)
    bm.to_mesh(me)
    bm.free()
    for k in ("car_body", "car_head", "car_tail", "car_glow_" + glow_key):
        me.materials.append(MATS[k])
    return me


def drive_linear(ob, idx, pos, vel_per_frame, scene):
    fc = ob.driver_add("location", idx)
    drv = fc.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "t"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "SCENE"
    var.targets[0].id = scene
    var.targets[0].data_path = '["tau"]'
    drv.expression = f"{pos:.3f}+{vel_per_frame:.5f}*t"


def build_traffic(scene):
    coll = new_collection("Traffic")
    meshes = [car_mesh(k) for k in ("magenta", "cyan", "violet")]
    T = (F_END + 40) / FPS
    lanes = []   # axis, cross-coordinate, z, dir, lo, hi, speed range, spacing range
    air = ((20, 34), (30, 75))
    for (x, z, d) in [(-8, 28, -1), (8, 28, 1), (-4, 36, -1), (4, 36, 1), (-6.5, 47, -1), (6.5, 47, 1),
                      (-3, 61, -1), (3, 61, 1), (-9, 80, -1), (9, 92, 1)]:
        lanes.append(("Y", x, z, d, -700.0, 1900.0, *air))
    # street-level traffic on the avenue (hovering just above the wet asphalt)
    for (x, d) in [(-9.6, -1), (-6.0, -1), (-2.4, -1), (2.4, 1), (6.0, 1), (9.6, 1)]:
        lanes.append(("Y", x, 0.75, d, -700.0, 1900.0, (11, 19), (14, 42)))
    # background streams of light above the outer blocks
    for (x, z, d) in [(-105, 72, 1), (-112, 88, -1), (105, 80, -1), (172, 110, 1), (-175, 125, -1),
                      (240, 95, -1), (-238, 140, 1), (310, 120, 1)]:
        lanes.append(("Y", x, z, d, -700.0, 1900.0, (24, 36), (40, 90)))
    for k in range(-6, 24, 2):
        yc = 70 * k
        lanes.append(("X", yc - 2.5, 33 + (k % 4) * 3, 1, -520.0, 520.0, (20, 34), (60, 130)))
        lanes.append(("X", yc + 2.5, 52 + (k % 3) * 4, -1, -520.0, 520.0, (20, 34), (60, 130)))
        if -2 <= k <= 16:
            lanes.append(("X", yc - 3.0, 0.75, 1, -300.0, 300.0, (10, 16), (40, 110)))
            lanes.append(("X", yc + 3.0, 0.75, -1, -300.0, 300.0, (10, 16), (40, 110)))
    n = 0
    for (axis, c, z, d, lo, hi, vr, sp) in lanes:
        v = RNG.uniform(*vr)
        span = v * T
        pos = lo - span if d > 0 else lo
        end = hi if d > 0 else hi + span
        ground = z < 2
        while pos < end:
            pos += RNG.uniform(*sp)
            vv = v * RNG.uniform(0.92, 1.08)
            ob = bpy.data.objects.new(f"Car{n:04d}", RNG.choice(meshes))
            coll.objects.link(ob)
            zz = z + (RNG.uniform(-0.15, 0.15) if ground else RNG.uniform(-1.2, 1.2))
            jitter = RNG.uniform(-0.3, 0.3) if ground else RNG.uniform(-0.6, 0.6)
            if axis == "Y":
                # skip ground cars that would sit inside the gate tower's solid pillars
                ob.location = (c + jitter, pos, zz)
                ob.rotation_euler = (0, 0, 0 if d > 0 else math.pi)
                idx = 1
            else:
                ob.location = (pos, c + jitter, zz)
                ob.rotation_euler = (0, 0, -math.pi / 2 if d > 0 else math.pi / 2)
                idx = 0
            drive_linear(ob, idx, pos, d * vv / FPS, scene)
            n += 1
    print("cars:", n)


def person_mesh(umb_key):
    bm = bmesh.new()
    def part(c, s, idx, kind="cube"):
        if kind == "cube":
            r = bmesh.ops.create_cube(bm, size=1.0)
        elif kind == "cyl":
            r = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.5, radius2=0.5, depth=1.0)
        elif kind == "umb":
            r = bmesh.ops.create_cone(bm, cap_ends=False, segments=12, radius1=0.5, radius2=0.02, depth=1.0)
        else:
            r = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.5)
        for v in r["verts"]:
            v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
        for f in {fc for v in r["verts"] for fc in v.link_faces}:
            f.material_index = idx
    part((0, 0, 0.95), (0.42, 0.3, 1.3), 0, "cyl")       # coat
    part((0, 0, 1.72), (0.22, 0.22, 0.24), 0, "sph")     # head
    if umb_key:
        part((0, 0, 1.98), (0.004, 0.004, 0.55), 0)        # shaft
        part((0, 0, 2.18), (1.15, 1.15, 0.28), 1, "umb")   # canopy
        r = bmesh.ops.create_cone(bm, cap_ends=False, segments=12, radius1=0.585, radius2=0.585, depth=0.04)
        for v in r["verts"]:
            v.co = Vector((v.co.x, v.co.y, v.co.z + 2.05))
        for f in {fc for v in r["verts"] for fc in v.link_faces}:
            f.material_index = 2
    me = bpy.data.meshes.new("Person_" + (umb_key or "none"))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS["coat"])
    me.materials.append(MATS["umbrella"])
    me.materials.append(MATS["neon_" + (umb_key or "cyan")])
    return me


def build_pedestrians(scene):
    coll = new_collection("Pedestrians")
    MATS["coat"] = principled_material("Coat", (0.02, 0.02, 0.025), rough=0.35)
    MATS["umbrella"] = principled_material("Umbrella", (0.01, 0.012, 0.02), rough=0.08, coat=1.0)
    keys = ["cyan", "magenta", "violet", "warm", "cyan", "orange", None, None]
    meshes = {k: person_mesh(k) for k in set(keys)}
    n = 0
    for side in (-1, 1):
        y = -620.0
        while y < 880:
            y += RNG.uniform(2.5, 9.0)
            x = side * RNG.uniform(12.6, 15.4)
            ob = bpy.data.objects.new(f"Ped{n:04d}", meshes[RNG.choice(keys)])
            coll.objects.link(ob)
            ob.location = (x, y, 0.18)
            moving = RNG.random() < 0.8
            d = RNG.choice((-1, 1))
            ob.rotation_euler = (0, 0, (0 if d > 0 else math.pi) if moving else RNG.uniform(0, 2 * math.pi))
            if moving:
                drive_linear(ob, 1, y, d * RNG.uniform(1.0, 1.6) / FPS, scene)
            n += 1
    print("pedestrians:", n)


def build_blimps():
    coll = new_collection("Blimps")
    for i, (p0, p1, rotz, holo) in enumerate((
            ((-300, 420, 240), (-60, 420, 240), math.pi / 2, 0),
            ((120, 1200, 205), (40, 1200, 205), math.pi / 2, 1))):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.5)
        for v in bm.verts:
            v.co = Vector((v.co.x * 16, v.co.y * 62, v.co.z * 16))
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((v.co.x * 5, v.co.y * 14, v.co.z * 3 - 9))
        me = bpy.data.meshes.new("Blimp")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(MATS["metal"])
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(f"Blimp{i}", me)
        coll.objects.link(ob)
        ob.rotation_euler = (0, 0, rotz)
        # holo screens on both flanks
        for sx in (-1, 1):
            sm = bpy.data.meshes.new("BlimpScreen")
            x = sx * 15.2
            sm.from_pydata([(x, -30, -7), (x, 30, -7), (x, 30, 7), (x, -30, 7)], [], [(0, 1, 2, 3)])
            sm.materials.append(MATS[f"holo{(holo + (sx > 0)) % 4}"])
            so = bpy.data.objects.new("BlimpScreen", sm)
            so.parent = ob
            coll.objects.link(so)
        for yy in (-58, 58):
            bmb = MeshBuilder()
            bmb.cbox((0, yy, 0), (1.5, 1.5, 1.5))
            bl = bmb.build("BlimpLight", [MATS["blink"]], coll)
            bl.parent = ob
        for f, loc in ((0, p0), (F_END, p1)):
            ob.location = loc
            ob.keyframe_insert("location", frame=f)
        if ob.animation_data and ob.animation_data.action:
            for fc in iter_fcurves(ob.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


# ----------------------------------------------------------------------------
# Time warp (speed ramp around the bridge)
# ----------------------------------------------------------------------------
SLOW = (838, 946, 0.78)   # start, end, depth (rate dips to 1-depth)


def rate(f):
    return 1.0 - SLOW[2] * bump(SLOW[0], SLOW[1], f)


def build_tau():
    tau = [0.0]
    for f in range(1, F_END + 40):
        # midpoint integration
        tau.append(tau[-1] + 0.5 * (rate(f - 1) + rate(f)))
    return tau


# ----------------------------------------------------------------------------
# Drone
# ----------------------------------------------------------------------------
def build_drone():
    coll = new_collection("Drone")
    root = bpy.data.objects.new("Drone", None)
    root.empty_display_type = "ARROWS"
    root.rotation_mode = "QUATERNION"
    coll.objects.link(root)

    def mk(name, bm, mats, parent=root, loc=(0, 0, 0), bevel=None, smooth=False):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        ob = bpy.data.objects.new(name, me)
        ob.parent = parent
        ob.location = loc
        coll.objects.link(ob)
        if bevel:
            md = ob.modifiers.new("Bevel", "BEVEL")
            md.width = bevel
            md.segments = 3
            md.limit_method = "ANGLE"
        return ob

    def box_bm(size, c=(0, 0, 0), bm=None, mat=0):
        bm = bm or bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((v.co.x * size[0] + c[0], v.co.y * size[1] + c[1], v.co.z * size[2] + c[2]))
        for f in {fc for v in r["verts"] for fc in v.link_faces}:
            f.material_index = mat
        return bm

    # fuselage: tapered body
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r["verts"]:
        x, y, z = v.co
        taper = 0.75 if y > 0 else 1.0
        v.co = Vector((x * 0.46 * (taper if z > 0 else 1.0), y * 0.86, z * 0.17))
    mk("D_Body", bm, [MATS["carbon"]], bevel=0.05)
    # canopy
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.5)
    for v in bm.verts:
        v.co = Vector((v.co.x * 0.30, v.co.y * 0.62, max(v.co.z, -0.05) * 0.22))
    mk("D_Canopy", bm, [MATS["canopy"]], loc=(0, 0.04, 0.07), smooth=True)
    # LED spine + rear light + front strip
    bm = box_bm((0.03, 0.6, 0.02), (0, -0.02, 0.18))
    box_bm((0.32, 0.02, 0.035), (0, 0.432, 0.0), bm)
    mk("D_LedSpine", bm, [MATS["led_cyan"]])
    bm = box_bm((0.36, 0.02, 0.05), (0, -0.435, 0.0))
    mk("D_LedRear", bm, [MATS["led_red"]])
    # gimbal camera
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=0.085)
    mk("D_Gimbal", bm, [MATS["gunmetal"]], loc=(0, 0.40, -0.12), smooth=True)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=0.04, segments=20)
    for v in bm.verts:
        v.co = Vector((v.co.x, 0.0, v.co.y))
    mk("D_Lens", bm, [MATS["led_white"]], loc=(0, 0.487, -0.12))
    # arms, motors, guards, LED rings, props
    props = []
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
        mx, my = 0.62 * sx, 0.56 * sy
        ang = math.atan2(my, mx)
        L = math.hypot(mx, my)
        bm = box_bm((L, 0.075, 0.045), (L / 2, 0, 0))
        for v in bm.verts:
            v.co = Matrix.Rotation(ang, 3, "Z") @ v.co
        mk(f"D_Arm{i}", bm, [MATS["carbon"]], bevel=0.015)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.075, radius2=0.065, depth=0.11)
        mk(f"D_Motor{i}", bm, [MATS["gunmetal"]], loc=(mx, my, 0.03), smooth=True)
        # guard ring
        bm = bmesh.new()
        ring_r, tube = 0.36, 0.022
        segs, tsegs = 48, 8
        verts = []
        for a in range(segs):
            th = 2 * math.pi * a / segs
            row = []
            for b2 in range(tsegs):
                ph = 2 * math.pi * b2 / tsegs
                rr = ring_r + tube * math.cos(ph)
                row.append(bm.verts.new((rr * math.cos(th), rr * math.sin(th), tube * 1.8 * math.sin(ph))))
            verts.append(row)
        for a in range(segs):
            for b2 in range(tsegs):
                bm.faces.new((verts[a][b2], verts[(a + 1) % segs][b2], verts[(a + 1) % segs][(b2 + 1) % tsegs],
                              verts[a][(b2 + 1) % tsegs]))
        mk(f"D_Guard{i}", bm, [MATS["carbon"]], loc=(mx, my, 0.03), smooth=True)
        bm = bmesh.new()
        verts = []
        for a in range(segs):
            th = 2 * math.pi * a / segs
            verts.append((bm.verts.new((0.385 * math.cos(th), 0.385 * math.sin(th), -0.012)),
                          bm.verts.new((0.385 * math.cos(th), 0.385 * math.sin(th), 0.012))))
        for a in range(segs):
            v0, v1 = verts[a]
            w0, w1 = verts[(a + 1) % segs]
            bm.faces.new((v0, w0, w1, v1))
        mk(f"D_LedRing{i}", bm, [MATS["led_cyan"] if sy > 0 else MATS["led_red"]], loc=(mx, my, 0.03))
        # propeller (two blades)
        bm = bmesh.new()
        for side in (1, -1):
            r2 = bmesh.ops.create_cube(bm, size=1.0)
            for v in r2["verts"]:
                x, y, z = v.co
                v.co = Vector((side * (x * 0.30 + 0.17), y * 0.055 * (1.0 - 0.4 * (x * side + 0.5)), z * 0.008 + 0.01 * y * side))
        p = mk(f"D_Prop{i}", bm, [MATS["prop"]], loc=(mx, my, 0.105))
        p.rotation_mode = "XYZ"
        props.append((p, 1 if (sx * sy) > 0 else -1))
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, radius=0.34, segments=32)
        mk(f"D_PropDisc{i}", bm, [MATS["propdisc"]], loc=(mx, my, 0.105))
    # skids
    for sx in (-1, 1):
        bm = box_bm((0.03, 0.7, 0.03), (sx * 0.22, 0, -0.27))
        box_bm((0.03, 0.03, 0.13), (sx * 0.22, 0.25, -0.2), bm)
        box_bm((0.03, 0.03, 0.13), (sx * 0.22, -0.25, -0.2), bm)
        mk(f"D_Skid{sx}", bm, [MATS["gunmetal"]], bevel=0.008)
    # small under-light so the drone lights nearby surfaces
    ld = bpy.data.lights.new("DroneUnderglow", "POINT")
    ld.energy = 0.0
    ld.color = NEON["cyan"]
    ld.shadow_soft_size = 0.15
    lo = bpy.data.objects.new("DroneUnderglow", ld)
    lo.parent = root
    lo.location = (0, 0, -0.32)
    coll.objects.link(lo)
    return root, props, ld


# ----------------------------------------------------------------------------
# Drone flight path
# ----------------------------------------------------------------------------
class Hermite:
    def __init__(self, samples, zero_vel=()):
        self.t = [s[0] for s in samples]
        self.p = [Vector(s[1]) for s in samples]
        n = len(samples)
        self.m = []
        for i in range(n):
            if i in zero_vel or i == 0 or i == n - 1:
                self.m.append(Vector((0, 0, 0)))
            else:
                self.m.append((self.p[i + 1] - self.p[i - 1]) / (self.t[i + 1] - self.t[i - 1]))

    def __call__(self, t):
        ts = self.t
        if t <= ts[0]:
            return self.p[0].copy()
        if t >= ts[-1]:
            return self.p[-1].copy()
        lo, hi = 0, len(ts) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ts[mid] <= t:
                lo = mid
            else:
                hi = mid
        h = ts[hi] - ts[lo]
        u = (t - ts[lo]) / h
        h00 = 2 * u ** 3 - 3 * u ** 2 + 1
        h10 = u ** 3 - 2 * u ** 2 + u
        h01 = -2 * u ** 3 + 3 * u ** 2
        h11 = u ** 3 - u ** 2
        return h00 * self.p[lo] + h10 * h * self.m[lo] + h01 * self.p[hi] + h11 * h * self.m[hi]


CHASE_V = 1.312      # metres per tau-frame (~31 m/s)
REST = DRONE_REST + Vector((0, 0, 0.33))


def chase_pos(tau):
    s = tau - 528
    y = 150 + CHASE_V * s
    env = smoothstep(528, 590, tau) * (1 - bump(800, 935, tau) * 1.0)
    env *= 1 - 0.6 * smoothstep(930, 990, tau)
    env *= 1 - smoothstep(1035, 1085, tau)
    x = 5.5 * math.sin(2 * math.pi * s / 150) * env
    z = 9.8 + 2.6 * math.sin(2 * math.pi * s / 115) * env - 1.6 * bump(820, 920, tau)
    return Vector((x, y, z))


def drone_path():
    P0 = REST
    samples = [(0, P0), (360, P0), (392, (18.6, 55.0, 50.3)), (418, (14.6, 55.6, 50.7)),
               (438, (9.6, 59.5, 49.2)), (458, (5.6, 72.0, 38.0)), (478, (3.0, 92.0, 22.0)),
               (500, (1.2, 117.0, 12.8)), (528, chase_pos(528))]
    for t in range(540, 1081, 6):
        samples.append((t, chase_pos(t)))
    samples += [(1102, (0, 903.5, 10.6)), (1124, (0, 931.5, 12.8)), (1142, (0, 952, 18.5)),
                (1156, (0, 963.5, 30)), (1172, (0, 968.5, 50)), (1200, (0, 970.5, 86)),
                (1230, (0, 970.5, 122)), (1258, (0, 970.0, 149)), (1280, (0, 969.5, 162.5)),
                (1300, (0, 969.0, 166.8)), (1322, (0, 968.8, 167.6)), (1600, (0, 968.6, 168.0))]
    zero = {1, 2, len(samples) - 1}
    return Hermite(samples, zero_vel=zero)


def gaussian_smooth(vals, sigma):
    if sigma <= 0:
        return list(vals)
    r = int(sigma * 3)
    w = [math.exp(-0.5 * (i / sigma) ** 2) for i in range(-r, r + 1)]
    out = []
    n = len(vals)
    for i in range(n):
        acc, ws = 0.0, 0.0
        for j, wj in enumerate(w):
            k = min(n - 1, max(0, i + j - r))
            acc += vals[k] * wj
            ws += wj
        out.append(acc / ws)
    return out


def compute_drone(tau):
    path = drone_path()
    N = F_END + 30
    P = [path(tau[f]) for f in range(N)]
    # hover bob at the end
    for f in range(N):
        t = tau[f]
        k = smoothstep(1295, 1330, t)
        P[f] = P[f] + Vector((0.05 * math.sin(f * 0.11), 0.0, 0.07 * math.sin(f * 0.17))) * k
    V = [Vector((0, 0, 0))] * N
    A = [Vector((0, 0, 0))] * N
    for f in range(1, N - 1):
        dt = max(1e-3, (tau[f + 1] - tau[f - 1]) / 2)
        V[f] = (P[f + 1] - P[f - 1]) / (2 * dt)
    for f in range(1, N - 1):
        dt = max(1e-3, (tau[f + 1] - tau[f - 1]) / 2)
        A[f] = (V[f + 1] - V[f - 1]) / (2 * dt)
    yaw, pitch, roll = [], [], []
    cur = math.pi / 2
    for f in range(N):
        t = tau[f]
        v, a = V[f], A[f]
        vh = math.hypot(v.x, v.y)
        if vh > 0.25 and t > 400:
            target = math.atan2(-v.x, v.y)
            while target - cur > math.pi:
                target -= 2 * math.pi
            while target - cur < -math.pi:
                target += 2 * math.pi
            cur = target
        if t >= 1150:
            cur_override = lerp(0.0, -math.pi, smootherstep(1305, 1375, t))
            cur = cur_override
        yaw.append(cur)
        fwd = Vector((-math.sin(cur), math.cos(cur), 0))
        right = Vector((math.cos(cur), math.sin(cur), 0))
        af = a.dot(fwd)
        ar = a.dot(right)
        vf = v.dot(fwd)
        pitch.append(-math.atan(0.30 * vf + 35.0 * af))
        roll.append(math.atan(45.0 * ar))
    yaw = gaussian_smooth(yaw, 3)
    pitch = gaussian_smooth(pitch, 4)
    roll = gaussian_smooth(roll, 4)
    # barrel roll under the bridge
    for f in range(N):
        roll[f] += 2 * math.pi * smootherstep(852, 884, tau[f])
    # idle wobble during hover
    Q = []
    for f in range(N):
        q = (Matrix.Rotation(yaw[f], 3, "Z") @ Matrix.Rotation(pitch[f], 3, "X") @ Matrix.Rotation(roll[f], 3, "Y")).to_quaternion()
        if Q and Q[-1].dot(q) < 0:
            q.negate()
        Q.append(q)
    return P, Q, V, roll


def animate_drone(root, props, light, P, Q, tau):
    for f in range(F_START - 2, F_END + 3):
        ff = max(0, f)
        root.location = P[ff]
        root.rotation_quaternion = Q[ff]
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_quaternion", frame=f)
    # props spin
    ang = [0.0] * 4
    for f in range(F_START, F_END + 3):
        t = tau[f]
        spin = math.radians(38.0) * smoothstep(296, 345, t)
        idle = math.radians(5.0) * smoothstep(270, 300, t)
        dtau = tau[f] - tau[f - 1] if f > 0 else 1.0
        for i, (p, d) in enumerate(props):
            ang[i] += d * (spin + idle) * dtau
            p.rotation_euler = (0, 0, ang[i] + i * 0.7)
            p.keyframe_insert("rotation_euler", index=2, frame=f)
    # prop discs fade in when spinning
    pd = MATS["propdisc"].node_tree.nodes["Principled BSDF"].inputs["Alpha"]
    for f, a in ((0, 0.0), (300, 0.0), (345, 0.22), (F_END, 0.22)):
        pd.default_value = a
        pd.keyframe_insert("default_value", frame=f)
    # LED power on with stutter
    keys = [(0, 0.0), (236, 0.0), (237, 6.0), (239, 0.0), (242, 9.0), (243, 1.0), (246, 14.0), (262, 14.0)]
    for mname, scale in (("led_cyan", 1.0), ("led_red", 0.45), ("led_white", 0.4)):
        s = MATS[mname].node_tree.nodes[MATS[mname]["emit_node"]].inputs["Strength"]
        for f, v in keys:
            s.default_value = v * scale
            s.keyframe_insert("default_value", frame=f)
        s.keyframe_insert("default_value", frame=F_END)
    set_constant_interp([MATS["led_cyan"], MATS["led_red"], MATS["led_white"]])
    for f, e in ((0, 0.0), (241, 0.0), (246, 25.0), (F_END, 25.0)):
        light.energy = e
        light.keyframe_insert("energy", frame=f)


# ----------------------------------------------------------------------------
# Cameras
# ----------------------------------------------------------------------------
SHOTS = [  # name, start, end(excl)
    ("S1_Establish", 0, 192),
    ("S2_Rooftop", 192, 360),
    ("S3_Dive", 360, 528),
    ("S4a_Chase", 528, 672),
    ("S4b_Track", 672, 816),
    ("S5_Bridge", 816, 960),
    ("S6_HeadOn", 960, 1128),
    ("S7_Ascent", 1128, 1344),
    ("S8_Reveal", 1344, 1488),
]


def look_quat(cam, tgt, roll=0.0):
    d = (Vector(tgt) - Vector(cam))
    q = d.to_track_quat("-Z", "Y")
    if roll:
        q = q @ Quaternion((0, 0, 1), roll)
    return q


def shake(f, amp, freq=0.06, seed=0.0):
    if amp == 0:
        return Quaternion()
    p = amp * noise.noise(Vector((f * freq, seed, 0.3)))
    y = amp * noise.noise(Vector((seed + 11.0, f * freq, 1.7)))
    r = 0.5 * amp * noise.noise(Vector((2.3, seed + 5.0, f * freq)))
    return Euler((p, y, r)).to_quaternion()


def spring_follow(frames, desired, k):
    out = {}
    cur = None
    for f in frames:
        d = desired(f)
        cur = d.copy() if cur is None else cur + (d - cur) * k
        out[f] = cur.copy()
    return out


def spring_follow_rel(frames, desired, anchor, k):
    out = {}
    cur = None
    for f in frames:
        off = desired(f) - anchor(f)
        cur = off.copy() if cur is None else cur + (off - cur) * k
        out[f] = anchor(f) + cur
    return out


def make_camera(name, coll):
    cd = bpy.data.cameras.new(name)
    cd.sensor_width = 36.0
    cd.clip_start = 0.05
    cd.clip_end = 6000
    cd.dof.use_dof = True
    ob = bpy.data.objects.new(name, cd)
    ob.rotation_mode = "QUATERNION"
    coll.objects.link(ob)
    return ob


def key_cam(ob, f, loc, quat, lens, focus, fstop, prev):
    ob.location = loc
    q = quat.copy()
    if prev is not None and prev.dot(q) < 0:
        q.negate()
    ob.rotation_quaternion = q
    ob.data.lens = lens
    ob.data.dof.focus_distance = max(0.1, focus)
    ob.data.dof.aperture_fstop = fstop
    ob.keyframe_insert("location", frame=f)
    ob.keyframe_insert("rotation_quaternion", frame=f)
    ob.data.keyframe_insert("lens", frame=f)
    ob.data.dof.keyframe_insert("focus_distance", frame=f)
    ob.data.dof.keyframe_insert("aperture_fstop", frame=f)
    return q


def build_cameras(scene, P, V, roll, tau):
    coll = new_collection("Cameras")
    cams = {}
    D = lambda f: P[max(0, min(len(P) - 1, f))]
    Vel = lambda f: V[max(0, min(len(V) - 1, f))]

    for name, s, e in SHOTS:
        cams[name] = make_camera(name, coll)

    def run(name, s, e, fn):
        ob = cams[name]
        prev = None
        for f in range(s - 2, e + 3):
            loc, tgt, lens, fstop, focus, rl, shk = fn(f)
            q = look_quat(loc, tgt, rl) @ shk
            prev = key_cam(ob, f, loc, q, lens, focus, fstop, prev)

    # S1 — establishing crane descending over the avenue
    def s1(f):
        u = smootherstep(-20, 215, f)
        loc = Vector((lerp(-6, -2.5, u), lerp(-470, -215, u), lerp(310, 88, u)))
        tgt = Vector((lerp(0, 0, u), lerp(990, 420, u), lerp(150, 40, u)))
        return loc, tgt, lerp(30, 30, u), 11.0, 400.0, math.radians(lerp(-4.0, 0.5, u)), shake(f, 0.002, 0.03, 1)
    run("S1_Establish", 0, 192, s1)

    # S2 — rooftop macro, rack focus from city bokeh to the drone
    def s2(f):
        u = smootherstep(185, 365, f)
        a = math.radians(lerp(40, 16, u))
        R = lerp(4.8, 3.0, u)
        hgt = lerp(0.75, 0.42, u)
        d0 = D(0)
        loc = d0 + Vector((R * math.cos(a), R * math.sin(a), hgt))
        tgt = d0 + Vector((-0.35, 0.0, 0.05))
        dist = (d0 - loc).length
        rk = smootherstep(212, 250, f)
        focus = lerp(70.0, dist, rk)
        return loc, tgt, 50.0, 1.8, focus, math.radians(-1.0), shake(f, 0.0025, 0.05, 2)
    run("S2_Rooftop", 192, 360, s2)

    # S3 — take-off and dive over the edge (spring follow)
    frames = list(range(330, 534))
    def s3_des(f):
        d = D(f)
        if f < 405:
            return D(0) + Vector((3.2, 1.4, 1.0)) + Vector((0, 0, 1.0)) * smoothstep(360, 405, f)
        v = Vel(f)
        dirv = v.normalized() if v.length > 1e-4 else Vector((0, 1, 0))
        back = 4.5 * smoothstep(405, 450, f) + 0.5
        return d - dirv * back + Vector((0, 0, 2.6))
    pos3 = spring_follow_rel(frames, s3_des, D, 0.09)
    tgt3 = spring_follow_rel(frames, lambda f: D(f) + Vel(f) * 4.0, D, 0.35)
    def s3(f):
        loc = pos3[f]
        tgt = tgt3[f]
        rl = -0.6 * roll[max(0, f)] if f > 420 else 0.0
        rl += math.radians(8) * bump(440, 520, f)
        lens = lerp(30, 22, smoothstep(400, 460, f))
        return loc, tgt, lens, 4.0, (D(f) - loc).length, rl, shake(f, 0.004 + 0.006 * smoothstep(430, 470, f), 0.09, 3)
    run("S3_Dive", 360, 528, s3)

    # S4a — high-speed chase
    frames = list(range(490, 680))
    def chase_des(f, back, up, side=0.0):
        d = D(f)
        v = Vel(f)
        dirv = v.normalized() if v.length > 1e-4 else Vector((0, 1, 0))
        rgt = dirv.cross(Vector((0, 0, 1))).normalized()
        return d - dirv * back + Vector((0, 0, up)) + rgt * side
    pos4 = spring_follow_rel(frames, lambda f: chase_des(f, 3.9, 0.95, 0.5), D, 0.12)
    tgt4 = spring_follow_rel(frames, lambda f: D(f) + Vel(f) * 4.0 + Vector((0, 0, 0.2)), D, 0.3)
    def s4a(f):
        loc = pos4[f]
        rl = -0.35 * (roll[f] if f < len(roll) else 0)
        return loc, tgt4[f], 24.0, 5.6, (D(f) - loc).length, rl, shake(f, 0.006, 0.12, 4)
    run("S4a_Chase", 528, 672, s4a)

    # S4b — side tracking with long lens and parallax
    frames = list(range(640, 830))
    pos4b = spring_follow_rel(frames, lambda f: Vector((10.4, D(f).y - 3.5 + 2.5 * smoothstep(672, 816, f), D(f).z + 0.4)), D, 0.25)
    def s4b(f):
        loc = pos4b[f]
        tgt = D(f) + Vector((0, 1.2, 0.05))
        return loc, tgt, 38.0, 2.4, (D(f) - loc).length, math.radians(1.5), shake(f, 0.004, 0.1, 5)
    run("S4b_Track", 672, 816, s4b)

    # S5 — bridge, slow-motion barrel roll
    frames = list(range(780, 970))
    pos5 = spring_follow_rel(frames, lambda f: chase_des(f, 4.6 - 1.6 * bump(840, 940, f), 0.65, -0.35), D, 0.15)
    tgt5 = spring_follow_rel(frames, lambda f: D(f) + Vel(f) * 3.0, D, 0.3)
    camroll = gaussian_smooth([roll[min(f, len(roll) - 1)] for f in range(len(roll))], 6)
    def s5(f):
        loc = pos5[f]
        rl = -0.45 * (camroll[f] - 2 * math.pi * smootherstep(852, 884, tau[f]))
        rl += -2 * math.pi * smootherstep(849, 906, tau[f])
        return loc, tgt5[f], 26.0, 4.0, (D(f) - loc).length, rl, shake(f, 0.005, 0.1, 6)
    run("S5_Bridge", 816, 960, s5)

    # S6 — head-on: camera flies backward ahead of the drone, drone passes, whip-pan
    f0 = 950
    y_start = D(f0).y + 20.0
    def cam_y(f):
        # camera speed: slightly slower than drone, then brakes after the pass
        y = y_start
        for k in range(f0, f):
            vv = 1.18 if k < 1072 else lerp(1.18, 0.35, smoothstep(1072, 1100, k))
            y += vv * (tau[k + 1] - tau[k])
        return y
    cy_cache = {}
    yv = y_start
    for k in range(f0, 1135):
        cy_cache[k] = yv
        vv = 1.152 if k < 1070 else lerp(1.152, 0.30, smoothstep(1070, 1098, k))
        yv += vv * (tau[k + 1] - tau[k])
    smooth_xz = spring_follow(list(range(f0, 1135)), lambda f: Vector((D(f).x + 1.9, 0, D(f).z + 1.0)), 0.12)
    tgt6 = spring_follow(list(range(f0, 1135)),
                         lambda f: D(f) + Vector((0, 0, 0.1)) + Vector((0, 18.0, 4.0)) * smoothstep(1076, 1100, f), 0.55)
    def s6(f):
        sx = smooth_xz[f]
        loc = Vector((sx.x, cy_cache[f], sx.z))
        return loc, tgt6[f], 30.0, 3.2, max(0.5, (D(f) - loc).length), math.radians(-2) * bump(1060, 1100, f), shake(f, 0.005, 0.1, 7)
    run("S6_HeadOn", 960, 1128, s6)

    # S7 — ascent: worm's-eye start, then crane up orbiting the climbing drone
    frames = list(range(1120, 1352))
    worm = Vector((-6.0, 900.0, 3.0))
    def s7_orbit(f):
        th = math.radians(lerp(-35, 28, smootherstep(1150, 1344, f)))
        R = lerp(8.5, 5.5, smootherstep(1150, 1344, f))
        d = D(f)
        return Vector((R * math.sin(th), d.y - R * math.cos(th), d.z - 1.6))
    orbit7 = spring_follow_rel(frames, s7_orbit, D, 0.12)
    tgt7 = spring_follow_rel(frames, lambda f: D(f) + Vector((0, 0, 0.6)), D, 0.3)
    def s7(f):
        w = smootherstep(1140, 1185, f)
        loc = worm.lerp(orbit7[f], w)
        lens = lerp(20, 30, smootherstep(1140, 1220, f))
        return loc, tgt7[f], lens, 4.0, (D(f) - loc).length, math.radians(lerp(4, -2, smoothstep(1128, 1344, f))), shake(f, 0.004, 0.07, 8)
    run("S7_Ascent", 1128, 1344, s7)

    # S8 — the reveal: pull back from the drone to the whole city
    def s8(f):
        u = smootherstep(1362, 1500, f) ** 1.25
        d = D(f)
        near = d + Vector((1.3, -4.6, 0.35)) + Vector((0.3, -1.2, 0.1)) * smoothstep(1344, 1365, f)
        far = Vector((-5.0, 640.0, 226.0))
        loc = near.lerp(far, u)
        tgt = (d + Vector((0, 0, 0.2))).lerp(Vector((0, 990, 150)), smootherstep(1366, 1480, f))
        lens = lerp(42, 26, smootherstep(1344, 1470, f))
        focus = (d - loc).length
        fst = lerp(2.8, 8.0, smoothstep(1344, 1420, f))
        return loc, tgt, lens, fst, focus, math.radians(lerp(-1.5, 1.0, u)), shake(f, 0.0025, 0.05, 9)
    run("S8_Reveal", 1344, 1488, s8)

    # bind cameras with markers
    for name, s, e in SHOTS:
        mk = scene.timeline_markers.new(name, frame=s)
        mk.camera = cams[name]
    scene.camera = cams["S1_Establish"]
    return cams


# ----------------------------------------------------------------------------
# Rain (one wrapped rain field per camera)
# ----------------------------------------------------------------------------
def rain_group():
    ng = bpy.data.node_groups.new("RainField", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    st = ng.interface.new_socket(name="Time", in_out="INPUT", socket_type="NodeSocketFloat")
    so = ng.interface.new_socket(name="Camera", in_out="INPUT", socket_type="NodeSocketObject")
    N = ng.nodes
    L = ng.links
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    half = Vector((26.0, 26.0, 15.0))
    pts = N.new("GeometryNodePoints")
    pts.inputs["Count"].default_value = 11000
    rv = N.new("FunctionNodeRandomValue")
    rv.data_type = "FLOAT_VECTOR"
    sock(rv, "Min").default_value = -half
    sock(rv, "Max").default_value = half
    rv.inputs["Seed"].default_value = 3
    oi = N.new("GeometryNodeObjectInfo")
    oi.transform_space = "ORIGINAL"
    L.new(gi.outputs["Camera"], oi.inputs["Object"])
    fall = N.new("ShaderNodeVectorMath")
    fall.operation = "SCALE"
    fall.inputs[0].default_value = (1.2, 0.6, -10.5)  # wind + fall speed (m/s)
    L.new(gi.outputs["Time"], fall.inputs["Scale"])
    add = N.new("ShaderNodeVectorMath"); add.operation = "ADD"
    L.new([o for o in rv.outputs if o.type == "VECTOR" and not o.is_unavailable][0], add.inputs[0])
    L.new(fall.outputs[0], add.inputs[1])
    # bias the box forward of the camera a little (most rain is in front)
    sub = N.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"
    L.new(add.outputs[0], sub.inputs[0])
    L.new(oi.outputs["Location"], sub.inputs[1])
    wrap = N.new("ShaderNodeVectorMath"); wrap.operation = "WRAP"
    L.new(sub.outputs[0], wrap.inputs[0])
    wrap.inputs[1].default_value = half
    wrap.inputs[2].default_value = -half
    add2 = N.new("ShaderNodeVectorMath"); add2.operation = "ADD"
    L.new(wrap.outputs[0], add2.inputs[0])
    L.new(oi.outputs["Location"], add2.inputs[1])
    L.new(add2.outputs[0], pts.inputs["Position"])
    cyl = N.new("GeometryNodeMeshCylinder")
    cyl.inputs["Vertices"].default_value = 3
    cyl.inputs["Radius"].default_value = 0.0045
    cyl.inputs["Depth"].default_value = 0.62
    iop = N.new("GeometryNodeInstanceOnPoints")
    L.new(pts.outputs["Points"], iop.inputs["Points"])
    L.new(cyl.outputs["Mesh"], iop.inputs["Instance"])
    iop.inputs["Rotation"].default_value = (math.atan2(0.6, 10.5), -math.atan2(1.2, 10.5), 0)
    sm = N.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = MATS["rain"]
    L.new(iop.outputs["Instances"], sm.inputs["Geometry"])
    L.new(sm.outputs["Geometry"], go.inputs["Geometry"])
    ident = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
    return ng, ident


def build_rain(cams, tau):
    coll = new_collection("Rain")
    ng, ident = rain_group()
    for name, s, e in SHOTS:
        me = bpy.data.meshes.new("RainSrc")
        ob = bpy.data.objects.new("Rain_" + name, me)
        coll.objects.link(ob)
        md = ob.modifiers.new("Rain", "NODES")
        md.node_group = ng
        inputs = md.properties.inputs
        getattr(inputs, ident["Camera"]).value = cams[name]
        tsock = getattr(inputs, ident["Time"])
        for attr in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
            setattr(ob, attr, False)
        try:
            ob.cycles.use_motion_blur = False
        except Exception:
            pass
        path = tsock.path_from_id("value")
        for f in range(s - 3, e + 4):
            tsock.value = tau[max(0, f)] / FPS
            ob.keyframe_insert(path, frame=f)
        # only render while its camera is active
        for f, hide in ((0, True), (s - 1, True), (s, False), (e, True)):
            if f < 0:
                continue
            ob.hide_render = hide
            ob.keyframe_insert("hide_render", frame=f)
        ob.hide_viewport = False


# ----------------------------------------------------------------------------
# World, render settings, compositor
# ----------------------------------------------------------------------------
FOG = (0.035, 0.022, 0.06)


def build_world(scene):
    w = bpy.data.worlds.new("NightSky")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree
    nt.nodes.clear()
    b = NB(nt)
    out = b.new("ShaderNodeOutputWorld")
    tc = b.new("ShaderNodeTexCoord")
    _, _, z = b.sep(tc.outputs["Generated"])
    col = b.ramp(z, [(0.0, (0.02, 0.012, 0.03)), (0.5, (0.09, 0.04, 0.10)), (0.56, (0.05, 0.025, 0.07)),
                      (0.75, (0.012, 0.01, 0.025)), (1.0, (0.003, 0.004, 0.01))])
    bg = b.new("ShaderNodeBackground")
    b.link_or_set(bg.inputs["Color"], col)
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    w.mist_settings.start = 15.0
    w.mist_settings.depth = 650.0
    w.mist_settings.falloff = "QUADRATIC"
    # faint moonlight for form
    sd = bpy.data.lights.new("Moon", "SUN")
    sd.energy = 0.06
    sd.color = (0.55, 0.65, 1.0)
    sd.angle = math.radians(2)
    so = bpy.data.objects.new("Moon", sd)
    so.rotation_euler = (math.radians(55), 0, math.radians(-30))
    scene.collection.objects.link(so)


def build_compositor(scene):
    ng = bpy.data.node_groups.new("NeonComp", "CompositorNodeTree")
    scene.compositing_node_group = ng
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers")
    rl.scene = scene
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["To Max"].default_value = 0.88
    L.new(rl.outputs["Mist"], mr.inputs["Value"])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(mr.outputs[0], sock(mix, "Factor_Float"))
    L.new(rl.outputs["Image"], sock(mix, "A_Color"))
    sock(mix, "B_Color").default_value = (*FOG, 1)
    gl = N.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Quality"].default_value = "High"
    gl.inputs["Threshold"].default_value = 0.85
    gl.inputs["Strength"].default_value = 0.55
    gl.inputs["Size"].default_value = 0.8
    L.new(sock(mix, "Result_Color", out=True), gl.inputs["Image"])
    ld = N.new("CompositorNodeLensdist")
    ld.inputs["Dispersion"].default_value = 0.018
    ld.inputs["Distortion"].default_value = -0.012
    L.new(gl.outputs["Image"], ld.inputs["Image"])
    go = N.new("NodeGroupOutput")
    L.new(ld.outputs["Image"], go.inputs[0])
    scene.render.use_compositing = True


def render_settings(scene):
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = 1600, 670     # 2.39:1 scope; upscaled + letterboxed to 1920x1080
    r.resolution_percentage = 100
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    r.use_persistent_data = True
    r.film_transparent = False
    r.filepath = "//frames/nr_"
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    c = scene.cycles
    c.device = "CPU"
    c.samples = 12
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.05
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    c.max_bounces = 4
    c.diffuse_bounces = 1
    c.glossy_bounces = 2
    c.transmission_bounces = 2
    c.transparent_max_bounces = 4
    c.volume_bounces = 0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 6.0
    c.blur_glossy = 1.0
    try:
        c.use_light_tree = False
    except Exception:
        pass
    scene.view_layers[0].use_pass_mist = True
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Punchy", "Punchy", "AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except Exception:
            continue
    vs.exposure = 0.35
    # EEVEE settings for users rendering on a GPU
    ee = scene.eevee
    for k, v in (("use_raytracing", True), ("taa_render_samples", 64), ("use_shadows", True)):
        if hasattr(ee, k):
            try:
                setattr(ee, k, v)
            except Exception:
                pass


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.join(HERE, "neon_rush.blend")
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    scene = reset_scene()
    fonts = {"bold": bpy.data.fonts.load(FONT_BOLD), "display": bpy.data.fonts.load(FONT_DISPLAY)}
    for ft in fonts.values():
        try:
            ft.pack()
        except Exception as e:
            print("font pack failed", e)
    build_materials()
    tau = build_tau()
    scene["tau"] = 0.0
    for f in range(F_START - 2, F_END + 3):
        scene["tau"] = tau[max(0, f)]
        scene.keyframe_insert('["tau"]', frame=f)
    build_city(fonts)
    build_gate_sign(fonts)
    build_traffic(scene)
    build_pedestrians(scene)
    build_blimps()
    root, props, light = build_drone()
    P, Q, V, roll = compute_drone(tau)
    animate_drone(root, props, light, P, Q, tau)
    cams = build_cameras(scene, P, V, roll, tau)
    build_rain(cams, tau)
    build_world(scene)
    render_settings(scene)
    build_compositor(scene)
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
