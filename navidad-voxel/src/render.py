"""Render driver: previews, full scene renders, event extraction."""
import argparse
import json
import math
import os
import pickle
import subprocess
import sys
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from engine import Renderer, Frame, BUILD, ROOT, smoothstep
import worlds
import models
from common import Ctx, FPS
import story

OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)
FONT_TITLE = "/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf"
FONT_BODY = "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"
if not os.path.exists(FONT_BODY):
    FONT_BODY = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"

WORLD_FUNCS = {"village": worlds.build_village, "forest": worlds.build_forest, "cavern": worlds.build_cavern,
               "forge": worlds.build_forge, "peak": worlds.build_peak}
_world_cache = {}


def get_world(name):
    if name in _world_cache:
        return _world_cache[name]
    pk = os.path.join(BUILD, name + ".pkl")
    vx = os.path.join(BUILD, name + ".vox")
    if os.path.exists(pk) and os.path.exists(vx):
        with open(pk, "rb") as f:
            wd = pickle.load(f)
    else:
        wd = WORLD_FUNCS[name]()
        wd.save(vx)
        with open(pk, "wb") as f:
            pickle.dump(wd, f)
    wd.path = vx
    _world_cache[name] = wd
    return wd


# ------------------------------------------------------------------ overlays
_text_cache = {}


def text_layer(key, W, H, draw_fn):
    k = (key, W, H)
    if k not in _text_cache:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_fn(img, W, H)
        arr = np.asarray(img).astype(np.float32) / 255.0
        _text_cache[k] = arr
    return _text_cache[k]


def shadowed_text(img, xy, text, font, fill=(255, 240, 210), anchor="mm", shadow=6, glow=None):
    W, H = img.size
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.text(xy, text, font=font, fill=(0, 0, 0, 210), anchor=anchor)
    sh = sh.filter(ImageFilter.GaussianBlur(shadow))
    img.alpha_composite(sh)
    if glow:
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(gl)
        d.text(xy, text, font=font, fill=glow, anchor=anchor)
        gl = gl.filter(ImageFilter.GaussianBlur(shadow * 2))
        img.alpha_composite(gl)
    d = ImageDraw.Draw(img)
    d.text(xy, text, font=font, fill=fill + (255,), anchor=anchor)


def draw_title(img, W, H):
    s = H / 1080
    f1 = ImageFont.truetype(FONT_TITLE, int(120 * s))
    f2 = ImageFont.truetype(FONT_BODY, int(48 * s))
    f0 = ImageFont.truetype(FONT_BOLD, int(40 * s))
    shadowed_text(img, (W / 2, H * 0.27), "LAS CRÓNICAS DE PINOALTO", f0, fill=(200, 225, 255), glow=(120, 170, 255, 120), shadow=int(5 * s) + 1)
    shadowed_text(img, (W / 2, H * 0.40), "Tilo y la Estrella del Alba", f1, glow=(255, 190, 90, 160), shadow=int(8 * s) + 1)
    shadowed_text(img, (W / 2, H * 0.53), "Capítulo 1 · Un cuento de Navidad", f2, fill=(230, 235, 255), shadow=int(5 * s) + 1)


def draw_chapter(text):
    def fn(img, W, H):
        s = H / 1080
        f1 = ImageFont.truetype(FONT_TITLE, int(54 * s))
        shadowed_text(img, (int(80 * s), int(H - 90 * s)), text, f1, anchor="ls", glow=(255, 190, 90, 120), shadow=int(5 * s) + 1)
    return fn


CREDITS = [
    (1.0, 7.0, ["Fin del Capítulo 1", "Las Crónicas de Pinoalto · Tilo y la Estrella del Alba"]),
    (7.5, 13.5, ["Mundo voxel con ray tracing en tiempo de CPU", "Música y efectos de sonido sintetizados con código"]),
    (14.0, 21.0, ["¡Feliz Navidad!", "La luz que compartes nunca se apaga"]),
]


def draw_credit(lines):
    def fn(img, W, H):
        s = H / 1080
        f1 = ImageFont.truetype(FONT_TITLE, int(84 * s))
        f2 = ImageFont.truetype(FONT_BODY, int(46 * s))
        shadowed_text(img, (W / 2, H * 0.44), lines[0], f1, glow=(255, 190, 90, 150), shadow=int(7 * s) + 1)
        shadowed_text(img, (W / 2, H * 0.56), lines[1], f2, fill=(230, 235, 255), shadow=int(5 * s) + 1)
    return fn


def composite(img, ctx, W, H):
    out = img.astype(np.float32) / 255.0
    for ov in ctx.overlay:
        kind = ov[0]
        if kind == "title":
            a = ov[1]
            if a <= 0.001:
                continue
            layer = text_layer("title", W, H, draw_title)
        elif kind == "chapter":
            a = ov[2]
            if a <= 0.001:
                continue
            layer = text_layer("ch:" + ov[1], W, H, draw_chapter(ov[1]))
        elif kind == "credits":
            t = ov[1]
            layer = None
            for (t0, t1, lines) in CREDITS:
                if t0 - 0.1 <= t <= t1 + 0.1:
                    a = smoothstep(t0, t0 + 1.2, t) * (1 - smoothstep(t1 - 1.2, t1, t))
                    layer = text_layer("cr:" + lines[0], W, H, draw_credit(lines))
            if layer is None or a <= 0.001:
                continue
        else:
            continue
        al = layer[:, :, 3:4] * a
        out = out * (1 - al) + layer[:, :, :3] * al
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ frame building
def build_ctx(scene, t, record, state):
    wd = get_world(scene["world"])
    f = Frame()
    ctx = Ctx(f, t, scene["start"] + t, wd, scene["name"], record, state)
    scene["fn"](ctx, scene["dur"])
    return ctx


