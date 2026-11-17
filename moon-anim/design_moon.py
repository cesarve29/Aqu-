"""Genera la geometría (malla inflada) y las texturas pintadas de la luna.

Coordenadas normalizadas: radio exterior = 1, centro en el origen, Y hacia arriba.
Salida en assets/: moon_mesh.npz, moon_albedo.png, moon_bump.png, preview.png
"""
import os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import Delaunay
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
os.makedirs(OUT, exist_ok=True)

N = 4096          # resolución de máscaras/texturas
L = 1.1           # la textura cubre [-L, L]^2
PIX = 2 * L / N
rng = np.random.default_rng(7)

ys, xs = np.mgrid[0:N, 0:N]
X = (xs + 0.5) * PIX - L
Y = L - (ys + 0.5) * PIX
R = np.hypot(X, Y)


def to_px(p):
    return ((p[0] + L) / PIX, (L - p[1]) / PIX)


def catmull(pts, n=24):
    """Curva Catmull-Rom abierta que pasa por todos los puntos."""
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts
    P = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)


def path(segments):
    """Une segmentos suavizados; las uniones entre segmentos son esquinas."""
    out = []
    for s in segments:
        c = catmull(s)
        out.extend(c[:-1] if out is not None else c)
    return np.array(out)


def closed_smooth(pts, n=24):
    pts = list(pts)
    c = catmull(pts[-2:] + pts + pts[:2], n)
    return c[2 * n:-2 * n]


def mask_from_poly(poly):
    im = Image.new("L", (N, N), 0)
    ImageDraw.Draw(im).polygon([to_px(p) for p in poly], fill=255)
    return np.array(im) > 127


def sdf(mask):
    """Distancia con signo (positiva dentro) en unidades normalizadas."""
    return (ndimage.distance_transform_edt(mask) - ndimage.distance_transform_edt(~mask)) * PIX


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def round_profile(d, w):
    t = np.clip(d / w, 0, 1)
    return np.sqrt(np.clip(1 - (1 - t) ** 2, 0, 1))


# ---------------------------------------------------------------- silueta
dark_poly = path([
    [(1.6, 0.62), (1.6, 0.69), (0.76, 0.69)],
    [(0.76, 0.69), (0.644, 0.752), (0.536, 0.813), (0.40, 0.851), (0.22, 0.86), (-0.03, 0.836),
     (-0.18, 0.757), (-0.30, 0.577), (-0.325, 0.35), (-0.305, 0.17), (-0.265, 0.088),
     (-0.20, 0.066), (0.20, 0.252), (0.68, 0.475)],
    [(0.68, 0.475), (0.31, 0.214), (0.04, -0.012), (-0.06, -0.13), (-0.09, -0.195)],
    [(-0.09, -0.195), (0.0, -0.222), (0.063, -0.245)],
    [(0.063, -0.245), (0.058, -0.29), (0.097, -0.33), (0.176, -0.36), (0.232, -0.352)],
    [(0.232, -0.352), (0.29, -0.31), (0.322, -0.288)],
    [(0.322, -0.288), (0.343, -0.355), (0.375, -0.393), (0.446, -0.39), (0.536, -0.336),
     (0.671, -0.234), (0.784, -0.099), (0.851, 0.081), (0.874, 0.284), (0.869, 0.491),
     (0.855, 0.62)],
    [(0.855, 0.62), (1.6, 0.62)],
])
disk = R <= 1.0
dark = mask_from_poly(dark_poly)
sil = disk & ~dark
sil = ndimage.binary_opening(sil, iterations=2)
d_sil = sdf(sil)

# ---------------------------------------------------------------- rasgos
EYE_C = np.array([-0.601, -0.016])
EYE_R = 0.185
d_eye = np.hypot(X - EYE_C[0], Y - EYE_C[1]) - EYE_R

cheek_poly = closed_smooth([(-0.80, -0.27), (-0.62, -0.205), (-0.42, -0.168), (-0.22, -0.178),
                            (-0.08, -0.20), (0.063, -0.245), (0.03, -0.30), (-0.06, -0.35),
                            (-0.14, -0.38), (-0.365, -0.398), (-0.59, -0.352), (-0.74, -0.305)])
d_cheek = sdf(mask_from_poly(cheek_poly))

