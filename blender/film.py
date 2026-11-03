"""
Cortometraje 3D procedural (Blender 5.2, EEVEE) - personaje original.

Uso:
  python3 film.py --shot N --still FRAME --out ruta.png      # un fotograma
  python3 film.py --shot N --frames A-B --outdir carpeta/    # secuencia

Planos (24 fps):
  1  Circuito de luz que forma el emblema          (240 f / 10 s)
  2  Ciudad nocturna, figura encapuchada de espaldas (288 f / 12 s)
  3  Primer plano: cae la capucha, pelo al viento   (312 f / 13 s)
  4  Energia cosmica alrededor de la figura         (360 f / 15 s)
  5  Plano general, destello y titulo               (240 f / 10 s)
"""
import bpy, bmesh, math, random, sys, os, argparse
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FPS = 24
RES_X, RES_Y = 1920, 804          # 2.39:1, se rellena a 1080 en post
SHOT_LEN = {1: 240, 2: 288, 3: 312, 4: 360, 5: 240}

PALETTE_CITY = [(0.1, 0.9, 1.0), (1.0, 0.25, 0.7), (1.0, 0.55, 0.15),
                (0.2, 1.0, 0.45), (0.45, 0.4, 1.0), (1.0, 0.85, 0.5)]


# ----------------------------------------------------------------- utilidades
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x, s.render.resolution_y = RES_X, RES_Y
    s.render.resolution_percentage = 100
    s.render.fps = FPS
    s.eevee.taa_render_samples = 48
    s.eevee.use_shadows = True
    s.eevee.use_raytracing = True
    s.eevee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    s.render.film_transparent = False
    try:
        s.view_settings.view_transform = 'AgX'
        s.view_settings.look = 'AgX - High Contrast'
    except Exception:
        pass
    s.render.image_settings.file_format = 'PNG'
    s.render.image_settings.color_depth = '8'
    return s


def new_mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    return m, nt, out


def mat_emit(name, color, strength):
    m, nt, out = new_mat(name)
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*color, 1)
    e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], out.inputs['Surface'])
    return m


def mat_principled(name, color, rough=0.5, metal=0.0, sheen=0.0, coat=0.0,
                   sss=0.0, emit=None, emit_str=0.0):
    m, nt, out = new_mat(name)
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['Sheen Weight'].default_value = sheen
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Subsurface Weight'].default_value = sss
    if emit:
        p.inputs['Emission Color'].default_value = (*emit, 1)
        p.inputs['Emission Strength'].default_value = emit_str
    nt.links.new(p.outputs[0], out.inputs['Surface'])
    return m, nt, p


