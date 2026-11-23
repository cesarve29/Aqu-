"""Build-time FX: void orb, rune circle, hex shield, levitating rocks, magic lights,
shockwaves and the geometry-node wrappers used by the per-frame runtime FX."""
import math
import bpy
import numpy as np
from mathutils import Vector, Euler, Matrix

import timeline as T
from timeline import E, ramp, smooth, clamp
from util import NB, new_material, mat_output, mesh_object, add_mod, get_coll, value_node

MAGENTA = (1.0, 0.10, 0.72)
VIOLET = (0.55, 0.12, 1.0)
CYAN = (0.0, 0.62, 1.0)
WHITE_HOT_M = (1.0, 0.75, 0.95)
WHITE_HOT_C = (0.75, 0.97, 1.0)


def _keyval(mat, node, f, v):
    s = mat.node_tree.nodes[node].outputs[0]
    s.default_value = v
    s.keyframe_insert('default_value', frame=f)


def _no_shadow(ob):
    ob.visible_shadow = False
    try:
        ob.visible_volume_scatter = False
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
def additive_emission(name, color, strength=5.0, attr_color=False, attr_emit=False, fresnel=None,
                      opaque=False):
    """Emission + transparent (additive look). Optional per-point attributes."""
    m = new_material(name)
    nb = NB(m.node_tree)
    col = (*color, 1)
    em = nb.n('ShaderNodeEmission', {'Color': col})
    stv = value_node(nb, strength, 'strength')
    st = stv
    if attr_emit:
        a = nb.n('ShaderNodeAttribute', attribute_name='emit', attribute_type='GEOMETRY')
        st = nb.math('MULTIPLY', (a, 'Fac' if 'Fac' in a.outputs else 'Factor'), stv)
    if attr_color:
        a = nb.n('ShaderNodeAttribute', attribute_name='col', attribute_type='GEOMETRY')
        nb.link((a, 'Color'), em.inputs['Color'])
    if fresnel is not None:
        lw = nb.n('ShaderNodeLayerWeight', {'Blend': fresnel})
        st = nb.math('MULTIPLY', st, nb.math('POWER', (lw, 'Facing'), 2.0))
    nb.link(st, em.inputs['Strength'])
    if opaque:
        out = mat_output(nb)
        nb.link(em, out.inputs['Surface'])
        return m
    tr = nb.n('ShaderNodeBsdfTransparent')
    add = nb.n('ShaderNodeAddShader')
    nb.link(em, add.inputs[0])
    nb.link(tr, add.inputs[1])
    out = mat_output(nb)
    nb.link(add, out.inputs['Surface'])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    return m


def orb_shell_material():
    m = new_material('OrbShell')
    nb = NB(m.node_tree)
    lw = nb.n('ShaderNodeLayerWeight', {'Blend': 0.5})
    facing = (lw, 'Facing')
    rim = nb.math('POWER', facing, 5.0)
    rim_sharp = nb.math('POWER', facing, 12.0)
    col = nb.mixc(rim_sharp, MAGENTA + (1,), WHITE_HOT_M + (1,))
    st = value_node(nb, 14.0, 'strength')
    em = nb.n('ShaderNodeEmission')
    nb.link(col, em.inputs['Color'])
    nb.link(nb.math('MULTIPLY', rim, st), em.inputs['Strength'])
    tr = nb.n('ShaderNodeBsdfTransparent')
    add = nb.n('ShaderNodeAddShader')
    nb.link(em, add.inputs[0])
    nb.link(tr, add.inputs[1])
    out = mat_output(nb)
    nb.link(add, out.inputs['Surface'])
    return m


