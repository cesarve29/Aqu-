"""Render frames of duelo.blend with the procedural FX handler active.

blender -b duelo.blend -P scene/render_frames.py -- --frames 1,300,950 --pct 50 --spp 16 --out preview/
blender -b duelo.blend -P scene/render_frames.py -- --range 1 1440 --out frames/ --skip-existing
"""
import os
import sys
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--frames', default='')
ap.add_argument('--range', nargs=2, type=int)
ap.add_argument('--step', type=int, default=1)
ap.add_argument('--pct', type=int, default=100)
ap.add_argument('--spp', type=int, default=0)
ap.add_argument('--out', default='preview/')
ap.add_argument('--skip-existing', action='store_true')
ap.add_argument('--no-denoise', action='store_true')
ap.add_argument('--no-mblur', action='store_true')
ap.add_argument('--no-comp', action='store_true')
a = ap.parse_args(argv)

sc = bpy.context.scene
sc.render.resolution_percentage = a.pct
if a.spp:
    if sc.render.engine == 'CYCLES':
        sc.cycles.samples = a.spp
    else:
        sc.eevee.taa_render_samples = a.spp
if a.no_denoise:
    sc.cycles.use_denoising = False
if a.no_mblur:
    sc.render.use_motion_blur = False
if a.no_comp:
    sc.render.use_compositing = False

try:
    import fx_runtime
    fx_runtime.register()
except ImportError as e:
    print('no fx runtime', e)

root = os.path.dirname(HERE)
out = a.out if os.path.isabs(a.out) else os.path.join(root, a.out)
os.makedirs(out, exist_ok=True)

if a.range:
    frames = list(range(a.range[0], a.range[1] + 1, a.step))
else:
    frames = [int(x) for x in a.frames.split(',') if x]

for f in frames:
    path = os.path.join(out, f'f{f:04d}.png')
    if a.skip_existing and os.path.exists(path):
        continue
    t0 = time.time()
    sc.frame_set(f)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f'FRAME {f} {time.time() - t0:.1f}s', flush=True)
