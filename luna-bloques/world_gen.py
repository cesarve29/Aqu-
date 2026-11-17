"""Genera el mundo de bloques: terreno, poblado japonés anime, pagoda, torii, cerezos, estanque.

Salida: assets/world.npz
  W         (NX, NY, NZ) uint8   id de bloque (0 = aire), índice [x, y, z] con origen en ORIGIN
  plants    (n, 4) float         x, y, z, tipo (0 = trigo, 1 = flores)
  lights    (n, 4) float         x, y, z, tipo (0 = farolillo, 1 = linterna de piedra, 2 = hoguera, 3 = ventana)
"""
import os
import numpy as np
from scipy import ndimage
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
rng = np.random.default_rng(5)

NX, NY, NZ = 256, 256, 64
ORIGIN = np.array([-128, -128, 0])          # coordenada del mundo del índice [0,0,0]
W = np.zeros((NX, NY, NZ), np.uint8)

AIR, GRASS, DIRT, STONE, COBBLE, PATH, PLAZA, SBRICK, PLANKS, LACQ, DWOOD, LOG, SHOJI, SHOJI_LIT, \
    ROOF, SAKURA, LEAVES, WATER, SAND, FARM, LANTERN, SLANTERN, TATAMI = range(23)

G = 5                                       # altura del suelo del poblado (cara superior)
plants, lights = [], []


def idx(x, y, z):
    return x - ORIGIN[0], y - ORIGIN[1], z - ORIGIN[2]


def setb(x, y, z, b):
    i, j, k = idx(x, y, z)
    if 0 <= i < NX and 0 <= j < NY and 0 <= k < NZ:
        W[i, j, k] = b


def getb(x, y, z):
    i, j, k = idx(x, y, z)
    if 0 <= i < NX and 0 <= j < NY and 0 <= k < NZ:
        return W[i, j, k]
    return 0


def fill(x0, x1, y0, y1, z0, z1, b):
    """Rellena el prisma [x0,x1] x [y0,y1] x [z0,z1] (inclusive)."""
    i0, j0, k0 = idx(x0, y0, z0)
    i1, j1, k1 = idx(x1, y1, z1)
    W[max(i0, 0):min(i1 + 1, NX), max(j0, 0):min(j1 + 1, NY), max(k0, 0):min(k1 + 1, NZ)] = b


# ------------------------------------------------------------------ terreno
xs = np.arange(NX) + ORIGIN[0]
ys = np.arange(NY) + ORIGIN[1]
XX, YY = np.meshgrid(xs, ys, indexing="ij")
RR = np.hypot(XX, YY * 0.9)
n1 = ndimage.gaussian_filter(rng.standard_normal((NX, NY)), 9)
n1 /= n1.std()
n2 = ndimage.gaussian_filter(rng.standard_normal((NX, NY)), 3)
n2 /= n2.std()
hills = np.clip((RR - 46) / 30, 0, 1) ** 1.4 * (9 + 4 * n1)          # colinas que rodean el valle
height = G + np.where(RR > 42, hills + 0.8 * n2 * np.clip((RR - 42) / 10, 0, 1), 0)
# detrás del poblado (norte) las colinas son más bajas para no tapar la luna
height = np.where(YY > 30, G + (height - G) * 0.55, height)
# valle por donde entra la calle principal (sur)
corr = np.clip((np.abs(XX) - 7) / 16, 0, 1)
corr = np.where(YY < -30, corr, 1.0) * 1.0 + np.where(YY < -30, 0, 0)
height = G + (height - G) * np.where(YY < -30, corr, 1.0)
height = np.round(height).astype(int)
height = np.clip(height, 2, 30)
for i in range(NX):
    for j in range(NY):
        h = height[i, j]
        W[i, j, :max(h - 4, 0)] = STONE
        W[i, j, max(h - 4, 0):h - 1] = DIRT
        W[i, j, h - 1] = GRASS
