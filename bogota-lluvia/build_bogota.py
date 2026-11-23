"""
BOGOTÁ BAJO LA LLUVIA — one-take drone shot over downtown Bogotá for Blender 5.3
================================================================================

Downtown Bogotá around Torre Colpatria, rebuilt from real map data:

  * buildings, streets and parks from OpenStreetMap (data/city.json, © OpenStreetMap
    contributors, ODbL), terrain from SRTM-based terrain tiles (data/dem.npz),
  * procedural facades (brick / concrete / plaster / curtain wall) with lit windows,
  * Torre Colpatria modelled by hand with its colour-changing LED facade,
  * wet streets, traffic (cars, yellow taxis, SITP buses, red TransMilenio),
  * rain, low clouds on the eastern hills, Monserrate lit on its peak.

    blender -b --factory-startup -P build_bogota.py            # -> bogota_lluvia.blend

Local frame: metres, origin at the foot of Torre Colpatria, +x east, +y north.
Timeline: 24 fps, frames 0..1439 (60 s), one continuous camera move.
"""

import bpy, math, random, sys, os, json
import numpy as np
from mathutils import Vector, Quaternion, Matrix, noise, kdtree
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blib import (clamp, smoothstep, smootherstep, lerp, ramp_color, sock, NB, new_material,  # noqa: E402
                  set_emission_sampling, new_collection, mesh_object, catmull, Path, gaussian)

FPS = 24
F_START, F_END = 0, 1439
RNG = random.Random(11)
OSM_BOX = (-1500.0, 1330.0, -1410.0, 1630.0)    # area covered by the OSM download (with margin)
GRID_ROT = math.radians(11.0)                    # Bogotá street grid: carreras run ~N 11° E
COLP_TOP, COLP_CROWN = 180.0, 192.0              # Torre Colpatria shaft / crown roof (m)
FINE = (-2400.0, 2600.0, -2400.0, 2600.0)        # fine terrain mesh extent
WET = 1.0

MATS = {}


def hsh(*a):
    """deterministic 0..1 hash"""
    h = 0
    for v in a:
        h = (h * 1000003) ^ hash(str(v))
    return (h & 0xFFFFFFF) / float(0xFFFFFFF)


# ----------------------------------------------------------------------------
# Terrain (exact triangle interpolation so roads/buildings sit on the mesh)
# ----------------------------------------------------------------------------
def blur(a, sigma):
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    return p


class Terrain:
    def __init__(self, path):
        d = np.load(path)
        self.xs, self.ys = d["xs"].astype(float), d["ys"].astype(float)
        self.res = self.xs[1] - self.xs[0]
        H = blur(d["H"].astype(float), 2.5)          # SRTM is a surface model: soften building bumps
        H -= self.h_raw(H, 0.0, 0.0)
        self.H = H

    def h_raw(self, H, x, y):
        i = int(np.argmin(np.abs(self.xs - x)))
        j = int(np.argmin(np.abs(self.ys - y)))
        return H[j, i]

    def h(self, x, y):
        fx = (x - self.xs[0]) / self.res
        fy = (y - self.ys[0]) / self.res
        i = min(max(int(math.floor(fx)), 0), len(self.xs) - 2)
        j = min(max(int(math.floor(fy)), 0), len(self.ys) - 2)
        u, v = clamp(fx - i), clamp(fy - j)
        H = self.H
        h00, h10, h01, h11 = H[j, i], H[j, i + 1], H[j + 1, i], H[j + 1, i + 1]
        if u >= v:
            return float(h00 + u * (h10 - h00) + v * (h11 - h10))
        return float(h00 + v * (h01 - h00) + u * (h11 - h01))

    def slope(self, x, y):
        e = 6.0
        return math.hypot(self.h(x + e, y) - self.h(x - e, y), self.h(x, y + e) - self.h(x, y - e)) / (2 * e)


def point_in_poly(px, py, poly):
    """vectorised even-odd test: px, py arrays"""
    inside = np.zeros(px.shape, bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        cond = ((y1 > py) != (y2 > py))
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = x1 + (py - y1) * (x2 - x1) / (y2 - y1 + 1e-12)
        inside ^= cond & (px < xint)
    return inside


def build_terrain(T, city, coll):
    ix0 = int(np.argmin(np.abs(T.xs - FINE[0])))
    ix1 = int(np.argmin(np.abs(T.xs - FINE[1])))
    iy0 = int(np.argmin(np.abs(T.ys - FINE[2])))
    iy1 = int(np.argmin(np.abs(T.ys - FINE[3])))
    xs, ys = T.xs[ix0:ix1 + 1], T.ys[iy0:iy1 + 1]
    H = T.H[iy0:iy1 + 1, ix0:ix1 + 1]
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys)
    # masks
    park = np.zeros(X.shape)
    forest = np.zeros(X.shape)
    for a in city["areas"]:
        t = a["t"]
        kind = t.get("leisure") or t.get("landuse") or t.get("natural")
        if kind in ("park", "garden", "grass", "pitch", "recreation_ground", "village_green", "grassland",
                    "meadow", "scrub", "playground"):
            tgt = park
        elif kind in ("wood", "forest"):
            tgt = forest
        else:
            continue
        p = np.array(a["p"])
        x0, y0 = p.min(0) - 10
        x1, y1 = p.max(0) + 10
        sel = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
        if not sel.any():
            continue
        tgt[sel] = np.maximum(tgt[sel], point_in_poly(X[sel], Y[sel], a["p"]).astype(float))
    gy, gx = np.gradient(H, T.res)
    slope = np.hypot(gx, gy)
    hill = np.maximum(np.clip((H - 110.0) / 70.0, 0, 1) * (X > 250), np.clip((H - 60.0) / 50.0, 0, 1) * (X > 600))
    forest = np.maximum(forest, hill)
    forest = np.maximum(forest, np.clip((slope - 0.32) / 0.15, 0, 1) * (X > 300))
    inbox = ((X > OSM_BOX[0]) & (X < OSM_BOX[1]) & (Y > OSM_BOX[2]) & (Y < OSM_BOX[3])).astype(float)
    filler = (1 - inbox) * (1 - forest) * (H < 95)
    verts = np.stack([X.ravel(), Y.ravel(), H.ravel()], 1)
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1))
            faces.append((a, a + nx + 1, a + nx))
    ob = mesh_object("Terrain", [tuple(v) for v in verts], faces, coll, mats=[MATS["ground"]], smooth=True,
                     attrs={"park": park.ravel().tolist(), "forest": forest.ravel().tolist(),
                            "filler": filler.ravel().tolist()})
    # coarse outer ring
    step = 4
    cx, cy = T.xs[::step], T.ys[::step]
    CX, CY = np.meshgrid(cx, cy)
    CH = T.H[::step, ::step] - 0.6
    cnx, cny = len(cx), len(cy)
    ov = np.stack([CX.ravel(), CY.ravel(), CH.ravel()], 1)
    of = []
    for j in range(cny - 1):
        for i in range(cnx - 1):
            if (cx[i] > FINE[0] + 60 and cx[i + 1] < FINE[1] - 60 and cy[j] > FINE[2] + 60 and cy[j + 1] < FINE[3] - 60):
                continue
            a = j * cnx + i
            of.append((a, a + 1, a + cnx + 1, a + cnx))
    oforest = np.clip((CH - 110.0) / 70.0, 0, 1) * (CX > 250)
    ofill = (1 - oforest) * (CH < 95)
    outer = mesh_object("TerrainOuter", [tuple(v) for v in ov], of, coll, mats=[MATS["ground"]], smooth=True,
                        attrs={"park": [0.0] * len(ov), "forest": oforest.ravel().tolist(),
                               "filler": ofill.ravel().tolist()})
    return ob, outer


# ----------------------------------------------------------------------------
# Materials
# ----------------------------------------------------------------------------
def attr_node(b, name, kind="GEOMETRY"):
    a = b.new("ShaderNodeAttribute", attribute_name=name, attribute_type=kind)
    return a.outputs["Fac"]


def principled(b, base, rough, metal=0.0, spec=0.5, normal=None, coat=0.0, emit=None, emit_strength=None):
    p = b.new("ShaderNodeBsdfPrincipled")
    b.set(p.inputs["Base Color"], base)
    b.set(p.inputs["Roughness"], rough)
    b.set(p.inputs["Metallic"], metal)
    try:
        b.set(p.inputs["Specular IOR Level"], spec)
    except KeyError:
        pass
    if coat:
        b.set(p.inputs["Coat Weight"], coat)
        p.inputs["Coat Roughness"].default_value = 0.05
    if normal is not None:
        b.set(p.inputs["Normal"], normal)
    if emit is not None:
        b.set(p.inputs["Emission Color"], emit)
        b.set(p.inputs["Emission Strength"], emit_strength if emit_strength is not None else 1.0)
    return p.outputs[0]


def rain_normal(b, coord, strength=0.25, scale=6.0):
    """animated ripple-ish micro normal for wet ground"""
    t = b.time()
    n = b.noise(coord, scale, detail=2.0, rough=0.5, dim="4D", w=b.math("MULTIPLY", t, 2.2))
    bm = b.new("ShaderNodeBump")
    bm.inputs["Strength"].default_value = strength
    bm.inputs["Distance"].default_value = 0.02
    b.set(bm.inputs["Height"], n.outputs["Fac"])
    return bm.outputs[0]


def puddles(b, coord, scale=0.18, lo=0.52, hi=0.6):
    n = b.noise(coord, scale, detail=4.0, rough=0.6)
    return b.math("MULTIPLY", b.math("SUBTRACT", n.outputs["Fac"], lo), 1.0 / (hi - lo), clamp=True)


