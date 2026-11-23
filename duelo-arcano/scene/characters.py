"""Procedural characters: the evil wizard and the shield-bearing guardian.

Everything is built in character-local space (facing -Y, Z up, feet at origin)
and parented to an armature object that is then placed in the world.
"""
import math
import bpy
import numpy as np
from mathutils import Vector, Matrix, Euler

import timeline as T
from util import (NB, new_material, mat_output, mesh_object, add_mod, get_coll,
                  grid_surface, auto_weights, single_weight, value_node)

# ----------------------------------------------------------------------------
# Skeleton (rest pose, T-pose arms with a slight elbow pre-bend)
# ----------------------------------------------------------------------------
UA, FA = 0.32, 0.30          # upper arm / forearm length
SH_X, SH_Z = 0.19, 1.60


def bone_table():
    b = {
        'root': ((0, 0, 0), (0, 0, 0.25), None),
        'hips': ((0, 0, 0.92), (0, 0, 1.12), 'root'),
        'spine': ((0, 0, 1.12), (0, 0, 1.40), 'hips'),
        'chest': ((0, 0, 1.40), (0, 0, 1.64), 'spine'),
        'neck': ((0, 0, 1.64), (0, -0.015, 1.78), 'chest'),
        'head': ((0, -0.015, 1.78), (0, -0.015, 2.00), 'neck'),
    }
    for s, sx in (('L', 1), ('R', -1)):
        b[f'shoulder.{s}'] = ((0.03 * sx, 0, 1.58), (SH_X * sx, 0, SH_Z), 'chest')
        b[f'upper_arm.{s}'] = ((SH_X * sx, 0, SH_Z), ((SH_X + UA) * sx, 0.035, SH_Z - 0.01), f'shoulder.{s}')
        b[f'forearm.{s}'] = (((SH_X + UA) * sx, 0.035, SH_Z - 0.01), ((SH_X + UA + FA) * sx, 0, SH_Z - 0.02), f'upper_arm.{s}')
        b[f'hand.{s}'] = (((SH_X + UA + FA) * sx, 0, SH_Z - 0.02), ((SH_X + UA + FA + 0.16) * sx, 0, SH_Z - 0.02), f'forearm.{s}')
    return b


WRIST_X = SH_X + UA + FA


def make_armature(name, coll):
    ad = bpy.data.armatures.new(name + '_rig')
    ob = bpy.data.objects.new(name + '_rig', ad)
    coll.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bt = bone_table()
    for bn, (h, t, par) in bt.items():
        eb = ad.edit_bones.new(bn)
        eb.head, eb.tail = Vector(h), Vector(t)
        eb.roll = 0.0
    for bn, (h, t, par) in bt.items():
        if par:
            ad.edit_bones[bn].parent = ad.edit_bones[par]
            ad.edit_bones[bn].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones:
        pb.rotation_mode = 'XYZ'
    ob.show_in_front = True
    return ob


def bones_local(names):
    bt = bone_table()
    return {n: (np.array(bt[n][0]), np.array(bt[n][1])) for n in names}


def parent_to_rig(ob, rig):
    ob.parent = rig
    ob.matrix_parent_inverse = Matrix.Identity(4)
    m = ob.modifiers.new('Armature', 'ARMATURE')
    m.object = rig
    return m


