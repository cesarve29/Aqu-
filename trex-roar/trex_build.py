"""Turns the SDF mesh into a rigged, shaded Blender T-Rex (teeth, eyes, claws,
armature, skin weights, materials with claw-wound scars)."""
import bpy, numpy as np, math
from mathutils import Vector, Matrix
import trex_sdf as T

rng = np.random.default_rng(7)

# ------------------------------------------------------------------ helpers
def mesh_from_arrays(name, verts, faces, smooth=True):
    me = bpy.data.meshes.new(name)
    faces = np.asarray(faces)
    n = faces.shape[1]
    me.vertices.add(len(verts)); me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel())
    me.loops.add(len(faces) * n); me.loops.foreach_set("vertex_index", faces.ravel().astype(np.int32))
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, len(faces) * n, n, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(faces), n, np.int32))
    me.polygons.foreach_set("use_smooth", np.full(len(faces), smooth))
    me.update(); me.validate()
    return me

def add_float_attr(me, name, arr):
    a = me.attributes.new(name, 'FLOAT', 'POINT'); a.data.foreach_set("value", np.asarray(arr, np.float32))

def add_vec_attr(me, name, arr):
    a = me.attributes.new(name, 'FLOAT_VECTOR', 'POINT'); a.data.foreach_set("vector", np.asarray(arr, np.float32).ravel())

def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)

def horn(length, r, curve=0.25, flat=0.8, seg=10, rings=8, root=0.3):
    """curved cone along +Z, curving towards +Y; returns verts, quad faces, t(0 base..1 tip)."""
    ts = np.concatenate([[-root], np.linspace(0, 1, rings)])
    vs, tt = [], []
    for t in ts:
        tc = max(t, 0.0)
        rad = r * (1 - tc ** 1.7) ** 0.8 if t < 1 else 0.0
        rad = max(rad, r * 0.06)
        cy = curve * length * tc ** 2
        for i in range(seg):
            a = 2 * np.pi * i / seg
            vs.append((rad * flat * np.cos(a), cy + rad * np.sin(a), t * length)); tt.append(tc)
    vs.append((0, curve * length, length * 1.02)); tt.append(1.0)
    fs = []
    nr = len(ts)
    for j in range(nr - 1):
        for i in range(seg):
            a = j * seg + i; b = j * seg + (i + 1) % seg
            fs.append((a, b, b + seg, a + seg))
    tip = len(vs) - 1
    tris = [((nr - 1) * seg + i, (nr - 1) * seg + (i + 1) % seg, tip) for i in range(seg)]
    return np.array(vs), fs, tris, np.array(tt)

def frame_from(z_dir, y_hint):
    z = np.asarray(z_dir, float); z /= np.linalg.norm(z)
    y = np.asarray(y_hint, float); y = y - z * (y @ z); y /= np.linalg.norm(y)
    x = np.cross(y, z)
    return np.stack([x, y, z], 1)

class Soup:
    """accumulates rigid bits (teeth/claws) into one mesh with a per-vertex 't' and bone."""
    def __init__(s): s.v = []; s.q = []; s.tr = []; s.t = []; s.bone = []; s.n = 0
    def add(s, verts, quads, tris, t, bone):
        s.q += [tuple(i + s.n for i in f) for f in quads]; s.tr += [tuple(i + s.n for i in f) for f in tris]
        s.v.append(verts); s.t.append(t); s.bone += [bone] * len(verts); s.n += len(verts)
    def build(s, name):
        v = np.concatenate(s.v)
        me = bpy.data.meshes.new(name)
        faces = s.q + s.tr
        me.from_pydata(v.tolist(), [], faces)
        me.polygons.foreach_set("use_smooth", np.ones(len(faces), bool)); me.update()
        add_float_attr(me, "t", np.concatenate(s.t))
        add_float_attr(me, "rnd", np.repeat(rng.random(len(s.v)), [len(x) for x in s.v]))
        return me, s.bone

# --------------------------------------------------------------------- teeth
def make_teeth():
    soup = Soup()
    # (y local, length factor) along each tooth row
    def row(st, jaw, ys, x_in, zcol, zoff, sign, lens):
        for side in (1, -1):
            for y, L in zip(ys, lens):
                if rng.random() < 0.05:
                    continue                                   # missing tooth
                L = L * rng.uniform(0.8, 1.15) * (0.55 if rng.random() < 0.08 else 1.0)
                x = side * (float(T.st_interp(st, 1, y)) - x_in)
                z = float(T.st_interp(st, zcol, y)) + zoff
                base = T.head_to_world([x, y + rng.uniform(-0.008, 0.008), z], jaw)[0]
                d_loc = np.array([side * rng.uniform(0.02, 0.16), rng.uniform(-0.12, 0.10), sign])
                zdir = T.head_dir_to_world(d_loc, jaw)[0]
                back = T.head_dir_to_world([0, 1, 0], jaw)[0]
                R = frame_from(zdir, back)
                r = np.clip(L * 0.21, 0.016, 0.034)
                v, q, tr, t = horn(L, r, curve=rng.uniform(0.12, 0.3), flat=0.72)
                soup.add(v @ R.T + base, q, tr, t, "jaw" if jaw else "head")
    # upper: premaxilla (front arc) + maxilla
    ys_u = np.concatenate([[-1.478, -1.455, -1.415], np.arange(-1.345, -0.36, 0.083)])
    len_u = np.interp(ys_u, [-1.48, -1.40, -1.25, -1.0, -0.8, -0.55, -0.36], [0.085, 0.10, 0.15, 0.185, 0.17, 0.11, 0.055])
    row(T.UPPER, False, ys_u, 0.042, 3, 0.02, -1, len_u)
    ys_l = np.concatenate([[-1.345, -1.31], np.arange(-1.245, -0.42, 0.079)])
    len_l = np.interp(ys_l, [-1.35, -1.25, -1.0, -0.8, -0.55, -0.42], [0.075, 0.11, 0.13, 0.12, 0.08, 0.05])
    row(T.LOWER, True, ys_l, 0.03, 2, -0.02, 1, len_l)
    return soup.build("teeth")

