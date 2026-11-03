"""
Cargador propio de datos MakeHuman (CC0): malla base, morphs de edad/genero,
esqueleto 'default' y pesos.  Solo lee archivos de datos (obj/json/target),
no ejecuta codigo de terceros.

Coordenadas: MakeHuman es Y-arriba en decimetros. Se convierte a Blender
(Z-arriba, metros) y se gira 180 grados para que el personaje mire a +Y.
"""
import bpy, bmesh, gzip, json, math, os
import numpy as np
from mathutils import Vector

MH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets_dl', 'mh')

TARGETS = [('data/targets/macrodetails/universal-male-young-averagemuscle-averageweight.target.gz', 1.0),
           ('data/targets/macrodetails/asian-male-young.target.gz', 1.0)]


def _conv(v):
    # MH (x, y, z) dm  ->  Blender (-x, z, y) m   (giro 180 + Y-up -> Z-up)
    v = np.asarray(v, dtype=np.float64)
    return np.stack([-v[..., 0], v[..., 2], v[..., 1]], axis=-1) * 0.1


def load_obj(path):
    verts, uvs, faces, fuv, fgroup = [], [], [], [], []
    group = None
    groups = {}
    with open(path) as f:
        for line in f:
            if line.startswith('v '):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('vt '):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith('g '):
                group = line.split()[1]
            elif line.startswith('f '):
                vi, ti = [], []
                for tok in line.split()[1:]:
                    p = tok.split('/')
                    vi.append(int(p[0]) - 1)
                    ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                faces.append(vi); fuv.append(ti); fgroup.append(group)
                groups.setdefault(group, set()).update(vi)
    return np.array(verts), np.array(uvs) if uvs else None, faces, fuv, fgroup, groups


def apply_targets(verts):
    v = verts.copy()
    for rel, w in TARGETS:
        with gzip.open(os.path.join(MH, rel), 'rt') as f:
            for line in f:
                p = line.split()
                if len(p) == 4 and not line.startswith('#'):
                    v[int(p[0])] += w * np.array([float(p[1]), float(p[2]), float(p[3])])
    return v


