"""Procedural forest clearing: terrain, conifers, broadleaf trees, ferns, grass,
rocks, a fallen log and floating dust motes.  Everything is instanced."""
import bpy, numpy as np, math
from mathutils import Euler
from trex_build import mesh_from_arrays, add_float_attr, NT, sstep

CLEAR_C = np.array([0.0, -5.0])          # centre of the clearing (between dinosaur and camera)
D_FAR = 30.0                             # beyond this the forest is baked into a background plate

def ground_h(x, y):
    r = np.hypot(x - CLEAR_C[0], y - CLEAR_C[1])
    far = sstep(7.0, 18.0, r)
    big = 0.55 * np.sin(x * 0.11 + 1.3) * np.cos(y * 0.09 + 0.4) + 0.30 * np.sin(x * 0.27 + y * 0.21 + 2.0)
    rise = 0.00042 * np.maximum(r - 12, 0) ** 2
    det = 0.05 * np.sin(x * 1.9 + 0.5 * np.sin(y * 2.3)) * np.sin(y * 1.7 + 1.0) + 0.025 * np.sin(x * 4.3 + 2) * np.sin(y * 3.9)
    return far * (big + rise) + det * (0.25 + 0.75 * far)

def rot_z(v, a):
    c, s = np.cos(a), np.sin(a)
    return np.stack([c * v[..., 0] - s * v[..., 1], s * v[..., 0] + c * v[..., 1], v[..., 2]], -1)

# ------------------------------------------------------------------ geometry
def tube(path, radii, sides=8):
    """tube mesh along a polyline; returns verts, quad faces."""
    path = np.asarray(path, float); n = len(path)
    tang = np.gradient(path, axis=0); tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    ref = np.where(np.abs(tang[:, 2:3]) > 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 0, 1.0]]))
    a = np.cross(tang, ref); a /= np.linalg.norm(a, axis=1, keepdims=True); b = np.cross(tang, a)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    v = path[:, None, :] + np.asarray(radii)[:, None, None] * (np.cos(ang)[None, :, None] * a[:, None, :] + np.sin(ang)[None, :, None] * b[:, None, :])
    i = np.arange(n - 1)[:, None] * sides + np.arange(sides)[None, :]
    j = np.arange(n - 1)[:, None] * sides + (np.arange(sides)[None, :] + 1) % sides
    f = np.stack([i, j, j + sides, i + sides], -1).reshape(-1, 4)
    return v.reshape(-1, 3), f

def leaves(centres, axis, normal, length, width, fold=0.18):
    """diamond leaves (2 tris each). arrays are (N,3)/(N,)."""
    side = np.cross(normal, axis); side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
    L = length[:, None]; W = width[:, None]
    base = centres - axis * L * 0.5; tip = centres + axis * L * 0.5
    up = normal * W * fold
    l = centres - side * W * 0.5 + up; r = centres + side * W * 0.5 + up
    v = np.stack([base, r, tip, l], 1).reshape(-1, 3)
    k = np.arange(len(centres))[:, None] * 4
    f = np.concatenate([k + [0, 1, 2], k + [0, 2, 3]], 0)
    return v, f

def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)

class MeshAcc:
    def __init__(s): s.v = []; s.f = []; s.mat = []; s.var = []; s.n = 0
    def add(s, v, f, mat, var=0.0):
        f = np.asarray(f)
        if f.shape[1] == 4:
            f = np.concatenate([f[:, [0, 1, 2]], f[:, [0, 2, 3]]])
        s.v.append(v); s.f.append(f + s.n); s.mat.append(np.full(len(f), mat, np.int32))
        s.var.append(np.broadcast_to(np.asarray(var, np.float32), (len(v),)).copy()); s.n += len(v)
    def build(s, name, mats, smooth_mat0=True):
        v = np.concatenate(s.v); f = np.concatenate(s.f); mi = np.concatenate(s.mat)
        me = mesh_from_arrays(name, v, f, smooth=False)
        me.polygons.foreach_set("material_index", mi)
        me.polygons.foreach_set("use_smooth", mi == 0 if smooth_mat0 else np.zeros(len(mi), bool))
        add_float_attr(me, "var", np.concatenate(s.var))
        for m in mats: me.materials.append(m)
        me.update()
        return me

