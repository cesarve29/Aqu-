"""
JARDÍN LUMEN — one-take FPV cinematic flight for Blender 5.3
=============================================================

A first-person aerial camera dives into a mossy rock gorge, threads it at speed,
bursts into a hidden crater garden of ~100k bioluminescent flowers (neon blue and
pink) and slows down in front of a sleeping moss-and-flower covered stone golem.

Everything is generated from code (no external assets):

    blender -b --factory-startup -P build_garden.py            # -> lumen_garden.blend

Timeline: 24 fps, frames 0..1439 (60 s), one continuous shot.
"""

import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Quaternion, Matrix, Euler, noise, kdtree

FPS = 24
F_START, F_END = 0, 1439
HERE = os.path.dirname(os.path.abspath(__file__))
RNG = random.Random(7)

C_CRATER = Vector((0.0, 120.0))
R_CRATER = 130.0
GORGE_Y0, GORGE_Y1 = -360.0, -4.0
GOLEM_POS = Vector((0.0, 236.0, 0.0))
GS = 1.25                                  # golem scale
FACE = Vector((0.0, 236.0 - 2.0 * GS, 28.0 * GS))   # point the final shot looks at
WATER_Z = -0.05
WAVE_T0, WAVE_SPEED = 21.5, 34.0           # reveal glow wave (s, m/s)

# zone colour ramp (0 = blue, 1 = pink) shared by shaders and lights
ZONE_RAMP = [(0.00, (0.02, 0.10, 1.00)), (0.28, (0.00, 0.70, 1.00)), (0.44, (0.22, 0.12, 1.00)),
             (0.56, (0.85, 0.06, 0.90)), (0.76, (1.00, 0.06, 0.42)), (1.00, (1.00, 0.30, 0.70))]