class Human:
    def __init__(self, name='Human', skin='young_asian_male'):
        verts, uvs, faces, fuv, fgroup, groups = load_obj(os.path.join(MH, 'data/3dobjs/base.obj'))
        self.mh_verts = apply_targets(verts)                   # en espacio MH (para mhclo)
        bl = _conv(self.mh_verts)
        body_idx = groups['body']
        self.floor = bl[list(body_idx), 2].min()
        bl[:, 2] -= self.floor
        self.bl_verts = bl
        self.groups = groups
        # malla del cuerpo (se conservan todos los vertices para que los indices coincidan)
        me = bpy.data.meshes.new(name)
        body_faces = [f for f, g in zip(faces, fgroup) if g == 'body']
        body_fuv = [t for t, g in zip(fuv, fgroup) if g == 'body']
        me.from_pydata(bl.tolist(), [], body_faces)
        uvl = me.uv_layers.new(name='UVMap')
        k = 0
        for poly, tl in zip(me.polygons, body_fuv):
            for li, t in zip(poly.loop_indices, tl):
                uvl.data[li].uv = uvs[t]
        for p in me.polygons:
            p.use_smooth = True
        self.body = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(self.body)
        self.body.data.materials.append(self.skin_material(skin))
        self._rig()
        # eliminar vertices de ayuda sueltos (los grupos de pesos se conservan)
        bm = bmesh.new(); bm.from_mesh(me)
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.to_mesh(me); bm.free()
        sub = self.body.modifiers.new('sub', 'SUBSURF'); sub.levels = 0; sub.render_levels = 1

    # ------------------------------------------------------------- material
    def skin_material(self, skin):
        m = bpy.data.materials.new('Skin_' + skin)
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        tex = nt.nodes.new('ShaderNodeTexImage')
        d = os.path.join(MH, 'skins', skin)
        png = [f for f in os.listdir(d) if f.endswith('.png') and 'diffuse' in f][0]
        tex.image = bpy.data.images.load(os.path.join(d, png))
        nt.links.new(tex.outputs['Color'], p.inputs['Base Color'])
        p.inputs['Roughness'].default_value = 0.5
        p.inputs['Subsurface Weight'].default_value = 0.25
        p.inputs['Subsurface Radius'].default_value = (1.0, 0.45, 0.25)
        p.inputs['Subsurface Scale'].default_value = 0.01
        p.inputs['Specular IOR Level'].default_value = 0.45
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900
        bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08
        nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])
        nt.links.new(p.outputs[0], out.inputs['Surface'])
        return m

    # ----------------------------------------------------------------- rig
    def _pos(self, spec):
        s = spec['strategy']
        if s == 'CUBE':
            idx = list(self.groups[spec['cube_name']])
            return self.bl_verts[idx].mean(axis=0)
        if s == 'VERTEX':
            return self.bl_verts[spec['vertex_index']]
        if s == 'MEAN':
            return self.bl_verts[spec['vertex_indices']].mean(axis=0)
        raise ValueError(s)

    def _rig(self):
        rig = json.load(open(os.path.join(MH, 'data/rigs/standard/rig.default.json')))
        wts = json.load(open(os.path.join(MH, 'data/rigs/standard/weights.default.json')))['weights']
        ad = bpy.data.armatures.new('Rig')
        arm = bpy.data.objects.new('Rig', ad)
        bpy.context.scene.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        ebs = {}
        for name, b in rig.items():
            eb = ad.edit_bones.new(name)
            eb.head = Vector(self._pos(b['head']))
            eb.tail = Vector(self._pos(b['tail']))
            if (eb.tail - eb.head).length < 1e-4:
                eb.tail = eb.head + Vector((0, 0, 0.01))
            eb.roll = b.get('roll', 0.0) + math.pi   # compensar el giro de 180 grados
            ebs[name] = eb
        for name, b in rig.items():
            if b.get('parent'):
                ebs[name].parent = ebs[b['parent']]
                ebs[name].use_connect = b.get('use_connect', False)
        bpy.ops.object.mode_set(mode='OBJECT')
        self.arm = arm
        # pesos
        ob = self.body
        for bone, lst in wts.items():
            if bone not in rig:
                continue
            vg = ob.vertex_groups.new(name=bone)
            for vi, w in lst:
                vg.add([vi], w, 'REPLACE')
        ob.parent = arm
        mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = arm
        self.weights = wts

    # ------------------------------------------------------------- utilidades
    def pose(self, bone, rot_deg, frame=None, mode='XYZ'):
        pb = self.arm.pose.bones[bone]
        pb.rotation_mode = mode
        pb.rotation_euler = tuple(math.radians(a) for a in rot_deg)
        if frame is not None:
            pb.keyframe_insert('rotation_euler', frame=frame)

    def bone_head(self, bone):
        bpy.context.view_layer.update()
        pb = self.arm.pose.bones[bone]
        return self.arm.matrix_world @ pb.head

    def fit_proxy(self, mhclo_path, name, material=None, offset_scale=1.0):
        """Ajusta una prenda/pelo .mhclo al cuerpo y le transfiere los pesos."""
        d = os.path.dirname(mhclo_path)
        refs, scales, obj_file = [], {}, None
        in_verts = False
        for line in open(mhclo_path):
            p = line.split()
            if not p or line.startswith('#'):
                continue
            if p[0] == 'obj_file':
                obj_file = p[1]
            elif p[0] in ('x_scale', 'y_scale', 'z_scale'):
                scales[p[0][0]] = (int(p[1]), int(p[2]), float(p[3]))
            elif p[0] == 'verts':
                in_verts = True
            elif in_verts and len(p) >= 9 and p[0].lstrip('-').isdigit():
                refs.append(([int(p[0]), int(p[1]), int(p[2])],
                             [float(p[3]), float(p[4]), float(p[5])],
                             [float(p[6]), float(p[7]), float(p[8])]))
            elif in_verts and len(p) == 1 and p[0].isdigit():
                refs.append(([int(p[0])] * 3, [1, 0, 0], [0, 0, 0]))
            elif in_verts and not p[0].lstrip('-').isdigit():
                in_verts = False
        V = self.mh_verts
        sc = {}
        for ax, k in (('x', 0), ('y', 1), ('z', 2)):
            a, b, s = scales[ax]
            sc[k] = abs(V[a][k] - V[b][k]) / s
        pv, puv, pf, pfuv, _, _ = load_obj(os.path.join(d, obj_file))
        out = np.zeros((len(refs), 3))
        for i, (vi, w, o) in enumerate(refs):
            pos = w[0] * V[vi[0]] + w[1] * V[vi[1]] + w[2] * V[vi[2]]
            out[i] = pos + np.array([o[0] * sc[0], o[1] * sc[1], o[2] * sc[2]]) * offset_scale
        bl = _conv(out); bl[:, 2] -= self.floor
        me = bpy.data.meshes.new(name)
        me.from_pydata(bl.tolist(), [], pf)
        if puv is not None:
            uvl = me.uv_layers.new(name='UVMap')
            for poly, tl in zip(me.polygons, pfuv):
                for li, t in zip(poly.loop_indices, tl):
                    if t >= 0:
                        uvl.data[li].uv = puv[t]
        for p in me.polygons:
            p.use_smooth = True
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        if material:
            ob.data.materials.append(material)
        # pesos interpolados
        vw = {}
        for bone, lst in self.weights.items():
            for vi, w in lst:
                vw.setdefault(vi, {})[bone] = w
        groups = {}
        for i, (vi, w, o) in enumerate(refs):
            acc = {}
            for v, ww in zip(vi, w):
                for bone, bw in vw.get(v, {}).items():
                    acc[bone] = acc.get(bone, 0) + bw * ww
            for bone, val in acc.items():
                if val > 1e-4:
                    if bone not in groups:
                        groups[bone] = ob.vertex_groups.new(name=bone)
                    groups[bone].add([i], val, 'REPLACE')
        ob.parent = self.arm
        mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = self.arm
        return ob, d