# rocas que asoman en las colinas
rock = (n2 > 2.0) & (RR > 52)
for i, j in zip(*np.nonzero(rock)):
    h = height[i, j]
    W[i, j, h - 1] = STONE


def ground(x, y):
    i, j, _ = idx(x, y, 0)
    return int(height[i, j])


# ------------------------------------------------------------------ estanque (sureste)
PX, PY, PR = 30, -26, 10
for x in range(PX - PR - 3, PX + PR + 4):
    for y in range(PY - PR - 3, PY + PR + 4):
        d = np.hypot((x - PX) / 1.25, y - PY)
        if d < PR:
            depth = 3 if d < PR - 2 else 2
            fill(x, x, y, y, G - depth, G - 1, WATER)
            fill(x, x, y, y, G - depth - 1, G - depth - 1, SAND)
        elif d < PR + 1.8:
            setb(x, y, G - 1, SAND)

# ------------------------------------------------------------------ plaza y calles
PLAZA_R = 11
for x in range(-PLAZA_R, PLAZA_R + 1):
    for y in range(-PLAZA_R, PLAZA_R + 1):
        d = np.hypot(x, y)
        if d <= PLAZA_R + 0.3:
            setb(x, y, G - 1, PLAZA if d < PLAZA_R - 1 else SBRICK)


def street(x0, y0, x1, y1, w=2):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for t in np.linspace(0, 1, n * 2):
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for dx in range(-w, w + 1):
            for dy in range(-w, w + 1):
                x, y = int(round(cx + dx)), int(round(cy + dy))
                if np.hypot(x, y) > PLAZA_R - 0.5 and getb(x, y, G - 1) not in (WATER, SAND):
                    setb(x, y, G - 1, PATH)


street(0, -PLAZA_R, 0, -78, 2)          # calle principal al sur (por donde entra la cámara)
street(-PLAZA_R, 0, -34, 0, 1)          # oeste hacia los campos
street(PLAZA_R, 0, 36, 2, 1)            # este
street(0, PLAZA_R, 0, 30, 1)            # norte
street(8, 8, 15, 18, 1)                 # a la pagoda

# ------------------------------------------------------------------ casas japonesas
def house(cx, cy, w, d, wall_h=4, door="s", lit_p=0.45, roof_extra=0):
    x0, x1 = cx - w // 2, cx + w // 2
    y0, y1 = cy - d // 2, cy + d // 2
    fill(x0, x1, y0, y1, G, G, SBRICK)                       # basamento
    fill(x0 + 1, x1 - 1, y0 + 1, y1 - 1, G, G, TATAMI)
    zb, zt = G + 1, G + wall_h
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            edge = x in (x0, x1) or y in (y0, y1)
            if not edge:
                continue
            corner = x in (x0, x1) and y in (y0, y1)
            post = corner or ((x - x0) % 3 == 0 and y in (y0, y1)) or ((y - y0) % 3 == 0 and x in (x0, x1))
            for z in range(zb, zt + 1):
                if z == zt:
                    setb(x, y, z, DWOOD)
                elif post:
                    setb(x, y, z, LACQ if corner else DWOOD)
                else:
                    lit = rng.random() < lit_p
                    setb(x, y, z, SHOJI_LIT if lit else SHOJI)
                    if lit and z == zb + 1:
                        lights.append((x, y, z, 3))
    # puerta (2 de alto) hacia la plaza
    if door == "s":
        dx, dy, ox, oy = cx, y0, 0, -1
    elif door == "n":
        dx, dy, ox, oy = cx, y1, 0, 1
    elif door == "e":
        dx, dy, ox, oy = x1, cy, 1, 0
    else:
        dx, dy, ox, oy = x0, cy, -1, 0
    for z in (zb, zb + 1):
        setb(dx, dy, z, AIR)
        setb(dx + (oy != 0), dy + (ox != 0), z, AIR)
    # farolillo junto a la puerta
    lx, ly = dx + ox - (oy != 0), dy + oy - (ox != 0)
    setb(lx, ly, zb + 2, LANTERN)
    lights.append((lx, ly, zb + 2, 0))
    # tejado a cuatro aguas con alero y esquinas levantadas
    z = zt + 1
    ex0, ex1, ey0, ey1 = x0 - 2, x1 + 2, y0 - 2, y1 + 2
    first = True
    while ex1 - ex0 >= 0 and ey1 - ey0 >= 0:
        for x in range(ex0, ex1 + 1):
            for y in range(ey0, ey1 + 1):
                if x in (ex0, ex1) or y in (ey0, ey1) or (ex1 - ex0 <= 2 or ey1 - ey0 <= 2):
                    setb(x, y, z, ROOF)
        if first:
            for x, y in ((ex0, ey0), (ex0, ey1), (ex1, ey0), (ex1, ey1)):
                setb(x, y, z + 1, ROOF)
            first = False
        ex0, ex1, ey0, ey1 = ex0 + 1, ex1 - 1, ey0 + 1, ey1 - 1
        z += 1
    # cumbrera
    if ex1 - ex0 < 0 or ey1 - ey0 < 0:
        pass
    return z


