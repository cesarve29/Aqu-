"""Python side of the voxel ray tracer: materials, models, renderer process."""
import math
import os
import struct
import subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
os.makedirs(BUILD, exist_ok=True)

# ----------------------------------------------------------------- materials
# id: (name, color1 sRGB, color2 sRGB, pattern, emission (linear HDR), reflectivity)
MATS = {}
M = {}


def mat(i, name, c1, c2, pat, emit=(0, 0, 0), refl=0.0):
    MATS[i] = (name, c1, c2, pat, emit, refl)
    M[name] = i


mat(1, "grass_snow", (121, 85, 58), (236, 242, 250), 5)
mat(2, "dirt", (121, 85, 58), (90, 62, 42), 0)
mat(3, "stone", (125, 125, 130), (100, 100, 105), 0)
mat(4, "cobble", (118, 118, 122), (80, 80, 85), 6)
mat(5, "planks", (160, 112, 66), (120, 80, 45), 1)
mat(6, "log", (88, 60, 38), (170, 130, 80), 3)
mat(7, "spruce_leaves", (38, 82, 52), (235, 242, 250), 4)
mat(8, "snow", (238, 244, 252), (220, 230, 245), 13)
mat(9, "ice", (150, 195, 235), (220, 240, 255), 10, (0, 0, 0), 0.55)
mat(10, "packed_ice", (120, 165, 220), (200, 225, 250), 10, (0, 0, 0), 0.35)
mat(11, "window", (255, 190, 100), (90, 60, 35), 11, (3.2, 2.0, 0.8))
mat(12, "roof_red", (150, 45, 40), (110, 30, 28), 12)
mat(13, "brick", (150, 75, 60), (180, 170, 160), 2)
mat(14, "lantern", (255, 200, 110), (50, 45, 40), 17, (5.0, 3.2, 1.3))
mat(15, "roof_dark", (70, 60, 75), (50, 40, 55), 12)
mat(16, "crystal_blue", (90, 170, 255), (220, 250, 255), 7, (0.10, 0.35, 0.9), 0.5)
mat(17, "crystal_purple", (170, 100, 255), (240, 220, 255), 7, (0.35, 0.12, 0.8), 0.5)
mat(18, "lava", (255, 140, 30), (120, 20, 5), 8, (6.0, 2.2, 0.4))
mat(19, "obsidian", (30, 22, 40), (50, 40, 70), 0, (0, 0, 0), 0.15)
mat(20, "iron", (95, 95, 100), (70, 70, 75), 15, (0, 0, 0), 0.25)
mat(21, "gold", (255, 205, 60), (255, 240, 160), 18, (6.0, 4.6, 1.6))
mat(22, "light_red", (255, 50, 40), (30, 50, 30), 9, (5.0, 0.5, 0.3))
mat(23, "light_green", (60, 255, 80), (30, 50, 30), 9, (0.5, 4.5, 0.8))
mat(24, "light_yellow", (255, 220, 80), (30, 50, 30), 9, (5.0, 3.8, 0.8))
mat(25, "light_blue", (80, 150, 255), (30, 50, 30), 9, (0.6, 1.6, 6.0))
mat(26, "moss_stone", (110, 112, 108), (70, 110, 50), 14)
mat(27, "deepslate", (70, 70, 80), (55, 55, 62), 0)
mat(28, "gravel", (130, 125, 120), (100, 95, 90), 0)
mat(29, "wool_red", (190, 40, 40), (150, 30, 30), 16)
mat(30, "wool_white", (235, 235, 235), (210, 210, 210), 16)
mat(31, "present_red", (200, 40, 45), (250, 220, 90), 20)
mat(32, "present_green", (40, 150, 70), (240, 240, 240), 20)
mat(33, "path", (175, 170, 165), (150, 145, 140), 0)
mat(34, "dark_planks", (90, 62, 40), (60, 40, 25), 1)
mat(35, "star_dull", (120, 105, 70), (90, 80, 60), 15)
mat(36, "cave_stone", (60, 72, 95), (45, 55, 75), 0)
mat(37, "cave_floor", (70, 82, 105), (55, 65, 85), 19, (0, 0, 0), 0.12)
mat(38, "anvil", (55, 55, 60), (40, 40, 45), 15, (0, 0, 0), 0.3)
mat(39, "glow_amber", (255, 170, 70), (255, 220, 160), 18, (4.0, 2.2, 0.7))
mat(40, "basalt", (55, 50, 52), (40, 36, 38), 0)
mat(41, "magma_rock", (75, 45, 35), (150, 60, 20), 14)
mat(42, "light_white", (255, 245, 230), (30, 50, 30), 9, (4.0, 3.8, 3.4))
mat(43, "hay", (210, 175, 80), (180, 140, 60), 1)
mat(44, "stone_brick", (128, 128, 134), (95, 95, 100), 2)
mat(45, "campfire", (255, 150, 50), (60, 40, 25), 8, (7.0, 3.0, 0.6))
mat(46, "crystal_gold", (255, 210, 110), (255, 250, 220), 7, (1.5, 1.0, 0.3), 0.5)
mat(47, "frost_stone", (150, 170, 200), (200, 220, 240), 0)
mat(48, "chain", (60, 58, 60), (40, 38, 40), 15)


