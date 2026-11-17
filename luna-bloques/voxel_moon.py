"""Voxeliza la luna sonriente de la referencia (silueta, ojo, nariz en punta y dientes).

Salida: assets/moon_vox.npz con
  occ  (nx, ny, nz) bool      ocupación de vóxeles (x a la derecha, y arriba, z hacia la cámara)
  col  (nx, ny, nz, 3) float  color por vóxel
  mat  (nx, ny, nz) uint8     0 = luna, 1 = ojo (cristal), 2 = brillo del ojo
  vox  tamaño del vóxel en unidades normalizadas (radio de la luna = 1)
"""
import os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
rng = np.random.default_rng(7)

N = 1024
L = 1.1
PIX = 2 * L / N
ys, xs = np.mgrid[0:N, 0:N]
X = (xs + 0.5) * PIX - L
Y = L - (ys + 0.5) * PIX
R = np.hypot(X, Y)


def to_px(p, n=N, l=L):
    pix = 2 * l / n
    return ((p[0] + l) / pix, (l - p[1]) / pix)


def catmull(pts, n=24):
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
    out = []
    for s in segments:
        out.extend(catmull(s)[:-1])
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
    return (ndimage.distance_transform_edt(mask) - ndimage.distance_transform_edt(~mask)) * PIX


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def round_profile(d, w):
    t = np.clip(d / w, 0, 1)
    return np.sqrt(np.clip(1 - (1 - t) ** 2, 0, 1))


# ------------------------------------------------------------------ silueta y rasgos (como la referencia)
dark_poly = path([
    [(1.6, 0.62), (1.6, 0.69), (0.76, 0.69)],
    [(0.76, 0.69), (0.644, 0.752), (0.536, 0.813), (0.40, 0.851), (0.22, 0.86), (-0.03, 0.836),
     (-0.18, 0.757), (-0.30, 0.577), (-0.325, 0.35), (-0.305, 0.17), (-0.265, 0.088),
     (-0.19, 0.035), (-0.12, -0.03), (-0.09, -0.11), (-0.09, -0.195)],
    [(-0.09, -0.195), (0.0, -0.222), (0.063, -0.245)],
    [(0.063, -0.245), (0.058, -0.29), (0.097, -0.33), (0.176, -0.36), (0.232, -0.352)],
    [(0.232, -0.352), (0.29, -0.31), (0.322, -0.288)],
    [(0.322, -0.288), (0.343, -0.355), (0.375, -0.393), (0.446, -0.39), (0.536, -0.336),
     (0.671, -0.234), (0.784, -0.099), (0.851, 0.081), (0.874, 0.284), (0.869, 0.491),
     (0.855, 0.62)],
    [(0.855, 0.62), (1.6, 0.62)],
])
sil = (R <= 1.0) & ~mask_from_poly(dark_poly)
sil = ndimage.binary_opening(sil, iterations=2)
d_sil = sdf(sil)

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

mid_line = catmull([(-0.70, -0.47), (-0.646, -0.527), (-0.455, -0.606), (-0.23, -0.64),
                    (-0.027, -0.606), (0.13, -0.527), (0.22, -0.437), (0.27, -0.37)], 40)


def mid_y(x):
    return np.interp(x, mid_line[:, 0], mid_line[:, 1])


tooth_lines = [mid_line]
for x in [-0.60, -0.36, -0.14, 0.02, 0.13, 0.215]:
    yb = mid_y(x)
    bow = 0.018 * np.sign(x + 0.1)
    tooth_lines.append(catmull([(x - 0.02 * x - 0.01, -0.27), (x + bow, (yb - 0.27) / 2 - 0.01), (x, yb)], 20))
for x in [-0.52, -0.30, -0.07, 0.09, 0.20]:
    yt = mid_y(x)
    bow = 0.02 * np.sign(x + 0.15)
    tooth_lines.append(catmull([(x, yt), (x + bow, yt - 0.09), (x + 0.06 * x, -0.86)], 20))

# ------------------------------------------------------------------ alturas (como la versión 3D)
SPH = 0.78 * np.sqrt(np.clip(1 - R ** 2, 0, 1))
BASE = SPH * round_profile(d_sil, 0.13)
fe = round_profile(d_sil, 0.035)
H = BASE.copy()
H += 0.07 * round_profile(d_cheek, 0.06) * fe
H += 0.06 * round_profile(d_fold, 0.035) * fe
teeth_in = smoothstep(0.0, 0.03, d_teeth) * (1 - smoothstep(-0.02, 0.0, d_cheek))
H -= 0.06 * teeth_in * fe
H -= 0.10 * smoothstep(0.0, -0.03, d_eye) * fe
H += 0.035 * np.exp(-((d_eye - 0.015) / 0.025) ** 2) * fe

