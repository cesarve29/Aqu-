"""Renderiza la animación con el motor voxel propio.

Uso:
  python3 render.py preview 0,120,240 [ancho] [salida_dir]   -> fotogramas sueltos
  python3 render.py all                                      -> los 480 fotogramas en frames/
"""
import os
import sys
import time
import numpy as np
from PIL import Image
from engine import Engine
import scene

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "preview":
        frames = [int(x) for x in sys.argv[2].split(",")]
        w = int(sys.argv[3]) if len(sys.argv) > 3 else 960
        out = sys.argv[4] if len(sys.argv) > 4 else os.path.join(HERE, "preview")
        eng = Engine(w, w * 9 // 16, 1.5)
    else:
        frames = range(scene.FRAMES)
        out = os.path.join(HERE, "frames")
        eng = Engine(1920, 1080, 2.0)          # supersampling 2x2 (antialiasing)
    os.makedirs(out, exist_ok=True)
    for f in frames:
        fn = os.path.join(out, f"bloque_{f:04d}.png")
        if mode == "all" and os.path.exists(fn):
            continue
        t0 = time.time()
        img = eng.render(scene.state(f, eng))
        Image.fromarray(img).save(fn)
        print(f"frame {f} {time.time() - t0:.2f}s", flush=True)