def orb_core_material():
    m = new_material('OrbCore')
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    t = nb.n('ShaderNodeValue')
    t.name = 't'
    fc = t.outputs[0].driver_add('default_value')
    fc.driver.expression = 'frame/24'
    vor = nb.n('ShaderNodeTexVoronoi', {'Vector': (tc, 'Object'), 'Scale': 3.2, 'Randomness': 1.0},
               feature='DISTANCE_TO_EDGE', voronoi_dimensions='4D')
    nb.link(nb.math('MULTIPLY', t, 0.9), (vor, 'W'))
    veins = nb.maprange((vor, 'Distance'), 0.06, 0.0)
    noise = nb.n('ShaderNodeTexNoise', {'Vector': (tc, 'Object'), 'Scale': 2.0, 'Detail': 4.0},
                 noise_dimensions='4D')
    nb.link(nb.math('MULTIPLY', t, 0.5), (noise, 'W'))
    vm = nb.math('MULTIPLY', veins, nb.maprange((noise, 'Factor'), 0.45, 0.65))
    st = value_node(nb, 3.0, 'strength')
    lw = nb.n('ShaderNodeLayerWeight', {'Blend': 0.35})
    rim = nb.math('POWER', (lw, 'Facing'), 2.5)
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {'Base Color': (0.0, 0.0, 0.0, 1), 'Roughness': 0.15,
                                             'Specular IOR Level': 0.8, 'Coat Weight': 1.0,
                                             'Emission Color': (*VIOLET, 1)})
    nb.link(nb.math('MULTIPLY', nb.math('ADD', vm, nb.math('MULTIPLY', rim, 0.6)), st),
            bsdf.inputs['Emission Strength'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    return m


def orb_plasma_material():
    m = new_material('OrbPlasma')
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    t = nb.n('ShaderNodeValue')
    fc = t.outputs[0].driver_add('default_value')
    fc.driver.expression = 'frame/24'
    vor = nb.n('ShaderNodeTexVoronoi', {'Vector': (tc, 'Object'), 'Scale': 2.4, 'Randomness': 1.0},
               feature='DISTANCE_TO_EDGE', voronoi_dimensions='4D')
    nb.link(nb.math('MULTIPLY', t, 2.2), (vor, 'W'))
    fil = nb.maprange((vor, 'Distance'), 0.035, 0.0)
    noise = nb.n('ShaderNodeTexNoise', {'Vector': (tc, 'Object'), 'Scale': 1.5, 'Detail': 2.0},
                 noise_dimensions='4D')
    nb.link(nb.math('MULTIPLY', t, 1.3), (noise, 'W'))
    msk = nb.maprange((noise, 'Factor'), 0.48, 0.6)
    st = value_node(nb, 7.0, 'strength')
    em = nb.n('ShaderNodeEmission', {'Color': (*MAGENTA, 1)})
    nb.link(nb.math('MULTIPLY', nb.math('MULTIPLY', fil, msk), st), em.inputs['Strength'])
    tr = nb.n('ShaderNodeBsdfTransparent')
    add = nb.n('ShaderNodeAddShader')
    nb.link(em, add.inputs[0])
    nb.link(tr, add.inputs[1])
    out = mat_output(nb)
    nb.link(add, out.inputs['Surface'])
    return m


# ----------------------------------------------------------------------------
def uv_sphere(name, r, coll, seg=48, rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r)
    ob = bpy.context.object
    ob.name = name
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def build_orb(coll):
    root = bpy.data.objects.new('Orb', None)
    coll.objects.link(root)
    core = uv_sphere('OrbCore', 0.70, coll)
    core.data.materials.append(orb_core_material())
    shell = uv_sphere('OrbShell', 1.0, coll)
    shell.data.materials.append(orb_shell_material())
    plasma = uv_sphere('OrbPlasma', 1.12, coll)
    plasma.data.materials.append(orb_plasma_material())
    for ob in (core, shell, plasma):
        ob.parent = root
        _no_shadow(ob)
    core.visible_shadow = True
    # orbit rings
    rings = []
    rmat = additive_emission('OrbRing', MAGENTA, 14.0)
    for i, (rx, ry) in enumerate(((65, 10), (-50, 40), (15, -70))):
        bpy.ops.mesh.primitive_torus_add(major_radius=1.6 + 0.22 * i, minor_radius=0.006,
                                         major_segments=96, minor_segments=8)
        ob = bpy.context.object
        ob.name = f'OrbRing{i}'
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
        ob.data.materials.append(rmat)
        ob.parent = root
        ob.rotation_euler = (math.radians(rx), math.radians(ry), 0)
        _no_shadow(ob)
        rings.append(ob)
    # light
    ld = bpy.data.lights.new('OrbLight', 'POINT')
    ld.color = (1.0, 0.25, 0.80)
    ld.shadow_soft_size = 0.15
    lo = bpy.data.objects.new('OrbLight', ld)
    coll.objects.link(lo)
    lo.parent = root

    # keyframes: position every frame, scale, visibility, ring spin, brightness
    for f in range(1, T.F_END + 1):
        p = T.orb_pos(f)
        r = T.orb_radius(f)
        vis = T.orb_visible(f) and r > 1e-3
        root.location = Vector(p)
        root.scale = (max(r, 1e-4),) * 3
        root.keyframe_insert('location', frame=f)
        root.keyframe_insert('scale', frame=f)
        root.rotation_euler = (f * 0.011, f * 0.017, f * 0.023)
        root.keyframe_insert('rotation_euler', frame=f)
    for ob in (core, shell, plasma, *rings, root):
        for f, v in ((E['orb_birth'] - 1, True), (E['orb_birth'], False), (E['burst'], True)):
            ob.hide_render = v
            ob.keyframe_insert('hide_render', frame=f)
    for i, ob in enumerate(rings):
        for f in range(1, T.F_END + 1, 4):
            ob.rotation_euler[2] = f * (0.09 + 0.04 * i) * (1 if i % 2 else -1)
            ob.keyframe_insert('rotation_euler', index=2, frame=f)
        # rings appear once the orb is charged enough
        m = ob.data.materials[0]
    for f in range(1, T.F_END + 1, 2):
        c = T.charge(f)
        r = T.orb_radius(f)
        fl = 1 + 0.12 * math.sin(f * 1.9) + 0.08 * math.sin(f * 3.7)
        energy = 0.0
        if T.orb_visible(f):
            if f < E['release']:
                energy = (40 + 1100 * c ** 1.6) * fl
            elif f < E['impact']:
                energy = 1300 * fl
            else:
                energy = (1500 + 900 * ramp(f, E['impact'], E['burst'])) * fl
        ld.energy = energy
        ld.keyframe_insert('energy', frame=f)
        ring_on = ramp(f, 520, 640) if f < E['release'] else 1.0
        _keyval(rmat, 'strength', f, 7.0 * ring_on * fl)
        for ob in rings:
            ob.scale = (ring_on,) * 3
            ob.keyframe_insert('scale', frame=f)
    return root


# ----------------------------------------------------------------------------
def build_rune_circle(coll):
    """Flat ribbons on the ground; uv.x = drawing order (0..1), uv.y = across."""
    verts, faces, uvs = [], [], []

    def ribbon(points, width, t0, t1):
        pts = np.asarray(points, dtype=float)
        n = len(pts)
        base = len(verts)
        for i in range(n):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, n - 1)]
            d = b - a
            d /= np.linalg.norm(d) + 1e-9
            nrm = np.array([-d[1], d[0]])
            t = t0 + (t1 - t0) * i / (n - 1)
            for s in (-1, 1):
                p = pts[i] + nrm * width * 0.5 * s
                verts.append((p[0], p[1], 0.0))
                uvs.append((t, 0.5 + 0.5 * s))
        for i in range(n - 1):
            a = base + 2 * i
            faces.append((a, a + 1, a + 3, a + 2))

    def circle(r, t0, t1, n=200, a0=0.0):
        return [(r * math.cos(a0 + 2 * math.pi * i / (n - 1)), r * math.sin(a0 + 2 * math.pi * i / (n - 1)))
                for i in range(n)]

    ribbon(circle(2.35, 0, 0), 0.035, 0.00, 0.22)
    ribbon(circle(2.22, 0, 0, a0=math.pi), 0.014, 0.05, 0.25)
    ribbon(circle(1.55, 0, 0, a0=0.5), 0.022, 0.20, 0.38)
    ribbon(circle(0.55, 0, 0), 0.018, 0.70, 0.80)
    # heptagram {7/3}
    k = 7
    star = [(1.55 * math.cos(math.pi / 2 + 2 * math.pi * (i * 3 % k) / k),
             1.55 * math.sin(math.pi / 2 + 2 * math.pi * (i * 3 % k) / k)) for i in range(k + 1)]
    for i in range(k):
        a, b = np.array(star[i]), np.array(star[i + 1])
        seg = [a + (b - a) * s for s in np.linspace(0, 1, 12)]
        ribbon(seg, 0.020, 0.38 + 0.3 * i / k, 0.38 + 0.3 * (i + 1) / k)
    # glyphs between the outer rings (small angular strokes)
    rng = np.random.default_rng(21)
    n_g = 30
    for g in range(n_g):
        a = 2 * math.pi * g / n_g
        t0 = 0.80 + 0.18 * g / n_g
        c = np.array([1.88 * math.cos(a), 1.88 * math.sin(a)])
        tang = np.array([-math.sin(a), math.cos(a)])
        rad = np.array([math.cos(a), math.sin(a)])
        strokes = rng.integers(2, 4)
        for sidx in range(strokes):
            p0 = c + tang * rng.uniform(-0.09, 0.09) + rad * rng.uniform(-0.12, 0.12)
            dirv = (tang * rng.uniform(-1, 1) + rad * rng.uniform(-1, 1))
            dirv /= np.linalg.norm(dirv) + 1e-9
            L = rng.uniform(0.08, 0.17)
            ribbon([p0, p0 + dirv * L * 0.5, p0 + dirv * L], 0.012, t0, t0 + 0.006)
    me_verts = np.array(verts)
    ob = mesh_object('RuneCircle', me_verts, faces, collection=coll, uvs=np.array(uvs), smooth=False)
    ob.location = (T.WIZ[0], T.WIZ[1], 0.012)

    m = new_material('Runes')
    nb = NB(m.node_tree)
    uv = nb.n('ShaderNodeUVMap', uv_map='UVMap')
    sep = nb.n('ShaderNodeSeparateXYZ', {'Vector': uv})
    reveal = value_node(nb, 0.0, 'reveal')
    diff = nb.math('SUBTRACT', reveal, (sep, 'X'))
    shown = nb.maprange(diff, 0.0, 0.004)
    head = nb.maprange(diff, 0.05, 0.0)                        # bright drawing head
    across = nb.math('SUBTRACT', 1.0, nb.math('ABSOLUTE', nb.math('SUBTRACT', nb.math('MULTIPLY', (sep, 'Y'), 2), 1)))
    core = nb.math('POWER', across, 0.6)
    st = value_node(nb, 10.0, 'strength')
    amt = nb.math('MULTIPLY', nb.math('MULTIPLY', shown, nb.math('ADD', 1.0, nb.math('MULTIPLY', head, 4.0))),
                  nb.math('MULTIPLY', core, st))
    col = nb.mixc(head, (*MAGENTA, 1), (*WHITE_HOT_M, 1))
    em = nb.n('ShaderNodeEmission')
    nb.link(col, em.inputs['Color'])
    nb.link(amt, em.inputs['Strength'])
    tr = nb.n('ShaderNodeBsdfTransparent')
    mix = nb.n('ShaderNodeMixShader')
    nb.link(nb.math('MINIMUM', 1.0, nb.math('MULTIPLY', shown, core)), mix.inputs[0])
    nb.link(tr, mix.inputs[1])
    nb.link(em, mix.inputs[2])
    out = mat_output(nb)
    nb.link(mix, out.inputs['Surface'])
    ob.data.materials.append(m)
    _no_shadow(ob)
    ob.visible_diffuse = True

    # glow pool on the ground
    bpy.ops.mesh.primitive_circle_add(vertices=64, radius=3.4, fill_type='TRIFAN')
    pool = bpy.context.object
    pool.name = 'RunePool'
    for c in pool.users_collection:
        c.objects.unlink(pool)
    coll.objects.link(pool)
    pool.location = (T.WIZ[0], T.WIZ[1], 0.008)
    pm = new_material('RunePool')
    nb = NB(pm.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    ln = nb.n('ShaderNodeVectorMath', operation='LENGTH')
    nb.link((tc, 'Object'), ln.inputs[0])
    fall = nb.math('POWER', nb.maprange((ln, 'Value'), 3.4, 0.0), 2.2)
    pst = value_node(nb, 0.0, 'strength')
    em = nb.n('ShaderNodeEmission', {'Color': (*MAGENTA, 1)})
    nb.link(nb.math('MULTIPLY', fall, pst), em.inputs['Strength'])
    tr = nb.n('ShaderNodeBsdfTransparent')
    add = nb.n('ShaderNodeAddShader')
    nb.link(em, add.inputs[0])
    nb.link(tr, add.inputs[1])
    out = mat_output(nb)
    nb.link(add, out.inputs['Surface'])
    pool.data.materials.append(pm)
    _no_shadow(pool)

    # underlight
    ld = bpy.data.lights.new('RuneLight', 'POINT')
    ld.color = (1.0, 0.2, 0.75)
    ld.shadow_soft_size = 1.2
    lo = bpy.data.objects.new('RuneLight', ld)
    coll.objects.link(lo)
    lo.location = (T.WIZ[0], T.WIZ[1] - 0.6, 0.25)

    for f in range(1, T.F_END + 1, 2):
        rv = ramp(f, E['runes_start'], E['runes_end'], smooth) * 1.02
        c = T.charge(f)
        fade = 1 - ramp(f, E['release'] + 20, E['release'] + 160)
        pulse = 1 + 0.15 * math.sin(f * 0.35)
        on = ramp(f, E['runes_start'], E['runes_start'] + 20)
        _keyval(m, 'reveal', f, rv)
        _keyval(m, 'strength', f, (6 + 22 * c) * pulse * (0.25 + 0.75 * fade))
        _keyval(pm, 'strength', f, (0.25 + 1.4 * c) * on * pulse * (0.15 + 0.85 * fade))
        ld.energy = (25 * on + 380 * c ** 1.3) * pulse * (0.2 + 0.8 * fade)
        ld.keyframe_insert('energy', frame=f)
        ob.rotation_euler[2] = f * 0.0025
        ob.keyframe_insert('rotation_euler', index=2, frame=f)
    return ob


# ----------------------------------------------------------------------------
def build_shield(coll):
    """Hex-cell spherical cap facing +Y. Per-vertex attributes in UV maps:
    UVMap: (cell_r normalized, edge 0 center..1 border); UVRand: (rand, unused)."""
    R_cap = 0.95
    R_sph = 2.1
    hex_r = 0.058
    gap = 0.008
    verts, faces, uv1, uv2 = [], [], [], []
    rng = np.random.default_rng(5)
    dx = math.sqrt(3) * hex_r
    for j in range(-20, 21):
        for i in range(-20, 21):
            cx = dx * (i + 0.5 * (j % 2))
            cz = 1.5 * hex_r * j
            rr = math.hypot(cx, cz)
            if rr > R_cap - hex_r * 0.5:
                continue
            rnd = rng.random()
            base = len(verts)

            def proj(x, z):
                # map onto sphere cap bulging toward +Y (toward the wizard)
                d = math.sqrt(max(R_sph ** 2 - x * x - z * z, 0.0))
                return (x, d - R_sph, z)
            verts.append(proj(cx, cz))
            uv1.append((rr / R_cap, 0.0))
            uv2.append((rnd, 0.0))
            for k in range(6):
                a = math.pi / 6 + k * math.pi / 3
                hx = cx + (hex_r - gap) * math.cos(a)
                hz = cz + (hex_r - gap) * math.sin(a)
                verts.append(proj(hx, hz))
                uv1.append((rr / R_cap, 1.0))
                uv2.append((rnd, 0.0))
            for k in range(6):
                faces.append((base, base + 1 + k, base + 1 + (k + 1) % 6))
    ob = mesh_object('ShieldHex', np.array(verts), faces, collection=coll, uvs=np.array(uv1), smooth=False)
    me = ob.data
    l2 = me.uv_layers.new(name='UVRand')
    lvi = np.zeros(len(me.loops), dtype=np.int32)
    me.loops.foreach_get('vertex_index', lvi)
    l2.data.foreach_set('uv', np.asarray(uv2, dtype=np.float32)[lvi].ravel())

    m = new_material('ShieldHex')
    nb = NB(m.node_tree)
    u1 = nb.n('ShaderNodeUVMap', uv_map='UVMap')
    s1 = nb.n('ShaderNodeSeparateXYZ', {'Vector': u1})
    u2 = nb.n('ShaderNodeUVMap', uv_map='UVRand')
    s2 = nb.n('ShaderNodeSeparateXYZ', {'Vector': u2})
    cr, edge, rnd = (s1, 'X'), (s1, 'Y'), (s2, 'X')
    form = value_node(nb, 0.0, 'form')            # 0..1 grows outward
    rip_t = value_node(nb, -10.0, 'ripple')       # ripple front radius (normalized)
    hit = value_node(nb, 0.0, 'hit')              # global flash
    flick = value_node(nb, 0.0, 'flicker')        # struggle instability 0..1
    st = value_node(nb, 4.0, 'strength')
    tt = nb.n('ShaderNodeValue')
    fc = tt.outputs[0].driver_add('default_value')
    fc.driver.expression = 'frame'
    # cell visibility: grows from the center with a little randomness
    thresh = nb.math('SUBTRACT', nb.math('MULTIPLY', form, 1.35), nb.math('MULTIPLY', rnd, 0.25))
    vis = nb.maprange(nb.math('SUBTRACT', thresh, cr), 0.0, 0.06)
    newcell = nb.maprange(nb.math('SUBTRACT', thresh, cr), 0.06, 0.0)   # just-born cells flare
    border = nb.math('POWER', edge, 6.0)
    fill = 0.035
    base_e = nb.math('ADD', fill, nb.math('MULTIPLY', border, 1.2))
    # ripple ring
    dr = nb.math('SUBTRACT', cr, rip_t)
    ripple = nb.math('EXPONENT', nb.math('MULTIPLY', nb.math('MULTIPLY', dr, dr), -90.0))
    # flicker: per-cell random strobe changing every 2 frames
    stepf = nb.math('FLOOR', nb.math('MULTIPLY', tt, 0.5))
    h = nb.math('FRACT', nb.math('MULTIPLY', nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', rnd, 91.7),
                                                                       nb.math('MULTIPLY', stepf, 13.13))), 43758.5))
    flk = nb.math('MULTIPLY', nb.maprange(h, 0.55, 1.0), flick)
    dim = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', nb.maprange(h, 0.0, 0.25), nb.math('MULTIPLY', flick, 0.8)))
    total = nb.math('ADD', base_e, nb.math('MULTIPLY', ripple, 2.2))
    total = nb.math('ADD', total, nb.math('MULTIPLY', flk, 2.5))
    total = nb.math('ADD', total, nb.math('MULTIPLY', newcell, 3.0))
    total = nb.math('MULTIPLY', total, nb.math('ADD', 1.0, nb.math('MULTIPLY', hit, 1.6)))
    total = nb.math('MULTIPLY', nb.math('MULTIPLY', total, dim), nb.math('MULTIPLY', vis, st))
    whit = nb.math('MINIMUM', 1.0, nb.math('ADD', nb.math('MULTIPLY', ripple, 0.8), nb.math('MULTIPLY', hit, 0.7)))
    col = nb.mixc(whit, (*CYAN, 1), (*WHITE_HOT_C, 1))
    em = nb.n('ShaderNodeEmission')
    nb.link(col, em.inputs['Color'])
    nb.link(total, em.inputs['Strength'])
    tr = nb.n('ShaderNodeBsdfTransparent')
    add = nb.n('ShaderNodeAddShader')
    nb.link(em, add.inputs[0])
    nb.link(tr, add.inputs[1])
    out = mat_output(nb)
    nb.link(add, out.inputs['Surface'])
    ob.data.materials.append(m)
    _no_shadow(ob)

    # smooth fresnel bubble behind the cells
    rings = []
    nu, nv = 64, 16
    for jv in range(nv):
        rr = R_cap * 1.02 * jv / (nv - 1)
        ring = []
        for iu in range(nu):
            a = 2 * math.pi * iu / nu
            x, z = rr * math.cos(a), rr * math.sin(a)
            d = math.sqrt(max(R_sph ** 2 - x * x - z * z, 0))
            ring.append((x, d - R_sph - 0.015, z))
        rings.append(ring)
    from util import grid_surface
    v, f_, uv = grid_surface(np.array(rings))
    bub = mesh_object('ShieldBubble', v, f_, collection=coll, uvs=uv)
    bm = new_material('ShieldBubble')
    nb = NB(bm.node_tree)
    u = nb.n('ShaderNodeUVMap', uv_map='UVMap')
    s = nb.n('ShaderNodeSeparateXYZ', {'Vector': u})
    edge_fade = nb.maprange((s, 'Y'), 1.0, 0.85)
    lw = nb.n('ShaderNodeLayerWeight', {'Blend': 0.35})
    fr = nb.math('POWER', (lw, 'Facing'), 2.0)
    bst = value_node(nb, 0.0, 'strength')
    em = nb.n('ShaderNodeEmission', {'Color': (*CYAN, 1)})
    nb.link(nb.math('MULTIPLY', nb.math('MULTIPLY', nb.math('ADD', 0.15, fr), edge_fade), bst),
            em.inputs['Strength'])
    tr = nb.n('ShaderNodeBsdfTransparent')
    add = nb.n('ShaderNodeAddShader')
    nb.link(em, add.inputs[0])
    nb.link(tr, add.inputs[1])
    out = mat_output(nb)
    nb.link(add, out.inputs['Surface'])
    bub.data.materials.append(bm)
    _no_shadow(bub)

    root = bpy.data.objects.new('ShieldRoot', None)
    coll.objects.link(root)
    ob.parent = root
    bub.parent = root
    ld = bpy.data.lights.new('ShieldLight', 'POINT')
    ld.color = (0.25, 0.85, 1.0)
    ld.shadow_soft_size = 0.8
    lo = bpy.data.objects.new('ShieldLight', ld)
    coll.objects.link(lo)
    lo.parent = root
    lo.location = (0, 0.35, 0)
    # impact light (white-magenta flash)
    ldi = bpy.data.lights.new('ImpactLight', 'POINT')
    ldi.color = (1.0, 0.6, 0.95)
    ldi.shadow_soft_size = 0.3
    li = bpy.data.objects.new('ImpactLight', ldi)
    coll.objects.link(li)

    for fr_ in range(1, T.F_END + 1):
        c = T.shield_center(fr_)
        root.location = Vector(c)
        root.keyframe_insert('location', frame=fr_)
        li.location = Vector(T.IMPACT_POS + np.array([0, 0.4 - T.shield_push(fr_), 0.1]))
        li.keyframe_insert('location', frame=fr_)
    for fr_ in range(1, T.F_END + 1):
        sf = T.shield_form(fr_)
        imp = T.flash_curve(fr_, E['impact'], 1, 14)
        bur = T.flash_curve(fr_, E['burst'], 1, 12)
        struggle = 1.0 if E['impact'] <= fr_ < E['burst'] else 0.0
        hitv = imp + bur * 1.2 + struggle * 0.25 * (1 + math.sin(fr_ * 1.3))
        # repeating ripples while the orb pushes
        if fr_ >= E['impact']:
            since = (fr_ - E['impact']) % 26 if fr_ < E['burst'] else fr_ - E['burst']
            rip = since / 22.0
        else:
            rip = -10
        flick = struggle * (0.35 + 0.65 * ramp(fr_, E['impact'] + 40, E['push_back_end'] + 10))
        flick *= 1 - ramp(fr_, E['push_fwd_start'] + 30, E['burst'])
        dis = ramp(fr_, E['shield_fade_start'], E['shield_fade_end'])
        flick = max(flick, 0.6 * dis)
        _keyval(m, 'form', fr_, sf if fr_ < E['shield_fade_start'] else 1.0 - dis)
        _keyval(m, 'ripple', fr_, rip)
        _keyval(m, 'hit', fr_, hitv)
        _keyval(m, 'flicker', fr_, flick)
        _keyval(m, 'strength', fr_, 2.4 * min(1.0, sf * 1.5 + 0.0) * (1 - 0.6 * dis))
        _keyval(bm, 'strength', fr_, (0.35 * sf + 1.2 * imp + 1.0 * bur) * (1 - dis))
        ld.energy = (120 * sf + 1500 * imp + 1300 * bur + struggle * 180 * (1 + math.sin(fr_ * 1.7))) * (1 - dis)
        ld.keyframe_insert('energy', frame=fr_)
        ldi.energy = 4000 * imp + 3500 * bur
        ldi.keyframe_insert('energy', frame=fr_)
    for o in (ob, bub):
        for fr_, v in ((1, True), (E['shield_start'] - 1, True), (E['shield_start'], False),
                       (E['shield_fade_end'] + 2, True)):
            o.hide_render = v
            o.keyframe_insert('hide_render', frame=fr_)
    return root