# ----------------------------------------------------------------------------
# small math helpers
# ----------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoothstep(a, b, x):
    if a == b:
        return 1.0 if x >= b else 0.0
    t = clamp((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def smootherstep(a, b, x):
    t = clamp((x - a) / (b - a))
    return t * t * t * (t * (t * 6 - 15) + 10)


def bump(a, b, x):
    if x <= a or x >= b:
        return 0.0
    return math.sin(math.pi * (x - a) / (b - a)) ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def fbm(x, y, z=0.0, oct=4):
    return noise.fractal(Vector((x, y, z)), 0.55, 2.0, oct, noise_basis="PERLIN_ORIGINAL")


def n1(x, y=0.0, z=0.0):
    return noise.noise(Vector((x, y, z)), noise_basis="PERLIN_ORIGINAL")


def ramp_color(stops, t):
    t = clamp(t)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            u = (t - p0) / max(1e-6, p1 - p0)
            return tuple(lerp(a, b, u) for a, b in zip(c0, c1))
    return stops[-1][1]


def zone_at(x, y):
    """0 = blue/cyan, 1 = pink/magenta; big soft patches + a pink halo near the golem."""
    z = 0.5 + 0.95 * n1(x * 0.016 + 3.1, y * 0.016 - 1.7, 0.4) + 0.25 * n1(x * 0.06, y * 0.06, 5.0)
    gd = math.hypot(x - GOLEM_POS.x, y - (GOLEM_POS.y - 20))
    z += 0.25 * (1 - smoothstep(10, 45, gd))
    return clamp(z)


# ----------------------------------------------------------------------------
# node helpers
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
    def __init__(self, nt):
        self.nt = nt

    def new(self, t, **kw):
        n = self.nt.nodes.new(t)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def set(self, s, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, s)
        elif v is not None:
            if isinstance(v, (tuple, list)) and len(v) == 3 and s.type == "RGBA":
                v = (*v, 1.0)
            s.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        m = self.new("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        if c is not None:
            self.set(m.inputs[2], c)
        return m.outputs[0]

    def vmath(self, op, a, b=None):
        m = self.new("ShaderNodeVectorMath", operation=op)
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        return m.outputs[1] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else m.outputs[0]

    def mix(self, fac, a, b):
        m = self.new("ShaderNodeMix", data_type="RGBA")
        self.set(sock(m, "Factor_Float"), fac)
        self.set(sock(m, "A_Color"), a)
        self.set(sock(m, "B_Color"), b)
        return sock(m, "Result_Color", out=True)

    def sep(self, v):
        s = self.new("ShaderNodeSeparateXYZ")
        self.set(s.inputs[0], v)
        return s.outputs

    def comb(self, x, y, z):
        c = self.new("ShaderNodeCombineXYZ")
        self.set(c.inputs[0], x)
        self.set(c.inputs[1], y)
        self.set(c.inputs[2], z)
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
        self.set(r.inputs[0], fac)
        return r.outputs[0]

    def noise(self, vec, scale, detail=3.0, rough=0.55, dim="3D", w=None):
        n = self.new("ShaderNodeTexNoise", noise_dimensions=dim)
        self.set(n.inputs["Vector"], vec)
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        if w is not None:
            self.set(n.inputs["W"], w)
        return n

    def time(self):
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


def new_collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(ob, coll):
    coll.objects.link(ob)
    return ob


def mesh_object(name, verts, faces, coll, mats=(), mat_idx=None, smooth=True, attrs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(clean_customdata=False)
    for m in mats:
        me.materials.append(m)
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", mat_idx)
    if smooth:
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    for k, vals in (attrs or {}).items():
        a = me.attributes.new(k, "FLOAT", "POINT")
        a.data.foreach_set("value", vals)
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
MATS = {}


def rock_moss_material(name, moss_amount, glow_specks):
    m, nt, out = new_material(name)
    b = NB(nt)
    geo = b.new("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    nrm = geo.outputs["Normal"]
    _, _, nz = b.sep(nrm)
    big = b.noise(pos, 0.12, 2.0, 0.6)
    mid = b.noise(pos, 0.9, 3.0, 0.6)
    fine = b.noise(pos, 6.0, 1.0, 0.6)
    # strata bands in the rock
    wave = b.new("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    b.set(wave.inputs["Vector"], pos)
    wave.inputs["Scale"].default_value = 0.18
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 1.0
    rock_col = b.ramp(b.math("ADD", b.math("MULTIPLY", mid.outputs["Fac"], 0.7), b.math("MULTIPLY", wave.outputs["Fac"], 0.3)),
                      [(0.25, (0.030, 0.029, 0.031)), (0.55, (0.075, 0.068, 0.062)), (0.8, (0.13, 0.12, 0.11))])
    # moss mask: up-facing + noisy patches that creep down walls
    mr = b.new("ShaderNodeMapRange")
    b.set(mr.inputs["Value"], nz)
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = 0.8
    patch = b.math("MULTIPLY", b.math("SUBTRACT", big.outputs["Fac"], 0.42), 2.6)
    moss_f = b.math("ADD", b.math("ADD", mr.outputs[0], patch), moss_amount - 0.35, clamp=True)
    moss_f = b.math("MULTIPLY", b.math("SUBTRACT", moss_f, 0.35), 2.2, clamp=True)
    moss_col = b.ramp(fine.outputs["Fac"], [(0.3, (0.012, 0.045, 0.010)), (0.55, (0.035, 0.11, 0.020)),
                                            (0.75, (0.08, 0.16, 0.035))])
    col = b.mix(moss_f, rock_col, moss_col)
    p = b.new("ShaderNodeBsdfPrincipled")
    b.set(p.inputs["Base Color"], col)
    b.set(p.inputs["Roughness"], b.math("ADD", b.math("MULTIPLY", moss_f, 0.25), 0.62))
    p.inputs["Sheen Weight"].default_value = 0.0
    b.set(p.inputs["Sheen Weight"], b.math("MULTIPLY", moss_f, 0.8))
    p.inputs["Sheen Tint"].default_value = (0.35, 0.8, 0.5, 1)
    # bump: chunky rock + fuzzy moss
    bh = b.math("ADD", b.math("MULTIPLY", mid.outputs["Fac"], 1.0),
                b.math("MULTIPLY", fine.outputs["Fac"], b.math("ADD", b.math("MULTIPLY", moss_f, 0.6), 0.25)))
    bp = b.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.55
    bp.inputs["Distance"].default_value = 0.25
    b.set(bp.inputs["Height"], bh)
    b.set(p.inputs["Normal"], bp.outputs[0])
    if glow_specks:
        vor = b.new("ShaderNodeTexVoronoi", feature="F1")
        b.set(vor.inputs["Vector"], pos)
        vor.inputs["Scale"].default_value = 7.0
        dist = vor.outputs["Distance"]
        sc = b.new("ShaderNodeSeparateColor")
        b.set(sc.inputs[0], vor.outputs["Color"])
        dot = b.math("LESS_THAN", dist, 0.07)
        sel = b.math("GREATER_THAN", sc.outputs[0], 0.85)
        speck = b.math("MULTIPLY", b.math("MULTIPLY", dot, sel), moss_f)
        speck_col = b.mix(sc.outputs[1], (0.0, 0.75, 1.0), (1.0, 0.15, 0.6))
        b.set(p.inputs["Emission Color"], speck_col)
        b.set(p.inputs["Emission Strength"], b.math("MULTIPLY", speck, 3.0))
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def ground_material():
    m, nt, out = new_material("Ground")
    b = NB(nt)
    geo = b.new("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    n_a = b.noise(pos, 0.25, 4.0, 0.6)
    n_b = b.noise(pos, 3.0, 3.0, 0.6)
    col = b.ramp(b.math("ADD", b.math("MULTIPLY", n_a.outputs["Fac"], 0.6), b.math("MULTIPLY", n_b.outputs["Fac"], 0.4)),
                 [(0.3, (0.012, 0.012, 0.012)), (0.5, (0.02, 0.05, 0.015)), (0.7, (0.05, 0.10, 0.03))])
    _, _, z = b.sep(pos)
    wet = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", b.math("SUBTRACT", z, WATER_Z), 4.0, clamp=True), clamp=True)
    p = b.new("ShaderNodeBsdfPrincipled")
    b.set(p.inputs["Base Color"], col)
    b.set(p.inputs["Roughness"], b.math("SUBTRACT", 0.85, b.math("MULTIPLY", wet, 0.6)))
    bp = b.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.4
    b.set(bp.inputs["Height"], n_b.outputs["Fac"])
    b.set(p.inputs["Normal"], bp.outputs[0])
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def water_material():
    m, nt, out = new_material("Water")
    b = NB(nt)
    geo = b.new("ShaderNodeNewGeometry")
    t = b.time()
    n = b.noise(geo.outputs["Position"], 1.6, 2.0, 0.5, dim="4D", w=b.math("MULTIPLY", t, 0.35))
    bp = b.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.06
    b.set(bp.inputs["Height"], n.outputs["Fac"])
    p = b.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.004, 0.006, 0.008, 1)
    p.inputs["Roughness"].default_value = 0.03
    p.inputs["IOR"].default_value = 1.33
    b.set(p.inputs["Normal"], bp.outputs[0])
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def glow_shader(b, base_strength, rim=True, wave=True, sat_boost=1.0, darken=0.25):
    """Emission colour from the instance 'zone' attribute + twinkle + reveal wave."""
    attr = b.new("ShaderNodeAttribute", attribute_type="INSTANCER", attribute_name="zone")
    oi = b.new("ShaderNodeObjectInfo")
    zone = b.math("ADD", attr.outputs["Fac"], b.math("MULTIPLY", b.math("SUBTRACT", oi.outputs["Random"], 0.5), 0.16))
    col = b.ramp(zone, ZONE_RAMP)
    t = b.time()
    tw = b.math("ADD", 0.85, b.math("MULTIPLY", 0.15, b.math("SINE", b.math("ADD", b.math("MULTIPLY", t, 2.1),
                                                                           b.math("MULTIPLY", oi.outputs["Random"], 40.0)))))
    strength = b.math("MULTIPLY", tw, b.math("ADD", base_strength * 0.7, b.math("MULTIPLY", oi.outputs["Random"], base_strength * 0.6)))
    if wave:
        loc = oi.outputs["Location"]
        lx, ly, _ = b.sep(loc)
        d = b.vmath("LENGTH", b.comb(lx, b.math("SUBTRACT", ly, -8.0), 0.0))
        r = b.math("MULTIPLY", b.math("SUBTRACT", t, WAVE_T0), WAVE_SPEED)
        g = b.math("EXPONENT", b.math("MULTIPLY", b.math("POWER", b.math("SUBTRACT", d, r), 2.0), -1.0 / 120.0))
        on = b.math("GREATER_THAN", t, WAVE_T0)
        strength = b.math("MULTIPLY", strength, b.math("ADD", 1.0, b.math("MULTIPLY", b.math("MULTIPLY", g, on), 2.2)))
    if rim:
        lw = b.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.35
        strength = b.math("MULTIPLY", strength, b.math("ADD", 0.55, b.math("MULTIPLY", lw.outputs["Facing"], 1.1)))
    return col, strength


def petal_material(name, base_strength, translucent=True):
    m, nt, out = new_material(name)
    b = NB(nt)
    col, strength = glow_shader(b, base_strength)
    p = b.new("ShaderNodeBsdfPrincipled")
    b.set(p.inputs["Base Color"], b.mix(0.75, col, (0.02, 0.02, 0.03)))
    p.inputs["Roughness"].default_value = 0.45
    b.set(p.inputs["Emission Color"], col)
    b.set(p.inputs["Emission Strength"], strength)
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def center_material():
    m, nt, out = new_material("FlowerCenter")
    b = NB(nt)
    col, strength = glow_shader(b, 3.5, rim=False)
    e = b.new("ShaderNodeEmission")
    b.set(e.inputs["Color"], b.mix(0.55, col, (1.0, 0.95, 0.9)))
    b.set(e.inputs["Strength"], strength)
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def stem_material():
    m, nt, out = new_material("Stem")
    b = NB(nt)
    tc = b.new("ShaderNodeTexCoord")
    _, _, z = b.sep(tc.outputs["Object"])
    p = b.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.01, 0.035, 0.02, 1)
    p.inputs["Roughness"].default_value = 0.6
    col, strength = glow_shader(b, 0.25, rim=False, wave=False)
    b.set(p.inputs["Emission Color"], col)
    b.set(p.inputs["Emission Strength"], b.math("MULTIPLY", strength, b.math("POWER", b.math("MULTIPLY", z, 1.2, clamp=True), 3.0)))
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def grass_material():
    m, nt, out = new_material("Grass")
    b = NB(nt)
    tc = b.new("ShaderNodeTexCoord")
    _, _, z = b.sep(tc.outputs["Object"])
    tip = b.math("POWER", b.math("MULTIPLY", z, 2.4, clamp=True), 4.0)
    p = b.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (0.012, 0.04, 0.015, 1)
    p.inputs["Roughness"].default_value = 0.55
    col, strength = glow_shader(b, 0.45, rim=False, wave=True)
    b.set(p.inputs["Emission Color"], b.mix(0.5, col, (0.1, 0.9, 0.7)))
    b.set(p.inputs["Emission Strength"], b.math("MULTIPLY", tip, strength))
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def emission_material(name, color, strength):
    m, nt, out = new_material(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m, e


def spore_material():
    m, nt, out = new_material("Spore")
    b = NB(nt)
    col, strength = glow_shader(b, 9.0, rim=False, wave=False)
    e = b.new("ShaderNodeEmission")
    b.set(e.inputs["Color"], b.mix(0.12, col, (0.8, 1.0, 0.9)))
    b.set(e.inputs["Strength"], strength)
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def build_materials():
    MATS["rock"] = rock_moss_material("RockMoss", 0.25, True)
    MATS["golem"] = rock_moss_material("GolemMoss", 0.55, True)
    MATS["ground"] = ground_material()
    MATS["water"] = water_material()
    MATS["petal"] = petal_material("Petal", 0.75)
    MATS["bell"] = petal_material("Bell", 1.4)
    MATS["mush"] = petal_material("MushCap", 1.7)
    MATS["center"] = center_material()
    MATS["stem"] = stem_material()
    MATS["grass"] = grass_material()
    MATS["spore"] = spore_material()
    MATS["vine"] = MATS["stem"]
    MATS["eye"], MATS["eye_em"] = emission_material("GolemEye", (0.55, 0.95, 1.0), 4.0)
    MATS["crystal"], MATS["crystal_em"] = emission_material("GolemCrystal", (1.0, 0.12, 0.55), 6.0)


# ----------------------------------------------------------------------------
# Terrain: gorge + crater
# ----------------------------------------------------------------------------
def gorge_cx(y):
    u = y - GORGE_Y0
    c = 9.0 * math.sin(u / 46.0) + 4.0 * math.sin(u / 19.0 + 1.2)
    return c * (1 - smoothstep(-80.0, -6.0, y))


def gorge_hw(y):
    u = y - GORGE_Y0
    hw = 9.5 + 1.5 * math.sin(u / 23.0 + 0.5) + 0.8 * n1(y * 0.05, 3.3)
    hw *= 1 - 0.2 * bump(-180, -120, y)
    hw = lerp(hw, 10.0, smoothstep(-40, -6, y))
    funnel = smoothstep(-262.0, -352.0, y)
    return hw + 26.0 * funnel ** 1.5


def gorge_h(y, side):
    funnel = smoothstep(-262.0, -352.0, y)
    return 38.0 + 8.0 * n1(y * 0.02, side * 5.0) - 10.0 * funnel


def ground_h(x, y):
    in_gorge = y < -6
    if in_gorge:
        return 0.16 * fbm(x * 0.12, y * 0.12, 1.0, 3) + 0.02
    h = 0.34 + 0.28 * fbm(x * 0.05, y * 0.05, 2.0, 4) + 0.08 * fbm(x * 0.4, y * 0.4, 4.0, 2)
    # reflecting pond in front of the golem
    pd = math.hypot((x - 0.0) / 17.0, (y - 190.0) / 9.0)
    h -= 1.1 * (1 - smoothstep(0.55, 1.05, pd))
    # crater floor rises toward the walls
    r = math.hypot(x - C_CRATER.x, y - C_CRATER.y)
    h += 2.0 * smoothstep(R_CRATER - 25, R_CRATER + 5, r) ** 2
    return h


def wall_disp(a, z, seed):
    """outward displacement (m) of a cliff at (along, height)."""
    d = 1.4 * fbm(a * 0.06, z * 0.08, seed, 4)
    d += 0.55 * fbm(a * 0.25, z * 0.3, seed + 7.0, 3)
    d += 0.45 * math.sin(z * 0.85 + 2.0 * n1(a * 0.05, seed))          # strata ledges
    d += 0.06 * max(0.0, z)                                            # lean back
    d += 2.2 * max(0.0, n1(a * 0.025, z * 0.04, seed + 3.0) - 0.15)     # big recesses
    return d


def wall_sheet(name, along, base_fn, out_fn, height_fn, seed, coll, dz=0.6, ascale=1.0):
    """Generic cliff sheet: base_fn(a) -> (x,y) of the cliff foot (no displacement),
    out_fn(a) -> unit outward 2D normal, height_fn(a) -> cliff height."""
    zmax = max(height_fn(a) for a in along[::20]) + 2
    verts = []
    ncol = len(along)
    nprof = int((zmax + 2.5) / dz) + 1
    nrow = nprof + 5
    for a in along:
        bx, by = base_fn(a)
        ox, oy = out_fn(a)
        H = height_fn(a)
        an = a * ascale
        for j in range(nprof):
            zz = -2.5 + (H + 2.5) * j / (nprof - 1)
            d = wall_disp(an, zz, seed)
            verts.append((bx + ox * d, by + oy * d, zz))
        dtop = wall_disp(an, H, seed)
        for k, (off, dzz) in enumerate(((1.2, 0.6), (3.5, 1.1), (8.0, 1.4), (20.0, 2.5), (60.0, 4.0))):
            zz = H + dzz + 1.2 * fbm(an * 0.05, off, seed + 11.0, 2)
            verts.append((bx + ox * (dtop + off), by + oy * (dtop + off), zz))
    faces = []
    for i in range(ncol - 1):
        for j in range(nrow - 1):
            v0 = i * nrow + j
            faces.append((v0, v0 + 1, v0 + nrow + 1, v0 + nrow))
    ob = mesh_object(name, verts, faces, coll, mats=[MATS["rock"]])
    orient_faces(ob)
    return ob


def orient_faces(ob):
    """Make normals point to the open side (toward the camera route) by checking a sample."""
    me = ob.data
    me.update()
    # the open side is where the gorge centre / crater centre is; sample average normal vs. that
    score = 0.0
    n = len(me.polygons)
    step = max(1, n // 2000)
    for i in range(0, n, step):
        p = me.polygons[i]
        c = p.center
        if c.y < -6:
            target = Vector((gorge_cx(c.y), c.y, c.z))
        else:
            target = Vector((C_CRATER.x, C_CRATER.y, c.z))
        score += p.normal.dot((target - c).normalized())
    if score < 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        me.update()


def add_wall_attrs(ob, extra_zone=0.0):
    """dens = ledges facing up (flowers grow there), zone from position."""
    me = ob.data
    me.update()
    nv = len(me.vertices)
    nz = [0.0] * (nv * 3)
    try:
        me.vertex_normals.foreach_get("vector", nz)
    except Exception:
        for i, v in enumerate(me.vertices):
            nz[i * 3: i * 3 + 3] = v.normal
    co = [0.0] * (nv * 3)
    me.vertices.foreach_get("co", co)
    dens, zone = [], []
    for i in range(nv):
        x, y, z = co[i * 3: i * 3 + 3]
        upn = nz[i * 3 + 2]
        d = smoothstep(0.55, 0.85, upn) * (0.35 if z < 30 else 0.1)
        dens.append(d)
        zone.append(zone_at(x, y))
    for k, vals in (("dens", dens), ("zone", zone)):
        a = me.attributes.get(k) or me.attributes.new(k, "FLOAT", "POINT")
        a.data.foreach_set("value", vals)


def build_terrain(coll):
    objs = {}
    step = 0.6
    ys = [GORGE_Y0 + i * step for i in range(int((GORGE_Y1 + 2.0 - GORGE_Y0) / step))]

    def eps(y):
        return (gorge_cx(y + 0.5) - gorge_cx(y - 0.5))

    for side, nm in ((-1, "GorgeWall_L"), (1, "GorgeWall_R")):
        def base_fn(a, side=side):
            return gorge_cx(a) + side * gorge_hw(a), a

        def out_fn(a, side=side):
            tx, ty = eps(a), 1.0
            l = math.hypot(tx, ty)
            # perpendicular to the centreline, pointing away from it
            return side * ty / l, -side * tx / l

        objs[nm] = wall_sheet(nm, ys, base_fn, out_fn, lambda a, side=side: gorge_h(a, side), 10.0 + side * 3, coll)

    # crater wall (gap at the south where the gorge enters)
    gap = math.asin(10.6 / R_CRATER)
    th0, th1 = -math.pi / 2 + gap, 1.5 * math.pi - gap
    n = int((th1 - th0) * R_CRATER / 0.85)
    ths = [th0 + (th1 - th0) * i / (n - 1) for i in range(n)]

    def cbase(a):
        return C_CRATER.x + R_CRATER * math.cos(a), C_CRATER.y + R_CRATER * math.sin(a)

    def cout(a):
        return math.cos(a), math.sin(a)

    def ch(a):
        north = max(0.0, math.sin(a)) ** 2
        return 47.0 + 8.0 * n1(a * 2.0, 9.0) - 15.0 * north

    objs["CraterWall"] = wall_sheet("CraterWall", ths, cbase, cout, ch, 40.0, coll, dz=0.7, ascale=R_CRATER)
    for ob in objs.values():
        add_wall_attrs(ob)

    # ---- ground: gorge floor strip
    verts, faces, dens, zone = [], [], [], []
    ny = int((-6.0 - GORGE_Y0) / 1.0) + 1
    nx = 25
    for i in range(ny):
        y = GORGE_Y0 + i * 1.0
        cx, hw = gorge_cx(y), gorge_hw(y) + 4.0
        for j in range(nx):
            x = cx - hw + 2 * hw * j / (nx - 1)
            verts.append((x, y, ground_h(x, y)))
            d = 0.05 + 0.08 * max(0.0, n1(x * 0.1, y * 0.1, 2.0)) + 0.95 * smoothstep(-150.0, -8.0, y) ** 1.5
            dens.append(d if ground_h(x, y) > WATER_Z + 0.02 else 0.0)
            zone.append(zone_at(x, y))
    for i in range(ny - 1):
        for j in range(nx - 1):
            v0 = i * nx + j
            faces.append((v0, v0 + nx, v0 + nx + 1, v0 + 1))
    objs["GorgeFloor"] = mesh_object("GorgeFloor", verts, faces, coll, mats=[MATS["ground"]],
                                     attrs={"dens": dens, "zone": zone})
    # ---- ground: crater disc
    verts, faces, dens, zone = [], [], [], []
    idx = {}
    R2 = R_CRATER + 8
    for iy in range(-6, int(C_CRATER.y + R2) + 1):
        for ix in range(int(-R2), int(R2) + 1):
            x, y = float(ix), float(iy)
            if math.hypot(x - C_CRATER.x, y - C_CRATER.y) > R2:
                continue
            idx[(ix, iy)] = len(verts)
            h = ground_h(x, y)
            verts.append((x + 0.3 * n1(x * 0.7, y * 0.7, 1.0), y + 0.3 * n1(x * 0.7, y * 0.7, 2.0), h))
            r = math.hypot(x - C_CRATER.x, y - C_CRATER.y)
            d = (0.8 + 0.45 * n1(x * 0.04, y * 0.04, 8.0)) * (1 - 0.5 * smoothstep(R_CRATER - 12, R_CRATER, r))
            if h < WATER_Z + 0.03:
                d = 0.0
            dens.append(max(0.0, d))
            zone.append(zone_at(x, y))
    for (ix, iy), v0 in idx.items():
        k = [(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)]
        if all(kk in idx for kk in k):
            faces.append(tuple(idx[kk] for kk in k))
    objs["CraterFloor"] = mesh_object("CraterFloor", verts, faces, coll, mats=[MATS["ground"]],
                                      attrs={"dens": dens, "zone": zone})
    # ---- water sheet (puddles in the gorge, pond in the crater)
    me = bpy.data.meshes.new("Water")
    me.from_pydata([(-220, -380, WATER_Z), (220, -380, WATER_Z), (220, 290, WATER_Z), (-220, 290, WATER_Z)], [], [(0, 1, 2, 3)])
    me.materials.append(MATS["water"])
    wo = bpy.data.objects.new("Water", me)
    coll.objects.link(wo)
    return objs


# ----------------------------------------------------------------------------
# Rocks (boulders, arches, golem parts)
# ----------------------------------------------------------------------------
def rock_blob(verts, faces, mat_idx, M, half, seed, rough=0.12, subdiv=3, mi=0, squar=0.55):
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=subdiv, radius=1.0)
    base = len(verts)
    tmp.verts.index_update()
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    amp = min(half) * rough
    for v in tmp.verts:
        d = v.co.normalized()
        p = Vector(tuple(math.copysign(abs(c) ** squar, c) for c in d))
        p = Vector((p.x * half.x, p.y * half.y, p.z * half.z))
        nl = Vector((d.x / half.x, d.y / half.y, d.z / half.z)).normalized()
        wp = M @ p
        q = wp * (0.9 / max(1.0, min(half))) + off
        disp = amp * noise.fractal(q, 0.6, 2.0, 4, noise_basis="PERLIN_ORIGINAL")
        disp -= amp * 1.6 * max(0.0, noise.noise(wp * 0.25 + off * 0.5) - 0.25)   # chipped facets
        verts.append(tuple(M @ (p + nl * disp)))
    for f in tmp.faces:
        faces.append(tuple(base + v.index for v in f.verts))
        mat_idx.append(mi)
    tmp.free()


def seg_matrix(p0, p1, up=Vector((0, 0, 1))):
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    side = ax.cross(up)
    if side.length < 1e-3:
        side = ax.cross(Vector((0, 1, 0)))
    side.normalize()
    upv = side.cross(ax).normalized()
    R = Matrix((side, ax, upv)).transposed()     # local x=side, y=axis, z=up
    M = R.to_4x4()
    M.translation = (p0 + p1) / 2
    return M, (p1 - p0).length


def rock_attrs(ob, dens_scale=1.0, up_lo=0.35, up_hi=0.8):
    me = ob.data
    me.update()
    nv = len(me.vertices)
    nrm = [0.0] * (nv * 3)
    try:
        me.vertex_normals.foreach_get("vector", nrm)
    except Exception:
        for i, v in enumerate(me.vertices):
            nrm[i * 3: i * 3 + 3] = v.normal
    co = [0.0] * (nv * 3)
    me.vertices.foreach_get("co", co)
    mw = ob.matrix_world
    dens, zone = [], []
    for i in range(nv):
        p = mw @ Vector(co[i * 3: i * 3 + 3])
        dens.append(dens_scale * smoothstep(up_lo, up_hi, nrm[i * 3 + 2]))
        zone.append(zone_at(p.x, p.y))
    for k, vals in (("dens", dens), ("zone", zone)):
        a = me.attributes.get(k) or me.attributes.new(k, "FLOAT", "POINT")
        a.data.foreach_set("value", vals)


def build_boulders(coll, path_pts):
    kd = kdtree.KDTree(len(path_pts))
    for i, p in enumerate(path_pts):
        kd.insert(p, i)
    kd.balance()
    verts, faces, mi = [], [], []
    placed = 0
    tries = 0
    while placed < 150 and tries < 4000:
        tries += 1
        if RNG.random() < 0.35:
            y = RNG.uniform(-330, -10)
            side = RNG.choice((-1, 1))
            x = gorge_cx(y) + side * (gorge_hw(y) - RNG.uniform(0.0, 2.5))
            s = RNG.uniform(0.7, 2.4)
        else:
            a = RNG.uniform(0, 2 * math.pi)
            r = R_CRATER * math.sqrt(RNG.random())
            x, y = C_CRATER.x + r * math.cos(a), C_CRATER.y + r * math.sin(a)
            if abs(x) < 32 and y > 195:
                continue
            s = RNG.uniform(0.8, 4.0) if RNG.random() < 0.8 else RNG.uniform(4, 7)
        z = ground_h(x, y)
        c = Vector((x, y, z + s * 0.25))
        _, _, dist = kd.find(c)
        if dist < s * 1.6 + 4.5:
            continue
        M = Matrix.Translation(c) @ Euler((RNG.uniform(-0.3, 0.3), RNG.uniform(-0.3, 0.3), RNG.uniform(0, 6.3))).to_matrix().to_4x4()
        half = Vector((s * RNG.uniform(0.8, 1.3), s * RNG.uniform(0.8, 1.3), s * RNG.uniform(0.5, 0.9)))
        rock_blob(verts, faces, mi, M, half, RNG.uniform(0, 100), rough=0.16, subdiv=3)
        placed += 1
    # rock arch over the gorge and a fallen slab bridge
    for ya, za, r in ((-150.0, 10.0, 2.6), (-62.0, 7.6, 2.0)):
        cx, hw = gorge_cx(ya), gorge_hw(ya)
        pts = []
        for k in range(9):
            t = k / 8
            x = cx - hw - 3 + (2 * hw + 6) * t
            z = za + 2.2 * math.sin(math.pi * t) - 0.6 + (8.0 * (abs(t - 0.5) * 2) ** 3 if ya < -100 else 0.0)
            pts.append(Vector((x, ya + 1.2 * math.sin(t * 5), z)))
        for p0, p1 in zip(pts, pts[1:]):
            M, ln = seg_matrix(p0, p1)
            rock_blob(verts, faces, mi, M, Vector((r, ln / 2 + r * 0.6, r * 0.9)), RNG.uniform(0, 100), rough=0.14, subdiv=3)
    ob = mesh_object("Boulders", verts, faces, coll, mats=[MATS["rock"]], mat_idx=mi)
    rock_attrs(ob, 0.9)
    return ob


GOLEM_PARTS_STATIC = [
    # (kind, a, b, radius/half, seed)
    ("seg", (-6, 1, 5), (-7, -14, 13), 4.0),      # L thigh
    ("seg", (-7, -14, 13), (-7.5, -20, 2.6), 3.5),  # L shin
    ("box", (-7.5, -23.5, 1.6), (3.6, 5.0, 2.0), 0),  # L foot
    ("seg", (6, 1, 5), (8.5, -11, 7.2), 4.0),     # R thigh
    ("seg", (8.5, -11, 7.2), (9.5, -24, 2.4), 3.4),  # R shin
    ("box", (9.6, -27.5, 1.6), (3.6, 5.0, 2.0), 0),  # R foot
    ("box", (0, 3, 6.5), (7.5, 5.5, 4.5), 0),     # pelvis
    ("seg", (-14, -2, 13), (-9, -13, 14.2), 3.0),  # L forearm on knee
    ("box", (-8.2, -16.8, 13.8), (3.0, 3.2, 2.3), 0),  # L hand
    ("seg", (15.5, 1, 12), (16.2, -6, 3.2), 3.0),  # R forearm down
    ("box", (16.6, -9.0, 1.7), (3.6, 3.8, 1.8), 0),  # R hand on ground
]
GOLEM_PARTS_BREATH = [
    ("box", (0, 5, 12.5), (8.2, 5.8, 5.2), -8),   # belly
    ("box", (0, 5.5, 19.5), (10.8, 6.8, 6.4), -12),  # chest
    ("box", (-11.8, 5, 22.0), (4.6, 4.6, 4.2), 0),  # L shoulder
    ("box", (11.8, 5, 22.0), (4.6, 4.6, 4.2), 0),   # R shoulder
    ("seg", (-12.5, 5, 21), (-14, -2, 13), 3.3),  # L upper arm
    ("seg", (12.5, 5, 21), (15.5, 1, 12), 3.3),   # R upper arm
    ("box", (0, 2.0, 28.4), (4.3, 4.4, 4.3), 14),  # head (bowed)
    ("box", (0, -1.6, 29.6), (4.6, 1.4, 1.2), 14),  # brow
    ("box", (0, 0.2, 25.2), (3.7, 3.5, 1.8), 10),  # jaw
    ("box", (0, -2.7, 27.3), (0.9, 1.0, 1.7), 16),  # nose ridge
    ("box", (-2.7, -2.0, 26.7), (1.4, 1.1, 1.0), 10),  # cheek L
    ("box", (2.7, -2.0, 26.7), (1.4, 1.1, 1.0), 10),   # cheek R
    ("box", (-3.6, 1.5, 31.4), (1.8, 2.0, 1.4), 25),  # crown rocks
    ("box", (2.8, 2.5, 31.8), (2.0, 1.8, 1.3), -15),
    ("box", (0, 8.5, 26.0), (6.5, 4.0, 3.0), 0),  # back hump
]


def build_golem(coll):
    gcoll = new_collection("Golem", coll)
    objs = []
    for nm, parts, breath in (("Golem_Base", GOLEM_PARTS_STATIC, False), ("Golem_Upper", GOLEM_PARTS_BREATH, True)):
        verts, faces, mi = [], [], []
        for k, part in enumerate(parts):
            kind = part[0]
            if kind == "seg":
                M, ln = seg_matrix(part[1], part[2])
                half = Vector((part[3], ln / 2 + part[3] * 0.5, part[3] * 0.95))
            else:
                c, half, tilt = Vector(part[1]), Vector(part[2]), part[3]
                M = Matrix.Translation(c) @ Matrix.Rotation(math.radians(tilt), 4, "X")
            seed = 50 + k * 3.7 + (20 if breath else 0)
            M = Matrix.Scale(GS, 4) @ M
            half = half * GS
            rock_blob(verts, faces, mi, M, half, seed, rough=0.2, subdiv=4, squar=0.72)
            # smaller stone plates stuck on the surface break up the silhouette
            prng = random.Random(int(seed * 10))
            for c in range(3 if min(half) > 2.5 else 1):
                d = Vector((prng.uniform(-1, 1), prng.uniform(-1, 1), prng.uniform(-0.2, 1))).normalized()
                sp = Vector(tuple(math.copysign(abs(cc) ** 0.72, cc) for cc in d))
                sp = Vector((sp.x * half.x, sp.y * half.y, sp.z * half.z)) * 0.9
                ph = min(half) * prng.uniform(0.3, 0.5)
                Mc = M @ Matrix.Translation(sp) @ Euler((prng.uniform(0, 3), prng.uniform(0, 3), prng.uniform(0, 3))).to_matrix().to_4x4()
                rock_blob(verts, faces, mi, Mc, Vector((ph * 1.3, ph, ph * 0.7)), seed + 100 + c, rough=0.22, subdiv=2, squar=0.8)
        ob = mesh_object(nm, verts, faces, gcoll, mats=[MATS["golem"]], mat_idx=mi)
        ob.location = GOLEM_POS
        objs.append(ob)
    bpy.context.view_layer.update()
    base, upper = objs
    # eyes + chest crystal on the breathing part
    eyes = []
    for sx in (-1.7, 1.7):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.6)
        me = bpy.data.meshes.new("Eye")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(MATS["eye"])
        e = bpy.data.objects.new("GolemEye", me)
        e.location = Vector((sx, -2.15, 28.35)) * GS
        e.scale = (1.0, 0.55, 0.65)
        gcoll.objects.link(e)
        e.parent = upper
        eyes.append(e)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 1.2, v.co.y * 0.8, v.co.z * 1.9))
    me = bpy.data.meshes.new("Crystal")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS["crystal"])
    cr = bpy.data.objects.new("GolemCrystal", me)
    cr.location = Vector((0.0, -1.0, 19.5)) * GS
    cr.rotation_euler = (math.radians(-12), 0, math.radians(8))
    gcoll.objects.link(cr)
    cr.parent = upper
    # breathing: a slow rise of the upper body
    for f in range(F_START, F_END + 1, 6):
        t = f / FPS
        upper.location = GOLEM_POS + Vector((0, 0.05 * math.sin(2 * math.pi * t / 6.5), 0.2 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 6.5))))
        upper.keyframe_insert("location", frame=f)
    # glow animation: crystal pulses with breath, eyes brighten at the end
    ce, ee = MATS["crystal_em"], MATS["eye_em"]
    for f in range(F_START, F_END + 1, 4):
        t = f / FPS
        br = 0.5 - 0.5 * math.cos(2 * math.pi * t / 6.5)
        ce.inputs["Strength"].default_value = 4.0 + 6.0 * br
        ce.inputs["Strength"].keyframe_insert("default_value", frame=f)
        wake = smootherstep(1330, 1420, f)
        ee.inputs["Strength"].default_value = 2.0 + 0.8 * br + 7.0 * wake
        ee.inputs["Strength"].keyframe_insert("default_value", frame=f)
    for ob in (base, upper):
        rock_attrs(ob, 2.2, 0.3, 0.75)
    return base, upper