def building_material():
    """procedural facades driven by face attributes and the 'facade' UV (metres)."""
    m, nt, out = new_material("Facade")
    b = NB(nt)
    uvn = b.new("ShaderNodeUVMap", uv_map="facade")
    u, v, _ = b.sep(uvn.outputs[0])
    bid = attr_node(b, "bid")
    btype = attr_node(b, "btype")          # 0 brick, 1 concrete, 2 glass, 3 plaster
    bh = attr_node(b, "bh")
    litf = attr_node(b, "lit")
    is_glass = b.math("COMPARE", btype, 2.0, 0.1)
    is_brick = b.math("COMPARE", btype, 0.0, 0.1)
    is_plas = b.math("COMPARE", btype, 3.0, 0.1)
    fh = b.math("ADD", 3.1, b.math("MULTIPLY", is_glass, 0.7))          # floor height
    ww = b.math("ADD", 1.9, b.math("MULTIPLY", bid, 0.7))               # window pitch
    fy = b.math("DIVIDE", v, fh)
    fx = b.math("DIVIDE", u, ww)
    floor_i = b.math("FLOOR", fy)
    col_i = b.math("FLOOR", fx)
    ry = b.math("FRACT", fy)
    rx = b.math("FRACT", fx)
    # window rectangle (curtain walls: continuous band)
    wx0 = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, is_glass), 0.27)
    win_x = b.math("MULTIPLY", b.math("GREATER_THAN", rx, wx0), b.math("LESS_THAN", rx, b.math("SUBTRACT", 1.0, wx0)))
    win_y = b.math("MULTIPLY", b.math("GREATER_THAN", ry, b.math("SUBTRACT", 0.32, b.math("MULTIPLY", is_glass, 0.22))),
                   b.math("LESS_THAN", ry, 0.84))
    above = b.math("GREATER_THAN", floor_i, 0.5)
    below_top = b.math("LESS_THAN", v, b.math("SUBTRACT", bh, 1.2))
    win = b.math("MULTIPLY", b.math("MULTIPLY", win_x, win_y), b.math("MULTIPLY", above, below_top))
    # mullions: a vertical bar in the middle and a transom near the top of each window (not on curtain walls)
    mull_v = b.math("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", rx, 0.5)), 0.022)
    mull_h = b.math("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", ry, 0.7)), 0.02)
    mull = b.math("MULTIPLY", b.math("MAXIMUM", mull_v, mull_h), b.math("SUBTRACT", 1.0, is_glass))
    win = b.math("MULTIPLY", win, b.math("SUBTRACT", 1.0, mull))
    # ground floor: shop fronts
    shop = b.math("MULTIPLY", b.math("LESS_THAN", floor_i, 0.5),
                  b.math("MULTIPLY", b.math("GREATER_THAN", v, 0.4), b.math("LESS_THAN", v, 2.9)))
    # per-window random
    wn = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    b.set(wn.inputs["Vector"], b.comb(col_i, floor_i, b.math("MULTIPLY", bid, 977.0)))
    r = wn.outputs["Value"]
    rc = wn.outputs["Color"]
    lit = b.math("LESS_THAN", r, litf)
    rsep = b.new("ShaderNodeSeparateColor")
    b.set(rsep.inputs[0], rc)
    warm = (1.0, 0.56, 0.24)
    cool = (0.72, 0.84, 1.0)
    wcol = b.mix(b.math("GREATER_THAN", rsep.outputs[0], b.math("ADD", 0.72, b.math("MULTIPLY", is_glass, -0.3))), warm, cool)
    wcol = b.mix(b.math("GREATER_THAN", rsep.outputs[1], 0.97), wcol, (0.35, 0.5, 1.0))
    # curtains / interior variation inside a window
    inner = b.noise(b.comb(u, v, b.math("MULTIPLY", bid, 50.0)), 1.6, detail=1.0)
    ivar = b.math("ADD", 0.3, b.math("MULTIPLY", inner.outputs["Fac"], 0.9))
    ivar = b.math("MULTIPLY", ivar, b.math("ADD", 0.55, b.math("MULTIPLY", b.math("SINE", b.math("MULTIPLY", rx, math.pi)), 0.6)))
    wstr = b.math("MULTIPLY", b.math("MULTIPLY", lit, ivar), b.math("ADD", 0.1, b.math("MULTIPLY", b.math("POWER", rsep.outputs[2], 2.0), 0.5)))
    emit_w = b.math("MULTIPLY", win, wstr)
    # shops: colourful strips
    shopn = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="2D")
    b.set(shopn.inputs["Vector"], b.comb(b.math("FLOOR", b.math("DIVIDE", u, 7.0)), b.math("MULTIPLY", bid, 91.0), 0))
    shop_on = b.math("LESS_THAN", shopn.outputs["Value"], 0.35)
    shop_col = b.ramp(shopn.outputs["Value"], [(0.0, (1.0, 0.75, 0.45)), (0.2, (1.0, 0.92, 0.8)), (0.35, (1.0, 0.3, 0.12)),
                                               (0.45, (0.3, 1.0, 0.55)), (0.55, (0.55, 0.75, 1.0)), (0.62, (1.0, 0.6, 0.2))])
    emit_s = b.math("MULTIPLY", b.math("MULTIPLY", shop, shop_on), 0.7)
    ecol = b.mix(shop, wcol, shop_col)
    estr = b.math("ADD", emit_w, emit_s)
    # wall colours
    bricks = b.new("ShaderNodeTexBrick")
    b.set(bricks.inputs["Vector"], uvn.outputs[0])
    bricks.inputs["Scale"].default_value = 1.0
    bricks.inputs["Brick Width"].default_value = 0.25
    bricks.inputs["Row Height"].default_value = 0.075
    bricks.inputs["Mortar Size"].default_value = 0.008
    bricks.inputs["Color1"].default_value = (0.21, 0.065, 0.035, 1)
    bricks.inputs["Color2"].default_value = (0.15, 0.045, 0.028, 1)
    bricks.inputs["Mortar"].default_value = (0.12, 0.10, 0.09, 1)
    conc = b.mix(b.noise(uvn.outputs[0], 0.35, 5.0).outputs["Fac"], (0.13, 0.13, 0.125), (0.2, 0.19, 0.18))
    plaster = b.ramp(b.math("FRACT", b.math("MULTIPLY", bid, 7.13)),
                     [(0.0, (0.55, 0.42, 0.22)), (0.25, (0.6, 0.58, 0.52)), (0.45, (0.25, 0.32, 0.45)),
                      (0.65, (0.5, 0.18, 0.12)), (0.85, (0.55, 0.5, 0.36)), (1.0, (0.35, 0.4, 0.3))], "CONSTANT")
    glassw = (0.03, 0.04, 0.05)
    wall = b.mix(is_brick, conc, bricks.outputs["Color"])
    wall = b.mix(is_plas, wall, plaster)
    wall = b.mix(is_glass, wall, glassw)
    # rain streaks / dirt on facades
    streak = b.noise(b.comb(b.math("MULTIPLY", u, 3.0), b.math("MULTIPLY", v, 0.08), bid), 2.0, 3.0)
    wall = b.mix(b.math("MULTIPLY", streak.outputs["Fac"], 0.5), wall, (0.03, 0.03, 0.03))
    wall = b.mix(0.35 * WET, wall, (0.0, 0.0, 0.0))     # darkened by water
    # glazing: dark reflective
    glass_col = (0.012, 0.016, 0.022)
    base = b.mix(b.math("MAXIMUM", win, shop), wall, glass_col)
    rough = b.mix(b.math("MAXIMUM", win, shop), (0.45, 0.45, 0.45), (0.04, 0.04, 0.04))
    rsplit = b.sep(rough)
    rough_v = b.math("MULTIPLY", rsplit[0], b.math("SUBTRACT", 1.0, b.math("MULTIPLY", is_glass, 0.5)))
    p = principled(b, base, rough_v, metal=0.0, spec=0.6, emit=ecol, emit_strength=estr)
    nt.links.new(p, out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def roof_material():
    m, nt, out = new_material("Roof")
    b = NB(nt)
    tc = b.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    c = b.mix(b.noise(pos, 0.08, 4).outputs["Fac"], (0.04, 0.04, 0.042), (0.09, 0.085, 0.08))
    pud = puddles(b, pos, 0.12, 0.5, 0.58)
    rough = b.math("ADD", 0.05, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, pud), 0.4))
    p = principled(b, c, rough, normal=rain_normal(b, pos, 0.15, 3.0))
    nt.links.new(p, out.inputs["Surface"])
    return m


def ground_material():
    m, nt, out = new_material("Ground")
    b = NB(nt)
    tc = b.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    park = attr_node(b, "park")
    forest = attr_node(b, "forest")
    filler = attr_node(b, "filler")
    px, py, pz = b.sep(pos)
    # sidewalks / plazas: wet concrete tiles
    tiles = b.new("ShaderNodeTexBrick")
    b.set(tiles.inputs["Vector"], pos)
    tiles.inputs["Scale"].default_value = 1.0
    tiles.inputs["Brick Width"].default_value = 0.8
    tiles.inputs["Row Height"].default_value = 0.4
    tiles.inputs["Mortar Size"].default_value = 0.01
    tiles.inputs["Color1"].default_value = (0.07, 0.067, 0.064, 1)
    tiles.inputs["Color2"].default_value = (0.05, 0.049, 0.047, 1)
    tiles.inputs["Mortar"].default_value = (0.04, 0.04, 0.04, 1)
    side = tiles.outputs["Color"]
    grass = b.mix(b.noise(pos, 0.3, 3).outputs["Fac"], (0.012, 0.03, 0.01), (0.03, 0.05, 0.018))
    fn = b.noise(pos, 0.012, 6, 0.7)
    trees = b.mix(fn.outputs["Fac"], (0.003, 0.007, 0.005), (0.014, 0.022, 0.012))
    # far city: rotated street grid with sodium / LED street lights
    ca, sa = math.cos(-GRID_ROT), math.sin(-GRID_ROT)
    gu = b.math("ADD", b.math("MULTIPLY", px, ca), b.math("MULTIPLY", py, -sa))
    gv = b.math("ADD", b.math("MULTIPLY", px, sa), b.math("MULTIPLY", py, ca))
    P, ST = 105.0, 15.0
    fu = b.math("FLOORED_MODULO", gu, P)
    fv = b.math("FLOORED_MODULO", gv, P)
    st_u = b.math("LESS_THAN", fu, ST)
    st_v = b.math("LESS_THAN", fv, ST)
    street = b.math("MAXIMUM", st_u, st_v)
    # lamps every 26 m along each street, at the kerb
    lamp_u = b.math("MULTIPLY", st_u, b.math("LESS_THAN", b.math("FLOORED_MODULO", gv, 26.0), 3.0))
    lamp_u = b.math("MULTIPLY", lamp_u, b.math("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", fu, 2.5)), 2.0))
    lamp_v = b.math("MULTIPLY", st_v, b.math("LESS_THAN", b.math("FLOORED_MODULO", gu, 26.0), 3.0))
    lamp_v = b.math("MULTIPLY", lamp_v, b.math("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", fv, 2.5)), 2.0))
    lamp = b.math("MAXIMUM", lamp_u, lamp_v)
    # light pools around them
    pool_u = b.math("MULTIPLY", st_u, b.math("SUBTRACT", 1.0, b.math("DIVIDE", b.math("ABSOLUTE", b.math("SUBTRACT", b.math("FLOORED_MODULO", gv, 26.0), 13.0)), 13.0)))
    pool_v = b.math("MULTIPLY", st_v, b.math("SUBTRACT", 1.0, b.math("DIVIDE", b.math("ABSOLUTE", b.math("SUBTRACT", b.math("FLOORED_MODULO", gu, 26.0), 13.0)), 13.0)))
    pool = b.math("POWER", b.math("MAXIMUM", pool_u, pool_v), 2.0)
    lane_hash = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="2D")
    b.set(lane_hash.inputs["Vector"], b.comb(b.math("FLOOR", b.math("DIVIDE", gu, P)), b.math("FLOOR", b.math("DIVIDE", gv, P)), 0))
    sodium = b.math("GREATER_THAN", lane_hash.outputs["Value"], 0.35)
    lcol = b.mix(sodium, (0.95, 0.85, 0.7), (1.0, 0.45, 0.12))
    far = b.mix(street, (0.008, 0.008, 0.008), (0.006, 0.006, 0.007))
    t = b.time()
    av_u = b.math("MULTIPLY", st_u, b.math("LESS_THAN", b.math("FLOORED_MODULO", b.math("FLOOR", b.math("DIVIDE", gu, P)), 7.0), 0.5))
    av_v = b.math("MULTIPLY", st_v, b.math("LESS_THAN", b.math("FLOORED_MODULO", b.math("FLOOR", b.math("DIVIDE", gv, P)), 7.0), 0.5))
    # two directions: white heads one side, red tails the other
    half_u = b.math("GREATER_THAN", fu, ST / 2)
    half_v = b.math("GREATER_THAN", fv, ST / 2)
    dots_u = b.math("LESS_THAN", b.math("FLOORED_MODULO", b.math("ADD", gv, b.math("MULTIPLY", b.math("SUBTRACT", b.math("MULTIPLY", half_u, 2.0), 1.0), b.math("MULTIPLY", t, 11.0))), 23.0), 2.2)
    dots_v = b.math("LESS_THAN", b.math("FLOORED_MODULO", b.math("ADD", gu, b.math("MULTIPLY", b.math("SUBTRACT", b.math("MULTIPLY", half_v, 2.0), 1.0), b.math("MULTIPLY", t, 11.0))), 29.0), 2.2)
    cars = b.math("MAXIMUM", b.math("MULTIPLY", av_u, dots_u), b.math("MULTIPLY", av_v, dots_v))
    red = b.math("MAXIMUM", b.math("MULTIPLY", av_u, half_u), b.math("MULTIPLY", av_v, half_v))
    gcol = b.mix(filler, side, far)
    gcol = b.mix(park, gcol, grass)
    gcol = b.mix(forest, gcol, trees)
    pud = puddles(b, pos, 0.15, 0.48, 0.56)
    rough = b.math("ADD", 0.04, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, pud), 0.3))
    rough = b.math("ADD", rough, b.math("MULTIPLY", b.math("MAXIMUM", park, forest), 0.5))
    emit_s = b.math("MULTIPLY", filler, b.math("ADD", b.math("ADD", b.math("MULTIPLY", lamp, 3.0), b.math("MULTIPLY", pool, 0.3)),
                                              b.math("ADD", b.math("MULTIPLY", street, 0.02), b.math("MULTIPLY", cars, 9.0))))
    lcol = b.mix(cars, lcol, b.mix(red, (1.0, 0.92, 0.8), (1.0, 0.04, 0.02)))
    emit_s = b.math("MULTIPLY", emit_s, b.math("SUBTRACT", 1.0, forest))
    vor = b.new("ShaderNodeTexVoronoi", feature="F1")
    b.set(vor.inputs["Vector"], pos)
    vor.inputs["Scale"].default_value = 0.025
    vsep = b.new("ShaderNodeSeparateColor")
    b.set(vsep.inputs[0], vor.outputs["Color"])
    house = b.math("MULTIPLY", b.math("LESS_THAN", vor.outputs["Distance"], 0.04), b.math("LESS_THAN", vsep.outputs[0], 0.18))
    house = b.math("MULTIPLY", b.math("MULTIPLY", house, forest), b.math("LESS_THAN", pz, 260.0))
    emit_s = b.math("ADD", emit_s, b.math("MULTIPLY", house, 6.0))
    lcol = b.mix(house, lcol, (1.0, 0.6, 0.3))
    cb = b.new("ShaderNodeBump")
    cb.inputs["Strength"].default_value = 0.7
    b.set(cb.inputs["Height"], b.noise(pos, 0.08, 4.0, 0.6).outputs["Fac"])
    b.set(cb.inputs["Normal"], rain_normal(b, pos, 0.2, 4.0))
    nrm = b.new("ShaderNodeMix", data_type="VECTOR")
    b.set(sock(nrm, "Factor_Float"), forest)
    b.set(sock(nrm, "A_Vector"), rain_normal(b, pos, 0.2, 4.0))
    b.set(sock(nrm, "B_Vector"), cb.outputs[0])
    p = principled(b, gcol, rough, normal=sock(nrm, "Result_Vector", out=True), emit=lcol, emit_strength=emit_s)
    nt.links.new(p, out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def asphalt_material():
    """wet asphalt with lane markings; UV 'road' = (along m, across m), attrs rw (width), twoway, rlen."""
    m, nt, out = new_material("Asphalt")
    b = NB(nt)
    uvn = b.new("ShaderNodeUVMap", uv_map="road")
    s, a, _ = b.sep(uvn.outputs[0])
    rw = attr_node(b, "rw")
    two = attr_node(b, "twoway")
    rlen = attr_node(b, "rlen")
    ped = attr_node(b, "ped")
    tc = b.new("ShaderNodeTexCoord")
    pos = tc.outputs["Object"]
    base = b.mix(b.noise(pos, 0.6, 5).outputs["Fac"], (0.012, 0.012, 0.013), (0.03, 0.029, 0.028))
    # pedestrian streets: pavers
    pav = b.new("ShaderNodeTexBrick")
    b.set(pav.inputs["Vector"], pos)
    pav.inputs["Scale"].default_value = 1.0
    pav.inputs["Brick Width"].default_value = 0.6
    pav.inputs["Row Height"].default_value = 0.3
    pav.inputs["Mortar Size"].default_value = 0.012
    pav.inputs["Color1"].default_value = (0.09, 0.06, 0.045, 1)
    pav.inputs["Color2"].default_value = (0.06, 0.05, 0.045, 1)
    pav.inputs["Mortar"].default_value = (0.03, 0.03, 0.03, 1)
    base = b.mix(ped, base, pav.outputs["Color"])
    ends = b.math("MULTIPLY", b.math("GREATER_THAN", s, 9.0), b.math("LESS_THAN", s, b.math("SUBTRACT", rlen, 9.0)))
    aa = b.math("ABSOLUTE", a)
    # centre double yellow on two-way roads
    cy = b.math("MULTIPLY", two, b.math("MULTIPLY", b.math("GREATER_THAN", aa, 0.06), b.math("LESS_THAN", aa, 0.2)))
    # dashed white lane lines at +-rw/4 on wide roads
    q = b.math("ABSOLUTE", b.math("SUBTRACT", aa, b.math("DIVIDE", rw, 4.0)))
    dash = b.math("LESS_THAN", b.math("FLOORED_MODULO", s, 9.0), 3.0)
    wl = b.math("MULTIPLY", b.math("MULTIPLY", b.math("LESS_THAN", q, 0.07), dash), b.math("GREATER_THAN", rw, 11.0))
    # edge lines
    el = b.math("MULTIPLY", b.math("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", aa, b.math("SUBTRACT", b.math("DIVIDE", rw, 2.0), 0.35))), 0.06),
                b.math("GREATER_THAN", rw, 8.0))
    paint_w = b.math("MULTIPLY", b.math("MAXIMUM", wl, el), ends)
    paint_y = b.math("MULTIPLY", cy, ends)
    wear = b.noise(pos, 1.5, 3).outputs["Fac"]
    wearm = b.math("GREATER_THAN", wear, 0.38)
    paint_w = b.math("MULTIPLY", b.math("MULTIPLY", paint_w, wearm), b.math("SUBTRACT", 1.0, ped))
    paint_y = b.math("MULTIPLY", b.math("MULTIPLY", paint_y, wearm), b.math("SUBTRACT", 1.0, ped))
    col = b.mix(paint_w, base, (0.35, 0.35, 0.33))
    col = b.mix(paint_y, col, (0.4, 0.26, 0.02))
    pud = puddles(b, pos, 0.2, 0.42, 0.5)
    rough = b.math("ADD", 0.015, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, pud), 0.22))
    p = principled(b, col, rough, spec=0.7, normal=rain_normal(b, pos, 0.28, 5.0))
    nt.links.new(p, out.inputs["Surface"])
    return m