# ----------------------------------------------------------------------------
LEV_ROCKS = 16


def lev_rock_state(i, f, rng_vals):
    """Position + rotation of levitating rock i at frame f."""
    a0, r0, h0, spd, ph, sz = rng_vals
    ground = np.array([T.WIZ[0] + r0 * math.cos(a0), T.WIZ[1] + r0 * math.sin(a0), sz * 0.3])
    rise = ramp(f, E['rocks_rise_start'] + i * 5, E['rocks_rise_end'] + i * 4, smooth)
    a = a0 + spd * max(0, f - E['rocks_rise_start']) * 0.004 * rise
    rr = r0 * (1 - 0.15 * rise)
    hover = np.array([T.WIZ[0] + rr * math.cos(a), T.WIZ[1] + rr * math.sin(a),
                      sz * 0.3 + rise * (h0 + 0.08 * math.sin(f * 0.07 + ph))])
    rot = np.array([f * 0.013 * spd, f * 0.009 * spd + ph, 0.0]) * rise
    if f < E['rocks_fall']:
        return hover, rot
    # fall with gravity from the hover position at release, one bounce
    p0, r_0 = lev_rock_state(i, E['rocks_fall'] - 1, rng_vals)
    t = (f - E['rocks_fall']) / T.FPS
    g = 9.81
    z0 = p0[2] - sz * 0.3
    tf = math.sqrt(2 * z0 / g) if z0 > 0 else 0
    if t < tf:
        z = z0 - 0.5 * g * t * t
    else:
        tb = t - tf
        v = 0.25 * g * tf
        z = max(0.0, v * tb - 0.5 * g * tb * tb)
    p = p0.copy()
    p[2] = sz * 0.3 + z
    out = np.array([math.cos(a0), math.sin(a0), 0]) * min(t, tf + 0.3) * 0.6
    rot = r_0 + np.array([2.0, 1.3, 0.0]) * min(t, tf + 0.4)
    return p + out, rot