teeth_poly = closed_smooth([(-0.76, -0.30), (-0.5, -0.30), (-0.2, -0.30), (0.04, -0.27),
                            (0.12, -0.33), (0.235, -0.352), (0.30, -0.40), (0.30, -0.47),
                            (0.24, -0.595), (0.13, -0.705), (0.0, -0.762), (-0.185, -0.775),
                            (-0.41, -0.708), (-0.59, -0.552), (-0.70, -0.415)])
d_teeth = sdf(mask_from_poly(teeth_poly) & sil)

fold_poly = closed_smooth([(0.322, -0.288), (0.352, -0.37), (0.34, -0.49), (0.285, -0.62),
                           (0.19, -0.735), (0.155, -0.712), (0.235, -0.60), (0.28, -0.48),
                           (0.29, -0.38), (0.298, -0.315)])
d_fold = sdf(mask_from_poly(fold_poly))

# líneas de los dientes ------------------------------------------------
mid_line = catmull([(-0.70, -0.47), (-0.646, -0.527), (-0.455, -0.606), (-0.23, -0.64),
                    (-0.027, -0.606), (0.13, -0.527), (0.22, -0.437), (0.27, -0.37)], 40)


def mid_y(x):
    return np.interp(x, mid_line[:, 0], mid_line[:, 1])


tooth_lines = [mid_line]
for x in [-0.60, -0.36, -0.14, 0.02, 0.13, 0.215]:      # fila superior
    yb = mid_y(x)
    bow = 0.018 * np.sign(x + 0.1)
    tooth_lines.append(catmull([(x - 0.02 * x - 0.01, -0.27), (x + bow, (yb - 0.27) / 2 - 0.01),
                                (x, yb)], 20))
for x in [-0.52, -0.30, -0.07, 0.09, 0.20]:              # fila inferior
    yt = mid_y(x)
    bow = 0.02 * np.sign(x + 0.15)
    tooth_lines.append(catmull([(x, yt), (x + bow, yt - 0.09), (x + 0.06 * x, -0.86)], 20))

line_img = Image.new("L", (N, N), 0)
dl = ImageDraw.Draw(line_img)
for ln in tooth_lines:
    dl.line([to_px(p) for p in ln], fill=255, width=3)
d_tline = ndimage.distance_transform_edt(~(np.array(line_img) > 127)) * PIX

# cráteres -------------------------------------------------------------
craters = []
def add_crater(cx, cy, r):
    craters.append((cx, cy, r))
# borde izquierdo (como la referencia)
for a in np.linspace(140, 230, 9):
    rr = rng.uniform(0.87, 0.94)
    add_crater(rr * np.cos(np.radians(a)), rr * np.sin(np.radians(a)), rng.uniform(0.025, 0.05))
# borde inferior derecho
for a in np.linspace(-95, -20, 9):
    rr = rng.uniform(0.84, 0.93)
    add_crater(rr * np.cos(np.radians(a)), rr * np.sin(np.radians(a)), rng.uniform(0.022, 0.05))
# dispersos por el resto
for _ in range(14):
    a = rng.uniform(0, 2 * np.pi)
    rr = np.sqrt(rng.uniform(0.2, 0.92))
    cx, cy = rr * np.cos(a), rr * np.sin(a)
    add_crater(cx, cy, rng.uniform(0.012, 0.03))

crater_h = np.zeros((N, N), np.float32)
crater_ring = np.zeros((N, N), np.float32)
crater_in = np.zeros((N, N), np.float32)
for cx, cy, r in craters:
    x0, x1 = int((cx - 2 * r + L) / PIX), int((cx + 2 * r + L) / PIX)
    y0, y1 = int((L - cy - 2 * r) / PIX), int((L - cy + 2 * r) / PIX)
    sl = (slice(max(y0, 0), min(y1, N)), slice(max(x0, 0), min(x1, N)))
    ex = 1.0 + rng.uniform(-0.25, 0.25)
    dd = np.hypot((X[sl] - cx) * ex, (Y[sl] - cy) / ex) / r
    bowl = -(1 - np.clip(dd, 0, 1) ** 2)
    rim = np.exp(-((dd - 1.0) / 0.22) ** 2)
    crater_h[sl] += bowl * 0.6 + rim * 0.35
    crater_ring[sl] = np.maximum(crater_ring[sl], rim)
    crater_in[sl] = np.maximum(crater_in[sl], (dd < 1) * (1 - dd))

