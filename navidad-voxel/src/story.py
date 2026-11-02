"""Scene timeline for 'Tilo y la Estrella del Alba'."""
import math
import os
import subprocess
import numpy as np
from engine import M, Frame, rot_x, rot_y, rot_z, I3, ease, ease_io, lerp, vlerp, smoothstep, catmull, ROOT
from models import IDS, humanoid_instances, golem_instances, walk_pose, idle_pose, Pose
from common import *

VOZ = os.path.join(ROOT, "voz")


def narr_dur(name):
    p = os.path.join(VOZ, name + ".mp3")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout
    return float(out.strip())


# =====================================================================  shared village helpers
VC = (96.0, 12.0, 104.0)
STAR_POS = (96.0, 55.3, 104.0)
WORKBENCH_TILO = (118.5, 12.0, 102.7)


def village_state(ctx, dim=0.0, flicker=0.0, lights_boost=1.0):
    f = ctx.f
    w = (1 - 0.65 * dim) * lights_boost
    f.emit("window", w)
    f.emit("lantern", (1 - 0.5 * dim) * lights_boost)
    for m in ("light_red", "light_green", "light_yellow", "light_blue", "light_white", "glow_amber"):
        f.emit(m, (1 - 0.8 * dim) * lights_boost)
    world_lights(ctx, scale=(1 - 0.6 * dim) * lights_boost, flicker=flicker)


def star(ctx, power, spin=None, rays=True):
    f = ctx.f
    yaw = (ctx.T * 0.35) if spin is None else spin
    on = min(max(power, 0), 3)
    tint = vlerp((0.42, 0.38, 0.3), (1, 1, 1), min(on, 1))
    f.inst(IDS["star"], STAR_POS, rot_y(yaw), 0.22, shadow=0, emit=on * 2.2, tint=tint)
    if on > 0.01:
        f.light((STAR_POS[0], STAR_POS[1] - 1.0, STAR_POS[2] + 0.0), (9 * on, 7 * on, 3 * on), 34, 0)
        f.glow(STAR_POS, (1.3 * on, 1.0 * on, 0.4 * on), 0.9)
        f.glow(STAR_POS, (0.35 * on, 0.22 * on, 0.08 * on), 2.6)
        if rays:
            for k in range(8):
                a = k / 8 * 2 * math.pi + ctx.T * 0.15
                L = 5.5 + 1.5 * math.sin(ctx.T * 1.3 + k)
                d = (math.cos(a) * L, math.sin(a) * L, 0)
                f.beam(STAR_POS, (STAR_POS[0] + d[0], STAR_POS[1] + d[1], STAR_POS[2] + 0.3),
                       (0.35 * on, 0.27 * on, 0.1 * on), 0.12)


CROWD = [("vil1", 1.62, 17.0, 0.09), ("vil2", 1.95, 17.5, 0.09), ("kid1", 1.78, 15.6, 0.065), ("vil3", 2.25, 16.5, 0.09),
         ("vil4", 2.55, 17.0, 0.09), ("kid2", 2.4, 15.4, 0.065), ("vil2", 0.55, 17.0, 0.09), ("vil3", 0.82, 16.2, 0.09),
         ("vil1", 2.85, 17.5, 0.09), ("vil4", 0.3, 17.5, 0.09), ("kid1", 0.65, 15.2, 0.065)]


def crowd_positions(wd):
    out = []
    for (v, a, r, s) in CROWD:
        x = VC[0] + math.cos(a) * r
        z = VC[2] + math.sin(a) * r
        out.append((v, (x, ground_at(wd, x, z), z), s, a))
    return out


def draw_crowd(ctx, look_up=0.0, talk=0.0, cheer=0.0, face=None, turn=None):
    for i, (v, p, s, a) in enumerate(crowd_positions(ctx.wd)):
        T = ctx.T + i * 1.37
        yaw = yaw_to(p, VC) if face is None else yaw_to(p, face)
        if turn is not None:
            yaw = angle_lerp(yaw, yaw_to(p, turn[0]), turn[1])
        pose = idle_pose(T)
        pose.head = (math.sin(T * 0.6) * 0.15 * (1 - look_up), 0.5 * look_up)
        if talk > 0:
            g = math.sin(T * 3.1 + i)
            pose.armL = (-0.4 - 0.5 * max(g, 0) * talk, 0.15)
            pose.armR = (-0.3 - 0.6 * max(-g, 0) * talk, -0.15)
            pose.head = (math.sin(T * 1.7) * 0.35 * talk, 0.05 + 0.1 * math.sin(T * 2.3))
        bob = 0.0
        if cheer > 0:
            hop = max(0.0, math.sin(T * 6.0 + i))
            bob = hop * 0.35 * cheer
            pose.armL = (-2.6 * cheer + 0.3 * math.sin(T * 6), 0.3)
            pose.armR = (-2.6 * cheer + 0.3 * math.cos(T * 6), -0.3)
            pose.head = (0, 0.3 * cheer)
        humanoid_instances(ctx.f, v, (p[0], p[1] + bob, p[2]), yaw, pose, scale=s)


def village_snow(ctx, center, n=3500, fall=1.3, color=(0.5, 0.55, 0.72)):
    return snow(ctx.T, center, n=n, box=(60, 36, 60), color=color, fall=fall)


# =====================================================================  TITLE
def sc_title(ctx, dur):
    t = ctx.t
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.15, fade=scene_fade(t, dur, 2.0, 1.2))
    village_state(ctx)
    star(ctx, 1.0)
    a = 2.15 - t * 0.022
    R = 78 - t * 0.6
    pos = (VC[0] + math.cos(a) * R, 52 - t * 0.5, VC[2] + math.sin(a) * R)
    lookat_cam(ctx, pos, (VC[0], 30 - t * 0.2, VC[2]), 42)
    ctx.f.particles(village_snow(ctx, (VC[0], 30, VC[2] + 30), n=5000))
    ctx.overlay.append(("title", smoothstep(2.0, 4.5, t) * (1 - smoothstep(dur - 3.0, dur - 1.2, t))))
    ctx.once("title_chime", 2.0, "chime_big")
    ctx.once("wind0", 0.0, "wind", dur=dur, level=0.5)


# =====================================================================  S01  Pinoalto
def sc_s01(ctx, dur):
    t = ctx.t
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.15, fade=scene_fade(t, dur, 0.9, 1.0))
    village_state(ctx)
    star(ctx, 1.0)
    i, u, L = shot(t, [0, 13, 25, 34.5], dur)
    if i == 0:
        k = ease_io(u / L)
        pos = vlerp((96, 86, 22), (100, 50, 64), k)
        lookat_cam(ctx, pos, vlerp((96, 30, 100), (96, 24, 104), k), 44)
    elif i == 1:
        k = ease_io(u / L)
        pos = vlerp((62, 34, 142), (128, 32, 140), k)
        lookat_cam(ctx, pos, vlerp((84, 15, 110), (110, 15, 110), k), 42)
    elif i == 2:
        k = ease_io(u / L)
        pos = vlerp((99, 17, 150), (98, 26, 142), k)
        lookat_cam(ctx, pos, vlerp((96, 20, 104), (96, 50, 104), k), 46)
    else:
        k = ease_io(u / L)
        pos = vlerp((96, 52, 152), (96, 78, 186), k)
        lookat_cam(ctx, pos, (96, 26, 100), 46)
    parts = [village_snow(ctx, (ctx.f.cam[0][0], ctx.f.cam[0][1] - 10, ctx.f.cam[0][2] - 25), n=4500)]
    # golden light wave across the roofs
    if t > 33.5:
        age = t - 33.5
        rad = age * 7.5
        a = max(0, 1 - age / 14)
        if rad < 110:
            parts.append(ring(t, (VC[0], 13, VC[2]), rad, n=900, alpha=0.9 * a, size=0.35, height=6))
        ctx.once("wave", 33.6, "shimmer", dur=6)
    ctx.f.particles(cat(*parts))
    ctx.once("chap1", 1.0, "chime_small")
    ctx.overlay.append(("chapter", "I. Pinoalto", smoothstep(1.0, 2.0, t) * (1 - smoothstep(6.0, 7.0, t))))


# =====================================================================  S02  Tilo the apprentice
def sc_s02(ctx, dur):
    t = ctx.t
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.2, fade=scene_fade(t, dur, 0.8, 0.8))
    village_state(ctx)
    star(ctx, 0.0)
    i, u, L = shot(t, [0, 15.0], dur)
    f = ctx.f
    if i == 0:
        # workbench close-up
        hammer = math.sin(u * 2 * math.pi * 1.6)
        pose = Pose(armL=(-0.95, 0.1), armR=(-1.15 - 0.45 * max(hammer, 0), -0.1), head=(0.1 * math.sin(u * 0.5), -0.45),
                    body=(0.12, 0))
        if u > 10.5:  # stops and looks at the toy
            k = ease((u - 10.5) / 1.0)
            pose.armR = (lerp(pose.armR[0], -0.7, k), -0.1)
            pose.head = (0.25 * k, lerp(-0.45, -0.1, k))
        tilo(ctx, WORKBENCH_TILO, math.pi, pose, lantern=False)
        if u <= 10.5 and int(u * 1.6 + 0.25) != ctx.state.get("hammer_k", -1):
            ctx.state["hammer_k"] = int(u * 1.6 + 0.25)
            if u > 0.3:
                ctx.event("hammer")
        f.inst(IDS["toy_train"], (118.3, 13.0, 100.75), rot_y(1.2), 0.07)
        f.inst(IDS["toy_soldier"], (118.85, 13.0, 101.2), rot_y(0.3), 0.06)
        f.inst(IDS["toy_soldier"], (117.9, 13.0, 101.35), rot_y(-0.4), 0.06)
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((114.8, 14.9, 97.6), (115.6, 14.4, 98.6), k), (118.4, 13.15, 101.6), 38)
        sp = None
        if u < 10.5:
            ph = (u * 1.6) % 1.0
            if ph < 0.25:
                sp = sparkles(u, [(118.4, 13.1, 101.3)], color=(2.5, 1.6, 0.5), size=0.025, n_per=6, spread=0.15, rise=0.3)
        f.particles(cat(snow(ctx.T, (116, 18, 100), n=2500, box=(30, 20, 30), color=(0.5, 0.55, 0.72)), sp))
    else:
        # Tilo in the plaza looking at the unlit star
        p = (96.5, ground_at(ctx.wd, 96.5, 121.5), 121.5)
        pose = idle_pose(u)
        pose.head = (0.0, 0.55 * ease(u / 3.0))
        tilo(ctx, p, yaw_to(p, VC), pose, lantern=False)
        k = ease_io(max(0, u - 2.0) / (L - 2.0))
        lookat_cam(ctx, vlerp((98.8, 13.4, 127.5), (98.2, 13.0, 126.4), k), vlerp((96.2, 13.6, 116), (96, 46, 104), k), 46)
        f.particles(cat(village_snow(ctx, (98, 25, 110), n=3500),
                        sparkles(u, [(96, 70, 60)], color=(0.0, 0.0, 0.0), n_per=1)))
    ctx.once("heart_a", 15.5, "music_cue", kind="wonder")


