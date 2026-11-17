"""Builds the whole shot from scratch and saves trex_roar.blend.

    python3 build_scene.py [out.blend] [--reuse-plates]     (needs `pip install bpy`, Blender 5.3)
or  blender -b -P build_scene.py -- out.blend

To make a CPU render of 360 frames practical, the distant forest (everything
further than forest.D_FAR from the clearing) is path-traced once into a
panoramic HDR plate that becomes the world background / ambient light of the
shot.  The dinosaur, terrain, undergrowth, nearby trees and the haze that
carries the light shafts stay fully 3D.
"""
import bpy, sys, os, math, time, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mathutils import Vector
import bmesh
import trex_sdf, trex_build, forest, animate
from trex_build import NT

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
pos_args = [a for a in argv if not a.startswith("--")]
OUT = os.path.abspath(pos_args[0]) if pos_args else os.path.join(HERE, "trex_roar.blend")
OUT_DIR = os.path.dirname(OUT)
CACHE = os.path.join(OUT_DIR, "trex_mesh_cache.npz")
REUSE_PLATES = "--reuse-plates" in argv

SUN_EL = math.radians(15.0)
SUN_ROT = math.radians(17.0)             # sky-texture convention: 0 = +Y, positive towards +X
HAZE = 0.007
WIN_LON = (math.radians(-52), math.radians(52))      # high-res window of the plate (in front of the camera)
WIN_LAT = (math.radians(-22), math.radians(74))
WIN_RES = (1900, 1760)
FULL_RES = (720, 360)


def emission_material(name, color, strength):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    n = NT(mat.node_tree); out = n.nodes["Material Output"]; n.nodes.remove(n.nodes["Principled BSDF"])
    em = n.node("ShaderNodeEmission"); em.inputs["Color"].default_value = color; em.inputs["Strength"].default_value = strength
    n.links.new(em.outputs[0], out.inputs["Surface"])
    return mat

def haze_material(name, density, hole_centre=None, hole_radius=0.0):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    n = NT(mat.node_tree); out = n.nodes["Material Output"]; n.nodes.remove(n.nodes["Principled BSDF"])
    vs = n.node("ShaderNodeVolumeScatter"); vs.inputs["Anisotropy"].default_value = 0.55
    vs.inputs["Color"].default_value = (0.93, 0.95, 1.0, 1)
    if hole_centre is None:
        vs.inputs["Density"].default_value = density
    else:       # no haze inside the near-field cylinder (that part is rendered live every frame)
        geo = n.node("ShaderNodeNewGeometry"); sep = n.node("ShaderNodeSeparateXYZ"); n.links.new(geo.outputs["Position"], sep.inputs[0])
        dx = n.math('SUBTRACT', sep.outputs[0], float(hole_centre[0])); dy = n.math('SUBTRACT', sep.outputs[1], float(hole_centre[1]))
        r = n.math('SQRT', n.math('ADD', n.math('MULTIPLY', dx, dx), n.math('MULTIPLY', dy, dy)))
        n.links.new(n.math('MULTIPLY', n.math('GREATER_THAN', r, hole_radius), density), vs.inputs["Density"])
    n.links.new(vs.outputs[0], out.inputs["Volume"])
    return mat