def build_levitating_rocks(coll, stone_mat):
    from environment import rock_mesh
    rng = np.random.default_rng(42)
    obs = []
    for i in range(LEV_ROCKS):
        a0 = math.radians(rng.uniform(25, 245))     # behind / beside him, off the camera lane
        # keep them out of the space directly in front of the wizard (the camera lane)
        r0 = rng.uniform(1.0, 2.6)
        h0 = rng.uniform(0.5, 2.4)
        spd = rng.uniform(0.6, 1.6) * (1 if rng.random() > 0.5 else -1)
        ph = rng.uniform(0, 6.28)
        sz = rng.uniform(0.06, 0.22)
        vals = (a0, r0, h0, spd, ph, sz)
        ob = rock_mesh(f'LevRock_{i}', (sz * 1.3, sz, sz * 0.8), 900 + i, coll, subdiv=1,
                       rough=1.6, nu=28, nv=18, taper=0.0)
        ob.data.materials.append(stone_mat)
        for f in range(1, T.F_END + 1):
            p, rot = lev_rock_state(i, f, vals)
            ob.location = Vector(p)
            ob.rotation_euler = Euler(rot)
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('rotation_euler', frame=f)
        obs.append(ob)
    return obs


# ----------------------------------------------------------------------------
def build_shockwaves(coll):
    """Expanding emissive rings: launch (vertical), impact (vertical), burst, ground ring."""
    specs = [
        ('SW_launch', E['release'], T.LAUNCH_POS, (math.radians(90), 0, 0), 2.8, 14, MAGENTA),
        ('SW_launch2', E['release'] + 1, T.LAUNCH_POS, (math.radians(90), 0, 0), 1.6, 10, WHITE_HOT_M),
        ('SW_ground', E['burst'] + 1, np.array([T.IMPACT_POS[0], T.IMPACT_POS[1] + 0.2, 0.05]), (0, 0, 0), 7.0, 26, (0.6, 0.5, 1.0)),
        ('SW_wizground', E['release'], np.array([T.WIZ[0], T.WIZ[1] - 0.3, 0.05]), (0, 0, 0), 5.0, 22, MAGENTA),
    ]
    for name, f0, pos, rot, rmax, dur, col in specs:
        bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.035, major_segments=128,
                                         minor_segments=8)
        ob = bpy.context.object
        ob.name = name
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
        mat = additive_emission(name + '_m', col, 0.0)
        ob.data.materials.append(mat)
        ob.location = Vector(pos)
        ob.rotation_euler = rot
        _no_shadow(ob)
        for f in range(f0 - 1, f0 + dur + 2):
            k = clamp((f - f0) / dur)
            s = 0.05 + rmax * (1 - (1 - k) ** 3)
            ob.scale = (s, s, max(0.3, 1.5 * (1 - k)))
            ob.keyframe_insert('scale', frame=f)
            _keyval(mat, 'strength', f, (0 if f < f0 else 10 * (1 - k) ** 2))
        for f, v in ((1, True), (f0 - 1, True), (f0, False), (f0 + dur + 1, True)):
            ob.hide_render = v
            ob.keyframe_insert('hide_render', frame=f)


