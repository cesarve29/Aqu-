"""Shared helpers for the scenes: environment presets, actors, particles, events."""
import math
import numpy as np
from engine import M, Frame, rot_x, rot_y, rot_z, I3, ease, ease_io, lerp, vlerp, smoothstep, catmull
from models import IDS, humanoid_instances, golem_instances, walk_pose, idle_pose, Pose

FPS = 60


# ---------------------------------------------------------------- context
class Ctx:
    def __init__(self, f, t, T, wd, scene, record, state):
        self.f = f          # Frame
        self.t = t          # local time in scene
        self.T = T          # global time
        self.wd = wd        # world data (markers, lights, heightmap)
        self.scene = scene
        self.record = record
        self.state = state  # persistent dict across frames of a scene (for events)
        self.overlay = []   # (kind, args)

    def event(self, name, **kw):
        if self.record:
            self.state.setdefault("_events", []).append((self.T, name, kw))

    def once(self, key, t_at, name, **kw):
        """emit event `name` once when local time crosses t_at"""
        if self.record and self.t >= t_at and not self.state.get("once_" + key):
            self.state["once_" + key] = True
            self.event(name, **kw)


# ---------------------------------------------------------------- terrain height
def walk_heightmap(wd):
    if hasattr(wd, "_walk_hm"):
        return wd._walk_hm
    v = wd.v
    X, Y, Z = v.shape
    skip = {0, M["spruce_leaves"], M["log"], M["light_red"], M["light_green"], M["light_yellow"],
            M["light_blue"], M["light_white"], M["chain"], M["lantern"]}
    solid = np.ones_like(v, bool)
    for s_ in skip:
        solid &= (v != s_)
    # ground = top of the first solid run from the bottom (ignores overhead structures)
    air = ~solid
    air[:, 0, :] = False
    first_air = np.argmax(air, axis=1)
    top = np.where(air.any(axis=1), first_air, Y)
    wd._walk_hm = top
    return top


def ground_at(wd, x, z):
    hm = walk_heightmap(wd)
    X, Z = hm.shape
    fx, fz = x - 0.5, z - 0.5
    x0, z0 = int(math.floor(fx)), int(math.floor(fz))
    tx, tz = fx - x0, fz - z0

    def H(a, b):
        a = min(max(a, 0), X - 1); b = min(max(b, 0), Z - 1)
        return hm[a, b]
    bil = (H(x0, z0) * (1 - tx) + H(x0 + 1, z0) * tx) * (1 - tz) + (H(x0, z0 + 1) * (1 - tx) + H(x0 + 1, z0 + 1) * tx) * tz
    here = H(int(math.floor(x)), int(math.floor(z)))
    return max(bil, here)


# ---------------------------------------------------------------- paths
class Path:
    def __init__(self, pts, speed=1.8, t0=0.0):
        self.pts = [np.array(p, float) for p in pts]
        seg = [np.linalg.norm(self.pts[i + 1] - self.pts[i]) for i in range(len(self.pts) - 1)]
        self.cum = np.concatenate([[0], np.cumsum(seg)])
        self.length = self.cum[-1]
        self.speed = speed
        self.t0 = t0

    def at_s(self, s):
        s = min(max(s, 0), self.length)
        i = int(np.searchsorted(self.cum, s, side="right") - 1)
        i = min(max(i, 0), len(self.pts) - 2)
        seg = self.cum[i + 1] - self.cum[i]
        u = (s - self.cum[i]) / seg if seg > 0 else 0
        p = self.pts[i] * (1 - u) + self.pts[i + 1] * u
        d = self.pts[i + 1] - self.pts[i]
        return p, d

    def state(self, t):
        s = (t - self.t0) * self.speed
        moving = 0 < s < self.length
        s = min(max(s, 0), self.length)
        p, d = self.at_s(s)
        # smooth heading by looking ahead/behind
        p2, _ = self.at_s(min(s + 0.6, self.length))
        p1, _ = self.at_s(max(s - 0.6, 0))
        dd = p2 - p1
        if np.linalg.norm(dd) < 1e-6:
            dd = d
        yaw = math.atan2(dd[0], dd[-1])
        return p, yaw, s, moving


def yaw_to(a, b):
    return math.atan2(b[0] - a[0], b[2] - a[2])


def angle_lerp(a, b, t):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * t


