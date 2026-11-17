"""Texturas 2D pintadas proceduralmente: nubes anime, silueta de pueblo, destello y halo."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def save_rgba(rgb, a, name):
    img = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])
    Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(OUT, name))


# ------------------------------------------------------------------ nubes
def cloud(seed, W=1536, H=768, n_puffs=26, name="cloud.png"):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    puffs = []
    base = H * 0.78
    for i in range(n_puffs):
        t = rng.uniform(0.08, 0.92)
        mound = np.sin(np.pi * (t - 0.08) / 0.84) ** 0.8
        r = H * (0.07 + 0.16 * mound * rng.uniform(0.6, 1.0))
        cx = t * W
        cy = base - r * rng.uniform(0.2, 0.8) - mound * H * rng.uniform(0.05, 0.32)
        puffs.append((cx, cy, r))
    # base plana con puffs pequeños
    for i in range(14):
        t = rng.uniform(0.05, 0.95)
        r = H * rng.uniform(0.05, 0.09)
        puffs.append((t * W, base - r * 0.3, r))
    puffs.sort(key=lambda p: p[1] - p[2] * 0.3)  # los de arriba primero, los de abajo delante
    warp = ndimage.gaussian_filter(rng.standard_normal((H, W)).astype(np.float32), 10)
    warp = warp / warp.std() * 1.6
    alpha = np.zeros((H, W), np.float32)
    shade = np.zeros((H, W), np.float32)
    rim = np.zeros((H, W), np.float32)
    Ld = np.array([-0.45, -0.75, 0.5]); Ld /= np.linalg.norm(Ld)   # luz desde arriba-izquierda
    for cx, cy, r in puffs:
        dx, dy = xx - cx, yy - cy
        dist = np.sqrt(dx * dx + dy * dy) + warp
        cov = smoothstep(r + 1.2, r - 1.2, dist)
        nx, ny = dx / r, dy / r
        nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
        lam = nx * Ld[0] + ny * Ld[1] + nz * Ld[2]
        edge = smoothstep(r * 0.86, r * 0.99, dist) * smoothstep(0.1, 0.5, lam)
        shade = shade * (1 - cov) + lam * cov
        rim = rim * (1 - cov) + edge * cov
        alpha = np.maximum(alpha, cov)
    # cortar la base y desvanecer abajo
    alpha *= smoothstep(base + H * 0.06, base - H * 0.02, yy + warp * 3)
    # posterizado suave (cel shading)
    shade = ndimage.gaussian_filter(shade, 2.5)
    lvl = 0.0 + 0.33 * smoothstep(-0.35, 0.05, shade) + 0.33 * smoothstep(0.2, 0.5, shade) \
        + 0.34 * smoothstep(0.62, 0.9, shade)
    cols = [hexc("#1d3b78"), hexc("#3570c2"), hexc("#5fa6e6"), hexc("#a9e0ff")]
    rgb = np.zeros((H, W, 3), np.float32)
    seg = np.clip(lvl * 3, 0, 2.999)
    i0 = seg.astype(int)
    f = (seg - i0)[..., None]
    C = np.stack(cols)
    rgb = C[i0] * (1 - f) + C[np.minimum(i0 + 1, 3)] * f
    rim = ndimage.gaussian_filter(rim, 1.5)
    rgb = rgb * (1 - 0.5 * rim[..., None]) + hexc("#e4f6ff") * 0.5 * rim[..., None]
    vert = smoothstep(base - H * 0.05, base + H * 0.04, yy)[..., None]
    rgb = rgb * (1 - 0.45 * vert) + hexc("#16305e") * 0.45 * vert
    save_rgba(rgb, alpha, name)


for i in range(5):
    cloud(100 + i, n_puffs=20 + 4 * i, name=f"cloud_{i}.png")

# ------------------------------------------------------------------ pueblo (silueta)
def town(seed=3, W=4096, H=2048):
    rng = np.random.default_rng(seed)
    far = Image.new("L", (W, H), 0)
    near = Image.new("L", (W, H), 0)
    win = Image.new("L", (W, H), 0)
    df, dn, dw = ImageDraw.Draw(far), ImageDraw.Draw(near), ImageDraw.Draw(win)

    def building(d, x, w, h, roof, draw_windows):
        top = H - h
        d.rectangle([x, top, x + w, H], fill=255)
        if roof == "gable":
            rh = w * rng.uniform(0.35, 0.6)
            d.polygon([(x - 10, top), (x + w / 2, top - rh), (x + w + 10, top)], fill=255)
        elif roof == "spire":
            rh = w * rng.uniform(1.4, 2.4)
            d.polygon([(x - 6, top), (x + w / 2, top - rh), (x + w + 6, top)], fill=255)
        elif roof == "dome":
            d.ellipse([x, top - w / 2, x + w, top + w / 2], fill=255)
            d.rectangle([x + w / 2 - 4, top - w / 2 - 60, x + w / 2 + 4, top - w / 2], fill=255)
        if rng.random() < 0.5:
            cx = x + rng.uniform(0.15, 0.7) * w
            d.rectangle([cx, top - rng.uniform(40, 90), cx + 26, top + 10], fill=255)
        if draw_windows:
            for wy in np.arange(top + 40, H - 60, 70):
                for wx in np.arange(x + 22, x + w - 30, 48):
                    if rng.random() < 0.16:
                        dw.rectangle([wx, wy, wx + 18, wy + 28], fill=255)

    x = -50
    while x < W:
        w = rng.uniform(150, 320)
        building(df, x, w, rng.uniform(650, 1000), rng.choice(["gable", "flat", "spire", "gable"]), False)
        x += w * rng.uniform(0.7, 1.0)
    x = -80
    while x < W:
        w = rng.uniform(170, 380)
        center = abs(x + w / 2 - W / 2) / (W / 2)
        h = rng.uniform(380, 720) * (0.75 + 0.35 * center)
        building(dn, x, w, h, rng.choice(["gable", "gable", "flat", "dome", "spire"], p=[.35, .25, .15, .1, .15]), True)
        x += w * rng.uniform(0.85, 1.05)
    # torre del reloj
    tx = W * 0.3
    dn.rectangle([tx, H - 1250, tx + 190, H], fill=255)
    dn.polygon([(tx - 20, H - 1250), (tx + 95, H - 1700), (tx + 210, H - 1250)], fill=255)
    dw.ellipse([tx + 45, H - 1180, tx + 145, H - 1080], fill=255)

    farm = np.array(far) / 255.0
    nearm = np.array(near) / 255.0
    winm = np.array(win) / 255.0 * nearm
    rim = np.clip(nearm - np.roll(nearm, 6, axis=0), 0, 1)
    rimf = np.clip(farm - np.roll(farm, 6, axis=0), 0, 1)
    glow = ndimage.gaussian_filter(winm, 14) * 2.5
    rgb = np.zeros((H, W, 3), np.float32) + hexc("#1a2f5e")
    rgb = rgb * (1 - rimf[..., None]) + hexc("#3d63a0") * rimf[..., None]
    fy = np.linspace(0, 1, H)[:, None, None]
    near_col = hexc("#0a1530") * (1 - 0.3 * fy) + hexc("#050a18") * 0.3 * fy
    rgb = rgb * (1 - nearm[..., None]) + near_col * nearm[..., None]
    rgb = rgb * (1 - rim[..., None] * 0.8) + hexc("#5f86c2") * rim[..., None] * 0.8
    rgb = rgb + hexc("#ffb85a") * np.clip(glow, 0, 1)[..., None] * 0.35
    rgb = rgb * (1 - winm[..., None]) + hexc("#ffd27a") * winm[..., None]
    alpha = np.maximum(farm * 0.92, nearm)
    alpha = np.maximum(alpha, np.clip(glow * 0.4, 0, 1))
    save_rgba(rgb, alpha, "town.png")


town()

# ------------------------------------------------------------------ destello (4 puntas)
S = 512
yy, xx = (np.mgrid[0:S, 0:S] - S / 2 + 0.5) / (S / 2)
r = np.hypot(xx, yy)
star = np.exp(-np.abs(xx) / 0.5) * np.exp(-(yy / 0.025) ** 2) + np.exp(-np.abs(yy) / 0.5) * np.exp(-(xx / 0.025) ** 2)
rx, ry = (xx + yy) / np.sqrt(2), (xx - yy) / np.sqrt(2)
star += 0.35 * (np.exp(-np.abs(rx) / 0.22) * np.exp(-(ry / 0.02) ** 2) + np.exp(-np.abs(ry) / 0.22) * np.exp(-(rx / 0.02) ** 2))
star += np.exp(-(r / 0.06) ** 2) * 1.5 + np.exp(-(r / 0.25) ** 2) * 0.25
star *= smoothstep(1.0, 0.8, r)
a = np.clip(star, 0, 1)
save_rgba(np.ones((S, S, 3)), a, "sparkle.png")

# ------------------------------------------------------------------ halo radial
S = 1024
yy, xx = (np.mgrid[0:S, 0:S] - S / 2 + 0.5) / (S / 2)
r = np.hypot(xx, yy)
a = np.exp(-((r) / 0.45) ** 2) * smoothstep(1.0, 0.85, r)
save_rgba(np.ones((S, S, 3)), a, "halo.png")
print("ok")