# ----------------------------------------------------------------------------
# Flower prototypes
# ----------------------------------------------------------------------------
def tube(verts, faces, mi, pts, radii, sides=5, m=0):
    base = len(verts)
    for k, (p, r) in enumerate(zip(pts, radii)):
        p = Vector(p)
        if k < len(pts) - 1:
            ax = (Vector(pts[k + 1]) - p).normalized()
        else:
            ax = (p - Vector(pts[k - 1])).normalized()
        sd = ax.cross(Vector((0, 1, 0)))
        if sd.length < 1e-3:
            sd = ax.cross(Vector((1, 0, 0)))
        sd.normalize()
        up = ax.cross(sd)
        for s in range(sides):
            a = 2 * math.pi * s / sides
            verts.append(tuple(p + (sd * math.cos(a) + up * math.sin(a)) * r))
    for k in range(len(pts) - 1):
        for s in range(sides):
            a0 = base + k * sides + s
            a1 = base + k * sides + (s + 1) % sides
            faces.append((a0, a1, a1 + sides, a0 + sides))
            mi.append(m)


def ico(verts, faces, mi, c, r, sub=1, m=0, sc=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    base = len(verts)
    bm.verts.index_update()
    for v in bm.verts:
        verts.append((c[0] + v.co.x * sc[0], c[1] + v.co.y * sc[1], c[2] + v.co.z * sc[2]))
    for f in bm.faces:
        faces.append(tuple(base + v.index for v in f.verts))
        mi.append(m)
    bm.free()


def stem_curve(h, bend, n=6):
    return [(bend * (k / (n - 1)) ** 2, 0.0, h * k / (n - 1)) for k in range(n)]


def proto_daisy(rng):
    v, f, mi = [], [], []
    h = rng.uniform(0.35, 0.5)
    pts = stem_curve(h, 0.06)
    tube(v, f, mi, pts, [0.008] * len(pts), 4, 0)
    top = Vector(pts[-1])
    tilt = Matrix.Rotation(0.5, 3, "Y")
    npet = 11
    for k in range(npet):
        a = 2 * math.pi * k / npet
        dirv = Vector((math.cos(a), math.sin(a), 0))
        side = Vector((-math.sin(a), math.cos(a), 0))
        base = len(v)
        for (r, w, z) in ((0.015, 0.012, 0.0), (0.08, 0.026, 0.018), (0.15, 0.018, 0.05), (0.18, 0.004, 0.075)):
            for s in (-1, 1):
                p = dirv * r + side * w * s + Vector((0, 0, z))
                v.append(tuple(top + tilt @ p))
        for q in range(3):
            a0 = base + q * 2
            f.append((a0, a0 + 1, a0 + 3, a0 + 2))
            mi.append(1)
    ico(v, f, mi, top + tilt @ Vector((0, 0, 0.012)), 0.028, 1, 2)
    return v, f, mi, [MATS["stem"], MATS["petal"], MATS["center"]]


def proto_cup(rng):
    v, f, mi = [], [], []
    h = rng.uniform(0.45, 0.65)
    pts = stem_curve(h, -0.05)
    tube(v, f, mi, pts, [0.01] * len(pts), 4, 0)
    top = Vector(pts[-1])
    rings = [(0.0, 0.02), (0.04, 0.055), (0.09, 0.075), (0.14, 0.085), (0.19, 0.095)]
    seg = 15
    base = len(v)
    for z, r in rings:
        for s in range(seg):
            a = 2 * math.pi * s / seg
            lobe = 1 + 0.35 * (z / 0.19) * max(0.0, math.cos(5 * a)) ** 2
            zz = z + 0.04 * (z / 0.19) * math.cos(5 * a)
            v.append((top.x + r * lobe * math.cos(a), top.y + r * lobe * math.sin(a), top.z + zz))
    for k in range(len(rings) - 1):
        for s in range(seg):
            a0 = base + k * seg + s
            a1 = base + k * seg + (s + 1) % seg
            f.append((a0, a1, a1 + seg, a0 + seg))
            mi.append(1)
    for k in range(3):
        a = 2 * math.pi * k / 3
        tube(v, f, mi, [top + Vector((0, 0, 0.02)), top + Vector((0.02 * math.cos(a), 0.02 * math.sin(a), 0.15))], [0.004, 0.003], 3, 0)
        ico(v, f, mi, top + Vector((0.02 * math.cos(a), 0.02 * math.sin(a), 0.155)), 0.012, 1, 2)
    # leaves
    for s in (-1, 1):
        lb = len(v)
        for (t, w) in ((0.0, 0.0), (0.35, 0.03), (0.7, 0.025), (1.0, 0.0)):
            p = Vector((s * 0.18 * t, 0.0, 0.05 + 0.18 * t - 0.12 * t * t))
            v.append(tuple(p + Vector((0, w, 0))))
            v.append(tuple(p + Vector((0, -w, 0))))
        for q in range(3):
            a0 = lb + q * 2
            f.append((a0, a0 + 1, a0 + 3, a0 + 2))
            mi.append(0)
    return v, f, mi, [MATS["stem"], MATS["petal"], MATS["center"]]


def proto_bells(rng):
    v, f, mi = [], [], []
    h = rng.uniform(0.5, 0.7)
    pts = [(0, 0, 0), (0.0, 0, h * 0.5), (0.05, 0, h * 0.85), (0.14, 0, h), (0.22, 0, h * 0.93)]
    tube(v, f, mi, pts, [0.009, 0.008, 0.007, 0.006, 0.005], 4, 0)
    for k, (t, s) in enumerate(((0.12, 1.0), (0.18, 0.8), (0.22, 0.65))):
        c = Vector((t, 0.03 * (k - 1), h * 0.93 - 0.02 - 0.03 * k))
        base = len(v)
        seg = 10
        for z, r in ((0.0, 0.012), (-0.03, 0.04), (-0.07, 0.055), (-0.085, 0.07)):
            for q in range(seg):
                a = 2 * math.pi * q / seg
                fl = 1 + (0.25 if z < -0.08 and q % 2 == 0 else 0.0)
                v.append(tuple(c + Vector((r * s * fl * math.cos(a), r * s * fl * math.sin(a), z * s))))
        for z in range(3):
            for q in range(seg):
                a0 = base + z * seg + q
                a1 = base + z * seg + (q + 1) % seg
                f.append((a0, a1, a1 + seg, a0 + seg))
                mi.append(1)
        ico(v, f, mi, c + Vector((0, 0, -0.07 * s)), 0.014 * s, 1, 2)
    return v, f, mi, [MATS["stem"], MATS["bell"], MATS["center"]]


def proto_stalk(rng):
    v, f, mi = [], [], []
    h = rng.uniform(1.1, 1.6)
    pts = stem_curve(h, 0.12, 8)
    tube(v, f, mi, pts, [0.016 * (1 - 0.6 * k / 7) for k in range(8)], 5, 0)
    nb = 16
    for k in range(nb):
        t = 0.45 + 0.55 * k / nb
        zc = h * t
        x = 0.12 * t * t
        a = k * 2.4
        rr = 0.05 * (1 - 0.6 * k / nb)
        c = (x + 0.04 * math.cos(a), 0.04 * math.sin(a), zc)
        ico(v, f, mi, c, rr, 1, 1, sc=(1, 1, 1.3))
    for k in range(4):
        a = k * 1.7
        tube(v, f, mi, [(0, 0, 0.1 + k * 0.08), (0.2 * math.cos(a), 0.2 * math.sin(a), 0.2 + k * 0.08)], [0.012, 0.004], 3, 0)
    return v, f, mi, [MATS["stem"], MATS["bell"]]


def proto_mush(rng):
    v, f, mi = [], [], []
    for k in range(rng.randint(3, 5)):
        a = rng.uniform(0, 6.28)
        d = rng.uniform(0.0, 0.18)
        c = Vector((d * math.cos(a), d * math.sin(a), 0))
        h = rng.uniform(0.07, 0.25)
        r = rng.uniform(0.05, 0.13)
        tube(v, f, mi, [c, c + Vector((0.01, 0, h))], [0.016, 0.012], 5, 0)
        base = len(v)
        seg = 12
        for z, rr in ((0.0, 0.2), (0.0, 1.0), (0.35, 0.85), (0.6, 0.55), (0.75, 0.0)):
            for q in range(seg):
                aa = 2 * math.pi * q / seg
                v.append(tuple(c + Vector((0.01 + r * rr * math.cos(aa), r * rr * math.sin(aa), h + z * r))))
        for z in range(4):
            for q in range(seg):
                a0 = base + z * seg + q
                a1 = base + z * seg + (q + 1) % seg
                f.append((a0, a1, a1 + seg, a0 + seg))
                mi.append(1)
    return v, f, mi, [MATS["stem"], MATS["mush"]]


def proto_tuft(rng):
    v, f, mi = [], [], []
    for k in range(7):
        a = rng.uniform(0, 6.28)
        h = rng.uniform(0.18, 0.42)
        lean = rng.uniform(0.05, 0.16)
        base = len(v)
        for t in (0.0, 0.5, 1.0):
            w = 0.012 * (1 - t) + 0.001
            p = Vector((math.cos(a) * lean * t * t, math.sin(a) * lean * t * t, h * t))
            sd = Vector((-math.sin(a), math.cos(a), 0)) * w
            v.append(tuple(p + sd))
            v.append(tuple(p - sd))
        for q in range(2):
            a0 = base + q * 2
            f.append((a0, a0 + 1, a0 + 3, a0 + 2))
            mi.append(0)
    return v, f, mi, [MATS["grass"]]


def build_prototypes():
    coll = new_collection("FlowerProtos")
    protos = {}
    rng = random.Random(11)
    for nm, fn in (("daisy", proto_daisy), ("cup", proto_cup), ("bells", proto_bells),
                   ("stalk", proto_stalk), ("mush", proto_mush), ("tuft", proto_tuft)):
        v, f, mi, mats = fn(rng)
        ob = mesh_object("Proto_" + nm, v, f, coll, mats=mats, mat_idx=mi, smooth=(nm != "tuft"))
        ob.location = (0, -600, -50)
        ob.hide_render = True
        protos[nm] = ob
    return protos


# ----------------------------------------------------------------------------
# Geometry-nodes scatter (shared by every surface that grows flowers)
# ----------------------------------------------------------------------------
SCATTER = [  # name, density per m2 at dens=1, scale range, avoid camera path (m)
    ("tuft", 1.4, (0.8, 1.5), 0.0),
    ("daisy", 0.85, (0.8, 1.5), 0.0),
    ("cup", 0.65, (0.8, 1.6), 0.0),
    ("bells", 0.6, (0.8, 1.5), 0.0),
    ("mush", 0.18, (0.8, 1.8), 0.0),
    ("stalk", 0.22, (0.8, 1.7), 3.4),
]


def scatter_group(protos, path_obj):
    ng = bpy.data.node_groups.new("FlowerScatter", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    s_mult = ng.interface.new_socket(name="Density", in_out="INPUT", socket_type="NodeSocketFloat")
    s_mult.default_value = 1.0
    s_seed = ng.interface.new_socket(name="Seed", in_out="INPUT", socket_type="NodeSocketInt")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    join = N.new("GeometryNodeJoinGeometry")
    L.new(gi.outputs["Geometry"], join.inputs[0])
    dens_attr = N.new("GeometryNodeInputNamedAttribute")
    dens_attr.data_type = "FLOAT"
    dens_attr.inputs["Name"].default_value = "dens"
    po = N.new("GeometryNodeObjectInfo")
    po.transform_space = "RELATIVE"
    po.inputs["Object"].default_value = path_obj
    for k, (nm, dpm, (s0, s1), avoid) in enumerate(SCATTER):
        dist = N.new("GeometryNodeDistributePointsOnFaces")
        dist.distribute_method = "RANDOM"
        L.new(gi.outputs["Geometry"], dist.inputs["Mesh"])
        m1 = N.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
        L.new(dens_attr.outputs[0] if dens_attr.outputs[0].type == "VALUE" else
              [o for o in dens_attr.outputs if o.type == "VALUE" and not o.is_unavailable][0], m1.inputs[0])
        m1.inputs[1].default_value = dpm
        m2 = N.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
        L.new(m1.outputs[0], m2.inputs[0])
        L.new(gi.outputs["Density"], m2.inputs[1])
        L.new(m2.outputs[0], dist.inputs["Density"])
        sd = N.new("ShaderNodeMath"); sd.operation = "ADD"
        L.new(gi.outputs["Seed"], sd.inputs[0])
        sd.inputs[1].default_value = k * 17
        fi = N.new("FunctionNodeFloatToInt")
        L.new(sd.outputs[0], fi.inputs[0])
        L.new(fi.outputs[0], dist.inputs["Seed"])
        pts_out = dist.outputs["Points"]
        sel = None
        if avoid > 0:
            prox = N.new("GeometryNodeProximity")
            try:
                prox.target_element = "EDGES"
            except Exception:
                pass
            tgt = [s for s in prox.inputs if s.type == "GEOMETRY"][0]
            L.new(po.outputs["Geometry"], tgt)
            dist_out = [o for o in prox.outputs if o.name == "Distance"][0]
            cmp = N.new("ShaderNodeMath"); cmp.operation = "GREATER_THAN"
            L.new(dist_out, cmp.inputs[0])
            cmp.inputs[1].default_value = avoid
            sel = cmp.outputs[0]
        oi = N.new("GeometryNodeObjectInfo")
        oi.inputs["Object"].default_value = protos[nm]
        iop = N.new("GeometryNodeInstanceOnPoints")
        L.new(pts_out, iop.inputs["Points"])
        L.new(oi.outputs["Geometry"], iop.inputs["Instance"])
        if sel is not None:
            L.new(sel, iop.inputs["Selection"])
        rr = N.new("FunctionNodeRandomValue"); rr.data_type = "FLOAT_VECTOR"
        sock(rr, "Min").default_value = (-0.22, -0.22, 0.0)
        sock(rr, "Max").default_value = (0.22, 0.22, 6.283)
        rr.inputs["Seed"].default_value = 100 + k
        L.new([o for o in rr.outputs if o.type == "VECTOR" and not o.is_unavailable][0], iop.inputs["Rotation"])
        rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"
        sock(rs, "Min").default_value = s0
        sock(rs, "Max").default_value = s1
        rs.inputs["Seed"].default_value = 200 + k
        L.new([o for o in rs.outputs if o.type == "VALUE" and not o.is_unavailable][0], iop.inputs["Scale"])
        L.new(iop.outputs["Instances"], join.inputs[0])
    L.new(join.outputs[0], go.inputs["Geometry"])
    ident = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
    return ng, ident


def add_scatter(ob, ng, ident, mult, seed):
    md = ob.modifiers.new("Flowers", "NODES")
    md.node_group = ng
    getattr(md.properties.inputs, ident["Density"]).value = mult
    getattr(md.properties.inputs, ident["Seed"]).value = seed


# ----------------------------------------------------------------------------
# Vines, wall fungi, giant flowers, spores
# ----------------------------------------------------------------------------
def build_vines(coll, walls, path_kd):
    v, f, mi = [], [], []
    count = 0
    for wall in walls:
        me = wall.data
        nv = len(me.vertices)
        for _ in range(240 if wall.name != "CraterWall" else 320):
            vi = RNG.randrange(nv)
            p = me.vertices[vi].co.copy()
            if p.z < 7 or p.z > 44:
                continue
            nrm = me.vertices[vi].normal
            if nrm.z > 0.3 or nrm.z < -0.6:
                continue
            ln = RNG.uniform(3.0, min(16.0, p.z - 1.0))
            # keep vines out of the flight corridor
            bottom = p - Vector((0, 0, ln))
            _, _, d = path_kd.find(Vector((bottom.x, bottom.y, bottom.z)))
            if d < 3.2:
                continue
            nseg = 8
            sway = Vector((nrm.x, nrm.y, 0)) * 0.4
            pts = [p + Vector((0, 0, -ln * k / nseg)) + sway * math.sin(k * 0.7) * (k / nseg) for k in range(nseg + 1)]
            tube(v, f, mi, pts, [0.035] * len(pts), 4, 0)
            for k in range(2, nseg + 1, 2):
                ico(v, f, mi, pts[k] + Vector((0.05, 0, 0)), RNG.uniform(0.05, 0.11), 1, 1)
            ico(v, f, mi, pts[-1], 0.13, 1, 1)
            count += 1
    ob = mesh_object("Vines", v, f, coll, mats=[MATS["stem"], MATS["bell"]], mat_idx=mi)
    zone = [zone_at(x, y) for (x, y, z) in v]
    a = ob.data.attributes.new("zone", "FLOAT", "POINT")
    a.data.foreach_set("value", zone)
    print("vines", count)
    return ob


def build_fungi(coll, walls, path_kd):
    v, f, mi = [], [], []
    for wall in walls:
        me = wall.data
        nv = len(me.vertices)
        n = 0
        tries = 0
        while n < (380 if wall.name != "CraterWall" else 420) and tries < 6000:
            tries += 1
            vi = RNG.randrange(nv)
            p = me.vertices[vi].co.copy()
            nrm = me.vertices[vi].normal.copy()
            if p.z < 0.2 or p.z > 9 or abs(nrm.z) > 0.5:
                continue
            _, _, d = path_kd.find(p)
            if d < 2.6:
                continue
            nh = Vector((nrm.x, nrm.y, 0)).normalized()
            for k in range(RNG.randint(2, 5)):
                c = p + Vector((RNG.uniform(-0.4, 0.4), RNG.uniform(-0.4, 0.4), RNG.uniform(-0.5, 0.6))) + nh * 0.05
                r = RNG.uniform(0.12, 0.42)
                base = len(v)
                seg = 10
                for z, rr in ((0.0, 0.0), (0.0, 1.0), (0.05, 0.8), (0.08, 0.0)):
                    for q in range(seg):
                        a = math.pi * (q / (seg - 1)) - math.pi / 2
                        dirv = nh * math.cos(a) + Vector((-nh.y, nh.x, 0)) * math.sin(a)
                        v.append(tuple(c + dirv * (r * rr) + Vector((0, 0, z * r * 4))))
                for z in range(3):
                    for q in range(seg - 1):
                        a0 = base + z * seg + q
                        f.append((a0, a0 + 1, a0 + seg + 1, a0 + seg))
                        mi.append(0)
            n += 1
    ob = mesh_object("WallFungi", v, f, coll, mats=[MATS["mush"]], mat_idx=mi)
    zone = [clamp(zone_at(x, y) * 0.6) for (x, y, z) in v]
    a = ob.data.attributes.new("zone", "FLOAT", "POINT")
    a.data.foreach_set("value", zone)
    return ob


def build_giants(coll, protos, path_kd):
    n = 0
    tries = 0
    while n < 140 and tries < 3000:
        tries += 1
        a = RNG.uniform(0, 2 * math.pi)
        r = (R_CRATER - 6) * math.sqrt(RNG.random())
        x, y = C_CRATER.x + r * math.cos(a), C_CRATER.y + r * math.sin(a)
        z = ground_h(x, y)
        if z < WATER_Z + 0.05 or (abs(x) < 30 and y > 198):
            continue
        s = RNG.uniform(3.0, 6.0)
        _, _, d = path_kd.find(Vector((x, y, z + 1.0)))
        if d < 4.5 + s * 0.15:
            continue
        kind = RNG.choice(("cup", "cup", "stalk", "bells", "daisy"))
        ob = bpy.data.objects.new("Giant_%s" % kind, protos[kind].data)
        ob.location = (x, y, z - 0.05)
        ob.rotation_euler = (RNG.uniform(-0.12, 0.12), RNG.uniform(-0.12, 0.12), RNG.uniform(0, 6.28))
        ob.scale = (s, s, s * RNG.uniform(0.9, 1.3))
        ob["zone"] = zone_at(x, y)
        coll.objects.link(ob)
        n += 1
    # glowing pads floating on the pond
    for k in range(60):
        a = RNG.uniform(0, 2 * math.pi)
        rr = math.sqrt(RNG.random()) * 0.85
        x, y = 15.0 * rr * math.cos(a), 190.0 + 7.5 * rr * math.sin(a)
        if ground_h(x, y) > WATER_Z - 0.05:
            continue
        ob = bpy.data.objects.new("PondFlower", protos["daisy"].data)
        ob.location = (x, y, WATER_Z - 0.42)
        ob.rotation_euler = (0, 0, RNG.uniform(0, 6.28))
        ob.scale = (RNG.uniform(1.4, 2.4),) * 3
        ob["zone"] = RNG.choice((0.15, 0.85, 0.7))
        coll.objects.link(ob)
    print("giant flowers", n)


def build_spores(coll, path_pts):
    pts, zone = [], []
    for k in range(3200):
        p = path_pts[RNG.randrange(len(path_pts))]
        off = Vector((RNG.gauss(0, 9), RNG.gauss(0, 9), RNG.uniform(-2.0, 9.0)))
        q = p + off
        gz = ground_h(q.x, q.y)
        q.z = max(q.z, gz + 0.3)
        pts.append(tuple(q))
        zone.append(zone_at(q.x, q.y))
    me = bpy.data.meshes.new("SporeCloud")
    me.from_pydata(pts, [], [])
    a = me.attributes.new("zone", "FLOAT", "POINT")
    a.data.foreach_set("value", zone)
    ob = bpy.data.objects.new("Spores", me)
    coll.objects.link(ob)
    ng = bpy.data.node_groups.new("SporeDrift", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    L.new(gi.outputs["Geometry"], m2p.inputs["Mesh"])
    st = N.new("GeometryNodeInputSceneTime")
    pos = N.new("GeometryNodeInputPosition")
    nz = N.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 0.12
    nz.inputs["Detail"].default_value = 1.0
    L.new(pos.outputs[0], nz.inputs["Vector"])
    tw = N.new("ShaderNodeMath"); tw.operation = "MULTIPLY"
    L.new(st.outputs["Seconds"], tw.inputs[0]); tw.inputs[1].default_value = 0.06
    L.new(tw.outputs[0], nz.inputs["W"])
    sub = N.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"
    L.new(nz.outputs["Color"], sub.inputs[0]); sub.inputs[1].default_value = (0.5, 0.5, 0.42)
    sc = N.new("ShaderNodeVectorMath"); sc.operation = "SCALE"
    L.new(sub.outputs[0], sc.inputs[0]); sc.inputs["Scale"].default_value = 7.0
    sp = N.new("GeometryNodeSetPosition")
    L.new(m2p.outputs["Points"], sp.inputs["Geometry"])
    L.new(sc.outputs[0], sp.inputs["Offset"])
    ic = N.new("GeometryNodeMeshIcoSphere")
    ic.inputs["Radius"].default_value = 0.016
    ic.inputs["Subdivisions"].default_value = 1
    iop = N.new("GeometryNodeInstanceOnPoints")
    L.new(sp.outputs["Geometry"], iop.inputs["Points"])
    L.new(ic.outputs["Mesh"], iop.inputs["Instance"])
    rs = N.new("FunctionNodeRandomValue"); rs.data_type = "FLOAT"
    sock(rs, "Min").default_value = 0.5
    sock(rs, "Max").default_value = 1.8
    L.new([o for o in rs.outputs if o.type == "VALUE" and not o.is_unavailable][0], iop.inputs["Scale"])
    sm = N.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = MATS["spore"]
    L.new(iop.outputs["Instances"], sm.inputs["Geometry"])
    L.new(sm.outputs["Geometry"], go.inputs["Geometry"])
    md = ob.modifiers.new("Drift", "NODES")
    md.node_group = ng
    for attr in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission"):
        setattr(ob, attr, False)
    return ob


# ----------------------------------------------------------------------------
# Lights
# ----------------------------------------------------------------------------
def point_light(coll, name, loc, color, power, radius):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = power
    ld.color = color
    ld.shadow_soft_size = radius
    try:
        ld.use_shadow = True
    except Exception:
        pass
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def build_lights(coll):
    n = 0
    # flower-field glow pools
    sp = 21.0
    gx = int(R_CRATER / sp) + 1
    for i in range(-gx, gx + 1):
        for j in range(-gx, gx + 1):
            x = C_CRATER.x + i * sp + RNG.uniform(-4, 4)
            y = C_CRATER.y + j * sp + RNG.uniform(-4, 4)
            r = math.hypot(x - C_CRATER.x, y - C_CRATER.y)
            if r > R_CRATER - 4 or (abs(x) < 26 and y > 205):
                continue
            h = ground_h(x, y)
            if h < WATER_Z:
                continue
            col = ramp_color(ZONE_RAMP, zone_at(x, y))
            point_light(coll, "FieldGlow", (x, y, h + 1.4), col, 520.0, 6.0)
            n += 1
    # gorge: fungus glow near the wall feet + a growing glow toward the exit
    y = GORGE_Y0 + 25
    side = 1
    while y < -6:
        x = gorge_cx(y) + side * (gorge_hw(y) - 1.8)
        zc = zone_at(x, y) * 0.55
        col = ramp_color(ZONE_RAMP, zc)
        pw = 700.0 + 900.0 * smoothstep(-140, -8, y)
        point_light(coll, "GorgeGlow", (x, y, 2.0), col, pw, 3.0)
        n += 1
        side = -side
        y += 8.0
    # golem: crystal + eyes + underglow from the flowers around its feet
    g = GOLEM_POS
    point_light(coll, "CrystalGlow", g + Vector((0, -3.5, 19.5)) * GS, (1.0, 0.15, 0.55), 2500.0, 1.0)
    for sx in (-1.7, 1.7):
        point_light(coll, "EyeGlow", g + Vector((sx, -3.6, 28.3)) * GS, (0.5, 0.9, 1.0), 90.0, 0.3)
    point_light(coll, "FaceUp", g + Vector((0, -16, 18)), (0.35, 0.6, 1.0), 6000.0, 6.0)
    point_light(coll, "FaceUpPink", g + Vector((-8, -12, 6)), (1.0, 0.2, 0.6), 4000.0, 5.0)
    for k, (x, y) in enumerate(((-16, 200), (14, 198), (-26, 222), (26, 222), (0, 204))):
        col = ramp_color(ZONE_RAMP, 0.18 if k % 2 else 0.8)
        point_light(coll, "GolemUnder", (x, y, 1.5), col, 2200.0, 4.0)
    print("lights", n)


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
    dirv = tc.outputs["Generated"]
    _, _, z = b.sep(dirv)
    sky = b.ramp(z, [(0.0, (0.006, 0.008, 0.016)), (0.5, (0.030, 0.026, 0.065)), (0.58, (0.016, 0.018, 0.045)),
                     (0.8, (0.005, 0.007, 0.022)), (1.0, (0.002, 0.003, 0.010))])
    # stars
    vor = b.new("ShaderNodeTexVoronoi", feature="F1")
    b.set(vor.inputs["Vector"], dirv)
    vor.inputs["Scale"].default_value = 520.0
    scs = b.new("ShaderNodeSeparateColor")
    b.set(scs.inputs[0], vor.outputs["Color"])
    star = b.math("MULTIPLY", b.math("LESS_THAN", vor.outputs["Distance"], 0.09), b.math("GREATER_THAN", scs.outputs[0], 0.9))
    star = b.math("MULTIPLY", star, b.math("MULTIPLY", b.math("GREATER_THAN", z, 0.52), b.math("ADD", 0.3, scs.outputs[1])))
    # moon low in the north, behind the golem
    md = Vector((0.22, 1.0, math.tan(math.radians(17.5)))).normalized()
    dp = b.vmath("DOT_PRODUCT", dirv, tuple(md))
    disc = b.math("GREATER_THAN", dp, math.cos(math.radians(1.6)))
    halo = b.math("POWER", b.math("MAXIMUM", dp, 0.0), 260.0)
    halo2 = b.math("POWER", b.math("MAXIMUM", dp, 0.0), 18.0)
    col = b.mix(b.math("MINIMUM", b.math("ADD", b.math("MULTIPLY", halo, 0.35), b.math("MULTIPLY", halo2, 0.08)), 1.0),
                sky, (0.35, 0.45, 0.75))
    bg = b.new("ShaderNodeBackground")
    b.set(bg.inputs["Color"], col)
    bg.inputs["Strength"].default_value = 2.2
    em = b.new("ShaderNodeEmission")
    b.set(em.inputs["Strength"], b.math("ADD", b.math("MULTIPLY", disc, 9.0), b.math("MULTIPLY", star, 3.0)))
    em.inputs["Color"].default_value = (0.85, 0.9, 1.0, 1)
    add = b.new("ShaderNodeAddShader")
    nt.links.new(bg.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    w.mist_settings.start = 8.0
    w.mist_settings.depth = 330.0
    w.mist_settings.falloff = "QUADRATIC"
    # moonlight from behind the golem (rim light), and a faint sky fill
    sd = bpy.data.lights.new("Moon", "SUN")
    sd.energy = 0.9
    sd.color = (0.55, 0.68, 1.0)
    sd.angle = math.radians(1.0)
    so = bpy.data.objects.new("Moon", sd)
    so.rotation_euler = Vector((0, 0, -1)).rotation_difference(-md).to_euler()
    scene.collection.objects.link(so)
    fd = bpy.data.lights.new("SkyFill", "SUN")
    fd.energy = 1.1
    fd.color = (0.4, 0.55, 1.0)
    fd.angle = math.radians(20)
    fo = bpy.data.objects.new("SkyFill", fd)
    fo.rotation_euler = (math.radians(18), math.radians(-10), 0)
    scene.collection.objects.link(fo)


# ----------------------------------------------------------------------------
# Camera path (one continuous FPV take)
# ----------------------------------------------------------------------------
def control_points():
    pts = [Vector((gorge_cx(-352), -352, 25.0)), Vector((gorge_cx(-318), -318, 18.0)),
           Vector((gorge_cx(-286), -286, 10.5)), Vector((gorge_cx(-262), -262, 5.0))]
    y = -246.0
    while y < -24:
        x = gorge_cx(y) + 1.3 * math.sin(y / 27.0)
        z = 3.4 + 1.1 * math.sin(y / 31.0)
        if abs(y + 150) < 22:
            z = lerp(z, 2.9, 1 - abs(y + 150) / 22)
        if abs(y + 62) < 18:
            z = lerp(z, 2.6, 1 - abs(y + 62) / 18)
        pts.append(Vector((x, y, z)))
        y += 14.0
    pts += [Vector((0.0, -10.0, 3.3)), Vector((0.0, 8.0, 6.5)), Vector((-2.0, 28.0, 15.0)),
            Vector((-6.0, 52.0, 21.0)), Vector((-20.0, 74.0, 10.0)), Vector((-46.0, 93.0, 3.0)),
            Vector((-66.0, 120.0, 2.7)), Vector((-63.0, 152.0, 2.7)), Vector((-45.0, 174.0, 2.8)),
            Vector((-22.0, 183.0, 2.9)), Vector((-6.0, 187.0, 3.6)), Vector((1.5, 193.0, 7.0)),
            Vector((2.5, 199.0, 13.0)), Vector((1.8, 204.5, 20.0)), Vector((1.0, 209.0, 26.5)),
            Vector((0.6, 212.5, 31.0)), Vector((0.4, 214.0, 32.6))]
    return pts


def catmull(pts, per=24):
    out = []
    P = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        # centripetal parameterisation
        def tj(ti, a, b):
            return ti + max(1e-4, (b - a).length) ** 0.5
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for k in range(per):
            t = t1 + (t2 - t1) * k / per
            A1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            A2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            A3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            B1 = A1 * ((t2 - t) / (t2 - t0)) + A2 * ((t - t0) / (t2 - t0))
            B2 = A2 * ((t3 - t) / (t3 - t1)) + A3 * ((t - t1) / (t3 - t1))
            out.append(B1 * ((t2 - t) / (t2 - t1)) + B2 * ((t - t1) / (t2 - t1)))
    out.append(pts[-1].copy())
    return out


class Path:
    def __init__(self, pts):
        self.p = pts
        self.s = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.s.append(self.s[-1] + (b - a).length)
        self.L = self.s[-1]

    def at(self, s):
        s = clamp(s, 0.0, self.L)
        lo, hi = 0, len(self.s) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.s[mid] <= s:
                lo = mid
            else:
                hi = mid
        u = (s - self.s[lo]) / max(1e-6, self.s[hi] - self.s[lo])
        return self.p[lo].lerp(self.p[hi], u)


SPEED_KEYS = [(0, 11.0), (60, 17.0), (110, 19.5), (420, 19.5), (470, 15.0), (540, 9.0), (590, 5.2), (640, 5.0),
              (700, 11.0), (760, 12.5), (1060, 11.5), (1110, 8.5), (1180, 5.5), (1260, 3.2), (1340, 1.1),
              (1439, 0.35)]


def speed_at(f):
    for (f0, v0), (f1, v1) in zip(SPEED_KEYS, SPEED_KEYS[1:]):
        if f <= f1:
            u = (f - f0) / (f1 - f0)
            u = u * u * (3 - 2 * u)
            return lerp(v0, v1, u)
    return SPEED_KEYS[-1][1]


def gaussian(vals, sigma):
    if sigma <= 0:
        return vals[:]
    r = int(sigma * 3)
    w = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-r, r + 1)]
    out = []
    n = len(vals)
    for i in range(n):
        acc, ws = 0.0, 0.0
        for k in range(-r, r + 1):
            j = min(n - 1, max(0, i + k))
            acc += vals[j] * w[k + r]
            ws += w[k + r]
        out.append(acc / ws)
    return out


def build_camera(scene, path):
    frames = list(range(F_START - 2, F_END + 3))
    raw = [speed_at(max(0, f)) for f in frames]
    s = [0.0]
    for v in raw[1:]:
        s.append(s[-1] + v / FPS)
    k = path.L / s[frames.index(F_END)]
    s = [x * k for x in s]
    print("path length %.1f m, speed scale %.3f" % (path.L, k))
    pos = [path.at(x) for x in s]
    spd = [v * k for v in raw]
    # look direction along the path with a speed dependent look-ahead
    dirs = []
    for i, f in enumerate(frames):
        ahead = max(3.0, spd[i] * 0.55)
        a = path.at(s[i] + ahead)
        b = path.at(max(0.0, s[i] - 1.0))
        d = (a - b)
        if d.length < 1e-4:
            d = dirs[-1] if dirs else Vector((0, 1, 0))
        dirs.append(d.normalized())
    yaw = [math.atan2(d.y, d.x) for d in dirs]
    for i in range(1, len(yaw)):
        while yaw[i] - yaw[i - 1] > math.pi:
            yaw[i] -= 2 * math.pi
        while yaw[i] - yaw[i - 1] < -math.pi:
            yaw[i] += 2 * math.pi
    yaw = gaussian(yaw, 4)
    pitch = gaussian([math.asin(clamp(d.z, -1, 1)) for d in dirs], 5)
    yr = [(yaw[min(i + 1, len(yaw) - 1)] - yaw[max(i - 1, 0)]) * FPS / 2 for i in range(len(yaw))]
    bank = [clamp(math.atan(spd[i] * yr[i] / 9.81) * 0.85, -0.66, 0.66) for i in range(len(yaw))]
    bank = gaussian(bank, 7)

    cam_d = bpy.data.cameras.new("FPV")
    cam_d.sensor_width = 36.0
    cam_d.clip_start = 0.05
    cam_d.clip_end = 2000.0
    cam_d.dof.use_dof = True
    cam = bpy.data.objects.new("FPV", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.rotation_mode = "QUATERNION"
    prev = None
    face = FACE
    for i, f in enumerate(frames):
        fp = max(0, f)
        p = pos[i]
        # reveal: tilt down over the field; final: settle onto the golem's face
        tilt = -math.radians(24) * smootherstep(520, 600, fp) * (1 - smootherstep(640, 730, fp))
        yw, pt = yaw[i], pitch[i] + tilt
        fwd = Vector((math.cos(yw) * math.cos(pt), math.sin(yw) * math.cos(pt), math.sin(pt)))
        w = smootherstep(1120, 1270, fp)
        to_face = (face - p).normalized()
        d = fwd.lerp(to_face, w).normalized()
        roll = bank[i] * (1 - w)
        # FPV micro-shake, scaled by speed
        amp = math.radians(0.28) * (spd[i] / 19.5) + math.radians(0.05)
        jx = amp * noise.noise(Vector((fp * 0.16, 1.3, 0.0)))
        jy = amp * noise.noise(Vector((fp * 0.16, 7.9, 0.0)))
        jr = amp * 1.4 * noise.noise(Vector((fp * 0.11, 4.2, 0.0)))
        jx += amp * 0.35 * noise.noise(Vector((fp * 0.55, 2.0, 1.0)))
        q = d.to_track_quat("-Z", "Y")
        q = q @ Quaternion((0, 0, 1), roll + jr) @ Quaternion((1, 0, 0), jy) @ Quaternion((0, 1, 0), jx)
        if prev is not None and q.dot(prev) < 0:
            q = -q
        prev = q
        cam.location = p
        cam.rotation_quaternion = q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
        lens = 17.0
        lens = lerp(lens, 21.0, smootherstep(480, 600, fp))
        lens = lerp(lens, 18.0, smootherstep(660, 760, fp))
        lens = lerp(lens, 25.0, smootherstep(1150, 1420, fp))
        cam_d.lens = lens
        cam_d.keyframe_insert("lens", frame=f)
        cam_d.dof.aperture_fstop = lerp(16.0, 2.8, smootherstep(1150, 1300, fp))
        cam_d.dof.focus_distance = lerp(30.0, (face - p).length, smootherstep(1100, 1220, fp))
        cam_d.dof.keyframe_insert("aperture_fstop", frame=f)
        cam_d.dof.keyframe_insert("focus_distance", frame=f)
    # report a few timing landmarks
    for fp in (0, 120, 300, 470, 520, 620, 760, 1000, 1150, 1300, 1439):
        i = frames.index(fp)
        print("frame %4d  pos (%.1f, %.1f, %.1f)  v %.1f m/s" % (fp, pos[i].x, pos[i].y, pos[i].z, spd[i]))
    return cam, pos


def path_mesh(coll, dense):
    me = bpy.data.meshes.new("CamPath")
    me.from_pydata([tuple(p) for p in dense], [(i, i + 1) for i in range(len(dense) - 1)], [])
    ob = bpy.data.objects.new("CamPath", me)
    coll.objects.link(ob)
    ob.hide_render = True
    return ob


# ----------------------------------------------------------------------------
# Render settings + compositor
# ----------------------------------------------------------------------------
FOG = (0.008, 0.016, 0.032)


def build_compositor(scene):
    ng = bpy.data.node_groups.new("LumenComp", "CompositorNodeTree")
    scene.compositing_node_group = ng
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers")
    rl.scene = scene
    mr = N.new("ShaderNodeMapRange")
    mr.inputs["To Max"].default_value = 0.85
    L.new(rl.outputs["Mist"], mr.inputs["Value"])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(mr.outputs[0], sock(mix, "Factor_Float"))
    L.new(rl.outputs["Image"], sock(mix, "A_Color"))
    sock(mix, "B_Color").default_value = (*FOG, 1)
    gl = N.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Quality"].default_value = "High"
    gl.inputs["Threshold"].default_value = 0.6
    gl.inputs["Strength"].default_value = 0.7
    gl.inputs["Size"].default_value = 0.85
    L.new(sock(mix, "Result_Color", out=True), gl.inputs["Image"])
    ld = N.new("CompositorNodeLensdist")
    ld.inputs["Dispersion"].default_value = 0.012
    L.new(gl.outputs["Image"], ld.inputs["Image"])
    go = N.new("NodeGroupOutput")
    L.new(ld.outputs["Image"], go.inputs[0])
    scene.render.use_compositing = True


def render_settings(scene):
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = 1440, 603
    r.resolution_percentage = 100
    r.use_motion_blur = True
    r.motion_blur_shutter = 0.5
    r.use_persistent_data = True
    r.filepath = "//frames/lg_"
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    c = scene.cycles
    c.device = "CPU"
    c.samples = 8
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.05
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    c.max_bounces = 3
    c.diffuse_bounces = 1
    c.glossy_bounces = 1
    c.transmission_bounces = 0
    c.transparent_max_bounces = 4
    c.volume_bounces = 0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 5.0
    c.blur_glossy = 1.0
    try:
        c.use_light_tree = True
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
    vs.exposure = 0.4


# ----------------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.join(HERE, "lumen_garden.blend")
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "LumenGarden"
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = F_START, F_END
    build_materials()
    world_c = new_collection("World")
    terrain = build_terrain(world_c)
    dense = catmull(control_points(), 24)
    path = Path(dense)
    cam, cam_pos = build_camera(scene, path)
    pkd = kdtree.KDTree(len(dense))
    for i, p in enumerate(dense):
        pkd.insert(p, i)
    pkd.balance()
    pobj = path_mesh(world_c, dense)
    boulders = build_boulders(world_c, dense)
    golem_base, golem_upper = build_golem(world_c)
    protos = build_prototypes()
    flora = new_collection("Flora")
    ng, ident = scatter_group(protos, pobj)
    for ob, mult, seed in ((terrain["CraterFloor"], 1.0, 1), (terrain["GorgeFloor"], 1.0, 2),
                           (terrain["CraterWall"], 1.0, 3), (terrain["GorgeWall_L"], 1.0, 4),
                           (terrain["GorgeWall_R"], 1.0, 5), (boulders, 1.0, 6),
                           (golem_base, 1.0, 7), (golem_upper, 1.0, 8)):
        add_scatter(ob, ng, ident, mult, seed)
    walls = [terrain["GorgeWall_L"], terrain["GorgeWall_R"], terrain["CraterWall"]]
    build_vines(flora, walls, pkd)
    build_fungi(flora, walls, pkd)
    build_giants(flora, protos, pkd)
    build_spores(flora, [cam_pos[i] for i in range(0, len(cam_pos), 2)])
    light_c = new_collection("Lights")
    build_lights(light_c)
    build_world(scene)
    render_settings(scene)
    build_compositor(scene)
    bpy.context.view_layer.update()
    # clearance report along the flight path
    for nm in ("GorgeWall_L", "GorgeWall_R", "CraterWall"):
        me = terrain[nm].data
        kd = kdtree.KDTree(len(me.vertices))
        for i, v in enumerate(me.vertices):
            kd.insert(v.co, i)
        kd.balance()
        md, mf = 1e9, -1
        for i, p in enumerate(cam_pos):
            _, _, d = kd.find(p)
            if d < md:
                md, mf = d, i - 2
        print("clearance %-12s %.2f m at frame %d" % (nm, md, mf))
    for ob in (boulders, golem_base, golem_upper):
        me = ob.data
        kd = kdtree.KDTree(len(me.vertices))
        mw = ob.matrix_world
        for i, v in enumerate(me.vertices):
            kd.insert(mw @ v.co, i)
        kd.balance()
        md, mf = 1e9, -1
        for i, p in enumerate(cam_pos):
            _, _, d = kd.find(p)
            if d < md:
                md, mf = d, i - 2
        print("clearance %-12s %.2f m at frame %d" % (ob.name, md, mf))
    gmin = min((p.z - ground_h(p.x, p.y), i - 2) for i, p in enumerate(cam_pos))
    print("min height over ground %.2f m at frame %d" % gmin)
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
