"""Render frames of trex_roar.blend.   python3 render.py blend outdir [start end step] [--pct N] [--samples N]"""
import bpy, sys, os, time
a = [x for x in sys.argv[1:] if not x.startswith("--")]
opt = {sys.argv[i][2:]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}
blend, outdir = a[0], a[1]
start, end, step = (int(a[2]), int(a[3]), int(a[4])) if len(a) >= 5 else (1, 360, 1)
bpy.ops.wm.open_mainfile(filepath=blend)
import addon_utils; addon_utils.enable("cycles")
s = bpy.context.scene
s.render.engine = 'CYCLES'; s.cycles.device = 'CPU'
if "pct" in opt: s.render.resolution_percentage = int(opt["pct"])
if "samples" in opt: s.cycles.samples = int(opt["samples"])
if "threads" in opt: s.render.threads_mode = 'FIXED'; s.render.threads = int(opt["threads"])
if opt.get("fog") == "0" and "Haze" in bpy.data.objects: bpy.data.objects["Haze"].hide_render = True
if opt.get("mblur") == "0": s.render.use_motion_blur = False
os.makedirs(outdir, exist_ok=True)
for f in range(start, end + 1, step):
    p = os.path.join(outdir, f"trex_{f:04d}.png")
    if os.path.exists(p): continue
    open(p, "wb").close()                       # claim the frame (lets several workers share the job)
    t = time.time()
    s.frame_set(f); s.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t:.1f}s", flush=True)
