#!/usr/bin/env python3
"""Renderiza todas las tomas en paralelo (N procesos de Cycles con 1 hilo cada uno)."""
import os
import subprocess
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = int(os.environ.get("UMBRA_FPS", 15))
SHOT_FPS = {8: 30, 13: 30}
DUR = {1: 10.0, 2: 10.0, 3: 11.0, 4: 13.0, 5: 9.0, 6: 12.0, 7: 9.0, 8: 2.5,
       9: 12.5, 10: 13.0, 11: 13.0, 12: 11.0, 13: 3.0, 14: 14.5, 15: 13.0, 16: 10.0}
CHUNK = 30


def run(job):
    s, a, b = job
    env = dict(os.environ, UMBRA_THREADS="1")
    r = subprocess.run([sys.executable, os.path.join(HERE, "scenes.py"), "--shot", str(s), "--frames", f"{a}-{b}"],
                       env=env, capture_output=True, text=True)
    ok = r.returncode == 0
    with open(os.path.join(HERE, "build", "render.log"), "a") as f:
        f.write(f"shot {s} frames {a}-{b} {'OK' if ok else 'FAIL'}\n")
        if not ok:
            f.write(r.stderr[-2000:] + "\n")
    return ok


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    jobs = []
    for s, d in DUR.items():
        n = int(round(d * SHOT_FPS.get(s, FPS)))
        for a in range(0, n, CHUNK):
            jobs.append((s, a, min(n, a + CHUNK)))
    with Pool(workers) as p:
        res = p.map(run, jobs, chunksize=1)
    print("done", sum(res), "/", len(res))