houses = [
    (-20, -5, 9, 7, 4, "e"), (-20, 9, 7, 7, 4, "e"), (-21, -20, 9, 7, 4, "e"),
    (20, -6, 9, 7, 4, "w"), (21, 9, 7, 9, 4, "w"),
    (-10, -24, 7, 7, 4, "e"), (10, -24, 7, 7, 4, "w"), (-10, -40, 7, 7, 3, "e"), (11, -42, 9, 7, 3, "w"),
    (-12, 21, 9, 7, 4, "s"), (-26, 26, 7, 7, 3, "s"), (31, 16, 7, 7, 3, "w"),
]
for h in houses:
    house(*h)

# ------------------------------------------------------------------ pagoda (noreste)
def pagoda(cx, cy, base=9, tiers=4):
    half = base // 2
    fill(cx - half - 1, cx + half + 1, cy - half - 1, cy + half + 1, G, G, SBRICK)
    fill(cx - half - 1, cx + half + 1, cy - half - 1, cy + half + 1, G + 1, G + 1, SBRICK)
    z = G + 2
    for t in range(tiers):
        hh = half - t
        wall = 3 if t == 0 else 2
        for x in range(cx - hh, cx + hh + 1):
            for y in range(cy - hh, cy + hh + 1):
                if x in (cx - hh, cx + hh) or y in (cy - hh, cy + hh):
                    for k in range(wall):
                        corner = x in (cx - hh, cx + hh) and y in (cy - hh, cy + hh)
                        post = corner or (x - cx) % 2 == 0 and (y - cy) % 2 == 0
                        setb(x, y, z + k, LACQ if post else SHOJI_LIT)
        lights.append((cx, cy - hh, z + 1, 3))
        z += wall
        # alero
        r = hh + 2
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                setb(x, y, z, ROOF)
        for x, y in ((cx - r, cy - r), (cx - r, cy + r), (cx + r, cy - r), (cx + r, cy + r)):
            setb(x, y, z + 1, ROOF)
        r -= 1
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                setb(x, y, z + 1, ROOF)
        fill(cx - hh + 1, cx + hh - 1, cy - hh + 1, cy + hh - 1, z + 1, z + 1, DWOOD)
        z += 2
    # aguja
    for k in range(6):
        setb(cx, cy, z + k, LACQ if k % 2 == 0 else SBRICK)
    setb(cx, cy, z + 6, LANTERN)
    lights.append((cx, cy, z + 6, 0))


pagoda(17, 21, 9, 4)

