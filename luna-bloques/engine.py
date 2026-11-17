"""Motor voxel propio: sube el mundo a la GPU (OpenGL 4.5 sin ventana) y renderiza fotogramas
con el shader de trazado de rayos + pétalos rasterizados + bloom + gradación de color."""
import os
import numpy as np
import moderngl
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TP = os.path.join(HERE, "texturepack")

# ------------------------------------------------------------------ tabla de bloques
# id: (arriba, lado, abajo, flags)   flags: 1 recorte, 2 agua, 4 emisivo, 8 emisivo por máscara, 16 brillante
CUT, WAT, EMI, EMASK, GLOSS = 1, 2, 4, 8, 16
BLOCKS = {
    1: ("grass_top", "grass_side", "dirt", 0),
    2: ("dirt", "dirt", "dirt", 0),
    3: ("stone", "stone", "stone", 0),
    4: ("cobble", "cobble", "cobble", 0),
    5: ("path_stone", "path_stone", "path_stone", 0),
    6: ("plaza_tiles", "plaza_tiles", "plaza_tiles", GLOSS),
    7: ("stone_bricks", "stone_bricks", "stone_bricks", 0),
    8: ("planks", "planks", "planks", 0),
    9: ("lacquer", "lacquer", "lacquer", GLOSS),
    10: ("dark_wood", "dark_wood", "dark_wood", 0),
    11: ("log_top", "log_side", "log_top", 0),
    12: ("shoji", "shoji", "shoji", 0),
    13: ("shoji_lit", "shoji_lit", "shoji_lit", EMI),
    14: ("roof_tiles", "roof_tiles", "roof_tiles", GLOSS),
    15: ("sakura_leaves", "sakura_leaves", "sakura_leaves", CUT),
    16: ("green_leaves", "green_leaves", "green_leaves", CUT),
    17: ("water", "water", "water", WAT),
    18: ("sand", "sand", "sand", 0),
    19: ("farmland", "dirt", "dirt", 0),
    20: ("paper_lantern", "paper_lantern", "paper_lantern", EMI),
    21: ("stone_bricks", "stone_lantern", "stone_bricks", EMASK),
    22: ("tatami", "tatami", "tatami", 0),
}

QUAD_VS = """
#version 450
in vec2 in_pos;
void main() { gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

PETAL_VS = """
#version 450
uniform mat4 uVP;
uniform vec3 uCamPos;
in vec3 in_pos;
in vec3 in_col;
out vec3 vCol;
out float vDist;
out vec3 vPos;
void main() {
    gl_Position = uVP * vec4(in_pos, 1.0);
    vCol = in_col;
    vDist = length(in_pos - uCamPos);
    vPos = in_pos;
}
"""

PETAL_FS = """
#version 450
in vec3 vCol;
in float vDist;
in vec3 vPos;
uniform vec3 uFirePos;
uniform float uFireI;
out vec4 fragColor;
void main() {
    vec3 c = pow(vCol, vec3(2.2));
    float fd = length(uFirePos - vPos);
    vec3 light = vec3(0.55, 0.55, 0.95) * 0.75 + vec3(0.25, 0.2, 0.4)
               + vec3(1.0, 0.45, 0.15) * uFireI * 0.5 / (1.0 + fd * fd * 0.06);
    c = c * light + c * 0.25;                       // un poco de translucidez
    float f = 1.0 - exp(-max(vDist - 30.0, 0.0) * 0.0055);
    c = mix(c, vec3(0.12, 0.06, 0.20), f);
    fragColor = vec4(c, 1.0);
}
"""

DOWN_FS = """
#version 450
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform float uThreshold;
out vec4 fragColor;
void main() {
    vec2 uv = gl_FragCoord.xy / vec2(textureSize(uSrc, 0)) * 0.5 * 2.0;
    uv = (gl_FragCoord.xy * 2.0) * uTexel;
    vec3 c = vec3(0.0);
    c += textureLod(uSrc, uv + uTexel * vec2(-1, -1), 0.0).rgb;
    c += textureLod(uSrc, uv + uTexel * vec2( 1, -1), 0.0).rgb;
    c += textureLod(uSrc, uv + uTexel * vec2(-1,  1), 0.0).rgb;
    c += textureLod(uSrc, uv + uTexel * vec2( 1,  1), 0.0).rgb;
    c *= 0.25;
    if (uThreshold > 0.0) {
        float l = max(c.r, max(c.g, c.b));
        c *= smoothstep(uThreshold, uThreshold * 2.0, l);
    }
    fragColor = vec4(c, 1.0);
}
"""

UP_FS = """
#version 450
uniform sampler2D uSrc;
uniform vec2 uTexel;     // texel de la fuente (más pequeña)
uniform vec2 uDstRes;
out vec4 fragColor;
void main() {
    vec2 uv = gl_FragCoord.xy / uDstRes;
    vec3 c = vec3(0.0);
    c += textureLod(uSrc, uv + uTexel * vec2(-1, -1), 0.0).rgb;
    c += textureLod(uSrc, uv + uTexel * vec2( 1, -1), 0.0).rgb;
    c += textureLod(uSrc, uv + uTexel * vec2(-1,  1), 0.0).rgb;
    c += textureLod(uSrc, uv + uTexel * vec2( 1,  1), 0.0).rgb;
    c += textureLod(uSrc, uv, 0.0).rgb * 4.0;
    fragColor = vec4(c / 8.0, 1.0);
}
"""

FINAL_FS = """
#version 450
uniform sampler2D uHdr;
uniform sampler2D uBloom;
uniform vec2 uOutRes;
uniform float uExposure;
uniform float uBloomK;
uniform float uTime;
out vec4 fragColor;