def steps(ctx, key, phase, surface="snow", vol=1.0, actor="tilo"):
    """emit footstep events whenever the walk phase crosses a multiple of pi"""
    k = int(math.floor(phase / math.pi))
    last = ctx.state.get("step_" + key)
    if last is not None and k != last and ctx.record:
        ctx.event("step", surface=surface, vol=vol, actor=actor)
    ctx.state["step_" + key] = k


# ---------------------------------------------------------------- environment presets
NIGHT = dict(sun=(0.42, 0.62, -0.66), suncol=(0.20, 0.25, 0.42), zen=(0.006, 0.010, 0.035), hor=(0.035, 0.055, 0.14),
             amb=(0.085, 0.105, 0.21), fog=(0.035, 0.055, 0.14), fogden=0.0045, stars=1.0, aurora=0.7,
             moon=(0.42, 0.62, -0.66), moonsize=0.035, mooncol=(2.6, 2.6, 2.9))
DAWN = dict(sun=(0.85, 0.22, 0.45), suncol=(0.55, 0.38, 0.30), zen=(0.03, 0.05, 0.16), hor=(0.55, 0.30, 0.32),
            amb=(0.16, 0.15, 0.24), fog=(0.30, 0.22, 0.30), fogden=0.004, stars=0.25, aurora=0.0,
            moon=(-0.6, 0.35, -0.7), moonsize=0.03, mooncol=(1.2, 1.2, 1.3))
CAVE = dict(sun=(0.3, 1.0, 0.2), suncol=(0.0, 0.0, 0.0), zen=(0.0, 0.0, 0.004), hor=(0.004, 0.008, 0.02),
            amb=(0.035, 0.05, 0.09), fog=(0.01, 0.02, 0.045), fogden=0.012, stars=0.0, aurora=0.0,
            moon=(0, 1, 0), moonsize=0.0, mooncol=(0, 0, 0))
FORGE = dict(sun=(0.3, 1.0, 0.2), suncol=(0.0, 0.0, 0.0), zen=(0.004, 0.0, 0.0), hor=(0.03, 0.008, 0.004),
             amb=(0.06, 0.04, 0.035), fog=(0.05, 0.014, 0.006), fogden=0.010, stars=0.0, aurora=0.0,
             moon=(0, 1, 0), moonsize=0.0, mooncol=(0, 0, 0))
PEAK = dict(sun=(0.3, 0.55, -0.78), suncol=(0.18, 0.24, 0.42), zen=(0.004, 0.008, 0.03), hor=(0.04, 0.06, 0.13),
            amb=(0.08, 0.10, 0.20), fog=(0.04, 0.06, 0.13), fogden=0.006, stars=0.9, aurora=1.2,
            moon=(0.3, 0.55, -0.78), moonsize=0.04, mooncol=(2.6, 2.6, 2.9))


def mix_env(a, b, t):
    out = {}
    for k in a:
        va, vb = a[k], b[k]
        if isinstance(va, tuple):
            out[k] = tuple(lerp(x, y, t) for x, y in zip(va, vb))
        else:
            out[k] = lerp(va, vb, t)
    return out


def apply_env(ctx, env, plane_y=None, plane_mat="snow", exposure=1.0, sat=1.05, contrast=1.04, tint=(1, 1, 1),
              vignette=0.38, fade=0.0, bloom=0.10, bloom_thr=0.9):
    f = ctx.f
    f.sun(env["sun"], env["suncol"])
    f.sky(env["zen"], env["hor"], env["stars"], env["aurora"], env["moon"], env["moonsize"], env["mooncol"], ctx.T)
    f.amb(env["amb"])
    f.fog(env["fog"], env["fogden"])
    if plane_y is None:
        f.plane(0, 0, M["snow"])
    else:
        f.plane(1, plane_y, M[plane_mat])
    f.grade(exposure=exposure, sat=sat, contrast=contrast, tint=tint, vignette=vignette, fade=fade, bloom=bloom, bloom_thr=bloom_thr)


def world_lights(ctx, scale=1.0, flicker=0.0):
    if scale <= 0.001:
        return
    for i, (p, c, r, sh) in enumerate(ctx.wd.lights):
        k = scale
        if flicker > 0:
            k *= 1.0 - flicker * (0.5 + 0.5 * math.sin(ctx.T * (7 + i % 5) + i * 1.7)) * (0.5 + 0.5 * math.sin(ctx.T * 13.1 + i))
        ctx.f.light(p, tuple(x * k for x in c), r, sh)


def scene_fade(t, dur, fin=0.8, fout=0.8):
    a = 1.0
    if t < fin:
        a = ease(t / fin)
    if t > dur - fout:
        a = min(a, ease((dur - t) / fout))
    return 1.0 - a


