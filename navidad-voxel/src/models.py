"""Voxel character models and a small skeletal rig for posing them."""
import math
import os
import numpy as np
from engine import VoxModel, BUILD, rot_x, rot_y, rot_z, I3

MODEL_DIR = os.path.join(BUILD, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

IDS = {}
_next = [0]


def reg(name, m):
    IDS[name] = _next[0]
    _next[0] += 1
    path = os.path.join(MODEL_DIR, name + ".vxm")
    m.save(path)
    return IDS[name]


SKIN = (238, 196, 160)
SKIN_D = (220, 170, 135)


def humanoid(prefix, coat, pants, boots, mitt, hair, hat=None, hat_trim=None, scarf=None, beard=None, kid=False, apron=None):
    # legs
    leg = VoxModel(3, 6, 3, pivot=(1.5, 6, 1.5))
    leg.box(0, 0, 0, 3, 2, 3, boots)
    leg.box(0, 2, 0, 3, 6, 3, pants)
    leg.box(0, 0, 2, 3, 1, 3, tuple(min(255, c + 25) for c in boots))
    reg(prefix + "_leg", leg)
    # torso (9x8x6 with core 7x6x4)
    def torso(with_scarf):
        t = VoxModel(9, 8, 6, pivot=(4.5, 0, 3))
        t.box(1, 0, 1, 8, 6, 5, coat)
        dark = tuple(int(c * 0.75) for c in coat)
        t.box(1, 1, 1, 8, 2, 5, (70, 45, 30))          # belt
        t.set(4, 1, 4, (240, 200, 70), emit=0.0)        # buckle (front = +z)
        t.box(4, 2, 4, 5, 6, 5, dark)                    # coat opening
        for y in (3, 4):
            t.set(3, y, 4, (230, 210, 150))
            t.set(5, y, 4, (230, 210, 150))
        if apron:
            t.box(2, 0, 4, 7, 5, 5, apron)
        if with_scarf and scarf:
            t.box(0, 5, 0, 9, 7, 6, scarf)
            t.box(2, 5, 1, 7, 7, 5, scarf)
            stripe = (245, 240, 230)
            for x in range(0, 9, 3):
                t.set(x, 6, 5, stripe)
                t.set(x, 6, 0, stripe)
            # hanging end at front-left
            t.box(1, 2, 5, 3, 5, 6, scarf)
            t.set(1, 3, 5, stripe); t.set(2, 3, 5, stripe)
        return t
    reg(prefix + "_torso", torso(True))
    if scarf:
        reg(prefix + "_torso_ns", torso(False))
    arm = VoxModel(2, 6, 2, pivot=(1, 6, 1))
    arm.box(0, 2, 0, 2, 6, 2, coat)
    arm.box(0, 0, 0, 2, 2, 2, mitt)
    reg(prefix + "_arm", arm)
    # head 7x9x7
    h = VoxModel(7, 9, 7, pivot=(3.5, 0, 3.5))
    h.box(0, 0, 0, 7, 7, 7, SKIN)
    h.box(0, 3, 0, 7, 7, 3, hair)       # back hair
    h.box(0, 5, 0, 7, 7, 7, hair)       # top hair
    h.box(0, 2, 0, 1, 7, 4, hair)
    h.box(6, 2, 0, 7, 7, 4, hair)
    h.box(1, 5, 6, 6, 6, 7, hair)       # fringe
    # face on +z
    h.set(2, 3, 6, (35, 30, 40)); h.set(4, 3, 6, (35, 30, 40))
    h.set(2, 4, 6, (250, 250, 250)); h.set(4, 4, 6, SKIN)
    h.box(2, 4, 6, 3, 5, 7, SKIN)
    h.set(1, 2, 6, (240, 150, 140)); h.set(5, 2, 6, (240, 150, 140))
    h.set(3, 1, 6, (170, 90, 80))
    h.set(3, 2, 6, SKIN_D)
    if beard:
        h.box(0, 0, 3, 7, 3, 7, beard)
        h.box(1, 0, 6, 6, 3, 7, beard)
        h.set(2, 3, 6, (35, 30, 40)); h.set(4, 3, 6, (35, 30, 40))
        h.box(2, 1, 6, 5, 2, 7, (150, 80, 70))
    if hat:
        h.box(0, 6, 0, 7, 8, 7, hat)
        h.box(0, 5, 0, 7, 6, 7, hat_trim or hat)
        h.box(1, 8, 1, 6, 9, 6, hat)
        h.set(3, 8, 3, hat_trim or (240, 240, 240))
    reg(prefix + "_head", h)


def build_models():
    # ---------------- Tilo
    humanoid("tilo", coat=(176, 112, 58), pants=(64, 72, 112), boots=(80, 52, 34), mitt=(60, 120, 70),
             hair=(110, 70, 40), hat=(52, 120, 76), hat_trim=(240, 240, 235), scarf=(200, 36, 40))
    # scarf tail (hangs at back of neck)
    st = VoxModel(2, 6, 1, pivot=(1, 6, 0.5))
    st.box(0, 0, 0, 2, 6, 1, (200, 36, 40))
    st.box(0, 1, 0, 2, 2, 1, (245, 240, 230)); st.box(0, 4, 0, 2, 5, 1, (245, 240, 230))
    st.box(0, 0, 0, 2, 1, 1, (230, 220, 210))
    reg("scarf_tail", st)
    # lantern
    ln = VoxModel(5, 7, 5, pivot=(2.5, 7, 2.5))
    iron = (50, 48, 52)
    ln.box(0, 0, 0, 5, 1, 5, iron)
    ln.box(0, 5, 0, 5, 6, 5, iron)
    for (x, z) in ((0, 0), (4, 0), (0, 4), (4, 4)):
        ln.box(x, 1, z, x + 1, 5, z + 1, iron)
    ln.box(1, 1, 1, 4, 5, 4, (255, 205, 120), emit=3.5)
    ln.box(1, 6, 1, 4, 7, 4, iron)
    ln.set(2, 6, 2, (90, 85, 80))
    reg("lantern", ln)
    # ---------------- villagers
    humanoid("vil1", coat=(120, 40, 45), pants=(60, 50, 45), boots=(50, 35, 25), mitt=(120, 90, 60), hair=(200, 200, 205),
             hat=(150, 30, 35), hat_trim=(240, 240, 240), beard=(235, 235, 240))
    humanoid("vil2", coat=(70, 90, 140), pants=(50, 50, 60), boots=(60, 40, 30), mitt=(200, 180, 150), hair=(60, 40, 25),
             hat=(230, 220, 200), hat_trim=(180, 60, 60))
    humanoid("vil3", coat=(90, 120, 70), pants=(80, 60, 40), boots=(50, 35, 25), mitt=(150, 60, 60), hair=(200, 120, 50),
             apron=(220, 210, 190))
    humanoid("vil4", coat=(150, 100, 160), pants=(60, 50, 70), boots=(60, 45, 35), mitt=(240, 240, 240), hair=(30, 25, 20),
             hat=(240, 240, 240), hat_trim=(150, 100, 160))
    humanoid("kid1", coat=(220, 160, 50), pants=(70, 70, 120), boots=(90, 50, 30), mitt=(200, 50, 50), hair=(150, 90, 40),
             hat=(200, 50, 50), hat_trim=(250, 250, 250))
    humanoid("kid2", coat=(60, 150, 170), pants=(90, 60, 50), boots=(60, 40, 30), mitt=(250, 220, 80), hair=(40, 30, 20),
             hat=(250, 220, 80), hat_trim=(60, 150, 170))
    # ---------------- golem
    stone = (118, 120, 112); stone_d = (92, 94, 88); moss = (70, 115, 55); moss_d = (55, 90, 45)
    rng = np.random.default_rng(7)

    def stone_box(m, x0, y0, z0, x1, y1, z1, mossy=0.25):
        for x in range(x0, x1):
            for y in range(y0, y1):
                for z in range(z0, z1):
                    r = rng.random()
                    top = y >= y1 - 2
                    if r < mossy * (1.8 if top else 0.7):
                        m.set(x, y, z, moss if rng.random() < 0.6 else moss_d)
                    else:
                        m.set(x, y, z, stone if rng.random() < 0.7 else stone_d)
    gb = VoxModel(14, 12, 9, pivot=(7, 0, 4.5))
    stone_box(gb, 0, 0, 0, 14, 12, 9)
    for x in range(1, 13):
        gb.set(x, 6, 8, (80, 82, 78))           # chest crack line
    gb.box(5, 7, 8, 9, 10, 9, (60, 62, 60))    # chest rune plate
    gb.box(6, 8, 8, 8, 9, 9, (255, 170, 70), emit=1.5)  # rune glow
    reg("golem_body", gb)

    def golem_head(smile):
        hd = VoxModel(9, 8, 8, pivot=(4.5, 0, 4))
        stone_box(hd, 0, 0, 0, 9, 8, 8, 0.3)
        hd.box(0, 6, 0, 9, 8, 8, moss)
        for (x, z) in ((1, 2), (6, 5), (3, 1), (7, 1)):
            hd.set(x, 7, z, moss_d)
        hd.box(1, 4, 7, 4, 5, 8, (40, 40, 40))   # brow
        hd.box(5, 4, 7, 8, 5, 8, (40, 40, 40))
        hd.box(2, 3, 7, 3, 4, 8, (255, 180, 80), emit=4.0)  # eyes
        hd.box(6, 3, 7, 7, 4, 8, (255, 180, 80), emit=4.0)
        hd.box(4, 2, 7, 5, 4, 8, stone_d)  # nose
        mouth = (45, 40, 40)
        if smile:
            hd.box(3, 1, 7, 6, 2, 8, mouth)
            hd.set(2, 2, 7, mouth); hd.set(6, 2, 7, mouth)
        else:
            hd.box(3, 2, 7, 6, 3, 8, mouth)
            hd.set(2, 1, 7, mouth); hd.set(6, 1, 7, mouth)
        return hd
    reg("golem_head_sad", golem_head(False))
    reg("golem_head_smile", golem_head(True))
    ga = VoxModel(5, 14, 5, pivot=(2.5, 14, 2.5))
    stone_box(ga, 0, 0, 0, 5, 14, 5)
    ga.box(0, 0, 0, 5, 3, 5, stone_d)
    reg("golem_arm", ga)
    gl = VoxModel(5, 7, 5, pivot=(2.5, 7, 2.5))
    stone_box(gl, 0, 0, 0, 5, 7, 5, 0.15)
    reg("golem_leg", gl)
    gs = VoxModel(16, 3, 11, pivot=(8, 0, 5.5))
    red = (200, 36, 40)
    gs.box(0, 0, 0, 16, 3, 11, red)
    gs.box(2, 0, 2, 14, 3, 9, 0)
    for x in range(0, 16, 3):
        gs.set(x, 1, 10, (245, 240, 230)); gs.set(x, 1, 0, (245, 240, 230))
    gs.box(11, -0 + 0, 10, 14, 3, 11, red)
    reg("golem_scarf", gs)
    gst = VoxModel(3, 8, 1, pivot=(1.5, 8, 0.5))
    gst.box(0, 0, 0, 3, 8, 1, red)
    gst.box(0, 2, 0, 3, 3, 1, (245, 240, 230)); gst.box(0, 5, 0, 3, 6, 1, (245, 240, 230))
    reg("golem_scarf_tail", gst)
    # ---------------- Lumi (light spirit)
    lu = VoxModel(5, 5, 5, pivot=(2.5, 2.5, 2.5))
    for x in range(5):
        for y in range(5):
            for z in range(5):
                d = (x - 2) ** 2 + (y - 2) ** 2 + (z - 2) ** 2
                if d <= 5:
                    lu.set(x, y, z, (255, 228, 150), emit=1.1)
    lu.set(1, 3, 4, (60, 40, 30)); lu.set(3, 3, 4, (60, 40, 30))
    lu.set(1, 3, 3, (60, 40, 30)); lu.set(3, 3, 3, (60, 40, 30))
    reg("lumi", lu)
    # ---------------- Star
    sm = VoxModel(19, 19, 3, pivot=(9.5, 9.5, 1.5))
    for x in range(19):
        for y in range(19):
            px, py = (x - 9) / 9.0, (y - 9) / 9.0
            ang = math.atan2(py, px) - math.pi / 2
            r = math.hypot(px, py)
            k = (math.cos(ang * 5) + 1) / 2
            lim = 0.42 + 0.58 * k ** 2.2
            if r <= lim:
                inner = r < lim - 0.22
                sm.set(x, y, 1, (255, 214, 90), emit=1.0)
                if inner:
                    sm.set(x, y, 0, (255, 230, 140), emit=1.0)
                    sm.set(x, y, 2, (255, 230, 140), emit=1.0)
    reg("star", sm)
    # ---------------- Bell
    bm = VoxModel(7, 7, 7, pivot=(3.5, 7, 3.5))
    for y in range(7):
        r = 1.2 + (6 - y) * 0.45 if y < 6 else 1.0
        for x in range(7):
            for z in range(7):
                if (x - 3) ** 2 + (z - 3) ** 2 <= r * r:
                    bm.set(x, y, z, (200, 160, 60), refl=0.3)
    bm.box(3, 0, 3, 4, 1, 4, (90, 70, 40))
    reg("bell", bm)
    # ---------------- Toys
    tr = VoxModel(8, 5, 4, pivot=(4, 0, 2))
    tr.box(0, 1, 0, 6, 3, 4, (200, 40, 40))
    tr.box(4, 3, 0, 6, 5, 4, (40, 80, 160))
    tr.box(1, 3, 1, 2, 5, 3, (40, 40, 40))
    tr.box(6, 1, 1, 8, 2, 3, (240, 200, 60))
    for x in (1, 4):
        tr.box(x, 0, 0, x + 1, 1, 4, (30, 30, 30))
    reg("toy_train", tr)
    so = VoxModel(3, 8, 3, pivot=(1.5, 0, 1.5))
    so.box(0, 0, 0, 3, 3, 3, (40, 40, 70))
    so.box(0, 3, 0, 3, 6, 3, (200, 40, 40))
    so.box(0, 6, 0, 3, 8, 3, (238, 196, 160))
    so.box(0, 7, 0, 3, 8, 3, (30, 30, 30))
    reg("toy_soldier", so)
    # ---------------- Owl
    ow = VoxModel(5, 7, 4, pivot=(2.5, 0, 2))
    ow.box(0, 0, 0, 5, 6, 4, (120, 90, 60))
    ow.box(1, 1, 3, 4, 4, 4, (200, 180, 150))
    ow.set(1, 4, 3, (255, 220, 60), emit=2.0); ow.set(3, 4, 3, (255, 220, 60), emit=2.0)
    ow.set(2, 3, 3, (220, 160, 60))
    ow.set(0, 6, 1, (110, 80, 50)); ow.set(4, 6, 1, (110, 80, 50))
    reg("owl", ow)
    # ---------------- ice cube (Hollow Winter body), eyes
    ic = VoxModel(1, 1, 1, pivot=(0.5, 0.5, 0.5))
    ic.set(0, 0, 0, (70, 110, 190), emit=2.2, refl=0.25)
    reg("frost_cube", ic)
    ic2 = VoxModel(1, 1, 1, pivot=(0.5, 0.5, 0.5))
    ic2.set(0, 0, 0, (30, 40, 70), refl=0.3)
    reg("dark_cube", ic2)
    ey = VoxModel(3, 2, 1, pivot=(1.5, 1, 0.5))
    ey.box(0, 0, 0, 3, 2, 1, (200, 240, 255), emit=5.0)
    reg("wraith_eye", ey)
    # ---------------- crystal petal
    cp = VoxModel(5, 18, 5, pivot=(2.5, 0, 2.5))
    for y in range(18):
        r = 2.4 if y < 12 else 2.4 * (18 - y) / 6.0
        for x in range(5):
            for z in range(5):
                if abs(x - 2) + abs(z - 2) <= r:
                    cp.set(x, y, z, (120, 200, 255) if (x + y + z) % 5 else (200, 240, 255), emit=0.35, refl=0.5)
    reg("crystal_petal", cp)
    # ---------------- campfire flame & fireworks rocket not needed (particles)
    # ---------------- chocolate mug (celebration detail)
    mg = VoxModel(3, 3, 3, pivot=(1.5, 0, 1.5))
    mg.box(0, 0, 0, 3, 3, 3, (230, 230, 230))
    mg.box(1, 2, 1, 2, 3, 2, (90, 50, 30))
    reg("mug", mg)
    return IDS


# =============================================================== rig / posing

class Pose:
    def __init__(self, **kw):
        self.legL = kw.get("legL", 0.0)
        self.legR = kw.get("legR", 0.0)
        self.armL = kw.get("armL", (0.0, 0.0))   # (pitch, roll)
        self.armR = kw.get("armR", (0.0, 0.0))
        self.head = kw.get("head", (0.0, 0.0))   # (yaw, pitch)
        self.body = kw.get("body", (0.0, 0.0))   # (pitch, roll) lean
        self.bob = kw.get("bob", 0.0)            # vertical offset in voxels


def walk_pose(phase, amp=0.6, arm_amp=0.5):
    s = math.sin(phase)
    return Pose(legL=s * amp, legR=-s * amp, armL=(-s * arm_amp, 0.05), armR=(s * arm_amp, -0.05),
                bob=abs(math.cos(phase)) * 0.5)


def idle_pose(t, breathe=1.0):
    b = math.sin(t * 2.0) * 0.03 * breathe
    return Pose(armL=(b, 0.06), armR=(-b, -0.06), head=(math.sin(t * 0.7) * 0.08, 0.0), bob=0)


def humanoid_instances(frame, prefix, pos, yaw, pose, scale=0.09, scarf=True, lantern=False, lantern_lit=1.0,
                       scarf_wave=0.0, tint=(1, 1, 1), emit=1.0):
    """Adds instances for a humanoid. pos = feet center (world). Returns dict of useful world points."""
    R0 = rot_y(yaw)
    p0 = np.array(pos, float)

    def W(local):
        return p0 + R0 @ (np.array(local, float) * scale)
    bob = pose.bob
    Rb = R0 @ rot_x(pose.body[0]) @ rot_z(pose.body[1])
    hip = np.array((0, 6 + bob, 0))
    # legs
    frame.inst(IDS[prefix + "_leg"], tuple(W(hip + (-1.5, 0, 0))), R0 @ rot_x(pose.legL), scale, tint=tint)
    frame.inst(IDS[prefix + "_leg"], tuple(W(hip + (1.5, 0, 0))), R0 @ rot_x(pose.legR), scale, tint=tint)
    # torso
    tname = prefix + "_torso" if (scarf or prefix + "_torso_ns" not in IDS) else prefix + "_torso_ns"
    torso_base = W(hip)
    frame.inst(IDS[tname], tuple(torso_base), Rb, scale, tint=tint)

    def B(local):  # body-local (relative to hip) to world
        return torso_base + Rb @ (np.array(local, float) * scale)
    # arms
    shL = B((-4.5, 6, 0))
    shR = B((4.5, 6, 0))
    RaL = Rb @ rot_x(pose.armL[0]) @ rot_z(-pose.armL[1])
    RaR = Rb @ rot_x(pose.armR[0]) @ rot_z(-pose.armR[1])
    frame.inst(IDS[prefix + "_arm"], tuple(shL), RaL, scale, tint=tint)
    frame.inst(IDS[prefix + "_arm"], tuple(shR), RaR, scale, tint=tint)
    handR = shR + RaR @ (np.array((0, -6, 0)) * scale)
    handL = shL + RaL @ (np.array((0, -6, 0)) * scale)
    # head
    neck = B((0, 6, 0))
    Rh = Rb @ rot_y(pose.head[0]) @ rot_x(-pose.head[1])
    frame.inst(IDS[prefix + "_head"], tuple(neck), Rh, scale, tint=tint)
    out = {"handR": handR, "handL": handL, "head": neck + Rh @ (np.array((0, 4, 0)) * scale), "neck": neck,
           "shoulderL": shL, "shoulderR": shR, "R": R0, "Rb": Rb}
    if scarf and prefix == "tilo":
        tail_pos = B((1.5, 7, -3.0))
        frame.inst(IDS["scarf_tail"], tuple(tail_pos), Rb @ rot_x(0.25 + scarf_wave), scale, tint=tint)
    if lantern:
        lp = handR
        Rl = R0 @ rot_x(math.sin(pose.armR[0]) * -0.3)
        frame.inst(IDS["lantern"], tuple(lp + np.array((0, -0.02, 0))), Rl, scale * 0.8, shadow=0, emit=lantern_lit)
        out["lantern"] = lp + Rl @ (np.array((0, -4.0, 0)) * scale * 0.8)
    return out


def golem_instances(frame, pos, yaw, sit=1.0, arm_pitch=(-0.9, -0.9), arm_in=0.35, head=(0.0, 0.0), smile=False,
                    eye=1.0, scarf=False, shiver=0.0, t=0.0, walk_phase=None, scale=0.22):
    R0 = rot_y(yaw)
    p0 = np.array(pos, float)
    jit = np.array((math.sin(t * 37) * 0.25, 0, math.cos(t * 41) * 0.2)) * shiver

    def W(local):
        return p0 + R0 @ (np.array(local, float) * scale)
    legL = legR = 0.0
    bob = 0.0
    if walk_phase is not None:
        s = math.sin(walk_phase)
        legL, legR = s * 0.45, -s * 0.45
        bob = abs(math.cos(walk_phase)) * 0.6
    # sitting: hips go down by ~5 voxels, legs forward
    hip_y = 7 - 5.0 * sit + bob
    lp = -1.45 * sit
    frame.inst(IDS["golem_leg"], tuple(W((-3.5, hip_y, 0))), R0 @ rot_x(lp + legL), scale)
    frame.inst(IDS["golem_leg"], tuple(W((3.5, hip_y, 0))), R0 @ rot_x(lp + legR), scale)
    Rb = R0 @ rot_x(0.12 * sit)
    base = W((0, hip_y, 0)) + jit * scale

    def B(local):
        return base + Rb @ (np.array(local, float) * scale)
    frame.inst(IDS["golem_body"], tuple(base), Rb, scale)
    for side, ap in ((-1, arm_pitch[0]), (1, arm_pitch[1])):
        sh = B((side * 9.5, 11, 0))
        aw = 0.0 if walk_phase is None else -side * math.sin(walk_phase) * 0.35
        Ra = Rb @ rot_x(ap + aw) @ rot_z(-side * -arm_in * 0.5) @ rot_y(side * -arm_in)
        frame.inst(IDS["golem_arm"], tuple(sh), Ra, scale)
    Rh = Rb @ rot_y(head[0]) @ rot_x(-head[1])
    neck = B((0, 12, 0.8))
    frame.inst(IDS["golem_head_smile" if smile else "golem_head_sad"], tuple(neck), Rh, scale, emit=eye)
    hands = (B((-6.5, 2.0, 7.5)), B((6.5, 2.0, 7.5)))
    if scarf:
        frame.inst(IDS["golem_scarf"], tuple(B((0, 11.2, 0))), Rb, scale)
        frame.inst(IDS["golem_scarf_tail"], tuple(B((3.5, 13.0, 5.6))), Rb @ rot_x(-0.1), scale)
    cup = B((0, 3.5, 9.0)) if sit > 0.5 else None
    return {"neck": neck, "head": neck + Rh @ (np.array((0, 4, 4)) * scale), "cup": cup, "base": base,
            "shoulder": (B((-9.5, 11, 0)), B((9.5, 11, 0))), "Rb": Rb}


if __name__ == "__main__":
    ids = build_models()
    print(ids)