# ------------------------------------------------------------------ torii en la calle principal
def torii(cy, half=5, h=8):
    for x in (-half + 1, half - 1):
        fill(x, x, cy, cy, G, G + h - 1, LACQ)
        setb(x, cy, G, SBRICK)
    fill(-half + 1, half - 1, cy, cy, G + h - 3, G + h - 3, LACQ)       # nuki
    fill(-half - 1, half + 1, cy, cy, G + h, G + h, LACQ)               # kasagi
    fill(-half - 1, half + 1, cy, cy, G + h + 1, G + h + 1, DWOOD)
    for x in (-half - 1, half + 1):
        setb(x, cy, G + h + 2, DWOOD)                                    # puntas levantadas
    setb(0, cy, G + h - 2, LACQ)
    setb(0, cy, G + h - 1, LACQ)


torii(-34, 5, 8)
torii(-56, 5, 7)

# ------------------------------------------------------------------ hoguera en el centro
fill(-1, 1, -1, 1, G - 1, G - 1, COBBLE)
for x, y in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
    setb(x, y, G, COBBLE)
setb(0, 0, G, LOG)
lights.append((0, 0, G + 1.5, 2))

# ------------------------------------------------------------------ linternas de piedra
def stone_lantern(x, y):
    g = ground(x, y)
    setb(x, y, g, SBRICK)
    setb(x, y, g + 1, SLANTERN)
    setb(x, y, g + 2, COBBLE)
    lights.append((x, y, g + 1, 1))


for y in range(-70, -12, 9):
    stone_lantern(-4, y)
    stone_lantern(4, y)
for a in np.linspace(0, 2 * np.pi, 8, endpoint=False) + np.pi / 8:
    stone_lantern(int(round(12.5 * np.cos(a))), int(round(12.5 * np.sin(a))))

# ------------------------------------------------------------------ puente sobre el estanque
for x in range(PX - 13, PX + 14):
    t = (x - PX) / 13
    z = G + int(round(2.2 * (1 - t * t))) - 1
    for y in (PY - 1, PY, PY + 1):
        setb(x, y, z, PLANKS)
    for y in (PY - 2, PY + 2):
        setb(x, y, z + 1, LACQ if x % 3 == 0 else AIR)

# ------------------------------------------------------------------ campos (oeste)
for x in range(-46, -30):
    for y in range(-14, 14):
        if (y + 14) % 4 == 3:
            setb(x, y, G - 1, WATER)
        else:
            setb(x, y, G - 1, FARM)
            plants.append((x + 0.5, y + 0.5, G, 0))

# ------------------------------------------------------------------ árboles
def tree(x, y, kind="sakura", h=None):
    g = ground(x, y)
    if getb(x, y, g - 1) in (WATER, SAND, PATH, PLAZA, SBRICK, FARM):
        return
    h = h or int(rng.integers(5, 8))
    leaf = SAKURA if kind == "sakura" else LEAVES
    bx, by = x, y
    for k in range(h):
        setb(bx, by, g + k, LOG)
        if k == h // 2 and kind == "sakura":
            bx += int(rng.integers(-1, 2))
            by += int(rng.integers(-1, 2))
            setb(bx, by, g + k, LOG)
    top = g + h
    for _ in range(3 if kind == "sakura" else 2):
        cx = bx + rng.uniform(-2.2, 2.2)
        cy = by + rng.uniform(-2.2, 2.2)
        cz = top - 1 + rng.uniform(-0.5, 1.5)
        r = rng.uniform(2.6, 3.6) if kind == "sakura" else rng.uniform(2.4, 3.2)
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                for dz in range(-3, 4):
                    px, py, pz = int(round(cx + dx)), int(round(cy + dy)), int(round(cz + dz))
                    d = np.sqrt(((px - cx) / r) ** 2 + ((py - cy) / r) ** 2 + ((pz - cz) / (r * 0.75)) ** 2)
                    if d < 1.0 - rng.uniform(0, 0.18) and getb(px, py, pz) == AIR:
                        setb(px, py, pz, leaf)


sakuras = [(-14, -11), (14, -12), (-15, 12), (6, 15), (-7, 14), (-27, -12), (26, -16), (-5, -48),
           (6, -50), (-8, -63), (7, -66), (40, -16), (20, -36), (-30, 14), (-36, -22), (25, 0),
           (-3, 35), (9, 34)]
