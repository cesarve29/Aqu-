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
import characters  # noqa: E402
import anim  # noqa: E402
import fx  # noqa: E402
import camera  # noqa: E402
import comp  # noqa: E402

for mod in (T, util, environment, characters, anim, fx, camera, comp):
    importlib.reload(mod)

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(os.path.dirname(HERE), 'duelo.blend')


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def render_settings():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = 100
    sc.render.fps = T.FPS
    sc.frame_start, sc.frame_end = T.F_START, T.F_END
    c = sc.cycles
    c.samples = 10
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.03
    c.adaptive_min_samples = 6
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.denoising_quality = 'HIGH'
    c.use_light_tree = True
    c.max_bounces = 6
    c.diffuse_bounces = 2
    c.glossy_bounces = 2
    c.transmission_bounces = 4
    c.transparent_max_bounces = 16
    c.volume_bounces = 0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 6.0
    c.blur_glossy = 1.0
    c.seed = 7
    c.use_animated_seed = True
    sc.render.use_persistent_data = True
    sc.render.use_motion_blur = False   # vector blur in the compositor instead
    sc.render.motion_blur_shutter = 0.45
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Punchy'
    except Exception:
        pass
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.render.image_settings.compression = 30
    sc.render.use_lock_interface = True
    sc.view_layers[0].use_pass_mist = True
    sc.view_layers[0].use_pass_vector = True
    sc.view_layers[0].use_pass_z = True


def build_moon_light():
    ld = bpy.data.lights.new('Moon', 'SUN')
    ld.energy = 0.8
    ld.color = (0.62, 0.72, 1.0)
    ld.angle = math.radians(1.2)
    ob = bpy.data.objects.new('Moon', ld)
    bpy.context.scene.collection.objects.link(ob)
    d = environment.MOON_DIR
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    # lightning boosts moon light
    for f0 in (T.E['lightning1'], T.E['lightning2'], T.E['lightning3']):
        for df, v in ((-3, 0.8), (0, 4.0), (2, 1.0), (4, 3.0), (7, 0.85), (14, 0.8)):
            ld.energy = v
            ld.keyframe_insert('energy', frame=f0 + df)
    ld.energy = 0.8
    return ob


def build_test_camera():
    cd = bpy.data.cameras.new('Cam')
    cd.lens = 32
    cd.sensor_width = 36
    ob = bpy.data.objects.new('Cam', cd)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def build_characters():
    C = characters
    coll = util.get_coll('Characters')
    wiz_neon = (1.0, 0.10, 0.78)
    wiz = dict(
        cloth=C.cloth_material('WizRobe', (0.006, 0.004, 0.009, 1), wiz_neon, sheen=(0.18, 0.08, 0.26)),
        cloth2=C.cloth_material('WizMantle', (0.005, 0.003, 0.008, 1), wiz_neon, sheen=(0.18, 0.08, 0.26)),
        hood=C.cloth_material('WizHood', (0.005, 0.003, 0.008, 1), wiz_neon, sheen=(0.18, 0.08, 0.26), zig=False),
        collar=C.cloth_material('WizCollar', (0.006, 0.004, 0.01, 1), wiz_neon, sheen=(0.18, 0.08, 0.26),
                                trim='top', zig=False),
        skin=C.skin_material('WizSkin', (0.20, 0.17, 0.21, 1), wiz_neon),
        eyes=C.emit_material('WizEyes', (1.0, 0.25, 0.85), 0.0),
        void=C.void_material(),
    )
    g_neon = (0.10, 0.85, 1.0)
    gua = dict(
        cloth=C.cloth_material('GuaCloak', (0.012, 0.018, 0.026, 1), g_neon, sheen=(0.12, 0.2, 0.3), zig=False),
        cloth2=C.cloth_material('GuaMantle', (0.018, 0.024, 0.032, 1), g_neon, sheen=(0.12, 0.2, 0.3), zig=False),
        hood=C.cloth_material('GuaHood', (0.014, 0.02, 0.028, 1), g_neon, sheen=(0.12, 0.2, 0.3), zig=False),
        skin=C.metal_material('GuaGauntlet'),
        eyes=C.emit_material('GuaEyes', (0.3, 0.9, 1.0), 6.0),
        void=wiz['void'],
    )
    w_rig, w_parts, w_wind = C.build_character(C.WIZARD, wiz, coll)
    g_rig, g_parts, g_wind = C.build_character(C.GUARDIAN, gua, coll)
    w_rig.location = tuple(T.WIZ)
    g_rig.location = tuple(T.DEF)
    g_rig.rotation_euler = (0, 0, math.pi)
    g_rig.scale = (0.93, 0.93, 0.93)
    bpy.context.view_layer.update()
    w_ctr = C.setup_controls(w_rig, coll)
    g_ctr = C.setup_controls(g_rig, coll)
    anim.animate_wizard(w_rig, w_ctr, wiz, w_parts, w_wind)
    anim.animate_guardian(g_rig, g_ctr, gua, g_parts, g_wind)
    return dict(wiz=(w_rig, w_parts, wiz), gua=(g_rig, g_parts, gua))


def build_rim_lights():
    from mathutils import Vector
    specs = [
        ('RimWizard', (0.6, 10.2, 3.4), (0, 7, 1.6), (0.55, 0.72, 1.0), 260, 2.5),
        ('RimGuardian', (-0.8, -10.0, 3.2), (0, -7, 1.5), (0.55, 0.75, 1.0), 200, 2.5),
        ('FillFront', (3.5, -1.0, 5.0), (0, 2, 1.2), (0.45, 0.55, 0.85), 90, 6.0),
    ]
    for name, loc, tgt, col, energy, size in specs:
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.color = col
        ld.size = size
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        ob.visible_camera = False
        ob.visible_glossy = False if name == 'FillFront' else True


def main():
    reset()
    render_settings()
    environment.build_environment()
    ms = bpy.context.scene.world.mist_settings
    ms.start, ms.depth, ms.falloff = 14.0, 110.0, 'QUADRATIC'
    build_moon_light()
    build_rim_lights()
    if '--no-chars' not in ARGS:
        build_characters()
    fx.build_fx(bpy.data.materials['Monolith'])
    cam = build_test_camera()
    camera.build_camera(cam)
    comp.build_compositor()
    for m in bpy.data.materials:          # lighting comes from explicit lamps
        m.cycles.emission_sampling = 'NONE'
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print('SAVED', OUT)


if __name__ == '__main__':
    main()