def render_plates(scene, cam_pos, plate_dir):
    """path-trace the far forest into a windowed hi-res equirect + a low-res full one."""
    os.makedirs(plate_dir, exist_ok=True)
    paths = [os.path.join(plate_dir, "far_window.exr"), os.path.join(plate_dir, "far_full.exr")]
    if REUSE_PLATES and all(os.path.exists(p) for p in paths):
        return paths
    r = scene.render; c = scene.cycles
    pd = bpy.data.cameras.new("PlateCam"); pcam = bpy.data.objects.new("PlateCam", pd); scene.collection.objects.link(pcam)
    pd.type = 'PANO'; pd.panorama_type = 'EQUIRECTANGULAR'; pd.clip_start = 0.1; pd.clip_end = 5000
    pcam.location = cam_pos; pcam.rotation_euler = (math.pi / 2, 0, 0)          # image centre looks along +Y
    old = dict(cam=scene.camera, res=(r.resolution_x, r.resolution_y, r.resolution_percentage), samples=c.samples,
               mb=r.use_motion_blur, comp=r.use_compositing, fmt=r.image_settings.file_format, path=r.filepath,
               depth=r.image_settings.color_depth, mode=r.image_settings.color_mode, thr=c.adaptive_threshold)
    scene.camera = pcam; r.use_motion_blur = False; r.use_compositing = False
    try: r.image_settings.media_type = 'IMAGE'
    except Exception: pass
    r.image_settings.file_format = 'OPEN_EXR'; r.image_settings.color_depth = '16'; r.image_settings.color_mode = 'RGB'
    r.resolution_percentage = 100; c.adaptive_threshold = 0.03
    for (lon, lat, res, spp), p in zip(((WIN_LON, WIN_LAT, WIN_RES, 40), ((-math.pi, math.pi), (-math.pi / 2, math.pi / 2), FULL_RES, 24)), paths):
        pd.longitude_min, pd.longitude_max = lon; pd.latitude_min, pd.latitude_max = lat
        r.resolution_x, r.resolution_y = res; c.samples = spp; r.filepath = p
        t = time.time(); bpy.ops.render.render(write_still=True); print("plate", os.path.basename(p), round(time.time() - t, 1), "s", flush=True)
    scene.camera = old["cam"]; r.resolution_x, r.resolution_y, r.resolution_percentage = old["res"]; c.samples = old["samples"]
    r.use_motion_blur = old["mb"]; r.use_compositing = old["comp"]; r.image_settings.file_format = old["fmt"]; r.filepath = old["path"]
    r.image_settings.color_depth = old["depth"]; r.image_settings.color_mode = old["mode"]; c.adaptive_threshold = old["thr"]
    bpy.data.objects.remove(pcam)
    return paths