# =====================================================================  S03  The star goes out
SPARK_DIRS = [((96, 55.3, 104), (60, 62, 80), (8, 70, 20)),      # forest (NW)
              ((96, 55.3, 104), (96, 70, 70), (96, 74, -20)),    # caverns (N)
              ((96, 55.3, 104), (130, 62, 80), (184, 70, 20))]   # forge (NE)


def spark_flight(k, u):
    a, b, c = (np.array(x, float) for x in SPARK_DIRS[k])
    u = min(max(u, 0), 1)
    return (1 - u) ** 2 * a + 2 * (1 - u) * u * b + u * u * c


WIND_CURVE = [(66, 70, 18), (84, 64, 44), (106, 60, 70), (98, 57, 94), (96, 55.5, 104)]


def wind_stream(t, progress, n=900, swirl=0.0):
    r = np.random.default_rng(77)
    ph = r.random(n)
    off = (r.random((n, 3)) - 0.5) * 2
    out = np.zeros((n, 9), np.float32)
    k = 0
    for i in range(n):
        u = (ph[i] + t * 0.18) % 1.0
        if u > progress:
            continue
        p = np.array(catmull(WIND_CURVE, u))
        spread = 1.2 + 3.0 * (1 - u)
        q = p + off[i] * spread + np.array((math.sin(t * 2 + i), math.cos(t * 1.7 + i), math.sin(t * 2.3 + i * 0.7))) * 0.6
        if swirl > 0:
            ang = t * 3.0 + i * 0.37
            rad = (0.6 + (i % 7) * 0.35) * (1.3 - 0.8 * swirl)
            sp = np.array(STAR_POS) + np.array((math.cos(ang) * rad, (i % 11 - 5) * 0.3, math.sin(ang) * rad))
            q = q * (1 - swirl) + sp * swirl
        out[k, :3] = q
        out[k, 3] = 0.2 * (1 - 0.65 * swirl)
        out[k, 4:7] = (0.6, 0.8, 1.1)
        out[k, 7] = 0.45 * min(1, (progress - u) * 6 + 0.2)
        out[k, 8] = 0
        k += 1
    return out[:k]


def sc_s03(ctx, dur):
    t = ctx.t
    f = ctx.f
    lead = 1.0
    T_BELL, T_IGN, T_WIND, T_WRAP, T_OUT, T_SPARK, T_DIM = 6.5, 12.0, 16.0, 28.5, 34.6, 37.0, 45.5
    star_p = 0.0
    if t > T_IGN:
        star_p = 0.75 * ease((t - T_IGN) / 3.0)
    if t > T_WRAP:
        star_p *= 1 - 0.5 * ease((t - T_WRAP) / 5) + 0.15 * math.sin(t * 20) * (t < T_OUT)
    if t > T_OUT:
        star_p = 0.0 if t > T_OUT + 0.25 else star_p * (1 - (t - T_OUT) / 0.25)
    dim = 0.0
    flick = 0.0
    if t > T_DIM:
        dim = ease((t - T_DIM) / 2.5)
        flick = 0.5 * (1 - ease((t - T_DIM - 2.5) / 2.0))
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.15, fade=scene_fade(t, dur, 0.8, 1.6))
    village_state(ctx, dim=dim, flicker=flick)
    star(ctx, star_p)
    i, u, L = shot(t, [0, 6.0, 12.0, 16.5, 27.5, 36.5, 45.0], dur)
    tilo_p = (VC[0] + math.cos(1.95) * 15.0, 12.0, VC[2] + math.sin(1.95) * 15.0)
    look_up = 1.0 if t > 4 else ease(t / 4)
    parts = []
    # bell
    bell_sw = 0.0
    if T_BELL < t < T_BELL + 9:
        bell_sw = 0.45 * math.sin((t - T_BELL) * 2.4) * (1 - (t - T_BELL) / 9)
    for n_ in range(4):
        ctx.once("bell%d" % n_, T_BELL + 0.6 + n_ * 1.31, "bell")
    f.inst(IDS["bell"], (80.5, 25.6, 88.5), rot_x(bell_sw), 0.25)
    if i != 1:
        draw_crowd(ctx, look_up=look_up)
        pose = idle_pose(t)
        pose.head = (0, 0.55 * look_up)
        tilo(ctx, tilo_p, yaw_to(tilo_p, VC), pose, lantern=False)
    if i == 0:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 30, 152), (96, 27, 146), k), (96, 24, 104), 44)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((80.5, 23.6, 80.0), (80.5, 24.2, 81.8), k), (80.5, 24.4, 88.5), 44)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 50.5, 121), (96, 52, 117), k), (96, 54.6, 104), 40)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((132, 40, 160), (126, 46, 152), k), vlerp((100, 40, 80), (96, 48, 92), k), 50)
    elif i == 4:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((104, 52, 124), (99, 54.5, 115), k), STAR_POS, 42, shake=0.4 * smoothstep(T_OUT - 2, T_OUT, t))
    elif i == 5:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 64, 168), (96, 70, 176), k), (96, 52, 90), 52)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((101, 19, 142), (100, 20, 139), k), (96, 18, 110), 44)
    # wind
    if t > T_WIND:
        prog = ease((t - T_WIND) / 10.0)
        sw = ease((t - T_WRAP) / 4.0) if t > T_WRAP else 0.0
        if t < T_OUT + 1.5:
            fadew = 1.0 if t < T_OUT else 1 - (t - T_OUT) / 1.5
            ws = wind_stream(t, prog, swirl=sw)
            ws[:, 7] *= fadew * (1 - 0.6 * sw)
            parts.append(ws)
    ctx.once("wind_cold", T_WIND, "cold_wind", dur=T_OUT - T_WIND + 2)
    ctx.once("ignite", T_IGN, "ignite_soft")
    ctx.once("out", T_OUT, "star_out")
    # sparks fly away
    if T_SPARK - 0.6 < t < T_SPARK + 7:
        for k_ in range(3):
            uu = (t - T_SPARK + 0.6 + k_ * 0.25) / 6.0
            if 0 <= uu <= 1:
                fn = (lambda tt, kk=k_: spark_flight(kk, (tt - T_SPARK + 0.6 + kk * 0.25) / 6.0))
                p = fn(t)
                spirit(ctx, p, k_, intensity=1.6, scale=0.16, light_r=14)
                parts.append(trail(fn, t, n=40, dt=0.04, color=SISTER_COLS[k_], size=0.45))
        ctx.once("sparks", T_SPARK - 0.5, "whoosh3")
    parts.append(village_snow(ctx, (ctx.f.cam[0][0], ctx.f.cam[0][1] - 10, ctx.f.cam[0][2] - 25), n=3000))
    f.particles(cat(*parts))
    ctx.overlay.append(("chapter", "II. La noche sin estrella", smoothstep(1.0, 2.0, t) * (1 - smoothstep(6.0, 7.0, t))))


# =====================================================================  S04  Tilo leaves
def sc_s04(ctx, dur):
    t = ctx.t
    f = ctx.f
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.2, fade=scene_fade(t, dur, 0.8, 1.0))
    village_state(ctx, dim=1.0)
    star(ctx, 0.0)
    i, u, L = shot(t, [0, 9.0, 17.2], dur)
    if i == 0:
        draw_crowd(ctx, talk=1.0, face=(96, 12, 125))
        tp = (VC[0] + math.cos(1.95) * 15.0, 12.0, VC[2] + math.sin(1.95) * 15.0)
        pose = idle_pose(t)
        pose.head = (0.2 * math.sin(t * 0.8), 0.15)
        tilo(ctx, tp, yaw_to(tp, (96, 12, 60)), pose, lantern=False)
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((80, 17.5, 125), (81.5, 16.8, 124), k), (93, 13.2, 118), 42)
        for n_ in range(6):
            ctx.once("murmur%d" % n_, 0.4 + n_ * 1.4, "murmur")
        f.particles(village_snow(ctx, (98, 20, 122), n=3000))
    elif i == 1:
        # take the lantern from the workbench
        p = WORKBENCH_TILO
        yaw = math.pi
        grab = ease((u - 2.5) / 1.0)
        pose = idle_pose(t)
        pose.armR = (lerp(-0.1, -1.3, grab) if u < 4.0 else lerp(-1.3, -0.35, ease((u - 4.0) / 0.8)), -0.1)
        lit = ease((u - 5.0) / 1.0)
        holding = u > 3.5
        if u > 6.3:  # turn to the street
            yaw = angle_lerp(math.pi, -math.pi / 2, ease((u - 6.3) / 1.2))
        pts = tilo(ctx, p, yaw, pose, lantern=holding, lit=lit)
        if not holding:
            f.inst(IDS["lantern"], (118.4, 13.0 + 7 * 0.09 * 0.8, 101.0), I3, 0.09 * 0.8, shadow=0, emit=0.0)
        ctx.once("grab", 3.5, "lantern_grab")
        ctx.once("light", 5.0, "lantern_light")
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((114.6, 14.7, 97.8), (115.3, 14.5, 98.4), k), (118.4, 13.3, 101.8), 38)
        f.particles(snow(ctx.T, (116, 18, 100), n=2500, box=(30, 20, 30), color=(0.5, 0.55, 0.72)))
    else:
        path = Path([(96.5, 86.0), (96.5, 70.0), (96.5, 46.0)], speed=2.5, t0=17.2)
        p2, yaw, s, mv = path.state(t)
        pos = (p2[0], ground_at(ctx.wd, p2[0], p2[1]), p2[1])
        ph = s / 0.62 * math.pi
        steps(ctx, "tilo", ph, "snow")
        tilo(ctx, pos, yaw, walk_pose(ph), lit=1.0)
        cam = (pos[0] + 6.0, pos[1] + 10.0, pos[2] + 7.0)
        lookat_cam(ctx, cam, (pos[0], pos[1] + 1.2, pos[2] - 5), 46)
        f.particles(village_snow(ctx, (pos[0], pos[1] + 8, pos[2] - 10), n=3500))
    ctx.overlay.append(("chapter", "III. La puerta del norte", smoothstep(9.3, 10.3, t) * (1 - smoothstep(14.0, 15.0, t))))