def trunk_path(h, r0, rng, flare=0.9, n=18):
    z = h * np.linspace(0, 1, n) ** 1.5
    ph = rng.uniform(0, 6.28, 2)
    off = np.stack([np.sin(z / h * 2.1 + ph[0]), np.sin(z / h * 1.7 + ph[1])], 1) * h * 0.018 * (z / h)[:, None]
    path = np.concatenate([off, z[:, None]], 1)
    rad = r0 * (1 - 0.8 * (z / h) ** 1.1) + r0 * flare * np.exp(-z / (r0 * 1.6))
    return path, rad

def make_conifer(rng, h, r0, mats, name):
    acc = MeshAcc()
    path, rad = trunk_path(h, r0, rng)
    path[0, 2] = -0.6
    acc.add(*tube(path, rad, 12), 0)
    zs = np.arange(h * rng.uniform(0.38, 0.5), h * 0.98, rng.uniform(1.0, 1.4))
    for z in zs:
        f = (z - zs[0]) / (h - zs[0])
        nb = rng.integers(4, 7); a0 = rng.uniform(0, 6.28)
        c = np.array([np.interp(z, path[:, 2], path[:, 0]), np.interp(z, path[:, 2], path[:, 1]), z])
        for k in range(nb):
            az = a0 + 2 * np.pi * k / nb + rng.uniform(-0.3, 0.3)
            Lb = (1.3 + 5.5 * (1 - f) ** 0.8) * rng.uniform(0.75, 1.1)
            t = np.linspace(0, 1, 7)
            droop = rng.uniform(0.25, 0.5)
            loc = np.stack([t * Lb, np.zeros(7), Lb * (0.12 * t - droop * t ** 2 + 0.22 * t ** 4)], 1)
            pts = rot_z(loc, az) + c
            acc.add(*tube(pts, 0.03 + 0.09 * (1 - t) * (1 - f * 0.6), 5), 0)
            # sprigs of foliage hanging along the branch
            ns = int(26 * Lb)
            tt = rng.uniform(0.18, 1.0, ns) ** 0.8
            cen = np.stack([np.interp(tt, t, pts[:, i]) for i in range(3)], 1)
            cen += rng.normal(0, 1, (ns, 3)) * np.array([0.38, 0.38, 0.16]) * (0.5 + tt[:, None])
            out = rot_z(np.array([1.0, 0, 0]), az)
            ax = unit(out + rng.normal(0, 0.55, (ns, 3)) + np.array([0, 0, -0.45]))
            nor = unit(np.array([0, 0, 1.0]) + rng.normal(0, 0.45, (ns, 3)))
            acc.add(*leaves(cen, ax, nor, rng.uniform(0.5, 0.95, ns), rng.uniform(0.16, 0.3, ns)), 1, np.repeat(rng.random(ns), 4))
    return acc.build(name, mats)

