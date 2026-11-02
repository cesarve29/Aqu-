"""Automatic QA: finds frames where Tilo is inside geometry, hidden behind walls, off screen,
or where the camera is inside/very close to geometry."""
import sys, math, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import render, story, models
from models import IDS

ids = models.build_models()
tilo_ids = {ids[k] for k in ids if k.startswith("tilo_")}
torso_ids = {ids["tilo_torso"], ids.get("tilo_torso_ns", -1)}
head_id = ids["tilo_head"]

def solid(v, p):
    X, Y, Z = v.shape
    x, y, z = (int(math.floor(c)) for c in p)
    return 0 <= x < X and 0 <= y < Y and 0 <= z < Z and v[x, y, z] != 0

def march_blocked(v, a, b, start):
    a = np.array(a); b = np.array(b); d = b - a; L = np.linalg.norm(d)
    n = int(L / 0.15)
    for i in range(n):
        s = L * i / n
        if s < start or s > L - 0.35:
            continue
        if solid(v, a + d * (s / L)):
            return s
    return None

def project(cam, tgt, fov, p, W=16 / 9):
    cam = np.array(cam); f = np.array(tgt) - cam; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    q = np.array(p) - cam; z = q @ f
    if z < 0.05: return None
    t = math.tan(math.radians(fov) / 2)
    return (q @ r) / (z * t * W), (q @ u) / (z * t)

names = sys.argv[1:] or [s[0] for s in story.SCENES]
tl, _ = story.timeline()
report = {}
for sc in tl:
    if sc["name"] not in names: continue
    wd = render.get_world(sc["world"]); v = wd.v
    issues = []
    n = render.nframes(sc)
    for k in range(0, n, 6):
        t = k / 60
        ctx = render.build_ctx(sc, t, False, {})
        cam, tgt, fov = ctx.f.cam
        clip = 0.0
        for ln in ctx.f.lines:
            if ln.startswith("CLIP"): clip = float(ln.split()[1])
        tags = []
        if solid(v, cam) and clip <= 0: tags.append("CAM_IN_SOLID")
        torso = head = None
        for ln in ctx.f.lines:
            if ln.startswith("I "):
                p = ln.split(); mid = int(p[1]); pos = (float(p[2]), float(p[3]), float(p[4]))
                if mid in torso_ids: torso = pos
                if mid == head_id: head = pos
        if torso is not None:
            chest = (torso[0], torso[1] + 0.35, torso[2])
            hd = (head[0], head[1] + 0.3, head[2])
            if solid(v, chest) or solid(v, hd): tags.append("TILO_IN_WALL")
            pr = project(cam, tgt, fov, chest)
            onscreen = pr is not None and abs(pr[0]) < 0.95 and abs(pr[1]) < 0.95
            if onscreen:
                b1 = march_blocked(v, cam, chest, clip)
                b2 = march_blocked(v, cam, hd, clip)
                if b1 is not None and b2 is not None: tags.append("TILO_HIDDEN")
        if clip > 0: tags.append("CLIP%.1f" % clip)
        if tags:
            issues.append((round(t, 2), tags))
    # compress into ranges per tag
    ranges = {}
    for t, tags in issues:
        for tg in tags:
            key = tg if not tg.startswith("CLIP") else "CLIP"
            rr = ranges.setdefault(key, [])
            if rr and t - rr[-1][1] <= 0.15: rr[-1][1] = t
            else: rr.append([t, t])
    report[sc["name"]] = ranges
    print(sc["name"], {k: [(a, b) for a, b in vv] for k, vv in ranges.items()}, flush=True)
json.dump(report, open("/tmp/qa_report.json", "w"))