# ---------------------------------------------------------------- particles
_rng = np.random.default_rng(2024)
SNOW_BASE = _rng.random((9000, 3)).astype(np.float32)
SNOW_SIZE = (0.035 + 0.06 * _rng.random(9000)).astype(np.float32)
SNOW_PH = (_rng.random(9000) * 6.283).astype(np.float32)


def snow(t, center, n=4000, box=(70, 40, 70), wind=(1.2, 0, 0.3), fall=1.4, size=1.0, color=(0.55, 0.6, 0.75), alpha=0.8,
         additive=False):
    n = min(n, len(SNOW_BASE))
    b = np.array(box, np.float32)
    base = SNOW_BASE[:n] * b
    drift = np.array(wind, np.float32) * t + np.array((0, -fall * t, 0), np.float32)
    sway = np.stack([np.sin(t * 1.3 + SNOW_PH[:n]) * 0.6, np.zeros(n), np.cos(t * 1.1 + SNOW_PH[:n]) * 0.6], 1)
    c = np.array(center, np.float32)
    p = np.mod(base + drift + sway - c + b / 2, b) - b / 2 + c
    out = np.zeros((n, 9), np.float32)
    out[:, :3] = p
    out[:, 3] = SNOW_SIZE[:n] * size
    out[:, 4:7] = color
    out[:, 7] = alpha
    out[:, 8] = 1.0 if additive else 0.0
    return out


def sparkles(t, pts, color=(3.0, 2.2, 0.8), size=0.06, n_per=6, spread=0.6, seed=1, rise=0.4, twinkle=4.0):
    """twinkling glitter around a list of points"""
    pts = np.asarray(pts, np.float32).reshape(-1, 3)
    r = np.random.default_rng(seed)
    k = len(pts) * n_per
    off = (r.random((k, 3)).astype(np.float32) - 0.5) * spread * 2
    ph = r.random(k).astype(np.float32) * 6.283
    sp = 0.5 + r.random(k).astype(np.float32)
    base = np.repeat(pts, n_per, axis=0)
    life = np.mod(t * 0.5 * sp + ph / 6.283, 1.0)
    pos = base + off + np.stack([np.zeros(k), life * rise, np.zeros(k)], 1)
    a = np.clip(np.sin(life * np.pi), 0, 1) * (0.5 + 0.5 * np.sin(t * twinkle * sp + ph))
    out = np.zeros((k, 9), np.float32)
    out[:, :3] = pos
    out[:, 3] = size
    out[:, 4:7] = color
    out[:, 7] = a
    out[:, 8] = 1
    return out


def trail(posfn, t, n=24, dt=0.035, color=(2.5, 1.9, 0.7), size=0.10, alpha=1.0):
    out = np.zeros((n, 9), np.float32)
    for i in range(n):
        p = posfn(t - i * dt)
        k = 1 - i / n
        out[i, :3] = p
        out[i, 3] = size * (0.4 + 0.6 * k)
        out[i, 4:7] = color
        out[i, 7] = alpha * k * k
        out[i, 8] = 1
    return out


def burst(age, center, color, n=90, speed=7.0, seed=0, size=0.16, gravity=2.0, life=2.6):
    """firework burst particles, age in seconds since explosion"""
    if age < 0 or age > life:
        return np.zeros((0, 9), np.float32)
    r = np.random.default_rng(seed)
    d = r.normal(size=(n, 3)).astype(np.float32)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    sp = speed * (0.75 + 0.25 * r.random(n)).astype(np.float32)
    dist = sp * (1 - np.exp(-age * 2.2)) / 2.2
    pos = np.asarray(center, np.float32) + d * dist[:, None] + np.array((0, -gravity * age * age * 0.5, 0), np.float32)
    out = np.zeros((n, 9), np.float32)
    out[:, :3] = pos
    out[:, 3] = size
    fadek = max(0.0, 1 - age / life)
    tw = 0.6 + 0.4 * np.sin(age * 25 + r.random(n) * 6.28)
    out[:, 4:7] = np.asarray(color, np.float32)
    out[:, 7] = (fadek ** 1.5) * tw
    out[:, 8] = 1
    return out