# =====================================================================  S05  Frozen forest
LAKE = (88.5, 10.0, 96.5)


def forest_trail_path(wd, t0, speed):
    pts = [(px, pz) for (px, pz) in wd.markers["trail"]]
    pts = pts + [(LAKE[0], LAKE[2] + 13.0), (LAKE[0], LAKE[2] + 1.8)]
    return Path(pts, speed=speed, t0=t0)


def sc_s05(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    apply_env(ctx, NIGHT, plane_y=None, exposure=1.25, fade=scene_fade(t, dur, 1.0, 1.0))
    world_lights(ctx)
    path = forest_trail_path(wd, t0=0.0, speed=2.05)
    # place Tilo along the trail with a time warp so he reaches the lake at ~40s
    tt = t * (path.length / 2.05) / 40.0
    p2, yaw, s, mv = path.state(tt)
    pos = (p2[0], ground_at(wd, p2[0], p2[1]), p2[1])
    on_ice = math.hypot(pos[0] - LAKE[0], (pos[2] - LAKE[2]) * 1.15) < 16
    if on_ice:
        pos = (pos[0], 10.0, pos[2])
    ph = s / 0.62 * math.pi
    if mv:
        steps(ctx, "tilo", ph, "ice" if on_ice else "snow")
    pose = walk_pose(ph) if mv else idle_pose(t)
    tl = tilo(ctx, pos, yaw, pose)
    # glow under the ice
    gl = 0.6 + 0.4 * math.sin(t * 3.0) + 0.3 * math.sin(t * 7.3)
    g_on = 0.4 + 0.6 * smoothstep(28.0, 33.0, t)
    f.glow((LAKE[0], 10.08, LAKE[2]), (2.4 * gl * g_on, 1.8 * gl * g_on, 0.7 * gl * g_on), 0.6)
    f.light((LAKE[0], 10.7, LAKE[2]), (2.5 * gl * g_on, 1.9 * gl * g_on, 0.8 * gl * g_on), 9, 0)
    parts = []
    # golden breadcrumb sparkles on the trail ahead
    ahead = []
    for d_ in (2.5, 5.0, 7.5, 10.0, 13.0, 16.0):
        q, _ = path.at_s(min(s + d_, path.length))
        ahead.append((q[0], ground_at(wd, q[0], q[1]) + 0.15, q[1]))
    parts.append(sparkles(t, ahead, color=(3.0, 2.2, 0.7), size=0.05, n_per=5, spread=0.5, rise=0.25))
    i, u, L = shot(t, [0, 12.0, 19.5, 24.0, 28.0], dur)
    if i == 0:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((88, 62, 176), (90, 40, 168), k), vlerp((88, 20, 120), (pos[0], pos[1] + 2, pos[2] - 8), k), 46)
    elif i == 1:
        cam = (pos[0] - 4.5, pos[1] + 6.5, pos[2] + 9.5)
        lookat_cam(ctx, cam, (pos[0], pos[1] + 1.2, pos[2] - 4), 44)
    elif i == 2:
        ox, oy, oz = wd.markers["owl"]
        head_turn = 0.5 * math.sin(u * 1.4)
        blink = 0.0 if (u % 2.3) < 0.15 else 1.0
        f.inst(IDS["owl"], (ox, oy, oz), rot_y(head_turn * 0.4), 0.11, emit=blink)
        lookat_cam(ctx, vlerp((ox + 2.2, oy + 1.2, oz + 3.2), (ox + 1.8, oy + 1.0, oz + 2.7), ease_io(u / L)),
                   (ox, oy + 0.4, oz), 38)
        ctx.once("owl", 19.9, "owl")
        ctx.once("owl2", 22.0, "owl")
    elif i == 3:
        fwd = np.array((math.sin(yaw), 0, math.cos(yaw)))
        right = np.array((math.cos(yaw), 0, -math.sin(yaw)))
        cam = np.array(pos) + fwd * 2.5 + right * 3.0 + np.array((0, 3.0, 0))
        lookat_cam(ctx, cam, (pos[0], pos[1] + 1.0, pos[2]), 42)
        ctx.once("heart", 24.5, "heartbeat", dur=3.5)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((LAKE[0] + 9, 22, LAKE[2] + 21), (LAKE[0] + 5, 16, LAKE[2] + 12), k),
                   vlerp((LAKE[0], 10, LAKE[2] + 4), (LAKE[0], 10.5, LAKE[2]), k), 44)
        ctx.once("glim", 29.0, "glimmer")
    if ctx.wd.markers.get("owl") and i != 2:
        ox, oy, oz = wd.markers["owl"]
        f.inst(IDS["owl"], (ox, oy, oz), I3, 0.11)
    parts.append(snow(ctx.T, (f.cam[0][0], f.cam[0][1] - 8, f.cam[0][2] - 18), n=3500, box=(50, 30, 50),
                      color=(0.5, 0.55, 0.72), fall=1.1))
    f.particles(cat(*parts))
    ctx.once("wind", 0.0, "wind", dur=dur, level=0.6)
    ctx.overlay.append(("chapter", "IV. El Bosque Escarchado", smoothstep(1.5, 2.5, t) * (1 - smoothstep(6.5, 7.5, t))))


# =====================================================================  S06  Lumi
def lumi_s06(t, head, shoulder):
    """position of Lumi in scene 6"""
    T_RISE, T_CIRC, T_LAND = 10.4, 12.0, 16.4
    ice = np.array((LAKE[0], 10.1, LAKE[2]))
    if t < T_RISE:
        return ice + np.array((0, 0.02 * math.sin(t * 6), 0))
    if t < T_CIRC:
        k = ease((t - T_RISE) / (T_CIRC - T_RISE))
        start = head + np.array((0.7, 0.1, 0))
        return ice * (1 - k) + start * k
    if t < T_LAND:
        k = (t - T_CIRC) / (T_LAND - T_CIRC)
        ang = k * 3 * 2 * math.pi
        r = 0.7
        c = head + np.array((math.cos(ang) * r, 0.1 + 0.15 * math.sin(ang * 2), math.sin(ang) * r))
        if k > 0.85:
            m = ease((k - 0.85) / 0.15)
            c = c * (1 - m) + shoulder * m
        return c
    return shoulder + np.array((0, 0.05 * math.sin(t * 4), 0))