def make_claws():
    soup = Soup()
    for side, sfx in ((1, ".L"), (-1, ".R")):
        m = np.array([side, 1, 1])
        for tip, base_pt in ((T.TOE_MID, T.BALL), (T.TOE_IN, T.BALL), (T.TOE_OUT, T.BALL)):
            d = (tip - base_pt); d[2] = 0; d /= np.linalg.norm(d)
            zdir = (d + np.array([0, 0, -0.18])) * m
            R = frame_from(zdir, [0, 0, -1])
            v, q, tr, t = horn(0.30, 0.075, curve=0.28, flat=0.75, seg=12)
            soup.add(v @ R.T + (tip + np.array([0, 0, 0.035]) - d * 0.06) * m, q, tr, t, "toes" + sfx)
        d = T.HALLUX_B - T.HALLUX_A; d /= np.linalg.norm(d)
        v, q, tr, t = horn(0.13, 0.04, curve=0.3, flat=0.75)
        soup.add(v @ frame_from(d * m, [0, 0, -1]).T + (T.HALLUX_B - d * 0.03) * m, q, tr, t, "meta" + sfx)
        for f in (T.FINGER1, T.FINGER2):
            d = f - T.WRIST; d /= np.linalg.norm(d)
            v, q, tr, t = horn(0.12, 0.03, curve=0.35, flat=0.7)
            soup.add(v @ frame_from(d * m, [0, 0, -1]).T + (f - d * 0.02) * m, q, tr, t, "farm" + sfx)
    return soup.build("claws")

def make_eyes():
    vs, fs, iris, pup, n = [], [], [], [], 0
    seg, rings = 32, 20
    gaze_l = np.array([0.80, -0.60, 0.02])
    for side in (1, -1):
        c = T.head_to_world(T.EYE_C * [side, 1, 1])[0]
        g = T.head_dir_to_world(gaze_l * [side, 1, 1])[0]
        R = frame_from(g, [0, 0, 1])
        r = T.EYE_R * 1.14
        pts = [(0, 0, r)]
        for j in range(1, rings):
            th = np.pi * j / rings
            for i in range(seg):
                ph = 2 * np.pi * i / seg
                pts.append((r * np.sin(th) * np.cos(ph), r * np.sin(th) * np.sin(ph), r * np.cos(th)))
        pts.append((0, 0, -r)); pts = np.array(pts)
        ang = np.arccos(np.clip(pts[:, 2] / r, -1, 1))
        az = np.arctan2(pts[:, 1], pts[:, 0])
        pup.append(np.hypot(ang * np.cos(az) / 0.30, ang * np.sin(az) / 1.0))
        for i in range(seg):
            fs.append((n, n + 1 + i, n + 1 + (i + 1) % seg))
            fs.append((n + len(pts) - 1, n + 1 + (rings - 2) * seg + (i + 1) % seg, n + 1 + (rings - 2) * seg + i))
        for j in range(rings - 2):
            for i in range(seg):
                a = n + 1 + j * seg + i; b = n + 1 + j * seg + (i + 1) % seg
                fs.append((a, a + seg, b + seg, b))
        vs.append(pts @ R.T + c); iris.append(ang); n += len(pts)
    me = bpy.data.meshes.new("eyes"); me.from_pydata(np.concatenate(vs).tolist(), [], fs)
    me.polygons.foreach_set("use_smooth", np.ones(len(fs), bool)); me.update()
    add_float_attr(me, "ang", np.concatenate(iris)); add_float_attr(me, "pup", np.concatenate(pup))
    return me

