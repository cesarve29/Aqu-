"""Fast Workbench animatic to check motion/timing (not the final look)."""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bpy
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'OBJECT'
sc.display.render_aa = 'OFF'
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
sc.render.use_compositing = False
sc.view_settings.view_transform = 'Standard'
for o in sc.objects:
    o.color = (0.55, 0.55, 0.6, 1)
for n in ('Wizard', 'Guardian', 'Orb', 'Shield', 'FX_', 'Rune', 'Lev', 'SW_', 'Blast'):
    for o in sc.objects:
        if o.name.startswith(n):
            o.color = {'Wizard': (0.6, 0.2, 0.7, 1), 'Guardian': (0.2, 0.6, 0.8, 1)}.get(n, (1, 0.4, 0.8, 1))
import fx_runtime; fx_runtime.register()
out = os.path.join(os.path.dirname(HERE), 'preview', 'animatic')
os.makedirs(out, exist_ok=True)
for f in range(1, sc.frame_end + 1):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f'a{f:04d}.jpg')
    sc.render.image_settings.file_format = 'JPEG'
    bpy.ops.render.render(write_still=True)
    if f % 100 == 0:
        print('ANIM', f, flush=True)
