"""Nubes 3D tipo cúmulo anime: suma de metabolas -> malla con marching cubes.

Salida: assets/cloud3d_{i}.npz  (V, F) en unidades donde el ancho de la nube ~ 2.
"""
import os
import numpy as np
from skimage import measure

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)


def cloud(seed, n_puffs):
    rng = np.random.default_rng(seed)
    puffs = []
    for _ in range(n_puffs + 10):
        t = rng.uniform(-0.85, 0.85)
        mound = np.cos(t * np.pi / 2 / 0.95) ** 1.2
        r = 0.12 + 0.26 * mound * rng.uniform(0.6, 1.0)
        x = t
        y = rng.uniform(-0.22, 0.22) * (0.5 + mound)          # profundidad
        z = r * rng.uniform(0.25, 0.7) + mound * rng.uniform(0.0, 0.35)
        puffs.append((x, y, z, r))
    for _ in range(12):                                       # base de bolitas
        t = rng.uniform(-0.95, 0.95)
        r = rng.uniform(0.08, 0.14)
        puffs.append((t, rng.uniform(-0.25, 0.25), r * 0.6, r))
    res = 0.02
    xs = np.arange(-1.6, 1.6, res)
    ys = np.arange(-1.0, 1.0, res)
    zs = np.arange(-0.2, 1.4, res)
    Xg, Yg, Zg = np.meshgrid(xs, ys, zs, indexing="ij")
    field = np.zeros_like(Xg, dtype=np.float32)
    for x, y, z, r in puffs:
        R = 1.3 * r
        sl = (slice(max(int((x - R + 1.6) / res), 0), int((x + R + 1.6) / res) + 1),
              slice(max(int((y - R + 1.0) / res), 0), int((y + R + 1.0) / res) + 1),
              slice(max(int((z - R + 0.2) / res), 0), int((z + R + 0.2) / res) + 1))
        d2 = ((Xg[sl] - x) ** 2 + (Yg[sl] - y) ** 2 + (Zg[sl] - z) ** 2) / (R * R)
        field[sl] += np.where(d2 < 1, (1 - d2) ** 2, 0)
    # base plana
    field *= np.clip((Zg - 0.0) / 0.05, 0, 1)
    field[[0, -1], :, :] = 0
    field[:, [0, -1], :] = 0
    field[:, :, [0, -1]] = 0
    verts, faces, _, _ = measure.marching_cubes(field, level=0.30, spacing=(res, res, res))
    verts += np.array([xs[0], ys[0], zs[0]])
    return verts.astype(np.float32), faces[:, ::-1].astype(np.int32)


for i in range(5):
    V, F = cloud(200 + i, 18 + 4 * i)
    np.savez_compressed(os.path.join(OUT, f"cloud3d_{i}.npz"), V=V, F=F)
    print(i, len(V), len(F))
