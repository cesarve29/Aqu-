"""The single continuous camera move (no cuts)."""
import math
import bpy
import numpy as np
from mathutils import Vector, Euler, Quaternion

import timeline as T
from timeline import E, ramp

# (frame, camera position, look target, focal length, focus point or None=target)
KEYS = [
    (1, (-2.8, -17.5, 4.6), (0.0, 4.0, 1.5), 28),
    (90, (-1.8, -14.6, 3.4), (0.0, 5.0, 1.45), 30),
    (200, (1.05, -9.7, 1.9), (0.0, 6.2, 1.55), 35),
    (300, (1.5, -3.0, 1.72), (0.0, 7.0, 1.6), 35),
    (420, (2.7, 1.8, 1.55), (0.0, 6.9, 1.55), 38),
    (560, (2.6, 3.4, 1.3), (0.0, 6.7, 1.65), 40),
    (690, (1.9, 3.3, 1.45), (0.0, 6.65, 1.95), 40),
    (790, (1.25, 4.0, 1.75), (0.0, 6.65, 2.0), 45),
    (848, (2.7, 3.8, 1.65), (-0.2, 6.9, 1.8), 40),
    (870, (2.9, 3.5, 1.72), (0.0, 6.0, 1.72), 35),
]
FLIGHT_CAM = [  # camera rides alongside the projectile, keeping its distance
    (890, (3.5, 1.6, 2.05)),
    (915, (3.6, -1.6, 2.0)),
    (940, (3.7, -4.3, 1.75)),
    (950, (3.9, -5.3, 1.6)),
]
LATE = [
    (950, (3.9, -5.3, 1.6), (0.0, -6.4, 1.45), 32),
    (1020, (3.5, -4.9, 1.38), (0.0, -6.5, 1.45), 35),
    (1092, (3.8, -5.5, 1.5), (0.0, -6.4, 1.45), 33),
    (1150, (4.6, -5.2, 1.9), (0.0, -5.6, 1.45), 30),
    (1250, (7.5, -4.0, 3.2), (0.0, -2.5, 1.4), 28),
    (1350, (11.5, -2.6, 4.0), (0.0, -0.5, 1.4), 25),
    (1440, (14.2, -2.6, 4.6), (0.0, 0.0, 1.3), 24),
]


def _fcurve_sampler(keys):
    """Use a temporary object's Bezier F-curves (auto-clamped) to interpolate."""
    tmp = bpy.data.objects.new('_interp', None)
    bpy.context.scene.collection.objects.link(tmp)
    for f, v in keys:
        tmp.location = v
        tmp.keyframe_insert('location', frame=f)
    from util import iter_fcurves
    fcs = sorted(iter_fcurves(tmp.animation_data.action), key=lambda c: c.array_index)
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        fc.update()

    def sample(f):
        return np.array([fc.evaluate(f) for fc in fcs])
    return sample, tmp


def _shake(f):
    """Rotational shake in radians (pitch, yaw, roll) + small translation."""
    t = f / T.FPS
    # gentle handheld drift
    rot = np.array([0.0022 * math.sin(t * 1.7) + 0.0014 * math.sin(t * 3.9 + 1),
                    0.0025 * math.sin(t * 1.3 + 2) + 0.0012 * math.sin(t * 4.3),
                    0.0016 * math.sin(t * 0.9 + 4)])
    tr = np.array([0.006 * math.sin(t * 1.1), 0.0, 0.005 * math.sin(t * 1.6 + 1)])
    for f0, amp, dec, fr in ((E['release'], 0.010, 7, 15), (E['impact'], 0.022, 9, 17),
                             (E['burst'], 0.030, 12, 14), (E['lightning2'], 0.002, 20, 6),
                             (E['lightning3'], 0.002, 20, 6)):
        if f >= f0:
            k = math.exp(-(f - f0) / dec) * amp
            rot += k * np.array([math.sin((f - f0) * fr * 0.37), math.sin((f - f0) * fr * 0.29 + 1.3),
                                 0.5 * math.sin((f - f0) * fr * 0.23 + 2.1)])
            tr += k * 2.0 * np.array([math.sin((f - f0) * 1.9), 0, math.sin((f - f0) * 2.3)])
    # rumble while the orb grinds against the shield
    if E['impact'] < f < E['burst']:
        rot += 0.0025 * np.array([math.sin(f * 2.1), math.sin(f * 2.7 + 1), 0])
    # building tension during the overhead charge
    c = T.charge(int(f))
    rot += 0.0012 * c * c * np.array([math.sin(f * 1.9), math.sin(f * 2.3), 0])
    return rot, tr


def build_camera(cam):
    sc = bpy.context.scene
    cd = cam.data
    cd.sensor_width = 36
    cd.clip_start = 0.05
    cd.clip_end = 400
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 2.8
    cd.dof.aperture_blades = 7
    cd.dof.aperture_ratio = 1.0

    pre = [(f, p) for f, p, _, _ in KEYS]
    post = [(f, p) for f, p, _, _ in LATE]
    pos_keys = pre + FLIGHT_CAM[:-1] + post
    tgt_keys_pre = [(f, t) for f, _, t, _ in KEYS]
    lens_keys = [(f, (l, 0, 0)) for f, _, _, l in KEYS] + [(f, (l, 0, 0)) for f, _, _, l in LATE]
    pos_s, o1 = _fcurve_sampler(pos_keys)
    tgt_s, o2 = _fcurve_sampler(tgt_keys_pre + [(f, t) for f, _, t, _ in LATE])
    lens_s, o3 = _fcurve_sampler(lens_keys)

    for f in range(T.F_START, T.F_END + 1):
        p = pos_s(f)
        tgt = tgt_s(f)
        focus = tgt.copy()
        # during the flight the camera looks at (and focuses on) the projectile
        if E['release'] - 6 <= f <= E['impact'] + 4:
            k_in = ramp(f, E['release'] - 6, E['release'] + 6)
            k_out = ramp(f, E['impact'] - 14, E['impact'] + 4)
            orb = T.orb_pos(min(f + 3, E['impact']))
            g = np.array([0.0, -6.4, 1.45])
            look = orb * (1 - k_out) + g * k_out
            tgt = tgt * (1 - k_in) + look * k_in
            focus = T.orb_pos(f) * (1 - k_out) + g * k_out if f < E['impact'] else g
        # around the charge, focus on the orb when it is in shot
        if E['orb_birth'] < f < E['release'] - 6:
            focus = T.orb_pos(f) * 0.65 + tgt * 0.35
        rot, tr = _shake(f)
        cam.location = Vector(p + tr)
        d = Vector(tgt) - Vector(p)
        q = d.to_track_quat('-Z', 'Y')
        e = q.to_euler()
        e.x += rot[0]
        e.z += rot[1]
        e.y += rot[2]
        cam.rotation_euler = e
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_euler', frame=f)
        cd.lens = float(lens_s(f)[0])
        cd.keyframe_insert('lens', frame=f)
        cd.dof.focus_distance = float(np.linalg.norm(np.asarray(focus) - p))
        cd.dof.keyframe_insert('focus_distance', frame=f)
    for o in (o1, o2, o3):
        bpy.data.objects.remove(o)
    # cinematic exposure: fade in from black, fade out at the end
    vs = sc.view_settings
    for f, ev in ((1, -9.0), (30, -0.6), (60, 0.0), (E['fade_start'], 0.0), (T.F_END, -10.0)):
        vs.exposure = ev
        vs.keyframe_insert('exposure', frame=f)
    return cam