def sc_s06(ctx, dur):
    t = ctx.t
    f = ctx.f
    apply_env(ctx, NIGHT, plane_y=None, exposure=1.25, fade=scene_fade(t, dur, 0.8, 1.0))
    world_lights(ctx)
    tp = (LAKE[0], 10.0, LAKE[2] + 1.8)
    yaw = math.pi
    # kneel then stand
    kneel = 1.0 - ease((t - 10.6) / 1.6)
    rub = math.sin(t * 9) * 0.18 if 4.5 < t < 9.6 else 0.0
    pose = Pose(legL=-1.35 * kneel, legR=-0.25 * kneel, bob=-2.6 * kneel,
                armL=(-1.0 * kneel - 0.05, 0.1), armR=(-1.1 * kneel + rub - 0.05, -0.1),
                head=(0, -0.5 * kneel), body=(0.35 * kneel, 0))
    if t > 12:
        pose = idle_pose(t)
    # head follows lumi after it rises
    head_pt = np.array((tp[0], tp[1] + 1.55, tp[2]))
    shoulder = np.array((tp[0] - 0.42, tp[1] + 1.30, tp[2] - 0.05))
    lp = lumi_s06(t, head_pt, shoulder)
    if 10.4 < t < 17:
        d = lp - head_pt
        hy = math.atan2(d[0], d[2]) - yaw
        hy = (hy + math.pi) % (2 * math.pi) - math.pi
        pose.head = (max(-1.2, min(1.2, hy)), 0.2)
    if t > 17:
        pose.head = (-0.6, 0.0) if t < 25 else (0.0, 0.15)
    tilo(ctx, tp, yaw, pose, lit=0.85)
    # Lumi
    li = 1.0 + 0.3 * math.sin(t * 5)
    if t < 10.4:
        li = 0.6 + 0.4 * ease((t - 2) / 7)
    lumi_pos = lp.copy()
    if t > 25.5:  # talks in front of the face, then darts north-east and back
        k = ease((t - 25.5) / 1.2)
        front = head_pt + np.array((0.0, 0.25, -0.75))
        lumi_pos = shoulder * (1 - k) + front * k
        talk = math.sin(t * 9) * 0.04
        lumi_pos = lumi_pos + np.array((0, talk, 0))
        if t > 31.5:
            m = math.sin(min(1, (t - 31.5) / 3.0) * math.pi)
            lumi_pos = lumi_pos + np.array((1.6, 0.6, -1.4)) * m
    lyaw = math.atan2((head_pt - lumi_pos)[0], (head_pt - lumi_pos)[2]) if t > 16 else t * 2
    spirit(ctx, lumi_pos, 0, intensity=li, scale=0.075, yaw=lyaw, light_r=8)
    parts = []
    if 1.2 < t < 4.5:  # warm breath
        r = np.random.default_rng(3)
        n = 60
        ages = (t - 1.2 - r.random(n) * 2.6)
        ok = (ages > 0) & (ages < 1.5)
        pp = np.zeros((n, 9), np.float32)
        mouth = np.array((tp[0], tp[1] + 0.95, tp[2] - 0.35))
        dirv = np.array((0, -0.5, -1.0))
        pp[:, :3] = mouth + dirv[None, :] * ages[:, None] * 0.5 + (r.random((n, 3)) - 0.5) * 0.2 * ages[:, None]
        pp[:, 3] = 0.05 + 0.08 * np.clip(ages, 0, 2)
        pp[:, 4:7] = (0.75, 0.78, 0.85)
        pp[:, 7] = np.where(ok, 0.35 * (1 - ages / 1.5), 0)
        pp[:, 8] = 0
        parts.append(pp)
        ctx.once("breath", 1.3, "breath")
    if 4.5 < t < 9.6:
        parts.append(sparkles(t, [(LAKE[0], 10.08, LAKE[2])], color=(1.5, 1.8, 2.4), size=0.03, n_per=20, spread=0.5, rise=0.1))
        ctx.once("rub", 4.6, "rub", dur=5.0)
    ctx.once("crack", 9.7, "ice_crack")
    ctx.once("free", 10.4, "chime_rise")
    if 10.4 < t < 17:
        fn = lambda tt: lumi_s06(tt, head_pt, shoulder)
        parts.append(trail(fn, t, n=22, dt=0.03, color=LUMI_COL, size=0.08, alpha=0.8))
    if 21.5 < t < 25:
        parts.append(sparkles(t, [lumi_pos], color=(3, 2.4, 1.0), size=0.025, n_per=24, spread=0.3, rise=0.4))
        ctx.once("laugh", 21.6, "giggle")
    ctx.once("talk", 25.8, "lumi_talk", dur=7.5)
    i, u, L = shot(t, [0, 10.2, 17.2, 25.2], dur)
    if i == 0:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((86.2, 11.9, 93.0), (86.8, 11.6, 93.6), k), (88.45, 10.5, 97.4), 38)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((92.0, 12.2, 93.2), (91.6, 12.0, 94.0), k), (88.5, 11.3, 98.0), 42)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((86.3, 12.0, 96.0), (86.6, 11.9, 96.4), k), (shoulder[0] + 0.25, shoulder[1] + 0.05, shoulder[2] + 0.1), 38)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((91.0, 11.9, 96.0), (90.6, 11.8, 95.6), k), (88.6, 11.45, 97.9), 40)
    parts.append(snow(ctx.T, (f.cam[0][0], f.cam[0][1] - 5, f.cam[0][2] - 12), n=2500, box=(36, 22, 36),
                      color=(0.5, 0.55, 0.72), fall=0.9))
    f.particles(cat(*parts))
    ctx.once("wind", 0.0, "wind", dur=dur, level=0.35)


# =====================================================================  S07  Crystal caverns
def companion(t, base, k=0, radius=0.65, height=1.5, speed=1.6):
    a = t * speed + k * 2.09
    return np.array((base[0] + math.cos(a) * radius, base[1] + height + 0.15 * math.sin(t * 3 + k), base[2] + math.sin(a) * radius))


def sc_s07(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    apply_env(ctx, CAVE, plane_y=None, exposure=1.35, fade=scene_fade(t, dur, 0.9, 1.0), bloom=0.14, bloom_thr=0.8)
    world_lights(ctx)
    ax, ay, az = wd.markers["altar"]
    bounce = wd.markers["bounce"]
    ex, ey, ez = wd.markers["entry"]
    path = Path([(ex, ez), (ex + math.sin(120 * 0.12) * 0 + 0, 112.0), (ax, 100.0), (ax, az + 11.5)], speed=2.0, t0=0.0)
    tt = min(t, 19.5) * path.length / 2.0 / 19.5
    p2, yaw, s, mv = path.state(tt)
    pos = (p2[0], ground_at(wd, p2[0], p2[1]), p2[1])
    ph = s / 0.62 * math.pi
    if mv and t < 19.5:
        steps(ctx, "tilo", ph, "cave")
        pose = walk_pose(ph)
    else:
        pose = idle_pose(t)
        yaw = math.pi
    T_RAISE, T_OPEN, T_OUT = 32.7, 44.0, 48.0
    raise_k = ease((t - T_RAISE) / 1.2)
    if t > T_RAISE:
        pose.armR = (lerp(pose.armR[0], -2.5, raise_k), -0.15)
        pose.head = (0.0, 0.35 * raise_k)
    tl = tilo(ctx, pos, yaw, pose, lit=1.0 + 0.6 * raise_k, light_r=11 + 4 * raise_k)
    # Lumi around Tilo
    lpos = companion(t, pos, 0)
    spirit(ctx, lpos, 0, intensity=1.0, yaw=t)
    # big crystal (petals) with spark inside
    open_k = ease((t - T_OPEN) / 3.2)
    base = np.array((ax, ay, az))
    for k_ in range(6):
        ang = k_ / 6 * 2 * math.pi + 0.3
        lean = lerp(-0.34, 0.95, open_k)
        R = rot_y(ang) @ rot_x(lean)
        p = base + np.array((math.sin(ang), 0, math.cos(ang))) * 1.25
        f.inst(IDS["crystal_petal"], tuple(p), R, 0.2, emit=1.0 + 2.0 * smoothstep(40.5, 44, t))
    sp_in = base + np.array((0, 1.6, 0))
    if t < T_OUT:
        spirit(ctx, sp_in + np.array((0, 0.05 * math.sin(t * 3), 0)), 1, intensity=0.8 + 0.4 * open_k, scale=0.08, light_r=7)
        sec = sp_in
    else:
        k = ease((t - T_OUT) / 2.5)
        spin = (t - T_OUT) * 6
        target = companion(t, pos, 1, radius=0.8)
        sec = sp_in * (1 - k) + target * k + np.array((math.cos(spin), 0.6 * math.sin(k * math.pi), math.sin(spin))) * 1.2 * (1 - k)
        spirit(ctx, sec, 1, intensity=1.3, scale=0.08, yaw=spin, light_r=9)
    parts = []
    # beam bouncing
    if t > T_RAISE + 1.0:
        lantern_pt = np.array(tl["lantern"])
        chain = [lantern_pt] + [np.array(b) for b in bounce] + [sp_in]
        times = [T_RAISE + 1.3, 36.2, 38.0, 39.6, 41.0]
        inten = 1.0 + 1.5 * smoothstep(41.0, 44.0, t) - 0.8 * smoothstep(49, 52, t)
        for j in range(len(chain) - 1):
            ts = times[j]
            if t < ts:
                break
            grow = ease((t - ts) / 0.9)
            a_, b_ = chain[j], chain[j + 1]
            e_ = a_ + (b_ - a_) * grow
            f.beam(tuple(a_), tuple(e_), (2.6 * inten, 1.9 * inten, 0.7 * inten), 0.07)
            f.beam(tuple(a_), tuple(e_), (0.5 * inten, 0.35 * inten, 0.12 * inten), 0.35)
            if j > 0:
                f.light(tuple(a_ + np.array((0, 0.5, 0))), (2.5 * inten, 1.8 * inten, 0.6 * inten), 8, 0)
                f.glow(tuple(a_), (1.5 * inten, 1.1 * inten, 0.4 * inten), 0.5)
            ctx.once("beam%d" % j, ts, "beam_hit", idx=j)
            if t > 41.0:  # golden river particles flowing along the beams
                n = 40
                uu = (np.arange(n) / n + t * 0.6) % 1.0
                pp = np.zeros((n, 9), np.float32)
                pp[:, :3] = a_[None, :] + (b_ - a_)[None, :] * uu[:, None]
                pp[:, 3] = 0.08
                pp[:, 4:7] = (3.0, 2.2, 0.8)
                pp[:, 7] = 0.8 * min(1, (t - 41) / 1.5)
                pp[:, 8] = 1
                parts.append(pp)
    ctx.once("open", T_OPEN, "crystal_open")
    ctx.once("out", T_OUT, "chime_rise")
    ctx.once("whisper", 26.3, "whisper")
    ctx.once("cave_amb", 0.0, "cave_ambience", dur=dur)
    if t > T_OUT:
        fn = (lambda tt: (sp_in * (1 - ease((tt - T_OUT) / 2.5)) + companion(tt, pos, 1, radius=0.8) * ease((tt - T_OUT) / 2.5)
                          + np.array((math.cos((tt - T_OUT) * 6), 0.6 * math.sin(ease((tt - T_OUT) / 2.5) * math.pi), math.sin((tt - T_OUT) * 6))) * 1.2 * (1 - ease((tt - T_OUT) / 2.5))))
        parts.append(trail(fn, t, n=26, dt=0.03, color=SISTER_COLS[1], size=0.09))
    # floating dust motes
    parts.append(sparkles(t, [(ax, ay + 6, az + 6)], color=(0.4, 0.7, 1.4), size=0.04, n_per=160, spread=14, rise=2.0, twinkle=1.5))
    i, u, L = shot(t, [0, 9.0, 19.8, 29.0, 41.0, 48.0], dur)
    if i == 0:
        cam = (pos[0] + 3.0, pos[1] + 7.0, pos[2] + 9.0)
        lookat_cam(ctx, cam, (pos[0], pos[1] + 1, pos[2] - 6), 46)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((ax + 2, ay + 21, az + 38), (ax - 9, ay + 17, az + 27), k), vlerp((ax, ay + 2, az + 16), (ax, ay + 2, az + 4), k), 50)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((ax + 6.5, ay + 5.0, az + 15.5), (ax + 4.5, ay + 4.2, az + 13.5), k), (ax, ay + 2.0, az + 2), 42)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((ax + 2, ay + 26, az + 34), (ax - 2, ay + 30, az + 30), k), (ax, ay + 2, az + 2), 52)
    elif i == 4:
        k = ease_io(u / L)
        a = 0.9 + k * 0.9
        lookat_cam(ctx, (ax + math.sin(a) * 13, ay + 7 - 2 * k, az + math.cos(a) * 13), (ax, ay + 2.0, az), 44)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((pos[0] + 5, pos[1] + 3.5, pos[2] + 4), (pos[0] + 4, pos[1] + 3.0, pos[2] + 3.2), k), (pos[0], pos[1] + 1.6, pos[2] - 1.5), 46)
    f.particles(cat(*parts))
    ctx.overlay.append(("chapter", "V. Las Cavernas de Cristal", smoothstep(1.5, 2.5, t) * (1 - smoothstep(6.5, 7.5, t))))


