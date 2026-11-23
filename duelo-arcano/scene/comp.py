"""Compositor: depth fog, bloom, anamorphic streaks, lens dispersion, vignette, grade."""
import bpy
from util import NB


def _menu(node, name, value):
    s = node.inputs[name]
    s.default_value = value


def _mix(nb, blend, fac, a, b):
    m = nb.n('ShaderNodeMix', data_type='RGBA', blend_type=blend)
    ins = [s for s in m.inputs if s.enabled]
    for sock, v in zip(ins, (fac, a, b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple) and not hasattr(v[0], 'outputs'):
            sock.default_value = v
        else:
            nb.link(v, sock)
    return m


def build_compositor():
    sc = bpy.context.scene
    g = bpy.data.node_groups.new('DuelComp', 'CompositorNodeTree')
    g.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    sc.compositing_node_group = g
    sc.render.use_compositing = True
    nb = NB(g)
    rl = nb.n('CompositorNodeRLayers')
    rl.scene = sc
    # depth fog from mist pass (cool blue haze)
    fog_amt = nb.n('ShaderNodeMath', operation='MULTIPLY')
    nb.link((rl, 'Mist'), fog_amt.inputs[0])
    fog_amt.inputs[1].default_value = 0.55
    vb = nb.n('CompositorNodeVecBlur')
    nb.link((rl, 'Image'), vb.inputs['Image'])
    nb.link((rl, 'Vector'), vb.inputs['Speed'])
    nb.link((rl, 'Depth'), vb.inputs['Depth'])
    vb.inputs['Samples'].default_value = 16
    vb.inputs['Shutter'].default_value = 0.45
    fog = _mix(nb, 'MIX', fog_amt, vb, (0.012, 0.018, 0.032, 1.0))
    # bloom (neon glow)
    bloom = nb.n('CompositorNodeGlare')
    nb.link(fog, bloom.inputs['Image'])
    _menu(bloom, 'Type', 'Bloom')
    _menu(bloom, 'Quality', 'High')
    bloom.inputs['Threshold'].default_value = 1.1
    bloom.inputs['Smoothness'].default_value = 0.4
    bloom.inputs['Strength'].default_value = 0.42
    bloom.inputs['Size'].default_value = 0.72
    bloom.inputs['Saturation'].default_value = 1.0
    # anamorphic streaks on the hottest highlights only
    st = nb.n('CompositorNodeGlare')
    nb.link(bloom, st.inputs['Image'])
    _menu(st, 'Type', 'Streaks')
    _menu(st, 'Quality', 'Medium')
    st.inputs['Threshold'].default_value = 25.0
    st.inputs['Streaks'].default_value = 2
    st.inputs['Streaks Angle'].default_value = 0.0
    st.inputs['Fade'].default_value = 0.93
    st.inputs['Strength'].default_value = 0.12
    st.inputs['Saturation'].default_value = 0.6
    st.inputs['Tint'].default_value = (0.75, 0.85, 1.0, 1.0)
    # lens dispersion (subtle chromatic aberration)
    lens = nb.n('CompositorNodeLensdist')
    nb.link(st, lens.inputs['Image'])
    lens.inputs['Distortion'].default_value = -0.008
    lens.inputs['Dispersion'].default_value = 0.012
    lens.inputs['Fit'].default_value = True
    # vignette
    em = nb.n('CompositorNodeEllipseMask')
    em.inputs['Size'].default_value = (0.92, 0.82)
    bl = nb.n('CompositorNodeBlur')
    nb.link(em, bl.inputs['Image'])
    bl.inputs['Size'].default_value = (260, 260)
    vig_fac = nb.n('ShaderNodeMapRange')
    nb.link(bl, vig_fac.inputs[0])
    vig_fac.inputs[3].default_value = 0.55
    vig_fac.inputs[4].default_value = 1.0
    vig = _mix(nb, 'MULTIPLY', 1.0, lens, (1, 1, 1, 1))
    vin = [s for s in vig.inputs if s.enabled]
    cc = nb.n('CompositorNodeCombineColor')
    for i in range(3):
        nb.link(vig_fac, cc.inputs[i])
    nb.link(cc, vin[2])
    # grade: teal shadows, slightly warm/magenta highlights
    cb = nb.n('CompositorNodeColorBalance')
    nb.link(vig, cb.inputs['Image'])
    try:
        _menu(cb, 'Type', 'Lift/Gamma/Gain')
    except Exception:
        pass
    lift = [s for s in cb.inputs if s.name == 'Lift' and s.bl_idname.startswith('NodeSocketColor')]
    gain = [s for s in cb.inputs if s.name == 'Gain' and s.bl_idname.startswith('NodeSocketColor')]
    gamma = [s for s in cb.inputs if s.name == 'Gamma' and s.bl_idname.startswith('NodeSocketColor')]
    if lift:
        lift[0].default_value = (0.985, 1.0, 1.03, 1)
    if gamma:
        gamma[0].default_value = (0.99, 1.0, 1.03, 1)
    if gain:
        gain[0].default_value = (1.04, 1.0, 1.02, 1)
    out = nb.n('NodeGroupOutput')
    nb.link(cb, out.inputs[0])
    return g