def move_mod_to(ob, modname, index):
    with bpy.context.temp_override(object=ob):
        bpy.ops.object.modifier_move_to_index(modifier=modname, index=index)


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
def cloth_material(name, base, neon, sheen=(0.3, 0.2, 0.4), trim='hem', zig=True,
                   trim_strength=9.0, rim_strength=1.2, rough=0.82):
    m = new_material(name)
    nb = NB(m.node_tree)
    uv = nb.n('ShaderNodeUVMap', uv_map='UVMap')
    sep = nb.n('ShaderNodeSeparateXYZ', {'Vector': uv})
    u, v = (sep, 'X'), (sep, 'Y')
    if trim == 'top':
        v = nb.math('SUBTRACT', 1.0, v)
    # main edge line + thin second line + zig-zag rune band
    edge = nb.maprange(v, 0.010, 0.006)
    line2 = nb.math('MULTIPLY', nb.maprange(v, 0.026, 0.029), nb.maprange(v, 0.034, 0.031))
    tri = nb.math('PINGPONG', nb.math('MULTIPLY', u, 90.0), 1.0)
    zline = nb.math('ADD', 0.048, nb.math('MULTIPLY', tri, 0.016))
    zd = nb.math('ABSOLUTE', nb.math('SUBTRACT', v, zline))
    zz = nb.maprange(zd, 0.0028, 0.0012)
    trim_mask = nb.math('ADD', edge, line2)
    if zig:
        trim_mask = nb.math('ADD', trim_mask, zz)
    trim_val = value_node(nb, trim_strength, 'trim')
    trim_em = nb.math('MULTIPLY', trim_mask, trim_val)
    # neon rim (view dependent outline glow)
    lw = nb.n('ShaderNodeLayerWeight', {'Blend': 0.18})
    rim = nb.math('POWER', (lw, 'Facing'), 7.0)
    rim_val = value_node(nb, rim_strength, 'rim')
    rim_em = nb.math('MULTIPLY', rim, rim_val)
    em = nb.math('ADD', trim_em, rim_em)
    # fabric color variation + weave bump
    tc = nb.n('ShaderNodeTexCoord')
    n1 = nb.n('ShaderNodeTexNoise', {'Vector': (tc, 'Object'), 'Scale': 9.0, 'Detail': 6.0})
    col = nb.mixc((n1, 'Factor'), base, tuple(min(1, c * 1.9) for c in base[:3]) + (1,))
    wave = nb.n('ShaderNodeTexWave', {'Vector': (tc, 'Object'), 'Scale': 3.5, 'Distortion': 6.0,
                                      'Detail': 3.0}, wave_type='BANDS', bands_direction='Z')
    bump = nb.n('ShaderNodeBump', {'Strength': 0.25, 'Distance': 0.01})
    nb.link((wave, 'Factor'), bump.inputs['Height'])
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {
        'Roughness': rough, 'Sheen Weight': 0.35, 'Sheen Roughness': 0.3,
        'Sheen Tint': (*sheen, 1), 'Emission Color': (*neon, 1), 'Specular IOR Level': 0.3})
    nb.link(col, bsdf.inputs['Base Color'])
    nb.link(em, bsdf.inputs['Emission Strength'])
    nb.link(bump, bsdf.inputs['Normal'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    return m


def skin_material(name, base, neon, veins=True):
    m = new_material(name)
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    n = nb.n('ShaderNodeTexNoise', {'Vector': (tc, 'Object'), 'Scale': 40.0, 'Detail': 8.0})
    col = nb.mixc((n, 'Factor'), base, tuple(c * 0.6 for c in base[:3]) + (1,))
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {'Roughness': 0.5, 'Subsurface Weight': 0.15,
                                             'Subsurface Radius': (0.5, 0.2, 0.3),
                                             'Subsurface Scale': 0.01,
                                             'Emission Color': (*neon, 1)})
    nb.link(col, bsdf.inputs['Base Color'])
    if veins:
        vor = nb.n('ShaderNodeTexVoronoi', {'Vector': (tc, 'Object'), 'Scale': 28.0},
                   feature='DISTANCE_TO_EDGE')
        vn = nb.maprange((vor, 'Distance'), 0.03, 0.0)
        glow = value_node(nb, 0.0, 'veins')
        nb.link(nb.math('MULTIPLY', vn, glow), bsdf.inputs['Emission Strength'])
    bump = nb.n('ShaderNodeBump', {'Strength': 0.3, 'Distance': 0.003})
    nb.link((n, 'Factor'), bump.inputs['Height'])
    nb.link(bump, bsdf.inputs['Normal'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    return m


def metal_material(name, base=(0.42, 0.45, 0.5), neon=(0.1, 0.85, 1.0), rim=0.6):
    m = new_material(name)
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    n = nb.n('ShaderNodeTexNoise', {'Vector': (tc, 'Object'), 'Scale': 30.0, 'Detail': 10.0})
    r = nb.maprange((n, 'Factor'), 0.3, 0.7, 0.22, 0.5)
    lw = nb.n('ShaderNodeLayerWeight', {'Blend': 0.2})
    rimv = nb.math('MULTIPLY', nb.math('POWER', (lw, 'Facing'), 4.0), value_node(nb, rim, 'rim'))
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {'Base Color': (*base, 1), 'Metallic': 1.0,
                                             'Emission Color': (*neon, 1)})
    nb.link(r, bsdf.inputs['Roughness'])
    nb.link(rimv, bsdf.inputs['Emission Strength'])
    bump = nb.n('ShaderNodeBump', {'Strength': 0.15, 'Distance': 0.002})
    nb.link((n, 'Factor'), bump.inputs['Height'])
    nb.link(bump, bsdf.inputs['Normal'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    return m


def emit_material(name, color, strength):
    m = new_material(name)
    nb = NB(m.node_tree)
    e = nb.n('ShaderNodeEmission', {'Color': (*color, 1)})
    val = value_node(nb, strength, 'strength')
    nb.link(val, e.inputs['Strength'])
    out = mat_output(nb)
    nb.link(e, out.inputs['Surface'])
    return m


def void_material():
    m = new_material('HoodVoid')
    nb = NB(m.node_tree)
    b = nb.n('ShaderNodeBsdfPrincipled', {'Base Color': (0.004, 0.003, 0.006, 1), 'Roughness': 0.9,
                                          'Specular IOR Level': 0.1})
    out = mat_output(nb)
    nb.link(b, out.inputs['Surface'])
    return m


# ----------------------------------------------------------------------------
# Garment generators (character-local)
# ----------------------------------------------------------------------------
def lathe(profile, nu, shape_fn=None, hem_fn=None, back_trail=0.0):
    """profile: list of (z, rx, ry, yoff). Returns rings (nv, nu, 3).
    hem_fn(angle) -> dz for the first ring (tattering); propagates fading upward."""
    rings = []
    nv = len(profile)
    for j, (z, rx, ry, yo) in enumerate(profile):
        ring = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            # angle 0 = front (-Y)
            x = rx * math.sin(a)
            y = -ry * math.cos(a) + yo
            zz = z
            fade = max(0.0, 1 - j / 5.0)
            if hem_fn is not None:
                zz += hem_fn(a) * fade
            # longer at the back
            back = (1 - math.cos(a)) * 0.5
            zz -= back_trail * back * fade
            if shape_fn:
                x, y, zz = shape_fn(x, y, zz, a, j)
            ring.append((x, y, zz))
        rings.append(ring)
    return np.array(rings)


def interp_profile(keys, n):
    """keys: list of (z, rx, ry, yoff); returns n smoothly interpolated rows by z."""
    keys = np.array(keys, dtype=float)
    zs = np.linspace(keys[0, 0], keys[-1, 0], n)
    out = []
    for z in zs:
        row = [z]
        for c in (1, 2, 3):
            row.append(float(np.interp(z, keys[:, 0], keys[:, c])))
        out.append(row)
    return out


def tatter(seed, amp, n_teeth):
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 4)
    def fn(a):
        saw = abs(((a * n_teeth / (2 * math.pi)) % 1.0) - 0.5) * 2   # 0..1 triangle
        nz = 0.5 * math.sin(a * 3 + ph[0]) + 0.3 * math.sin(a * 7 + ph[1]) + 0.2 * math.sin(a * 13 + ph[2])
        return -amp * (0.55 * saw ** 2 + 0.45 * (nz * 0.5 + 0.5))
    return fn


def build_robe(P, rig, coll, mat):
    keys = P['robe_profile']
    prof = interp_profile(keys, 46)
    rings = lathe(prof, 96, hem_fn=P.get('hem_fn'), back_trail=P.get('back_trail', 0.0))
    v, f, uv = grid_surface(rings)
    ob = mesh_object(P['name'] + '_robe', v, f, collection=coll, uvs=uv)
    ob.data.materials.append(mat)
    return ob


def build_hood(P, coll, mat):
    nu, nv = 64, 34
    rings = []
    s0 = P.get('hood_scale', 1.0)
    for j in range(nv):
        s = j / (nv - 1)
        cy = -0.150 + 0.42 * s ** 0.85
        cz = 1.83 + 0.07 * s + P.get('hood_tip', 0.22) * s ** 3
        hw = (0.150 + 0.07 * math.sin(math.pi * min(1, s * 1.25)) * (1 - s) + 0.02) * (1 - s ** 2.2) + 0.006
        hh = (0.205 + 0.06 * math.sin(math.pi * min(1, s * 1.1))) * (1 - s ** 1.8) + 0.006
        ring = []
        for i in range(nu):
            a = 2 * math.pi * i / nu      # 0 = top
            x = hw * math.sin(a)
            z = cz + hh * math.cos(a)
            y = cy
            if j == 0:
                # brim overhangs at the top, opens at the bottom
                y += -0.035 * max(0, math.cos(a)) + 0.03 * max(0, -math.cos(a))
                z += 0.012 * math.cos(a)
            # lower part drapes onto shoulders
            if math.cos(a) < 0:
                k = (-math.cos(a)) ** 2
                x *= 1 + 0.55 * k * (1 - s)
                z -= 0.08 * k * (1 - s * 0.5)
            ring.append((x * s0, y * s0, (z - 1.8) * s0 + 1.8))
        rings.append(ring)
    v, f, uv = grid_surface(np.array(rings), cap_end=True)
    ob = mesh_object(P['name'] + '_hood', v, f, collection=coll, uvs=uv)
    ob.data.materials.append(mat)
    add_mod(ob, 'SOLIDIFY', thickness=0.012, offset=1.0)
    return ob


def build_mantle(P, coll, mat):
    keys = [(1.28, 0.42, 0.34, 0.02), (1.42, 0.38, 0.29, 0.01), (1.58, 0.30, 0.21, 0.0),
            (1.68, 0.17, 0.13, 0.0), (1.73, 0.10, 0.09, 0.0)]
    prof = interp_profile(keys, 18)
    n_teeth = P.get('mantle_teeth', 14)
    def hem(a):
        saw = abs(((a * n_teeth / (2 * math.pi)) % 1.0) - 0.5) * 2
        return -0.09 * (1 - saw) ** 1.5
    rings = lathe(prof, 112, hem_fn=hem if P.get('mantle_dagged', True) else None)
    rings[:, :, :] *= 1.0
    v, f, uv = grid_surface(rings)
    ob = mesh_object(P['name'] + '_mantle', v, f, collection=coll, uvs=uv)
    ob.data.materials.append(mat)
    add_mod(ob, 'SOLIDIFY', thickness=0.01, offset=1.0)
    return ob


def build_collar(P, coll, mat):
    nu, nv = 60, 14
    rings = []
    span = math.radians(115)
    for j in range(nv):
        t = j / (nv - 1)
        ring = []
        for i in range(nu):
            uu = i / (nu - 1)
            a = -span + 2 * span * uu          # 0 = back (+Y)
            r = 0.16 + 0.15 * t ** 1.6
            spikes = 5
            tip = abs(((uu * spikes) % 1.0) - 0.5) * 2      # 1 at seams
            ztop = 1.62 + 0.36 + 0.10 * (1 - tip) ** 2 * (0.6 + 0.4 * math.cos(a))
            z = 1.60 + (ztop - 1.60) * t
            x = r * math.sin(a)
            y = r * math.cos(a) * 0.95 + 0.02
            # flare outward at the sides near the front
            ring.append((x, y, z))
        rings.append(ring)
    v, f, uv = grid_surface(np.array(rings), closed_u=False)
    ob = mesh_object(P['name'] + '_collar', v, f, collection=coll, uvs=uv)
    ob.data.materials.append(mat)
    add_mod(ob, 'SOLIDIFY', thickness=0.014, offset=0.0)
    return ob


def build_sleeve(P, side, coll, mat):
    sx = 1 if side == 'L' else -1
    nu, nv = 40, 30
    x0, x1 = SH_X - 0.04, WRIST_X + 0.05
    rings = []
    tat = P.get('sleeve_tatter', 0.0)
    rng = np.random.default_rng(7 if side == 'L' else 8)
    ph = rng.uniform(0, 6.28, 3)
    for j in range(nv):
        t = j / (nv - 1)
        r = 0.085 + 0.025 * t + P.get('sleeve_flare', 0.09) * t ** 3
        ring = []
        for i in range(nu):
            a = 2 * math.pi * i / nu          # 0 = down (-Z)
            down = (math.cos(a) * 0.5 + 0.5)
            x = x0 + (x1 - x0) * t
            # bell sleeve: lower side hangs longer at the cuff
            x += (0.07 * down ** 1.5 + tat * (0.5 + 0.5 * math.sin(a * 5 + ph[0])) * down) * t ** 6
            y = r * math.sin(a) * 0.95
            z = -r * math.cos(a) * (1.0 + 0.25 * t ** 2 * down)
            # elbow prebend follows the bone line
            yo = 0.035 * (1 - abs(t - 0.5) * 2) if t > 0 else 0
            ring.append((x * sx, y + yo, z + SH_Z - 0.015 * t - 0.01 * t ** 3))
        rings.append(ring)
    v, f, uv = grid_surface(np.array(rings))
    ob = mesh_object(f"{P['name']}_sleeve.{side}", v, f, collection=coll, uvs=uv)
    ob.data.materials.append(mat)
    add_mod(ob, 'SOLIDIFY', thickness=0.008, offset=1.0)
    return ob


def build_hand(P, side, coll, mat):
    """Skin-modifier hand in rest pose (fingers along +-X, palm down, thumb -Y)."""
    sx = 1 if side == 'L' else -1
    me = bpy.data.meshes.new(f"{P['name']}_hand.{side}")
    w0 = np.array([WRIST_X, 0.0, SH_Z - 0.02])
    verts = [tuple(w0)]
    radii = [(0.030, 0.022)]
    edges = []
    fl = P['finger_len']
    fr = P['finger_r']
    curl = P['curl']
    spread = P.get('spread', 0.12)
    for k, (dy, L) in enumerate(zip((-0.030, -0.010, 0.010, 0.029), fl)):
        base = w0 + np.array([0.085, dy * 1.05, -0.004])
        mid = w0 + np.array([0.042, dy * 0.6, 0.0])
        i_mid = len(verts)
        verts.append(tuple(mid))
        radii.append((0.018, 0.012))
        edges.append((0, i_mid))
        i_base = len(verts)
        verts.append(tuple(base))
        radii.append((fr * 1.25, fr * 1.15))
        edges.append((i_mid, i_base))
        d = np.array([1.0, dy * spread * 18, 0.0])
        d /= np.linalg.norm(d)
        p = base.copy()
        prev = i_base
        ang = 0.0
        for seg, frac in enumerate((0.45, 0.32, 0.23)):
            ang += curl[seg]
            dd = np.array([d[0] * math.cos(ang), d[1] * math.cos(ang), -math.sin(ang)])
            p = p + dd * L * frac
            verts.append(tuple(p))
            rr = fr * (1.0 - 0.22 * (seg + 1)) * (1.15 if seg < 2 else 1.0)
            radii.append((rr, rr * 0.9))
            edges.append((prev, len(verts) - 1))
            prev = len(verts) - 1
    # thumb
    tb = w0 + np.array([0.025, -0.032, -0.01])
    verts.append(tuple(tb))
    radii.append((fr * 1.4, fr * 1.3))
    edges.append((0, len(verts) - 1))
    prev = len(verts) - 1
    p = tb.copy()
    d = np.array([0.55, -0.6, -0.45])
    for seg, (L, bend) in enumerate(((0.04, 0.0), (0.035, 0.35), (0.028, 0.35))):
        dd = d / np.linalg.norm(d)
        p = p + dd * L
        d = d + np.array([0.25, 0.25, -0.1]) * bend
        verts.append(tuple(p))
        radii.append((fr * (1.15 - 0.2 * seg), fr * (1.05 - 0.2 * seg)))
        edges.append((prev, len(verts) - 1))
        prev = len(verts) - 1
    verts = [(v[0] * sx, v[1], v[2]) for v in verts]
    me.from_pydata(verts, edges, [])
    ob = bpy.data.objects.new(me.name, me)
    coll.objects.link(ob)
    sk = ob.modifiers.new('skin', 'SKIN')
    sk.branch_smoothing = 0.5
    sk.use_smooth_shade = True
    for i, r in enumerate(radii):
        ob.data.skin_vertices[0].data[i].radius = r
    ob.data.skin_vertices[0].data[0].use_root = True
    add_mod(ob, 'SUBSURF', levels=1, render_levels=1)
    with bpy.context.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='skin')
        bpy.ops.object.modifier_apply(modifier='subsurf')
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def build_eyes(P, coll, mat):
    obs = []
    for sx in (1, -1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1)
        ob = bpy.context.object
        ob.name = f"{P['name']}_eye{'L' if sx > 0 else 'R'}"
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
        ob.scale = (0.017, 0.006, 0.0075)
        ob.location = (0.042 * sx, -0.118, 1.885)
        ob.rotation_euler = (0, math.radians(-20 * sx), 0)
        ob.data.materials.append(mat)
        obs.append(ob)
    return obs


# ----------------------------------------------------------------------------
# Character assembly
# ----------------------------------------------------------------------------
WIZARD = dict(
    name='Wizard',
    robe_profile=[(0.02, 0.47, 0.42, 0.05), (0.35, 0.36, 0.31, 0.03), (0.75, 0.25, 0.20, 0.01),
                  (0.98, 0.215, 0.165, 0.0), (1.15, 0.19, 0.14, 0.0), (1.40, 0.215, 0.15, 0.0),
                  (1.58, 0.235, 0.15, 0.0), (1.66, 0.16, 0.12, 0.0), (1.72, 0.085, 0.08, 0.0)],
    hem_fn=tatter(4, 0.10, 11), back_trail=0.04,
    finger_len=(0.105, 0.118, 0.108, 0.085), finger_r=0.0085,
    curl=(0.35, 0.45, 0.4), spread=0.18,
    sleeve_flare=0.065, sleeve_tatter=0.04,
    mantle_teeth=13, hood_tip=0.26,
)

GUARDIAN = dict(
    name='Guardian',
    robe_profile=[(0.02, 0.38, 0.34, 0.03), (0.40, 0.30, 0.26, 0.02), (0.80, 0.23, 0.19, 0.01),
                  (0.98, 0.215, 0.165, 0.0), (1.15, 0.20, 0.145, 0.0), (1.40, 0.225, 0.16, 0.0),
                  (1.58, 0.24, 0.16, 0.0), (1.66, 0.16, 0.12, 0.0), (1.72, 0.085, 0.08, 0.0)],
    hem_fn=tatter(9, 0.03, 7), back_trail=0.02,
    finger_len=(0.085, 0.095, 0.088, 0.07), finger_r=0.0115,
    curl=(0.12, 0.15, 0.1), spread=0.10,
    sleeve_flare=0.03, sleeve_tatter=0.0,
    mantle_teeth=8, mantle_dagged=False, hood_tip=0.08, hood_scale=0.98,
)


def flutter_setup(name, coll):
    wind = bpy.data.objects.new(name + '_wind', None)
    coll.objects.link(wind)
    wind.scale = (0.6, 0.6, 0.6)
    tex = bpy.data.textures.new(name + '_flutter', 'CLOUDS')
    tex.noise_scale = 0.45
    tex.noise_depth = 2
    fold = bpy.data.objects.new(name + '_folds', None)
    coll.objects.link(fold)
    fold.scale = (0.12, 0.12, 2.2)
    ftex = bpy.data.textures.new(name + '_foldtex', 'CLOUDS')
    ftex.noise_scale = 0.5
    ftex.noise_depth = 1
    return wind, tex, fold, ftex


def add_cloth_mods(ob, wind, tex, fold, ftex, flutter_group, fold_strength=0.03,
                   flutter=0.03):
    if fold_strength:
        d = add_mod(ob, 'DISPLACE', 'folds', texture=ftex, strength=fold_strength, mid_level=0.5,
                    texture_coords='OBJECT', texture_coords_object=fold, direction='NORMAL')
    d = add_mod(ob, 'DISPLACE', 'flutter', texture=tex, strength=flutter, mid_level=0.5,
                texture_coords='OBJECT', texture_coords_object=wind, direction='NORMAL',
                vertex_group=flutter_group)
    return d


def uv_v_weights(ob, group, fn):
    """vertex group from per-vertex uv v (lathe meshes: v=0 at hem)."""
    me = ob.data
    vg = ob.vertex_groups.new(name=group)
    uvl = me.uv_layers[0].data
    vv = np.zeros(len(me.vertices))
    for loop in me.loops:
        vv[loop.vertex_index] = uvl[loop.index].uv[1]
    for i, val in enumerate(vv):
        vg.add([i], float(fn(val)), 'REPLACE')


def build_character(P, palette, coll):
    rig = make_armature(P['name'], coll)
    wind, tex, fold, ftex = flutter_setup(P['name'], coll)
    wind.parent = rig
    fold.parent = rig
    mats = palette
    parts = {}

    robe = build_robe(P, rig, coll, mats['cloth'])
    uv_v_weights(robe, 'flutter', lambda v: (1 - v) ** 2.2)
    add_cloth_mods(robe, wind, tex, fold, ftex, 'flutter', 0.035, 0.05)
    auto_weights(robe, bones_local(['hips', 'spine', 'chest']), power=3)
    parent_to_rig(robe, rig)
    add_mod(robe, 'SOLIDIFY', thickness=0.012, offset=1.0)
    add_mod(robe, 'SUBSURF', levels=1, render_levels=2)
    parts['robe'] = robe

    mantle = build_mantle(P, coll, mats['cloth2'])
    uv_v_weights(mantle, 'flutter', lambda v: (1 - v) ** 2)
    mods_before = len(mantle.modifiers)
    add_cloth_mods(mantle, wind, tex, fold, ftex, 'flutter', 0.0, 0.025)
    auto_weights(mantle, bones_local(['chest', 'shoulder.L', 'shoulder.R', 'neck']), power=3)
    parent_to_rig(mantle, rig)
    move_mod_to(mantle, 'Armature', len(mantle.modifiers) - 1)
    move_mod_to(mantle, 'solidify', len(mantle.modifiers) - 1)
    add_mod(mantle, 'SUBSURF', levels=1, render_levels=2)
    parts['mantle'] = mantle

    hood = build_hood(P, coll, mats['hood'])
    auto_weights(hood, bones_local(['head', 'neck']), power=3,
                 override=lambda co, W, names: np.stack([
                     np.where(co[:, 2] > 1.74, 1.0, 0.25), np.where(co[:, 2] > 1.74, 0.05, 1.0)], 1))
    parent_to_rig(hood, rig)
    move_mod_to(hood, 'Armature', 0)
    add_mod(hood, 'SUBSURF', levels=1, render_levels=2)
    parts['hood'] = hood

    # dark void head inside the hood
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1)
    void = bpy.context.object
    void.name = P['name'] + '_void'
    for c in void.users_collection:
        c.objects.unlink(void)
    coll.objects.link(void)
    void.scale = (0.105, 0.115, 0.135)
    void.location = (0, -0.015, 1.86)
    void.data.materials.append(mats['void'])
    bpy.context.view_layer.update()
    mw = void.matrix_world.copy()
    void.parent = rig
    void.parent_type = 'BONE'
    void.parent_bone = 'head'
    void.matrix_world = mw
    parts['void'] = void

    if P['name'] == 'Wizard':
        collar = build_collar(P, coll, mats['collar'])
        auto_weights(collar, bones_local(['chest', 'neck']), power=3)
        parent_to_rig(collar, rig)
        move_mod_to(collar, 'Armature', 0)
        add_mod(collar, 'SUBSURF', levels=1, render_levels=2)
        parts['collar'] = collar

    for side in ('L', 'R'):
        sl = build_sleeve(P, side, coll, mats['cloth2'])
        uv_v_weights(sl, 'flutter', lambda v: v ** 3)
        add_cloth_mods(sl, wind, tex, fold, ftex, 'flutter', 0.0, 0.02)
        auto_weights(sl, bones_local(['chest', f'shoulder.{side}', f'upper_arm.{side}', f'forearm.{side}']),
                     power=4)
        parent_to_rig(sl, rig)
        move_mod_to(sl, 'Armature', len(sl.modifiers) - 1)
        add_mod(sl, 'SUBSURF', levels=1, render_levels=2)
        parts[f'sleeve.{side}'] = sl

        h = build_hand(P, side, coll, mats['skin'])
        single_weight(h, f'hand.{side}')
        parent_to_rig(h, rig)
        parts[f'hand.{side}'] = h

    eyes = build_eyes(P, coll, mats['eyes'])
    bpy.context.view_layer.update()
    for e in eyes:
        mw = e.matrix_world.copy()
        e.parent = rig
        e.parent_type = 'BONE'
        e.parent_bone = 'head'
        e.matrix_world = mw
    parts['eyes'] = eyes

    for ob in parts.values():
        if isinstance(ob, list):
            continue
        for p in ob.data.polygons:
            p.use_smooth = True
    return rig, parts, wind


# ----------------------------------------------------------------------------
# Rig controls: IK + hand orientation + head tracking
# ----------------------------------------------------------------------------
def setup_controls(rig, coll):
    ctr = {}
    name = rig.name.replace('_rig', '')
    for side in ('L', 'R'):
        tgt = bpy.data.objects.new(f'{name}_hand_tgt.{side}', None)
        tgt.empty_display_size = 0.08
        coll.objects.link(tgt)
        tgt.rotation_mode = 'QUATERNION'
        pole = bpy.data.objects.new(f'{name}_pole.{side}', None)
        coll.objects.link(pole)
        pole.parent = rig
        sx = 1 if side == 'L' else -1
        pole.location = (0.55 * sx, 0.65, 1.05)
        pb = rig.pose.bones[f'forearm.{side}']
        ik = pb.constraints.new('IK')
        ik.target = tgt
        ik.pole_target = pole
        ik.pole_angle = math.radians(-90 if side == 'L' else -90)
        ik.chain_count = 2
        ik.use_stretch = False
        hb = rig.pose.bones[f'hand.{side}']
        cr = hb.constraints.new('COPY_ROTATION')
        cr.target = tgt
        ctr[f'tgt.{side}'] = tgt
        ctr[f'pole.{side}'] = pole
    look = bpy.data.objects.new(f'{name}_look', None)
    coll.objects.link(look)
    head = rig.pose.bones['head']
    dt = head.constraints.new('DAMPED_TRACK')
    dt.target = look
    # bone Z axis points forward (-Y) for an upright bone with roll 0
    zf = (rig.data.bones['head'].matrix_local.to_3x3() @ Vector((0, 0, 1))).y
    dt.track_axis = 'TRACK_Z' if zf < 0 else 'TRACK_NEGATIVE_Z'
    dt.influence = 0.85
    ctr['look'] = look
    return ctr


def hand_rest_frame(side):
    """Rest hand directions in character-local space: fingers, palm normal, thumb."""
    sx = 1 if side == 'L' else -1
    return Vector((sx, 0, 0)), Vector((0, 0, -1)), Vector((0, -1, 0))


def hand_target_rotation(rig, side, f_world, n_world):
    """World rotation for the hand target so the hand's fingers point along f and
    the palm faces n."""
    A = rig.matrix_world.to_3x3().normalized()
    Ai = A.inverted()
    f = (Ai @ Vector(f_world)).normalized()
    n = Ai @ Vector(n_world)
    n = (n - f * n.dot(f)).normalized()
    d0, n0, t0 = hand_rest_frame(side)
    t = n.cross(f) if side == 'L' else f.cross(n)
    M1 = Matrix((f, n, t)).transposed()
    M0 = Matrix((d0, n0, t0)).transposed()
    R = M1 @ M0.transposed()
    B = rig.data.bones[f'hand.{side}'].matrix_local.to_3x3()
    return (A @ R @ B).to_quaternion()


def key_hand(rig, ctr, side, frame, pos_world, f_world, n_world):
    tgt = ctr[f'tgt.{side}']
    tgt.location = Vector(pos_world)
    q = hand_target_rotation(rig, side, f_world, n_world)
    if tgt.rotation_quaternion.dot(q) < 0:
        q.negate()
    tgt.rotation_quaternion = q
    tgt.keyframe_insert('location', frame=frame)
    tgt.keyframe_insert('rotation_quaternion', frame=frame)


def key_bone_rot(rig, bone, frame, euler):
    pb = rig.pose.bones[bone]
    pb.rotation_euler = Euler(euler)
    pb.keyframe_insert('rotation_euler', frame=frame)