# =====================================================================  S08  Forgotten forge
def golem_seated(ctx, t, shiver=0.0, smile=False, eye=1.0, scarf=False, open_k=0.0, head=(0.0, 0.0)):
    wd = ctx.wd
    sx, sy, sz = wd.markers["seat"]
    gp = (sx, sy - 0.44, sz)
    arm = lerp(-0.95, -0.35, open_k)
    ain = lerp(0.38, -0.25, open_k)
    return golem_instances(ctx.f, gp, 0.0, sit=1.0, arm_pitch=(arm, arm), arm_in=ain, head=head, smile=smile, eye=eye,
                           scarf=scarf, shiver=shiver, t=ctx.T)


def sc_s08(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    apply_env(ctx, FORGE, plane_y=None, exposure=1.25, fade=scene_fade(t, dur, 0.9, 1.0), bloom=0.13, bloom_thr=0.85)
    world_lights(ctx)
    ex, ey, ez = wd.markers["entry"]
    sx, sy, sz = wd.markers["seat"]
    path = Path([(ex, ez), (ex, 104.0), (ex, 94.0), (74.5, 86.5)], speed=2.0, t0=0.0)
    tt = min(t, 26.0) * path.length / 2.0 / 26.0
    p2, yaw, s, mv = path.state(tt)
    pos = (p2[0], ground_at(wd, p2[0], p2[1]), p2[1])
    ph = s / 0.62 * math.pi
    on_bridge = 94 < pos[2] < 102
    if mv and t < 26:
        steps(ctx, "tilo", ph, "wood" if on_bridge else "stone")
        pose = walk_pose(ph)
    else:
        pose = idle_pose(t)
        pose.head = (0.0, 0.35)
        yaw = yaw_to(pos, (sx, 0, sz))
    tilo(ctx, pos, yaw, pose)
    spirit(ctx, companion(t, pos, 0), 0, intensity=1.0, yaw=t)
    spirit(ctx, companion(t, pos, 1, radius=0.8), 1, intensity=1.0, yaw=-t)
    g = golem_seated(ctx, t, eye=0.35)
    cup = np.array(g["cup"])
    spirit(ctx, cup + np.array((0, 0.1, 0)), 2, intensity=0.9 + 0.2 * math.sin(t * 2), scale=0.08, light_r=7)
    parts = [sparkles(t, [(72, 13, 72)], color=(3.0, 1.0, 0.2), size=0.05, n_per=200, spread=30, rise=6.0, twinkle=3)]
    i, u, L = shot(t, [0, 9.0, 15.0, 22.0], dur)
    if i == 0:
        cam = (pos[0] - 5.5, pos[1] + 7.5, pos[2] + 8.0)
        lookat_cam(ctx, cam, (pos[0], pos[1] + 1, pos[2] - 6), 46)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((60, 18, 98), (84, 18, 98), k), vlerp((66, 17, 80), (78, 17, 80), k), 46)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((86, 24, 100), (84, 23, 97), k), (pos[0], 12.5, pos[2] - 2), 48)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((73.4, 14.6, 94.5), (74.2, 14.9, 90.5), k), vlerp((76.5, 15.5, 80), (77.2, 16.6, 78.5), k), 44)
    f.particles(cat(*parts))
    ctx.once("forge_amb", 0.0, "forge_ambience", dur=dur)
    ctx.once("golem_reveal", 22.4, "music_cue", kind="golem")
    ctx.overlay.append(("chapter", "VI. La Forja Olvidada", smoothstep(1.5, 2.5, t) * (1 - smoothstep(6.5, 7.5, t))))


# =====================================================================  S09  The golem
def sc_s09(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    apply_env(ctx, FORGE, plane_y=None, exposure=1.25, fade=scene_fade(t, dur, 0.8, 1.2), bloom=0.13, bloom_thr=0.85)
    world_lights(ctx)
    sx, sy, sz = wd.markers["seat"]
    stx, sty, stz = wd.markers["step"]
    T_SCARF_OFF, T_WALK, T_CLIMB, T_WRAP, T_SMILE, T_OPEN, T_FLY = 24.2, 25.0, 27.6, 30.6, 38.9, 41.5, 43.0
    base_pos = np.array((74.5, 12.0, 86.5))
    pos = base_pos.copy()
    if t < 2.5:  # step back, afraid
        pos = base_pos + np.array((0, 0, 0.6)) * ease(t / 1.2)
    else:
        pos = base_pos + np.array((0, 0, 0.6))
    scarf_on = t < T_SCARF_OFF
    pose = idle_pose(t)
    yaw = yaw_to(pos, (sx, 0, sz))
    mv = False
    if t >= T_WALK:
        path = Path([(pos[0], pos[2]), (stx, stz + 1.2), (stx, stz)], speed=1.6, t0=T_WALK)
        p2, yaw2, s, mv = path.state(t)
        pos = np.array((p2[0], 12.0, p2[1]))
        if mv:
            yaw = yaw2
            ph = s / 0.62 * math.pi
            pose = walk_pose(ph)
            steps(ctx, "tilo", ph, "stone")
        else:
            yaw = yaw_to(pos, (sx, 0, sz))
    if t >= T_CLIMB:
        k = ease((t - T_CLIMB) / 0.7)
        pos = np.array((stx, 12.0 + 1.0 * k, stz - 0.0))
        if T_CLIMB + 0.7 < t < T_WRAP + 1.6:  # tiptoe, arms up
            m = ease((t - T_CLIMB - 0.7) / 0.8)
            pose = Pose(armL=(-2.7 * m, 0.25), armR=(-2.7 * m, -0.25), head=(0, 0.5 * m), bob=0.6 * m)
        elif t >= T_WRAP + 1.6:
            pose = idle_pose(t)
            pose.head = (0, 0.45)
    if 1.0 < t < 2.5:
        pose.armL = (-0.6, 0.3)
        pose.armR = (-0.6, -0.3)
    if T_SCARF_OFF - 0.6 < t < T_WALK:  # pulling off the scarf
        m = math.sin((t - T_SCARF_OFF + 0.6) / 1.4 * math.pi)
        pose.armR = (-2.2 * m, -0.4)
    tl = tilo(ctx, tuple(pos), yaw, pose, scarf=scarf_on)
    # scarf carried in the hand
    if T_SCARF_OFF <= t < T_WRAP:
        hr = tl["handR"]
        f.inst(IDS["scarf_tail"], tuple(hr), rot_y(yaw) @ rot_z(0.3), 0.11)
    shiver = 1.0 if 2.5 < t < T_WRAP + 1 else (0.3 if t < 2.5 else 0.0)
    if t > T_WRAP:
        shiver *= max(0.0, 1 - (t - T_WRAP) / 1.0)
    talk = 10.1 < t < 21.6
    head = (0.0, 0.0)
    if talk:
        head = (0.08 * math.sin(t * 1.3), -0.05 + 0.07 * math.sin(t * 4.5))
    if t > 31:
        head = (0.0, -0.18)
    smile = t > T_SMILE
    eye = 0.35 + 1.3 * smoothstep(T_SMILE - 0.5, T_SMILE + 1.5, t)
    open_k = ease((t - T_OPEN) / 1.5)
    g = golem_seated(ctx, t, shiver=shiver, smile=smile, eye=eye, scarf=t > T_WRAP, open_k=open_k, head=head)
    cup = np.array(g["cup"])
    parts = []
    # spirits
    lpos = companion(t, pos, 0)
    spos = companion(t, pos, 1, radius=0.8)
    spirit(ctx, lpos, 0, intensity=1.0, yaw=t)
    spirit(ctx, spos, 1, intensity=1.0, yaw=-t)
    if t < T_FLY:
        third = cup + np.array((0, 0.1 + 0.25 * open_k, 0))
    else:
        k = ease((t - T_FLY) / 2.2)
        dst = companion(t, pos, 2, radius=0.9)
        third = (cup + np.array((0, 0.35, 0))) * (1 - k) + dst * k + np.array((0, 1.2, 0)) * math.sin(k * math.pi)
        fn = (lambda tt: (cup + np.array((0, 0.35, 0))) * (1 - ease((tt - T_FLY) / 2.2)) + companion(tt, pos, 2, radius=0.9) * ease((tt - T_FLY) / 2.2) + np.array((0, 1.2, 0)) * math.sin(ease((tt - T_FLY) / 2.2) * math.pi))
        parts.append(trail(fn, t, n=24, dt=0.03, color=SISTER_COLS[2], size=0.09))
    spirit(ctx, third, 2, intensity=1.0 + 0.3 * math.sin(t * 2), scale=0.08, light_r=8)
    if T_WRAP - 0.2 < t < T_WRAP + 2.5:
        parts.append(sparkles(t, [g["neck"]], color=(3.0, 1.6, 1.4), size=0.05, n_per=50, spread=1.6, rise=1.2))
    if T_SMILE < t < T_SMILE + 3:
        parts.append(sparkles(t, [g["head"]], color=(3.0, 2.0, 0.8), size=0.05, n_per=30, spread=1.4, rise=1.0))
    parts.append(sparkles(t, [(72, 13, 72)], color=(3.0, 1.0, 0.2), size=0.05, n_per=200, spread=30, rise=6.0, twinkle=3))
    ctx.once("rumble1", 10.2, "golem_voice", dur=6.3)
    ctx.once("rumble2", 17.2, "golem_voice", dur=4.3)
    ctx.once("shiver", 2.8, "stone_shiver", dur=T_WRAP - 2.8)
    ctx.once("scarf", T_SCARF_OFF - 0.4, "cloth")
    ctx.once("wrap", T_WRAP - 0.2, "cloth")
    ctx.once("wrapchime", T_WRAP + 0.2, "chime_small")
    ctx.once("smile", T_SMILE, "warm_swell")
    ctx.once("fly", T_FLY, "chime_rise")
    ctx.once("forge_amb", 0.0, "forge_ambience", dur=dur)
    i, u, L = shot(t, [0, 3.0, 10.0, 22.2, 32.6, 38.6, 46.0], dur)
    gh = np.array(g["head"])
    if i == 0:
        lookat_cam(ctx, (70.0, 14.4, 88.0), (75.5, 14.2, 83.5), 44)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((81.5, 16.0, 86.5), (80.8, 16.4, 85.0), k), (77.5, 16.2, 78.5), 40, shake=0.3)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((73.2, 14.1, 90.2), (73.6, 14.3, 89.2), k), (77.4, 16.7, 78.6), 40)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((66.5, 18.0, 88.0), (67.5, 17.5, 87.0), k), (76.0, 15.3, 80.0), 46)
    elif i == 4:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((70.5, 15.0, 84.0), (70.8, 15.2, 83.2), k), (75.5, 15.4, 80.5), 44)
    elif i == 5:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((78.5, 15.2, 87.6), (78.0, 15.0, 86.5), k), (77.3, 16.0, 78.8), 44)
    else:
        k = ease_io(u / L)
        a = 0.4 + k * 0.6
        lookat_cam(ctx, (stx + math.sin(a) * 6, 15.5, stz + math.cos(a) * 6), (stx + 1, 14.5, stz - 2.5), 46)
    f.particles(cat(*parts))