def make_broadleaf(rng, h, r0, mats, name):
    acc = MeshAcc()
    hs = h * rng.uniform(0.42, 0.55)
    path, rad = trunk_path(hs, r0, rng, n=12)
    rad = r0 * (1 - 0.35 * np.linspace(0, 1, 12)) + r0 * 0.9 * np.exp(-path[:, 2] / (r0 * 1.6)); path[0, 2] = -0.6
    acc.add(*tube(path, rad, 12), 0)
    top = path[-1]
    nb = rng.integers(4, 7)
    for k in range(nb):
        az = 2 * np.pi * k / nb + rng.uniform(-0.4, 0.4)
        Lb = (h - hs) * rng.uniform(0.75, 1.15)
        t = np.linspace(0, 1, 8)
        spread = rng.uniform(0.45, 0.85)
        loc = np.stack([spread * Lb * t ** 1.3, 0.12 * Lb * np.sin(t * 3 + k), Lb * 0.85 * t ** 0.8], 1)
        pts = rot_z(loc, az) + top
        acc.add(*tube(pts, r0 * 0.5 * (1 - 0.85 * t) + 0.03, 7), 0)
        for j in range(3):                              # leaf clouds on the outer half of each bough
            cc = pts[rng.integers(4, 8)] + rng.normal(0, 1.0, 3) * [1.2, 1.2, 0.6]
            R = rng.uniform(2.0, 3.4)
            nl = int(520 * R / 2.7)
            d = unit(rng.normal(0, 1, (nl, 3)))
            cen = cc + d * R * rng.uniform(0.45, 1.0, (nl, 1)) ** 0.6 * np.array([1.0, 1.0, 0.6])
            ax = unit(rng.normal(0, 1, (nl, 3)) + np.array([0, 0, -0.5]))
            nor = unit(rng.normal(0, 1, (nl, 3)) + np.array([0, 0, 1.2]))
            acc.add(*leaves(cen, ax, nor, rng.uniform(0.35, 0.6, nl), rng.uniform(0.2, 0.34, nl)), 1, np.repeat(rng.random(nl), 4))
    return acc.build(name, mats)

def make_fern(rng, mats, name, size=1.0, trunk=0.0):
    acc = MeshAcc()
    nf = rng.integers(11, 18)
    if trunk > 0:
        acc.add(*tube([(0, 0, -0.2), (0.02, 0, trunk * 0.5), (0, 0.03, trunk)], [0.16, 0.13, 0.12], 8), 2)
    NP = 40
    for k in range(nf):
        az = 2 * np.pi * k / nf + rng.uniform(-0.25, 0.25)
        L = size * rng.uniform(0.75, 1.25)
        el = rng.uniform(0.35, 1.25)                    # launch elevation
        t = np.linspace(0, 1, NP + 2)
        loc = np.stack([L * (np.cos(el) * t + 0.12 * t ** 2), np.zeros_like(t), L * (np.sin(el) * t - (0.55 + 0.3 * np.cos(el)) * t ** 2.2)], 1)
        pts = rot_z(loc, az) + np.array([0, 0, trunk])
        var = rng.random()
        acc.add(*tube(pts[::6], 0.012 * size * (1 - 0.8 * t[::6]) + 0.003, 4), 1, var)
        tang = unit(np.gradient(pts, axis=0))
        side = unit(np.cross(tang, np.array([0, 0, 1.0])))
        nor = np.cross(side, tang)
        idx = np.arange(2, NP + 2)
        pl = L * 0.25 * np.sin(np.pi * ((idx - 1.5) / (NP + 0.5)) ** 0.75) + 0.015
        for sgn in (1, -1):
            ax = unit(sgn * side[idx] + 0.4 * tang[idx] - 0.3 * nor[idx])
            cen = pts[idx] + ax * pl[:, None] * 0.5
            acc.add(*leaves(cen, ax, nor[idx], pl, np.full(len(idx), L * 0.03), fold=0.1), 1, var)
    return acc.build(name, mats, smooth_mat0=False)

def make_grass(rng, mats, name):
    acc = MeshAcc()
    nb = 46
    for k in range(nb):
        az = rng.uniform(0, 6.28); lean = rng.uniform(0.1, 0.8); L = rng.uniform(0.12, 0.42)
        base = np.array([rng.normal(0, 0.12), rng.normal(0, 0.12), -0.02])
        t = np.linspace(0, 1, 5)
        loc = np.stack([L * lean * t ** 1.8, np.zeros(5), L * t * (1 - 0.25 * lean * t)], 1)
        c = rot_z(loc, az) + base
        s = rot_z(np.array([0.0, 1.0, 0]), az) * (0.012 * (1 - t ** 2))[:, None]
        v = np.concatenate([c - s, c + s]); i = np.arange(4)
        f = np.stack([i, i + 1, i + 6, i + 5], 1)
        acc.add(v, f, 1, rng.random())
    return acc.build(name, mats, smooth_mat0=False)