face_zone = (d_teeth > -0.05) | (d_cheek > -0.05) | (d_eye < 0.06) | (d_fold > -0.04)
fz = ndimage.gaussian_filter(face_zone.astype(np.float32), 20)
crater_h *= 1 - fz
crater_ring *= 1 - fz
crater_in *= 1 - fz

# ---------------------------------------------------------------- altura (malla)
dome = 0.12 + 0.16 * np.clip(1 - R ** 2, 0, 1)
H = round_profile(d_sil, 0.11) * dome
H += 0.045 * round_profile(d_cheek, 0.05) * (d_sil > 0)
H += 0.035 * round_profile(d_fold, 0.03) * (d_sil > 0)
teeth_in = smoothstep(0.0, 0.035, d_teeth) * (1 - smoothstep(-0.02, 0.0, d_cheek))
H -= 0.03 * teeth_in
H += 0.022 * np.exp(-((d_eye - 0.012) / 0.03) ** 2) * (d_sil > 0)
H = np.where(d_sil > 0, H, 0).astype(np.float32)

# ---------------------------------------------------------------- bump (detalle fino)
noise = ndimage.gaussian_filter(rng.standard_normal((N, N)).astype(np.float32), 6)
noise /= noise.std()
noise2 = ndimage.gaussian_filter(rng.standard_normal((N, N)).astype(np.float32), 30)
noise2 /= noise2.std()
groove = np.exp(-(d_tline / 0.006) ** 2) * (d_teeth > 0) * (d_cheek < 0)
bump = 0.5 + 0.07 * crater_h - 0.20 * groove + 0.003 * noise + 0.004 * noise2
bump = np.clip(bump, 0, 1)

# ---------------------------------------------------------------- albedo pintado
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


center_col = hexc("#FFF8DA")
edge_col = hexc("#F4D47A")
t_edge = np.clip(1 - smoothstep(0.0, 0.09, d_sil) * 0.8 - 0.1 * R ** 3, 0, 1) * 0.85
alb = lerp(center_col[None, None], edge_col[None, None], t_edge)
alb *= (1 + 0.012 * noise2)[..., None]
# cráteres
alb = lerp(alb, hexc("#D8A94C")[None, None], np.clip(crater_ring * 0.25, 0, 1))
alb = lerp(alb, hexc("#EBCB7A")[None, None], np.clip(crater_in * 0.4, 0, 1))
# dientes
teeth_m = smoothstep(-0.002, 0.004, d_teeth)
teeth_col = lerp(hexc("#FFFDF4")[None, None], hexc("#EFE0C2")[None, None],
                 np.clip(1 - smoothstep(0.0, 0.08, -d_cheek) + 1 - smoothstep(0.0, 0.06, d_teeth), 0, 1))
alb = lerp(alb, teeth_col, teeth_m)
line_m = np.exp(-(d_tline / 0.0045) ** 2) * teeth_m * (1 - smoothstep(-0.01, 0.0, d_cheek))
alb = lerp(alb, hexc("#B98455")[None, None], np.clip(line_m * 0.9, 0, 1))
# contornos suaves de los rasgos (línea de dibujo ocre)
def ink(d, w, s):
    return np.exp(-(d / w) ** 2) * s
outline = np.maximum.reduce([
    ink(d_cheek, 0.005, 0.75) * (Y < -0.24),
    ink(d_fold, 0.005, 0.7),
    ink(d_teeth, 0.006, 0.8) * (d_cheek < -0.004),
    ink(d_eye + 0.004, 0.006, 0.55),
])
outline *= (d_sil > 0.003)
alb = lerp(alb, hexc("#B88A45")[None, None], np.clip(outline, 0, 1))
# sombra suave bajo el pómulo y alrededor del ojo
shade = 0.35 * np.exp(-((-d_cheek - 0.02) / 0.03) ** 2) * (d_cheek < 0) * (Y > -0.32) * (Y < -0.15)
shade += 0.25 * np.exp(-((d_eye - 0.04) / 0.03) ** 2)
alb = lerp(alb, hexc("#E2B95A")[None, None], np.clip(shade * (1 - teeth_m), 0, 1))
alb = np.clip(alb, 0, 1)
# fuera de la silueta: color de borde (evita halos al filtrar)
alb[d_sil < 0] = edge_col

Image.fromarray((alb * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "moon_albedo.png"))
Image.fromarray((bump * 65535).astype(np.uint16)).save(os.path.join(OUT, "moon_bump.png"))
# máscara de dientes (para un material más brillante) en canal propio
Image.fromarray((teeth_m * 255).astype(np.uint8)).save(os.path.join(OUT, "moon_teeth_mask.png"))