for x, y in sakuras:
    tree(x, y, "sakura")
for _ in range(170):
    a = rng.uniform(0, 2 * np.pi)
    r = rng.uniform(44, 122)
    x, y = int(r * np.cos(a)), int(r * np.sin(a) / 0.9)
    if y > 25 and abs(x) < 30:
        continue               # deja libre la vista hacia la luna
    tree(x, y, "green" if rng.random() < 0.7 else "sakura", int(rng.integers(5, 9)))

# ------------------------------------------------------------------ flores
for _ in range(500):
    x, y = int(rng.integers(-60, 60)), int(rng.integers(-75, 50))
    g = ground(x, y)
    if getb(x, y, g - 1) == GRASS and getb(x, y, g) == AIR and np.hypot(x, y) > 13:
        plants.append((x + 0.5, y + 0.5, g, 1))

# ------------------------------------------------------------------ luz de bloques y luz del cielo (estilo Minecraft)
TRANSP = np.isin(W, [AIR, SAKURA, LEAVES, WATER])
SOFT = np.isin(W, [SAKURA, LEAVES, WATER])           # atenúan un nivel extra
blk = np.zeros(W.shape, np.int16)
blk[W == LANTERN] = 15
blk[W == SLANTERN] = 14
blk[W == SHOJI_LIT] = 11
fi, fj, fk = idx(0, 0, G + 1)
blk[fi, fj, fk] = 15                                   # hoguera
src = blk.copy()


def propagate(L, iters=15):
    for _ in range(iters):
        nb = np.zeros_like(L)
        for ax in range(3):
            for sh in (1, -1):
                r = np.roll(L, sh, axis=ax)
                sl = [slice(None)] * 3
                sl[ax] = 0 if sh == 1 else -1
                r[tuple(sl)] = 0
                np.maximum(nb, r, out=nb)
        nb = nb - 1 - SOFT
        L = np.where(TRANSP, np.maximum(L, nb), L)
        L = np.maximum(L, src_cur)
    return L


src_cur = src
blk = np.clip(propagate(blk), 0, 15)
# luz del cielo: 15 sobre el primer bloque opaco de cada columna, luego se difunde
opaque = ~TRANSP
below = np.cumsum(opaque[:, :, ::-1], axis=2)[:, :, ::-1] > 0   # hay algo opaco en o por encima
sky = np.where(~below, 15, 0).astype(np.int16)
src_cur = sky.copy()
sky = np.clip(propagate(sky), 0, 15)
light = np.stack([blk, sky], -1).astype(np.uint8) * 17   # 0..255
np.savez_compressed(os.path.join(OUT, "world.npz"), W=W, origin=ORIGIN, plants=np.array(plants, np.float32),
                    lights=np.array(lights, np.float32), ground=np.array([G]), light=light)
print("bloques", int((W > 0).sum()), "plantas", len(plants), "luces", len(lights))

# mapa cenital de control
pal = np.array([[0, 0, 0], [90, 190, 90], [130, 80, 50], [120, 120, 150], [100, 100, 140], [200, 170, 130],
                [130, 100, 180], [140, 150, 180], [210, 140, 70], [200, 40, 60], [80, 50, 75], [110, 70, 50],
                [235, 230, 245], [255, 230, 170], [50, 90, 150], [245, 150, 190], [50, 160, 100],
                [50, 130, 230], [240, 220, 160], [100, 60, 40], [255, 90, 70], [255, 190, 100], [190, 200, 110]],
               np.uint8)
top = np.zeros((NX, NY), np.uint8)
for k in range(NZ):
    m = W[:, :, k] > 0
    top[m] = W[:, :, k][m]
Image.fromarray(pal[top].transpose(1, 0, 2)[::-1]).resize((NX * 4, NY * 4), Image.NEAREST).save(
    os.path.join(OUT, "_map.png"))
