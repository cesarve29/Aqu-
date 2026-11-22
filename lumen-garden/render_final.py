"""Resumable final render.

    blender -b lumen_garden.blend -P render_final.py -a            # CPU (this project's settings)
    blender -b lumen_garden.blend -P render_final.py -a -- --gpu   # NVIDIA RTX: OptiX, more samples

Frames go to ./frames/####.png. Existing frames are skipped and placeholders
are written, so several Blender processes can share the job or resume after a stop.
"""
import bpy, sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
sc = bpy.context.scene
r = sc.render
r.filepath = "//frames/lg_"
r.use_overwrite = False
r.use_placeholder = True

if "--gpu" in argv:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            if any(d.type == backend for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == backend
                sc.cycles.device = "GPU"
                print("Using GPU backend", backend)
                break
        except Exception:
            continue
    # a GPU can afford full quality: native 1080p scope, more samples, light tree
    r.resolution_x, r.resolution_y = 1920, 804
    sc.cycles.samples = 128
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_light_tree = True
    sc.cycles.max_bounces = 8
    sc.cycles.glossy_bounces = 4
    sc.cycles.diffuse_bounces = 3
