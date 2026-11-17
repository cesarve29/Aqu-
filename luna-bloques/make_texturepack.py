"""Texture pack propio estilo anime (32x32 por bloque), generado proceduralmente.

Salida: texturepack/blocks/<nombre>.png, texturepack/skins/*.png y texturepack/preview.png
Todo es original: paletas saturadas, contornos marcados y vetas en espiral al estilo anime.
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "texturepack", "blocks")
SKIN = os.path.join(HERE, "texturepack", "skins")
os.makedirs(OUT, exist_ok=True)
os.makedirs(SKIN, exist_ok=True)
T = 32
rng = np.random.default_rng(2024)
yy, xx = np.mgrid[0:T, 0:T].astype(np.float32)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def ramp(t, cols):
    """t en [0,1] -> color mediante una paleta escalonada (aspecto pintado/posterizado)."""
    cols = [hexc(c) for c in cols]
    idx = np.clip((t * len(cols)).astype(int), 0, len(cols) - 1)
    return np.stack(cols)[idx]


def tnoise(scale, seed=None, octaves=2):
    """Ruido suave que se repite (tileable) en el bloque."""
    r = rng if seed is None else np.random.default_rng(seed)
    acc = np.zeros((T, T), np.float32)
    amp = 1.0
    for o in range(octaves):
        n = r.standard_normal((T, T)).astype(np.float32)
        n = ndimage.gaussian_filter(n, scale / (2 ** o), mode="wrap")
        acc += amp * n / (n.std() + 1e-6)
        amp *= 0.5
    acc -= acc.min()
    return acc / (acc.max() + 1e-6)


def outline(mask, img, col, width=1):
    """Pinta un contorno oscuro alrededor de las regiones de la máscara."""
    er = ndimage.binary_erosion(mask, iterations=width, border_value=1)
    edge = mask & ~er
    img[edge] = hexc(col)
    return img


def border(img, col, w=1, alpha=1.0):
    m = np.zeros((T, T), bool)
    m[:w, :] = m[-w:, :] = m[:, :w] = m[:, -w:] = True
    img[m] = img[m] * (1 - alpha) + hexc(col) * alpha
    return img


def save(name, rgb, alpha=None):
    rgb = np.clip(rgb, 0, 1)
    arr = (rgb * 255 + 0.5).astype(np.uint8)
    if alpha is not None:
        a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(np.dstack([arr, a]), "RGBA").save(os.path.join(OUT, name + ".png"))
    else:
        Image.fromarray(arr, "RGB").save(os.path.join(OUT, name + ".png"))


def highlight_strokes(img, n, col, length=(3, 6), mask=None):
    """Pinceladas cortas diagonales de brillo (toque 'anime')."""
    c = hexc(col)
    for _ in range(n):
        x, y = rng.integers(1, T - 1, 2)
        L = rng.integers(*length)
        for k in range(L):
            px, py = (x + k) % T, (y - k // 2) % T
            if mask is None or mask[py, px]:
                img[py, px] = c
    return img


# ------------------------------------------------------------------ hierba
def grass_top():
    n = tnoise(3, octaves=3)
    img = ramp(n, ["#2E8B57", "#3FAE5A", "#54C75E", "#6FDB6A"])
    # mechones de hierba en forma de "v" claros y oscuros
    for _ in range(26):
        x, y = rng.integers(0, T, 2)
        dark = rng.random() < 0.45
        c = hexc("#237A4B") if dark else hexc("#9BEF7F")
        for k in range(3):
            img[(y - k) % T, (x - k // 2) % T] = c
            img[(y - k) % T, (x + 1 + k // 2) % T] = c * 0.97
    return img


def dirt():
    n = tnoise(2.2, octaves=3)
    img = ramp(n, ["#6B3B2A", "#80492F", "#955A37", "#A86B42"])
    for _ in range(9):  # piedrecitas con contorno
        x, y = rng.integers(1, T - 3, 2)
        img[y:y + 2, x:x + 3] = hexc("#C79A6B")
        img[y + 2, x:x + 3] = hexc("#5A2F22")
    return img


def grass_side():
    img = dirt()
    top = ramp(tnoise(3), ["#3FAE5A", "#54C75E", "#6FDB6A"])
    depth = 6 + (3 * np.sin(xx[0] * 0.9) + 2 * np.sin(xx[0] * 2.3 + 1)).astype(int)
    for x in range(T):
        d = max(4, depth[x])
        img[:d, x] = top[:d, x]
        img[d, x] = hexc("#237A4B")
        if rng.random() < 0.25:  # gotas de hierba
            img[d:d + 2, x] = hexc("#2E8B57")
    img[0, :] = hexc("#8BEA7A")
    return img


# ------------------------------------------------------------------ piedra
def stone():
    n = tnoise(2.5, octaves=3)
    img = ramp(n, ["#5D6688", "#6E78A0", "#8089B3", "#929CC4"])
    # grietas estilizadas
    for _ in range(4):
        x, y = rng.integers(0, T, 2)
        for k in range(rng.integers(5, 10)):
            x = (x + rng.integers(-1, 2)) % T
            y = (y + 1) % T
            img[y, x] = hexc("#3E4566")
    img = highlight_strokes(img, 6, "#B9C2EA")
    return img


def stones_pattern(base_cols, mortar, hi, cells=7, seed=0):
    """Piedras redondeadas tipo empedrado con contorno marcado."""
    r = np.random.default_rng(seed)
    pts = r.uniform(0, T, (cells, 2))
    pts = np.concatenate([pts + [dx, dy] for dx in (-T, 0, T) for dy in (-T, 0, T)])
    d = np.sqrt((xx[..., None] - pts[:, 0]) ** 2 + (yy[..., None] - pts[:, 1]) ** 2)
    ds = np.sort(d, axis=2)
    lab = np.argmin(d, axis=2) % cells
    edge = (ds[..., 1] - ds[..., 0]) < 1.6
    shade = r.uniform(0, 1, cells)[lab]
    n = tnoise(2)
    img = ramp(np.clip(0.55 * shade + 0.45 * n, 0, 0.999), base_cols)
    # brillo arriba-izquierda de cada piedra
    gx = np.gradient(ds[..., 1] - ds[..., 0], axis=1)
    gy = np.gradient(ds[..., 1] - ds[..., 0], axis=0)
    lit = ((gx + gy) > 0.35) & ((ds[..., 1] - ds[..., 0]) < 4.5) & ~edge
    img[lit] = hexc(hi)
    img[edge] = hexc(mortar)
    return img


def cobble():
    return stones_pattern(["#5B5F86", "#6B70A0", "#7C82B5", "#8E95C6"], "#2D2F4A", "#AEB6E6", 8, 3)


def path_stone():
    return stones_pattern(["#A88A6E", "#B89A7A", "#C7AA88", "#D6BB98"], "#6E4E3A", "#EEDBBE", 9, 7)


def plaza_tiles():
    """Losas moradas como el suelo del ejemplo, en ladrillo trabado."""
    img = ramp(tnoise(2.5), ["#6A4C93", "#7A5BA6", "#8B6BB8"])
    m = np.zeros((T, T), bool)
    for row in range(4):
        y0 = row * 8
        m[y0, :] = True
        off = 0 if row % 2 == 0 else 8
        for x0 in range(off, T, 16):
            m[y0:y0 + 8, x0 % T] = True
    img[m] = hexc("#3B2A5C")
    hl = np.roll(m, 1, axis=0) & ~m
    img[hl] = hexc("#B49BDB")
    return img


def stone_bricks():
    img = ramp(tnoise(2.5), ["#6F7898", "#7E88AA", "#8E98BB"])
    m = np.zeros((T, T), bool)
    for row in range(4):
        y0 = row * 8
        m[y0, :] = True
        off = 0 if row % 2 == 0 else 8
        for x0 in range(off, T + 16, 16):
            m[y0:y0 + 8, x0 % T] = True
    img[m] = hexc("#3D4360")
    img[np.roll(m, 1, axis=0) & ~m] = hexc("#B4BDDD")
    return img


# ------------------------------------------------------------------ madera
def swirl_wood(cols, line, seed, cx=None, cy=None):
    """Veta en espiral muy marcada (look de madera anime)."""
    r = np.random.default_rng(seed)
    cx = r.uniform(4, T - 4) if cx is None else cx
    cy = r.uniform(4, T - 4) if cy is None else cy
    dx, dy = xx - cx, (yy - cy) * 1.0
    rad = np.sqrt(dx ** 2 + dy ** 2)
    ang = np.arctan2(dy, dx)
    v = (rad * 0.55 + ang * 1.1 + 2.0 * tnoise(4, seed)) % 3.0 / 3.0
    img = ramp(v, cols)
    lines = (np.abs(((rad * 0.55 + ang * 1.1 + 2.0 * tnoise(4, seed)) % 3.0) - 0.15) < 0.18)
    img[lines] = hexc(line)
    return img


def planks():
    img = np.zeros((T, T, 3), np.float32)
    for b in range(2):  # 2 tablones anchos con remolino visible
        sw = swirl_wood(["#B5652E", "#C8763A", "#D98A48", "#E89E5A"], "#7A3A18", 10 + b,
                        cx=8 + 16 * b, cy=b * 16 + 8)
        img[b * 16:(b + 1) * 16] = sw[b * 16:(b + 1) * 16]
        img[b * 16] = hexc("#5C2A12")
        img[b * 16 + 1] = np.minimum(img[b * 16 + 1] * 1.15, 1)
    return img


def lacquer():
    """Madera lacada roja (torii, pilares)."""
    n = tnoise(4)
    img = ramp(n, ["#A3192B", "#BC2233", "#D02E3D"])
    for x in range(T):
        if (x * 7) % 11 == 0:
            img[:, x] = img[:, x] * 0.85
    img[:, 2:4] = hexc("#E8576A")
    img = border(img, "#5E0D18")
    return img


def dark_wood():
    n = tnoise(3)
    img = ramp(n, ["#3B2236", "#4A2C45", "#5A3654"])
    for x in range(0, T, 8):
        img[:, x] = hexc("#22121F")
        img[:, x + 1] = hexc("#7A4D72")
    return img


def log_side():
    img = np.zeros((T, T, 3), np.float32)
    n = tnoise(2.0, octaves=2)
    for x in range(T):
        stripe = (x // 4) % 2
        img[:, x] = ramp(n[:, x] * 0.5 + 0.5 * stripe, ["#4B2A1E", "#5E3524", "#71422C", "#86513A"])
    for _ in range(8):
        x = rng.integers(0, T)
        y0 = rng.integers(0, T)
        img[np.arange(y0, y0 + 6) % T, x] = hexc("#2F1912")
    img = highlight_strokes(img, 5, "#A8735A", (2, 4))
    return img


def log_top():
    return border(swirl_wood(["#C98A4E", "#D99C5E", "#E8B072", "#D99C5E"], "#8A5226", 99,
                             cx=15.5, cy=15.5), "#4B2A1E", 2)


# ------------------------------------------------------------------ hojas
def leaves(cols, dark, hi, seed):
    r = np.random.default_rng(seed)
    a = np.zeros((T, T), np.float32)
    img = np.zeros((T, T, 3), np.float32)
    n = tnoise(2.5, seed)
    for _ in range(22):  # racimos redondeados
        cx, cy = r.uniform(0, T, 2)
        rr = r.uniform(3.5, 6.5)
        d = np.sqrt(((xx - cx + T / 2) % T - T / 2) ** 2 + ((yy - cy + T / 2) % T - T / 2) ** 2)
        m = d < rr
        a[m] = 1
        t = np.clip(0.6 - (d - rr * 0.3) / rr * 0.6 + 0.3 * n, 0, 0.999)
        img[m] = ramp(t[m], cols)
    holes = r.random((T, T)) < 0.06
    a[holes] = 0
    edge = (a > 0) & ~ndimage.binary_erosion(a > 0, border_value=1)
    img[edge] = hexc(dark)
    img = highlight_strokes(img, 10, hi, (2, 4), a > 0)
    return img, a


def sakura_leaves():
    return leaves(["#E0679A", "#EE84B0", "#F7A4C6", "#FFC6DD"], "#9E2F66", "#FFE6F1", 5)


def green_leaves():
    return leaves(["#1F8A5B", "#2DA36A", "#43BD78", "#62D48A"], "#145238", "#B8F2A6", 6)


# ------------------------------------------------------------------ casa japonesa
def shoji(lit=False):
    base = ["#FFE9B8", "#FFF2CF"] if lit else ["#E9E2F2", "#F4EFFA"]
    img = ramp(tnoise(5), base)
    if lit:
        g = np.exp(-((xx - 15.5) ** 2 + (yy - 15.5) ** 2) / 220)
        img = img * (0.88 + 0.2 * g[..., None])
    frame = hexc("#3B2236")
    m = np.zeros((T, T), bool)
    for v in (0, 1, 10, 21, 30, 31):
        m[:, v] = True
    for h in (0, 1, 8, 16, 24, 30, 31):
        m[h, :] = True
    img[m] = frame
    return img


def roof_tiles():
    """Tejas kawara en filas arqueadas (azul petróleo)."""
    img = np.zeros((T, T, 3), np.float32)
    for row in range(4):
        y0 = row * 8
        off = 0 if row % 2 == 0 else 4
        for k in range(-1, 5):
            cx = k * 8 + off + 4
            d = np.abs(xx - cx)
            m = (d <= 4) & (yy >= y0) & (yy < y0 + 8)
            t = np.clip(1 - d / 4.5, 0, 0.999) * 0.8 + (yy - y0) / 40
            img[m] = ramp(t[m], ["#22426E", "#2C5A8C", "#3A72A8", "#4E8CC4"])
            arc = m & (np.abs(d - 4) < 0.6)
            img[arc] = hexc("#122640")
        img[y0 + 7, :] = hexc("#0E1C33")
    return img


def tatami():
    img = ramp(tnoise(3), ["#A9B55E", "#B8C46A", "#C7D178"])
    for y in range(0, T, 2):
        img[y, :] = img[y, :] * 0.93
    img[:, :2] = hexc("#2F4A2A")
    img[:, -2:] = hexc("#2F4A2A")
    return img


def paper_lantern():
    img = ramp(tnoise(4), ["#E2453C", "#F05A48", "#FF7558"])
    for y in range(3, T - 3, 5):
        img[y, :] = hexc("#B32A2A")
    g = np.exp(-((xx - 15.5) ** 2 / 90 + (yy - 15.5) ** 2 / 160))
    img = img * (0.8 + 0.45 * g[..., None])
    img[:3, :] = hexc("#2A1A12")
    img[-3:, :] = hexc("#2A1A12")
    return img


# ------------------------------------------------------------------ agua, arena, otros
def water():
    n = tnoise(3.5, octaves=2)
    img = ramp(n, ["#1E6FD1", "#2A86E6", "#38A0F2", "#4FBBFA"])
    for _ in range(9):  # ondas tipo anime
        x, y = rng.integers(0, T, 2)
        for k in range(6):
            yy2 = (y + int(round(np.sin(k * 0.9) * 1.2))) % T
            img[yy2, (x + k) % T] = hexc("#BFF1FF")
    return img


def sand():
    img = ramp(tnoise(2, octaves=3), ["#E8C98E", "#F0D69E", "#F7E3B2", "#FCEFC8"])
    for _ in range(14):
        x, y = rng.integers(0, T, 2)
        img[y, x] = hexc("#C9A46A")
    return img


def farmland():
    img = ramp(tnoise(2.5), ["#5A3222", "#6B3B2A", "#7C462F"])
    for y in range(0, T, 6):
        img[y:y + 2, :] = hexc("#40231A")
    return img


def crop():
    a = np.zeros((T, T), np.float32)
    img = np.zeros((T, T, 3), np.float32)
    for x in range(2, T, 5):
        h = rng.integers(16, 28)
        for y in range(T - h, T):
            a[y, x] = 1
            img[y, x] = hexc("#7FBF3F") if y > T - h + 5 else hexc("#F2C94C")
            if y < T - h + 6:
                a[y, x + 1] = 1
                img[y, x + 1] = hexc("#E0A93A")
    return img, a


def flowers():
    a = np.zeros((T, T), np.float32)
    img = np.zeros((T, T, 3), np.float32)
    cols = ["#FF6FA8", "#FFD84D", "#B57BFF", "#FFFFFF"]
    for x in range(3, T - 3, 7):
        h = rng.integers(10, 20)
        img[T - h:, x] = hexc("#2DA36A")
        a[T - h:, x] = 1
        c = hexc(cols[rng.integers(0, 4)])
        y = T - h
        for dx, dy in ((0, -2), (-2, 0), (2, 0), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            img[y + dy, x + dx] = c
            a[y + dy, x + dx] = 1
        img[y, x] = hexc("#FFE9A0")
        a[y, x] = 1
    return img, a


def moon_block():
    img = ramp(tnoise(3, octaves=3), ["#E9D7A6", "#F1E2B6", "#F7EBC6", "#FCF3D8"])
    for _ in range(3):
        x, y = rng.integers(4, T - 4, 2)
        rr = rng.uniform(1.5, 3.2)
        d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
        img[d < rr] = img[d < rr] * 0.93
        img[np.abs(d - rr) < 0.6] = hexc("#D6BE84")
    return img


def stone_lantern():
    img = stone_bricks()
    g = np.exp(-((xx - 15.5) ** 2 + (yy - 15.5) ** 2) / 40)
    win = (np.abs(xx - 15.5) < 6) & (np.abs(yy - 15.5) < 6)
    img[win] = ramp(np.clip(g[win], 0, 0.999), ["#FF9F43", "#FFC46B", "#FFE3A3"])
    img[(np.abs(xx - 15.5) < 7) & (np.abs(yy - 15.5) < 7) & ~win] = hexc("#2D2F4A")
    return img


blocks = {
    "grass_top": grass_top(), "grass_side": grass_side(), "dirt": dirt(),
    "stone": stone(), "cobble": cobble(), "path_stone": path_stone(), "plaza_tiles": plaza_tiles(),
    "stone_bricks": stone_bricks(), "planks": planks(), "lacquer": lacquer(), "dark_wood": dark_wood(),
    "log_side": log_side(), "log_top": log_top(), "shoji": shoji(False), "shoji_lit": shoji(True),
    "roof_tiles": roof_tiles(), "tatami": tatami(), "paper_lantern": paper_lantern(),
    "water": water(), "sand": sand(), "farmland": farmland(), "moon_block": moon_block(),
    "stone_lantern": stone_lantern(),
}
for k, v in blocks.items():
    save(k, v)
cut = {"sakura_leaves": sakura_leaves(), "green_leaves": green_leaves(), "crop": crop(),
       "flowers": flowers()}
for k, (v, a) in cut.items():
    save(k, v, a)

# ------------------------------------------------------------------ caras y ropa (aldeanos)
FT = 16  # resolución de las piezas de personaje


def face(skin, hair, eye, smirk_open=False):
    """Cara anime: flequillo, ojos grandes con brillo, sonrisa pícara de lado (no carcajada)."""
    S = hexc(skin)
    img = np.tile(S, (FT, FT, 1))
    H = hexc(hair)
    Hd = H * 0.7
    # flequillo con mechones
    for x in range(FT):
        h = 4 + (2 if x % 5 in (1, 2) else 0) + (1 if x % 3 == 0 else 0)
        img[:h, x] = H
        img[h - 1, x] = Hd
    img[:, :1] = H
    img[:, -1:] = H
    # ojos grandes (2x3 + brillo), mirada entrecerrada pícara (párpado superior recto)
    E = hexc(eye)
    for ex in (3, 10):
        img[7:11, ex:ex + 3] = E
        img[10, ex:ex + 3] = E * 0.6
        img[9, ex + 1] = np.minimum(E * 1.5, 1)
        img[7, ex:ex + 3] = hexc("#1A1020")        # párpado
        img[6, ex:ex + 3] = hexc("#1A1020")       # pestañas
        img[6, ex - 1 if ex == 3 else ex + 3] = hexc("#1A1020")
        img[8, ex] = hexc("#FFFFFF")               # brillo
    # cejas inclinadas (gesto travieso)
    img[5, 3:6] = Hd
    img[5, 10:13] = Hd
    img[4, 3] = Hd
    img[4, 12] = Hd
    # rubor
    img[10, 2:4] = S * np.array([1.0, 0.75, 0.8])
    img[10, 12:14] = S * np.array([1.0, 0.75, 0.8])
    # sonrisa de lado
    M = hexc("#5A1F2E")
    if smirk_open:
        img[12, 6:11] = M
        img[13, 7:11] = M
        img[12, 7:10] = hexc("#FFFFFF")
        img[11, 10:12] = M
    else:
        img[12, 6:10] = M
        img[11, 10:12] = M
        img[12, 5] = M * 1.3
    return img


def hair_tile(hair, back=False):
    H = hexc(hair)
    img = np.tile(H, (FT, FT, 1)) * (0.92 + 0.12 * ndimage.gaussian_filter(
        rng.standard_normal((FT, FT)), 1.0)[..., None])
    for x in range(0, FT, 3):
        img[:, x] = H * 0.78
    img[:, 1::3] = np.minimum(img[:, 1::3] * 1.12, 1)
    if back:
        img[-2:, :] = H * 0.6
    return img


def kimono(col, accent):
    C, A = hexc(col), hexc(accent)
    img = np.tile(C, (FT, FT, 1)) * (0.95 + 0.08 * tnoise(2)[:FT, :FT, None])
    # cuello cruzado en V
    for y in range(9):
        lx, rx = 3 + (y * 4) // 8, 12 - (y * 4) // 8
        img[y, lx + 2:rx - 1] = hexc("#F3E9F7")   # interior claro
        img[y, lx:lx + 2] = hexc("#FFFFFF")       # solapas
        img[y, rx - 1:rx + 1] = hexc("#FFFFFF")
    img[9:12, :] = A          # obi (faja)
    img[10, 7:9] = hexc("#FFD84D")
    # flores estampadas
    for _ in range(4):
        x, y = rng.integers(1, FT - 1), rng.integers(12, FT - 1)
        img[y, x] = hexc("#FFE6F1")
    return img


def plain(col, shade=0.85):
    C = hexc(col)
    img = np.tile(C, (FT, FT, 1))
    img[-2:, :] = C * shade
    return img


def save16(name, rgb):
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(SKIN, name + ".png"))


SKINS = ["#FFE0C8", "#F6CDB0", "#E8B892", "#FCE6D8"]
HAIRS = ["#F48FB1", "#3A2B4A", "#E8E4F2", "#7A4A2A", "#5B7BE0", "#2B2B33", "#F2B84B", "#9C6ADE"]
EYES = ["#C2185B", "#6A3DE8", "#1E88E5", "#E53935", "#00897B", "#8E24AA"]
KIMONO = [("#3949AB", "#E91E63"), ("#D81B60", "#311B92"), ("#00897B", "#FFB300"),
          ("#5E35B1", "#FF7043"), ("#C62828", "#212121"), ("#F06292", "#4A148C"),
          ("#1E88E5", "#F8BBD0"), ("#43A047", "#6D4C41")]
for i in range(8):
    s, h, e = SKINS[i % 4], HAIRS[i], EYES[i % 6]
    save16(f"face_{i}", face(s, h, e, False))
    save16(f"face_{i}_risa", face(s, h, e, True))
    save16(f"hair_{i}", hair_tile(h))
    save16(f"hairback_{i}", hair_tile(h, True))
    save16(f"kimono_{i}", kimono(*KIMONO[i]))
    save16(f"sleeve_{i}", plain(KIMONO[i][0]))
    save16(f"skin_{i}", plain(s, 0.92))
    save16(f"hakama_{i}", plain(["#2B2B45", "#3E2723", "#263238", "#4A148C"][i % 4]))

# ------------------------------------------------------------------ hoja de muestra
names = list(blocks) + list(cut)
cols = 9
rows = (len(names) + cols - 1) // cols
S = 96
sheet = Image.new("RGB", (cols * (S + 8) + 8, rows * (S + 8) + 8 + 2 * (S + 8)), (40, 26, 60))
for i, n in enumerate(names):
    im = Image.open(os.path.join(OUT, n + ".png")).convert("RGBA")
    bg = Image.new("RGBA", im.size, (40, 26, 60, 255))
    bg.alpha_composite(im)
    sheet.paste(bg.convert("RGB").resize((S, S), Image.NEAREST), (8 + (i % cols) * (S + 8), 8 + (i // cols) * (S + 8)))
y0 = 8 + rows * (S + 8)
for i in range(8):
    im = Image.open(os.path.join(SKIN, f"face_{i}.png")).resize((S, S), Image.NEAREST)
    sheet.paste(im, (8 + i * (S + 8), y0))
    im = Image.open(os.path.join(SKIN, f"kimono_{i}.png")).resize((S, S), Image.NEAREST)
    sheet.paste(im, (8 + i * (S + 8), y0 + S + 8))
sheet.save(os.path.join(HERE, "texturepack", "preview.png"))
print("ok", len(names), "bloques")