def mat_commands():
    out = []
    for i, (name, c1, c2, pat, emit, refl) in sorted(MATS.items()):
        out.append("MAT %d %d %d %d %d %d %d %d %.3f %.3f %.3f %.3f" % (i, *c1, *c2, pat, *emit, refl))
    return out


# ----------------------------------------------------------------- grids

def save_world(path, vox):
    """vox: numpy uint8 array indexed [x, y, z]."""
    X, Y, Z = vox.shape
    arr = np.ascontiguousarray(vox.transpose(1, 2, 0))  # (Y, Z, X)
    with open(path, "wb") as f:
        f.write(struct.pack("iii", X, Y, Z))
        f.write(arr.astype(np.uint8).tobytes())


class VoxModel:
    """Small voxel model with its own palette. Palette entries: (r,g,b, emit, refl)."""

    def __init__(self, w, h, d, pivot=(0, 0, 0)):
        self.v = np.zeros((w, h, d), np.uint8)
        self.pal = [(0, 0, 0, 0, 0)]
        self.pivot = pivot
        self.palidx = {}

    def color(self, rgb, emit=0.0, refl=0.0):
        key = (tuple(rgb), emit, refl)
        if key not in self.palidx:
            self.pal.append((rgb[0], rgb[1], rgb[2], emit, refl))
            self.palidx[key] = len(self.pal) - 1
        return self.palidx[key]

    def box(self, x0, y0, z0, x1, y1, z1, rgb, emit=0.0, refl=0.0):
        c = 0 if rgb == 0 else self.color(rgb, emit, refl)
        self.v[x0:x1, y0:y1, z0:z1] = c
        return c

    def set(self, x, y, z, rgb, emit=0.0, refl=0.0):
        w, h, d = self.v.shape
        if 0 <= x < w and 0 <= y < h and 0 <= z < d:
            self.v[x, y, z] = self.color(rgb, emit, refl)

    def save(self, path):
        w, h, d = self.v.shape
        arr = np.ascontiguousarray(self.v.transpose(1, 2, 0))
        with open(path, "wb") as f:
            f.write(struct.pack("iii", w, h, d))
            f.write(struct.pack("fff", *self.pivot))
            f.write(struct.pack("i", len(self.pal)))
            for p in self.pal:
                f.write(struct.pack("ffffff", p[0], p[1], p[2], p[3], p[4], 0.0))
            f.write(arr.tobytes())


# ----------------------------------------------------------------- math helpers

def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