# ------------------------------------------------------------------ rejilla de vóxeles
G = 84                       # vóxeles a lo ancho de [-L, L]
VOX = 2 * L / G
gc = (np.arange(G) + 0.5) * VOX - L            # centros
GX, GY = np.meshgrid(gc, gc[::-1])             # fila 0 = arriba


def samp(img):
    cols = (GX + L) / PIX - 0.5
    rows = (L - GY) / PIX - 0.5
    return ndimage.map_coordinates(img.astype(np.float32), [rows, cols], order=1, mode="nearest")


sil_v = samp(sil) > 0.5
Hf = samp(H)
Hb = samp(BASE)
dch, dte, dfo, dey = samp(d_cheek), samp(d_teeth), samp(d_fold), samp(d_eye)
Rv = np.hypot(GX, GY)

NZ = int(np.ceil(1.0 / VOX)) * 2 + 4
zc = (np.arange(NZ) - NZ / 2 + 0.5) * VOX
occ = np.zeros((G, G, NZ), bool)      # [x, y, z] con y hacia arriba
front = np.zeros((G, G), int)
for i in range(G):          # columna x
    for j in range(G):      # fila (y de arriba a abajo)
        if not sil_v[j, i]:
            continue
        zf, zb = Hf[j, i], Hb[j, i]
        k = (zc <= max(zf, VOX * 0.6)) & (zc >= -max(zb, VOX * 0.6))
        occ[i, G - 1 - j, k] = True
        front[j, i] = np.nonzero(k)[0].max()

# ------------------------------------------------------------------ colores (paleta pixel-art)
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


C_CENTER, C_MID, C_EDGE = hexc("#FFF6D2"), hexc("#FBE7A6"), hexc("#F2CC6E")
C_CRATER, C_CRATER_IN = hexc("#D7A84E"), hexc("#EBC977")
C_TEETH, C_TEETH_SH = hexc("#FFFDF6"), hexc("#EEDDBE")
C_LINE, C_INK = hexc("#B07A4A"), hexc("#B88A45")
C_EYE, C_EYE_RIM = hexc("#0E4A50"), hexc("#3E8C8A")

face_col = np.zeros((G, G, 3), np.float32)
t_edge = np.clip(1 - samp(smoothstep(0.0, 0.10, d_sil)), 0, 1)
face_col[:] = C_CENTER
face_col[t_edge > 0.25] = C_MID
face_col[(t_edge > 0.6) | (Rv > 0.9)] = C_EDGE
# variación tipo "bloque" (ruido por vóxel muy suave)
face_col *= (1 + 0.025 * rng.standard_normal((G, G)))[..., None]

# cráteres a resolución de vóxel
face_zone = (dte > -0.06) | (dch > -0.06) | (dey < 0.08) | (dfo > -0.05)
for a in list(np.linspace(140, 230, 7)) + list(np.linspace(-95, -20, 7)):
    rr = rng.uniform(0.84, 0.92)
    cx, cy, r = rr * np.cos(np.radians(a)), rr * np.sin(np.radians(a)), rng.uniform(0.035, 0.06)
    d = np.hypot(GX - cx, GY - cy) / r
    ring = (d > 0.6) & (d < 1.15) & ~face_zone
    face_col[ring] = C_CRATER
    face_col[(d <= 0.6) & ~face_zone] = C_CRATER_IN
for _ in range(10):
    a = rng.uniform(0, 2 * np.pi)
    rr = np.sqrt(rng.uniform(0.15, 0.8))
    cx, cy, r = rr * np.cos(a), rr * np.sin(a), rng.uniform(0.025, 0.04)
    d = np.hypot(GX - cx, GY - cy) / r
    face_col[(d > 0.55) & (d < 1.1) & ~face_zone] = C_CRATER

# dientes
teeth_m = (dte > 0) & (dch < 0)
face_col[teeth_m] = C_TEETH
face_col[teeth_m & (dch > -0.07)] = C_TEETH_SH
line_img = Image.new("L", (G, G), 0)
dl = ImageDraw.Draw(line_img)
for ln in tooth_lines:
    dl.line([to_px(p, G) for p in ln], fill=255, width=1)
lines_v = (np.array(line_img) > 127) & teeth_m
face_col[lines_v] = C_LINE


def edge_of(m):
    return m & ~ndimage.binary_erosion(m, border_value=0)


