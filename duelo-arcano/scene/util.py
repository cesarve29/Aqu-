"""bpy helpers: node building, mesh creation, weights, keyframes."""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix, Euler


# ----------------------------------------------------------------------------
# Node builder
# ----------------------------------------------------------------------------
class NB:
    """Tiny node-graph builder. Works for shader / geometry / compositor trees."""

    def __init__(self, tree, clear=True):
        self.t = tree
        if clear:
            for n in list(tree.nodes):
                tree.nodes.remove(n)
        self.x = 0

    def n(self, typ, inputs=None, **props):
        node = self.t.nodes.new(typ)
        node.location = (self.x, 0)
        self.x += 220
        for k, v in props.items():
            setattr(node, k, v)
        if inputs:
            for k, v in inputs.items():
                sock = self._in(node, k)
                if isinstance(v, tuple) and len(v) == 2 and hasattr(v[0], 'outputs'):
                    self.link(v, sock)
                elif hasattr(v, 'is_output'):
                    self.link(v, sock)
                elif hasattr(v, 'outputs') and hasattr(v, 'bl_idname'):
                    self.link(v, sock)
                else:
                    sock.default_value = v
        return node

    @staticmethod
    def _in(node, key):
        if isinstance(key, int):
            return node.inputs[key]
        # prefer enabled sockets with this name
        for s in node.inputs:
            if s.name == key and s.enabled:
                return s
        return node.inputs[key]

    @staticmethod
    def _out(src):
        if isinstance(src, tuple):
            node, key = src
            if isinstance(key, int):
                return node.outputs[key]
            for s in node.outputs:
                if s.name == key and s.enabled:
                    return s
            return node.outputs[key]
        if hasattr(src, 'is_output'):
            return src
        # node: first enabled output
        for s in src.outputs:
            if s.enabled:
                return s
        return src.outputs[0]

    def link(self, src, dst):
        if isinstance(dst, tuple):
            dst = self._in(dst[0], dst[1])
        self.t.links.new(self._out(src), dst)

    # -- shader shortcuts --------------------------------------------------
    def math(self, op, a, b=None, c=None, clamp=False):
        node = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                node.inputs[i].default_value = v
            else:
                self.link(v, node.inputs[i])
        return node

    def mixc(self, fac, a, b, blend='MIX'):
        node = self.n('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        ins = [s for s in node.inputs if s.enabled]
        for sock, v in zip(ins, (fac, a, b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, (list, tuple)) and not hasattr(v[0], 'outputs'):
                sock.default_value = v if len(v) == 4 else (*v, 1.0)
            else:
                self.link(v, sock)
        return node

    def mixf(self, fac, a, b):
        node = self.n('ShaderNodeMix', data_type='FLOAT')
        ins = [s for s in node.inputs if s.enabled]
        for sock, v in zip(ins, (fac, a, b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return node

    def maprange(self, v, a0, a1, b0=0.0, b1=1.0, clamp=True, interp='LINEAR'):
        node = self.n('ShaderNodeMapRange', clamp=clamp, interpolation_type=interp)
        ins = [s for s in node.inputs if s.enabled]
        self.link(v, ins[0]) if not isinstance(v, (int, float)) else None
        for sock, val in zip(ins[1:5], (a0, a1, b0, b1)):
            if isinstance(val, (int, float)):
                sock.default_value = val
            else:
                self.link(val, sock)
        return node


def new_material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m


def mat_output(nb):
    return nb.n('ShaderNodeOutputMaterial', target='ALL')


def value_node(nb, val, label):
    v = nb.n('ShaderNodeValue')
    v.outputs[0].default_value = val
    v.label = label
    v.name = label
    return v


# ----------------------------------------------------------------------------
# Meshes
# ----------------------------------------------------------------------------
def mesh_object(name, verts, faces, edges=(), collection=None, uvs=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], list(edges), [tuple(f) for f in faces])
    me.validate()
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        # uvs: per-vertex (u,v) -> expand to loops
        loop_vi = np.zeros(len(me.loops), dtype=np.int32)
        me.loops.foreach_get('vertex_index', loop_vi)
        uv = np.asarray(uvs, dtype=np.float32)[loop_vi]
        uvl.data.foreach_set('uv', uv.ravel())
    if smooth and len(me.polygons):
        me.shade_smooth() if hasattr(me, 'shade_smooth') else None
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def grid_surface(rings, closed_u=True, cap_end=False):
    """rings: array (nv, nu, 3). Returns verts, faces, uvs (u around, v along)."""
    rings = np.asarray(rings)
    nv, nu, _ = rings.shape
    verts = rings.reshape(-1, 3)
    faces = []
    cols = nu if closed_u else nu - 1
    for j in range(nv - 1):
        for i in range(cols):
            a = j * nu + i
            b = j * nu + (i + 1) % nu
            c = (j + 1) * nu + (i + 1) % nu
            d = (j + 1) * nu + i
            faces.append((a, b, c, d))
    uvs = np.zeros((nv * nu, 2))
    for j in range(nv):
        for i in range(nu):
            uvs[j * nu + i] = (i / (nu if closed_u else nu - 1), j / (nv - 1))
    verts = list(verts)
    if cap_end:
        c = rings[-1].mean(axis=0)
        ci = len(verts)
        verts.append(c)
        uvs = np.vstack([uvs, [[0.5, 1.0]]])
        base = (nv - 1) * nu
        for i in range(nu if closed_u else nu - 1):
            faces.append((base + i, base + (i + 1) % nu, ci))
    return np.array(verts), faces, uvs


def add_mod(ob, typ, name=None, **props):
    m = ob.modifiers.new(name or typ.lower(), typ)
    for k, v in props.items():
        setattr(m, k, v)
    return m


def link_obj(ob, coll):
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)


def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


# ----------------------------------------------------------------------------
# Skinning weights (distance to bone segments)
# ----------------------------------------------------------------------------
def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    proj = a + t[:, None] * ab[None, :]
    return np.linalg.norm(p - proj, axis=1)


def auto_weights(ob, bones, power=4.0, top=2, override=None):
    """bones: dict name -> (head, tail) in object space of the mesh (rest)."""
    me = ob.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    names = list(bones.keys())
    D = np.stack([seg_dist(co, np.asarray(bones[n][0]), np.asarray(bones[n][1])) for n in names], axis=1)
    W = 1.0 / (D ** power + 1e-6)
    if override is not None:
        W = override(co, W, names)
    # keep top-k
    idx = np.argsort(-W, axis=1)
    mask = np.zeros_like(W, dtype=bool)
    rows = np.arange(len(W))[:, None]
    mask[rows, idx[:, :top]] = True
    W = np.where(mask, W, 0)
    W /= W.sum(axis=1, keepdims=True) + 1e-12
    for j, n in enumerate(names):
        vg = ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)
        nz = np.nonzero(W[:, j] > 1e-4)[0]
        for i in nz:
            vg.add([int(i)], float(W[i, j]), 'REPLACE')


def single_weight(ob, bone):
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')


# ----------------------------------------------------------------------------
# Keyframes
# ----------------------------------------------------------------------------
def key(obj, path, frame, value=None, index=-1, interp=None):
    if value is not None:
        if index >= 0:
            getattr(obj, path)[index] = value
        else:
            try:
                setattr(obj, path, value)
            except Exception:
                exec(f'obj.{path} = value')
    obj.keyframe_insert(data_path=path, frame=frame, index=index)
    if interp:
        set_interp(obj, interp)


def set_interp(idblock, interp='BEZIER', path_filter=None):
    ad = getattr(idblock, 'animation_data', None)
    if not ad or not ad.action:
        return
    for fc in iter_fcurves(ad.action):
        if path_filter and path_filter not in fc.data_path:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def iter_fcurves(action):
    """Blender 4.4+ slotted actions: walk layers/strips/channelbags."""
    if hasattr(action, 'layers') and len(action.layers):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        yield fc
    elif hasattr(action, 'fcurves'):
        for fc in action.fcurves:
            yield fc


def key_socket(sock, frame, value):
    sock.default_value = value
    sock.keyframe_insert('default_value', frame=frame)


def look_rot(direction, up=(0, 0, 1)):
    d = Vector(direction).normalized()
    return d.to_track_quat('-Z', 'Y').to_euler()
