"""Shared helpers (math, node building, meshes, camera spline) for the Blender scene builders."""
import bpy, math
from mathutils import Vector, noise

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
