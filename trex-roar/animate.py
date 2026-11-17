"""Procedural animation: FK body performance, analytic leg IK, baked per-frame
keys for the rig and the hand-held camera (with roar shake)."""
import bpy, numpy as np, math
from scipy.interpolate import PchipInterpolator
from mathutils import Matrix, Quaternion, Vector
import trex_sdf as T

FPS = 24
N_FRAMES = 360

def K(t, keys):
    ks = np.array(keys, float)
    return float(PchipInterpolator(ks[:, 0], ks[:, 1])(np.clip(t, ks[0, 0], ks[-1, 0])))

def nz(t, f, seed):
    """smooth pseudo random signal in ~[-1,1] with base frequency f (Hz)."""
    return (math.sin(2 * math.pi * f * t + seed * 1.7) + 0.6 * math.sin(2 * math.pi * f * 1.93 * t + seed * 4.1)
            + 0.35 * math.sin(2 * math.pi * f * 3.31 * t + seed * 9.3)) / 1.95

def Rx(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def Ry(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def Rz(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def M4(R, p):
    m = np.eye(4); m[:3, :3] = R; m[:3, 3] = p; return m
def euler(pitch=0, yaw=0, roll=0):
    r = math.radians
    return Rz(r(yaw)) @ Rx(r(pitch)) @ Ry(r(roll))
def unit(v): return v / np.linalg.norm(v)

# ----------------------------------------------------------- the performance
def roar_env(t):      # main roar loudness 0..1
    return K(t, [(0, 0), (4.55, 0), (4.95, 1), (8.9, 1), (9.5, 0.55), (10.2, 0), (15, 0)])
def bark_env(t):
    return K(t, [(0, 0), (12.75, 0), (13.05, 1), (13.5, 0.8), (13.95, 0), (15, 0)])
def stomp_env(t, t0=3.0):
    return math.exp(-(t - t0) / 0.28) * (1 - math.exp(-(t - t0) / 0.02)) if t > t0 else 0.0

def performance(t):
    """returns dict bone -> (pitch, yaw, roll) deltas in degrees, plus extras."""
    P = {}
    roar = roar_env(t); bark = bark_env(t); loud = max(roar, bark)
    breath = math.sin(2 * math.pi * t / 2.6)
    trem = 0.4 * loud * nz(t, 8.0, 1.0)              # high frequency roar tremor
    # --- body: turn to the camera, step in, crouch forward for the roar
    fwd = K(t, [(0, 0), (2.2, 0), (3.1, 1.0), (4.4, 1.05), (4.95, 1.3), (9.4, 1.35), (10.6, 1.15), (12.8, 1.15), (13.1, 1.45), (14.0, 1.2), (15, 1.2)])
    drop = K(t, [(0, 0), (2.2, 0), (2.7, 0.06), (3.05, 0.2), (3.5, 0.10), (4.4, 0.04), (4.95, 0.22), (9.4, 0.24), (10.6, 0.14), (12.8, 0.16), (13.1, 0.24), (14, 0.18), (15, 0.18)])
    body_yaw = K(t, [(0, 0), (2.0, 0), (3.2, 4), (5.0, 7), (9.5, 8), (15, 8)])
    lean = K(t, [(0, 0), (2.2, 0), (3.1, 3), (4.4, -5), (4.95, 9), (9.3, 10), (10.6, 5), (12.8, 6), (13.1, 9), (14, 6), (15, 6)])
    P["hips"] = (lean + 0.5 * breath + 0.8 * trem, body_yaw + 1.2 * nz(t, 0.21, 2), 2.0 * nz(t, 0.17, 3) + K(t, [(0, 0), (2.3, 0), (2.7, -3), (3.1, 2), (3.6, 0), (15, 0)]))
    P["hips_loc"] = np.array([0.25 * math.sin(math.radians(body_yaw)) * 0 + 0.08 * nz(t, 0.19, 5), -fwd, -drop + 0.02 * breath])
    P["spine1"] = (lean * 0.25 + 0.6 * breath, body_yaw * 0.25, 0)
    P["spine2"] = (lean * 0.3 + 1.0 * breath + 1.0 * trem, body_yaw * 0.3 + K(t, [(0, 3), (1.0, 3), (2.2, -2), (15, -2)]), 0)
    # --- neck & head: look away -> notice camera -> coil -> lunge & roar -> stare -> bark
    look_yaw = K(t, [(0, 30), (0.9, 28), (1.9, -16), (3.2, -20), (4.4, -19), (5.0, -17), (6.5, -9), (8.2, -21), (9.4, -15), (10.8, -20), (12.7, -17), (13.1, -14), (15, -17)])
    neck_pitch = K(t, [(0, -4), (0.9, -5), (2.0, 4), (3.2, 7), (4.0, -7), (4.5, -11), (4.95, 13), (9.3, 15), (10.2, 6), (11.2, 11), (12.6, 12), (12.85, 5), (13.1, 15), (14.0, 11), (15, 10)])
    # desired head pitch relative to the rest pose (rest is 12 deg nose-down); parents are compensated
    head_des = K(t, [(0, -6), (0.9, -6), (2.0, 6), (3.2, 8), (4.0, -8), (4.5, -22), (4.95, -3), (7, -6), (9.3, -3), (10.2, 8), (11.2, 16), (12.6, 15), (12.85, 2), (13.1, -4), (14.0, 12), (15, 14)])
    head_pitch = head_des - (1.55 * lean + 1.5 * neck_pitch)
    head_roll = K(t, [(0, 0), (1.9, 5), (3.2, -4), (4.9, 0), (6.4, 9), (8.2, -8), (9.5, 0), (11.2, 9), (12.6, 7), (13.1, 0), (15, -5)])
    for b, w in (("neck1", 0.40), ("neck2", 0.34), ("neck3", 0.26)):
        P[b] = (neck_pitch * w * 1.5 + 0.5 * trem, look_yaw * w * 0.8 + 1.2 * loud * nz(t, 1.4, 7), head_roll * 0.2)
    P["head"] = (head_pitch + 1.6 * trem + 1.0 * nz(t, 0.4, 11), look_yaw * 0.35 + 2.0 * loud * nz(t, 1.9, 8) + 1.0 * nz(t, 0.33, 12), head_roll + 2.0 * loud * nz(t, 1.7, 9))
    # --- jaw (total opening in degrees; rest pose is 30)
    jaw = K(t, [(0, 3), (0.8, 3), (1.3, 7), (2.0, 4), (3.0, 6), (3.6, 9), (4.45, 16), (4.95, 60), (6.5, 63), (8.8, 60), (9.6, 36), (10.3, 9), (11.2, 6), (12.0, 11), (12.7, 8), (13.08, 50), (13.5, 44), (13.95, 6), (15, 5)])
    jaw += 4.0 * trem + 1.5 * max(0.0, math.sin(2 * math.pi * t / 2.6)) * (1 - loud)
    P["jaw"] = (jaw - 30.0, 0, 0)
    P["tongue1"] = (-6 * loud + 2 * trem, 2.5 * loud * nz(t, 6, 14), 0)
    P["tongue2"] = (-16 * loud + 4 * loud * nz(t, 7, 15), 4 * loud * nz(t, 5, 16), 0)
    # --- tail: counterbalance + lazy travelling sway, lashing during the roar
    tail_up = K(t, [(0, 0), (2.2, 0), (4.4, 2), (4.95, -7), (9.3, -8), (10.6, -2), (15, -2)])
    for i in range(6):
        ph = 0.75 * i
        sway = (4.0 + 1.6 * i) * math.sin(2 * math.pi * t / 4.3 - ph) + loud * (3 + 2.2 * i) * math.sin(2 * math.pi * t / 1.15 - ph)
        P[f"tail{i+1}"] = (tail_up * (0.5 if i < 2 else 0.25) - lean * (0.55 if i == 0 else 0.1), sway - (body_yaw * 0.3 if i == 0 else 0), 0)
    # --- tiny arms twitch
    for sfx, sd in ((".L", 1), (".R", -1)):
        P["uarm" + sfx] = (18 * loud + 5 * nz(t, 0.7, 20 + sd), 0, sd * 8 * loud)
        P["farm" + sfx] = (-25 * loud + 8 * nz(t, 1.1, 30 + sd), 0, 0)
    # --- feet: the right foot (x<0, nearer the camera side) takes one heavy step
    step = K(t, [(0, 0), (2.25, 0), (3.0, 1), (15, 1)])
    lift = max(0.0, math.sin(math.pi * np.clip((t - 2.25) / 0.75, 0, 1))) ** 0.8
    P["foot.R"] = dict(offset=np.array([0.10 * step, -1.75 * step, 0.55 * lift]), toe_pitch=28 * lift * (1 - step) - 14 * lift * step, meta_pitch=22 * lift)
    lstep = K(t, [(0, 0), (12.55, 0), (13.1, 1), (15, 1)])
    llift = max(0.0, math.sin(math.pi * np.clip((t - 12.55) / 0.55, 0, 1)))
    P["foot.L"] = dict(offset=np.array([0, -0.75 * lstep, 0.3 * llift]), toe_pitch=20 * llift * (1 - lstep), meta_pitch=-10 * K(t, [(0, 0), (3.0, 0), (5.0, 1), (12.5, 1), (13.1, 0), (15, 0)]) + 14 * llift)
    return P

# ------------------------------------------------------------------ solving
class Rig:
    def __init__(s, rig_ob):
        s.ob = rig_ob
        s.names = [b.name for b in rig_ob.data.bones]
        s.rest = {b.name: np.array(b.matrix_local) for b in rig_ob.data.bones}
        s.parent = {b.name: (b.parent.name if b.parent else None) for b in rig_ob.data.bones}

    def solve(s, t):
        P = performance(t)
        M = {}; R = s.rest
        def fk(name):
            par = s.parent[name]
            pit, yaw, rol = P.get(name, (0, 0, 0))
            Rr = R[name][:3, :3]
            B = np.eye(4); B[:3, :3] = Rr.T @ euler(pit, yaw, rol) @ Rr
            if name + "_loc" in P: B[:3, 3] = Rr.T @ P[name + "_loc"]
            M[name] = (M[par] @ np.linalg.inv(R[par]) @ R[name] @ B) if par else R[name] @ B
        order = ["root", "hips", "spine1", "spine2", "neck1", "neck2", "neck3", "head", "jaw", "tongue1", "tongue2"] + [f"tail{i}" for i in range(1, 7)] + ["uarm.L", "farm.L", "uarm.R", "farm.R"]
        for nme in order: fk(nme)
        hipsD = M["hips"] @ np.linalg.inv(R["hips"])
        for sfx, sd in ((".L", 1), (".R", -1)):
            m = np.array([sd, 1, 1])
            H0, K0, A0, B0 = T.HIP * m, T.KNEE * m, T.ANKLE * m, T.BALL * m
            f = P["foot" + sfx]
            Hp = (hipsD @ np.append(H0, 1))[:3]
            Bp = B0 + f["offset"]
            mdir = Rx(math.radians(f["meta_pitch"])) @ unit(B0 - A0)
            L3 = np.linalg.norm(B0 - A0); Ap = Bp - mdir * L3
            L1 = np.linalg.norm(K0 - H0); L2 = np.linalg.norm(A0 - K0)
            d = Ap - Hp; D = np.linalg.norm(d)
            if D > (L1 + L2) * 0.995:
                D = (L1 + L2) * 0.995; Ap = Hp + unit(d) * D; Bp = Ap + mdir * L3; d = Ap - Hp
            a = (L1 * L1 - L2 * L2 + D * D) / (2 * D); hgt = math.sqrt(max(L1 * L1 - a * a, 1e-6))
            pole = np.array([0.18 * sd, -1.0, 0.1]); pole = unit(pole - unit(d) * (pole @ unit(d)))
            Kp = Hp + unit(d) * a + pole * hgt
            def frame(p0, p1, nrm):
                y = unit(p1 - p0); z = unit(np.cross(nrm, y)); x = np.cross(y, z); return np.stack([x, y, z], 1)
            n0 = unit(np.cross(K0 - H0, A0 - K0)); n1 = unit(np.cross(Kp - Hp, Ap - Kp))
            for bone, (r0, r1), (p0, p1) in (("thigh", (H0, K0), (Hp, Kp)), ("shin", (K0, A0), (Kp, Ap)), ("meta", (A0, B0), (Ap, Bp))):
                Q = frame(p0, p1, n1) @ frame(r0, r1, n0).T
                M[bone + sfx] = M4(Q @ R[bone + sfx][:3, :3], p0)
            M["toes" + sfx] = M4(Rx(math.radians(f["toe_pitch"])) @ R["toes" + sfx][:3, :3], Bp)
        # channel values
        out = {}
        for nme in s.names:
            par = s.parent[nme]
            B = np.linalg.inv(R[nme]) @ M[nme] if par is None else np.linalg.inv(np.linalg.inv(R[par]) @ R[nme]) @ np.linalg.inv(M[par]) @ M[nme]
            q = Matrix(B[:3, :3].tolist()).to_quaternion()
            out[nme] = (B[:3, 3].copy(), np.array(q))
        return out, M

def make_channelbag(idblock, name, id_type='OBJECT'):
    ad = idblock.animation_data_create()
    act = bpy.data.actions.new(name); ad.action = act
    slot = act.slots.new(id_type=id_type, name=idblock.name); ad.action_slot = slot
    layer = act.layers.new("Layer"); strip = layer.strips.new(type='KEYFRAME')
    return strip.channelbag(slot, ensure=True)

def bake_curve(cb, path, index, frames, values, group=None):
    fc = cb.fcurves.new(path, index=index) if group is None else cb.fcurves.new(path, index=index, group_name=group)
    n = len(frames)
    fc.keyframe_points.add(n)
    co = np.empty(n * 2, np.float32); co[0::2] = frames; co[1::2] = values
    fc.keyframe_points.foreach_set("co", co)
    fc.keyframe_points.foreach_set("interpolation", np.full(n, 1, np.int32))      # LINEAR
    fc.update()

def animate_rig(rig_ob):
    rig = Rig(rig_ob)
    frames = np.arange(0, N_FRAMES + 2)
    loc = {n: [] for n in rig.names}; rot = {n: [] for n in rig.names}
    track = {"head": [], "mouth": []}
    for f in frames:
        ch, M = rig.solve((f - 1) / FPS)
        for n, (l, q) in ch.items():
            if rot[n] and np.dot(rot[n][-1], q) < 0: q = -q
            loc[n].append(l); rot[n].append(q)
        Hd = M["head"] @ np.linalg.inv(rig.rest["head"])
        Jd = M["jaw"] @ np.linalg.inv(rig.rest["jaw"])
        eye_mid = T.head_to_world([0, -0.45, 0.45])[0]; up = T.head_to_world([0, -1.0, -0.05])[0]; lo = T.head_to_world([0, -1.0, -0.12], True)[0]
        track["head"].append((Hd @ np.append(eye_mid, 1))[:3])
        track["mouth"].append(0.5 * ((Hd @ np.append(up, 1))[:3] + (Jd @ np.append(lo, 1))[:3]))
    cb = make_channelbag(rig_ob, "TRexPerformance")
    for n in rig.names:
        L = np.array(loc[n]); Q = np.array(rot[n])
        moving_loc = np.abs(L).max() > 1e-5
        for i in range(4):
            bake_curve(cb, f'pose.bones["{n}"].rotation_quaternion', i, frames, Q[:, i], n)
        if moving_loc:
            for i in range(3):
                bake_curve(cb, f'pose.bones["{n}"].location', i, frames, L[:, i], n)
    W = np.array(rig_ob.matrix_world)
    return {k: (np.array(v) @ W[:3, :3].T + W[:3, 3]) for k, v in track.items()}, frames

# -------------------------------------------------------------------- camera
def shake_env(t):
    return min(1.0, 0.95 * roar_env(t) + 0.75 * bark_env(t) + 1.1 * stomp_env(t, 3.02) + 0.5 * stomp_env(t, 13.1))

def animate_camera(cam, track, frames, base):
    """hand-held camera: slow drift, look-at following the head, shake with the roar."""
    cb = make_channelbag(cam, "CameraHandheld")
    cbd = make_channelbag(cam.data, "CameraFocus", id_type='CAMERA')
    locs, rots, foc, lens = [], [], [], []
    head = track["head"]; mouth = track["mouth"]
    # smooth the look-at target so the operator lags behind the animal
    def smooth(a, k):
        out = a.copy()
        for i in range(1, len(a)): out[i] = out[i - 1] + (a[i] - out[i - 1]) * k
        return out
    prev_q = None
    for i, f in enumerate(frames):
        t = (f - 1) / FPS
        w = K(t, [(0, 0.0), (4.3, 0.0), (5.0, 0.8), (9.4, 0.8), (10.5, 0.35), (12.7, 0.3), (13.1, 0.75), (14, 0.4), (15, 0.4)])
        tgt = head[i] * (1 - w) + mouth[i] * w
        locs.append(tgt)
    tg = smooth(np.array(locs), 0.24); locs = []
    for i, f in enumerate(frames):
        t = (f - 1) / FPS
        e = shake_env(t)
        back = K(t, [(0, 0), (4.6, 0.10), (5.2, 0.28), (9.5, 0.50), (12.6, 0.55), (13.2, 0.68), (15, 0.72)])     # operator backs away
        p = base + np.array([0.10 * math.sin(t * 0.5), -back, K(t, [(0, 0.0), (2.4, 0.0), (3.3, -0.22), (4.5, -0.42), (5.3, -0.58), (10, -0.56), (15, -0.5)])])
        p = p + 0.012 * np.array([nz(t, 0.35, 41), nz(t, 0.31, 42), nz(t, 0.4, 43)])
        p = p + e * np.array([0.012 * nz(t, 4.3, 44), 0.008 * nz(t, 3.9, 45), 0.014 * nz(t, 5.1, 46)])
        look = tg[i] + np.array([0, 0, K(t, [(0, -0.9), (4.4, -0.75), (5.2, 0.05), (9.4, 0.1), (10.6, -0.25), (15, -0.25)])])
        q = (Vector(look) - Vector(p)).to_track_quat('-Z', 'Y')
        r = math.radians
        drift = Quaternion((1, 0, 0), r(0.35 * nz(t, 0.45, 51))) @ Quaternion((0, 1, 0), r(0.35 * nz(t, 0.38, 52))) @ Quaternion((0, 0, 1), r(0.5 * nz(t, 0.3, 53)))
        shk = Quaternion((1, 0, 0), r(e * 0.42 * nz(t, 5.3, 54))) @ Quaternion((0, 1, 0), r(e * 0.34 * nz(t, 4.6, 55))) @ Quaternion((0, 0, 1), r(e * 0.5 * nz(t, 4.9, 56)))
        q = q @ drift @ shk
        if prev_q is not None and q.dot(prev_q) < 0: q.negate()
        prev_q = q.copy()
        locs.append(p); rots.append(np.array(q))
        foc.append(max(0.6, float(np.linalg.norm(tg[i] - p)) - 0.25))
        lens.append(K(t, [(0, 26), (4.4, 27), (5.2, 26), (9.5, 26.5), (12.6, 28), (15, 28)]))
    locs = np.array(locs); rots = np.array(rots)
    cam.rotation_mode = 'QUATERNION'
    for i in range(3): bake_curve(cb, "location", i, frames, locs[:, i])
    for i in range(4): bake_curve(cb, "rotation_quaternion", i, frames, rots[:, i])
    bake_curve(cbd, "dof.focus_distance", 0, frames, np.array(foc))
    bake_curve(cbd, "lens", 0, frames, np.array(lens))

def animate_plants(plants, centre, frames, radius=9.0):
    """undergrowth near the action trembles; the roar blast shoves it around."""
    n = 0
    for ob in plants:
        d = math.hypot(ob.location.x - centre[0], ob.location.y - centre[1])
        if d > radius: continue
        n += 1
        cb = make_channelbag(ob, "Sway." + ob.name)
        base = np.array(ob.rotation_euler); seed = n * 1.37
        fr = frames[::2]
        vals = np.zeros((len(fr), 2))
        for i, f in enumerate(fr):
            t = (f - 1) / FPS
            a = 0.025 + 0.11 * roar_env(max(t - d * 0.03, 0)) + 0.07 * bark_env(t) + 0.08 * stomp_env(t, 3.02)
            vals[i] = (a * nz(t, 1.3 + 0.2 * (n % 5), seed), a * nz(t, 1.1 + 0.15 * (n % 7), seed + 5))
        for k in range(2):
            fc = cb.fcurves.new("rotation_euler", index=k)
            fc.keyframe_points.add(len(fr)); co = np.empty(len(fr) * 2, np.float32); co[0::2] = fr; co[1::2] = base[k] + vals[:, k]
            fc.keyframe_points.foreach_set("co", co); fc.update()
    return n