# =====================================================================  S10  The Hollow Winter
SUMMIT = (88.5, 62.0, 88.5)
VORTEX = np.array((88.5, 62.0, 81.0))
_vr = np.random.default_rng(99)
VCUBES = [(i * 2.39996, _vr.random(), 0.45 + _vr.random() * 0.75, _vr.random() * 6.28, 0.6 + 0.8 * _vr.random()) for i in range(70)]


def vortex(ctx, t, form, light=0.0, dissolve=0.0, speed=1.0, eyes=1.0):
    """form: 0..1 rising; light: 0..1 inner light; dissolve: 0..1"""
    f = ctx.f
    H = 13.0
    parts = []
    for i, (ga, hu, sz, ph, sp) in enumerate(VCUBES):
        h = hu * H
        if hu > form:
            continue
        d_i = (i % 10) / 10.0
        vis = 1.0 - smoothstep(d_i * 0.7, d_i * 0.7 + 0.3, dissolve)
        if vis <= 0.01:
            continue
        r = 1.2 + h * 0.42 + 0.4 * math.sin(t * 1.3 + ph)
        a = ga + t * speed * (1.4 - hu * 0.6) * sp
        p = VORTEX + np.array((math.cos(a) * r, h + 0.6 * math.sin(t * 2 + ph), math.sin(a) * r))
        R = rot_y(a * 1.7 + ph) @ rot_x(t * sp + ph)
        tint = vlerp((0.25, 0.3, 0.45), (1.0, 1.0, 1.0), light)
        f.inst(IDS["frost_cube"], tuple(p), R, sz * vis, shadow=0, emit=light * 0.6, tint=tint)
    # eyes
    if eyes > 0.01 and form > 0.85:
        ey = VORTEX + np.array((0, 9.0, 5.2))
        for sx in (-1.3, 1.3):
            p = ey + np.array((sx, 0, 0))
            f.inst(IDS["wraith_eye"], tuple(p), rot_z(-sx * 0.25), 0.35, shadow=0, emit=eyes)
            f.glow(tuple(p), (0.8 * eyes, 1.2 * eyes, 1.6 * eyes), 0.6)
    if light > 0.01:
        f.light(tuple(VORTEX + np.array((0, 6, 0))), (1.2 * light, 1.8 * light, 2.7 * light), 24, 0)
        f.glow(tuple(VORTEX + np.array((0, 6, 0))), (0.35 * light, 0.55 * light, 0.85 * light), 3.0)
    return parts


def vortex_snow(t, intensity, center):
    s = snow(t, center, n=int(4000 * intensity) + 200, box=(40, 26, 40), wind=(14 * intensity, -2, 4 * intensity),
             fall=1.0, color=(0.55, 0.62, 0.8), alpha=0.75, size=1.2)
    return s


def sc_s10(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    apply_env(ctx, PEAK, plane_y=4.0, exposure=1.25, fade=scene_fade(t, dur, 0.9, 1.0))
    path = Path([(88.5, 118.0), (88.5, 108.0), (88.5, 99.0), (88.5, 94.0)], speed=1.7, t0=0.0)
    tt = min(t, 9.5) * path.length / 1.7 / 9.5
    p2, yaw, s, mv = path.state(tt)
    pos = (p2[0], ground_at(wd, p2[0], p2[1]), p2[1])
    ph = s / 0.62 * math.pi
    lean = 0.0
    if mv and t < 9.5:
        steps(ctx, "tilo", ph, "snow")
        pose = walk_pose(ph)
        pose.body = (0.25, 0)
    else:
        pose = idle_pose(t)
        yaw = math.pi
        if 22 < t < 34:  # braces against the wind
            m = ease((t - 22) / 1.0) * (1 - ease((t - 33) / 1.0))
            pose.body = (0.3 * m, 0)
            pose.armL = (-1.9 * m, 0.4 * m)
            pose.head = (0, -0.3 * m)
        if t > 34:
            m = ease((t - 34) / 1.5)
            pose.armR = (-2.4 * m, -0.1)
            pose.head = (0, 0.35 * m)
    raise_k = ease((t - 34) / 1.5) if t > 34 else 0.0
    lit = 1.6 + 0.8 * raise_k
    tl = tilo(ctx, pos, yaw, pose, lit=lit, light_r=10 + 8 * raise_k, light_col=(3.0, 2.2, 1.0),
              wave=math.sin(ctx.T * 9) * 0.5)
    # the three sparks are inside the lantern: extra coloured glows
    lp = np.array(tl["lantern"])
    for k_ in range(3):
        a = t * 3 + k_ * 2.09
        q = lp + np.array((math.cos(a) * 0.06, 0.02 * math.sin(t * 5 + k_), math.sin(a) * 0.06))
        f.glow(tuple(q), tuple(c * 0.25 for c in SISTER_COLS[k_]), 0.1)
    form = ease((t - 8.5) / 5.0)
    eyes = ease((t - 14.5) / 1.0)
    roar = 17 < t < 25
    vortex(ctx, t, form, light=0.0, speed=1.0 + 0.6 * roar, eyes=eyes * (1.0 + 0.6 * roar * (0.5 + 0.5 * math.sin(t * 12))))
    ctx.once("rise", 8.5, "vortex_rise")
    ctx.once("roar1", 19.0, "roar")
    ctx.once("roar2", 21.8, "roar")
    ctx.once("blizzard", 0.0, "blizzard", dur=dur, level=1.0)
    ctx.once("warm", 34.5, "warm_swell")
    intensity = 0.35 + 0.65 * form
    parts = [vortex_snow(ctx.T, intensity, (pos[0], pos[1] + 6, pos[2] - 6))]
    if t > 34:  # warm bubble of light around Tilo
        parts.append(sparkles(t, [lp], color=(3.0, 2.2, 0.8), size=0.05, n_per=40, spread=1.5 + raise_k, rise=0.6))
    i, u, L = shot(t, [0, 8.0, 17.0, 25.0, 34.0], dur)
    if i == 0:
        cam = (pos[0] + 5.0, pos[1] + 7.0, pos[2] + 10.0)
        lookat_cam(ctx, cam, (pos[0], pos[1] + 1.0, pos[2] - 4), 46)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((92.5, 65.0, 104.0), (91.5, 64.5, 101.0), k), (88.5, 68.0 + 2 * k, 84.0), 54)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((89.5, 69.5, 95.0), (89.0, 70.0, 93.5), k), (88.5, 70.5, 84.0), 46, shake=1.5 if roar else 0.3)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((87.2, 63.4, 91.2), (87.4, 63.3, 91.0), k), (pos[0], pos[1] + 1.2, pos[2]), 40, shake=0.5)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96.5, 64.8, 99.5), (97.5, 65.3, 100.5), k), (88.5, 66.5, 86.5), 50)
    f.particles(cat(*parts))
    ctx.overlay.append(("chapter", "VII. El Invierno Hueco", smoothstep(1.5, 2.5, t) * (1 - smoothstep(6.5, 7.5, t))))