ink = (edge_of(dch > 0) & (GY < -0.2)) | edge_of(dfo > 0) | (edge_of(dte > 0) & (dch < 0))
face_col[ink & sil_v] = C_INK

# ------------------------------------------------------------------ volumen de color y materiales
col = np.zeros((G, G, NZ, 3), np.float32)
mat = np.zeros((G, G, NZ), np.uint8)
side = C_EDGE * 0.97
for i in range(G):
    for j in range(G):
        if not sil_v[j, i]:
            continue
        yi = G - 1 - j
        col[i, yi, :] = side
        kf = front[j, i]
        col[i, yi, max(kf - 1, 0):kf + 1] = face_col[j, i]   # capa frontal con el dibujo

# ojo: esfera de cristal que sobresale de la cuenca
eye_in = dey < 0
eye_rad = EYE_R
base_eye_z = float(samp(BASE)[np.unravel_index(np.argmin(dey), dey.shape)])
ex, ey = EYE_C
for i in range(G):
    for j in range(G):
        if dey[j, i] > 0.012:
            continue
        x, y = GX[j, i], GY[j, i]
        yi = G - 1 - j
        rr2 = eye_rad ** 2 - (x - ex) ** 2 - (y - ey) ** 2
        zt = base_eye_z - 0.10 + np.sqrt(max(rr2, 0)) * 0.85
        k = zc <= zt
        k &= zc >= -max(Hb[j, i], VOX)
        occ[i, yi, :] = occ[i, yi, :] | k
        kk = np.nonzero(k)[0]
        if len(kk):
            top = kk.max()
            rim = dey[j, i] > -0.03
            col[i, yi, top - 1:top + 1] = C_EYE_RIM if rim else C_EYE
            mat[i, yi, top - 2:top + 1] = 1
# brillo del ojo (como la referencia: punto blanco algo arriba a la derecha del centro)
for (hx, hy, s) in ((0.035, 0.03, 0.035), (-0.07, -0.06, 0.018)):
    d = np.hypot(GX - (ex + hx), GY - (ey + hy))
    for j, i in zip(*np.nonzero(d < s + VOX * 0.5)):
        yi = G - 1 - j
        kk = np.nonzero(occ[i, yi])[0]
        if len(kk):
            mat[i, yi, kk.max()] = 2
            col[i, yi, kk.max()] = 1.0

# ------------------------------------------------------------------ nariz (cono voxelizado)
B = np.array([-0.155, -0.062])
Tp = np.array([0.68, 0.475])
zB = float(ndimage.map_coordinates(BASE, [[(L - B[1]) / PIX], [(B[0] + L) / PIX]], order=1)[0]) - 0.06
zT = 0.80
A3 = np.array([B[0], B[1], zB])
B3 = np.array([Tp[0], Tp[1], zT])
ax = B3 - A3
Lax = np.linalg.norm(ax)
axn = ax / Lax
XX, YY, ZZ = np.meshgrid(gc, gc, zc, indexing="ij")
P = np.stack([XX - A3[0], YY - A3[1], ZZ - A3[2]], -1)
t = (P @ axn) / Lax
perp = P - (t * Lax)[..., None] * axn
pd = np.linalg.norm(perp, axis=-1)
rad = 0.13 * np.clip(1 - t, 0, 1) ** 1.05 + 0.012
nose = (t > -0.15) & (t < 1.0) & (pd < rad)
occ |= nose
col[nose] = C_CENTER
# sombreado del lado inferior de la nariz (pintado, estilo anime)
under = nose & (perp[..., 1] < -rad * 0.35)
col[under] = C_MID
mat[nose] = 0

# no dejar luna detrás del cuerpo en la zona oscura (el occ ya lo respeta)
np.savez_compressed(os.path.join(OUT, "moon_vox.npz"), occ=occ, col=col.astype(np.float16),
                    mat=mat, vox=np.array([VOX]))
print("voxels", int(occ.sum()), "grid", occ.shape)

# vista previa frontal (proyección del vóxel más cercano)
img = np.zeros((G, G, 3), np.float32) + hexc("#1A2A5A")
for i in range(G):
    for yi in range(G):
        kk = np.nonzero(occ[i, yi])[0]
        if len(kk):
            k = kk.max()
            c = col[i, yi, k]
            img[G - 1 - yi, i] = c * (0.75 + 0.25 * (k / NZ))
Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((G * 8, G * 8), Image.NEAREST).save(
    os.path.join(OUT, "_moon_vox_preview.png"))