def build_blast_spheres(coll):
    specs = [('Blast_impact', E['impact'], T.IMPACT_POS + np.array([0, 0.2, 0]), 1.4, 12, WHITE_HOT_C, 6.0),
             ('Blast_burst', E['burst'], T.IMPACT_POS + np.array([0, 0.25, 0]), 2.6, 16, MAGENTA, 8.0),
             ('Blast_launch', E['release'], T.LAUNCH_POS, 0.9, 8, MAGENTA, 5.0)]
    for name, f0, pos, rmax, dur, col, peak in specs:
        ob = uv_sphere(name, 1.0, coll, seg=48, rings=24)
        mat = additive_emission(name + '_m', col, 0.0, fresnel=0.25)
        ob.data.materials.append(mat)
        ob.location = Vector(pos)
        _no_shadow(ob)
        for f in range(f0 - 1, f0 + dur + 2):
            k = clamp((f - f0) / dur)
            s = 0.05 + rmax * (1 - (1 - k) ** 2.5)
            ob.scale = (s, s, s)
            ob.keyframe_insert('scale', frame=f)
            _keyval(mat, 'strength', f, 0 if f < f0 else peak * (1 - k) ** 2)
        for f, v in ((1, True), (f0 - 1, True), (f0, False), (f0 + dur + 1, True)):
            ob.hide_render = v
            ob.keyframe_insert('hide_render', frame=f)