I3 = np.eye(3)


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0) if b != a else (1.0 if x >= b else 0.0)
    return t * t * (3 - 2 * t)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_io(t):
    t = min(max(t, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return tuple(lerp(x, y, t) for x, y in zip(a, b))


def catmull(points, t):
    """Catmull-Rom through list of tuples, t in [0,1]."""
    n = len(points)
    if n == 1:
        return points[0]
    t = min(max(t, 0.0), 1.0) * (n - 1)
    i = min(int(t), n - 2)
    u = t - i
    p0 = np.array(points[max(i - 1, 0)], float)
    p1 = np.array(points[i], float)
    p2 = np.array(points[i + 1], float)
    p3 = np.array(points[min(i + 2, n - 1)], float)
    r = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)
    return tuple(r)


# ----------------------------------------------------------------- frame builder

class Frame:
    def __init__(self):
        self.lines = ["FRAME"]
        self.parts = None
        self.cam = None

    def camera(self, pos, target, fov=40.0, roll=0.0):
        self.cam = (pos, target, fov)
        self.lines.append("CAM %.4f %.4f %.4f %.4f %.4f %.4f %.3f %.4f" % (*pos, *target, fov, roll))

    def sun(self, d, col):
        self.lines.append("SUN %.4f %.4f %.4f %.4f %.4f %.4f" % (*d, *col))

    def sky(self, zen, hor, stars, aurora, moon_dir, moon_size, moon_col, t):
        self.lines.append("SKY " + " ".join("%.4f" % v for v in (*zen, *hor, stars, aurora, *moon_dir, moon_size, *moon_col, t)))

    def amb(self, c):
        self.lines.append("AMB %.4f %.4f %.4f" % tuple(c))

    def fog(self, c, den):
        self.lines.append("FOG %.4f %.4f %.4f %.5f" % (*c, den))

    def plane(self, on, y, m):
        self.lines.append("PLANE %d %.3f %d" % (on, y, m))

    def emit(self, m, s):
        self.lines.append("EMIT %d %.4f" % (M[m] if isinstance(m, str) else m, s))

    def grade(self, exposure=1.0, sat=1.0, contrast=1.0, tint=(1, 1, 1), vignette=0.35, fade=0.0, bloom=0.08, bloom_thr=1.0):
        self.lines.append("GRADE %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (exposure, sat, contrast, *tint, vignette, fade, bloom, bloom_thr))

    def inst(self, model, pos, R=I3, scale=1.0, shadow=1, emit=1.0, tint=(1, 1, 1)):
        R = np.asarray(R)
        self.lines.append("I %d %.4f %.4f %.4f %s %.5f %d %.4f %.4f %.4f %.4f" % (
            model, *pos, " ".join("%.5f" % v for v in R.flatten()), scale, shadow, emit, *tint))

    def light(self, p, c, r, shadow=1):
        self.lines.append("L %.4f %.4f %.4f %.4f %.4f %.4f %.3f %d" % (*p, *c, r, shadow))

    def glow(self, p, c, size):
        self.lines.append("G %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (*p, *c, size))

    def beam(self, a, b, c, w):
        self.lines.append("B %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f" % (*a, *b, *c, w))

    def particles(self, arr):
        """arr: float32 array (n, 9): x y z size r g b a type"""
        self.parts = np.ascontiguousarray(arr, dtype=np.float32)

    def encode(self):
        s = ("\n".join(self.lines) + "\n").encode()
        if self.parts is not None and len(self.parts):
            s += ("PARTS %d\n" % len(self.parts)).encode() + self.parts.tobytes()
        s += b"RENDER\n"
        return s


class Renderer:
    def __init__(self, w=1920, h=1080, threads=None):
        self.w, self.h = w, h
        env = dict(os.environ)
        if threads:
            env["OMP_NUM_THREADS"] = str(threads)
        self.p = subprocess.Popen([os.path.join(BUILD, "voxrt"), str(w), str(h)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, env=env, bufsize=0)
        self.send("\n".join(mat_commands()) + "\n")
        self.models_loaded = {}

    def send(self, s):
        if isinstance(s, str):
            s = s.encode()
        self.p.stdin.write(s)
        self.p.stdin.flush()

    def world(self, path):
        self.send("WORLD %s\n" % path)

    def model(self, mid, path):
        self.send("MODEL %d %s\n" % (mid, path))

    def render(self, frame):
        self.send(frame.encode())
        n = self.w * self.h * 3
        buf = bytearray()
        while len(buf) < n:
            chunk = self.p.stdout.read(n - len(buf))
            if not chunk:
                raise RuntimeError("renderer died")
            buf += chunk
        return np.frombuffer(bytes(buf), np.uint8).reshape(self.h, self.w, 3)

    def close(self):
        try:
            self.send("QUIT\n")
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()
            self.p.wait()