def make_saliva():
    """thin strands whose top is glued to the upper jaw and bottom to the lower jaw."""
    vs, fs, wj, n = [], [], [], 0
    spots = [(0.20, -0.62), (-0.17, -0.80), (0.12, -1.02), (-0.22, -0.50), (0.24, -0.45)]
    for x, y in spots:
        zu = float(T.st_interp(T.UPPER, 3, y)) + 0.10
        a = T.head_to_world([x, y, zu])[0]
        b = T.head_to_world([x * 0.8, y + 0.04, float(T.st_interp(T.LOWER, 2, y)) - 0.10], True)[0]
        rings, seg = 14, 6
        r0 = rng.uniform(0.0022, 0.004)
        for j in range(rings + 1):
            t = j / rings
            c = a + (b - a) * t + np.array([0.02 * math.sin(x * 50), 0.05, 0.0]) * math.sin(math.pi * t)
            rad = r0 * (0.35 + 2.2 * (2 * t - 1) ** 4 + 0.5 * abs(math.sin(t * 9 + x * 40)))
            for i in range(seg):
                ph = 2 * np.pi * i / seg
                vs.append(c + rad * np.array([np.cos(ph), np.sin(ph), 0])); wj.append(t * t * (3 - 2 * t))
        for j in range(rings):
            for i in range(seg):
                p = n + j * seg + i; q = n + j * seg + (i + 1) % seg
                fs.append((p, q, q + seg, p + seg))
        n += (rings + 1) * seg
    me = bpy.data.meshes.new("saliva"); me.from_pydata(np.array(vs).tolist(), [], fs)
    me.polygons.foreach_set("use_smooth", np.ones(len(fs), bool)); me.update()
    return me, np.array(wj)

# ------------------------------------------------------------------ armature
def bone_table():
    zc = lambda y: float(T.body_axis(y)[0])
    B = [("root", (0, 0.5, 0), (0, -0.5, 0), None),
         ("hips", (0, 0.2, 3.35), (0, -0.9, 3.30), "root"),
         ("spine1", (0, -0.9, 3.30), (0, -1.9, 3.25), "hips"),
         ("spine2", (0, -1.9, 3.25), tuple(T.N0), "spine1"),
         ("neck1", tuple(T.N0), tuple(T.N1), "spine2"),
         ("neck2", tuple(T.N1), tuple(T.N2), "neck1"),
         ("neck3", tuple(T.N2), tuple(T.N3), "neck2"),
         ("head", tuple(T.N3), tuple(T.N3 + T.RH @ np.array([0, -0.9, 0])), "neck3"),
         ("jaw", tuple(T.JAW_PIVOT), tuple(T.head_to_world([0, -1.2, -0.12], True)[0]), "head"),
         ("tongue1", tuple(T.head_to_world([0, -0.22, -0.16], True)[0]), tuple(T.head_to_world([0, -0.62, -0.15], True)[0]), "jaw"),
         ("tongue2", tuple(T.head_to_world([0, -0.62, -0.15], True)[0]), tuple(T.head_to_world([0, -1.04, -0.14], True)[0]), "tongue1")]
    ty = [0.2, 1.3, 2.4, 3.5, 4.6, 5.7, 7.3]
    for i in range(6):
        B.append((f"tail{i+1}", (0, ty[i], zc(ty[i])), (0, ty[i + 1], zc(ty[i + 1])), "hips" if i == 0 else f"tail{i}"))
    for side, sfx in ((1, ".L"), (-1, ".R")):
        m = np.array([side, 1, 1])
        B += [("thigh" + sfx, tuple(T.HIP * m), tuple(T.KNEE * m), "hips"),
              ("shin" + sfx, tuple(T.KNEE * m), tuple(T.ANKLE * m), "thigh" + sfx),
              ("meta" + sfx, tuple(T.ANKLE * m), tuple(T.BALL * m), "shin" + sfx),
              ("toes" + sfx, tuple(T.BALL * m), tuple(T.TOE_MID * m), "meta" + sfx),
              ("uarm" + sfx, tuple(T.SHOULDER * m), tuple(T.ELBOW * m), "spine2"),
              ("farm" + sfx, tuple(T.ELBOW * m), tuple(T.WRIST * m), "uarm" + sfx)]
    return B