# ----------------------------------------------------------------------------
# Geometry-node wrappers for runtime FX
# ----------------------------------------------------------------------------
def gn_group(kind, mat):
    name = f'FX_{kind}_{mat.name}'
    g = bpy.data.node_groups.get(name)
    if g:
        return g
    g = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nb = NB(g)
    gi = nb.n('NodeGroupInput')
    na = nb.n('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    na.inputs['Name'].default_value = 'radius'
    if kind == 'points':
        conv = nb.n('GeometryNodeMeshToPoints')
        nb.link((gi, 0), conv.inputs['Mesh'])
        nb.link((na, 'Attribute'), conv.inputs['Radius'])
        geo = conv
    else:
        conv = nb.n('GeometryNodeMeshToCurve')
        nb.link((gi, 0), conv.inputs['Mesh'])
        sr = nb.n('GeometryNodeSetCurveRadius')
        nb.link(conv, sr.inputs['Curve'])
        nb.link((na, 'Attribute'), sr.inputs['Radius'])
        geo = sr
    sm = nb.n('GeometryNodeSetMaterial')
    nb.link(geo, sm.inputs['Geometry'])
    sm.inputs['Material'].default_value = mat
    go = nb.n('NodeGroupOutput')
    nb.link(sm, go.inputs[0])
    return g


def fx_object(name, kind, mat, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0)], [], [])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    mod = ob.modifiers.new('fx', 'NODES')
    mod.node_group = gn_group(kind, mat)
    _no_shadow(ob)
    ob['fx_kind'] = kind
    return ob