# ---------------------------------------------------------------- malla
def sample(img, px, py):
    cols = (px + L) / PIX - 0.5
    rows = (L - py) / PIX - 0.5
    return ndimage.map_coordinates(img, [rows, cols], order=1, mode="nearest")


contours = measure.find_contours(d_sil, 0.0)
bpts = []
SPACING = 0.0065
for c in contours:
    if len(c) < 20:
        continue
    px = (c[:, 1] + 0.5) * PIX - L
    py = L - (c[:, 0] + 0.5) * PIX
    seg = np.hypot(np.diff(px), np.diff(py))
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(int(s[-1] / (SPACING * 0.85)), 8)
    ss = np.linspace(0, s[-1], n, endpoint=False)
    bpts.append(np.stack([np.interp(ss, s, px), np.interp(ss, s, py)], 1))
bpts = np.concatenate(bpts)

h = SPACING
gy = np.arange(-1.0, 1.0, h * 0.866)
ipts = []
for j, yv in enumerate(gy):
    xv = np.arange(-1.0, 1.0, h) + (h / 2 if j % 2 else 0)
    ipts.append(np.stack([xv, np.full_like(xv, yv)], 1))
ipts = np.concatenate(ipts)
ipts += rng.uniform(-h * 0.05, h * 0.05, ipts.shape)
din = sample(d_sil, ipts[:, 0], ipts[:, 1])
ipts = ipts[din > h * 0.7]

pts = np.concatenate([bpts, ipts])
tri = Delaunay(pts)
F = tri.simplices
cen = pts[F].mean(1)
keep = sample(d_sil, cen[:, 0], cen[:, 1]) > 0
F = F[keep]
# orientación CCW (normal +Z)
a, b, c = pts[F[:, 0]], pts[F[:, 1]], pts[F[:, 2]]
cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
F[cross < 0] = F[cross < 0][:, ::-1]
used = np.unique(F)
remap = -np.ones(len(pts), int)
remap[used] = np.arange(len(used))
pts = pts[used]
F = remap[F]
nb = int(np.sum(used < len(bpts)))

hz = sample(H, pts[:, 0], pts[:, 1])
hz[:nb] = 0.0
front = np.column_stack([pts, hz])
back = np.column_stack([pts[nb:], -hz[nb:] * 0.6])
V = np.vstack([front, back])
bmap = np.concatenate([np.arange(nb), len(pts) + np.arange(len(pts) - nb)])
Fb = bmap[F][:, ::-1]
FF = np.vstack([F, Fb])
np.savez_compressed(os.path.join(OUT, "moon_mesh.npz"), V=V.astype(np.float32), F=FF.astype(np.int32),
                    eye=np.array([EYE_C[0], EYE_C[1], EYE_R,
                                  float(sample(H, np.array([EYE_C[0]]), np.array([EYE_C[1]]))[0])]),
                    L=np.array([L]))
print("verts", len(V), "faces", len(FF), "boundary", nb)

# ---------------------------------------------------------------- preview vs referencia
ref = Image.open("/root/.claude/uploads/c72e5fec-7855-5826-8e0c-9f7e65553794/5090cae3-image.webp").convert("RGB")
cx, cy, rr = 962, 536, 444
ref = ref.crop((int(cx - L * rr), int(cy - L * rr), int(cx + L * rr), int(cy + L * rr))).resize((800, 800))
shade_prev = np.clip(0.55 + 0.45 * np.gradient(ndimage.gaussian_filter(H, 3), axis=0) / PIX * -0.6
                     + 0.25 * np.gradient(ndimage.gaussian_filter(H, 3), axis=1) / PIX * -0.6, 0.3, 1.3)
prev = alb * shade_prev[..., None]
prev[d_sil < 0] = hexc("#163a5a")
ey = np.hypot(X - EYE_C[0], Y - EYE_C[1]) < EYE_R
prev[ey] = hexc("#0f3b40")
pv = Image.fromarray((np.clip(prev, 0, 1) * 255).astype(np.uint8)).resize((800, 800))
both = Image.new("RGB", (1600, 800))
both.paste(ref, (0, 0)); both.paste(pv, (800, 0))
both.save(os.path.join(HERE, "..", "moon-anim", "assets", "preview.png"))
