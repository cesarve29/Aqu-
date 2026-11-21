"""Render preview stills: blender -b neon_rush.blend -P render_stills.py -- OUTDIR PCT SAMPLES f1 f2 ..."""
import bpy, sys, os, time

argv = sys.argv[sys.argv.index("--") + 1:]
outdir, pct, samples = argv[0], int(argv[1]), int(argv[2])
frames = [int(a) for a in argv[3:]]
sc = bpy.context.scene
sc.render.resolution_percentage = pct
sc.cycles.samples = samples
os.makedirs(outdir, exist_ok=True)
for f in frames:
    t = time.time()
    sc.frame_set(f)
    sc.render.filepath = os.path.join(outdir, f"still_{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t:.1f}s", flush=True)