def mat_random_emit(name, palette, smin, smax):
    """Emision cuyo color/intensidad depende del Random de cada objeto."""
    m, nt, out = new_mat(name)
    info = nt.nodes.new('ShaderNodeObjectInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    n = len(palette)
    while len(els) < n:
        els.new(0.5)
    for i, c in enumerate(palette):
        els[i].position = i / n
        els[i].color = (*c, 1)
    rng = nt.nodes.new('ShaderNodeMapRange')
    rng.inputs['To Min'].default_value = smin
    rng.inputs['To Max'].default_value = smax
    # segunda semilla para la intensidad
    mth = nt.nodes.new('ShaderNodeMath'); mth.operation = 'FRACT'
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 7.31
    e = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(info.outputs['Random'], ramp.inputs['Fac'])
    nt.links.new(info.outputs['Random'], mul.inputs[0])
    nt.links.new(mul.outputs[0], mth.inputs[0])
    nt.links.new(mth.outputs[0], rng.inputs['Value'])
    nt.links.new(ramp.outputs['Color'], e.inputs['Color'])
    nt.links.new(rng.outputs['Result'], e.inputs['Strength'])
    nt.links.new(e.outputs[0], out.inputs['Surface'])
    return m


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    return link(bpy.data.objects.new(name, me))


def ico(name, r=1.0, sub=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    return link(e)


def key(obj, path, frame, value, interp=None):
    setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)


def set_linear(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    try:
        curves = ad.action.fcurves
    except AttributeError:      # acciones por capas (Blender 4.4+)
        curves = [fc for l in ad.action.layers for st in l.strips
                  for cb in st.channelbags for fc in cb.fcurves]
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def camera(name, loc, target, lens=50, fstop=2.0, focus_obj=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_end = 2000
    cam = link(bpy.data.objects.new(name, cd))
    cam.location = loc
    tc = cam.constraints.new('TRACK_TO')
    tc.target = target
    tc.track_axis = 'TRACK_NEGATIVE_Z'
    tc.up_axis = 'UP_Y'
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cd.dof.focus_object = focus_obj or target
    bpy.context.scene.camera = cam
    return cam


def area_light(name, loc, target, color, power, size=1.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.color = color; ld.energy = power; ld.size = size
    l = link(bpy.data.objects.new(name, ld))
    l.location = loc
    c = l.constraints.new('TRACK_TO'); c.target = target
    c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return l


def point_light(name, loc, color, power, radius=0.1):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.color = color; ld.energy = power; ld.shadow_soft_size = radius
    l = link(bpy.data.objects.new(name, ld)); l.location = loc
    return l


def world_color(color, strength=1.0):
    w = bpy.data.worlds.new('W'); bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = w.node_tree.nodes.get('Background') or w.node_tree.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*color, 1)
    bg.inputs['Strength'].default_value = strength
    return w


def compositor(bloom=0.8, threshold=0.6, size=0.85):
    s = bpy.context.scene
    ng = bpy.data.node_groups.new('Comp', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    gl = ng.nodes.new('CompositorNodeGlare')
    for v in ('Bloom', 'BLOOM'):
        try:
            gl.inputs['Type'].default_value = v; break
        except Exception:
            pass
    for nm, v in (('Quality', 'High'), ('Quality', 'HIGH')):
        try:
            gl.inputs[nm].default_value = v; break
        except Exception:
            pass
    gl.inputs['Threshold'].default_value = threshold
    gl.inputs['Strength'].default_value = bloom
    gl.inputs['Size'].default_value = size
    ld = ng.nodes.new('CompositorNodeLensdist')
    ld.inputs['Dispersion'].default_value = 0.012
    ld.inputs['Distortion'].default_value = -0.01
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
    ng.links.new(gl.outputs['Image'], ld.inputs['Image'])
    ng.links.new(ld.outputs['Image'], out.inputs[0])
    s.compositing_node_group = ng


# ---------------------------------------------------------- emblema original
def emblem(name, radius, mat, bevel, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Emblema original: anillo partido, tres rayos y un rombo central.
    Dibujado en el plano XY local. Devuelve lista de curvas."""
    curves = []

    def polyline(pts, cyclic=False, nm='e'):
        cd = bpy.data.curves.new(name + nm, 'CURVE')
        cd.dimensions = '3D'
        cd.bevel_depth = bevel
        cd.bevel_resolution = 2
        sp = cd.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p[0], p[1], 0, 1)
        sp.use_cyclic_u = cyclic
        o = link(bpy.data.objects.new(name + nm, cd))
        o.data.materials.append(mat)
        o.parent = parent; o.location = loc; o.rotation_euler = rot
        curves.append(o)
        return o

    # anillo exterior en tres arcos (huecos a 90, 210, 330 grados)
    for k in range(3):
        a0 = math.radians(90 + 120 * k + 14)
        a1 = math.radians(90 + 120 * (k + 1) - 14)
        pts = [(radius * math.cos(a0 + (a1 - a0) * i / 24),
                radius * math.sin(a0 + (a1 - a0) * i / 24)) for i in range(25)]
        polyline(pts, nm=f'arc{k}')
    # tres rayos hacia dentro desde los huecos
    for k in range(3):
        a = math.radians(90 + 120 * k)
        polyline([(radius * 1.12 * math.cos(a), radius * 1.12 * math.sin(a)),
                  (radius * 0.55 * math.cos(a), radius * 0.55 * math.sin(a))], nm=f'ray{k}')
    # anillo interior
    pts = [(radius * 0.32 * math.cos(2 * math.pi * i / 40),
            radius * 0.32 * math.sin(2 * math.pi * i / 40)) for i in range(40)]
    polyline(pts, cyclic=True, nm='inner')
    # rombo central
    r = radius * 0.16
    polyline([(0, r * 1.5), (r, 0), (0, -r * 1.5), (-r, 0)], cyclic=True, nm='core')
    return curves


# ------------------------------------------------------------------ personaje
import numpy as np
from mathutils import Matrix
import mhload

SCALE = 1.08
TORSO = ('spine', 'pelvis', 'upperleg', 'lowerleg', 'root', 'breast', 'clavicle', 'neck01', 'shoulder01')
ARMS = ('upperarm', 'lowerarm', 'shoulder01')
HANDS = ('finger', 'metacarpal', 'wrist')


def fcurves_of(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return []
    try:
        return list(ad.action.fcurves)
    except AttributeError:
        out = []
        for l in ad.action.layers:
            for st in l.strips:
                for cb in st.channelbags:
                    out += list(cb.fcurves)
        return out


def add_noise(obj, path, strength, scale, seed=0):
    for i, fc in enumerate(fcurves_of(obj)):
        if fc.data_path == path:
            m = fc.modifiers.new('NOISE')
            m.strength = strength; m.scale = scale; m.phase = seed * 13 + i * 7.3


def hair_wind_group(strength, gust, speed):
    ng = bpy.data.node_groups.new('HairWind', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links.new
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    pos = N.new('GeometryNodeInputPosition')
    tm = N.new('GeometryNodeInputSceneTime')
    sp = N.new('ShaderNodeMath'); sp.operation = 'MULTIPLY'; sp.inputs[1].default_value = speed
    nz = N.new('ShaderNodeTexNoise'); nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = 7.0; nz.inputs['Detail'].default_value = 3
    cen = N.new('ShaderNodeVectorMath'); cen.operation = 'SUBTRACT'
    cen.inputs[1].default_value = (0.5, 0.5, 0.5)
    par = N.new('GeometryNodeSplineParameter')
    pw = N.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6
    k = N.new('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.inputs[1].default_value = strength
    sc = N.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'
    sn = N.new('ShaderNodeMath'); sn.operation = 'SINE'
    sn2 = N.new('ShaderNodeMath'); sn2.operation = 'MULTIPLY_ADD'
    sn2.inputs[1].default_value = 0.35; sn2.inputs[2].default_value = 0.65
    gk = N.new('ShaderNodeMath'); gk.operation = 'MULTIPLY'
    gs = N.new('ShaderNodeVectorMath'); gs.operation = 'SCALE'
    gs.inputs[0].default_value = gust
    add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    setp = N.new('GeometryNodeSetPosition')
    L(tm.outputs['Seconds'], sp.inputs[0]); L(sp.outputs[0], nz.inputs['W'])
    L(pos.outputs[0], nz.inputs['Vector'])
    L(nz.outputs['Color'], cen.inputs[0])
    L(par.outputs['Factor'], pw.inputs[0]); L(pw.outputs[0], k.inputs[0])
    L(cen.outputs[0], sc.inputs[0]); L(k.outputs[0], sc.inputs['Scale'])
    L(sp.outputs[0], sn.inputs[0]); L(sn.outputs[0], sn2.inputs[0])
    L(sn2.outputs[0], gk.inputs[0]); L(pw.outputs[0], gk.inputs[1])
    L(gk.outputs[0], gs.inputs['Scale'])
    L(sc.outputs[0], add.inputs[0]); L(gs.outputs[0], add.inputs[1])
    L(gi.outputs[0], setp.inputs['Geometry']); L(add.outputs[0], setp.inputs['Offset'])
    L(setp.outputs[0], go.inputs[0])
    return ng


class Profile:
    """Secciones del torso medidas sobre el cuerpo real (x max, y min/max por altura)."""

    def __init__(self, co, mask, z0, z1, step=0.03):
        zs, rx, y0, y1 = [], [], [], []
        for z in np.arange(z0, z1 + 1e-6, step):
            m = mask & (np.abs(co[:, 2] - z) < step * 0.75)
            if m.sum() < 4:
                continue
            zs.append(z); rx.append(np.abs(co[m, 0]).max())
            y0.append(co[m, 1].min()); y1.append(co[m, 1].max())
        k = np.ones(3) / 3
        sm = lambda a: np.convolve(np.pad(a, 1, mode='edge'), k, mode='valid')
        self.z = np.array(zs); self.rx = sm(np.array(rx))
        self.y0 = sm(np.array(y0)); self.y1 = sm(np.array(y1))

    def at(self, z):
        rx = np.interp(z, self.z, self.rx); y0 = np.interp(z, self.z, self.y0)
        y1 = np.interp(z, self.z, self.y1)
        return rx, (y1 - y0) / 2, (y0 + y1) / 2


class Figure:
    """Personaje original sobre cuerpo MakeHuman (CC0) con esqueleto:
    abrigo largo a medida con faldones abiertos, esclavina, cuello alto,
    ribetes de luz, cinturon, guantes, botas, bufanda carmesi y pelo blanco
    de hebras reales.  Mira hacia +Y."""

    def __init__(self, loc=(0, 0, 0), hood_up=True, right_arm_up=False, seed=7,
                 hair_wind=0.03, hair_gust=(0.015, -0.01, 0.0), scarf_lift=False):
        random.seed(seed); np.random.seed(seed)
        self.root = empty('FigRoot', (0, 0, 0))
        self.wind = empty('Wind', (0, 0, 0))
        self._materials()
        h = self.h = mhload.Human()
        h.arm.scale = (SCALE,) * 3
        h.arm.parent = self.root
        self.arm = h.arm
        self.arm_rest()
        if right_arm_up:
            self.arm_up()
        self._measure()
        self._body_materials()
        self._coat()
        self._capelet()
        self._collar()
        self._belt()
        self._sleeves()
        self._boots()
        self._face()
        self._hair(hair_wind, hair_gust)
        self._hood(hood_up)
        if scarf_lift is None:
            self._scarf(False)
        x, ry, cy = self.prof.at(self.z_cape_mid)
        emblem('BackEmblem', 0.1, self.glow_mat, 0.003, parent=None,
               loc=(0, cy - ry - self.cape_off(self.z_cape_mid) - 0.006, self.z_cape_mid),
               rot=(math.radians(90), 0, math.radians(180)))
        self.root.location = loc

    # ---- poses
    def arm_rest(self, frame=None):
        self.h.pose('upperarm01.L', (-44, 0, 6), frame); self.h.pose('upperarm01.R', (-44, 0, -6), frame)
        self.h.pose('lowerarm01.L', (0, 0, 0), frame); self.h.pose('lowerarm01.R', (0, 0, 0), frame)

    def arm_up(self, frame=None):
        self.h.pose('upperarm01.R', (55, 0, 62), frame)
        self.h.pose('lowerarm01.R', (0, 0, -10), frame)

    def head(self, rot, frame=None):
        self.h.pose('head', rot, frame)

    def parent_bone(self, obj, bone):
        bpy.context.view_layer.update()
        arm = self.arm; pb = arm.pose.bones[bone]
        M = arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
        mw = obj.matrix_world.copy()
        obj.parent = arm; obj.parent_type = 'BONE'; obj.parent_bone = bone
        obj.matrix_parent_inverse = M.inverted()
        obj.matrix_basis = mw

    # ---- medicion del cuerpo posado
    def _measure(self):
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = self.h.body.evaluated_get(dg)
        me = ev.to_mesh()
        mw = self.h.body.matrix_world
        co = np.array([tuple(mw @ v.co) for v in me.vertices])
        nm = np.array([tuple((mw.to_3x3() @ v.normal).normalized()) for v in me.vertices])
        ev.to_mesh_clear()
        names = {g.index: g.name for g in self.h.body.vertex_groups}
        dom = []
        for v in self.h.body.data.vertices:
            dom.append(names[max(v.groups, key=lambda g: g.weight).group] if v.groups else '')
        self.co, self.nm, self.dom = co, nm, dom
        torso = np.array([d.startswith(TORSO) for d in dom])
        self.z_neck = self.arm.matrix_world @ self.arm.pose.bones['neck01'].head
        self.z_neck = self.z_neck.z
        self.z_shoulder = (self.arm.matrix_world @ self.arm.pose.bones['upperarm01.L'].head).z
        self.z_waist = (self.arm.matrix_world @ self.arm.pose.bones['spine03'].head).z
        self.prof = Profile(co, torso, 0.15, self.z_neck + 0.02)
        hd = np.array([d == 'head' for d in dom])
        self.head_c = Vector(((co[hd, 0].min() + co[hd, 0].max()) / 2,
                              (co[hd, 1].min() + co[hd, 1].max()) / 2 - 0.01,
                              co[hd, 2].min() * 0.35 + co[hd, 2].max() * 0.65))
        self.head_top = co[hd, 2].max()
        self.z_hem = 0.3
        self.z_cape_top = self.z_shoulder + 0.07
        self.z_cape_bot = self.z_shoulder - 0.27
        self.z_cape_mid = self.z_shoulder - 0.13
        self.slit_top = 0.72

    def cxyz(self, z, a, inflate=0.0, folds=True, ease=None):
        """Punto de la superficie del abrigo a la altura z y angulo a."""
        zw = self.z_waist
        rx, ry, cy = self.prof.at(min(max(z, self.prof.z[0]), self.prof.z[-1]))
        e = 0.03 if ease is None else ease
        if z < zw:   # falda que se abre hacia abajo
            rxw, ryw, cyw = self.prof.at(zw)
            k = (zw - z)
            rx = max(rx + e, rxw + e + k * 0.2); ry = max(ry + e, ryw + e + k * 0.15)
            cy = cyw * (1 - min(1, k * 2)) + cy * min(1, k * 2)
        else:
            rx += e; ry += e
        f = 1 - abs(z - (self.z_shoulder - 0.03)) / 0.12
        ex = 1 - 0.5 * smooth(f) if f > 0 else 1.0
        if folds:
            inflate += 0.01 * math.sin(7 * a + z * 2.5) * max(0.0, (zw - z) / zw) \
                       + 0.004 * math.sin(13 * a - z * 4) * max(0.0, (0.9 - z) / 0.9)
        c, s_ = math.cos(a), math.sin(a)
        return ((rx + inflate) * math.copysign(abs(c) ** ex, c), cy + (ry + inflate) * s_, z)

    # ---- materiales
    def _materials(self):
        def fabric(name, col, sheen_tint, bump_s=0.3, rough=0.82):
            m, nt, p = mat_principled(name, col, rough=rough, sheen=0.5)
            p.inputs['Sheen Tint'].default_value = (*sheen_tint, 1)
            tc = nt.nodes.new('ShaderNodeTexCoord')
            nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 11
            nz.inputs['Detail'].default_value = 8
            wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 320
            wv.inputs['Distortion'].default_value = 1.5
            wv2 = nt.nodes.new('ShaderNodeTexWave'); wv2.inputs['Scale'].default_value = 320
            wv2.bands_direction = 'Y'
            a1 = nt.nodes.new('ShaderNodeMath'); a1.operation = 'ADD'
            a2 = nt.nodes.new('ShaderNodeMath'); a2.operation = 'ADD'
            b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump_s
            b.inputs['Distance'].default_value = 0.002
            for t in (nz, wv, wv2):
                nt.links.new(tc.outputs['Object'], t.inputs['Vector'])
            nt.links.new(wv.outputs['Fac'], a1.inputs[0]); nt.links.new(wv2.outputs['Fac'], a1.inputs[1])
            nt.links.new(a1.outputs[0], a2.inputs[0]); nt.links.new(nz.outputs['Fac'], a2.inputs[1])
            nt.links.new(a2.outputs[0], b.inputs['Height'])
            nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
            mr = nt.nodes.new('ShaderNodeMapRange')
            mr.inputs['To Min'].default_value = 0.75; mr.inputs['To Max'].default_value = 1.2
            mix = nt.nodes.new('ShaderNodeVectorMath'); mix.operation = 'SCALE'
            mix.inputs[0].default_value = col
            nt.links.new(nz.outputs['Fac'], mr.inputs['Value'])
            nt.links.new(mr.outputs['Result'], mix.inputs['Scale'])
            nt.links.new(mix.outputs[0], p.inputs['Base Color'])
            return m
        self.coat_mat = fabric('Coat', (0.018, 0.02, 0.03), (0.55, 0.7, 1.0))
        self.cape_mat = fabric('Cape', (0.028, 0.028, 0.038), (0.7, 0.75, 1.0), bump_s=0.4)
        self.pants_mat = fabric('Pants', (0.012, 0.012, 0.016), (0.5, 0.5, 0.6))
        self.scarf_mat = fabric('Scarf', (0.3, 0.012, 0.03), (1.0, 0.45, 0.5), rough=0.7)
        self.leather_mat, _, _ = mat_principled('Leather', (0.022, 0.017, 0.015), rough=0.33, coat=0.6)
        self.metal_mat, _, _ = mat_principled('Metal', (0.75, 0.75, 0.8), rough=0.22, metal=1.0)
        self.glow_mat = mat_emit('Piping', (0.15, 0.85, 1.0), 5.0)
        m, nt, p = mat_principled('Hair', (0.92, 0.92, 0.97), rough=0.28, sheen=0.4, coat=0.5)
        hi = nt.nodes.new('ShaderNodeHairInfo')
        rp = nt.nodes.new('ShaderNodeValToRGB')
        rp.color_ramp.elements[0].color = (0.55, 0.56, 0.66, 1)
        rp.color_ramp.elements[1].position = 0.3
        rp.color_ramp.elements[1].color = (0.97, 0.97, 1.0, 1)
        nt.links.new(hi.outputs['Intercept'], rp.inputs['Fac'])
        nt.links.new(rp.outputs['Color'], p.inputs['Base Color'])
        self.hair_mat = m
        self.cap_mat, _, _ = mat_principled('HairCap', (0.7, 0.71, 0.8), rough=0.5, sheen=0.5)

    def _body_materials(self):
        me = self.h.body.data
        for m in (self.leather_mat, self.pants_mat, self.leather_mat):
            me.materials.append(m)
        names = {g.index: g.name for g in self.h.body.vertex_groups}
        vdom = {}
        for v in me.vertices:
            vdom[v.index] = names[max(v.groups, key=lambda g: g.weight).group] if v.groups else ''
        for p in me.polygons:
            ds = [vdom[i] for i in p.vertices]
            if any(d.startswith(HANDS) for d in ds):
                p.material_index = 1
            elif any(d.startswith(('foot', 'toe', 'lowerleg02')) for d in ds):
                p.material_index = 3
            elif all(d.startswith(('upperleg', 'lowerleg', 'pelvis', 'spine0', 'root', 'breast',
                                   'clavicle', 'upperarm', 'lowerarm', 'shoulder')) for d in ds):
                p.material_index = 2

    # ---- piezas de ropa
    def _strip(self, name, rows, seg, a0, a1, xyz, closed=False, split_fn=None, mat=None,
               thick=0.012, weight_fn=None):
        bm = bmesh.new()
        rings = []
        n = seg if closed else seg + 1
        for z in rows:
            ring = [bm.verts.new(xyz(z, a0 + (a1 - a0) * i / seg, i)) for i in range(n)]
            if closed:
                ring.append(bm.verts.new(xyz(z, a1, seg)) if split_fn and split_fn(z) else ring[0])
            rings.append(ring)
        for r0, r1 in zip(rings[:-1], rings[1:]):
            for i in range(seg):
                bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
        o = mesh_obj(name, bm)
        for p in o.data.polygons:
            p.use_smooth = True
        o.parent = self.root
        o.data.materials.append(mat or self.coat_mat)
        if weight_fn:
            vg = o.vertex_groups.new(name='w')
            for v in o.data.vertices:
                vg.add([v.index], weight_fn(v.co), 'REPLACE')
        if thick:
            o.modifiers.new('sol', 'SOLIDIFY').thickness = thick
        return o, rings

    def _wind_mods(self, o, big, small, scale_big=0.35, scale_small=0.1, sub=True):
        t1 = bpy.data.textures.new(o.name + 'W1', 'CLOUDS'); t1.noise_scale = scale_big
        t1.cloud_type = 'COLOR'
        d = o.modifiers.new('wind', 'DISPLACE'); d.texture = t1; d.direction = 'RGB_TO_XYZ'
        d.texture_coords = 'OBJECT'; d.texture_coords_object = self.wind
        d.strength = big; d.vertex_group = 'w'
        t2 = bpy.data.textures.new(o.name + 'W2', 'CLOUDS'); t2.noise_scale = scale_small
        d2 = o.modifiers.new('flutter', 'DISPLACE'); d2.texture = t2
        d2.texture_coords = 'OBJECT'; d2.texture_coords_object = self.wind
        d2.strength = small; d2.vertex_group = 'w'
        if sub:
            s = o.modifiers.new('sub', 'SUBSURF'); s.levels = 1; s.render_levels = 2
        return t1, t2

    def hem_w(self, z):
        return smooth((self.z_waist - 0.05 - z) / 0.7) ** 1.2

    def _coat(self):
        seg = 64
        top = self.z_neck + 0.015
        rows = list(np.linspace(self.z_hem, top, 52))
        front = math.pi / 2
        st = self.slit_top
        fo = self.z_waist - 0.06        # abertura delantera (abrigo abierto abajo)
        bm = bmesh.new()
        rings = []
        half = seg // 2
        for z in rows:
            ef = 0.16 * max(0.0, (fo - z) / (fo - self.z_hem)) ** 0.7 + (0.02 if z < fo else 0)
            eb = 0.07 * max(0.0, (st - z) / (st - self.z_hem)) ** 0.8
            ring = []
            for i in range(seg + 1):
                a = front + 2 * math.pi * i / seg
                if z < fo and i == 0:
                    a += ef
                elif z < fo and i == seg:
                    a -= ef
                elif i == seg:
                    ring.append(ring[0]); continue
                if i == half and z < st:
                    ring.append(bm.verts.new(self.cxyz(z, a - eb)))
                    ring.append(bm.verts.new(self.cxyz(z, a + eb)))
                    continue
                if i == half:
                    v = bm.verts.new(self.cxyz(z, a)); ring.append(v); ring.append(v); continue
                ring.append(bm.verts.new(self.cxyz(z, a)))
            rings.append(ring)
        # ring tiene seg+2 entradas (indice half duplicado)
        for r0, r1 in zip(rings[:-1], rings[1:]):
            for i in range(seg + 1):
                if i == half:
                    continue      # salto entre las dos copias de la costura trasera
                a0_, a1_ = r0[i], r0[i + 1]; b0_, b1_ = r1[i], r1[i + 1]
                if len({a0_, a1_, b1_, b0_}) < 3:
                    continue
                try:
                    bm.faces.new((a0_, a1_, b1_, b0_))
                except ValueError:
                    pass
        o = mesh_obj('Coat', bm)
        for p in o.data.polygons:
            p.use_smooth = True
        o.parent = self.root
        o.data.materials.append(self.coat_mat)
        vg = o.vertex_groups.new(name='w')
        for v in o.data.vertices:
            vg.add([v.index], self.hem_w(v.co.z), 'REPLACE')
        o.modifiers.new('sol', 'SOLIDIFY').thickness = 0.012
        self.coat_tex = self._wind_mods(o, 0.12, 0.03)
        self.coat = o
        back = -math.pi / 2
        hem = [self.cxyz(self.z_hem + 0.005, back + 0.07 + (math.pi - 0.07 - 0.17) * i / 45, inflate=0.006)
               for i in range(46)]
        self._piping('HemPipeL', hem, 0.004, wind=True)
        hem = [self.cxyz(self.z_hem + 0.005, back - 0.07 - (math.pi - 0.07 - 0.17) * i / 45, inflate=0.006)
               for i in range(46)]
        self._piping('HemPipeR', hem, 0.004, wind=True)
        seam = [self.cxyz(z, back, inflate=0.004, folds=False)
                for z in np.linspace(self.z_cape_bot - 0.02, st + 0.01, 20)]
        self._piping('BackSeam', seam, 0.0025)

    def cape_off(self, z):
        return 0.022 + (self.z_cape_top - z) * 0.14

    def _capelet(self):
        span = 1.75
        back = -math.pi / 2
        rows = list(np.linspace(self.z_cape_top, self.z_cape_bot, 16))

        def xyz(z, a, i):
            x, y, _ = self.cxyz(z, a, inflate=self.cape_off(z), folds=False)
            dz = 0.012 * math.sin(9 * a) * (self.z_cape_top - z) * 3
            return (x, y, z + dz)
        o, rings = self._strip('Capelet', rows, 44, back - span, back + span, xyz,
                               mat=self.cape_mat, thick=0.01,
                               weight_fn=lambda co: smooth((self.z_cape_top - 0.05 - co.z) / 0.25) * 0.6)
        self._wind_mods(o, 0.035, 0.012)
        bottom = [xyz(self.z_cape_bot, back - span + 2 * span * i / 70, 0) for i in range(71)]
        bottom = [(x * 1.02, y * 1.02 - 0.001, z - 0.004) for x, y, z in bottom]
        self._piping('CapePipe', bottom, 0.0035)

    def _collar(self):
        gap = 0.42
        back = -math.pi / 2
        zb = self.z_neck - 0.01
        CH = 0.045
        rows = list(np.linspace(zb, zb + CH, 5))
        nx = self.co[[i for i, d in enumerate(self.dom) if d.startswith('neck')], :]
        cx, cy = nx[:, 0].mean(), nx[:, 1].mean()
        r0 = max(np.abs(nx[:, 0] - cx).max(), np.abs(nx[:, 1] - cy).max()) + 0.004

        def xyz(z, a, i):
            r = r0 + (z - zb) * 0.12
            return (cx + r * math.cos(a), cy + 0.95 * r * math.sin(a), z)
        self._strip('Collar', rows, 40, back - (math.pi - gap), back + (math.pi - gap), xyz,
                    mat=self.cape_mat, thick=0.012)
        top = [xyz(zb + CH, back - (math.pi - gap) + 2 * (math.pi - gap) * i / 50, 0) for i in range(51)]
        pass  # sin ribete superior: se leia como un aro

    def _belt(self):
        back = -math.pi / 2
        zw = self.z_waist - 0.04

        def xyz(z, a, i):
            return self.cxyz(z, a, inflate=0.012, folds=False)
        self._strip('Belt', [zw - 0.03, zw, zw + 0.03], 64, back, back + 2 * math.pi, xyz,
                    closed=True, mat=self.leather_mat, thick=0.008)
        x, y, z = self.cxyz(zw, back, inflate=0.024, folds=False)
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        b = mesh_obj('Buckle', bm); b.parent = self.root
        b.location = (x, y, z); b.scale = (0.07, 0.012, 0.05)
        b.data.materials.append(self.metal_mat)
        bv = b.modifiers.new('bev', 'BEVEL'); bv.width = 0.25; bv.segments = 3
        g = link(bpy.data.objects.new('BuckleGlow', ico('BG', 0.008, 2)))
        g.parent = self.root; g.location = (x, y - 0.008, z); g.data.materials.append(self.glow_mat)

    def _piping(self, name, pts, r, wind=False):
        cd = bpy.data.curves.new(name, 'CURVE'); cd.dimensions = '3D'
        cd.bevel_depth = r; cd.bevel_resolution = 2
        sp = cd.splines.new('POLY'); sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (*p, 1)
        o = link(bpy.data.objects.new(name, cd)); o.parent = self.root
        o.data.materials.append(self.glow_mat)
        if not wind:
            return o
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        m = link(bpy.data.objects.new(name + 'M', me)); m.parent = self.root
        m.data.materials.clear(); m.data.materials.append(self.glow_mat)
        vg = m.vertex_groups.new(name='w')
        for v in me.vertices:
            vg.add([v.index], self.hem_w(v.co.z), 'REPLACE')
        t1, t2 = self.coat_tex
        d = m.modifiers.new('wind', 'DISPLACE'); d.texture = t1; d.direction = 'RGB_TO_XYZ'
        d.texture_coords = 'OBJECT'; d.texture_coords_object = self.wind
        d.strength = 0.12; d.vertex_group = 'w'
        d2 = m.modifiers.new('flutter', 'DISPLACE'); d2.texture = t2
        d2.texture_coords = 'OBJECT'; d2.texture_coords_object = self.wind
        d2.strength = 0.03; d2.vertex_group = 'w'
        bpy.data.objects.remove(o)
        return m

    def _sub_body(self, name, keep_fn, push, mat):
        """Copia de la malla del cuerpo (con pesos y esqueleto) restringida a una region
        y empujada a lo largo de las normales: mangas, casquete del pelo..."""
        me = self.h.body.data.copy(); me.name = name
        ob = bpy.data.objects.new(name, me); link(ob)
        for vg in self.h.body.vertex_groups:
            ob.vertex_groups.new(name=vg.name)
        names = {g.index: g.name for g in self.h.body.vertex_groups}
        bm = bmesh.new(); bm.from_mesh(me)
        dl = bm.verts.layers.deform.active
        def dom(v):
            d = v[dl]
            return names[max(d.items(), key=lambda kv: kv[1])[0]] if d else ''
        kill = [f for f in bm.faces if not keep_fn([dom(v) for v in f.verts], f)]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * push
        bm.to_mesh(me); bm.free()
        me.materials.clear(); me.materials.append(mat)
        ob.parent = self.arm
        ob.modifiers.new('rig', 'ARMATURE').object = self.arm
        return ob

    def _boots(self):
        b = self._sub_body('Boots', lambda ds, f: all(d.startswith(('foot', 'toe', 'lowerleg')) for d in ds)
                           and f.calc_center_median().z < 0.42 / SCALE, 0.009, self.leather_mat)
        b.modifiers.new('sol', 'SOLIDIFY').thickness = 0.005
        s = b.modifiers.new('sub', 'SUBSURF'); s.levels = 1; s.render_levels = 1

    def _sleeves(self):
        s = self._sub_body('Sleeves', lambda ds, f: all(d.startswith(ARMS + ('clavicle', 'spine05', 'breast'))
                                                      or d.startswith('lowerarm02') for d in ds)
                           and any(d.startswith(('upperarm', 'lowerarm')) for d in ds),
                           0.022, self.coat_mat)
        s.modifiers.new('sol', 'SOLIDIFY').thickness = 0.006
        sb = s.modifiers.new('sub', 'SUBSURF'); sb.levels = 1; sb.render_levels = 2
        # ribete luminoso en el puño
        for side in 'LR':
            bm = bmesh.new()
            bmesh.ops.create_circle(bm, cap_ends=False, segments=24, radius=0.047)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
            ring = mesh_obj('CuffRing' + side, bm)
            sk = ring.modifiers.new('skin', 'WIREFRAME'); sk.thickness = 0.004
            ring.data.materials.append(self.glow_mat)
            ring.parent = self.arm; ring.parent_type = 'BONE'; ring.parent_bone = 'lowerarm02.' + side
            ring.matrix_parent_inverse = Matrix.Identity(4)
            ring.location = (0, -0.03, 0)

    def _face(self):
        mh = mhload.MH
        eye_m, nt, p = mat_principled('Eyes', (1, 1, 1), rough=0.08, coat=1.0)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(os.path.join(mh, 'eyes/materials/brown_eye.png'))
        nt.links.new(tex.outputs['Color'], p.inputs['Base Color'])
        self.h.fit_proxy(os.path.join(mh, 'eyes/high-poly/high-poly.mhclo'), 'Eyes', eye_m)
        br_m, nt, p = mat_principled('Brows', (0.85, 0.85, 0.9), rough=0.6)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(os.path.join(mh, 'eyebrows/eyebrow001/eyebrow001.png'))
        nt.links.new(tex.outputs['Alpha'], p.inputs['Alpha'])
        self.h.fit_proxy(os.path.join(mh, 'eyebrows/eyebrow001/eyebrow001.mhclo'), 'Brows', br_m)

    def _scalp_sel(self, ds, f):
        if not all(d == 'head' for d in ds):
            return False
        c = f.calc_center_median(); n = f.normal
        hc = self.head_c_local
        rel = c - hc
        if rel.z < -0.14 or (rel.z < -0.03 and rel.y > -0.02) or (rel.z < -0.09 and abs(rel.x) > 0.045):
            return False
        if rel.y > 0.03 and rel.z < 0.06:        # cara y frente
            return False
        if abs(rel.x) > 0.062 and rel.z < -0.01 and rel.y > -0.015:  # orejas
            return False
        return True

    def _hair(self, wind_strength, gust):
        """~12k hebras reales (Curves) que nacen del cuero cabelludo del modelo."""
        # coordenadas del cuerpo (sin escala del rig) para seleccionar el cuero cabelludo
        inv = (self.arm.matrix_world).inverted()
        self.head_c_local = inv @ self.head_c
        cap = self._sub_body('HairCap', self._scalp_sel, 0.0015, self.cap_mat)
        self.hair_cap = cap
        bpy.context.view_layer.update()
        mw = cap.matrix_world
        dg = bpy.context.evaluated_depsgraph_get()
        ev = cap.evaluated_get(dg); me = ev.to_mesh()
        roots, normals, areas = [], [], []
        for p in me.polygons:
            roots.append(tuple(mw @ p.center)); normals.append(tuple((mw.to_3x3() @ p.normal).normalized()))
            areas.append(p.area)
        ev.to_mesh_clear()
        roots = np.array(roots); normals = np.array(normals); areas = np.array(areas)
        rng = np.random.default_rng(3)
        P = 10
        t = np.linspace(0, 1, P)
        hc = np.array(self.head_c)
        n_guides = 560
        gidx = rng.choice(len(roots), n_guides, p=areas / areas.sum())
        all_pts, radii = [], []
        for gi in gidx:
            d = normals[gi]; root = roots[gi]
            rel = (root - hc) / np.linalg.norm(root - hc)
            # campo de peinado: arriba hacia atras/arriba, lados y nuca hacia abajo
            up = max(0.0, rel[2])
            flow = np.array([rel[0] * 0.25, -0.55 - 0.3 * up, 1.0 * up - 0.9 * (1 - up)])
            if rel[1] > 0.25:      # flequillo: hacia delante, abajo y a un lado
                flow = np.array([0.5 + rng.uniform(-.3, .3), 0.6, -0.7])
            flow += rng.normal(size=3) * 0.18
            tang = flow - d * flow.dot(d); tang /= np.linalg.norm(tang) + 1e-9
            g = tang * 0.85 + d * rng.uniform(0.18, 0.4) * (0.6 + up); g /= np.linalg.norm(g)
            L = rng.uniform(0.06, 0.11) * (0.7 + 0.45 * up)
            sweep = d * 0.15 * up + tang * 0.3 + np.array([0, 0, -0.35])
            sweep /= np.linalg.norm(sweep)
            twist = rng.normal(size=3) * 0.1
            guide = (root[None] + g[None] * L * t[:, None] + sweep[None] * L * 0.4 * (t ** 2)[:, None]
                     + twist[None] * L * 0.3 * (t ** 3)[:, None])
            nch = 26
            jit = rng.normal(size=(nch, 3)) * 0.008
            jit -= np.outer(jit @ d, d)
            lenf = rng.uniform(0.72, 1.06, nch)
            clump = rng.uniform(0.85, 0.97)
            for c in range(nch):
                tt = t * lenf[c]
                gi_ = np.array([np.interp(tt, t, guide[:, k]) for k in range(3)]).T
                off = jit[c][None] * (1 - clump * tt[:, None] ** 0.8)
                fr = rng.normal(size=(P, 3)) * 0.0012 * tt[:, None]
                all_pts.append(gi_ + off + fr)
                radii.append(np.linspace(0.0009, 0.00012, P) * rng.uniform(0.8, 1.2))
        pts = np.concatenate(all_pts)
        cv = bpy.data.hair_curves.new('Hair')
        cv.add_curves([P] * len(all_pts))
        cv.position_data.foreach_set('vector', pts.astype(np.float32).ravel())
        ra = cv.attributes.get('radius') or cv.attributes.new('radius', 'FLOAT', 'POINT')
        ra.data.foreach_set('value', np.concatenate(radii).astype(np.float32))
        cv.materials.append(self.hair_mat)
        o = link(bpy.data.objects.new('Hair', cv))
        o.modifiers.new('wind', 'NODES').node_group = hair_wind_group(wind_strength, gust, 0.6)
        self.hair_piv = empty('HairPiv', tuple(self.head_c))
        self.parent_bone(self.hair_piv, 'head')
        bpy.context.view_layer.update()
        o.parent = self.hair_piv
        o.matrix_parent_inverse = self.hair_piv.matrix_world.inverted()
        self.hair = o

    def _hood(self, up):
        bm = bmesh.new()
        R = 0.138
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=28, radius=R)
        kill = [v for v in bm.verts if (v.co.y > 0.0 and v.co.z < 0.06) or v.co.z < -0.17
                or (v.co.y > 0.11)]
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
        for v in bm.verts:
            if v.co.y < 0 and v.co.z > 0:
                v.co.y -= 0.075 * (v.co.z / R) ** 3
                v.co.z += 0.02 * (v.co.z / R) ** 3
            if v.co.z < -0.04:
                f = (-0.04 - v.co.z) / 0.13
                v.co.x *= 1 + 0.9 * f; v.co.y = v.co.y * (1 + 0.5 * f) - 0.02 * f
        o = mesh_obj('Hood', bm)
        o.location = tuple(self.head_c + Vector((0, -0.012, 0.012)))
        o.scale = (0.96, 1.08, 1.06)
        for p in o.data.polygons:
            p.use_smooth = True
        o.data.materials.append(self.cape_mat)
        o.modifiers.new('sol', 'SOLIDIFY').thickness = 0.012
        sub = o.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
        ht = bpy.data.textures.new('HoodFolds', 'CLOUDS'); ht.noise_scale = 0.14
        hd = o.modifiers.new('folds', 'DISPLACE'); hd.texture = ht; hd.strength = 0.018
        hd.texture_coords = 'OBJECT'; hd.texture_coords_object = self.wind
        self.parent_bone(o, 'head')
        self.hood = o
        self.hood_piv = o
        if up:
            self.hair_piv.scale = (0.6, 0.6, 0.6)
            self.hair.hide_render = True
            self.hair_cap.hide_render = True
        else:
            self.lower_hood_instant()

    def _scarf(self, lift):
        n, w = 44, 0.13
        x0, ry0, cy0 = self.prof.at(self.z_neck - 0.04)
        start = Vector((0.04, cy0 - ry0 - 0.06, self.z_neck - 0.02))
        bm = bmesh.new()
        rows = []
        for i in range(n + 1):
            s = i / n
            if lift:
                c = start + Vector((0.35 * s, -0.55 * s, 0.25 * s - 0.15 * s * s))
            else:
                c = start + Vector((0.12 * s + 0.1 * s * s, -0.08 * s - 0.25 * s * s, -1.0 * s))
                if c.z > self.z_hem:
                    x, ry, cy = self.prof.at(min(c.z, self.prof.z[-1]))
                    back_y = cy - ry - 0.03 - (self.cape_off(c.z) if self.z_cape_bot < c.z < self.z_cape_top else 0)
                    c.y = min(c.y, back_y - 0.03 - 0.035 * s)
            side = Vector((1, 0.15, 0)).normalized()
            ww = w * (1 - 0.25 * s)
            rows.append([bm.verts.new(c + side * ww * (j / 3 - 0.5)) for j in range(4)])
        for r0, r1 in zip(rows[:-1], rows[1:]):
            for j in range(3):
                bm.faces.new((r0[j], r0[j + 1], r1[j + 1], r1[j]))
        o = mesh_obj('Scarf', bm); o.parent = self.root
        for p in o.data.polygons:
            p.use_smooth = True
        o.data.materials.append(self.scarf_mat)
        vg = o.vertex_groups.new(name='w')
        for k, v in enumerate(o.data.vertices):
            s = (k // 4) / n
            vg.add([v.index], smooth(s * 1.4) * (0.7 + 0.3 * s), 'REPLACE')
        o.modifiers.new('sol', 'SOLIDIFY').thickness = 0.006
        wave = o.modifiers.new('wave', 'WAVE'); wave.use_x = True; wave.use_y = False
        wave.height = 0.035; wave.width = 0.5; wave.speed = 0.06; wave.narrowness = 1.2
        wave.vertex_group = 'w'
        self._wind_mods(o, 0.22, 0.05, scale_big=0.3, scale_small=0.08)
        self.scarf = o

    def dissolve_material(self):
        """Tela que se deshace con bordes de luz cian (umbral en el nodo 'Thr')."""
        m, nt, out = new_mat('HoodDissolve')
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        p.inputs['Base Color'].default_value = (0.02, 0.02, 0.025, 1)
        p.inputs['Roughness'].default_value = 0.88
        p.inputs['Sheen Weight'].default_value = 0.35
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (1, 1, 1)
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 14
        nz.inputs['Detail'].default_value = 4
        # gradiente vertical: se deshace de arriba abajo
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        grad = nt.nodes.new('ShaderNodeMapRange')
        grad.inputs['From Min'].default_value = 0.0; grad.inputs['From Max'].default_value = 0.22
        grad.inputs['To Min'].default_value = 0.0; grad.inputs['To Max'].default_value = 0.6
        mixv = nt.nodes.new('ShaderNodeMath'); mixv.operation = 'ADD'
        mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.5
        flip = nt.nodes.new('ShaderNodeMath'); flip.operation = 'SUBTRACT'; flip.inputs[0].default_value = 1.0
        thr = nt.nodes.new('ShaderNodeValue'); thr.name = 'Thr'; thr.outputs[0].default_value = -0.05
        alive = nt.nodes.new('ShaderNodeMath'); alive.operation = 'GREATER_THAN'
        edge_d = nt.nodes.new('ShaderNodeMath'); edge_d.operation = 'SUBTRACT'
        edge = nt.nodes.new('ShaderNodeMapRange')
        edge.inputs['From Min'].default_value = 0.035; edge.inputs['From Max'].default_value = 0.0
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (0.25, 0.85, 1.0, 1); em.inputs['Strength'].default_value = 40
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        m1 = nt.nodes.new('ShaderNodeMixShader'); m2 = nt.nodes.new('ShaderNodeMixShader')
        L = nt.links.new
        L(tc.outputs['Object'], nz.inputs['Vector'])
        L(tc.outputs['Object'], sep.inputs[0])
        L(sep.outputs['Z'], grad.inputs['Value'])
        L(nz.outputs['Fac'], mixv.inputs[0]); L(grad.outputs['Result'], mixv.inputs[1])
        L(mixv.outputs[0], mul.inputs[0]); L(mul.outputs[0], flip.inputs[1])
        # v = 1 - (noise + grad)/2 : arriba se deshace antes
        L(flip.outputs[0], alive.inputs[0]); L(thr.outputs[0], alive.inputs[1])
        L(flip.outputs[0], edge_d.inputs[0]); L(thr.outputs[0], edge_d.inputs[1])
        L(edge_d.outputs[0], edge.inputs['Value'])
        L(edge.outputs['Result'], m1.inputs['Fac'])
        L(p.outputs[0], m1.inputs[1]); L(em.outputs[0], m1.inputs[2])
        L(alive.outputs[0], m2.inputs['Fac'])
        L(tr.outputs[0], m2.inputs[1]); L(m1.outputs[0], m2.inputs[2])
        L(m2.outputs[0], out.inputs['Surface'])
        return m

    def lower_hood_instant(self):
        self.hood.hide_render = True
        self.hair_piv.scale = (1, 1, 1)

    def animate_wind(self, frames, speed=0.03, gust=(1, 0.2, 0.3)):
        self.wind.location = (0, 0, 0)
        self.wind.keyframe_insert('location', frame=1)
        self.wind.location = (gust[0] * speed * frames, gust[1] * speed * frames,
                              gust[2] * speed * frames)
        self.wind.keyframe_insert('location', frame=frames)
        set_linear(self.wind)


def rim_lights(target, cyan=900, magenta=700, fill=45, z=2.3):
    area_light('RimC', (-1.6, 2.6, z), target, (0.25, 0.85, 1.0), cyan, 1.5)
    area_light('RimM', (1.7, 2.4, z - 0.2), target, (1.0, 0.3, 0.75), magenta, 1.5)
    area_light('Fill', (-2.0, -3.0, 2.2), target, (1.0, 0.75, 0.55), fill, 3)
    area_light('Top', (0.3, 0.6, 4.5), target, (0.6, 0.7, 1.0), 110, 2)


def dust(n, box, mat, rmin=0.004, rmax=0.012, seed=3, parent=None):
    random.seed(seed)
    me = ico('Dust', 1.0, 1)
    objs = []
    for i in range(n):
        o = link(bpy.data.objects.new('Dust', me))
        o.location = (random.uniform(*box[0]), random.uniform(*box[1]), random.uniform(*box[2]))
        r = random.uniform(rmin, rmax); o.scale = (r, r, r)
        o.data.materials.append(mat) if not o.data.materials else None
        o.parent = parent
        objs.append(o)
    return objs


# ----------------------------------------------------------------- ciudad
def city(seed=11):
    random.seed(seed)
    # suelo mojado
    m, nt, p = mat_principled('Asphalt', (0.012, 0.013, 0.018), rough=0.12, coat=0.4)
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 3.0
    ramp = nt.nodes.new('ShaderNodeMapRange')
    ramp.inputs['To Min'].default_value = 0.05; ramp.inputs['To Max'].default_value = 0.45
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Value'])
    nt.links.new(ramp.outputs['Result'], p.inputs['Roughness'])
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200)
    g = mesh_obj('Ground', bm); g.data.materials.append(m)

    # edificios con ventanas
    bm_mat, bnt, bp = mat_principled('Building', (0.01, 0.011, 0.016), rough=0.6)
    brick = bnt.nodes.new('ShaderNodeTexBrick')
    brick.inputs['Scale'].default_value = 1.0
    brick.inputs['Mortar Size'].default_value = 0.42
    brick.inputs['Color1'].default_value = (1.0, 0.75, 0.45, 1)
    brick.inputs['Color2'].default_value = (0.4, 0.75, 1.0, 1)
    brick.inputs['Mortar'].default_value = (0, 0, 0, 1)
    brick.inputs['Brick Width'].default_value = 1.2
    brick.inputs['Row Height'].default_value = 1.1
    tc = bnt.nodes.new('ShaderNodeTexCoord')
    sep = bnt.nodes.new('ShaderNodeTexNoise'); sep.inputs['Scale'].default_value = 0.9
    thr = bnt.nodes.new('ShaderNodeMath'); thr.operation = 'GREATER_THAN'
    thr.inputs[1].default_value = 0.6
    mult = bnt.nodes.new('ShaderNodeVectorMath'); mult.operation = 'SCALE'
    bnt.links.new(tc.outputs['Object'], brick.inputs['Vector'])
    bnt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    bnt.links.new(sep.outputs['Fac'], thr.inputs[0])
    bnt.links.new(brick.outputs['Color'], mult.inputs[0])
    bnt.links.new(thr.outputs[0], mult.inputs['Scale'])
    bnt.links.new(mult.outputs[0], bp.inputs['Emission Color'])
    bp.inputs['Emission Strength'].default_value = 0.12
    cube = bpy.data.meshes.new('B'); bmc = bmesh.new()
    bmesh.ops.create_cube(bmc, size=1.0); bmesh.ops.translate(bmc, verts=bmc.verts, vec=(0, 0, 0.5))
    bmc.to_mesh(cube); bmc.free()
    for i in range(70):
        b = link(bpy.data.objects.new('Bld', cube))
        side = random.choice((-1, 1))
        b.location = (side * random.uniform(6, 60), random.uniform(25, 160), 0)
        b.scale = (random.uniform(5, 14), random.uniform(5, 14), random.uniform(12, 70))
        b.data.materials.append(bm_mat) if not b.data.materials else None

    # luces bokeh (farolas, coches, neones)
    lmat = mat_random_emit('Bokeh', PALETTE_CITY, 4, 30)
    sph = ico('BokehSph', 1.0, 2)
    for i in range(260):
        o = link(bpy.data.objects.new('L', sph))
        y = random.uniform(9, 90)
        x = random.gauss(0, 7 + y * 0.25)
        z = random.choice((random.uniform(0.3, 2.0), random.uniform(0.3, 2.0),
                           random.uniform(2, 16)))
        o.location = (x, y, z)
        r = random.uniform(0.05, 0.22) * (1 + y / 40)
        o.scale = (r, r, r)
        if not o.data.materials:
            o.data.materials.append(lmat)
    # farolas en fila
    lamp = mat_emit('Lamp', (1.0, 0.7, 0.35), 18)
    for side in (-1, 1):
        for k in range(14):
            o = link(bpy.data.objects.new('Lamp', sph))
            o.location = (side * 4.5, 8 + k * 7, 5.5); o.scale = (0.18, 0.18, 0.18)
            o.data.materials.append(lamp) if not o.data.materials else None
    world_color((0.006, 0.009, 0.02), 1.0)


# ===================================================================== PLANOS
def shot1():
    s = reset(); s.frame_end = SHOT_LEN[1]
    world_color((0.0, 0.0, 0.0), 0)
    random.seed(5)
    # fondo: gradiente radial azul
    m, nt, out = new_mat('BG')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    gr = nt.nodes.new('ShaderNodeTexGradient'); gr.gradient_type = 'SPHERICAL'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (0.05, 0.08, 0.05)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.002, 0.004, 0.02, 1)
    ramp.color_ramp.elements[1].color = (0.012, 0.03, 0.16, 1)
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 0.35
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nt.links.new(mp.outputs[0], gr.inputs['Vector'])
    nt.links.new(gr.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
    bg = mesh_obj('BG', bm); bg.rotation_euler = (math.radians(90), 0, 0)
    bg.location = (0, 0.6, 0); bg.data.materials.append(m)

    bright = mat_emit('Circuit', (0.1, 0.45, 1.0), 4.5)
    dim = mat_emit('CircuitDim', (0.06, 0.22, 0.9), 1.2)
    grid = 0.5
    starts = []
    for i in range(46):
        # empiezan en los bordes y avanzan en tramos ortogonales hacia el centro
        edge = random.choice(('L', 'R', 'T', 'B'))
        if edge in 'LR':
            x = -11 if edge == 'L' else 11; z = random.randint(-10, 10) * grid
        else:
            z = -6 if edge == 'B' else 6; x = random.randint(-20, 20) * grid
        pts = [(x, z)]
        for k in range(random.randint(4, 8)):
            px, pz = pts[-1]
            if k % 2 == 0:
                nx = px + (-px) * random.uniform(0.25, 0.6)
                pts.append((round(nx / grid) * grid, pz))
            else:
                nz = pz + (-pz) * random.uniform(0.25, 0.6)
                pts.append((px, round(nz / grid) * grid))
        # remate a 45 grados hacia el anillo del emblema
        px, pz = pts[-1]
        dist = math.hypot(px, pz) or 1
        if dist > 1.7:
            pts.append((px * 1.7 / dist, pz * 1.7 / dist))
        starts.append(pts)
    curves = []
    for i, pts in enumerate(starts):
        big = i % 3 != 0
        cd = bpy.data.curves.new('C', 'CURVE'); cd.dimensions = '3D'
        cd.bevel_depth = 0.022 if big else 0.01; cd.bevel_resolution = 1
        sp = cd.splines.new('POLY'); sp.points.add(len(pts) - 1)
        for j, (x, z) in enumerate(pts):
            sp.points[j].co = (x, 0, z, 1)
        o = link(bpy.data.objects.new('C', cd))
        o.data.materials.append(bright if big else dim)
        start = random.randint(1, 120); dur = random.randint(50, 100)
        cd.bevel_factor_end = 0.0; cd.keyframe_insert('bevel_factor_end', frame=start)
        cd.bevel_factor_end = 1.0; cd.keyframe_insert('bevel_factor_end', frame=start + dur)
        # nodo brillante al final de cada linea
        x, z = pts[-1]
        n = link(bpy.data.objects.new('Node', ico('Node', 0.05, 1)))
        n.location = (x, -0.02, z); n.data.materials.append(bright)
        n.scale = (0.001,) * 3; n.keyframe_insert('scale', frame=start + dur - 1)
        n.scale = (1,) * 3; n.keyframe_insert('scale', frame=start + dur + 4)
        curves.append(o)
    # rejilla tenue estatica
    gmat = mat_emit('Grid', (0.05, 0.12, 0.5), 0.12)
    for k in range(-22, 23, 2):
        for vert in (True, False):
            cd = bpy.data.curves.new('G', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = 0.004
            sp = cd.splines.new('POLY'); sp.points.add(1)
            if vert:
                sp.points[0].co = (k * grid, 0.3, -8, 1); sp.points[1].co = (k * grid, 0.3, 8, 1)
            else:
                if abs(k) > 14:
                    continue
                sp.points[0].co = (-14, 0.3, k * grid, 1); sp.points[1].co = (14, 0.3, k * grid, 1)
            o = link(bpy.data.objects.new('G', cd)); o.data.materials.append(gmat)

    # emblema que se enciende al final
    emat = mat_emit('Emblem', (0.3, 0.8, 1.0), 0.0)
    em_node = emat.node_tree.nodes['Emission']
    em_node.inputs['Strength'].default_value = 0.0
    em_node.inputs['Strength'].keyframe_insert('default_value', frame=150)
    em_node.inputs['Strength'].default_value = 16.0
    em_node.inputs['Strength'].keyframe_insert('default_value', frame=178)
    em_node.inputs['Strength'].default_value = 7.0
    em_node.inputs['Strength'].keyframe_insert('default_value', frame=210)
    epiv = empty('EmbPiv', (0, -0.05, 0)); epiv.rotation_euler = (math.radians(90), 0, 0)
    ecurves = emblem('Emb', 1.55, emat, 0.03, parent=epiv)
    for i, c in enumerate(ecurves):
        c.data.bevel_factor_end = 0.0; c.data.keyframe_insert('bevel_factor_end', frame=150 + i * 3)
        c.data.bevel_factor_end = 1.0; c.data.keyframe_insert('bevel_factor_end', frame=185 + i * 3)
    epiv.rotation_euler = (math.radians(90), math.radians(-25), 0)
    epiv.keyframe_insert('rotation_euler', frame=150)
    epiv.rotation_euler = (math.radians(90), 0, 0)
    epiv.keyframe_insert('rotation_euler', frame=200)

    dmat = mat_emit('Dust1', (0.5, 0.75, 1.0), 6)
    dp = empty('DustPar')
    dust(260, ((-9, 9), (-9, -1), (-5, 5)), dmat, 0.006, 0.02, parent=dp)
    dp.location = (0, 0, -0.5); dp.keyframe_insert('location', frame=1)
    dp.location = (0.6, 0, 0.8); dp.keyframe_insert('location', frame=SHOT_LEN[1])
    set_linear(dp)

    tgt = empty('Tgt', (0, 0, 0))
    cam = camera('Cam', (1.5, -13, -1.2), tgt, lens=40, fstop=1.8)
    cam.keyframe_insert('location', frame=1)
    cam.location = (0.0, -9.0, 0.0); cam.keyframe_insert('location', frame=SHOT_LEN[1])
    compositor(bloom=0.7, threshold=1.0, size=0.88)


def shot2():
    s = reset(); s.frame_end = SHOT_LEN[2]
    city()
    fig = Figure(loc=(0, 0, 0), hood_up=True)
    fig.animate_wind(SHOT_LEN[2])
    tgt = empty('Tgt', (0, 0, 1.45))
    rim_lights(tgt)
    dmat = mat_emit('Dust2', (1.0, 0.85, 0.7), 5)
    dp = empty('DustPar')
    dust(300, ((-4, 4), (-8, 3), (0, 4)), dmat, 0.004, 0.012, parent=dp)
    dp.keyframe_insert('location', frame=1)
    dp.location = (0.8, 0.3, -0.4); dp.keyframe_insert('location', frame=SHOT_LEN[2]); set_linear(dp)
    cam = camera('Cam', (0.9, -10.5, 1.25), tgt, lens=55, fstop=1.4)
    cam.keyframe_insert('location', frame=1)
    cam.location = (0.35, -3.4, 1.55); cam.keyframe_insert('location', frame=SHOT_LEN[2])
    compositor(bloom=0.55, threshold=1.2, size=0.85)


def shot3():
    s = reset(); s.frame_end = SHOT_LEN[3]
    city()
    fig = Figure(loc=(0, 0, 0), hood_up=True)
    fig.animate_wind(SHOT_LEN[3], speed=0.045)
    # la capucha se desintegra en luz y revela el pelo
    hm = fig.dissolve_material()
    fig.hood.data.materials[0] = hm
    thr = hm.node_tree.nodes['Thr'].outputs[0]
    thr.default_value = -0.05; thr.keyframe_insert('default_value', frame=60)
    thr.default_value = 1.05; thr.keyframe_insert('default_value', frame=112)
    for ob in (fig.hair, fig.hair_cap):
        ob.hide_render = True; ob.keyframe_insert('hide_render', frame=69)
        ob.hide_render = False; ob.keyframe_insert('hide_render', frame=70)
    fig.hair_piv.scale = (0.6, 0.6, 0.6); fig.hair_piv.keyframe_insert('scale', frame=70)
    fig.hair_piv.scale = (1.02, 1.02, 1.05); fig.hair_piv.keyframe_insert('scale', frame=112)
    fig.hair_piv.scale = (1, 1, 1); fig.hair_piv.keyframe_insert('scale', frame=126)
    tgt = empty('Tgt', (0, 0.02, 1.66))
    rim_lights(tgt, cyan=1100, magenta=900)
    # particulas que empiezan a flotar
    pmat = mat_emit('Spark', (0.6, 0.85, 1.0), 12)
    pp = empty('SparkPar', (0, 0, -1.2))
    dust(220, ((-1.2, 1.2), (-1.0, 1.2), (0.6, 2.4)), pmat, 0.002, 0.007, seed=9, parent=pp)
    pp.keyframe_insert('location', frame=120)
    pp.location = (0, 0, 0.9); pp.keyframe_insert('location', frame=SHOT_LEN[3]); set_linear(pp)
    cam = camera('Cam', (0.9, -1.75, 1.8), tgt, lens=50, fstop=1.6)
    cam.keyframe_insert('location', frame=1)
    cam.location = (0.62, -1.2, 1.75); cam.keyframe_insert('location', frame=SHOT_LEN[3])
    compositor(bloom=0.5, threshold=1.2, size=0.85)


def nebula_world():
    w = bpy.data.worlds.new('Neb'); bpy.context.scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.noise_dimensions = '4D'
    noise.inputs['Scale'].default_value = 1.6; noise.inputs['Detail'].default_value = 8
    noise.inputs['Roughness'].default_value = 0.62
    noise.inputs['W'].default_value = 0.0
    noise.inputs['W'].keyframe_insert('default_value', frame=1)
    noise.inputs['W'].default_value = 0.6
    noise.inputs['W'].keyframe_insert('default_value', frame=SHOT_LEN[4])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].position = 0.38; el[0].color = (0.0, 0.0, 0.004, 1)
    el[1].position = 0.75; el[1].color = (0.9, 0.12, 0.45, 1)
    e2 = el.new(0.55); e2.color = (0.12, 0.04, 0.35, 1)
    e3 = el.new(0.66); e3.color = (0.55, 0.06, 0.12, 1)
    # estrellas
    vor = nt.nodes.new('ShaderNodeTexVoronoi'); vor.inputs['Scale'].default_value = 220
    vor.feature = 'F1'
    st = nt.nodes.new('ShaderNodeMapRange')
    st.inputs['From Min'].default_value = 0.06; st.inputs['From Max'].default_value = 0.0
    st.inputs['To Max'].default_value = 3.0
    add = nt.nodes.new('ShaderNodeMix'); add.data_type = 'RGBA'; add.blend_type = 'ADD'
    add.inputs['Factor'].default_value = 1.0
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.55
    nt.links.new(tc.outputs['Generated'], noise.inputs['Vector'])
    nt.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(vor.outputs['Distance'], st.inputs['Value'])
    nt.links.new(ramp.outputs['Color'], add.inputs['A'])
    nt.links.new(st.outputs['Result'], add.inputs['B'])
    nt.links.new(add.outputs['Result'], bg.inputs['Color'])
    nt.links.new(bg.outputs[0], out.inputs['Surface'])


def shot4():
    s = reset(); s.frame_end = SHOT_LEN[4]
    nebula_world()
    fig = Figure(loc=(0, 0, 0), hood_up=False, right_arm_up=True)
    fig.animate_wind(SHOT_LEN[4], speed=0.08, gust=(0.3, 0.2, 1.0))
    tgt = empty('Tgt', (0, 0, 1.6))
    fig = fig
    # el brazo derecho se alza durante los primeros 3 s
    fig.arm_rest(frame=1); fig.arm_up(frame=72)
    fig.head((0, 0, 0), frame=1); fig.head((-14, 0, 6), frame=80)
    # orbe en la mano (sigue al hueso de la muneca)
    orb_mat = mat_emit('Orb', (1.0, 0.25, 0.55), 30)
    orb = link(bpy.data.objects.new('Orb', ico('Orb', 0.07, 3)))
    orb.data.materials.append(orb_mat)
    orb.parent = fig.arm; orb.parent_type = 'BONE'; orb.parent_bone = 'wrist.R'
    orb.matrix_parent_inverse = Matrix.Identity(4); orb.location = (0, 0.09, 0)
    orb.scale = (0.15,) * 3; orb.keyframe_insert('scale', frame=40)
    orb.scale = (1,) * 3; orb.keyframe_insert('scale', frame=110)
    orb.scale = (1.5,) * 3; orb.keyframe_insert('scale', frame=SHOT_LEN[4])
    pl = point_light('OrbLight', (0, 0, 0), (1.0, 0.3, 0.55), 80, 0.1)
    pl.parent = fig.arm; pl.parent_type = 'BONE'; pl.parent_bone = 'wrist.R'
    pl.matrix_parent_inverse = Matrix.Identity(4); pl.location = (0, 0.12, 0)
    pl.data.energy = 10; pl.data.keyframe_insert('energy', frame=40)
    pl.data.energy = 600; pl.data.keyframe_insert('energy', frame=SHOT_LEN[4])
    area_light('RimV', (-1.8, 2.2, 2.8), tgt, (0.55, 0.3, 1.0), 900, 2)
    area_light('RimR', (1.8, 1.8, 0.6), tgt, (1.0, 0.15, 0.2), 700, 2)
    area_light('FillB', (0.0, -3.5, 1.0), tgt, (0.3, 0.4, 1.0), 25, 4)

    # espirales de energia
    random.seed(21)
    rmat = mat_random_emit('Energy', [(1.0, 0.2, 0.45), (0.65, 0.2, 1.0), (1.0, 0.35, 0.2),
                                      (0.9, 0.5, 1.0)], 3, 12)
    for k in range(9):
        piv = empty('Spin', (0, 0, 0))
        cd = bpy.data.curves.new('Rib', 'CURVE'); cd.dimensions = '3D'
        cd.bevel_depth = random.uniform(0.004, 0.012); cd.bevel_resolution = 1
        sp = cd.splines.new('NURBS'); n = 60; sp.points.add(n - 1)
        r0 = random.uniform(0.6, 1.6); ph = random.uniform(0, 6.28)
        turns = random.uniform(0.6, 1.4); z0 = random.uniform(0.0, 0.8)
        hz = random.uniform(1.6, 2.6)
        for i in range(n):
            t = i / (n - 1); a = ph + t * turns * 2 * math.pi
            r = r0 * (1 - 0.35 * t)
            sp.points[i].co = (r * math.cos(a), r * math.sin(a), z0 + t * hz, 1)
        sp.order_u = 4; sp.use_endpoint_u = True
        o = link(bpy.data.objects.new('Rib', cd)); o.parent = piv
        o.data.materials.append(rmat)
        cd.bevel_factor_start = 0; cd.bevel_factor_end = 0
        st = random.randint(20, 120)
        cd.keyframe_insert('bevel_factor_end', frame=st)
        cd.bevel_factor_end = 1; cd.keyframe_insert('bevel_factor_end', frame=st + 60)
        cd.bevel_factor_start = 0; cd.keyframe_insert('bevel_factor_start', frame=st + 40)
        cd.bevel_factor_start = 0.6; cd.keyframe_insert('bevel_factor_start', frame=st + 140)
        piv.rotation_euler = (0, 0, 0); piv.keyframe_insert('rotation_euler', frame=1)
        piv.rotation_euler = (0, 0, random.choice((-1, 1)) * random.uniform(4, 8))
        piv.keyframe_insert('rotation_euler', frame=SHOT_LEN[4]); set_linear(piv)
    # particulas orbitando
    pme = ico('P', 1.0, 1)
    for k in range(3):
        piv = empty('Orbit', (0, 0, 0))
        for i in range(170):
            o = link(bpy.data.objects.new('P', pme)); o.parent = piv
            a = random.uniform(0, 6.28); r = random.uniform(0.5, 2.4)
            o.location = (r * math.cos(a), r * math.sin(a), random.uniform(0, 3.2))
            sc = random.uniform(0.004, 0.016); o.scale = (sc,) * 3
            if not o.data.materials:
                o.data.materials.append(rmat)
        piv.keyframe_insert('rotation_euler', frame=1)
        piv.rotation_euler = (0, 0, (k + 1) * 1.2 * (1 if k % 2 else -1))
        piv.keyframe_insert('rotation_euler', frame=SHOT_LEN[4]); set_linear(piv)
    cam = camera('Cam', (-1.4, -3.4, 0.7), tgt, lens=32, fstop=2.8)
    cam.keyframe_insert('location', frame=1)
    cam.location = (1.2, -3.0, 0.9); cam.keyframe_insert('location', frame=SHOT_LEN[4])
    compositor(bloom=0.6, threshold=1.1, size=0.9)


def shot5():
    s = reset(); s.frame_end = SHOT_LEN[5]
    city()
    for o in [o for o in bpy.data.objects if o.name.startswith('Lamp') and o.location.y < 16]:
        bpy.data.objects.remove(o)
    fig = Figure(loc=(0, 0, 0), hood_up=False)
    fig.animate_wind(SHOT_LEN[5], speed=0.06)
    tgt = empty('Tgt', (0, 0, 1.2))
    rim_lights(tgt)
    for n in ('RimC', 'RimM', 'Fill', 'Top'):
        bpy.data.objects[n].visible_glossy = False
    # columna de luz
    bmat = mat_emit('Beam', (0.55, 0.35, 1.0), 0)
    bn = bmat.node_tree.nodes['Emission'].inputs['Strength']
    bn.default_value = 0; bn.keyframe_insert('default_value', frame=110)
    bn.default_value = 60; bn.keyframe_insert('default_value', frame=140)
    bn.default_value = 25; bn.keyframe_insert('default_value', frame=200)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=0.35, radius2=0.35, depth=300)
    beam = mesh_obj('Beam', bm); beam.location = (0, 0.3, 150); beam.data.materials.append(bmat)
    beam.scale = (0.05, 0.05, 1); beam.keyframe_insert('scale', frame=110)
    beam.scale = (1, 1, 1); beam.keyframe_insert('scale', frame=135)
    # titulo
    tmat = mat_emit('Title', (0.85, 0.9, 1.0), 0)
    tn = tmat.node_tree.nodes['Emission'].inputs['Strength']
    tn.default_value = 0; tn.keyframe_insert('default_value', frame=165)
    tn.default_value = 6; tn.keyframe_insert('default_value', frame=200)
    td = bpy.data.curves.new('Title', 'FONT'); td.body = 'O R I G E N'
    td.align_x = 'CENTER'; td.align_y = 'CENTER'; td.size = 1.0; td.extrude = 0.0
    title = link(bpy.data.objects.new('Title', td)); title.data.materials.append(tmat)
    title.rotation_euler = (math.radians(90), 0, 0)
    cam = camera('Cam', (0.3, -3.5, 1.5), tgt, lens=35, fstop=2.8)
    cam.keyframe_insert('location', frame=1)
    cam.location = (0.0, -22, 6.0); cam.keyframe_insert('location', frame=150)
    cam.location = (0.0, -24, 6.4); cam.keyframe_insert('location', frame=SHOT_LEN[5])
    bpy.context.view_layer.update()
    # el titulo flota delante de la camara al final
    title.parent = cam; title.location = (0, -0.35, -3.0); title.rotation_euler = (0, 0, 0)
    title.scale = (0.32,) * 3
    title.hide_render = True   # el titulo se compone nitido en post (finalize.sh)
    compositor(bloom=1.0, threshold=0.85, size=0.92)


SHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--shot', type=int, required=True)
    ap.add_argument('--still', type=int)
    ap.add_argument('--frames')
    ap.add_argument('--out')
    ap.add_argument('--outdir')
    ap.add_argument('--samples', type=int)
    ap.add_argument('--percent', type=int, default=100)
    ap.add_argument('--res')
    ap.add_argument('--save-blend')
    a = ap.parse_args(argv)
    SHOTS[a.shot]()
    s = bpy.context.scene
    s.render.resolution_percentage = a.percent
    if a.res:
        s.render.resolution_x, s.render.resolution_y = map(int, a.res.split('x'))
    if a.samples:
        s.eevee.taa_render_samples = a.samples
    if a.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save_blend))
    import time
    if a.still:
        s.frame_set(a.still)
        s.render.filepath = os.path.abspath(a.out)
        t = time.time(); bpy.ops.render.render(write_still=True)
        print(f'RENDERED still {a.out} in {time.time() - t:.1f}s', flush=True)
    elif a.frames:
        f0, f1 = map(int, a.frames.split('-'))
        os.makedirs(a.outdir, exist_ok=True)
        for f in range(f0, f1 + 1):
            p = os.path.join(os.path.abspath(a.outdir), f'{f:04d}.png')
            if os.path.exists(p):
                continue
            s.frame_set(f); s.render.filepath = p
            t = time.time(); bpy.ops.render.render(write_still=True)
            print(f'RENDERED frame {f} in {time.time() - t:.1f}s', flush=True)


if __name__ == '__main__':
    main()