vec3 aces(vec3 x) {
    const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

void main() {
    vec2 uv = gl_FragCoord.xy / uOutRes;
    // aberración cromática muy suave en los bordes
    vec2 dc = (uv - 0.5);
    float ca = dot(dc, dc) * 0.0035;
    vec3 hdr;
    hdr.r = texture(uHdr, uv + dc * ca).r;
    hdr.g = texture(uHdr, uv).g;
    hdr.b = texture(uHdr, uv - dc * ca).b;
    vec3 bloom = texture(uBloom, uv).rgb;
    vec3 c = (hdr + bloom * uBloomK) * uExposure;
    c = aces(c);
    // gradación anime: más saturación, sombras hacia violeta, luces cálidas
    float l = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(vec3(l), c, 1.22);
    c += vec3(0.020, 0.0, 0.035) * (1.0 - l);
    c = pow(clamp(c, 0.0, 1.0), vec3(1.0 / 2.2));
    // viñeta
    float v = smoothstep(1.05, 0.35, length(dc * vec2(1.0, 0.85)) * 1.25);
    c *= mix(0.72, 1.0, v);
    c += (hash(gl_FragCoord.xy + uTime * 61.0) - 0.5) * 0.012;      // grano
    fragColor = vec4(c, 1.0);
}
"""


def _load_rgba(path, flip=True):
    im = np.array(Image.open(path).convert("RGBA"))
    return im[::-1] if flip else im


class Engine:
    def __init__(self, out_w=1920, out_h=1080, ss=1.0):
        self.out = (out_w, out_h)
        self.res = (int(out_w * ss), int(out_h * ss))
        ctx = self.ctx = moderngl.create_standalone_context(backend="egl", require=450)
        A = os.path.join(HERE, "assets")

        # --- mundo
        w = np.load(os.path.join(A, "world.npz"))
        W = w["W"]
        self.origin = w["origin"].astype(np.float32)
        self.size = W.shape
        self.t_world = ctx.texture3d(W.shape, 1, np.ascontiguousarray(W.transpose(2, 1, 0)).tobytes(), dtype="u1")
        self.t_world.filter = (moderngl.NEAREST, moderngl.NEAREST)
        L = w["light"]
        self.t_light = ctx.texture3d(W.shape, 2, np.ascontiguousarray(L.transpose(2, 1, 0, 3)).tobytes(), dtype="f1")
        self.t_light.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.t_light.repeat_x = self.t_light.repeat_y = self.t_light.repeat_z = False
        self.plants = w["plants"]

        # --- texturas de bloques (texture pack)
        names = []
        for b in BLOCKS.values():
            for n in b[:3]:
                if n not in names:
                    names.append(n)
        layers = [_load_rgba(os.path.join(TP, "blocks", n + ".png")) for n in names]
        arr = np.stack(layers)
        self.t_blocks = ctx.texture_array((32, 32, len(layers)), 4, arr.tobytes())
        self.t_blocks.build_mipmaps()
        self.t_blocks.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.NEAREST)
        self.face_tex = np.zeros((32, 4), np.int32)
        for bid, (t, s, b, fl) in BLOCKS.items():
            self.face_tex[bid] = (names.index(t), names.index(s), names.index(b), fl)

        # --- luna voxel
        m = np.load(os.path.join(A, "moon_vox.npz"))
        occ, col, mat = m["occ"], m["col"].astype(np.float32), m["mat"]
        rgba = np.zeros(occ.shape + (4,), np.uint8)
        rgba[..., :3] = np.clip(col * 255, 0, 255).astype(np.uint8)
        rgba[..., 3] = np.where(occ, (mat.astype(np.int32) + 1) * 85, 0).astype(np.uint8)
        self.moon_size = occ.shape
        self.moon_vox_norm = float(m["vox"][0])
        self.t_moon = ctx.texture3d(occ.shape, 4, np.ascontiguousarray(rgba.transpose(2, 1, 0, 3)).tobytes())
        self.t_moon.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # --- texturas de personajes
        sk = os.path.join(TP, "skins")
        self.skin_names = sorted(f[:-4] for f in os.listdir(sk) if f.endswith(".png"))
        skins = [_load_rgba(os.path.join(sk, n + ".png")) for n in self.skin_names]
        flames = []
        for c in [(255, 236, 140), (255, 178, 60), (255, 110, 40), (255, 70, 90)]:
            im = np.zeros((16, 16, 4), np.uint8)
            im[..., :3] = c
            im[..., 3] = 255
            im[::4, ::4, :3] = np.minimum(np.array(c) + 40, 255)
            flames.append(im)
        self.skin_names += ["flame_0", "flame_1", "flame_2", "flame_3"]
        skins += flames
        self.t_skin = ctx.texture_array((16, 16, len(skins)), 4, np.stack(skins).tobytes())
        self.t_skin.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # --- máscara de nubes de bloques
        rng = np.random.default_rng(3)
        from scipy import ndimage
        n = ndimage.gaussian_filter(rng.standard_normal((64, 64)), 2.2, mode="wrap")
        n2 = ndimage.gaussian_filter(rng.standard_normal((64, 64)), 0.8, mode="wrap")
        cm = ((n / n.std() + 0.35 * n2 / n2.std()) > 0.55).astype(np.uint8) * 255
        self.t_cloud = ctx.texture((64, 64), 1, np.ascontiguousarray(cm.T).tobytes())
        self.t_cloud.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # --- programas
        src = open(os.path.join(HERE, "shaders", "voxel.frag")).read()
        self.p_main = ctx.program(vertex_shader=QUAD_VS, fragment_shader=src)
        self.p_petal = ctx.program(vertex_shader=PETAL_VS, fragment_shader=PETAL_FS)
        self.p_down = ctx.program(vertex_shader=QUAD_VS, fragment_shader=DOWN_FS)
        self.p_up = ctx.program(vertex_shader=QUAD_VS, fragment_shader=UP_FS)
        self.p_final = ctx.program(vertex_shader=QUAD_VS, fragment_shader=FINAL_FS)
        quad = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], np.float32).tobytes())
        self.vao = {p: ctx.vertex_array(prog, [(quad, "2f", "in_pos")])
                    for p, prog in (("main", self.p_main), ("down", self.p_down), ("up", self.p_up),
                                    ("final", self.p_final))}
        self.box_ubo = ctx.buffer(reserve=160 * (64 + 16 + 16 + 16))
        self.petal_vbo = ctx.buffer(reserve=4 * 6 * 6 * 4000)
        self.petal_vao = ctx.vertex_array(self.p_petal, [(self.petal_vbo, "3f 3f", "in_pos", "in_col")])

        # --- framebuffers
        rw, rh = self.res
        self.t_hdr = ctx.texture((rw, rh), 4, dtype="f2")
        self.t_hdr.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.t_hdr.repeat_x = self.t_hdr.repeat_y = False
        self.depth = ctx.depth_renderbuffer((rw, rh))
        self.fb_hdr = ctx.framebuffer([self.t_hdr], self.depth)
        self.bloom_levels = []
        bw, bh = rw, rh
        for _ in range(6):
            bw, bh = max(bw // 2, 1), max(bh // 2, 1)
            t = ctx.texture((bw, bh), 4, dtype="f2")
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
            t2 = ctx.texture((bw, bh), 4, dtype="f2")
            t2.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t2.repeat_x = t2.repeat_y = False
            self.bloom_levels.append((t, ctx.framebuffer([t]), t2, ctx.framebuffer([t2])))
        self.t_out = ctx.texture(self.out, 4)
        self.fb_out = ctx.framebuffer([self.t_out])
        self.near_far = (0.1, 3000.0)

        # uniformes fijos
        p = self.p_main
        p["uRes"] = self.res
        p["uWorldSize"] = tuple(int(s) for s in self.size)
        p["uWorldOrigin"] = tuple(float(o) for o in self.origin)
        p["uFaceTex"].write(self.face_tex.tobytes())
        p["uMoonSize"] = tuple(int(s) for s in self.moon_size)
        p["uNearFar"] = self.near_far
        for name, unit in (("uWorld", 0), ("uLight", 1), ("uBlockTex", 2), ("uMoon", 3), ("uSkinTex", 4),
                           ("uCloudMask", 5)):
            p[name] = unit

    def skin(self, name):
        return self.skin_names.index(name)

    # ------------------------------------------------------------------ render
    def render(self, st):
        ctx = self.ctx
        p = self.p_main
        cam_pos = np.asarray(st["cam_pos"], np.float32)
        R = np.asarray(st["cam_rot"], np.float32)        # columnas: derecha, arriba, adelante
        tan_half = np.tan(np.radians(st["fov"]) / 2)
        p["uCamPos"] = tuple(cam_pos)
        p["uCamRot"] = tuple(R.T.ravel())
        p["uTanHalf"] = float(tan_half)
        p["uTime"] = float(st["time"])
        p["uJitter"] = tuple(st.get("jitter", (0.0, 0.0)))
        p["uMoonC"] = tuple(st["moon_c"])
        p["uMoonR"] = tuple(np.asarray(st["moon_r"], np.float32).T.ravel())
        p["uMoonVox"] = float(st["moon_radius"] * self.moon_vox_norm)
        p["uMoonGlint"] = float(st["moon_glint"])
        p["uSunDir"] = tuple(st["sun_dir"])
        p["uFirePos"] = tuple(st["fire_pos"])
        p["uFireI"] = float(st["fire_i"])
        p["uCloudOff"] = tuple(st["cloud_off"])

        # cajas de personajes
        boxes = st["boxes"]          # lista de (M 4x4 local->mundo, half(3), texA(4), texB(4))
        nb = len(boxes)
        inv = np.zeros((160, 4, 4), np.float32)
        half = np.zeros((160, 4), np.float32)
        ta = np.zeros((160, 4), np.int32)
        tb = np.zeros((160, 4), np.int32)
        for i, (M, h, a, b) in enumerate(boxes):
            inv[i] = np.linalg.inv(M).T          # std140: columnas
            half[i, :3] = h
            ta[i] = a
            tb[i] = b
        self.box_ubo.write(inv.tobytes() + half.tobytes() + ta.tobytes() + tb.tobytes())
        self.box_ubo.bind_to_uniform_block(0)
        groups = st["groups"]        # lista de (centro, radio, i0, i1)
        sph = np.zeros((24, 4), np.float32)
        rng_ = np.zeros((24, 4), np.int32)
        for g, (c, r, i0, i1) in enumerate(groups):
            sph[g] = (*c, r)
            rng_[g, :2] = (i0, i1)
        p["uGroupSph"].write(sph.tobytes())
        p["uGroupRange"].write(rng_.tobytes())
        p["uNumGroups"] = len(groups)

        self.t_world.use(0)
        self.t_light.use(1)
        self.t_blocks.use(2)
        self.t_moon.use(3)
        self.t_skin.use(4)
        self.t_cloud.use(5)

        self.fb_hdr.use()
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.depth_func = "1"
        self.vao["main"].render(moderngl.TRIANGLES, vertices=3)

        # pétalos
        pv = st.get("petals")
        if pv is not None and len(pv):
            ctx.depth_func = "<"
            n, f = self.near_far
            aspect = self.res[0] / self.res[1]
            proj = np.zeros((4, 4), np.float32)
            proj[0, 0] = 1 / (tan_half * aspect)
            proj[1, 1] = 1 / tan_half
            proj[2, 2] = -(f + n) / (f - n)
            proj[2, 3] = -2 * f * n / (f - n)
            proj[3, 2] = -1
            view = np.eye(4, dtype=np.float32)
            view[0, :3], view[1, :3], view[2, :3] = R[:, 0], R[:, 1], -R[:, 2]
            view[:3, 3] = -view[:3, :3] @ cam_pos
            vp = proj @ view
            self.p_petal["uVP"].write(vp.T.astype(np.float32).tobytes())
            self.p_petal["uCamPos"] = tuple(cam_pos)
            self.p_petal["uFirePos"] = tuple(st["fire_pos"])
            self.p_petal["uFireI"] = float(st["fire_i"])
            data = np.ascontiguousarray(pv, np.float32)
            self.petal_vbo.orphan(max(data.nbytes, 64))
            self.petal_vbo.write(data.tobytes())
            self.petal_vao.render(moderngl.TRIANGLES, vertices=len(data))
        ctx.disable(moderngl.DEPTH_TEST)

        # bloom
        src = self.t_hdr
        for li, (t, fb, t2, fb2) in enumerate(self.bloom_levels):
            fb.use()
            src.use(0)
            self.p_down["uSrc"] = 0
            self.p_down["uTexel"] = (1 / src.size[0], 1 / src.size[1])
            self.p_down["uThreshold"] = 1.0 if li == 0 else 0.0
            self.vao["down"].render(moderngl.TRIANGLES, vertices=3)
            src = t
        up = self.bloom_levels[-1][0]
        for li in range(len(self.bloom_levels) - 2, -1, -1):
            t, fb, t2, fb2 = self.bloom_levels[li]
            fb2.use()
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.ONE, moderngl.ZERO
            up.use(0)
            self.p_up["uSrc"] = 0
            self.p_up["uTexel"] = (1 / up.size[0], 1 / up.size[1])
            self.p_up["uDstRes"] = t.size
            self.vao["up"].render(moderngl.TRIANGLES, vertices=3)
            # sumar el nivel actual
            ctx.blend_func = moderngl.ONE, moderngl.ONE
            t.use(0)
            self.p_up["uSrc"] = 0
            self.p_up["uTexel"] = (0.0, 0.0)
            self.vao["up"].render(moderngl.TRIANGLES, vertices=3)
            ctx.disable(moderngl.BLEND)
            up = t2

        self.fb_out.use()
        self.t_hdr.use(0)
        up.use(1)
        f = self.p_final
        f["uHdr"] = 0
        f["uBloom"] = 1
        f["uOutRes"] = self.out
        f["uExposure"] = float(st.get("exposure", 1.0))
        f["uBloomK"] = float(st.get("bloom", 0.22))
        f["uTime"] = float(st["time"])
        self.vao["final"].render(moderngl.TRIANGLES, vertices=3)
        data = self.fb_out.read(components=3)
        img = np.frombuffer(data, np.uint8).reshape(self.out[1], self.out[0], 3)[::-1]
        return img