# =====================================================================  S11  Dissolving into snow
def sc_s11(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    env = mix_env(PEAK, dict(PEAK, aurora=1.8, fogden=0.004), smoothstep(20, 30, t))
    apply_env(ctx, env, plane_y=4.0, exposure=1.25, fade=scene_fade(t, dur, 0.6, 1.8))
    pos = (88.5, ground_at(wd, 88.5, 94.0), 94.0)
    pose = idle_pose(t)
    pose.armR = (-2.4, -0.1)
    pose.head = (0, 0.35)
    tl = tilo(ctx, pos, math.pi, pose, lit=1.6, light_col=(3.0, 2.2, 1.0), wave=math.sin(ctx.T * 6) * 0.3)
    lp = np.array(tl["lantern"])
    T_OUT, T_LIGHT, T_DIS = 1.6, 11.0, 22.3
    light = ease((t - T_LIGHT) / 6.0)
    dis = ease((t - T_DIS) / 7.0)
    vortex(ctx, t, 1.0, light=light, dissolve=dis, speed=lerp(1.0, 0.35, light), eyes=max(0, 1 - light * 1.3))
    parts = []
    # three sparks circle the vortex
    for k_ in range(3):
        def sp_pos(tt, kk=k_):
            u = ease((tt - T_OUT) / 2.5)
            a = tt * 1.6 + kk * 2.09
            rr = 4.2 + 1.5 * math.sin(tt * 0.7 + kk)
            orbit = VORTEX + np.array((math.cos(a) * rr, 4.0 + kk * 2.5 + math.sin(tt * 1.1 + kk), math.sin(a) * rr))
            if tt > T_DIS:
                m = ease((tt - T_DIS) / 3.0)
                orbit = orbit * (1 - m) + (VORTEX + np.array((0, 6 + kk, 0))) * m
            return lp * (1 - u) + orbit * u
        if t > T_OUT:
            p = sp_pos(t)
            inten = 1.4 * (1 - smoothstep(T_DIS + 2.0, T_DIS + 5, t))
            spirit(ctx, p, k_, intensity=inten, scale=0.09, light_r=12, yaw=t * 2)
            if inten > 0.05:
                parts.append(trail(sp_pos, t, n=30, dt=0.04, color=SISTER_COLS[k_], size=0.18, alpha=inten / 1.4))
    ctx.once("open", 0.8, "lantern_open")
    ctx.once("spk", T_OUT, "whoosh3")
    ctx.once("light", T_LIGHT, "inner_light", dur=10)
    ctx.once("sigh", 17.5, "sigh")
    ctx.once("dis", T_DIS, "dissolve", dur=9)
    ctx.once("bl", 0.0, "blizzard", dur=18, level=0.7)
    # glowing snow
    if t > T_DIS - 1:
        g = smoothstep(T_DIS - 1, T_DIS + 4, t)
        gs = snow(ctx.T, (88.5, 64, 88.5), n=int(3500 * g) + 10, box=(90, 50, 90), wind=(0.6, 0, 0.2), fall=0.9,
                  color=(1.2, 1.6, 2.6), alpha=0.7 * g, size=1.4, additive=True)
        parts.append(gs)
    if t < T_DIS + 3:
        parts.append(vortex_snow(ctx.T, 1.0 - light * 0.8, (pos[0], pos[1] + 6, pos[2] - 6)))
    i, u, L = shot(t, [0, 3.2, 11.0, 22.0, 31.0], dur)
    if i == 0:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((lp[0] + 1.6, lp[1] - 0.2, lp[2] + 2.2), (lp[0] + 1.8, lp[1] + 0.3, lp[2] + 2.8), k), tuple(lp + np.array((0, 0.2, -1.5))), 40)
    elif i == 1:
        k = ease_io(u / L)
        a = 0.3 + k * 0.8
        lookat_cam(ctx, (88.5 + math.sin(a) * 20, 70 + 2 * k, 81 + math.cos(a) * 20), (88.5, 68, 82), 50)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 66, 98), (94, 68, 95), k), (88.5, 69, 82), 48)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 70, 104), (104, 82, 122), k), vlerp((88.5, 68, 84), (88.5, 56, 82), k), 52)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((104, 82, 122), (108, 86, 128), k), (86, 48, 80), 54)
    f.particles(cat(*parts))


# =====================================================================  S12  Return and the star relit
def sc_s12(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    T_LIGHT = 30.0
    env = mix_env(NIGHT, DAWN, 0.35 + 0.65 * smoothstep(T_LIGHT, T_LIGHT + 10, t))
    flash = math.exp(-max(0, t - T_LIGHT) * 2.0) * (t > T_LIGHT)
    apply_env(ctx, env, plane_y=11.0, exposure=1.15 + 0.6 * flash, fade=scene_fade(t, dur, 0.8, 1.5))
    # light wave: village relights
    wave = smoothstep(T_LIGHT + 3, T_LIGHT + 9, t)
    village_state(ctx, dim=1.0 - wave, lights_boost=1.0 + 0.25 * wave)
    star_p = 0.0
    if t > T_LIGHT:
        star_p = 1.0 + 1.6 * flash
    star(ctx, star_p)
    # Tilo path: gate -> plaza -> climb tree
    T_CLIMB0, T_CLIMB1 = 17.3, 24.5
    path = Path([(96.5, 46.0), (96.5, 70.0), (96.5, 89.5)], speed=2.4, t0=0.5)
    climbing = False
    if t < T_CLIMB0:
        p2, yaw, s, mv = path.state(t)
        pos = (p2[0], ground_at(wd, p2[0], p2[1]), p2[1])
        ph = s / 0.62 * math.pi
        if mv:
            steps(ctx, "tilo", ph, "snow")
            pose = walk_pose(ph)
        else:
            pose = idle_pose(t)
            pose.head = (0, 0.5)
    else:
        climbing = t < T_CLIMB1
        k = ease_io((t - T_CLIMB0) / (T_CLIMB1 - T_CLIMB0))
        y = lerp(12.0, 52.6, k)
        frac = (52 - y) / 36.0
        r = 1.2 + max(frac, 0) * 10.5 + 0.9
        ang = lerp(-math.pi / 2, -math.pi / 2 + 1.2, k)
        pos = (VC[0] + math.cos(ang) * r, y, VC[2] + math.sin(ang) * r)
        yaw = yaw_to(pos, VC)
        ph = (t - T_CLIMB0) * 7
        if climbing:
            pose = Pose(armL=(-2.6 + 0.5 * math.sin(ph), 0.2), armR=(-2.6 - 0.5 * math.sin(ph), -0.2),
                        legL=-0.6 * max(0, math.sin(ph)), legR=-0.6 * max(0, -math.sin(ph)), head=(0, 0.4))
            if int(ph / math.pi) != ctx.state.get("climb_k"):
                ctx.state["climb_k"] = int(ph / math.pi)
                ctx.event("rustle")
        else:
            pose = idle_pose(t)
            pose.head = (0, 0.45)
            yaw = 0.0
            pos = (VC[0] + 0.4, 53.0, VC[2] - 1.6)
            if t > T_LIGHT + 1:
                pose.armL = (-2.6, 0.3)
                pose.armR = (-2.6, -0.3)
    lit = 1.0 if t < 25.0 else max(0.25, 1 - (t - 25) / 1.5)
    tl = tilo(ctx, pos, yaw, pose, lit=lit)
    # golem walking behind
    gpath = Path([(96.5, 44.0), (96.5, 78.0)], speed=1.7, t0=3.0)
    g2, gyaw, gs, gmv = gpath.state(t)
    gpos = (g2[0], ground_at(wd, g2[0], g2[1]), g2[1])
    gph = gs / 1.4 * math.pi
    golem_instances(f, gpos, gyaw if gmv else math.pi * 0 + 0.0, sit=0.0, arm_pitch=(0.0, 0.0), arm_in=0.0,
                    smile=True, eye=1.4, scarf=True, t=ctx.T, walk_phase=gph if gmv else None)
    if gmv:
        k_ = int(gph / math.pi)
        if k_ != ctx.state.get("gstep"):
            ctx.state["gstep"] = k_
            ctx.event("golem_step")
    # crowd turns toward the gate, then cheers
    cheer = smoothstep(T_LIGHT + 2, T_LIGHT + 4, t)
    draw_crowd(ctx, look_up=smoothstep(17, 20, t), cheer=cheer, turn=((96, 12, 60), 1.0 - smoothstep(16, 19, t)))
    parts = []
    # spirits fly from the lantern to the star
    lp = np.array(tl["lantern"])
    T_FLY = 25.1
    for k_ in range(3):
        if t < T_FLY:
            continue
        u = ease((t - T_FLY - k_ * 0.25) / 3.2)
        if u >= 1:
            continue
        a = u * 4 + k_ * 2.09
        p = lp * (1 - u) + np.array(STAR_POS) * u + np.array((math.cos(a), 0.8 * math.sin(u * math.pi), math.sin(a))) * 1.6 * math.sin(u * math.pi)
        spirit(ctx, p, k_, intensity=1.3, scale=0.08, light_r=10, yaw=a)
    if T_LIGHT - 0.2 < t < T_LIGHT + 12:
        age = t - T_LIGHT
        if age > 0:
            parts.append(ring(t, (VC[0], 13, VC[2]), age * 12, n=1200, alpha=max(0, 1 - age / 12) * 1.2, size=0.45, height=8))
            parts.append(burst(age, STAR_POS, (3.0, 2.3, 0.9), n=160, speed=16, seed=8, size=0.25, gravity=0.6, life=3.5))
    ctx.once("fly", T_FLY, "whoosh3")
    ctx.once("light", T_LIGHT, "star_ignite")
    ctx.once("cheer", T_LIGHT + 2.2, "cheer", dur=9)
    ctx.once("bells", T_LIGHT + 3.0, "bells_peal", dur=10)
    i, u, L = shot(t, [0, 8.4, 17.0, 25.0, 33.5, 45.0], dur)
    if i == 0:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((100, 22, 40), (100, 21, 52), k), (pos[0], pos[1] + 1, pos[2] + 6), 46)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((112, 22, 90), (110, 23, 86), k), vlerp((96, 15, 72), (96, 15, 80), k), 50)
    elif i == 2:
        k = ease_io(u / L)
        a = -math.pi / 2 + 0.2 + k * 1.0
        R = 24 - 6 * k
        lookat_cam(ctx, (VC[0] + math.cos(a) * R, pos[1] + 3, VC[2] + math.sin(a) * R), (pos[0], pos[1] + 0.8, pos[2]), 48)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((99, 56, 95.5), (100.0, 56.5, 94.0), k), (96.2, 54.4, 103.0), 46)
    elif i == 4:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 60, 128), (96, 86, 186), k), vlerp((96, 52, 104), (96, 24, 92), k), 52)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 17, 138), (96, 18, 134), k), (96, 20, 110), 46)
    parts.append(village_snow(ctx, (f.cam[0][0], f.cam[0][1] - 10, f.cam[0][2] - 25), n=2500))
    f.particles(cat(*parts))
    ctx.overlay.append(("chapter", "VIII. La Estrella del Alba", smoothstep(1.0, 2.0, t) * (1 - smoothstep(6.0, 7.0, t))))


