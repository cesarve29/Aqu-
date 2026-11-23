"""World, terrain, standing stones, distant mountains."""
import math
import random
import bpy
import numpy as np
from mathutils import Vector, Euler

import timeline as T
from util import NB, new_material, mat_output, mesh_object, add_mod, get_coll, key, value_node

MOON_DIR = Vector((-0.42, 1.0, 0.36)).normalized()


# ----------------------------------------------------------------------------
def build_world():
    w = bpy.data.worlds.get('Night') or bpy.data.worlds.new('Night')
    bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nb = NB(w.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    d = (tc, 'Generated')  # world: view direction
    # elevation
    sep = nb.n('ShaderNodeSeparateXYZ', {'Vector': d})
    elev = nb.maprange((sep, 'Z'), -0.05, 0.6)
    horizon = (0.020, 0.028, 0.048, 1)
    zenith = (0.0025, 0.0035, 0.009, 1)
    grad = nb.mixc(elev, horizon, zenith)

    # clouds (animated drift through W)
    drift = nb.n('ShaderNodeValue')
    drift.name = 'cloud_drift'
    fc = drift.outputs[0].driver_add('default_value')
    fc.driver.expression = 'frame*0.0016'
    vscale = nb.n('ShaderNodeVectorMath', operation='MULTIPLY')
    nb.link(d, vscale.inputs[0])
    vscale.inputs[1].default_value = (2.2, 2.2, 5.0)
    off = nb.n('ShaderNodeVectorMath', operation='ADD')
    nb.link(vscale, off.inputs[0])
    comb = nb.n('ShaderNodeCombineXYZ')
    nb.link(drift, comb.inputs[0])
    nb.link(comb, off.inputs[1])
    noise = nb.n('ShaderNodeTexNoise', {'Vector': off, 'Scale': 1.6, 'Detail': 9.0,
                                        'Roughness': 0.62, 'Distortion': 0.35},
                 noise_dimensions='4D')
    nb.link(drift, (noise, 'W'))
    cloud = nb.maprange((noise, 'Factor'), 0.48, 0.80)
    cloud_mask = nb.math('MULTIPLY', cloud, nb.maprange((sep, 'Z'), -0.02, 0.12))

    # moon
    md = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.link(d, md.inputs[0])
    md.inputs[1].default_value = tuple(MOON_DIR)
    disc = nb.maprange((md, 'Value'), math.cos(math.radians(1.55)), math.cos(math.radians(1.35)))
    halo = nb.math('POWER', nb.maprange((md, 'Value'), 0.0, 1.0), 180.0)
    halo2 = nb.math('POWER', nb.maprange((md, 'Value'), 0.0, 1.0), 12.0)
    moon_l = nb.math('ADD', nb.math('MULTIPLY', disc, 40.0),
                     nb.math('ADD', nb.math('MULTIPLY', halo, 1.4), nb.math('MULTIPLY', halo2, 0.06)))
    occl = nb.math('SUBTRACT', 1.0, nb.math('MULTIPLY', cloud_mask, 0.85))
    moon_v = nb.math('MULTIPLY', moon_l, occl)

    # cloud lighting: brighter near moon (silver lining) + lightning flashes
    lit = nb.math('ADD', 0.012, nb.math('MULTIPLY', halo2, 0.35))
    flash = value_node(nb, 0.0, 'lightning')
    flash_pos = nb.n('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    nb.link(d, flash_pos.inputs[0])
    flash_pos.inputs[1].default_value = tuple(Vector((0.6, 0.8, 0.25)).normalized())
    flash_local = nb.math('POWER', nb.maprange((flash_pos, 'Value'), 0.2, 1.0), 3.0)
    flash_amt = nb.math('MULTIPLY', flash, nb.math('ADD', 0.25, flash_local))
    cloud_bright = nb.math('ADD', lit, nb.math('MULTIPLY', flash_amt, 1.6))
    cc = nb.n('ShaderNodeCombineColor')
    nb.link(cloud_bright, cc.inputs[0])
    nb.link(cloud_bright, cc.inputs[1])
    nb.link(cloud_bright, cc.inputs[2])
    tint = nb.mixc(1.0, cc, (0.75, 0.85, 1.25, 1), blend='MULTIPLY')
    sky = nb.mixc(cloud_mask, grad, tint)
    moon_col = nb.mixc(1.0, (0.85, 0.92, 1.0, 1), (1, 1, 1, 1))
    moon_rgb = nb.n('ShaderNodeVectorMath', operation='SCALE')
    nb.link(moon_col, moon_rgb.inputs[0])
    nb.link(moon_v, moon_rgb.inputs['Scale'])
    final = nb.n('ShaderNodeVectorMath', operation='ADD')
    nb.link(sky, final.inputs[0])
    nb.link(moon_rgb, final.inputs[1])
    bg = nb.n('ShaderNodeBackground', {'Strength': 1.0})
    nb.link(final, bg.inputs['Color'])
    # lighting contribution kept low (we light with lamps) but camera sees full sky
    lp = nb.n('ShaderNodeLightPath')
    bg_l = nb.n('ShaderNodeBackground', {'Color': (0.010, 0.014, 0.026, 1), 'Strength': 1.0})
    mix = nb.n('ShaderNodeMixShader')
    nb.link((lp, 'Is Camera Ray'), mix.inputs[0])
    nb.link(bg_l, mix.inputs[1])
    nb.link(bg, mix.inputs[2])
    out = nb.n('ShaderNodeOutputWorld')
    nb.link(mix, out.inputs['Surface'])
    # flash also brightens ambient
    fl2 = nb.math('ADD', 1.0, nb.math('MULTIPLY', flash, 5.0))
    nb.link(fl2, bg_l.inputs['Strength'])

    # keyframe lightning flashes (double flicker)
    sock = flash.outputs[0]
    for f0 in (T.E['lightning1'], T.E['lightning2'], T.E['lightning3']):
        for df, v in ((-3, 0), (0, 1.0), (2, 0.15), (4, 0.8), (7, 0.05), (14, 0.0)):
            sock.default_value = v
            sock.keyframe_insert('default_value', frame=f0 + df)
    sock.default_value = 0
    return w


# ----------------------------------------------------------------------------
def ground_material():
    m = new_material('Ground')
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    obj = (tc, 'Object')
    sep = nb.n('ShaderNodeSeparateXYZ', {'Vector': obj})
    rx = nb.math('MULTIPLY', (sep, 'X'), (sep, 'X'))
    ry = nb.math('MULTIPLY', (sep, 'Y'), (sep, 'Y'))
    rad = nb.math('SQRT', nb.math('ADD', rx, ry))
    # flagstone region mask (circle r<9.3)
    plaza = nb.maprange(rad, 9.6, 8.9)
    # flagstones: voronoi distance to edge
    vor = nb.n('ShaderNodeTexVoronoi', {'Vector': obj, 'Scale': 1.25, 'Randomness': 0.85},
               feature='DISTANCE_TO_EDGE', voronoi_dimensions='2D')
    grout = nb.maprange((vor, 'Distance'), 0.015, 0.05)          # 0 in cracks
    vorc = nb.n('ShaderNodeTexVoronoi', {'Vector': obj, 'Scale': 1.25, 'Randomness': 0.85},
                feature='F1', voronoi_dimensions='2D')
    stone_var = nb.maprange((vorc, 'Color'), 0, 1, 0.65, 1.15)
    n1 = nb.n('ShaderNodeTexNoise', {'Vector': obj, 'Scale': 3.0, 'Detail': 12.0, 'Roughness': 0.6})
    n2 = nb.n('ShaderNodeTexNoise', {'Vector': obj, 'Scale': 0.25, 'Detail': 6.0, 'Roughness': 0.5})
    dirt = nb.mixc((n1, 'Factor'), (0.030, 0.028, 0.026, 1), (0.060, 0.058, 0.055, 1))
    stone = nb.mixc((n1, 'Factor'), (0.050, 0.052, 0.058, 1), (0.090, 0.092, 0.100, 1))
    sv = nb.n('ShaderNodeCombineColor', {'Red': stone_var, 'Green': stone_var, 'Blue': stone_var})
    stone2 = nb.mixc(1.0, stone, sv, blend='MULTIPLY')
    stone3 = nb.mixc(grout, (0.012, 0.012, 0.013, 1), stone2)
    base = nb.mixc(plaza, dirt, stone3)
    # wet puddles: low roughness where large noise is high
    wet = nb.maprange((n2, 'Factor'), 0.60, 0.66)
    rough = nb.maprange(wet, 0, 1, 0.78, 0.22)
    rough2 = nb.mixf(grout, 0.95, rough)  # cracks stay rough
    darken = nb.mixc(wet, base, nb.mixc(1.0, base, (0.55, 0.55, 0.6, 1), blend='MULTIPLY'))
    # bump
    bump_h = nb.math('ADD', nb.math('MULTIPLY', (n1, 'Factor'), 0.6),
                     nb.math('MULTIPLY', nb.math('MULTIPLY', grout, plaza), 0.6))
    bump = nb.n('ShaderNodeBump', {'Strength': 0.35, 'Distance': 0.03})
    nb.link(bump_h, bump.inputs['Height'])
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {'Specular IOR Level': 0.5})
    nb.link(darken, bsdf.inputs['Base Color'])
    nb.link(rough2, bsdf.inputs['Roughness'])
    nb.link(bump, bsdf.inputs['Normal'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    return m


def build_ground(coll):
    n = 260
    size = 140.0
    xs = np.linspace(-size / 2, size / 2, n)
    X, Y = np.meshgrid(xs, xs)
    r = np.sqrt(X ** 2 + Y ** 2)
    rng = np.random.default_rng(3)
    # terrain: flat plaza, rolling outside, rises far away (cliff edges)
    Z = np.zeros_like(X)
    for k, (fx, amp) in enumerate(((0.05, 1.4), (0.11, 0.6), (0.23, 0.25), (0.5, 0.08))):
        ph = rng.uniform(0, 6.28, 4)
        Z += amp * (np.sin(X * fx + ph[0]) * np.cos(Y * fx * 1.3 + ph[1]) +
                    0.5 * np.sin((X + Y) * fx * 0.7 + ph[2]))
    plaza = np.clip((r - 9.5) / 8.0, 0, 1) ** 1.5
    Z = Z * plaza + (-0.02)
    Z += np.clip((r - 30) / 40, 0, 1) ** 2 * 6.0       # gentle rise far away
    verts = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
    faces = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            faces.append((a, a + 1, a + n + 1, a + n))
    ob = mesh_object('Ground', verts, faces, collection=coll)
    ob.data.materials.append(ground_material())
    return ob


# ----------------------------------------------------------------------------
def stone_material():
    m = new_material('Monolith')
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    obj = (tc, 'Object')
    n1 = nb.n('ShaderNodeTexNoise', {'Vector': obj, 'Scale': 2.5, 'Detail': 14.0, 'Roughness': 0.65})
    n2 = nb.n('ShaderNodeTexNoise', {'Vector': obj, 'Scale': 0.7, 'Detail': 4.0})
    col = nb.mixc((n1, 'Factor'), (0.045, 0.047, 0.052, 1), (0.11, 0.112, 0.12, 1))
    lichen = nb.maprange((n2, 'Factor'), 0.55, 0.65)
    col2 = nb.mixc(nb.math('MULTIPLY', lichen, 0.6), col, (0.07, 0.08, 0.055, 1))
    # glowing cracks (react to the wizard's charge)
    vor = nb.n('ShaderNodeTexVoronoi', {'Vector': obj, 'Scale': 1.3, 'Randomness': 1.0},
               feature='DISTANCE_TO_EDGE')
    crack = nb.maprange((vor, 'Distance'), 0.012, 0.0)
    crack_mask = nb.maprange((n2, 'Factor'), 0.45, 0.55)
    crack2 = nb.math('MULTIPLY', crack, crack_mask)
    glow = value_node(nb, 0.0, 'crack_glow')
    em = nb.math('MULTIPLY', crack2, glow)
    bump_h = nb.math('ADD', (n1, 'Factor'), nb.math('MULTIPLY', crack, -0.5))
    bump = nb.n('ShaderNodeBump', {'Strength': 0.6, 'Distance': 0.05})
    nb.link(bump_h, bump.inputs['Height'])
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {'Roughness': 0.78, 'Emission Color': (1.0, 0.12, 0.75, 1)})
    nb.link(col2, bsdf.inputs['Base Color'])
    nb.link(bump, bsdf.inputs['Normal'])
    nb.link(em, bsdf.inputs['Emission Strength'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    # glow follows the charge (keyed every 6 frames)
    s = glow.outputs[0]
    for f in range(1, T.F_END + 1, 6):
        s.default_value = 6.0 * T.charge(f) ** 2
        s.keyframe_insert('default_value', frame=f)
    return m


def rock_mesh(name, dims, seed, coll, subdiv=1, rough=0.35, taper=0.18, nu=56, nv=40):
    """Rounded, tapered, noisy superellipsoid rock (origin at its center)."""
    from mathutils import noise as mn
    rng = np.random.default_rng(seed)
    off = Vector(rng.uniform(-100, 100, 3))
    sx, sy, sz = dims
    rings = []
    for j in range(nv + 1):
        th = math.pi * j / nv              # 0 top .. pi bottom
        ct, st = math.cos(th), math.sin(th)
        ring = []
        for i in range(nu):
            ph = 2 * math.pi * i / nu
            cp, sp = math.cos(ph), math.sin(ph)
            e = 0.28
            x = math.copysign(abs(st) ** e, st) * math.copysign(abs(cp) ** e, cp)
            y = math.copysign(abs(st) ** e, st) * math.copysign(abs(sp) ** e, sp)
            z = math.copysign(abs(ct) ** e, ct)
            p = Vector((x * sx / 2, y * sy / 2, z * sz / 2))
            tz = (p.z / sz + 0.5)
            k = 1 - taper * tz
            p.x *= k
            p.y *= k
            n = Vector((x / sx, y / sy, z / sz)).normalized()
            q = p * (1.0 / max(min(sx, sy), 0.3)) * 1.4 + off
            d = mn.fractal(q, 0.6, 2.1, 6) * 0.5
            d += 0.6 * (mn.voronoi(q * 0.8)[0][0] - 0.4)
            p += n * d * rough * min(sx, sy) * 0.35
            ring.append(tuple(p))
        rings.append(ring)
    rings = np.array(rings)
    verts, faces = [], []
    verts.append(tuple(rings[0].mean(axis=0)))
    for j in range(1, nv):
        verts.extend(map(tuple, rings[j]))
    verts.append(tuple(rings[nv].mean(axis=0)))
    top, bot = 0, len(verts) - 1
    def vid(j, i):
        return 1 + (j - 1) * nu + (i % nu)
    for i in range(nu):
        faces.append((top, vid(1, i + 1), vid(1, i)))
        faces.append((bot, vid(nv - 1, i), vid(nv - 1, i + 1)))
    for j in range(1, nv - 1):
        for i in range(nu):
            faces.append((vid(j, i), vid(j, i + 1), vid(j + 1, i + 1), vid(j + 1, i)))
    ob = mesh_object(name, verts, faces, collection=coll)
    for p in ob.data.polygons:
        p.use_smooth = True
    if subdiv:
        add_mod(ob, 'SUBSURF', levels=0, render_levels=subdiv)
    return ob


def build_stones(coll):
    mat = stone_material()
    rng = np.random.default_rng(11)
    stones = []
    R = 11.8
    # angles in degrees (0 = +X). Keep the camera entry corridor (~-100 deg) clear.
    ring = [-62, -28, 8, 38, 64, 116, 142, 172, 205, 232]
    for i, a in enumerate(ring):
        ar = math.radians(a + rng.uniform(-4, 4))
        h = rng.uniform(3.0, 4.6)
        w = rng.uniform(0.9, 1.3)
        dpt = rng.uniform(0.5, 0.75)
        ob = rock_mesh(f'Monolith_{i}', (w, dpt, h), 100 + i, coll, rough=1.0)
        ob.location = (R * math.cos(ar), R * math.sin(ar), h / 2 - 0.25)
        ob.rotation_euler = (rng.uniform(-0.06, 0.06), rng.uniform(-0.08, 0.08), ar + math.pi / 2)
        ob.data.materials.append(mat)
        stones.append(ob)
    # one fallen, broken monolith
    ob = rock_mesh('Monolith_fallen', (0.9, 0.6, 3.4), 77, coll, rough=1.0)
    ob.location = (8.6, -7.2, 0.25)
    ob.rotation_euler = (math.radians(84), 0.2, math.radians(30))
    ob.data.materials.append(mat)
    # trilithon behind the wizard (frames him)
    for sx in (-1.55, 1.55):
        ob = rock_mesh(f'Trilithon_post_{sx}', (1.05, 0.8, 4.6), 200 + int(sx * 10), coll, rough=0.8, taper=0.1)
        ob.location = (sx, 12.4, 2.05)
        ob.rotation_euler = (0, 0, rng.uniform(-0.05, 0.05))
        ob.data.materials.append(mat)
    ob = rock_mesh('Trilithon_lintel', (4.6, 0.9, 0.85), 250, coll, rough=0.8, taper=0.0)
    ob.location = (0.1, 12.4, 4.72)
    ob.rotation_euler = (0, math.radians(2.5), 0)
    ob.data.materials.append(mat)
    # rubble
    for i in range(46):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(5.5, 24)
        if abs(math.atan2(math.sin(a), math.cos(a)) - math.radians(-95)) < 0.25 and r < 16:
            continue
        x, y = r * math.cos(a), r * math.sin(a)
        if abs(x) < 2.2 and -9 < y < 9:      # keep the duel line clear
            continue
        s = rng.uniform(0.15, 0.55) * (1.6 if r > 13 else 1.0)
        ob = rock_mesh(f'Rubble_{i}', (s * rng.uniform(0.8, 1.6), s * rng.uniform(0.8, 1.4), s * 0.7),
                       400 + i, coll, subdiv=0, rough=0.5, nu=20, nv=12)
        ob.location = (x, y, s * 0.18)
        ob.rotation_euler = (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.3))
        ob.data.materials.append(mat)
    return stones


def build_mountains(coll):
    m = new_material('Mountains')
    nb = NB(m.node_tree)
    tc = nb.n('ShaderNodeTexCoord')
    n = nb.n('ShaderNodeTexNoise', {'Vector': (tc, 'Object'), 'Scale': 0.08, 'Detail': 8.0})
    col = nb.mixc((n, 'Factor'), (0.010, 0.013, 0.020, 1), (0.022, 0.026, 0.036, 1))
    bsdf = nb.n('ShaderNodeBsdfPrincipled', {'Roughness': 0.95})
    nb.link(col, bsdf.inputs['Base Color'])
    out = mat_output(nb)
    nb.link(bsdf, out.inputs['Surface'])
    rng = np.random.default_rng(5)
    nu, nv = 720, 12
    rings = []
    phase = rng.uniform(0, 6.28, 6)
    for j in range(nv):
        t = j / (nv - 1)
        ring = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            h = (14 + 10 * math.sin(a * 3 + phase[0]) + 7 * math.sin(a * 7 + phase[1]) +
                 3.5 * math.sin(a * 17 + phase[2]) + 1.5 * math.sin(a * 41 + phase[3]) +
                 0.6 * math.sin(a * 97 + phase[4]))
            # taller peaks behind the wizard (+Y)
            h += 12 * max(0, math.sin(a)) ** 3
            rr = 150 - t * 25
            z = -2 + t * h + (t * (1 - t)) * 6
            ring.append((rr * math.cos(a), rr * math.sin(a), z))
        rings.append(ring)
    from util import grid_surface
    v, f, uv = grid_surface(np.array(rings), closed_u=True)
    ob = mesh_object('Mountains', v, f, collection=coll)
    ob.data.materials.append(m)
    ob.visible_shadow = False
    return ob


def build_environment():
    coll = get_coll('Environment')
    build_world()
    build_ground(coll)
    build_stones(coll)
    build_mountains(coll)
    return coll
