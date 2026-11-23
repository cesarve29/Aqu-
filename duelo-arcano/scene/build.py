"""Build the whole scene and save duelo.blend.

blender -b --factory-startup -P scene/build.py -- [--preview]
"""
import os
import sys
import math
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import timeline as T  # noqa: E402
import util  # noqa: E402
import environment  # noqa: E402

for mod in (T, util, environment):
    importlib.reload(mod)

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(os.path.dirname(HERE), 'duelo.blend')


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def render_settings():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = 100
    sc.render.fps = T.FPS
    sc.frame_start, sc.frame_end = T.F_START, T.F_END
    e = sc.eevee
    e.taa_render_samples = 12
    e.use_raytracing = True
    e.ray_tracing_method = 'SCREEN'
    try:
        e.ray_tracing_options.resolution_scale = '2'
        e.ray_tracing_options.use_denoise = True
    except Exception as ex:
        print('rt opts', ex)
    e.use_fast_gi = False
    e.use_shadows = True
    e.shadow_ray_count = 1
    e.shadow_step_count = 6
    e.use_volumetric_shadows = True
    e.volumetric_tile_size = '8'
    e.volumetric_samples = 48
    e.volumetric_start = 0.5
    e.volumetric_end = 70.0
    e.volumetric_light_clamp = 0.0
    e.clamp_surface_indirect = 10.0
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.45
    try:
        e.motion_blur_steps = 1
    except Exception:
        pass
    sc.render.film_transparent = False
    sc.render.filter_size = 1.3
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 30
    sc.render.use_lock_interface = True
    sc.view_layers[0].use_pass_mist = True


def build_moon_light():
    ld = bpy.data.lights.new('Moon', 'SUN')
    ld.energy = 0.55
    ld.color = (0.62, 0.72, 1.0)
    ld.angle = math.radians(1.2)
    ob = bpy.data.objects.new('Moon', ld)
    bpy.context.scene.collection.objects.link(ob)
    d = environment.MOON_DIR
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    # lightning boosts moon light
    for f0 in (T.E['lightning1'], T.E['lightning2'], T.E['lightning3']):
        for df, v in ((-3, 0.55), (0, 3.5), (2, 0.8), (4, 2.6), (7, 0.6), (14, 0.55)):
            ld.energy = v
            ld.keyframe_insert('energy', frame=f0 + df)
    ld.energy = 0.55
    return ob


def build_test_camera():
    cd = bpy.data.cameras.new('Cam')
    cd.lens = 32
    cd.sensor_width = 36
    ob = bpy.data.objects.new('Cam', cd)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def main():
    reset()
    render_settings()
    environment.build_environment()
    ms = bpy.context.scene.world.mist_settings
    ms.start, ms.depth, ms.falloff = 14.0, 110.0, 'QUADRATIC'
    build_moon_light()
    cam = build_test_camera()
    if 'camera' in sys.modules:
        pass
    try:
        import camera as cammod
        importlib.reload(cammod)
        cammod.build_camera(cam)
    except ImportError:
        from mathutils import Vector
        cam.location = (1.2, -10.5, 1.9)
        d = Vector((0, 7, 1.6)) - cam.location
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print('SAVED', OUT)


if __name__ == '__main__':
    main()