def ring(t, center, radius, color=(3, 2.2, 0.8), n=400, size=0.25, alpha=1.0, height=0.6, seed=5):
    r = np.random.default_rng(seed)
    ang = r.random(n).astype(np.float32) * 6.283
    jitter = r.random(n).astype(np.float32)
    rr = radius * (0.97 + 0.06 * jitter)
    out = np.zeros((n, 9), np.float32)
    out[:, 0] = center[0] + np.cos(ang) * rr
    out[:, 1] = center[1] + height * r.random(n)
    out[:, 2] = center[2] + np.sin(ang) * rr
    out[:, 3] = size
    out[:, 4:7] = color
    out[:, 7] = alpha * (0.5 + 0.5 * np.sin(t * 6 + ang * 7))
    out[:, 8] = 1
    return out


def cat(*arrs):
    arrs = [a for a in arrs if a is not None and len(a)]
    if not arrs:
        return np.zeros((0, 9), np.float32)
    return np.concatenate(arrs, 0)


# ---------------------------------------------------------------- light spirits
LUMI_COL = (2.6, 2.0, 0.85)
SISTER_COLS = [(2.6, 2.0, 0.85), (2.2, 1.5, 2.4), (1.2, 2.2, 2.6)]
SISTER_TINT = [(1, 1, 1), (1.0, 0.75, 1.0), (0.75, 0.95, 1.0)]


def spirit(ctx, pos, k=0, intensity=1.0, scale=0.07, yaw=0.0, light=True, light_r=8.0, shadow_light=1, glow=1.0):
    f = ctx.f
    if intensity <= 0.01:
        return
    col = SISTER_COLS[k]
    f.inst(IDS["lumi"], tuple(pos), rot_y(yaw), scale, shadow=0, emit=intensity * 0.6, tint=SISTER_TINT[k])
    if light:
        f.light(tuple(pos), tuple(c * intensity for c in col), light_r, shadow_light)
    if glow > 0:
        f.glow(tuple(pos), tuple(c * 0.55 * intensity * glow for c in col), 0.22)


def tilo(ctx, pos, yaw, pose, scarf=True, lantern=True, lit=1.0, light=True, scale=0.09, light_col=(2.8, 1.9, 0.8),
         light_r=10.0, wave=None):
    if wave is None:
        wave = math.sin(ctx.T * 3.1) * 0.15
    pts = humanoid_instances(ctx.f, "tilo", pos, yaw, pose, scale=scale, scarf=scarf, lantern=lantern, lantern_lit=lit,
                             scarf_wave=wave)
    if lantern and lit > 0.01 and light:
        lp = pts["lantern"]
        flick = 1.0 + 0.06 * math.sin(ctx.T * 17) + 0.04 * math.sin(ctx.T * 29)
        ctx.f.light(tuple(lp + np.array((0, 0.1, 0))), tuple(c * lit * flick for c in light_col), light_r, 1)
        ctx.f.glow(tuple(lp), tuple(c * 0.22 * lit for c in light_col), 0.12)
    return pts


def auto_clip(wd, pos, target):
    """distance along the camera->target segment beyond which nothing blocks the target"""
    p = np.array(pos, float); q = np.array(target, float)
    d = q - p
    L = float(np.linalg.norm(d))
    if L < 1e-3:
        return 0.0
    v = wd.v
    X, Y, Z = v.shape
    n = int(L / 0.2) + 1
    clip = 0.0
    for i in range(n, -1, -1):  # from camera side towards target? walk from target back to camera
        s = L * i / n
        x, y, z = p + d * (s / L)
        xi, yi, zi = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        if 0 <= xi < X and 0 <= yi < Y and 0 <= zi < Z and v[xi, yi, zi]:
            if s < L - 1.2:
                clip = s + 0.8
                break
    return min(clip, max(L - 1.0, 0.0))


def lookat_cam(ctx, pos, target, fov=40.0, roll=0.0, shake=0.0):
    clip = auto_clip(ctx.wd, pos, target)
    if clip > 0:
        ctx.f.lines.append("CLIP %.3f" % clip)
    if shake > 0:
        T = ctx.T
        pos = (pos[0] + shake * math.sin(T * 23.0) * 0.05, pos[1] + shake * math.sin(T * 31.0) * 0.05,
               pos[2] + shake * math.cos(T * 27.0) * 0.05)
    ctx.f.camera(tuple(pos), tuple(target), fov, roll)


def shot(t, cuts, dur=None):
    """cuts: list of start times. returns (index, local time in shot, shot duration)"""
    idx = 0
    for i, c in enumerate(cuts):
        if t >= c:
            idx = i
    end = cuts[idx + 1] if idx + 1 < len(cuts) else dur
    return idx, t - cuts[idx], max((end - cuts[idx]), 1e-3) if end else 1.0