def plate_world(paths):
    """world that shows the baked far forest; lighting rays see a clamped version."""
    world = bpy.data.worlds.new("FarForestPlate"); world.use_nodes = True
    n = NT(world.node_tree); bg = n.nodes["Background"]
    tc = n.node("ShaderNodeTexCoord"); nrm = n.node("ShaderNodeVectorMath", operation='NORMALIZE'); n.links.new(tc.outputs["Generated"], nrm.inputs[0])
    sep = n.node("ShaderNodeSeparateXYZ"); n.links.new(nrm.outputs[0], sep.inputs[0])
    lon = n.math('ARCTAN2', sep.outputs[0], sep.outputs[1]); lat = n.math('ARCSINE', sep.outputs[2])
    def tex(path, lon_rng, lat_rng, ext):
        img = bpy.data.images.load(path); img.pack()
        u = n.math('DIVIDE', n.math('SUBTRACT', lon, lon_rng[0]), lon_rng[1] - lon_rng[0])
        v = n.math('DIVIDE', n.math('SUBTRACT', lat, lat_rng[0]), lat_rng[1] - lat_rng[0])
        uv = n.node("ShaderNodeCombineXYZ"); n.links.new(u, uv.inputs[0]); n.links.new(v, uv.inputs[1])
        t = n.node("ShaderNodeTexImage", image=img, extension=ext, interpolation='Cubic'); n.links.new(uv.outputs[0], t.inputs[0])
        return t, u, v
    win, u, v = tex(paths[0], WIN_LON, WIN_LAT, 'EXTEND')
    full, _, _ = tex(paths[1], (-math.pi, math.pi), (-math.pi / 2, math.pi / 2), 'EXTEND')
    def inside(x, m=0.012):      # soft edge so the window blends into the low-res panorama
        return n.math('MULTIPLY', n.smooth(0.0, m, x), n.math('SUBTRACT', 1.0, n.smooth(1.0 - m, 1.0, x)))
    col = n.mix(n.math('MULTIPLY', inside(u), inside(v)), full.outputs["Color"], win.outputs["Color"])
    lp = n.node("ShaderNodeLightPath")
    cl = n.node("ShaderNodeMix", data_type='RGBA', blend_type='DARKEN'); cl.inputs["Factor"].default_value = 1.0
    n.links.new(col, cl.inputs[6]); cl.inputs[7].default_value = (3.0, 3.0, 3.0, 1)
    n.links.new(n.mix(lp.outputs["Is Camera Ray"], cl.outputs[2], col), bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    return world

def main():
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils; addon_utils.enable("cycles")
    scene = bpy.context.scene; scene.name = "TRexRoar"
    def coll(name):
        c = bpy.data.collections.new(name); scene.collection.children.link(c); return c

    # ---------------------------------------------------------------- T-Rex
    if not os.path.exists(CACHE) or os.path.getmtime(CACHE) < os.path.getmtime(os.path.join(HERE, "trex_sdf.py")):
        print("meshing the T-Rex signed distance field ...", flush=True)
        v, f, n = trex_sdf.build()
        np.savez(CACHE, verts=v, faces=f, normals=n, **trex_sdf.vertex_data(v))
    trex_c = coll("TRex")
    parts = trex_build.build_trex(trex_c, CACHE)
    rig = parts["rig"]
    rig.rotation_euler = (0, 0, math.radians(21))
    bpy.context.view_layer.update()
    track, frames = animate.animate_rig(rig)
    print("trex + animation", round(time.time() - t0, 1), flush=True)

    # --------------------------------------------------------------- camera
    peak = track["mouth"][int(6.2 * animate.FPS)]
    cam_base = np.array([peak[0] - 0.35, peak[1] - 2.65, 1.5])
    forest.CLEAR_C = np.array([0.0, 0.5 * (cam_base[1] + 1.0)])
    cam_base[2] += float(forest.ground_h(cam_base[0], cam_base[1]))
    cd = bpy.data.cameras.new("Camera"); cam = bpy.data.objects.new("Camera", cd); scene.collection.objects.link(cam); scene.camera = cam
    cd.sensor_width = 36; cd.lens = 27; cd.clip_start = 0.05; cd.clip_end = 5000
    cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.0; cd.dof.aperture_blades = 7
    animate.animate_camera(cam, track, frames, cam_base)

    # --------------------------------------------------------------- forest
    sun_dir = Vector((math.cos(SUN_EL) * math.sin(SUN_ROT), math.cos(SUN_EL) * math.cos(SUN_ROT), math.sin(SUN_EL)))
    near_c, far_c = coll("ForestNear"), coll("ForestFar")
    fo = forest.build_forest(near_c, far_c, cam_base[:2], math.atan2(sun_dir.y, sun_dir.x), view_xy=peak[:2])
    nsw = animate.animate_plants([p for p in fo["plants"] if p.name in near_c.objects], 0.5 * (cam_base[:2] + np.array([0, -3.0])), frames)
    mcb = animate.make_channelbag(fo["motes"], "MotesDrift")
    for i, v in enumerate([(0.0, 0.5), (0.0, -0.35), (0.0, 0.25)]):
        fc = mcb.fcurves.new("location", index=i); fc.keyframe_points.add(2)
        fc.keyframe_points[0].co = (1, v[0]); fc.keyframe_points[1].co = (animate.N_FRAMES, v[1])
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    fo["motes"].location = (cam_base[0], cam_base[1] + 13.0, 0)
    print("forest", round(time.time() - t0, 1), "near objs", len(near_c.objects), "far objs", len(far_c.objects), "swaying", nsw, flush=True)

    # ---------------------------------------------------------------- light
    sky_world = bpy.data.worlds.new("Sky"); scene.world = sky_world; sky_world.use_nodes = True
    nt = sky_world.node_tree; bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky"); sky.sky_type = 'MULTIPLE_SCATTERING'
    sky.sun_elevation = SUN_EL; sky.sun_rotation = SUN_ROT; sky.sun_disc = False
    sky.air_density = 1.0; sky.aerosol_density = 3.5; sky.ozone_density = 1.0
    nt.links.new(sky.outputs[0], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 0.20

    sd = bpy.data.lights.new("Sun", 'SUN'); sd.energy = 20.0; sd.color = (1.0, 0.74, 0.46); sd.angle = math.radians(2.0)
    sun = bpy.data.objects.new("Sun", sd); scene.collection.objects.link(sun)
    sun.rotation_euler = (-sun_dir).to_track_quat('-Z', 'Y').to_euler()

    # a higher warm "top" sun that only rakes the upper edges: gives the animal its golden rim against the haze
    rd = bpy.data.lights.new("SunRim", 'SUN'); rd.energy = 5.0; rd.color = (1.0, 0.70, 0.40); rd.angle = math.radians(6.0)
    rim = bpy.data.objects.new("SunRim", rd); near_c.objects.link(rim)
    rdir = Vector((math.cos(math.radians(40)) * math.sin(SUN_ROT + 0.25), math.cos(math.radians(40)) * math.cos(SUN_ROT + 0.25), math.sin(math.radians(40))))
    rim.rotation_euler = (-rdir).to_track_quat('-Z', 'Y').to_euler()

    # the visible sun disc (camera only) that the bloom catches; baked into the plate
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    dm = bpy.data.meshes.new("SunDisc"); bm.to_mesh(dm); bm.free()
    disc = bpy.data.objects.new("SunDisc", dm); far_c.objects.link(disc)
    dist = 1500.0; disc.location = Vector((cam_base[0], cam_base[1], cam_base[2])) + sun_dir * dist; disc.scale = (dist * math.tan(math.radians(0.8)),) * 3
    dm.materials.append(emission_material("SunDisc", (1.0, 0.76, 0.48, 1), 1800.0))
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter", "visible_shadow"):
        setattr(disc, attr, False)

    # soft cool fill from behind the camera (sky bounce) so the face and teeth read
    fd = bpy.data.lights.new("Fill", 'AREA'); fd.shape = 'DISK'; fd.size = 9.0; fd.energy = 2600.0; fd.color = (0.86, 0.90, 1.0)
    fill = bpy.data.objects.new("Fill", fd); near_c.objects.link(fill)
    fill.location = (cam_base[0] - 5.0, cam_base[1] - 3.0, 7.5)
    fill.rotation_euler = (Vector(peak) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    kd = bpy.data.lights.new("Kicker", 'AREA'); kd.shape = 'DISK'; kd.size = 5.0; kd.energy = 1100.0; kd.color = (1.0, 0.72, 0.45)
    kick = bpy.data.objects.new("Kicker", kd); near_c.objects.link(kick)
    kick.location = (cam_base[0] + 6.5, cam_base[1] + 2.0, 0.8)
    kick.rotation_euler = (Vector(peak) - kick.location).to_track_quat('-Z', 'Y').to_euler()
    for l in (fd, kd):
        try: l.cycles.cast_shadow = True
        except Exception: pass

    # morning haze: a live cylinder over the clearing (light shafts) + a far shell baked into the plate
    cc = forest.CLEAR_C; R = forest.D_FAR + 2.0
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=R, radius2=R, depth=36.0)
    hm = bpy.data.meshes.new("HazeNear"); bm.to_mesh(hm); bm.free()
    haze = bpy.data.objects.new("HazeNear", hm); near_c.objects.link(haze); haze.location = (cc[0], cc[1], 17.5); haze.display_type = 'WIRE'
    hm.materials.append(haze_material("HazeNear", HAZE))
    haze.visible_diffuse = False; haze.visible_glossy = False; haze.visible_transmission = False
    haze.hide_render = "--live-haze" not in argv       # optional: true volumetric shafts in the clearing (about 30% slower)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    fm = bpy.data.meshes.new("HazeFar"); bm.to_mesh(fm); bm.free()
    hazef = bpy.data.objects.new("HazeFar", fm); far_c.objects.link(hazef); hazef.scale = (300, 300, 50); hazef.location = (cc[0], cc[1] + 20, 24.5); hazef.display_type = 'WIRE'
    fm.materials.append(haze_material("HazeFar", HAZE, cc, R))

    # --------------------------------------------------------------- render
    r = scene.render; r.engine = 'CYCLES'
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, 100
    r.fps = animate.FPS; scene.frame_start = 1; scene.frame_end = animate.N_FRAMES; scene.frame_set(1)
    c = scene.cycles
    c.device = 'CPU'; c.samples = 16; c.use_adaptive_sampling = True; c.adaptive_threshold = 0.06; c.adaptive_min_samples = 6
    c.use_denoising = True; c.denoiser = 'OPENIMAGEDENOISE'; c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.max_bounces = 3; c.diffuse_bounces = 0; c.glossy_bounces = 2; c.transmission_bounces = 3; c.transparent_max_bounces = 4; c.volume_bounces = 0
    c.sample_clamp_indirect = 5.0; c.sample_clamp_direct = 0.0; c.caustics_reflective = False; c.caustics_refractive = False
    r.use_motion_blur = True; r.motion_blur_shutter = 0.4
    r.use_persistent_data = True
    try: r.image_settings.media_type = 'IMAGE'
    except Exception: pass
    r.image_settings.file_format = 'PNG'; r.image_settings.color_mode = 'RGB'; r.image_settings.compression = 30
    r.filepath = "//frames/trex_"
    vs = scene.view_settings
    for attr, val in (("view_transform", "AgX"), ("look", "AgX - Punchy")):
        try: setattr(vs, attr, val)
        except Exception as e: print("view setting", attr, e)
    vs.exposure = 0.0

    # ------------------------------------------------- bake the far forest
    hide_for_plate = [trex_c, near_c]
    for cl in hide_for_plate: cl.hide_render = True
    fo["ground"].hide_render = False
    scene.collection.objects.link(fo["ground"]); near_c.objects.unlink(fo["ground"])     # terrain is in both passes
    paths = render_plates(scene, Vector(cam_base) + Vector((0, -0.35, 0)), os.path.join(OUT_DIR, "plates"))
    for cl in hide_for_plate: cl.hide_render = False
    far_c.hide_render = True; far_c.hide_viewport = True
    scene.world = plate_world(paths)
    print("plates", round(time.time() - t0, 1), flush=True)

    # ----------------------------------------------------------- compositor
    # near-field haze from the mist pass (matches the haze baked into the plate), then bloom
    img = bpy.data.images.load(paths[0]); px = np.array(img.pixels[:], np.float32).reshape(img.size[1], img.size[0], -1)[..., :3]
    row0 = int((0.0 - WIN_LAT[0]) / (WIN_LAT[1] - WIN_LAT[0]) * img.size[1])
    band = px[row0 + 8: row0 + 70].reshape(-1, 3); lum = band.sum(1)
    haze_col = band[lum < np.quantile(lum, 0.7)].mean(0) * 1.0
    bpy.data.images.remove(img)
    print("haze colour", haze_col, flush=True)
    R = forest.D_FAR + 2.0
    scene.view_layers[0].use_pass_mist = True
    scene.world.mist_settings.start = 0.0; scene.world.mist_settings.depth = R; scene.world.mist_settings.falloff = 'LINEAR'
    tree = bpy.data.node_groups.new("TRexComp", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    n = NT(tree)
    rl = n.node("CompositorNodeRLayers"); rl.scene = scene
    go = n.node("NodeGroupOutput")
    fog = n.math('SUBTRACT', 1.0, n.math('EXPONENT', n.math('MULTIPLY', rl.outputs["Mist"], -HAZE * R * (0.0 if "--live-haze" in argv else 1.0))))
    mixn = n.node("ShaderNodeMix", data_type='RGBA', blend_type='MIX')
    n.links.new(fog, mixn.inputs["Factor"]); n.links.new(rl.outputs["Image"], mixn.inputs[6]); mixn.inputs[7].default_value = (*[float(x) for x in haze_col], 1.0)
    gl = n.node("CompositorNodeGlare")
    gl.inputs["Type"].default_value = 'Fog Glow'; gl.inputs["Quality"].default_value = 'High'
    gl.inputs["Threshold"].default_value = 2.5; gl.inputs["Strength"].default_value = 0.55; gl.inputs["Size"].default_value = 0.8
    n.links.new(mixn.outputs[2], gl.inputs["Image"]); n.links.new(gl.outputs["Image"], go.inputs["Image"])
    scene.compositing_node_group = tree
    r.use_compositing = True; r.compositor_device = 'CPU'

    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print("saved", OUT, round(time.time() - t0, 1), "s", flush=True)

main()