def make_armature(coll):
    arm = bpy.data.armatures.new("TRexRig"); ob = bpy.data.objects.new("TRexRig", arm)
    coll.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    for name, h, t, par in bone_table():
        b = arm.edit_bones.new(name); b.head = h; b.tail = t; b.roll = 0
        if par: b.parent = arm.edit_bones[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return ob

def chain_w(s, joints, blend):
    """partition of unity along a chain: returns (n_bones, N) weights; joints ascending."""
    S = [np.ones_like(s)] + [sstep(-0.5, 0.5, (s - j) / b) for j, b in zip(joints, blend)] + [np.zeros_like(s)]
    return np.stack([S[i] - S[i + 1] for i in range(len(joints) + 1)])

def skin_weights(verts, d):
    """dict bone -> weight array, from SDF group membership + chain parameter."""
    N = len(verts); x = verts[:, 0]; y = verts[:, 1].astype(np.float64); z = verts[:, 2].astype(np.float64)
    tau = {g[0]: g[4] for g in T.GROUPS}
    m = {k: np.clip(1 - np.maximum(d["d_" + k], 0) / tau[k], 0, 1) ** 2 for k in tau}
    hj = np.maximum(m["head"], m["jaw"])
    m["neck"] = m["neck"] * (1 - hj) ** 2
    m["axial"] = m["axial"] * (1 - hj)
    W = {}
    def add(name, w):
        W[name] = W.get(name, 0) + w
    ax = chain_w(y, [-1.9, -0.9, 0.2, 1.3, 2.4, 3.5, 4.6, 5.7], [0.7, 0.7, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8])
    for i, nme in enumerate(["spine2", "spine1", "hips", "tail1", "tail2", "tail3", "tail4", "tail5", "tail6"]):
        add(nme, m["axial"] * ax[i])
    # neck parameter: arclength of closest point on the neck polyline
    P = np.stack([y, z], 1); pts = [T.N0[1:], T.N1[1:], T.N2[1:], T.N3[1:]]
    best = np.full(N, 1e9); s_par = np.zeros(N); acc = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a; L = np.linalg.norm(ab)
        t = ((P - a) @ ab) / (L * L)
        tcl = np.clip(t, 0, 1)
        dist = np.linalg.norm(P - (a + tcl[:, None] * ab), axis=1)
        tt = np.where(a is pts[0], np.minimum(t, 1), tcl) if a is pts[0] else tcl
        upd = dist < best
        s_par = np.where(upd, acc + tt * L, s_par); best = np.where(upd, dist, best); acc += L
    l1 = np.linalg.norm(T.N1 - T.N0); l2 = np.linalg.norm(T.N2 - T.N1)
    nk = chain_w(s_par, [0.05, l1, l1 + l2], [0.6, 0.5, 0.5])
    for i, nme in enumerate(["spine2", "neck1", "neck2", "neck3"]):
        add(nme, m["neck"] * nk[i])
    # tongue rides the jaw, with two bones along it
    yl = T.to_local(np.abs(x), y, z, T.RJ, T.JAW_PIVOT, T.HEAD_SCALE)[1]
    tg = d["tongue"]
    tc = chain_w(-yl, [0.30, 0.62], [0.25, 0.3])
    add("head", m["head"] * (1 - tg))
    add("jaw", m["jaw"] * (1 - tg) + tg * tc[0])
    add("tongue1", tg * tc[1]); add("tongue2", tg * tc[2])
    L = x >= 0
    for g in ("thigh", "shin", "meta", "toes", "uarm", "farm"):
        add(g + ".L", m[g] * L); add(g + ".R", m[g] * ~L)
    tot = sum(W.values())
    lost = tot < 1e-4
    W["hips"] = W["hips"] + lost
    tot = sum(W.values())
    return {k: (w / tot).astype(np.float32) for k, w in W.items()}

def assign_weights(ob, W, q=40):
    for name, w in W.items():
        vg = ob.vertex_groups.new(name=name)
        wq = np.round(w * q).astype(np.int32)
        for lvl in range(1, q + 1):
            idx = np.nonzero(wq == lvl)[0]
            if len(idx):
                vg.add(idx.tolist(), lvl / q, 'REPLACE')

def rigid_weights(ob, bones):
    bones = np.array(bones)
    for name in np.unique(bones):
        ob.vertex_groups.new(name=str(name)).add(np.nonzero(bones == name)[0].tolist(), 1.0, 'REPLACE')

def bind(ob, rig):
    md = ob.modifiers.new("Armature", 'ARMATURE'); md.object = rig
    ob.parent = rig

# ----------------------------------------------------------------- materials
class NT:
    """tiny node-tree builder."""
    def __init__(s, tree): s.t = tree; s.nodes = tree.nodes; s.links = tree.links
    def node(s, typ, **props):
        n = s.nodes.new(typ)
        for k, v in props.items(): setattr(n, k, v)
        return n
    def set(s, node, **inputs):
        for k, v in inputs.items():
            key = int(k[1:]) if k[0] == "_" and k[1:].isdigit() else k.replace("_", " ")
            sock = node.inputs[key]
            if isinstance(v, bpy.types.NodeSocket): s.links.new(v, sock)
            else: sock.default_value = v
        return node
    def math(s, op, a, b=None, c=None, clamp=False):
        n = s.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None: continue
            if isinstance(v, bpy.types.NodeSocket): s.links.new(v, n.inputs[i])
            else: n.inputs[i].default_value = v
        return n.outputs[0]
    def mix(s, fac, a, b, typ='RGBA', blend='MIX'):
        n = s.node("ShaderNodeMix", data_type=typ, blend_type=blend)
        ia, ib = (n.inputs["A"], n.inputs["B"]) if typ == 'FLOAT' else (n.inputs[6], n.inputs[7])
        for sock, v in ((n.inputs["Factor"], fac), (ia, a), (ib, b)):
            if isinstance(v, bpy.types.NodeSocket): s.links.new(v, sock)
            else: sock.default_value = v
        return n.outputs["Result"] if typ == 'FLOAT' else n.outputs[2]
    def ramp(s, fac, stops, interp='LINEAR'):
        n = s.node("ShaderNodeValToRGB"); n.color_ramp.interpolation = interp
        el = n.color_ramp.elements
        while len(el) < len(stops): el.new(0.5)
        for e, (p, c) in zip(el, stops): e.position = p; e.color = c
        s.links.new(fac, n.inputs[0]); return n.outputs[0]
    def attr(s, name, out="Fac"):
        return s.node("ShaderNodeAttribute", attribute_name=name).outputs[out]
    def smooth(s, lo, hi, x):
        n = s.node("ShaderNodeMapRange", interpolation_type='SMOOTHSTEP')
        s.set(n, From_Min=lo, From_Max=hi); s.links.new(x, n.inputs[0]); return n.outputs[0]

def claw_group():
    """node group: local wound coords -> gash / rim masks for 3 parallel claw slashes."""
    g = bpy.data.node_groups.new("ClawMarks", "ShaderNodeTree")
    for nme, typ in (("Vector", "NodeSocketVector"), ("Spacing", "NodeSocketFloat"), ("HalfLen", "NodeSocketFloat"),
                     ("Width", "NodeSocketFloat"), ("Seed", "NodeSocketFloat")):
        g.interface.new_socket(nme, in_out='INPUT', socket_type=typ)
    for nme in ("Gash", "Rim"):
        g.interface.new_socket(nme, in_out='OUTPUT', socket_type="NodeSocketFloat")
    n = NT(g); gi = n.node("NodeGroupInput"); go = n.node("NodeGroupOutput")
    sep = n.node("ShaderNodeSeparateXYZ"); n.links.new(gi.outputs["Vector"], sep.inputs[0])
    u, v, w = sep.outputs
    def sines(x, f1, f2, ph):
        a1 = n.math('SINE', n.math('ADD', n.math('MULTIPLY', x, f1), ph))
        a2 = n.math('SINE', n.math('ADD', n.math('MULTIPLY', x, f2), n.math('MULTIPLY', ph, 2.3)))
        return n.math('ADD', n.math('MULTIPLY', a1, 0.6), n.math('MULTIPLY', a2, 0.4))
    seed = gi.outputs["Seed"]
    un = n.math('DIVIDE', u, gi.outputs["HalfLen"])
    wob = n.math('MULTIPLY', sines(un, 2.1, 5.3, seed), n.math('MULTIPLY', gi.outputs["Spacing"], 0.22))
    v2 = n.math('ADD', v, wob)
    idx = n.math('MINIMUM', n.math('MAXIMUM', n.math('ROUND', n.math('DIVIDE', v2, gi.outputs["Spacing"])), -1.0), 1.0)
    vv = n.math('SUBTRACT', v2, n.math('MULTIPLY', idx, gi.outputs["Spacing"]))
    L = n.math('MULTIPLY', gi.outputs["HalfLen"], n.math('SUBTRACT', 1.0, n.math('MULTIPLY', n.math('ABSOLUTE', idx), 0.16)))
    uoff = n.math('MULTIPLY', n.math('MULTIPLY', idx, gi.outputs["HalfLen"]), 0.13)
    uu = n.math('DIVIDE', n.math('SUBTRACT', u, uoff), L)
    taper = n.math('SQRT', n.math('MAXIMUM', n.math('SUBTRACT', 1.0, n.math('MULTIPLY', uu, uu)), 0.0))
    rag = sines(un, 17.0, 41.0, n.math('ADD', seed, n.math('MULTIPLY', idx, 2.9)))
    wid = n.math('MULTIPLY', n.math('MULTIPLY', gi.outputs["Width"], taper), n.math('ADD', 1.0, n.math('MULTIPLY', rag, 0.35)))
    t = n.math('DIVIDE', n.math('ABSOLUTE', vv), n.math('MAXIMUM', wid, 1e-4))
    depth = n.math('SUBTRACT', 1.0, n.smooth(0.16, 0.26, n.math('ABSOLUTE', w)))
    live = n.math('MULTIPLY', depth, n.math('GREATER_THAN', taper, 0.02))
    gash = n.math('MULTIPLY', n.math('SUBTRACT', 1.0, n.smooth(0.45, 1.0, t)), live)
    rim = n.math('MULTIPLY', n.math('MULTIPLY', n.math('SUBTRACT', 1.0, n.smooth(0.9, 2.4, t)), live), n.math('SUBTRACT', 1.0, gash))
    n.links.new(gash, go.inputs["Gash"]); n.links.new(rim, go.inputs["Rim"])
    return g

def wound_specs(verts, normals):
    """wound frames snapped to the rest surface: (origin, u, v, n, spacing, halflen, width, fresh)."""
    h = lambda p: T.head_to_world(p)[0]
    raw = [  # target point, slash direction, spacing, half length, width, fresh
        (h([-0.27, -0.98, 0.26]), T.head_dir_to_world([0.0, -0.75, -0.62])[0], 0.066, 0.30, 0.019, 1.0),
        (h([0.40, -0.52, 0.50]), T.head_dir_to_world([0.0, -0.45, -0.9])[0], 0.05, 0.24, 0.011, 0.0),
        (h([0.24, -1.10, 0.33]), T.head_dir_to_world([-0.3, -0.8, -0.3])[0], 0.048, 0.19, 0.013, 0.8),
        (h([-0.36, -0.35, 0.30]), T.head_dir_to_world([0.0, -0.3, -0.95])[0], 0.045, 0.17, 0.010, 0.1),
        (np.array([-0.50, -3.72, 3.95]), np.array([0, -0.55, -0.83]), 0.10, 0.45, 0.026, 1.0),
        (np.array([0.50, -3.55, 3.55]), np.array([0, 0.5, -0.86]), 0.09, 0.38, 0.018, 0.15),
        (np.array([-0.88, -1.70, 3.20]), np.array([0, 0.75, -0.66]), 0.13, 0.66, 0.030, 0.9),
        (np.array([0.88, -2.1, 3.30]), np.array([0, 0.6, -0.8]), 0.12, 0.5, 0.022, 0.1),
        (np.array([-1.0, -0.55, 2.75]), np.array([0, -0.5, -0.86]), 0.11, 0.48, 0.026, 0.9),
        (np.array([1.0, -0.45, 2.6]), np.array([0, 0.3, -0.95]), 0.10, 0.38, 0.018, 0.0),
        (np.array([0.45, 1.6, 3.6]), np.array([0, 0.8, -0.6]), 0.09, 0.4, 0.018, 0.0),
    ]
    out = []
    for p, u, sp, hl, wd, fresh in raw:
        i = np.argmin(((verts - p) ** 2).sum(1))
        o = verts[i].astype(float); nn = normals[i].astype(float); nn /= np.linalg.norm(nn)
        u = u - nn * (u @ nn); u /= np.linalg.norm(u)
        out.append((o, u, np.cross(nn, u), nn, sp, hl, wd, fresh))
    return out

def wound_attrs(me, verts, normals, wounds):
    """per-vertex local wound coordinates of the nearest wound, so the shader only
    evaluates one set of claw marks (coords are linear -> interpolation is exact)."""
    N = len(verts)
    wq = np.tile(np.array([99.0, 99.0, 99.0], np.float32), (N, 1)); wp = np.tile(np.array([0.1, 0.3, 0.02], np.float32), (N, 1))
    wf = np.zeros((N, 3), np.float32)
    best = np.full(N, 1e9)
    for k, (o, u, v, nn, sp, hl, wd, fresh) in enumerate(wounds):
        rel = verts.astype(float) - o
        q = np.stack([rel @ u, rel @ v, rel @ nn], 1)
        m = (np.abs(q[:, 0]) < hl * 1.3 + 0.25) & (np.abs(q[:, 1]) < sp + 0.4) & (np.abs(q[:, 2]) < 0.3) & ((normals @ nn) > 0.15)
        score = np.abs(q[:, 2]) + 0.2 * np.hypot(q[:, 0], q[:, 1])
        m &= score < best
        best[m] = score[m]
        wq[m] = q[m]; wp[m] = (sp, hl, wd); wf[m] = (fresh, 3.7 * k + 1.0, 0)
    add_vec_attr(me, "wq", wq); add_vec_attr(me, "wp", wp); add_vec_attr(me, "wf", wf)

def skin_material():
    mat = bpy.data.materials.new("TRexSkin"); mat.use_nodes = True
    n = NT(mat.node_tree); bsdf = n.nodes["Principled BSDF"]
    P = n.attr("rest", "Vector")
    mouth = n.attr("mouth"); tongue = n.attr("tongue"); dorsal = n.attr("dorsal"); stripe = n.attr("stripe")
    ssize = n.attr("ssize"); mottle = n.attr("mottle"); mdepth = n.attr("mdepth")
    # --- scales: one voronoi (edge distance) drives colour + bump
    e1 = n.node("ShaderNodeTexVoronoi", feature='DISTANCE_TO_EDGE'); n.set(e1, Vector=P); n.links.new(ssize, e1.inputs["Scale"])
    crease = n.smooth(0.0, 0.10, e1.outputs["Distance"])            # 0 in the crevices between scales
    mid = n.set(n.node("ShaderNodeTexNoise"), Vector=P, Scale=11.0, Detail=1.0, Roughness=0.6)
    mv = mid.outputs[0]
    # --- colour
    belly = (0.27, 0.20, 0.12, 1); flank = (0.10, 0.075, 0.04, 1); back = (0.026, 0.026, 0.017, 1)
    col = n.ramp(dorsal, [(0.0, belly), (0.45, flank), (1.0, back)])
    col = n.mix(n.math('MULTIPLY', stripe, 0.85), col, (0.012, 0.012, 0.01, 1))
    col = n.mix(n.math('MULTIPLY', mottle, 0.5), col, (0.19, 0.115, 0.055, 1))                       # rusty mottling
    hsv = n.node("ShaderNodeHueSaturation"); n.links.new(col, hsv.inputs["Color"])
    n.links.new(n.math('ADD', 0.62, n.math('MULTIPLY', mv, 0.8)), hsv.inputs["Value"])
    col = hsv.outputs[0]
    col = n.mix(n.math('MULTIPLY', n.math('SUBTRACT', 1.0, crease), 0.8), col, (0.011, 0.009, 0.007, 1))   # dirt in crevices
    # --- mouth interior
    flesh = n.mix(mv, (0.30, 0.045, 0.045, 1), (0.50, 0.14, 0.12, 1))
    mcol = n.mix(n.smooth(0.3, 0.95, mouth), (0.13, 0.022, 0.03, 1), flesh)
    mcol = n.mix(tongue, mcol, n.mix(mv, (0.26, 0.05, 0.055, 1), (0.44, 0.15, 0.14, 1)))
    mcol = n.mix(n.math('MULTIPLY', mdepth, 0.93), mcol, (0.02, 0.003, 0.004, 1))                    # dark gullet
    inm = n.smooth(0.12, 0.5, mouth)
    col = n.mix(inm, col, mcol)
    # --- claw wounds (local coords come from vertex attributes)
    gn = n.node("ShaderNodeGroup", node_tree=claw_group())
    n.links.new(n.attr("wq", "Vector"), gn.inputs["Vector"])
    wp = n.node("ShaderNodeSeparateXYZ"); n.links.new(n.attr("wp", "Vector"), wp.inputs[0])
    wf = n.node("ShaderNodeSeparateXYZ"); n.links.new(n.attr("wf", "Vector"), wf.inputs[0])
    n.links.new(wp.outputs[0], gn.inputs["Spacing"]); n.links.new(wp.outputs[1], gn.inputs["HalfLen"]); n.links.new(wp.outputs[2], gn.inputs["Width"])
    n.links.new(wf.outputs[1], gn.inputs["Seed"])
    skin_only = n.math('SUBTRACT', 1.0, inm)
    gash = n.math('MULTIPLY', gn.outputs["Gash"], skin_only); rim = n.math('MULTIPLY', gn.outputs["Rim"], skin_only)
    fresh = wf.outputs[0]
    rim_col = n.mix(fresh, (0.26, 0.19, 0.16, 1), (0.15, 0.03, 0.022, 1))          # healed scar tissue vs inflamed
    col = n.mix(n.math('MULTIPLY', n.math('POWER', rim, 1.5), 0.8), col, rim_col)
    gash_col = n.mix(fresh, (0.12, 0.07, 0.06, 1), n.mix(mv, (0.11, 0.004, 0.004, 1), (0.02, 0.001, 0.001, 1)))
    col = n.mix(gash, col, gash_col)
    n.links.new(col, bsdf.inputs["Base Color"])
    # --- roughness / wetness
    rough = n.math('ADD', 0.44, n.math('MULTIPLY', mv, 0.22))
    rough = n.math('ADD', rough, n.math('MULTIPLY', n.math('SUBTRACT', 1.0, crease), 0.2))
    wet = n.math('MAXIMUM', inm, n.math('MULTIPLY', gash, fresh))
    rough = n.mix(wet, rough, n.mix(inm, 0.30, 0.14, 'FLOAT'), 'FLOAT')
    n.links.new(rough, bsdf.inputs["Roughness"])
    n.links.new(n.math('MULTIPLY', inm, 0.8), bsdf.inputs["Coat Weight"]); bsdf.inputs["Coat Roughness"].default_value = 0.06
    # --- bump: scales + lumps, then gashes cut in with a raised rim
    h = n.math('MULTIPLY', crease, 0.8)
    h = n.math('ADD', h, n.math('MULTIPLY', mv, 1.6))
    h = n.math('MULTIPLY', h, n.math('ADD', 1.0, n.math('MULTIPLY', inm, 0.6)))
    h = n.math('ADD', h, n.math('MULTIPLY', rim, 2.5))
    h = n.math('SUBTRACT', h, n.math('MULTIPLY', gash, 7.0))
    bump = n.node("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.006
    n.links.new(h, bump.inputs["Height"]); n.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    return mat

def tooth_material():
    mat = bpy.data.materials.new("Teeth"); mat.use_nodes = True
    n = NT(mat.node_tree); bsdf = n.nodes["Principled BSDF"]
    t = n.attr("t"); rnd = n.attr("rnd")
    geo = n.node("ShaderNodeNewGeometry")
    nz = n.set(n.node("ShaderNodeTexNoise"), Vector=geo.outputs["Position"], Scale=60.0, Detail=3.0)
    col = n.ramp(t, [(0.0, (0.16, 0.085, 0.035, 1)), (0.22, (0.50, 0.37, 0.19, 1)), (0.65, (0.74, 0.66, 0.47, 1)), (1.0, (0.62, 0.55, 0.40, 1))])
    col = n.mix(n.math('MULTIPLY', nz.outputs[0], 0.5), col, (0.30, 0.19, 0.08, 1))
    col = n.mix(n.math('MULTIPLY', rnd, 0.35), col, (0.33, 0.24, 0.12, 1))
    n.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.22; bsdf.inputs["Coat Weight"].default_value = 0.5; bsdf.inputs["Coat Roughness"].default_value = 0.08
    bsdf.inputs["Subsurface Weight"].default_value = 0.15; bsdf.inputs["Subsurface Radius"].default_value = (0.01, 0.008, 0.005)
    return mat

def claw_material():
    mat = bpy.data.materials.new("Claws"); mat.use_nodes = True
    n = NT(mat.node_tree); bsdf = n.nodes["Principled BSDF"]
    col = n.ramp(n.attr("t"), [(0.0, (0.02, 0.017, 0.013, 1)), (0.6, (0.045, 0.036, 0.026, 1)), (1.0, (0.17, 0.14, 0.10, 1))])
    n.links.new(col, bsdf.inputs["Base Color"]); bsdf.inputs["Roughness"].default_value = 0.35
    return mat

def eye_material():
    mat = bpy.data.materials.new("Eye"); mat.use_nodes = True
    n = NT(mat.node_tree); bsdf = n.nodes["Principled BSDF"]
    a = n.attr("ang")
    iris = n.ramp(a, [(0.0, (0.42, 0.15, 0.01, 1)), (0.34, (0.50, 0.24, 0.02, 1)), (0.48, (0.14, 0.04, 0.004, 1)), (0.56, (0.012, 0.007, 0.005, 1))])
    col = n.mix(n.smooth(0.34, 0.42, n.attr("pup")), (0, 0, 0, 1), iris)
    n.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.12; bsdf.inputs["Coat Weight"].default_value = 0.6; bsdf.inputs["Coat Roughness"].default_value = 0.03
    return mat

def saliva_material():
    mat = bpy.data.materials.new("Saliva"); mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.9, 0.9, 0.85, 1); b.inputs["Roughness"].default_value = 0.03
    b.inputs["Transmission Weight"].default_value = 0.9; b.inputs["IOR"].default_value = 1.34
    return mat

# --------------------------------------------------------------------- build
def build_trex(coll, npz_path):
    d = np.load(npz_path)
    verts, faces, normals = d["verts"], d["faces"], d["normals"]
    me = mesh_from_arrays("TRexBody", verts, faces)
    add_vec_attr(me, "rest", verts)
    for k in ("mouth", "tongue"):
        add_float_attr(me, k, d[k])
    # large-scale colour pattern
    x, y, z = verts[:, 0].astype(float), verts[:, 1].astype(float), verts[:, 2].astype(float)
    wob = T.wobble(x, y, z, 1.7) + 0.5 * T.wobble(x, y, z, 4.1, 2.0)
    zc, hh = T.body_axis(y)
    rel = np.where((np.abs(x) < 0.95) & (z > 1.9), (z - zc) / np.maximum(hh, 0.25), normals[:, 2] * 0.6)
    dorsal = sstep(-0.95, 0.45, rel * 0.9 + normals[:, 2] * 0.22 + 0.22 * wob)
    head = d["d_head"] < 0.05; jaw = d["d_jaw"] < 0.05
    dorsal = np.where(jaw & ~head, np.minimum(dorsal, 0.35), dorsal)
    band = np.sin(y * 3.4 + 1.8 * T.wobble(x, y, z, 1.1, 5.0) + 0.8 * np.abs(x))
    stripe = sstep(0.2, 0.75, band) * sstep(0.3, 0.65, dorsal) * sstep(-3.9, -3.0, y) + 0.0
    add_float_attr(me, "dorsal", dorsal); add_float_attr(me, "stripe", stripe)
    ob = bpy.data.objects.new("TRexBody", me); coll.objects.link(ob)
    add_float_attr(me, "mottle", sstep(0.15, 0.8, 0.5 + 0.5 * (T.wobble(x, y, z, 2.6, 9.0) + 0.6 * T.wobble(x, y, z, 6.3, 4.0))))
    hd = np.minimum(d["d_head"], d["d_jaw"])
    limb = np.minimum(np.minimum(d["d_meta"], d["d_toes"]), d["d_farm"])
    ss = 44.0 + 30.0 * sstep(0.3, 0.0, hd) - 14.0 * sstep(0.3, 0.9, dorsal) + 12.0 * sstep(0.1, 0.0, limb)
    add_float_attr(me, "ssize", ss)
    yl = T.to_local(np.abs(x), y, z, T.RH, T.JAW_PIVOT, T.HEAD_SCALE)[1]
    add_float_attr(me, "mdepth", sstep(-0.75, 0.05, yl) * d["mouth"])
    wound_attrs(me, verts, normals, wound_specs(verts, normals))
    me.materials.append(skin_material())

    rig = make_armature(coll)
    assign_weights(ob, skin_weights(verts, d)); bind(ob, rig)

    tm, tb = make_teeth(); teeth = bpy.data.objects.new("Teeth", tm); coll.objects.link(teeth)
    tm.materials.append(tooth_material()); rigid_weights(teeth, tb); bind(teeth, rig)
    cm, cb = make_claws(); claws = bpy.data.objects.new("Claws", cm); coll.objects.link(claws)
    cm.materials.append(claw_material()); rigid_weights(claws, cb); bind(claws, rig)
    em = make_eyes(); eyes = bpy.data.objects.new("Eyes", em); coll.objects.link(eyes)
    em.materials.append(eye_material()); rigid_weights(eyes, ["head"] * len(em.vertices)); bind(eyes, rig)
    sm, wj = make_saliva(); sal = bpy.data.objects.new("Saliva", sm); coll.objects.link(sal)
    sm.materials.append(saliva_material())
    sal.vertex_groups.new(name="jaw"); sal.vertex_groups.new(name="head")
    for i, w in enumerate(wj):
        sal.vertex_groups["jaw"].add([i], float(w), 'REPLACE'); sal.vertex_groups["head"].add([i], float(1 - w), 'REPLACE')
    bind(sal, rig)
    for o in (ob, teeth, claws, eyes, sal):          # camera-shake blur only: skipping deformation blur keeps CPU renders fast
        o.cycles.use_deform_motion = False
    return dict(body=ob, rig=rig, teeth=teeth, claws=claws, eyes=eyes, saliva=sal)