def build_runtime_fx_objects(coll):
    """Empty containers filled every frame by fx_runtime.py."""
    pm = additive_emission('FXPoint', MAGENTA, 6.0, attr_color=True, attr_emit=True, opaque=True)
    cm = additive_emission('FXCurve', MAGENTA, 8.0, attr_color=True, attr_emit=True, opaque=True)
    # dark debris (non emissive)
    dm = new_material('FXDebris')
    nb = NB(dm.node_tree)
    a = nb.n('ShaderNodeAttribute', attribute_name='emit', attribute_type='GEOMETRY')
    b = nb.n('ShaderNodeBsdfPrincipled', {'Base Color': (0.04, 0.04, 0.045, 1), 'Roughness': 0.85,
                                          'Emission Color': (1.0, 0.35, 0.6, 1)})
    nb.link((a, 'Fac' if 'Fac' in a.outputs else 'Factor'), b.inputs['Emission Strength'])
    o = mat_output(nb)
    nb.link(b, o.inputs['Surface'])
    names = {
        'FX_gather': ('points', pm), 'FX_orbsparks': ('points', pm), 'FX_embers': ('points', pm),
        'FX_arcs': ('curves', cm), 'FX_trail': ('curves', cm), 'FX_sparks': ('curves', cm),
        'FX_fragments': ('curves', cm), 'FX_motes': ('points', pm), 'FX_debris': ('points', dm),
        'FX_hexbits': ('points', pm), 'FX_flame': ('points', pm),
    }
    obs = {}
    for n, (kind, mat) in names.items():
        obs[n] = fx_object(n, kind, mat, coll)
    obs['FX_debris'].visible_shadow = True
    return obs


def build_fragment_lights(coll):
    import fx_runtime
    for i, sp in enumerate(fx_runtime.FRAG):
        ld = bpy.data.lights.new(f'FragLight{i}', 'POINT')
        ld.color = (1.0, 0.3, 0.8)
        ld.shadow_soft_size = 0.2
        lo = bpy.data.objects.new(f'FragLight{i}', ld)
        coll.objects.link(lo)
        lo.location = Vector(sp['end']) + Vector((0, 0, 0.3))
        fh = int(sp['t0'] + sp['dur'])
        for f in range(fh - 2, fh + 30):
            ld.energy = 1800 * T.flash_curve(f, fh, 1, 6)
            ld.keyframe_insert('energy', frame=f)
        ld.energy = 0
        ld.keyframe_insert('energy', frame=1)


def build_fx(stone_mat):
    coll = get_coll('FX')
    build_fragment_lights(coll)
    build_orb(coll)
    build_rune_circle(coll)
    build_shield(coll)
    build_levitating_rocks(coll, stone_mat)
    build_shockwaves(coll)
    build_blast_spheres(coll)
    build_runtime_fx_objects(coll)
    return coll