class SceneRenderer:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.r = Renderer(W, H)
        self.cur_world = None
        ids = models.build_models()
        for n, i in ids.items():
            self.r.model(i, os.path.join(models.MODEL_DIR, n + ".vxm"))

    def frame(self, scene, t, state):
        wd = get_world(scene["world"])
        if self.cur_world != scene["world"]:
            self.r.world(wd.path)
            self.cur_world = scene["world"]
        ctx = build_ctx(scene, t, False, state)
        img = self.r.render(ctx.f)
        return composite(img, ctx, self.W, self.H)

    def close(self):
        self.r.close()


def scene_by_name(name):
    tl, total = story.timeline()
    for s in tl:
        if s["name"] == name:
            return s
    raise KeyError(name)


def nframes(scene):
    return int(round(scene["dur"] * FPS))


def preview(names, W=480, H=270, every=1.0, cols=6):
    sr = SceneRenderer(W, H)
    for name in names:
        sc = scene_by_name(name)
        ts = np.arange(0, sc["dur"], every)
        imgs = []
        t0 = time.time()
        for t in ts:
            img = sr.frame(sc, float(t), {})
            imgs.append(Image.fromarray(img))
        rows = (len(imgs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * W, rows * H))
        d = ImageDraw.Draw(sheet)
        for k, im in enumerate(imgs):
            x, y = (k % cols) * W, (k // cols) * H
            sheet.paste(im, (x, y))
            d.text((x + 4, y + 4), "%.1f" % ts[k], fill=(255, 255, 0))
        p = os.path.join(OUT, "preview_%s.jpg" % name)
        sheet.save(p, quality=85)
        print("preview", name, len(imgs), "frames %.1fs" % (time.time() - t0), p, flush=True)
    sr.close()


def still(name, t, W=1920, H=1080):
    sr = SceneRenderer(W, H)
    sc = scene_by_name(name)
    t0 = time.time()
    img = sr.frame(sc, t, {})
    p = os.path.join(OUT, "still_%s_%05.1f.png" % (name, t))
    Image.fromarray(img).save(p)
    print("still", p, "%.2fs" % (time.time() - t0))
    sr.close()


CHUNK = 600  # frames per resumable chunk


def render_scene(name, W=1920, H=1080, crf=18, preset="faster"):
    sc = scene_by_name(name)
    if os.path.exists(os.path.join(OUT, "scenes", "%s.mp4" % name)):
        return
    cdir = os.path.join(OUT, "chunks")
    os.makedirs(cdir, exist_ok=True)
    n = nframes(sc)
    sr = None
    for c0 in range(0, n, CHUNK):
        k = c0 // CHUNK
        path = os.path.join(cdir, "%s_%03d.mp4" % (name, k))
        if os.path.exists(path):
            continue
        if sr is None:
            sr = SceneRenderer(W, H)
        tmp = path + ".part.mp4"
        c1 = min(n, c0 + CHUNK)
        ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                               "-pix_fmt", "yuv420p", "-threads", "2", tmp], stdin=subprocess.PIPE)
        t0 = time.time()
        state = {}
        for f_ in range(c0, c1):
            img = sr.frame(sc, f_ / FPS, state)
            ff.stdin.write(img.tobytes())
        ff.stdin.close()
        ff.wait()
        os.replace(tmp, path)
        print("%s chunk %d (%d-%d of %d) %.2fs/frame" % (name, k, c0, c1, n, (time.time() - t0) / (c1 - c0)), flush=True)
    if sr is not None:
        sr.close()


def extract_events():
    models.build_models()
    tl, total = story.timeline()
    events = []
    for sc in tl:
        state = {}
        n = nframes(sc)
        for k in range(n):
            build_ctx(sc, k / FPS, True, state)
        for (T, name, kw) in state.get("_events", []):
            events.append(dict(t=round(T, 3), name=name, scene=sc["name"], **kw))
        print("events", sc["name"], len(state.get("_events", [])), flush=True)
    meta = dict(total=total, scenes=[{k: v for k, v in s.items() if k != "fn"} for s in tl], events=events)
    with open(os.path.join(BUILD, "timeline.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print("total events", len(events))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["preview", "still", "scene", "events", "all"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--t", type=float, default=0)
    ap.add_argument("--every", type=float, default=1.0)
    ap.add_argument("--w", type=int, default=0)
    ap.add_argument("--h", type=int, default=0)
    a = ap.parse_args()
    if a.mode == "preview":
        names = a.names or [s[0] for s in story.SCENES]
        preview(names, W=a.w or 480, H=a.h or 270, every=a.every)
    elif a.mode == "still":
        still(a.names[0], a.t, W=a.w or 1920, H=a.h or 1080)
    elif a.mode == "scene":
        for n in a.names:
            render_scene(n, W=a.w or 1920, H=a.h or 1080)
    elif a.mode == "events":
        extract_events()
    elif a.mode == "all":
        for s in story.SCENES:
            render_scene(s[0], W=a.w or 1920, H=a.h or 1080)
        print("ALL DONE", flush=True)