def make_rock(rng, mats, name):
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    v = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", v); v = v.reshape(-1, 3).astype(float)
    ph = rng.uniform(0, 6.28, 6)
    d = 1 + 0.22 * np.sin(v[:, 0] * 2.1 + ph[0]) * np.sin(v[:, 1] * 2.4 + ph[1]) + 0.16 * np.sin(v[:, 2] * 3.3 + ph[2]) * np.sin(v[:, 0] * 3.1 + ph[3]) \
        + 0.06 * np.sin(v[:, 1] * 7 + ph[4]) * np.sin(v[:, 2] * 6 + ph[5])
    v = v * d[:, None] * np.array([1.0, 0.8, 0.55])
    me.vertices.foreach_set("co", v.astype(np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool)); me.update()
    add_float_attr(me, "var", np.zeros(len(v)))
    me.materials.append(mats[3])
    return me

# ----------------------------------------------------------------- materials
def bark_material():
    mat = bpy.data.materials.new("Bark"); mat.use_nodes = True
    n = NT(mat.node_tree); b = n.nodes["Principled BSDF"]
    tc = n.node("ShaderNodeTexCoord"); mp = n.node("ShaderNodeMapping"); n.links.new(tc.outputs["Object"], mp.inputs[0]); mp.inputs["Scale"].default_value = (7, 7, 0.9)
    nz = n.set(n.node("ShaderNodeTexNoise"), Vector=mp.outputs[0], Scale=1.0, Detail=3.0, Roughness=0.65)
    col = n.ramp(nz.outputs[0], [(0.3, (0.012, 0.009, 0.007, 1)), (0.62, (0.075, 0.05, 0.034, 1)), (0.8, (0.14, 0.11, 0.08, 1))])
    sep = n.node("ShaderNodeSeparateXYZ"); n.links.new(tc.outputs["Object"], sep.inputs[0])
    moss = n.math('MULTIPLY', n.math('SUBTRACT', 1.0, n.smooth(0.3, 3.5, sep.outputs[2])), n.smooth(0.4, 0.6, nz.outputs[0]))
    col = n.mix(moss, col, (0.035, 0.065, 0.012, 1))
    n.links.new(col, b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.85
    bump = n.node("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.05
    n.links.new(nz.outputs[0], bump.inputs["Height"]); n.links.new(bump.outputs[0], b.inputs["Normal"])
    return mat

def leaf_material(name, dark, light, trans=0.45):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    n = NT(mat.node_tree); out = n.nodes["Material Output"]; n.nodes.remove(n.nodes["Principled BSDF"])
    col = n.mix(n.attr("var"), dark, light)
    dif = n.node("ShaderNodeBsdfDiffuse"); tr = n.node("ShaderNodeBsdfTranslucent"); gl = n.node("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.35
    n.links.new(col, dif.inputs[0])
    hs = n.node("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = 1.25; hs.inputs["Value"].default_value = 1.6; n.links.new(col, hs.inputs["Color"])
    n.links.new(hs.outputs[0], tr.inputs[0])
    m1 = n.node("ShaderNodeMixShader"); m1.inputs[0].default_value = trans
    n.links.new(dif.outputs[0], m1.inputs[1]); n.links.new(tr.outputs[0], m1.inputs[2])
    m2 = n.node("ShaderNodeMixShader"); m2.inputs[0].default_value = 0.06
    n.links.new(m1.outputs[0], m2.inputs[1]); n.links.new(gl.outputs[0], m2.inputs[2])
    n.links.new(m2.outputs[0], out.inputs["Surface"])
    return mat

def rock_material():
    mat = bpy.data.materials.new("Rock"); mat.use_nodes = True
    n = NT(mat.node_tree); b = n.nodes["Principled BSDF"]
    tc = n.node("ShaderNodeTexCoord")
    nz = n.set(n.node("ShaderNodeTexNoise"), Vector=tc.outputs["Object"], Scale=3.0, Detail=4.0, Roughness=0.6)
    geo = n.node("ShaderNodeNewGeometry"); sep = n.node("ShaderNodeSeparateXYZ"); n.links.new(geo.outputs["Normal"], sep.inputs[0])
    col = n.ramp(nz.outputs[0], [(0.3, (0.03, 0.03, 0.028, 1)), (0.7, (0.12, 0.115, 0.10, 1))])
    moss = n.math('MULTIPLY', n.smooth(0.25, 0.75, sep.outputs[2]), n.smooth(0.35, 0.55, nz.outputs[0]))
    col = n.mix(moss, col, (0.03, 0.06, 0.01, 1))
    n.links.new(col, b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.8
    bump = n.node("ShaderNodeBump"); bump.inputs["Distance"].default_value = 0.08
    n.links.new(nz.outputs[0], bump.inputs["Height"]); n.links.new(bump.outputs[0], b.inputs["Normal"])
    return mat

def ground_material():
    mat = bpy.data.materials.new("ForestFloor"); mat.use_nodes = True
    n = NT(mat.node_tree); b = n.nodes["Principled BSDF"]
    geo = n.node("ShaderNodeNewGeometry"); P = geo.outputs["Position"]
    big = n.set(n.node("ShaderNodeTexNoise"), Vector=P, Scale=0.4, Detail=1.0, Roughness=0.6)
    fine = n.set(n.node("ShaderNodeTexNoise"), Vector=P, Scale=14.0, Detail=3.0, Roughness=0.75)
    soil = n.mix(fine.outputs[0], (0.016, 0.011, 0.007, 1), (0.075, 0.048, 0.027, 1))
    col = n.mix(n.smooth(0.5, 0.62, fine.outputs[0]), soil, (0.105, 0.055, 0.02, 1))                # leaf litter
    col = n.mix(n.smooth(0.5, 0.68, big.outputs[0]), col, n.mix(fine.outputs[0], (0.02, 0.045, 0.008, 1), (0.05, 0.085, 0.015, 1)))  # moss
    n.links.new(col, b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.9
    bump = n.node("ShaderNodeBump"); bump.inputs["Distance"].default_value = 0.03; bump.inputs["Strength"].default_value = 1.0
    n.links.new(fine.outputs[0], bump.inputs["Height"]); n.links.new(bump.outputs[0], b.inputs["Normal"])
    return mat

def mote_material():
    mat = bpy.data.materials.new("Motes"); mat.use_nodes = True
    n = NT(mat.node_tree); out = n.nodes["Material Output"]; n.nodes.remove(n.nodes["Principled BSDF"])
    em = n.node("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.78, 0.45, 1); em.inputs["Strength"].default_value = 3.0
    n.links.new(em.outputs[0], out.inputs["Surface"])
    return mat

# ------------------------------------------------------------------- scatter
def scatter(rng, n, rmin, rmax, min_d, avoid, centre=CLEAR_C, power=1.0, existing=None):
    pts = [] if existing is None else list(existing)
    keep = []
    tries = 0
    while len(keep) < n and tries < n * 60:
        tries += 1
        r = rmin + (rmax - rmin) * rng.random() ** power; a = rng.uniform(0, 2 * np.pi)
        p = centre + r * np.array([np.cos(a), np.sin(a)])
        if avoid(p): continue
        if pts and min_d > 0 and np.min(np.hypot(*(np.array(pts) - p).T)) < min_d: continue
        pts.append(p); keep.append(p)
    return np.array(keep)

def instance(colls, me, name, p, z, rot_z_, scale, tilt=0.0, rng=None):
    near = np.hypot(p[0] - CLEAR_C[0], p[1] - CLEAR_C[1]) < D_FAR
    ob = bpy.data.objects.new(name, me); colls[0 if near else 1].objects.link(ob)
    ob.location = (p[0], p[1], z); ob.scale = (scale,) * 3 if np.isscalar(scale) else scale
    ob.rotation_euler = Euler((tilt * math.cos(rot_z_ * 3), tilt * math.sin(rot_z_ * 3), rot_z_))
    return ob

def build_forest(coll, far_coll, cam_xy, sun_az, view_xy=(0.6, -6.0), seed=11):
    """cam_xy: camera ground position; sun_az: direction (radians, atan2(y,x)) *towards* the sun."""
    rng = np.random.default_rng(seed); colls = (coll, far_coll)
    bark = bark_material()
    needle = leaf_material("Needles", (0.012, 0.035, 0.012, 1), (0.04, 0.085, 0.02, 1), 0.35)
    leaf = leaf_material("Leaves", (0.02, 0.06, 0.01, 1), (0.10, 0.15, 0.02, 1), 0.5)
    fernm = leaf_material("Fern", (0.014, 0.05, 0.010, 1), (0.055, 0.105, 0.018, 1), 0.45)
    rockm = rock_material()
    mats_c = [bark, needle]; mats_b = [bark, leaf]; mats_f = [bark, fernm, bark, rockm]
    out = {}
    # ---- terrain
    s = np.linspace(-1, 1, 420)
    ax = 130 * (0.10 * s + 0.90 * s * np.abs(s) ** 1.6)
    X, Y = np.meshgrid(ax + CLEAR_C[0], ax + CLEAR_C[1], indexing="ij")
    Z = ground_h(X, Y)
    v = np.stack([X, Y, Z], -1).reshape(-1, 3)
    n = len(s); i = (np.arange(n - 1)[:, None] * n + np.arange(n - 1)[None, :]).ravel()
    f = np.stack([i, i + n, i + n + 1, i + 1], 1)
    gme = mesh_from_arrays("Ground", v, f); gme.materials.append(ground_material())
    g = bpy.data.objects.new("Ground", gme); coll.objects.link(g); out["ground"] = g

    sun_dir = np.array([np.cos(sun_az), np.sin(sun_az)])
    cam = np.asarray(cam_xy, float)
    def seg_dist(p, a, b):
        ab = b - a; t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1); return np.linalg.norm(p - (a + t * ab))
    rex = np.array([0.0, -1.0]); view_tgt = np.asarray(view_xy, float)       # view_tgt: where the action is, seen from the camera
    def avoid_tree(p):
        if seg_dist(p, cam, view_tgt + np.array([0.0, 8.0])) < 6.5: return True  # keep the view clear
        if np.linalg.norm(p - rex) < 9.5: return True
        d = p - cam; along = d @ sun_dir; across = abs(d[0] * sun_dir[1] - d[1] * sun_dir[0])
        if 0 < along < 40 and across < 2.6 + 0.07 * along: return True            # near trees leave a gap for the low sun
        if along >= 40 and across < 2.4: return True
        return False
    # ---- trees
    conifers = [make_conifer(rng, h, r, mats_c, f"Conifer{i}") for i, (h, r) in enumerate([(34, 0.75), (27, 0.6), (40, 0.95), (22, 0.45)])]
    broads = [make_broadleaf(rng, h, r, mats_b, f"Broadleaf{i}") for i, (h, r) in enumerate([(20, 0.55), (26, 0.7), (16, 0.42)])]
    tp = scatter(rng, 250, 10.0, 120.0, 4.2, avoid_tree, power=0.75)
    trees = []
    for k, p in enumerate(tp):
        me = conifers[rng.integers(len(conifers))] if rng.random() < 0.62 else broads[rng.integers(len(broads))]
        trees.append(instance(colls, me, f"Tree.{k:03d}", p, float(ground_h(p[0], p[1])) - 0.15, rng.uniform(0, 6.28), rng.uniform(0.8, 1.25), tilt=rng.uniform(0, 0.05)))
    out["trees"] = trees
    # ---- undergrowth
    ferns = [make_fern(rng, mats_f, f"Fern{i}", size=sz, trunk=tr) for i, (sz, tr) in enumerate([(1.0, 0), (1.4, 0), (0.7, 0), (1.7, 0.9), (1.5, 0.45)])]
    grass = [make_grass(rng, mats_f, f"Grass{i}") for i in range(3)]
    rocks = [make_rock(rng, mats_f, f"Rock{i}") for i in range(3)]
    feet = [np.array([0.72, -0.9]), np.array([-0.72, -0.9])]
    def avoid_plant(p, rad=2.6, lane=3.2):
        if seg_dist(p, cam, view_tgt) < lane: return True                        # keep the camera's view of the animal clear
        if np.linalg.norm(p - cam) < 4.5: return True
        if seg_dist(p, np.array([0.0, -6.5]), np.array([0.0, 7.0])) < rad: return True
        return False
    out["plants"] = []
    fp = scatter(rng, 900, 2.5, 70.0, 0.9, avoid_plant, power=1.5)
    for k, p in enumerate(fp):
        me = ferns[rng.choice(5, p=[0.34, 0.24, 0.26, 0.07, 0.09])]
        out["plants"].append(instance(colls, me, f"Fern.{k:03d}", p, float(ground_h(p[0], p[1])), rng.uniform(0, 6.28), rng.uniform(0.7, 1.35), tilt=rng.uniform(0, 0.12)))
    gp = scatter(rng, 2600, 0.5, 38.0, 0.0, lambda p: avoid_plant(p, 1.6, 0.9) or np.linalg.norm(p - cam) < 2.0, power=1.25)
    for k, p in enumerate(gp):
        out["plants"].append(instance(colls, grass[rng.integers(3)], f"Grass.{k:04d}", p, float(ground_h(p[0], p[1])), rng.uniform(0, 6.28), rng.uniform(0.6, 1.5)))
    # two low ferns framing the bottom corners of the shot
    vdir = unit(view_tgt - cam); vside = np.array([vdir[1], -vdir[0]])
    for k, (fw, sd, sc) in enumerate([(3.4, -1.9, 0.8), (3.8, 2.1, 0.85), (5.2, -2.9, 1.0), (5.8, 3.1, 1.1)]):
        p = cam + vdir * fw + vside * sd
        out["plants"].append(instance(colls, ferns[0], f"FernFG.{k}", p, float(ground_h(p[0], p[1])), rng.uniform(0, 6.28), sc))
    rp = scatter(rng, 46, 4.0, 45.0, 2.0, lambda p: avoid_plant(p, 3.0), power=1.2)
    for k, p in enumerate(rp):
        sc = rng.uniform(0.25, 1.3) * np.array([1, rng.uniform(0.7, 1.2), rng.uniform(0.6, 1.0)])
        instance(colls, rocks[rng.integers(3)], f"Rock.{k:02d}", p, float(ground_h(p[0], p[1])) - 0.1 * sc[0], rng.uniform(0, 6.28), tuple(sc), tilt=rng.uniform(0, 0.3))
    # ---- fallen log
    path, rad = trunk_path(17, 0.55, rng, flare=0.5)
    acc = MeshAcc(); acc.add(*tube(path, rad, 12), 0)
    log = bpy.data.objects.new("FallenLog", acc.build("FallenLog", [bark])); coll.objects.link(log)
    log.location = (-7.5, 1.5, 0.35); log.rotation_euler = Euler((0.0, math.radians(86), math.radians(28)))
    # ---- dust motes / pollen drifting in the light
    nm = 380
    c = np.stack([rng.uniform(-7, 7, nm), rng.uniform(-13, 2, nm), rng.uniform(0.2, 7.5, nm)], 1)
    d = unit(rng.normal(0, 1, (nm, 3)))
    side = unit(np.cross(d, rng.normal(0, 1, (nm, 3)))); r = rng.uniform(0.003, 0.008, nm)[:, None]
    up = np.cross(d, side)
    v = np.stack([c + d * r, c + side * r, c + up * r, c - d * r, c - side * r, c - up * r], 1).reshape(-1, 3)
    k = np.arange(nm)[:, None] * 6
    f = np.concatenate([k + t for t in ([0, 1, 2], [0, 2, 4], [0, 4, 5], [0, 5, 1], [3, 2, 1], [3, 4, 2], [3, 5, 4], [3, 1, 5])])
    mm = mesh_from_arrays("Motes", v, f, smooth=False); mm.materials.append(mote_material())
    motes = bpy.data.objects.new("Motes", mm); coll.objects.link(motes); out["motes"] = motes
    return out