def colpatria_material():
    """Torre Colpatria: dark glass + LED grid washing through colours."""
    m, nt, out = new_material("ColpatriaLED")
    b = NB(nt)
    uvn = b.new("ShaderNodeUVMap", uv_map="facade")
    u, v, _ = b.sep(uvn.outputs[0])
    t = b.time()
    led_v = b.math("LESS_THAN", b.math("FLOORED_MODULO", u, 1.5), 0.08)
    led_h = b.math("LESS_THAN", b.math("FLOORED_MODULO", v, 3.75), 0.3)
    # colour: slow waves rising up the tower
    phase = b.math("ADD", b.math("MULTIPLY", t, 0.045), b.math("MULTIPLY", v, -0.0045))
    phase = b.math("ADD", phase, b.math("MULTIPLY", b.math("SINE", b.math("MULTIPLY", u, 0.05)), 0.04))
    stops = [(0.0, (1.0, 0.05, 0.35)), (0.18, (0.65, 0.05, 1.0)), (0.36, (0.05, 0.25, 1.0)), (0.52, (0.0, 0.8, 1.0)),
             (0.68, (1.0, 0.35, 0.05)), (0.84, (1.0, 0.05, 0.12)), (1.0, (1.0, 0.05, 0.35))]
    col = b.ramp(b.math("FRACT", phase), stops)
    band = b.math("POWER", b.math("MAXIMUM", b.math("SINE", b.math("ADD", b.math("MULTIPLY", v, 0.05), b.math("MULTIPLY", t, -0.9))), 0.0), 4.0)
    led = b.math("ADD", b.math("MULTIPLY", led_h, 1.0), b.math("MULTIPLY", led_v, 0.25))
    strength = b.math("MULTIPLY", led, b.math("ADD", 0.9, b.math("MULTIPLY", band, 0.8)))
    # offices behind the glass: a few lit bays, cool fluorescent / warm
    wn = b.new("ShaderNodeTexWhiteNoise", noise_dimensions="2D")
    b.set(wn.inputs["Vector"], b.comb(b.math("FLOOR", b.math("DIVIDE", u, 3.0)), b.math("FLOOR", b.math("DIVIDE", v, 3.75)), 0))
    office = b.math("MULTIPLY", b.math("LESS_THAN", wn.outputs["Value"], 0.07), b.math("SUBTRACT", 1.0, led_h))
    ocol = b.mix(b.math("GREATER_THAN", wn.outputs["Value"], 0.035), (0.75, 0.85, 1.0), (1.0, 0.7, 0.45))
    col = b.mix(b.math("MULTIPLY", office, b.math("SUBTRACT", 1.0, led_v)), col, ocol)
    glow = b.math("ADD", b.math("ADD", strength, b.math("MULTIPLY", office, 0.12)), 0.03)
    p = principled(b, (0.01, 0.012, 0.018), 0.06, metal=0.3, spec=0.8, emit=col, emit_strength=glow)
    nt.links.new(p, out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m, stops


def car_paint_material():
    m, nt, out = new_material("CarPaint")
    b = NB(nt)
    c = attr_node(b, "col", "INSTANCER")
    pal = b.ramp(c, [(0.0, (0.5, 0.5, 0.52)), (0.25, (0.02, 0.02, 0.022)), (0.45, (0.6, 0.6, 0.62)),
                     (0.6, (0.25, 0.02, 0.02)), (0.72, (0.03, 0.06, 0.15)), (0.85, (0.15, 0.15, 0.16)),
                     (1.0, (0.7, 0.7, 0.7))], "CONSTANT")
    p = principled(b, pal, 0.25, metal=0.5, coat=1.0)
    nt.links.new(p, out.inputs["Surface"])
    return m


def simple_material(name, col, rough=0.5, metal=0.0, coat=0.0):
    m, nt, out = new_material(name)
    b = NB(nt)
    p = principled(b, col, rough, metal=metal, coat=coat)
    nt.links.new(p, out.inputs["Surface"])
    return m


def emission_material(name, col, strength, sampling="NONE"):
    m, nt, out = new_material(name)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*col, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, sampling)
    return m


def lamp_head_material():
    m, nt, out = new_material("LampHead")
    b = NB(nt)
    w = attr_node(b, "warm")
    col = b.mix(w, (0.92, 0.9, 1.0), (1.0, 0.42, 0.1))
    e = b.new("ShaderNodeEmission")
    b.set(e.inputs["Color"], col)
    e.inputs["Strength"].default_value = 22.0
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def blink_material():
    """red aviation lights blinking (phase from attribute)"""
    m, nt, out = new_material("AviationRed")
    b = NB(nt)
    ph = attr_node(b, "phase")
    t = b.time()
    on = b.math("LESS_THAN", b.math("FRACT", b.math("ADD", b.math("MULTIPLY", t, 0.75), ph)), 0.45)
    e = b.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (1.0, 0.03, 0.02, 1)
    b.set(e.inputs["Strength"], b.math("ADD", 0.3, b.math("MULTIPLY", on, 25.0)))
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def window_glow_material(name, col, strength):
    """bus windows: lit interiors"""
    return emission_material(name, col, strength)


