"""Animación: cámara, luna, aldeanos (cajas articuladas), llamas de la hoguera y pétalos de cerezo.

state(frame) devuelve el diccionario que consume Engine.render().
"""
import numpy as np

FPS = 24
FRAMES = 480                      # 20 s
G = 5.0                           # suelo del poblado

# ------------------------------------------------------------------ utilidades de matrices
def T(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def Rx(a):
    c, s = np.cos(a), np.sin(a)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = c, -s, s, c
    return m


def Ry(a):
    c, s = np.cos(a), np.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    return m


def Rz(a):
    c, s = np.cos(a), np.sin(a)
    m = np.eye(4)
    m[0, 0], m[0, 1], m[1, 0], m[1, 1] = c, -s, s, c
    return m


def look_rot(pos, tgt):
    f = np.asarray(tgt, float) - pos
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return np.stack([r, u, f], 1)


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ luna
MOON_C = np.array([0.0, 300.0, 140.0])
MOON_R = 80.0
VILLAGE = np.array([0.0, 0.0, G])
SUN = np.array([0.35, 0.75, 0.56])
SUN /= np.linalg.norm(SUN)


def moon_state(t):
    c = MOON_C + np.array([0, 0, 1.8 * np.sin(t * 2 * np.pi / 6.0)])
    z = VILLAGE - c
    z /= np.linalg.norm(z)
    x = np.cross([0, 0, 1], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.stack([x, y, z], 1)
    wob = Rz(np.radians(2.0 * np.sin(t * 2 * np.pi / 7.0)))[:3, :3] @ Rx(
        np.radians(1.5 * np.sin(t * 2 * np.pi / 9.0 + 1)))[:3, :3]
    glint = 0.5 + 0.5 * np.sin(t * 2.2)
    glint = max(glint, np.exp(-((t - 16.5) / 0.35) ** 2) * 2.0)     # destello del ojo al final
    return c, wob @ R, glint


# ------------------------------------------------------------------ cámara
# (fotograma, posición, objetivo, fov vertical)
CAM_KEYS = [
    (0,   (0.0, -94.0, 12.0), tuple(MOON_C), 24.0),
    (70,  (0.0, -91.0, 12.0), tuple(MOON_C + [0, 0, -4]), 22.5),
    (165, (0.0, -86.0, 10.5), (0.0, 0.0, 14.0), 48.0),
    (250, (0.0, -60.0, 7.6), (0.0, 0.0, 15.0), 52.0),
    (330, (0.3, -30.0, 7.8), (0.0, 20.0, 20.0), 56.0),
    (400, (-3.5, -15.5, 8.2), (1.0, 25.0, 26.0), 60.0),
    (480, (-4.0, -37.0, 26.0), (0.0, 22.0, 29.5), 68.0),
]


def catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def cam_state(f):
    ks = CAM_KEYS
    fr = np.array([k[0] for k in ks], float)
    i = int(np.clip(np.searchsorted(fr, f, side="right") - 1, 0, len(ks) - 2))
    t = (f - fr[i]) / (fr[i + 1] - fr[i])
    t = smooth(t) * 0.35 + t * 0.65
    def get(j, k):
        j = int(np.clip(j, 0, len(ks) - 1))
        return np.array(ks[j][k], float)
    pos = catmull(get(i - 1, 1), get(i, 1), get(i + 1, 1), get(i + 2, 1), t)
    tgt = catmull(get(i - 1, 2), get(i, 2), get(i + 1, 2), get(i + 2, 2), t)
    fov = (1 - smooth(t)) * ks[i][3] + smooth(t) * ks[i + 1][3]
    # leve vaivén de cámara en mano
    tt = f / FPS
    pos = pos + 0.05 * np.array([np.sin(tt * 1.3), np.sin(tt * 0.9 + 1), np.sin(tt * 1.7 + 2)])
    return pos, look_rot(pos, tgt), fov


# ------------------------------------------------------------------ aldeanos
rng = np.random.default_rng(42)


class Path:
    def __init__(self, pts):
        pts = np.asarray(pts, float)
        seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
        self.pts, self.cum, self.L = pts, np.concatenate([[0], np.cumsum(seg)]), seg.sum()

    def at(self, s):
        s = s % self.L
        i = int(np.searchsorted(self.cum, s, side="right") - 1)
        a, b = self.pts[i], self.pts[(i + 1) % len(self.pts)]
        u = (s - self.cum[i]) / (self.cum[i + 1] - self.cum[i])
        p = a + (b - a) * u
        d = b - a
        return p, d / np.linalg.norm(d)


def circle(r, n=96, cw=False):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if cw:
        a = -a
    return np.stack([r * np.cos(a), r * np.sin(a)], 1)


def rounded_rect(x0, x1, y0, y1, r, n=12):
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for a in np.linspace(a0, a0 + 90, n):
            pts.append((cx + r * np.cos(np.radians(a)), cy + r * np.sin(np.radians(a))))
    return pts


ring_a = Path(circle(6.2))
ring_b = Path(circle(8.6, cw=True))
lane = Path(rounded_rect(-1.7, 1.7, -32.0, -12.5, 1.6))

villagers = []
vid = 0
for path, n, speed in ((ring_a, 6, 3.0), (ring_b, 5, 3.4), (lane, 4, 3.7)):
    for k in range(n):
        villagers.append(dict(
            path=path, s0=path.L * k / n + rng.uniform(-0.6, 0.6), speed=speed * rng.uniform(0.92, 1.08),
            var=vid % 8, tail=rng.integers(0, 3), phase=rng.uniform(0, 6.28),
            chuckles=np.sort(rng.uniform(0, FRAMES / FPS, 6)), scale=rng.uniform(0.93, 1.05)))
        vid += 1


def box(M, half, texA, texB):
    return (M, np.asarray(half, float), tuple(int(v) for v in texA), tuple(int(v) for v in texB))


def villager_boxes(v, t, eng, cam_pos):
    p, d = v["path"].at(v["s0"] + v["speed"] * t)
    heading = np.arctan2(-d[0], d[1])
    stride = (v["s0"] + v["speed"] * t) / 1.55 * 2 * np.pi + v["phase"]
    sc = v["scale"]
    bob = 0.07 * abs(np.sin(stride))
    # risita: dura ~0.9 s, cara con sonrisa abierta y mirada pícara a cámara
    ch = 0.0
    for c in v["chuckles"]:
        ch = max(ch, float(np.clip(1 - abs(t - c) / 0.45, 0, 1)))
    laughing = ch > 0.15
    to_cam = cam_pos[:2] - p
    yaw_cam = np.arctan2(-to_cam[0], to_cam[1]) - heading
    yaw_cam = (yaw_cam + np.pi) % (2 * np.pi) - np.pi
    head_yaw = np.clip(yaw_cam, -0.9, 0.9) * smooth(ch * 1.6)
    head_tilt = -0.12 * ch + 0.05 * np.sin(stride * 2)
    shake = 0.05 * np.sin(t * 2 * np.pi * 6.5) * ch
    i = v["var"]
    S = eng.skin
    face = S(f"face_{i}_risa") if laughing else S(f"face_{i}")
    hair, hback, kim, slv, skn, hak = (S(f"hair_{i}"), S(f"hairback_{i}"), S(f"kimono_{i}"), S(f"sleeve_{i}"),
                                       S(f"skin_{i}"), S(f"hakama_{i}"))
    root = T(p[0], p[1], G + bob) @ Rz(heading) @ np.diag([sc, sc, sc, 1])
    out = []
    swing = 0.75 * np.sin(stride)
    for side, sgn in ((-1, 1), (1, -1)):
        hip = root @ T(0.14 * side, 0, 0.52) @ Rx(swing * sgn)
        out.append(box(hip @ T(0, 0, -0.26), (0.13, 0.14, 0.26), (hak,) * 4, (hak, hak, 0, 0)))
    torso = root @ T(0, 0, 0.52) @ Rx(-0.14) @ Ry(0.03 * np.sin(stride))
    out.append(box(torso @ T(0, 0, 0.33), (0.31, 0.18, 0.33), (slv, slv, kim, slv), (slv, slv, 0, 0)))
    for side, sgn in ((-1, -1), (1, 1)):
        sh = torso @ T(0.42 * side, 0, 0.6) @ Rx(0.65 * np.sin(stride) * sgn - 0.1) @ Ry(0.12 * side)
        out.append(box(sh @ T(0, 0, -0.27), (0.11, 0.11, 0.31), (slv,) * 4, (slv, skn, 0, 0)))
    neck = torso @ T(0, 0, 0.66 + 0.03 * ch * np.sin(t * 40)) @ Rz(head_yaw + shake) @ Rx(head_tilt)
    head = neck @ T(0, 0.02, 0.41)
    out.append(box(head, (0.41, 0.41, 0.41), (hair, hair, face, hback), (hair, skn, 0, 0)))
    if v["tail"] == 1:     # coleta
        out.append(box(head @ T(0, -0.46, 0.05) @ Rx(0.35 + 0.15 * np.sin(stride)), (0.12, 0.09, 0.26),
                       (hair,) * 4, (hair, hair, 0, 0)))
    elif v["tail"] == 2:   # moño
        out.append(box(head @ T(0, -0.12, 0.5), (0.17, 0.17, 0.12), (hair,) * 4, (hair, hair, 0, 0)))
    center = (root @ np.array([0, 0, 1.1, 1]))[:3]
    return out, center, 1.6 * sc


def fire_boxes(t, eng):
    out = []
    r = np.random.default_rng(9)
    for k in range(12):
        life = 0.9 + 0.3 * r.random()
        ph = (t / life + r.random()) % 1.0
        x0, y0 = r.uniform(-0.45, 0.45, 2)
        z = G + 1.0 + ph * 2.6
        s = 0.34 * (1 - ph) ** 0.8 + 0.04
        x = x0 * (1 - ph * 0.6) + 0.08 * np.sin(t * 6 + k)
        y = y0 * (1 - ph * 0.6) + 0.08 * np.cos(t * 5 + k * 2)
        lay = eng.skin(f"flame_{min(int(ph * 4), 3)}")
        M = T(x, y, z) @ Rz(t * 2 + k) @ Rx(0.3 * k)
        out.append(box(M, (s, s, s * 1.2), (lay,) * 4, (lay, lay, 1, 0)))
    return out


# ------------------------------------------------------------------ pétalos
NP = 2000
pr = np.random.default_rng(77)
P_BASE = np.stack([pr.uniform(-45, 45, NP), pr.uniform(-100, 35, NP), pr.uniform(0, 30, NP)], 1)
P_AX = pr.standard_normal((NP, 3))
P_AX /= np.linalg.norm(P_AX, axis=1, keepdims=True)
P_W = pr.uniform(1.5, 4.0, NP)
P_PH = pr.uniform(0, 6.28, NP)
P_COL = np.array([[1.0, 0.45, 0.70], [0.98, 0.38, 0.62], [1.0, 0.58, 0.78], [0.92, 0.32, 0.58]])[pr.integers(0, 4, NP)]
BOX_LO, BOX_SZ = np.array([-45, -100, G]), np.array([90, 135, 30])


def petals(t, cam_pos):
    pos = P_BASE + np.stack([1.3 * t + 0.6 * np.sin(t * 0.8 + P_PH), 0.5 * t + 0.4 * np.cos(t * 0.6 + P_PH),
                             -0.85 * t + 0.25 * np.sin(t * 1.7 + P_PH)], 1)
    pos = BOX_LO + (pos - BOX_LO) % BOX_SZ
    near = np.linalg.norm(pos - cam_pos, axis=1) < 60
    pos, ax, w, ph, col = pos[near], P_AX[near], P_W[near], P_PH[near], P_COL[near]
    ang = w * t + ph
    e1 = np.tile([0.12, 0, 0], (len(pos), 1))
    e2 = np.tile([0, 0.085, 0], (len(pos), 1))

    def rot(v):
        c, s = np.cos(ang)[:, None], np.sin(ang)[:, None]
        return v * c + np.cross(ax, v) * s + ax * (np.sum(ax * v, 1, keepdims=True)) * (1 - c)
    a, b = rot(e1), rot(e2)
    v0, v1, v2, v3 = pos - a - b, pos + a - b, pos + a + b, pos - a + b
    tri = np.stack([v0, v1, v2, v0, v2, v3], 1)               # (n, 6, 3)
    cols = np.repeat(col[:, None], 6, 1)
    return np.concatenate([tri, cols], 2).reshape(-1, 6)


# ------------------------------------------------------------------ estado completo
def state(f, eng):
    t = f / FPS
    cam_pos, cam_rot, fov = cam_state(f)
    mc, mr, glint = moon_state(t)
    boxes, groups = [], []
    for v in villagers:
        bx, c, r = villager_boxes(v, t, eng, cam_pos)
        groups.append((c, r, len(boxes), len(boxes) + len(bx)))
        boxes += bx
    fb = fire_boxes(t, eng)
    groups.append(((0.0, 0.0, G + 2.2), 2.4, len(boxes), len(boxes) + len(fb)))
    boxes += fb
    fire_i = 7.0 * (0.85 + 0.1 * np.sin(t * 11) + 0.05 * np.sin(t * 23 + 1))
    return dict(cam_pos=cam_pos, cam_rot=cam_rot, fov=fov, time=t, moon_c=mc, moon_r=mr, moon_radius=MOON_R,
                moon_glint=glint, sun_dir=SUN, fire_pos=(0.0, 0.0, G + 1.8), fire_i=fire_i,
                cloud_off=(1.6 * t, 0.4 * t), boxes=boxes, groups=groups, petals=petals(t, cam_pos),
                exposure=1.05, bloom=0.2)
