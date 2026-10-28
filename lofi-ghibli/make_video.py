#!/usr/bin/env python3
"""
夜のカフェへ  ·  lofi · una noche con Mochi
Video lofi de estilo anime/acuarela (~2:46) generado 100% por codigo:
Hana cocina bacon con huevos y tostadas, cena con su gato Mochi, se arregla
para salir y pasea de noche por el barrio hasta una cafeteria. Mochi la
acompana en todo momento. Banda sonora lofi sintetizada (soundtrack.py).

Uso:
    python3 make_video.py                  -> noche_con_mochi_1080p.mp4 (1920x1080, 24 fps)
    python3 make_video.py --stills 5 20 40 -> PNGs de esos segundos (para revisar)
Requiere: numpy, Pillow, pycairo, scipy, ffmpeg y la fuente "Klee One" (OFL).
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cairo
import numpy as np
from PIL import Image, ImageFilter

import scenes as S
from gfx import W, H, ease, clamp

FPS = 24
HERE = os.path.dirname(os.path.abspath(__file__))
XF = 1.0  # duracion del fundido entre escenas

# (inicio, fin, funcion)
TIMELINE = [
    (0.0, 14.0, S.sc_establish),
    (14.0, 36.0, S.sc_kitchen),
    (36.0, 52.0, S.sc_food),
    (52.0, 68.0, S.sc_dinner),
    (68.0, 84.0, S.sc_ready),
    (84.0, 112.0, S.sc_street),
    (112.0, 128.0, S.sc_river),
    (128.0, 142.0, S.sc_cafe_out),
    (142.0, 166.0, S.sc_cafe_in),
]
DUR = TIMELINE[-1][1]

_POST = {}


def _post_assets():
    if not _POST:
        rng = np.random.default_rng(7)
        # textura de papel de acuarela + vineta
        low = rng.random((H // 8, W // 8)).astype(np.float32)
        low = np.array(Image.fromarray((low * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
                       .filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255
        fine = rng.random((H, W)).astype(np.float32)
        fine = np.array(Image.fromarray((fine * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),
                        dtype=np.float32) / 255
        paper = 1.0 + 0.05 * (low - 0.5) + 0.05 * (fine - 0.5)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        vig = 1.0 - 0.32 * np.clip(d - 0.45, 0, None) ** 1.6
        _POST['mul'] = (paper * vig)[..., None].astype(np.float32)
        _POST['grain'] = [(rng.standard_normal((H // 2, W // 2)) * 4.0).astype(np.float32) for _ in range(6)]
    return _POST


def render_scene(fn, lt):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0, 0, 0)
    ctx.paint()
    fn(ctx, lt)
    surf.flush()
    buf = np.ndarray((H, W, 4), np.uint8, surf.get_data())
    return buf[:, :, 2::-1].astype(np.float32)


def render_frame(n):
    t = n / FPS
    acc = None
    for (a, b, fn) in TIMELINE:
        lo = a - XF / 2 if a > 0 else 0
        hi = b + XF / 2 if b < DUR else DUR
        if not (lo <= t < hi):
            continue
        img = render_scene(fn, t - a)
        if acc is None:
            acc = img
        else:
            w = ease((t - (a - XF / 2)) / XF)
            acc = acc * (1 - w) + img * w
    img = acc
    P = _post_assets()
    # bloom suave
    small = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR)
    sm = np.asarray(small, dtype=np.float32)
    sm = np.clip(sm - 150, 0, None) * 1.6
    bl = Image.fromarray(np.clip(sm, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9))
    bl = np.asarray(bl.resize((W, H), Image.BILINEAR), dtype=np.float32)
    img = img + bl * 0.45
    # tono lofi: negros levantados, ligero calido
    img = img * np.array([0.95, 0.93, 0.90], np.float32) + np.array([14, 11, 16], np.float32)
    img = img * P['mul']
    g = P['grain'][n % len(P['grain'])]
    g = np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)
    img = img + g[..., None]
    # fundido de entrada / salida
    fade = ease(t / 1.5) * ease((DUR - t) / 3.0)
    if fade < 1:
        img = img * fade
    return np.clip(img, 0, 255).astype(np.uint8)


def _render_chunk(args):
    idx, n0, n1, path = args
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-tune', 'animation',
           '-pix_fmt', 'yuv420p', path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(n0, n1):
        proc.stdin.write(render_frame(n).tobytes())
        if (n - n0) % (FPS * 10) == 0:
            print("  [parte %d] %6.1fs" % (idx, n / FPS), flush=True)
    proc.stdin.close()
    proc.wait()
    return path


def main():
    args = sys.argv[1:]
    if args and args[0] == '--stills':
        os.makedirs(os.path.join(HERE, 'stills'), exist_ok=True)
        for s in args[1:]:
            n = int(round(float(s) * FPS))
            Image.fromarray(render_frame(n)).save(os.path.join(HERE, 'stills', 'frame_%06.2f.png' % float(s)))
        return
    import soundtrack
    wav = os.path.join(HERE, 'soundtrack.wav')
    out = os.path.join(HERE, 'noche_con_mochi_1080p.mp4')
    print("Sintetizando banda sonora...")
    soundtrack.write_wav(wav, soundtrack.build(DUR))
    total = int(DUR * FPS)
    workers = max(1, min(8, os.cpu_count() or 1))
    parts = workers * 2
    bounds = [round(total * k / parts) for k in range(parts + 1)]
    tmp = os.path.join(HERE, 'parts')
    os.makedirs(tmp, exist_ok=True)
    jobs = [(k, bounds[k], bounds[k + 1], os.path.join(tmp, 'part_%02d.mp4' % k)) for k in range(parts)]
    print("Renderizando %d cuadros con %d procesos..." % (total, workers))
    with Pool(workers) as pool:
        files = pool.map(_render_chunk, jobs, chunksize=1)
    lst = os.path.join(tmp, 'list.txt')
    with open(lst, 'w') as f:
        for p in files:
            f.write("file '%s'\n" % p)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-i', wav,
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                    '-movflags', '+faststart', out], check=True)
    for p in files:
        os.remove(p)
    os.remove(lst)
    os.rmdir(tmp)
    print("Listo:", out)


if __name__ == '__main__':
    main()