def rain_material():
    """drops only catch light from lamps/tower/headlights (glossy), faint against the sky"""
    m, nt, out = new_material("Rain")
    b = NB(nt)
    tr = b.new("ShaderNodeBsdfTransparent")
    gl = b.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.35
    gl.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1)
    em = b.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.6, 0.68, 0.8, 1)
    em.inputs["Strength"].default_value = 0.035
    ad = b.new("ShaderNodeAddShader")
    nt.links.new(gl.outputs[0], ad.inputs[0])
    nt.links.new(em.outputs[0], ad.inputs[1])
    # drops seen against the sky (view ray pointing up) fade out; against the city they stay
    geo = b.new("ShaderNodeNewGeometry")
    _, _, iz = b.sep(geo.outputs["Incoming"])
    vis = b.math("SUBTRACT", 1.0, b.math("DIVIDE", b.math("ADD", b.math("MULTIPLY", iz, -1.0), 0.05), 0.05, clamp=True))
    mx = b.new("ShaderNodeMixShader")
    b.set(mx.inputs[0], b.math("MULTIPLY", vis, 0.4))
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(ad.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def cloud_material():
    m, nt, out = new_material("LowCloud")
    b = NB(nt)
    tc = b.new("ShaderNodeTexCoord")
    g = tc.outputs["Generated"]
    gx, _, gy = b.sep(g)
    oi = b.new("ShaderNodeObjectInfo")
    t = b.time()
    n = b.noise(b.comb(b.math("ADD", b.math("MULTIPLY", gx, 2.2), b.math("MULTIPLY", t, 0.006)), b.math("MULTIPLY", gy, 1.2),
                       b.math("MULTIPLY", oi.outputs["Random"], 10.0)), 2.2, 6.0, 0.62)
    edge = b.math("MULTIPLY", b.math("SINE", b.math("MULTIPLY", gx, math.pi)), b.math("SINE", b.math("MULTIPLY", gy, math.pi)))
    dens = b.math("MULTIPLY", b.math("MULTIPLY", b.math("SUBTRACT", n.outputs["Fac"], 0.45), 2.5, clamp=True), b.math("POWER", edge, 1.6))
    dens = b.math("MINIMUM", dens, 0.6)
    tr = b.new("ShaderNodeBsdfTransparent")
    em = b.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.05, 0.045, 0.05, 1)
    em.inputs["Strength"].default_value = 1.0
    df = b.new("ShaderNodeBsdfDiffuse")
    df.inputs["Color"].default_value = (0.18, 0.19, 0.24, 1)
    ad = b.new("ShaderNodeAddShader")
    nt.links.new(em.outputs[0], ad.inputs[0])
    nt.links.new(df.outputs[0], ad.inputs[1])
    mx = b.new("ShaderNodeMixShader")
    b.set(mx.inputs[0], dens)
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(ad.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    set_emission_sampling(m, "NONE")
    return m


def tree_material():
    m, nt, out = new_material("Foliage")
    b = NB(nt)
    oi = b.new("ShaderNodeObjectInfo")
    c = b.mix(oi.outputs["Random"], (0.012, 0.03, 0.012), (0.035, 0.05, 0.02))
    p = principled(b, c, 0.35)
    nt.links.new(p, out.inputs["Surface"])
    return m


def build_materials():
    MATS["facade"] = building_material()
    MATS["roof"] = roof_material()
    MATS["ground"] = ground_material()
    MATS["asphalt"] = asphalt_material()
    MATS["colpatria"], MATS["colp_stops"] = colpatria_material()
    MATS["paint"] = car_paint_material()
    MATS["taxi"] = simple_material("TaxiYellow", (0.8, 0.45, 0.0), 0.25, coat=1.0)
    MATS["tm_red"] = simple_material("TransMilenioRed", (0.55, 0.01, 0.01), 0.3, coat=1.0)
    MATS["sitp"] = simple_material("SITPBlue", (0.03, 0.12, 0.45), 0.3, coat=1.0)
    MATS["white"] = simple_material("BusWhite", (0.6, 0.6, 0.62), 0.3, coat=1.0)
    MATS["carglass"] = simple_material("CarGlass", (0.01, 0.01, 0.012), 0.03, metal=0.2)
    MATS["tyre"] = simple_material("Tyre", (0.01, 0.01, 0.01), 0.6)
    MATS["head"] = emission_material("Headlight", (1.0, 0.92, 0.8), 16.0)
    MATS["tail"] = emission_material("Taillight", (1.0, 0.02, 0.01), 7.0)
    MATS["taxisign"] = emission_material("TaxiSign", (1.0, 0.8, 0.4), 2.5)
    MATS["buswin"] = window_glow_material("BusInterior", (0.85, 0.9, 1.0), 1.2)
    MATS["metal"] = simple_material("PoleMetal", (0.08, 0.08, 0.085), 0.35, metal=0.8)
    MATS["lamp"] = lamp_head_material()
    MATS["blink"] = blink_material()
    MATS["rain"] = rain_material()
    MATS["cloud"] = cloud_material()
    MATS["foliage"] = tree_material()
    MATS["bark"] = simple_material("Bark", (0.03, 0.022, 0.015), 0.7)
    MATS["church"] = emission_material("FloodlitWhite", (1.0, 0.9, 0.75), 3.0)
    MATS["crown_white"] = simple_material("CrownMetal", (0.5, 0.5, 0.52), 0.3, metal=0.9)


# ----------------------------------------------------------------------------
# Buildings
# ----------------------------------------------------------------------------
def poly_area(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def clean_poly(p, eps=0.25):
    out = []
    for q in p:
        if not out or math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) > eps:
            out.append(q)
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def parse_num(s):
    try:
        return float(str(s).replace("m", "").replace(",", ".").split(";")[0].strip())
    except Exception:
        return None


def estimate_height(t, area, cx, cy, bid):
    h = parse_num(t.get("height"))
    if h:
        return h
    lv = parse_num(t.get("building:levels"))
    if lv:
        return lv * 3.2 + 1.0
    kind = t.get("building", "yes")
    r = hsh(bid, "h")
    d = math.hypot(cx - 0, cy - 250)                      # core: Centro Internacional
    if kind in ("house", "terrace", "detached"):
        fl = 2 + int(r * 2)
    elif kind in ("residential", "apartments"):
        fl = 4 + int(r * 8)
    elif kind in ("commercial", "retail", "office", "hotel"):
        fl = 3 + int(r * 8)
    elif kind in ("university", "school", "public", "government", "college", "hospital"):
        fl = 3 + int(r * 4)
    elif kind in ("church", "cathedral", "chapel"):
        return 18.0 + r * 10
    elif kind in ("garage", "shed", "kiosk", "service", "construction"):
        fl = 1 + int(r * 2)
    else:
        if area < 150:
            fl = 2 + int(r * 3)
        elif area < 600:
            fl = 3 + int(r * 5)
        else:
            fl = 4 + int(r * 8)
        if area > 300 and d < 900 and hsh(bid, "tall") < 0.12:
            fl = 12 + int(hsh(bid, "t2") * 14)
    return fl * 3.2 + 1.0


def facade_type(t, h, bid):
    name = (t.get("name") or "").lower()
    if "torres del parque" in name:
        return 0
    if h > 60:
        return 2 if hsh(bid, "g") < 0.6 else 1
    mat = (t.get("building:material") or "").lower()
    if "brick" in mat:
        return 0
    r = hsh(bid, "ft")
    if h > 25:
        return 0 if r < 0.45 else (1 if r < 0.8 else 2)
    return 0 if r < 0.45 else (3 if r < 0.75 else 1)


class MeshAcc:
    """accumulates walls/roofs with a metre-based 'facade' UV and per-face attributes"""

    def __init__(self):
        self.v, self.f, self.uv, self.mi = [], [], [], []
        self.fattr = {}

    def face(self, idx, uvs, mi, attrs):
        self.f.append(idx)
        self.uv.extend(uvs)
        self.mi.append(mi)
        for k, val in attrs.items():
            self.fattr.setdefault(k, []).append(val)

    def prism(self, poly, z0, z1, attrs, u0=0.0, vref=None, roof=True, roof_mi=1, wall_mi=0):
        if poly_area(poly) < 0:
            poly = poly[::-1]
        n = len(poly)
        vref = z0 if vref is None else vref
        base = len(self.v)
        for x, y in poly:
            self.v.append((x, y, z0))
        for x, y in poly:
            self.v.append((x, y, z1))
        u = u0
        for i in range(n):
            j = (i + 1) % n
            L = math.hypot(poly[j][0] - poly[i][0], poly[j][1] - poly[i][1])
            self.face((base + i, base + j, base + n + j, base + n + i),
                      [(u, z0 - vref), (u + L, z0 - vref), (u + L, z1 - vref), (u, z1 - vref)], wall_mi, attrs)
            u += L
        if roof:
            self.face(tuple(base + n + i for i in range(n)), [(p[0], p[1]) for p in poly], roof_mi, attrs)

    def build(self, name, coll, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for m in mats:
            me.materials.append(m)
        me.polygons.foreach_set("material_index", self.mi)
        uvl = me.uv_layers.new(name="facade")
        flat = [c for uv in self.uv for c in uv]
        uvl.data.foreach_set("uv", flat)
        for k, vals in self.fattr.items():
            a = me.attributes.new(k, "FLOAT", "FACE")
            a.data.foreach_set("value", vals)
        me.validate(clean_customdata=False)
        me.update()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def build_buildings(T, city, coll):
    acc = MeshAcc()
    tall, colp_poly = [], None
    n = 0
    for b in city["buildings"]:
        t = b["t"]
        if t.get("name") == "Torre Colpatria":
            colp_poly = clean_poly(b["p"])
            continue
        if t.get("building") in ("roof", "no", "ruins"):
            continue
        p = clean_poly(b["p"])
        if "building:part" in t and math.hypot(sum(q[0] for q in p) / max(1, len(p)), sum(q[1] for q in p) / max(1, len(p))) < 25:
            continue                     # parts of Torre Colpatria (modelled by hand)
        if len(p) < 3:
            continue
        area = abs(poly_area(p))
        if area < 12:
            continue
        cx = sum(q[0] for q in p) / len(p)
        cy = sum(q[1] for q in p) / len(p)
        bid = b["id"]
        hs = [T.h(x, y) for x, y in p]
        g = min(hs)
        h = estimate_height(t, area, cx, cy, bid)
        mh = parse_num(t.get("min_height")) or 0.0
        if not mh and parse_num(t.get("building:min_level")):
            mh = parse_num(t.get("building:min_level")) * 3.2
        z0 = g - 1.5 if mh < 0.5 else g + mh
        z1 = g + h
        if z1 - z0 < 2.5:
            continue
        ft = facade_type(t, h, bid)
        core = 1 - smoothstep(300, 1500, math.hypot(cx, cy - 200))
        lit = 0.06 + 0.14 * hsh(bid, "lit") + 0.06 * core + (0.05 if ft == 2 else 0.0)
        acc.prism(p, z0, z1, {"bid": hsh(bid, "bid"), "btype": float(ft), "bh": h, "lit": lit},
                  u0=hsh(bid, "u") * 40.0, vref=g)
        if h > 90:
            tall.append((p, z1, bid))
        n += 1
    filler_n = build_filler(T, acc)
    ob = acc.build("Buildings", coll, [MATS["facade"], MATS["roof"]])
    print("buildings", n, "filler", filler_n, "faces", len(acc.f))
    return ob, colp_poly, tall


def build_filler(T, acc):
    """generic city blocks beyond the OSM area, on the rotated Bogotá grid"""
    P, ST = 105.0, 15.0
    ca, sa = math.cos(GRID_ROT), math.sin(GRID_ROT)
    n = 0
    R = 6200.0
    k = int(R / P) + 2
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            # block corner in grid space -> world
            gu0, gv0 = i * P + ST, j * P + ST
            cu, cv = gu0 + (P - ST) / 2, gv0 + (P - ST) / 2
            cx, cy = cu * ca - cv * sa, cu * sa + cv * ca
            d = math.hypot(cx, cy)
            if d > R:
                continue
            if OSM_BOX[0] - 40 < cx < OSM_BOX[1] + 40 and OSM_BOX[2] - 40 < cy < OSM_BOX[3] + 40:
                continue
            if not (FINE[0] - 3500 < cx < FINE[1] + 4300 and FINE[2] - 3500 < cy < FINE[3] + 4300):
                continue
            hc = T.h(cx, cy)
            if hc > 90 or T.slope(cx, cy) > 0.12:
                continue
            if cx > 900 and hc > 60:
                continue
            r = hsh(i, j)
            if r < 0.06:            # a few parks / empty lots
                continue
            lots = 1 if d > 3800 else (3 + int(hsh(i, j, "l") * 4))
            bw = (P - ST)
            for l in range(lots):
                a0 = l * bw / lots + 1.0
                a1 = (l + 1) * bw / lots - 1.0
                for side in ((0, bw),) if lots == 1 else ((0, bw / 2 - 0.5), (bw / 2 + 0.5, bw)):
                    corners = [(gu0 + a0, gv0 + side[0]), (gu0 + a1, gv0 + side[0]),
                               (gu0 + a1, gv0 + side[1]), (gu0 + a0, gv0 + side[1])]
                    poly = [(u * ca - v * sa, u * sa + v * ca) for u, v in corners]
                    rr = hsh(i, j, l, side, "h")
                    fl = 2 + int(rr * 4) + (int(hsh(i, j, l, "m") * 5) if hsh(i, j, "zone") > 0.6 else 0)
                    if rr > 0.9:
                        fl = 7 + int(hsh(i, j, l, "t") * 16)
                    h = fl * 3.0 + 0.8
                    g = min(T.h(x, y) for x, y in poly)
                    bid = hsh(i, j, l, side)
                    acc.prism(poly, g - 2.0, g + h, {"bid": bid, "btype": 0.0 if rr < 0.6 else 3.0, "bh": h,
                                                      "lit": 0.05 + 0.1 * hsh(i, j, l, "lit")},
                              u0=bid * 30.0, vref=g)
                    n += 1
    return n


def build_colpatria(T, poly, coll):
    acc = MeshAcc()
    g = min(T.h(x, y) for x, y in poly)
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    at = {"bid": 0.5, "btype": 2.0, "bh": COLP_CROWN, "lit": 0.5}
    acc.prism(poly, g - 2.0, COLP_TOP, at, vref=g, roof=False)
    crown = [(cx + (x - cx) * 0.9, cy + (y - cy) * 0.9) for x, y in poly]
    acc.prism(crown, COLP_TOP - 0.5, COLP_CROWN, at, vref=g, roof=True, roof_mi=1)
    # thin roof ledge between shaft and crown
    acc.prism([(cx + (x - cx) * 1.01, cy + (y - cy) * 1.01) for x, y in poly], COLP_TOP - 0.6, COLP_TOP + 0.4, at,
              vref=g, roof=True, roof_mi=2, wall_mi=2)
    ob = acc.build("TorreColpatria", coll, [MATS["colpatria"], MATS["roof"], MATS["crown_white"]])
    # antenna mast + aviation light
    mast = []
    mf = []
    for k, (r, z0, z1) in enumerate(((0.35, COLP_CROWN, COLP_CROWN + 8), (0.12, COLP_CROWN + 8, COLP_CROWN + 18))):
        base = len(mast)
        for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            mast.append((cx + sx * r, cy + sy * r, z0))
        for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            mast.append((cx + sx * r, cy + sy * r, z1))
        for i in range(4):
            j = (i + 1) % 4
            mf.append((base + i, base + j, base + 4 + j, base + 4 + i))
    mesh_object("ColpatriaMast", mast, mf, coll, mats=[MATS["crown_white"]], smooth=False)
    return ob, (cx, cy), g


def build_aviation_lights(tall, coll, extra):
    v, f, ph = [], [], []
    for p, z, bid in tall:
        xs = [q[0] for q in p]
        ys = [q[1] for q in p]
        for (x, y) in ((min(xs) + 1, min(ys) + 1), (max(xs) - 1, max(ys) - 1)):
            cube(v, f, (x, y, z + 0.6), 0.25)
            ph.extend([hsh(bid, x)] * 6)
    for (x, y, z, pph) in extra:
        cube(v, f, (x, y, z), 0.22)
        ph.extend([pph] * 6)
    ob = mesh_object("AviationLights", v, f, coll, mats=[MATS["blink"]], smooth=False)
    a = ob.data.attributes.new("phase", "FLOAT", "FACE")
    a.data.foreach_set("value", ph)
    return ob


def cube(v, f, c, r, sz=None):
    sx, sy, sz_ = (r, r, r) if sz is None else sz
    base = len(v)
    for dz in (-sz_, sz_):
        for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
            v.append((c[0] + dx, c[1] + dy, c[2] + dz))
    f.extend([(base + 0, base + 3, base + 2, base + 1), (base + 4, base + 5, base + 6, base + 7),
              (base + 0, base + 1, base + 5, base + 4), (base + 1, base + 2, base + 6, base + 5),
              (base + 2, base + 3, base + 7, base + 6), (base + 3, base + 0, base + 4, base + 7)])


# ----------------------------------------------------------------------------
# Roads, street lamps
# ----------------------------------------------------------------------------
ROAD_W = {"trunk": 20, "primary": 14, "secondary": 11, "tertiary": 9, "residential": 7, "unclassified": 6.5,
          "service": 4.5, "pedestrian": 7, "living_street": 6, "primary_link": 7, "secondary_link": 7,
          "tertiary_link": 6.5, "trunk_link": 8, "busway": 7}
ROAD_DZ = {"trunk": 0.16, "primary": 0.15, "secondary": 0.14, "tertiary": 0.13, "busway": 0.15}


def road_width(t):
    hw = t["highway"]
    lanes = parse_num(t.get("lanes"))
    w = ROAD_W.get(hw)
    if w is None:
        return None
    if lanes and hw not in ("pedestrian", "service"):
        w = max(w * 0.7, lanes * 3.3 + 1.2)
    return w


def resample(p, step):
    out = [p[0]]
    for a, b in zip(p, p[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(math.ceil(L / step)))
        for i in range(1, k + 1):
            out.append((a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k))
    return out


def build_roads(T, city, coll):
    v, f, uv = [], [], []
    fa = {"rw": [], "twoway": [], "rlen": [], "ped": []}
    lamps = []
    for r in city["roads"]:
        t = r["t"]
        w = road_width(t)
        if w is None or len(r["p"]) < 2:
            continue
        if t.get("bridge") == "yes" or (parse_num(t.get("layer")) or 0) < 0:
            continue
        p = resample(r["p"], 3.0)
        n = len(p)
        dz = ROAD_DZ.get(t["highway"], 0.11)
        ped = 1.0 if t["highway"] == "pedestrian" else 0.0
        two = 0.0 if (t.get("oneway") in ("yes", "-1") or ped or t["highway"].endswith("link")) else 1.0
        if w < 8:
            two = 0.0
        # cumulative length
        s = [0.0]
        for a, b in zip(p, p[1:]):
            s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        L = s[-1]
        base = len(v)
        for i in range(n):
            a = p[max(i - 1, 0)]
            b = p[min(i + 1, n - 1)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            for side in (-1, 1):
                x = p[i][0] + nx * side * w / 2
                y = p[i][1] + ny * side * w / 2
                v.append((x, y, T.h(x, y) + dz))
        for i in range(n - 1):
            a0, a1 = base + 2 * i, base + 2 * i + 1
            b0, b1 = base + 2 * i + 2, base + 2 * i + 3
            f.append((a0, b0, b1, a1))
            uv.extend([(s[i], -w / 2), (s[i + 1], -w / 2), (s[i + 1], w / 2), (s[i], w / 2)])
            fa["rw"].append(w)
            fa["twoway"].append(two)
            fa["rlen"].append(L)
            fa["ped"].append(ped)
        # street lamps
        if t["highway"] in ("trunk", "primary", "secondary", "tertiary", "residential", "pedestrian", "busway",
                            "unclassified", "living_street"):
            spacing = 30.0 if t["highway"] in ("trunk", "primary", "secondary") else 34.0
            warm = 0.0 if t["highway"] in ("trunk", "primary", "secondary") else 1.0
            if hsh(r["id"], "sod") < 0.25:
                warm = 1.0 - warm
            k = 0
            d = 6.0 + hsh(r["id"], "o") * 10
            while d < L - 4:
                # find segment
                i = max(0, min(n - 2, int(np.searchsorted(s, d)) - 1))
                u = (d - s[i]) / max(1e-6, s[i + 1] - s[i])
                x = p[i][0] + (p[i + 1][0] - p[i][0]) * u
                y = p[i][1] + (p[i + 1][1] - p[i][1]) * u
                dx, dy = p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]
                ln = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / ln, dx / ln
                side = 1 if k % 2 == 0 or w < 10 else -1
                lx, ly = x + nx * side * (w / 2 + 0.7), y + ny * side * (w / 2 + 0.7)
                lamps.append((lx, ly, T.h(lx, ly), -nx * side, -ny * side, warm, t["highway"]))
                d += spacing
                k += 1
    me = bpy.data.meshes.new("Roads")
    me.from_pydata(v, [], f)
    me.materials.append(MATS["asphalt"])
    uvl = me.uv_layers.new(name="road")
    uvl.data.foreach_set("uv", [c for q in uv for c in q])
    for k, vals in fa.items():
        a = me.attributes.new(k, "FLOAT", "FACE")
        a.data.foreach_set("value", vals)
    me.update()
    ob = bpy.data.objects.new("Roads", me)
    coll.objects.link(ob)
    print("road faces", len(f), "lamps", len(lamps))
    return ob, lamps


def build_lamps(lamps, coll):
    v, f, mi, warm_f = [], [], [], []
    for (x, y, g, ax, ay, warm, hw) in lamps:
        H = 9.0 if hw in ("trunk", "primary", "secondary") else 7.0
        b0 = len(f)
        cube(v, f, (x, y, g + H / 2), 0.0, sz=(0.08, 0.08, H / 2))
        arm = 1.6
        cube(v, f, (x + ax * arm / 2, y + ay * arm / 2, g + H), 0.0, sz=(0.05 + abs(ax) * arm / 2, 0.05 + abs(ay) * arm / 2, 0.05))
        mi.extend([0] * (len(f) - b0))
        b1 = len(f)
        cube(v, f, (x + ax * arm, y + ay * arm, g + H - 0.12), 0.0, sz=(0.32, 0.32, 0.06))
        mi.extend([1] * (len(f) - b1))
        warm_f.extend([warm] * (len(f) - b0))
    ob = mesh_object("StreetLamps", v, f, coll, mats=[MATS["metal"], MATS["lamp"]], mat_idx=mi, smooth=False)
    a = ob.data.attributes.new("warm", "FLOAT", "FACE")
    a.data.foreach_set("value", warm_f)
    return ob


def point_light(coll, name, loc, color, power, radius):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = power
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    coll.objects.link(ob)
    return ob


def build_lamp_lights(lamps, cam_pos, coll):
    kd = kdtree.KDTree(len(cam_pos))
    for i, p in enumerate(cam_pos):
        kd.insert(p, i)
    kd.balance()
    n = 0
    for (x, y, g, ax, ay, warm, hw) in lamps:
        H = 9.0 if hw in ("trunk", "primary", "secondary") else 7.0
        p = Vector((x + ax * 1.6, y + ay * 1.6, g + H - 0.5))
        _, _, d = kd.find(p)
        if d > 170:
            continue
        col = (1.0, 0.45, 0.14) if warm > 0.5 else (0.85, 0.88, 1.0)
        point_light(coll, "StreetLight", p, col, 380.0 if warm > 0.5 else 460.0, 0.25)
        n += 1
    print("street lights", n)


# ----------------------------------------------------------------------------
# Traffic
# ----------------------------------------------------------------------------
def chains_by_name(city, classes):
    ways = [r for r in city["roads"] if r["t"]["highway"] in classes and len(r["p"]) >= 2]
    key = lambda q: (round(q[0], 1), round(q[1], 1))
    by_start = {}
    for r in ways:
        by_start.setdefault((r["t"].get("name"), key(r["p"][0])), []).append(r)
    used = set()
    chains = []
    for r in ways:
        if r["id"] in used:
            continue
        used.add(r["id"])
        pts = list(r["p"])
        tags = r["t"]
        while True:
            nxt = [w for w in by_start.get((tags.get("name"), key(pts[-1])), []) if w["id"] not in used
                   and w["t"].get("oneway") == tags.get("oneway")]
            if not nxt:
                break
            used.add(nxt[0]["id"])
            pts += nxt[0]["p"][1:]
        chains.append((pts, tags))
    return chains


def build_vehicle_protos(coll):
    """V0 car, V1 taxi, V2 SITP bus, V3 TransMilenio articulated. +X forward, origin on the road."""
    protos = []

    def box(v, f, mi, c, s, m):
        b = len(f)
        cube(v, f, c, 0.0, sz=s)
        mi.extend([m] * (len(f) - b))

    def car(name, paint_idx, taxi=False):
        v, f, mi = [], [], []
        box(v, f, mi, (0, 0, 0.68), (2.2, 0.88, 0.36), 0)               # body
        box(v, f, mi, (-0.25, 0, 1.25), (1.15, 0.8, 0.26), 1)           # cabin glass
        box(v, f, mi, (-0.25, 0, 1.53), (1.0, 0.76, 0.03), 0)           # roof
        for sx in (1.45, -1.45):
            for sy in (0.82, -0.82):
                box(v, f, mi, (sx, sy, 0.33), (0.33, 0.12, 0.33), 2)    # wheels
        for sy in (0.6, -0.6):
            box(v, f, mi, (2.2, sy, 0.78), (0.03, 0.17, 0.07), 3)       # headlights
            box(v, f, mi, (-2.2, sy, 0.82), (0.03, 0.2, 0.06), 4)       # taillights
        mats = [paint_idx, MATS["carglass"], MATS["tyre"], MATS["head"], MATS["tail"]]
        if taxi:
            box(v, f, mi, (-0.3, 0, 1.66), (0.25, 0.4, 0.1), 5)
            mats.append(MATS["taxisign"])
        return mesh_object(name, v, f, coll, mats=mats, mat_idx=mi, smooth=False)

    protos.append(car("V0_car", MATS["paint"]))
    protos.append(car("V1_taxi", MATS["taxi"], taxi=True))

    def bus(name, length, body, segs=1):
        v, f, mi = [], [], []
        seg_len = length / segs
        for k in range(segs):
            x0 = length / 2 - seg_len * (k + 0.5)
            box(v, f, mi, (x0, 0, 1.75), (seg_len / 2 - 0.25, 1.25, 1.35), 0)       # body
            box(v, f, mi, (x0, 0, 2.1), (seg_len / 2 - 0.35, 1.27, 0.55), 1)        # lit windows band
            box(v, f, mi, (x0, 0, 0.75), (seg_len / 2 - 0.3, 1.26, 0.35), 2)        # lower white skirt
            for wx in (x0 + seg_len / 2 - 1.8, x0 - seg_len / 2 + 2.0):
                for sy in (1.15, -1.15):
                    box(v, f, mi, (wx, sy, 0.5), (0.5, 0.15, 0.5), 3)
        for sy in (0.85, -0.85):
            box(v, f, mi, (length / 2, sy, 0.8), (0.03, 0.2, 0.1), 4)
            box(v, f, mi, (-length / 2, sy, 0.9), (0.03, 0.2, 0.12), 5)
        box(v, f, mi, (length / 2 + 0.01, 0, 2.9), (0.02, 0.7, 0.12), 6)              # route display
        return mesh_object(name, v, f, coll, mats=[body, MATS["buswin"], MATS["white"], MATS["tyre"], MATS["head"],
                                                   MATS["tail"], MATS["taxisign"]], mat_idx=mi, smooth=False)

    protos.append(bus("V2_sitp", 12.0, MATS["sitp"]))
    protos.append(bus("V3_transmilenio", 18.0, MATS["tm_red"], segs=2))
    return protos


TM_ROADS = ("Avenida Calle 26", "Avenida Carrera 10", "Avenida Calle 13", "Avenida Jiménez", "Avenida Caracas")


def build_traffic(T, city, coll, proto_coll):
    classes = ("trunk", "primary", "secondary", "tertiary", "primary_link", "secondary_link", "trunk_link", "residential")
    chains = chains_by_name(city, classes)
    cu = bpy.data.curves.new("TrafficLanes", "CURVE")
    cu.dimensions = "3D"
    pts_out, at = [], {k: [] for k in ("ci", "off", "spd", "back", "lane", "L", "kind", "col")}
    ci = 0
    for pts, tags in chains:
        p = resample(pts, 4.0)
        if len(p) < 3:
            continue
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:]))
        if L < 70:
            continue
        cx = sum(q[0] for q in p) / len(p)
        cy = sum(q[1] for q in p) / len(p)
        if math.hypot(cx, cy) > 2000:
            continue
        hw = tags["highway"]
        sp = cu.splines.new("POLY")
        sp.points.add(len(p) - 1)
        for k, (x, y) in enumerate(p):
            sp.points[k].co = (x, y, T.h(x, y) + ROAD_DZ.get(hw, 0.11) + 0.02, 1.0)
        w = road_width(tags) or 7.0
        oneway = tags.get("oneway") in ("yes", "-1") or hw.endswith("link")
        rev = 1.0 if tags.get("oneway") == "-1" else 0.0
        lanes = int(parse_num(tags.get("lanes")) or (2 if hw in ("trunk", "primary") else 1 if hw == "residential" else 2))
        lanes = max(1, min(4, lanes))
        major = hw in ("trunk", "primary", "secondary")
        dirs = [(rev, 1)] if oneway else [(0.0, 1), (1.0, 1)]
        per_dir = lanes if oneway else max(1, lanes // 2)
        name = tags.get("name") or ""
        tm = any(nm in name for nm in TM_ROADS)
        for back, _ in dirs:
            for li in range(per_dir):
                if oneway:
                    lane = (li - (per_dir - 1) / 2) * 3.2
                else:
                    lane = 1.9 + li * 3.2
                lane = min(lane, w / 2 - 1.2) if not oneway else lane
                gap_lo, gap_hi = (14, 38) if major else (35, 110)
                s = hsh(ci, back, li) * 20
                spd = (7.5 if major else 5.0) + hsh(ci, li, back, "v") * 3.5
                while s < L:
                    r = hsh(ci, back, li, round(s))
                    kind = 1 if r < 0.32 else 0
                    if major and r > 0.9:
                        kind = 2
                    pts_out.append((0.0, 0.0, 0.0))
                    at["ci"].append(float(ci))
                    at["off"].append(s)
                    at["spd"].append(spd * (0.92 + 0.16 * hsh(ci, s, "jit")))
                    at["back"].append(back)
                    at["lane"].append(lane)
                    at["L"].append(L)
                    at["kind"].append(float(kind))
                    at["col"].append(hsh(ci, s, "c"))
                    s += gap_lo + (gap_hi - gap_lo) * hsh(ci, s, "g")
            if tm and not oneway:
                # TransMilenio in the central lanes
                s = hsh(ci, back, "tm") * 60
                while s < L:
                    pts_out.append((0.0, 0.0, 0.0))
                    at["ci"].append(float(ci)); at["off"].append(s); at["spd"].append(9.5); at["back"].append(back)
                    at["lane"].append(0.0 + 1.75 if not oneway else 0.0); at["L"].append(L); at["kind"].append(3.0)
                    at["col"].append(0.5)
                    s += 140 + 120 * hsh(ci, s, "tg")
        ci += 1
    cob = bpy.data.objects.new("TrafficLanes", cu)
    coll.objects.link(cob)
    cob.hide_render = True
    cob.hide_viewport = True
    me = bpy.data.meshes.new("Vehicles")
    me.from_pydata(pts_out, [], [])
    for k, vals in at.items():
        a = me.attributes.new(k, "FLOAT", "POINT")
        a.data.foreach_set("value", vals)
    ob = bpy.data.objects.new("Traffic", me)
    coll.objects.link(ob)
    g = GN("TrafficFlow")
    pts = g.n("GeometryNodeMeshToPoints")
    g.s(pts.inputs["Mesh"], g.gi.outputs["Geometry"])
    t = g.n("GeometryNodeInputSceneTime").outputs["Seconds"]
    Lr = g.attr("L")
    m = g.math("FLOORED_MODULO", g.math("ADD", g.attr("off"), g.math("MULTIPLY", g.attr("spd"), t)), Lr)
    back = g.attr("back")
    s = g.math("ADD", m, g.math("MULTIPLY", back, g.math("SUBTRACT", Lr, g.math("MULTIPLY", m, 2.0))))
    oi = g.n("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = cob
    scn = g.n("GeometryNodeSampleCurve", mode="LENGTH", use_all_curves=False)
    g.s(scn.inputs["Curves"], oi.outputs["Geometry"])
    g.s(scn.inputs["Length"], s)
    f2i = g.n("FunctionNodeFloatToInt", rounding_mode="ROUND")
    g.s(f2i.inputs[0], g.attr("ci"))
    g.s(scn.inputs["Curve Index"], f2i.outputs[0])
    sign = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", back, 2.0))
    dirv = g.vm("SCALE", scn.outputs["Tangent"], scale=sign)
    right = g.vm("NORMALIZE", g.vm("CROSS_PRODUCT", dirv, (0.0, 0.0, 1.0)))
    pos = g.vm("ADD", scn.outputs["Position"], g.vm("SCALE", right, scale=g.attr("lane")))
    setp = g.n("GeometryNodeSetPosition")
    g.s(setp.inputs["Geometry"], pts.outputs["Points"])
    g.s(setp.inputs["Position"], pos)
    rot = g.n("FunctionNodeAxesToRotation", primary_axis="X", secondary_axis="Z")
    g.s(rot.inputs["Primary Axis"], dirv)
    rot.inputs["Secondary Axis"].default_value = (0.0, 0.0, 1.0)
    fade = g.math("MULTIPLY", g.math("DIVIDE", s, 6.0, clamp=True), g.math("DIVIDE", g.math("SUBTRACT", Lr, s), 6.0, clamp=True))
    ci_n = g.n("GeometryNodeCollectionInfo")
    ci_n.inputs["Collection"].default_value = proto_coll
    ci_n.inputs["Separate Children"].default_value = True
    ci_n.inputs["Reset Children"].default_value = True
    kind_i = g.n("FunctionNodeFloatToInt", rounding_mode="ROUND")
    g.s(kind_i.inputs[0], g.attr("kind"))
    iop = g.n("GeometryNodeInstanceOnPoints")
    g.s(iop.inputs["Points"], setp.outputs["Geometry"])
    g.s(iop.inputs["Instance"], ci_n.outputs["Instances"])
    iop.inputs["Pick Instance"].default_value = True
    g.s(iop.inputs["Instance Index"], kind_i.outputs[0])
    g.s(iop.inputs["Rotation"], rot.outputs["Rotation"])
    g.s(iop.inputs["Scale"], fade)
    g.s(g.go.inputs["Geometry"], iop.outputs["Instances"])
    md = ob.modifiers.new("Flow", "NODES")
    md.node_group = g.ng
    print("traffic: lanes", ci, "vehicles", len(pts_out))
    return ob


class GN:
    def __init__(self, name):
        self.ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        self.ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        self.ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        self.N, self.L = self.ng.nodes, self.ng.links
        self.gi = self.N.new("NodeGroupInput")
        self.go = self.N.new("NodeGroupOutput")

    def n(self, t, **kw):
        nd = self.N.new(t)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def s(self, sk, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.L.new(v, sk)
        elif v is not None:
            sk.default_value = v

    def math(self, op, a, b=None, c=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.s(m.inputs[0], a)
        if b is not None:
            self.s(m.inputs[1], b)
        if c is not None:
            self.s(m.inputs[2], c)
        return m.outputs[0]

    def vm(self, op, a, b=None, scale=None):
        m = self.n("ShaderNodeVectorMath", operation=op)
        self.s(m.inputs[0], a)
        if b is not None:
            self.s(m.inputs[1], b)
        if scale is not None:
            self.s(sock(m, "Scale"), scale)
        return sock(m, "Value", out=True) if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else sock(m, "Vector", out=True)

    def attr(self, name):
        a = self.n("GeometryNodeInputNamedAttribute", data_type="FLOAT")
        a.inputs["Name"].default_value = name
        return a.outputs["Attribute"]

    def sep(self, v):
        s = self.n("ShaderNodeSeparateXYZ")
        self.s(s.inputs[0], v)
        return s.outputs

    def comb(self, x, y, z):
        c = self.n("ShaderNodeCombineXYZ")
        self.s(c.inputs[0], x)
        self.s(c.inputs[1], y)
        self.s(c.inputs[2], z)
        return c.outputs[0]


# ----------------------------------------------------------------------------
# Rain, clouds, trees, landmarks on the hills
# ----------------------------------------------------------------------------
RAIN_BOX = (36.0, 36.0, 24.0)
RAIN_FALL = Vector((1.2, 0.6, -8.5))


def build_rain(cam, coll, count=12000):
    rng = random.Random(5)
    pts = [(rng.uniform(-0.5, 0.5) * RAIN_BOX[0], rng.uniform(-0.5, 0.5) * RAIN_BOX[1],
            rng.uniform(-0.5, 0.5) * RAIN_BOX[2]) for _ in range(count)]
    me = bpy.data.meshes.new("RainDrops")
    me.from_pydata(pts, [], [])
    ob = bpy.data.objects.new("Rain", me)
    coll.objects.link(ob)
    # streak prototype: two crossed thin quads along the fall direction
    d = RAIN_FALL.normalized()
    w, ln = 0.0045, 0.55
    side1 = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.99 else Vector((1, 0, 0))).normalized()
    side2 = d.cross(side1).normalized()
    v, f = [], []
    for sd in (side1, side2):
        b = len(v)
        for a, s_ in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
            p = d * (a * ln / 2) + sd * (s_ * w)
            v.append(tuple(p))
        f.append((b, b + 1, b + 2, b + 3))
    streak = mesh_object("RainStreak", v, f, coll, mats=[MATS["rain"]], smooth=False)
    streak.hide_render = True
    streak.location = (0, 0, -500)
    g = GN("RainFall")
    m2p = g.n("GeometryNodeMeshToPoints")
    g.s(m2p.inputs["Mesh"], g.gi.outputs["Geometry"])
    t = g.n("GeometryNodeInputSceneTime").outputs["Seconds"]
    pos = g.n("GeometryNodeInputPosition").outputs[0]
    ci = g.n("GeometryNodeObjectInfo")
    ci.inputs["Object"].default_value = cam
    camloc = ci.outputs["Location"]
    q = g.vm("SUBTRACT", g.vm("ADD", pos, g.vm("SCALE", tuple(RAIN_FALL), scale=t)), camloc)
    B = RAIN_BOX
    qn = g.vm("SUBTRACT", q, g.vm("MULTIPLY", g.vm("FLOOR", g.vm("ADD", g.vm("DIVIDE", q, B), (0.5, 0.5, 0.5))), B))
    newp = g.vm("ADD", camloc, qn)
    x, y, z = g.sep(qn)
    a = g.math("MAXIMUM", g.math("MAXIMUM", g.math("ABSOLUTE", g.math("DIVIDE", x, B[0] / 2)),
                                  g.math("ABSOLUTE", g.math("DIVIDE", y, B[1] / 2))),
               g.math("ABSOLUTE", g.math("DIVIDE", z, B[2] / 2)))
    edge = g.math("SUBTRACT", 1.0, g.math("DIVIDE", g.math("SUBTRACT", a, 0.75), 0.2, clamp=True))
    near = g.math("DIVIDE", g.math("SUBTRACT", g.vm("LENGTH", qn), 1.6), 2.0, clamp=True)
    rnd = g.n("FunctionNodeRandomValue", data_type="FLOAT")
    sock(rnd, "Min").default_value = 0.6
    sock(rnd, "Max").default_value = 1.4
    sc = g.math("MULTIPLY", g.math("MULTIPLY", edge, near), [o for o in rnd.outputs if not o.is_unavailable][0])
    setp = g.n("GeometryNodeSetPosition")
    g.s(setp.inputs["Geometry"], m2p.outputs["Points"])
    g.s(setp.inputs["Position"], newp)
    oi = g.n("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = streak
    iop = g.n("GeometryNodeInstanceOnPoints")
    g.s(iop.inputs["Points"], setp.outputs["Geometry"])
    g.s(iop.inputs["Instance"], oi.outputs["Geometry"])
    g.s(iop.inputs["Scale"], sc)
    g.s(g.go.inputs["Geometry"], iop.outputs["Instances"])
    md = ob.modifiers.new("Fall", "NODES")
    md.node_group = g.ng
    for attr in ("visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission"):
        setattr(ob, attr, False)
    return ob


def local_peak(T, x, y, r=250):
    best = (-1e9, x, y)
    for dx in np.arange(-r, r + 1, 10):
        for dy in np.arange(-r, r + 1, 10):
            h = T.h(x + dx, y + dy)
            if h > best[0]:
                best = (h, x + dx, y + dy)
    return best


def build_hills(T, coll):
    """Monserrate sanctuary + Guadalupe on the peaks, antenna lights, low clouds on the hills."""
    v, f = [], []
    h, mx, my = local_peak(T, 1540, -575)
    cube(v, f, (mx, my, h + 7), 0, sz=(16, 6, 7))                      # church nave
    cube(v, f, (mx - 14, my, h + 14), 0, sz=(3.5, 3.5, 14))            # towers
    cube(v, f, (mx - 14, my + 9, h + 12), 0, sz=(3, 3, 12))
    cube(v, f, (mx + 22, my - 10, h + 4), 0, sz=(10, 7, 4))            # restaurants
    gh, gx, gy = local_peak(T, 1810, -2100, 350)
    cube(v, f, (gx, gy, gh + 9), 0, sz=(2.2, 2.2, 9))                  # Guadalupe statue
    cube(v, f, (gx + 12, gy, gh + 5), 0, sz=(7, 5, 5))
    # funicular / cable-car line lights down Monserrate
    sx, sy = mx - 600, my + 230
    for k in range(26):
        u = k / 25
        x, y = lerp(mx - 20, sx, u), lerp(my + 5, sy, u)
        cube(v, f, (x, y, T.h(x, y) + 2.0), 0.9)
    mesh_object("Monserrate", v, f, coll, mats=[MATS["church"]], smooth=False)
    print("Monserrate peak", round(mx), round(my), round(h), "| Guadalupe", round(gx), round(gy), round(gh))
    extra = [(mx + 40, my + 30, h + 30, 0.1), (mx + 120, my + 260, T.h(mx + 120, my + 260) + 40, 0.4),
             (gx + 30, gy + 40, gh + 35, 0.7)]
    # low clouds clinging to the eastern hills
    cl = []
    rng = random.Random(9)
    for k in range(14):
        y = rng.uniform(-2600, 2400)
        x = rng.uniform(900, 2300)
        z = T.h(x, y) + rng.uniform(-90, 50)
        w, hgt = rng.uniform(700, 1400), rng.uniform(160, 320)
        me = bpy.data.meshes.new("Cloud")
        me.from_pydata([(-w / 2, 0, -hgt / 2), (w / 2, 0, -hgt / 2), (w / 2, 0, hgt / 2), (-w / 2, 0, hgt / 2)], [], [(0, 1, 2, 3)])
        me.materials.append(MATS["cloud"])
        ob = bpy.data.objects.new("LowCloud", me)
        ob.location = (x, y, z)
        ob.rotation_euler = (0, 0, math.radians(90 + rng.uniform(-25, 25)))
        coll.objects.link(ob)
        for fr, dxx in ((0, 0.0), (F_END, rng.uniform(-60, 60))):
            ob.location = (x, y + dxx, z)
            ob.keyframe_insert("location", frame=fr)
        for fc in ob.animation_data.action.fcurves if hasattr(ob.animation_data.action, "fcurves") else []:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        for attr in ("visible_shadow",):
            setattr(ob, attr, False)
        cl.append(ob)
    return extra, (mx, my, h)


def build_trees(terrain, coll):
    """trees in parks via geometry nodes (density from the 'park' attribute)"""
    v, f = [], []
    # trunk
    cube(v, f, (0, 0, 2.0), 0, sz=(0.18, 0.18, 2.0))
    tr = mesh_object("TreeTrunk", v, f, coll, mats=[MATS["bark"]], smooth=False)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=3.0)
    for vv in bm.verts:
        co = vv.co.copy()
        nn = noise.noise(co * 0.6 + Vector((3, 1, 2)))
        vv.co = co * (1 + 0.25 * nn)
        vv.co.z = vv.co.z * 0.85 + 5.5
    me = bpy.data.meshes.new("TreeCanopy")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS["foliage"])
    can = bpy.data.objects.new("TreeCanopy", me)
    coll.objects.link(can)
    tree_c = new_collection("TreeProto", coll)
    for ob in (tr, can):
        coll.objects.unlink(ob)
        tree_c.objects.link(ob)
    tree_c.hide_render = True
    g = GN("ParkTrees")
    dist = g.n("GeometryNodeDistributePointsOnFaces", distribute_method="RANDOM")
    g.s(dist.inputs["Mesh"], g.gi.outputs["Geometry"])
    g.s(dist.inputs["Density"], g.math("MULTIPLY", g.attr("park"), 0.011))
    dist.inputs["Seed"].default_value = 4
    cinfo = g.n("GeometryNodeCollectionInfo")
    cinfo.inputs["Collection"].default_value = tree_c
    iop = g.n("GeometryNodeInstanceOnPoints")
    g.s(iop.inputs["Points"], dist.outputs["Points"])
    g.s(iop.inputs["Instance"], cinfo.outputs["Instances"])
    rs = g.n("FunctionNodeRandomValue", data_type="FLOAT")
    sock(rs, "Min").default_value = 0.7
    sock(rs, "Max").default_value = 1.3
    g.s(iop.inputs["Scale"], [o for o in rs.outputs if not o.is_unavailable][0])
    rr = g.n("FunctionNodeRandomValue", data_type="FLOAT_VECTOR")
    sock(rr, "Min").default_value = (0, 0, 0)
    sock(rr, "Max").default_value = (0, 0, 6.28)
    g.s(iop.inputs["Rotation"], [o for o in rr.outputs if o.type == "VECTOR" and not o.is_unavailable][0])
    join = g.n("GeometryNodeJoinGeometry")
    g.s(join.inputs[0], g.gi.outputs["Geometry"])
    g.s(join.inputs[0], iop.outputs["Instances"])
    g.s(g.go.inputs["Geometry"], join.outputs[0])
    md = terrain.modifiers.new("Trees", "NODES")
    md.node_group = g.ng


# ----------------------------------------------------------------------------
# World + key lights
# ----------------------------------------------------------------------------
def build_world(scene):
    w = bpy.data.worlds.new("RainySky")
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
    sky = b.ramp(z, [(0.0, (0.01, 0.01, 0.012)), (0.47, (0.045, 0.038, 0.035)), (0.5, (0.055, 0.044, 0.038)),
                     (0.58, (0.045, 0.042, 0.048)), (0.72, (0.03, 0.035, 0.052)), (1.0, (0.017, 0.022, 0.044))], "EASE")
    cl = b.noise(dirv, 4.0, 5.0, 0.6)
    sky = b.mix(b.math("MULTIPLY", b.math("SUBTRACT", cl.outputs["Fac"], 0.4), 0.5, clamp=True), sky,
                (0.06, 0.055, 0.06))
    bg = b.new("ShaderNodeBackground")
    b.set(bg.inputs["Color"], sky)
    bg.inputs["Strength"].default_value = 1.5
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    w.mist_settings.start = 25.0
    w.mist_settings.depth = 9000.0
    w.mist_settings.falloff = "LINEAR"
    # soft cool skylight (overcast blue hour)
    sd = bpy.data.lights.new("Overcast", "SUN")
    sd.energy = 0.3
    sd.color = (0.6, 0.72, 1.0)
    sd.angle = math.radians(60)
    so = bpy.data.objects.new("Overcast", sd)
    so.rotation_euler = (math.radians(25), math.radians(15), 0)
    scene.collection.objects.link(so)


def build_colpatria_lights(center, coll, stops):
    """area lights on the four faces, colour animated to match the LED wash (they light the street)."""
    cx, cy = center
    lights = []
    for k, (nx, ny) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
        ld = bpy.data.lights.new("ColpatriaWash", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = 34.0, 90.0
        ld.energy = 22000.0
        ob = bpy.data.objects.new("ColpatriaWash", ld)
        ob.location = (cx + nx * 20.0, cy + ny * 20.0, 60.0)
        d = Vector((nx, ny, -0.25)).normalized()
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        coll.objects.link(ob)
        lights.append(ld)
    for fr in range(0, F_END + 1, 6):
        t = fr / FPS
        ph = (t * 0.045 - 60 * 0.0045) % 1.0
        c = ramp_color(stops, ph)
        for ld in lights:
            ld.color = c
            ld.keyframe_insert("color", frame=fr)
    # warm street level spill from shops along Carrera 7
    return lights


# ----------------------------------------------------------------------------
# Camera
# ----------------------------------------------------------------------------
def cra7_center(city):
    pts = []
    for r in city["roads"]:
        if r["t"].get("name") == "Avenida Carrera 7" and r["t"]["highway"] in ("primary", "secondary", "tertiary"):
            pts += r["p"]
    pts.sort(key=lambda q: q[1])
    return pts


def x_at(pts, y):
    for a, b in zip(pts, pts[1:]):
        if a[1] <= y <= b[1]:
            u = (y - a[1]) / max(1e-6, b[1] - a[1])
            return a[0] + (b[0] - a[0]) * u
    return pts[-1][0]


def control_points(T, city):
    """(point, frame) pairs: Carrera 7 low run -> climb the east face of the tower -> over the top -> arc."""
    c7 = cra7_center(city)
    cps = []
    for y, fr in ((222, 0), (182, 62), (142, 122), (104, 178), (70, 228)):
        x = x_at(c7, y)
        cps.append((Vector((x, y, T.h(x, y) + 10.5)), fr))
    cps += [((40.0, 36.0, 12.5), 276), ((34.0, 16.0, 22.0), 326), ((35.0, 6.0, 42.0), 380), ((35.0, 1.5, 78.0), 450),
            ((35.0, 0.0, 118.0), 525), ((35.0, 0.0, 152.0), 590), ((34.0, 0.0, 178.0), 640), ((30.0, -1.0, 198.0), 690),
            ((22.0, -12.0, 211.0), 735), ((4.0, -16.0, 218.0), 780), ((-26.0, -18.0, 220.0), 840),
            ((-62.0, -20.0, 218.0), 930), ((-105.0, -18.0, 216.0), 1020), ((-145.0, -40.0, 217.0), 1110),
            ((-172.0, -75.0, 221.0), 1210), ((-190.0, -112.0, 226.0), 1320), ((-200.0, -135.0, 230.0), 1439)]
    return [(Vector(p), fr) for p, fr in cps]


def monotone(xs, ys):
    """Fritsch-Carlson monotone cubic interpolant"""
    n = len(xs)
    d = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [(d[i - 1] + d[i]) / 2 if d[i - 1] * d[i] > 0 else 0.0 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0.0
            continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        r = a * a + b * b
        if r > 9:
            t = 3 / math.sqrt(r)
            m[i], m[i + 1] = t * a * d[i], t * b * d[i]

    def f(x):
        if x <= xs[0]:
            return ys[0] + m[0] * (x - xs[0])
        if x >= xs[-1]:
            return ys[-1] + m[-1] * (x - xs[-1])
        i = max(k for k in range(n - 1) if xs[k] <= x)
        h = xs[i + 1] - xs[i]
        t = (x - xs[i]) / h
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * ys[i] + h10 * h * m[i] + h01 * ys[i + 1] + h11 * h * m[i + 1]
    return f


YAW_KEYS = [(330, -150.0), (430, -180.0), (1000, -180.0)]
PITCH_KEYS = [(0, 3.0), (180, 9.0), (290, 30.0), (380, 44.0), (590, 42.0), (650, 18.0), (700, 4.0), (780, -8.0),
              (950, -11.0), (1080, -7.0), (1439, -4.0)]


def keyed(keys, f):
    if f <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f <= f1:
            u = smootherstep(f0, f1, f)
            return lerp(v0, v1, u)
    return keys[-1][1]


def build_camera(scene, path, cp_frames):
    frames = list(range(F_START - 2, F_END + 3))
    sf = monotone([float(fr) for fr in cp_frames], [path.s[i * 24] for i in range(len(cp_frames))])
    s = [sf(float(f)) for f in frames]
    print("path length %.1f m" % path.L)
    pos = [path.at(x) for x in s]
    spd = [abs(s[min(i + 1, len(s) - 1)] - s[max(i - 1, 0)]) * FPS / 2 for i in range(len(s))]
    dirs = []
    for i, f in enumerate(frames):
        ahead = max(4.0, spd[i] * 0.8)
        a = path.at(s[i] + ahead)
        b = path.at(max(0.0, s[i] - 1.0))
        d = a - b
        d.z = 0
        if d.length < 1e-4:
            d = dirs[-1] if dirs else Vector((0, -1, 0))
        dirs.append(d.normalized())
    yaw_f = [math.degrees(math.atan2(d.y, d.x)) for d in dirs]
    for i in range(1, len(yaw_f)):
        while yaw_f[i] - yaw_f[i - 1] > 180:
            yaw_f[i] -= 360
        while yaw_f[i] - yaw_f[i - 1] < -180:
            yaw_f[i] += 360
    yaw_f = gaussian(yaw_f, 6)
    manual = YAW_KEYS
    yaw = []
    for i, f in enumerate(frames):
        fp = max(0, f)
        w = smootherstep(220, 400, fp)
        ym = keyed(manual, fp)
        yaw.append(lerp(yaw_f[i], ym, w))
    yaw = gaussian(yaw, 4)
    yr = [(yaw[min(i + 1, len(yaw) - 1)] - yaw[max(i - 1, 0)]) * FPS / 2 for i in range(len(yaw))]
    bank = gaussian([clamp(math.radians(yr[i]) * spd[i] / 9.81 * 0.6, -0.35, 0.35) for i in range(len(yaw))], 8)

    cam_d = bpy.data.cameras.new("Drone")
    cam_d.sensor_width = 36.0
    cam_d.clip_start = 0.1
    cam_d.clip_end = 12000.0
    cam = bpy.data.objects.new("Drone", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.rotation_mode = "QUATERNION"
    prev = None
    look_a = Vector((0.0, 0.0, 168.0))       # crown of the tower
    look_b = Vector((600.0, 50.0, 187.0))     # tower (left) + Monserrate (right) framing
    for i, f in enumerate(frames):
        fp = max(0, f)
        p = pos[i]
        yw = math.radians(yaw[i])
        pt = math.radians(keyed(PITCH_KEYS, fp))
        fwd = Vector((math.cos(yw) * math.cos(pt), math.sin(yw) * math.cos(pt), math.sin(pt)))
        wl = smootherstep(1060, 1300, fp)
        tgt = look_a.lerp(look_b, smootherstep(1180, 1439, fp))
        d = fwd.lerp((tgt - p).normalized(), wl).normalized()
        roll = bank[i] * (1 - 0.7 * smootherstep(300, 420, fp) * (1 - smootherstep(700, 800, fp)))
        amp = math.radians(0.22) * (spd[i] / 15.0) + math.radians(0.06)
        jx = amp * noise.noise(Vector((fp * 0.13, 1.3, 0.0)))
        jy = amp * noise.noise(Vector((fp * 0.13, 7.9, 0.0)))
        jr = amp * 1.2 * noise.noise(Vector((fp * 0.09, 4.2, 0.0)))
        q = d.to_track_quat("-Z", "Y")
        q = q @ Quaternion((0, 0, 1), roll + jr) @ Quaternion((1, 0, 0), jy) @ Quaternion((0, 1, 0), jx)
        if prev is not None and q.dot(prev) < 0:
            q = -q
        prev = q
        cam.location = p
        cam.rotation_quaternion = q
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
        lens = 20.0
        lens = lerp(lens, 17.0, smootherstep(300, 420, fp))
        lens = lerp(lens, 21.0, smootherstep(700, 850, fp))
        lens = lerp(lens, 26.0, smootherstep(1050, 1439, fp))
        cam_d.lens = lens
        cam_d.keyframe_insert("lens", frame=f)
    for fp in (0, 150, 300, 420, 560, 700, 780, 900, 1050, 1200, 1439):
        i = frames.index(fp)
        print("frame %4d  pos (%.1f, %.1f, %.1f)  v %.1f m/s" % (fp, pos[i].x, pos[i].y, pos[i].z, spd[i]))
    return cam, pos


# ----------------------------------------------------------------------------
# Render settings + compositor
# ----------------------------------------------------------------------------
FOG = (0.08, 0.064, 0.055)


def build_compositor(scene):
    """mist fog on geometry; the sky (mist == 1) keeps its own gradient."""
    ng = bpy.data.node_groups.new("BogotaComp", "CompositorNodeTree")
    scene.compositing_node_group = ng
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers")
    rl.scene = scene
    mr = N.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Max"].default_value = 0.5
    mr.inputs["To Max"].default_value = 0.88
    L.new(rl.outputs["Mist"], mr.inputs["Value"])
    sky = N.new("ShaderNodeMath")
    sky.operation = "LESS_THAN"
    L.new(rl.outputs["Mist"], sky.inputs[0])
    sky.inputs[1].default_value = 0.985
    fac = N.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    L.new(mr.outputs[0], fac.inputs[0])
    L.new(sky.outputs[0], fac.inputs[1])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(fac.outputs[0], sock(mix, "Factor_Float"))
    L.new(rl.outputs["Image"], sock(mix, "A_Color"))
    sock(mix, "B_Color").default_value = (*FOG, 1)
    gl = N.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Quality"].default_value = "High"
    gl.inputs["Threshold"].default_value = 0.9
    gl.inputs["Strength"].default_value = 0.55
    gl.inputs["Size"].default_value = 0.8
    L.new(sock(mix, "Result_Color", out=True), gl.inputs["Image"])
    ld = N.new("CompositorNodeLensdist")
    ld.inputs["Dispersion"].default_value = 0.01
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
    r.filepath = "//frames/bg_"
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    c = scene.cycles
    c.device = "CPU"
    c.samples = 10
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
    c.transmission_bounces = 0
    c.transparent_max_bounces = 8
    c.volume_bounces = 0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 6.0
    c.blur_glossy = 0.5
    try:
        c.use_light_tree = True
    except Exception:
        pass
    scene.view_layers[0].use_pass_mist = True

    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Punchy", "Punchy"):
        try:
            vs.look = look
            break
        except Exception:
            continue
    vs.exposure = 0.55


# ----------------------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = os.path.join(HERE, "bogota_lluvia.blend")
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "BogotaLluvia"
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = F_START, F_END
    city = json.load(open(os.path.join(HERE, "data", "city.json")))
    T = Terrain(os.path.join(HERE, "data", "dem.npz"))
    build_materials()
    world_c = new_collection("City")
    terrain, outer = build_terrain(T, city, world_c)
    bld, colp_poly, tall = build_buildings(T, city, world_c)
    colp, colp_c, colp_g = build_colpatria(T, colp_poly, world_c)
    roads, lamps = build_roads(T, city, world_c)
    build_lamps(lamps, world_c)
    cps = control_points(T, city)
    dense = catmull([p for p, _ in cps], 24)
    path = Path(dense)
    cam, cam_pos = build_camera(scene, path, [fr for _, fr in cps])
    light_c = new_collection("Lights")
    build_lamp_lights(lamps, cam_pos, light_c)
    build_colpatria_lights(colp_c, light_c, MATS["colp_stops"])
    extra, monserrate = build_hills(T, world_c)
    extra.append((colp_c[0], colp_c[1], COLP_CROWN + 18.5, 0.0))
    build_aviation_lights(tall, world_c, extra)
    proto_c = new_collection("VehicleProtos")
    build_vehicle_protos(proto_c)
    proto_c.hide_render = True
    for ob in proto_c.objects:
        ob.location = (0, 0, -300)
    traffic_c = new_collection("Traffic")
    build_traffic(T, city, traffic_c, proto_c)
    build_trees(terrain, world_c)
    build_rain(cam, new_collection("Rain"))
    build_world(scene)
    render_settings(scene)
    build_compositor(scene)
    bpy.context.view_layer.update()
    # clearance along the flight path
    for ob in (bld, colp):
        me = ob.data
        bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
        md, mf = 1e9, -1
        for i, p in enumerate(cam_pos):
            hit = bvh.find_nearest(p)
            if hit[0] is not None and hit[3] < md:
                md, mf = hit[3], i - 2
        print("clearance %-16s %.2f m at frame %d" % (ob.name, md, mf))
    gmin = min((p.z - T.h(p.x, p.y), i - 2) for i, p in enumerate(cam_pos))
    print("min height over ground %.2f m at frame %d" % gmin)
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