# =====================================================================  S13  Celebration
FIREWORKS = []
_fr = np.random.default_rng(31)
_t = 0.5
while _t < 60:
    col = [(3.2, 0.6, 0.4), (0.6, 3.0, 0.8), (3.0, 2.4, 0.6), (0.7, 1.4, 3.4), (2.8, 0.8, 2.8), (3.0, 3.0, 3.0)][_fr.integers(6)]
    FIREWORKS.append((_t, (96 + _fr.normal() * 18, 46 + _fr.random() * 18, 96 + _fr.normal() * 14), col, int(_fr.integers(100000))))
    _t += 0.7 + _fr.random() * 1.4


def fireworks(ctx, t, center_bias=None, scale=1.0):
    parts = []
    f = ctx.f
    for (t0, c, col, seed) in FIREWORKS:
        age = t - t0
        if -1.2 < age < 0:  # rocket going up
            k = (age + 1.2) / 1.2
            p = (c[0], 14 + (c[1] - 14) * ease(k), c[2])
            parts.append(np.array([[p[0], p[1], p[2], 0.12, 3, 2.2, 1.2, 1.0, 1]], np.float32))
        if 0 <= age < 3.0:
            parts.append(burst(age, c, col, n=110, speed=9, seed=seed % 1000, size=0.22))
            if age < 0.6:
                fl = math.exp(-age * 5)
                f.light(c, tuple(x * 6 * fl for x in col), 45, 0)
                f.glow(c, tuple(x * 1.0 * fl for x in col), 2.5)
        ctx.once("fwl%d" % seed, t0 - 1.2, "firework_launch")
        ctx.once("fwb%d" % seed, t0, "firework_boom", dist=0.5)
    return parts


def sc_s13(ctx, dur):
    t = ctx.t
    f = ctx.f
    wd = ctx.wd
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.15, fade=scene_fade(t, dur, 1.0, 2.0))
    village_state(ctx, lights_boost=1.15)
    star(ctx, 1.2)
    parts = fireworks(ctx, t)
    draw_crowd(ctx, cheer=0.6 + 0.4 * math.sin(t * 0.5))
    # campfire glow & golem seated with kids on shoulders
    fx, fy, fz = wd.markers["campfire"]
    fl = 1.0 + 0.15 * math.sin(ctx.T * 11) + 0.1 * math.sin(ctx.T * 23)
    f.light((fx, fy + 0.8, fz), (5 * fl, 2.6 * fl, 0.8 * fl), 13, 1)
    f.glow((fx, fy + 0.3, fz), (1.6 * fl, 0.8 * fl, 0.25 * fl), 0.9)
    gpos = (fx - 5.0, 12.0 + 0.66, fz + 3.0)
    g = golem_instances(f, gpos, yaw_to(gpos, (fx, 0, fz)), sit=1.0, arm_pitch=(-0.4, -0.4), arm_in=0.0, smile=True,
                        eye=1.4, scarf=True, t=ctx.T, head=(0.1 * math.sin(t * 0.8), 0.05))
    for k_, sh in enumerate(g["shoulder"]):
        kid = "kid1" if k_ == 0 else "kid2"
        bounce = 0.05 * max(0, math.sin(ctx.T * 5 + k_ * 2))
        pk = (sh[0], sh[1] + 0.35 + bounce, sh[2])
        pose = Pose(legL=-1.3, legR=-1.3, armL=(-2.6 + 0.3 * math.sin(ctx.T * 4 + k_), 0.3), armR=(-2.6 + 0.3 * math.cos(ctx.T * 4 + k_), -0.3),
                    head=(0.0, 0.4), bob=-3.0)
        humanoid_instances(f, kid, pk, yaw_to(gpos, (fx, 0, fz)), pose, scale=0.065)
    # fire sparks
    parts.append(sparkles(t, [(fx, fy + 0.5, fz)], color=(3.0, 1.2, 0.3), size=0.04, n_per=30, spread=0.6, rise=3.0, twinkle=6))
    # Tilo & Lumi under the tree
    tp = (VC[0] - 4.0, 12.0, VC[2] + 15.5)
    pose = idle_pose(t)
    pose.head = (0, 0.55)
    tilo(ctx, tp, yaw_to(tp, VC), pose, scarf=False, lantern=False)
    spirit(ctx, companion(t, tp, 0, radius=0.7, height=1.7), 0, intensity=1.0, yaw=t)
    # mugs of hot chocolate in villagers' hands are implied; a few on the logs
    f.inst(IDS["mug"], (fx - 3.2, 13.0, fz + 4.2), I3, 0.08)
    f.inst(IDS["mug"], (fx + 4.2, 13.0, fz - 0.6), I3, 0.08)
    # gently glowing blue snow (the Hollow Winter visiting)
    gs = snow(ctx.T, (96, 30, 112), n=2600, box=(70, 40, 70), color=(0.8, 1.1, 1.9), alpha=0.6, size=1.1, fall=0.8,
              additive=True)
    parts.append(gs)
    parts.append(village_snow(ctx, (96, 25, 115), n=2500))
    i, u, L = shot(t, [0, 9.2, 15.0, 28.0, 38.0], dur)
    if i == 0:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 24, 152), (96, 22, 146), k), (96, 40, 100), 52)
    elif i == 1:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((fx + 3.5, 15.5, fz + 9.5), (fx + 2.5, 15.0, fz + 8.6), k), (gpos[0], 15.0, gpos[2]), 44)
    elif i == 2:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((60, 32, 140), (132, 30, 136), k), vlerp((80, 20, 108), (112, 20, 108), k), 46)
    elif i == 3:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((tp[0] + 2.0, 13.4, tp[2] + 4.2), (tp[0] + 1.6, 13.0, tp[2] + 3.4), k), vlerp((tp[0], 14, tp[2] - 3), (96, 40, 104), k), 48)
    else:
        k = ease_io(u / L)
        lookat_cam(ctx, vlerp((96, 30, 140), (96, 52, 132), k), vlerp((96, 40, 104), (96, 56, 100), k), 52)
    ctx.once("party", 0.0, "party_ambience", dur=dur)
    ctx.once("fire", 0.0, "fire_crackle", dur=dur)
    f.particles(cat(*parts))
    ctx.overlay.append(("chapter", "IX. Feliz Navidad", smoothstep(1.0, 2.0, t) * (1 - smoothstep(6.0, 7.0, t))))


# =====================================================================  CREDITS
def sc_credits(ctx, dur):
    t = ctx.t
    f = ctx.f
    apply_env(ctx, NIGHT, plane_y=11.0, exposure=1.1, fade=scene_fade(t, dur, 1.5, 3.0))
    village_state(ctx, lights_boost=1.1)
    star(ctx, 1.1)
    parts = fireworks(ctx, t + 20)
    a = 1.2 + t * 0.03
    R = 70
    lookat_cam(ctx, (VC[0] + math.cos(a) * R, 44, VC[2] + math.sin(a) * R), (VC[0], 30, VC[2]), 46)
    parts.append(village_snow(ctx, (VC[0], 30, VC[2] + 20), n=4000))
    f.particles(cat(*parts))
    ctx.overlay.append(("credits", t, dur))


# =====================================================================  timeline
SCENES = [
    # name, world, narration, lead, tail, function, music mood
    ("title", "village", None, 0.0, 14.0, sc_title, "intro"),
    ("s01", "village", "S01", 1.0, 2.5, sc_s01, "village"),
    ("s02", "village", "S02", 1.5, 2.5, sc_s02, "village"),
    ("s03", "village", "S03", 1.0, 5.0, sc_s03, "tension"),
    ("s04", "village", "S04", 1.0, 3.0, sc_s04, "resolve"),
    ("s05", "forest", "S05", 2.0, 3.0, sc_s05, "forest"),
    ("s06", "forest", "S06", 1.0, 3.5, sc_s06, "wonder"),
    ("s07", "cavern", "S07", 2.0, 3.0, sc_s07, "cave"),
    ("s08", "forge", "S08", 2.0, 3.0, sc_s08, "forge"),
    ("s09", "forge", "S09", 1.0, 4.0, sc_s09, "golem"),
    ("s10", "peak", "S10", 2.0, 3.0, sc_s10, "storm"),
    ("s11", "peak", "S11", 1.0, 6.0, sc_s11, "release"),
    ("s12", "village", "S12", 1.5, 7.0, sc_s12, "triumph"),
    ("s13", "village", "S13", 1.0, 4.0, sc_s13, "celebrate"),
    ("credits", "village", None, 0.0, 22.0, sc_credits, "outro"),
]


def timeline():
    out = []
    T = 0.0
    for (name, world, narr, lead, tail, fn, mood) in SCENES:
        if narr:
            nd = narr_dur(narr)
            dur = lead + nd + tail
        else:
            nd = 0
            dur = tail
        out.append(dict(name=name, world=world, narr=narr, lead=lead, start=T, dur=dur, narr_dur=nd, fn=fn, mood=mood))
        T += dur
    return out, T


if __name__ == "__main__":
    tl, total = timeline()
    for s in tl:
        print("%-8s %-8s start %7.2f dur %6.2f" % (s["name"], s["world"], s["start"], s["dur"]))
    print("TOTAL %.2f s = %d:%05.2f" % (total, total // 60, total % 60))
