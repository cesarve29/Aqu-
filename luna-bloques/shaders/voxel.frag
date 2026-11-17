#version 450
// Motor voxel por trazado de rayos (DDA) con efectos de "shader pack":
// sombras de la luna, AO suave por vértice, luz de bloques y de cielo, reflejos en el agua,
// niebla, nubes de bloques, estrellas y la luna voxel con halo.

out vec4 fragColor;

uniform vec2 uRes;
uniform vec2 uJitter;
uniform vec3 uCamPos;
uniform mat3 uCamRot;          // columnas: derecha, arriba, adelante
uniform float uTanHalf;        // tan(fov vertical / 2)
uniform float uTime;
uniform vec2 uNearFar;

// --- mundo
uniform usampler3D uWorld;
uniform sampler3D uLight;      // r = luz de bloques, g = luz de cielo
uniform ivec3 uWorldSize;
uniform vec3 uWorldOrigin;
uniform sampler2DArray uBlockTex;
uniform ivec4 uFaceTex[32];    // x arriba, y lado, z abajo, w flags

// --- luna
uniform sampler3D uMoon;       // rgb color, a: 0 vacío, ~0.33 luna, ~0.66 ojo, 1 brillo
uniform ivec3 uMoonSize;
uniform vec3 uMoonC;
uniform mat3 uMoonR;           // local -> mundo
uniform float uMoonVox;
uniform float uMoonGlint;

// --- personajes (cajas orientadas)
uniform sampler2DArray uSkinTex;
layout(std140, binding = 0) uniform Boxes {
    mat4 bInv[160];
    vec4 bHalf[160];
    ivec4 bTexA[160];          // +X -X +Y -Y
    ivec4 bTexB[160];          // +Z -Z flags -
};
uniform int uNumGroups;
uniform vec4 uGroupSph[24];
uniform ivec4 uGroupRange[24];

// --- luces y ambiente
uniform vec3 uSunDir;
uniform vec3 uFirePos;
uniform float uFireI;
uniform vec2 uCloudOff;
uniform sampler2D uCloudMask;

const uint WATER = 17u;
const int F_CUTOUT = 1, F_WATER = 2, F_EMIT = 4, F_EMITMASK = 8, F_GLOSSY = 16;

vec3 srgb(vec3 c) { return pow(c, vec3(2.2)); }

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// ------------------------------------------------------------------ cielo
const vec3 ZENITH = vec3(0.010, 0.010, 0.050);
const vec3 HORIZON = vec3(0.20, 0.07, 0.26);
const vec3 FOGC = vec3(0.12, 0.06, 0.20);

vec3 skyColor(vec3 rd) {
    float h = clamp(rd.z, -0.2, 1.0);
    vec3 c = mix(HORIZON, ZENITH, pow(clamp(h, 0.0, 1.0), 0.45));
    c = mix(c, vec3(0.42, 0.16, 0.38), exp(-abs(h) * 14.0) * 0.6);   // franja rosa en el horizonte
    // halo de la luna
    vec3 md = normalize(uMoonC - uCamPos);
    float ang = acos(clamp(dot(rd, md), -1.0, 1.0));
    float ar = atan(float(uMoonSize.x) * 0.5 * uMoonVox / length(uMoonC - uCamPos));
    c += vec3(0.50, 0.58, 0.95) * 0.30 * exp(-max(ang - ar * 0.85, 0.0) / (ar * 0.45));
    c += vec3(0.45, 0.25, 0.55) * 0.10 * exp(-ang / (ar * 3.0));
    // estrellas cuadradas (píxel)
    if (rd.z > 0.03) {
        vec3 a = abs(rd);
        vec2 uv; float face;
        if (a.z >= a.x && a.z >= a.y) { uv = rd.xy / a.z; face = 0.0; }
        else if (a.x >= a.y) { uv = rd.yz / a.x; face = 1.0 + sign(rd.x); }
        else { uv = rd.xz / a.y; face = 4.0 + sign(rd.y); }
        vec2 g = uv * 260.0;
        vec2 cell = floor(g);
        float hs = hash12(cell + face * 917.0);
        if (hs > 0.9935) {
            vec2 f = fract(g) - 0.5;
            float sz = 0.18 + 0.2 * fract(hs * 97.0);
            if (max(abs(f.x), abs(f.y)) < sz) {
                float tw = 0.6 + 0.4 * sin(uTime * (2.0 + 4.0 * fract(hs * 31.0)) + hs * 60.0);
                vec3 sc = mix(vec3(1.0, 0.85, 0.95), vec3(0.75, 0.85, 1.0), fract(hs * 13.0));
                c += sc * tw * 2.2 * smoothstep(0.03, 0.2, rd.z);
            }
        }
    }
    return c;
}

// ------------------------------------------------------------------ mundo: DDA
struct Hit { float t; uint id; ivec3 cell; ivec3 n; };

uint blockAt(ivec3 c) {
    if (any(lessThan(c, ivec3(0))) || any(greaterThanEqual(c, uWorldSize))) return 0u;
    return texelFetch(uWorld, c, 0).r;
}

vec2 faceUV(vec3 f, ivec3 n) {
    if (n.z != 0) return vec2(f.x, n.z > 0 ? f.y : 1.0 - f.y);
    if (n.x != 0) return vec2(n.x > 0 ? f.y : 1.0 - f.y, f.z);
    return vec2(n.y > 0 ? 1.0 - f.x : f.x, f.z);
}

int faceLayer(uint id, ivec3 n) {
    ivec4 ft = uFaceTex[int(id)];
    return n.z > 0 ? ft.x : (n.z < 0 ? ft.z : ft.y);
}

float texLod(float t, ivec3 n, vec3 rd) {
    float px = t * 2.0 * uTanHalf / uRes.y * 32.0;
    float graze = 1.0 / max(abs(dot(vec3(n), rd)), 0.25);
    return log2(max(px * sqrt(graze), 1e-4));
}

// mode: 0 = primario, 1 = sombra, 2 = bajo el agua (ignora el agua)
bool traceWorld(vec3 ro, vec3 rd, float tmax, int mode, out Hit h) {
    vec3 p = ro - uWorldOrigin;
    vec3 inv = 1.0 / rd;
    vec3 t0 = -p * inv, t1 = (vec3(uWorldSize) - p) * inv;
    vec3 tmn = min(t0, t1), tmx = max(t0, t1);
    float tn = max(max(tmn.x, tmn.y), max(tmn.z, 0.0));
    float tf = min(min(tmx.x, tmx.y), min(tmx.z, tmax));
    if (tn >= tf) return false;
    vec3 ps = p + rd * (tn + 1e-4);
    ivec3 c = clamp(ivec3(floor(ps)), ivec3(0), uWorldSize - 1);
    ivec3 stp = ivec3(sign(rd));
    vec3 tDelta = abs(inv);
    vec3 tNext = (vec3(c) + max(vec3(stp), 0.0) - p) * inv;
    ivec3 n = ivec3(0);
    if (tn == tmn.x) n = ivec3(-stp.x, 0, 0);
    else if (tn == tmn.y) n = ivec3(0, -stp.y, 0);
    else n = ivec3(0, 0, -stp.z);
    float t = tn;
    for (int i = 0; i < 600; i++) {
        uint id = texelFetch(uWorld, c, 0).r;
        if (id != 0u) {
            int fl = uFaceTex[int(id)].w;
            bool take = true;
            if ((fl & F_WATER) != 0) take = (mode == 0);
            else if ((fl & F_CUTOUT) != 0) {
                vec3 f = clamp(p + rd * t - vec3(c), 0.0, 1.0);
                float a = textureLod(uBlockTex, vec3(faceUV(f, n), faceLayer(id, n)), 0.0).a;
                take = a > 0.5;
            }
            if (take) { h.t = t; h.id = id; h.cell = c; h.n = n; return true; }
        }
        if (tNext.x < tNext.y) {
            if (tNext.x < tNext.z) { t = tNext.x; c.x += stp.x; tNext.x += tDelta.x; n = ivec3(-stp.x, 0, 0); }
            else { t = tNext.z; c.z += stp.z; tNext.z += tDelta.z; n = ivec3(0, 0, -stp.z); }
        } else {
            if (tNext.y < tNext.z) { t = tNext.y; c.y += stp.y; tNext.y += tDelta.y; n = ivec3(0, -stp.y, 0); }
            else { t = tNext.z; c.z += stp.z; tNext.z += tDelta.z; n = ivec3(0, 0, -stp.z); }
        }
        if (t > tf) return false;
        if (any(lessThan(c, ivec3(0))) || any(greaterThanEqual(c, uWorldSize))) return false;
    }
    return false;
}

// ------------------------------------------------------------------ personajes
bool boxHit(int i, vec3 ro, vec3 rd, float tmax, out float tHit, out int face, out vec3 lp) {
    vec3 o = (bInv[i] * vec4(ro, 1.0)).xyz;
    vec3 d = mat3(bInv[i]) * rd;
    vec3 hb = bHalf[i].xyz;
    vec3 inv = 1.0 / d;
    vec3 t0 = (-hb - o) * inv, t1 = (hb - o) * inv;
    vec3 tmn = min(t0, t1), tmx = max(t0, t1);
    float tn = max(max(tmn.x, tmn.y), tmn.z);
    float tf = min(min(tmx.x, tmx.y), tmx.z);
    if (tn > tf || tf < 0.0 || tn > tmax || tn < 1e-3) return false;
    tHit = tn;
    lp = o + d * tn;
    if (tn == tmn.x) face = d.x < 0.0 ? 0 : 1;
    else if (tn == tmn.y) face = d.y < 0.0 ? 2 : 3;
    else face = d.z < 0.0 ? 4 : 5;
    return true;
}

bool traceBoxes(vec3 ro, vec3 rd, float tmax, out float tBest, out int bi, out int bface, out vec3 blp) {
    tBest = tmax; bi = -1;
    for (int g = 0; g < uNumGroups; g++) {
        vec3 oc = ro - uGroupSph[g].xyz;
        float b = dot(oc, rd);
        float cc = dot(oc, oc) - uGroupSph[g].w * uGroupSph[g].w;
        float disc = b * b - cc;
        if (disc < 0.0) continue;
        float ts = -b - sqrt(disc);
        if (ts > tBest || -b + sqrt(disc) < 0.0) continue;
        for (int i = uGroupRange[g].x; i < uGroupRange[g].y; i++) {
            float th; int f; vec3 lp;
            if (boxHit(i, ro, rd, tBest, th, f, lp)) { tBest = th; bi = i; bface = f; blp = lp; }
        }
    }
    return bi >= 0;
}

// ------------------------------------------------------------------ luna voxel
bool traceMoon(vec3 ro, vec3 rd, out float tHit, out vec4 vox, out vec3 nw) {
    mat3 Rt = transpose(uMoonR);
    vec3 p = Rt * (ro - uMoonC) / uMoonVox + vec3(uMoonSize) * 0.5;
    vec3 d = Rt * rd / uMoonVox;
    vec3 inv = 1.0 / d;
    vec3 t0 = -p * inv, t1 = (vec3(uMoonSize) - p) * inv;
    vec3 tmn = min(t0, t1), tmx = max(t0, t1);
    float tn = max(max(tmn.x, tmn.y), max(tmn.z, 0.0));
    float tf = min(min(tmx.x, tmx.y), tmx.z);
    if (tn >= tf) return false;
    ivec3 c = clamp(ivec3(floor(p + d * (tn + 1e-4))), ivec3(0), uMoonSize - 1);
    ivec3 stp = ivec3(sign(d));
    vec3 tDelta = abs(inv);
    vec3 tNext = (vec3(c) + max(vec3(stp), 0.0) - p) * inv;
    ivec3 n;
    if (tn == tmn.x) n = ivec3(-stp.x, 0, 0);
    else if (tn == tmn.y) n = ivec3(0, -stp.y, 0);
    else n = ivec3(0, 0, -stp.z);
    float t = tn;
    for (int i = 0; i < 320; i++) {
        vec4 v = texelFetch(uMoon, c, 0);
        if (v.a > 0.1) { tHit = t; vox = v; nw = uMoonR * vec3(n); return true; }
        if (tNext.x < tNext.y) {
            if (tNext.x < tNext.z) { t = tNext.x; c.x += stp.x; tNext.x += tDelta.x; n = ivec3(-stp.x, 0, 0); }
            else { t = tNext.z; c.z += stp.z; tNext.z += tDelta.z; n = ivec3(0, 0, -stp.z); }
        } else {
            if (tNext.y < tNext.z) { t = tNext.y; c.y += stp.y; tNext.y += tDelta.y; n = ivec3(0, -stp.y, 0); }
            else { t = tNext.z; c.z += stp.z; tNext.z += tDelta.z; n = ivec3(0, 0, -stp.z); }
        }
        if (t > tf || any(lessThan(c, ivec3(0))) || any(greaterThanEqual(c, uMoonSize))) return false;
    }
    return false;
}

vec3 shadeMoon(vec4 v, vec3 nw, vec3 rd) {
    vec3 L = normalize(uMoonR * vec3(-0.55, 0.55, 0.65));
    float ndl = dot(nw, L);
    float cel = ndl > 0.25 ? 1.0 : (ndl > -0.2 ? 0.78 : 0.62);       // sombreado por bandas (anime)
    vec3 col = srgb(v.rgb);
    if (v.a > 0.9) return vec3(3.5) * (0.6 + 0.8 * uMoonGlint);    // brillo del ojo
    if (v.a > 0.5) {                                                  // cristal del ojo
        float fr = pow(1.0 - max(dot(-rd, nw), 0.0), 3.0);
        return col * 1.1 + vec3(0.25, 0.6, 0.6) * fr * 0.6;
    }
    return col * vec3(1.0, 0.93, 0.78) * cel * 1.1;
}

// ------------------------------------------------------------------ nubes de bloques
const float CZ0 = 84.0, CZ1 = 88.0, CS = 7.0;

bool cloudAt(ivec2 cc) {
    return texelFetch(uCloudMask, ivec2(mod(vec2(cc), 64.0)), 0).r > 0.5;
}

bool traceClouds(vec3 ro, vec3 rd, out float tHit, out vec3 n) {
    if (abs(rd.z) < 1e-4) return false;
    float ta = (CZ0 - ro.z) / rd.z, tb = (CZ1 - ro.z) / rd.z;
    float tn = max(min(ta, tb), 0.0), tf = max(ta, tb);
    if (tf <= tn) return false;
    vec2 off = uCloudOff;
    vec2 p = (ro.xy + off) / CS;
    vec2 d = rd.xy / CS;
    vec2 ps = p + d * tn;
    ivec2 c = ivec2(floor(ps));
    ivec2 stp = ivec2(sign(d));
    vec2 inv = 1.0 / d;
    vec2 tD = abs(inv);
    vec2 tN = (vec2(c) + max(vec2(stp), 0.0) - p) * inv;
    float t = tn;
    n = vec3(0.0, 0.0, -sign(rd.z));
    for (int i = 0; i < 48; i++) {
        if (cloudAt(c)) { tHit = t; return true; }
        if (tN.x < tN.y) { t = tN.x; c.x += stp.x; tN.x += tD.x; n = vec3(-float(stp.x), 0.0, 0.0); }
        else { t = tN.y; c.y += stp.y; tN.y += tD.y; n = vec3(0.0, -float(stp.y), 0.0); }
        if (t > tf) return false;
    }
    return false;
}

// ------------------------------------------------------------------ sombreado de superficies
float occ(ivec3 c) {
    uint id = blockAt(c);
    return (id != 0u && id != WATER) ? 1.0 : 0.0;
}

float vao(float s1, float s2, float c) { return (s1 + s2 > 1.5) ? 0.0 : (3.0 - s1 - s2 - c) / 3.0; }

float faceAO(ivec3 cell, ivec3 n, vec3 f) {
    ivec3 q = cell + n;
    ivec3 U, V; float fu, fv;
    if (n.z != 0) { U = ivec3(1, 0, 0); V = ivec3(0, 1, 0); fu = f.x; fv = f.y; }
    else if (n.x != 0) { U = ivec3(0, 1, 0); V = ivec3(0, 0, 1); fu = f.y; fv = f.z; }
    else { U = ivec3(1, 0, 0); V = ivec3(0, 0, 1); fu = f.x; fv = f.z; }
    float u0 = occ(q - U), u1 = occ(q + U), v0 = occ(q - V), v1 = occ(q + V);
    float a00 = vao(u0, v0, occ(q - U - V)), a10 = vao(u1, v0, occ(q + U - V));
    float a01 = vao(u0, v1, occ(q - U + V)), a11 = vao(u1, v1, occ(q + U + V));
    return mix(mix(a00, a10, fu), mix(a01, a11, fu), fv);
}

float shadowVis(vec3 p) {
    Hit hs;
    if (traceWorld(p, uSunDir, 90.0, 1, hs)) return 0.0;
    float tb; int bi, bf; vec3 lp;
    if (traceBoxes(p, uSunDir, 40.0, tb, bi, bf, lp)) return 0.0;
    return 1.0;
}

vec2 lightAt(vec3 p) {
    return texture(uLight, (p - uWorldOrigin) / vec3(uWorldSize)).rg;
}

vec3 lighting(vec3 p, vec3 n, float ao, vec3 rd, float gloss) {
    vec2 L = lightAt(p + n * 0.5);
    float ndl = max(dot(n, uSunDir), 0.0);
    float vis = ndl > 0.0 ? shadowVis(p + n * 2e-3) : 0.0;
    vec3 moon = vec3(0.52, 0.60, 1.0) * 1.05 * ndl * vis;
    vec3 amb = vec3(0.11, 0.10, 0.24) * (0.2 + 0.8 * L.g * L.g) * (0.35 + 0.65 * ao);
    float flick = 0.92 + 0.08 * sin(uTime * 13.0) * sin(uTime * 7.3 + 1.0);
    vec3 blk = vec3(1.0, 0.52, 0.22) * pow(L.r, 2.4) * 2.6 * flick * (0.5 + 0.5 * ao);
    vec3 fd = uFirePos - p;
    float fdist = length(fd);
    vec3 fire = vec3(1.0, 0.45, 0.15) * uFireI * max(dot(n, fd / fdist), 0.0) / (1.0 + fdist * fdist * 0.06);
    vec3 col = moon + amb + blk + fire;
    if (gloss > 0.0) {
        vec3 hv = normalize(uSunDir - rd);
        col += vec3(0.6, 0.7, 1.0) * pow(max(dot(n, hv), 0.0), 60.0) * gloss * vis;
    }
    return col;
}

vec3 applyFog(vec3 c, float t, vec3 rd, vec3 p) {
    float f = 1.0 - exp(-max(t - 30.0, 0.0) * 0.0055);
    float hf = exp(-max(p.z - 5.0, 0.0) * 0.18) * 0.18 * (1.0 - exp(-t * 0.015));
    vec3 md = normalize(uMoonC - uCamPos);
    vec3 fc = FOGC + vec3(0.25, 0.25, 0.45) * pow(max(dot(rd, md), 0.0), 8.0) * 0.35;
    return mix(c, fc, clamp(f + hf, 0.0, 1.0));
}

vec3 shadeBlock(Hit h, vec3 ro, vec3 rd, out vec3 hp) {
    hp = ro + rd * h.t;
    vec3 f = clamp(hp - uWorldOrigin - vec3(h.cell), 0.0, 1.0);
    vec3 n = vec3(h.n);
    int layer = faceLayer(h.id, h.n);
    vec4 tx = textureLod(uBlockTex, vec3(faceUV(f, h.n), layer), texLod(h.t, h.n, rd));
    vec3 alb = srgb(tx.rgb);
    int fl = uFaceTex[int(h.id)].w;
    float ao = faceAO(h.cell, h.n, f);
    vec3 col = alb * lighting(hp, n, ao, rd, (fl & F_GLOSSY) != 0 ? 1.0 : 0.0);
    if ((fl & F_EMIT) != 0) col += alb * 1.9;
    if ((fl & F_EMITMASK) != 0) {
        float m = smoothstep(0.15, 0.35, tx.r - tx.b);
        col += alb * m * 3.5;
    }
    return col;
}

vec3 shadeSkin(int bi, int face, vec3 lp, vec3 ro, vec3 rd, float t) {
    vec3 hb = bHalf[bi].xyz;
    vec3 q = clamp(lp / (2.0 * hb) + 0.5, 0.0, 1.0);
    vec2 uv; int layer;
    ivec4 A = bTexA[bi], B = bTexB[bi];
    if (face == 0) { uv = vec2(q.y, q.z); layer = A.x; }
    else if (face == 1) { uv = vec2(1.0 - q.y, q.z); layer = A.y; }
    else if (face == 2) { uv = vec2(1.0 - q.x, q.z); layer = A.z; }
    else if (face == 3) { uv = vec2(q.x, q.z); layer = A.w; }
    else if (face == 4) { uv = vec2(q.x, q.y); layer = B.x; }
    else { uv = vec2(q.x, 1.0 - q.y); layer = B.y; }
    vec3 ln = vec3(0.0);
    ln[face / 2] = (face % 2 == 0) ? 1.0 : -1.0;
    mat3 toWorld = inverse(mat3(bInv[bi]));
    vec3 n = normalize(toWorld * ln);
    vec3 alb = srgb(textureLod(uSkinTex, vec3(uv, layer), 0.0).rgb);
    vec3 hp = ro + rd * t;
    if (B.z == 1) return alb * 4.0;                                   // llamas
    float rim = pow(1.0 - max(dot(-rd, n), 0.0), 3.0);
    return alb * lighting(hp, n, 1.0, rd, 0.0) + alb * rim * vec3(0.35, 0.3, 0.6) * 0.5;
}

vec3 shadeSky(vec3 ro, vec3 rd, out float tOut) {
    tOut = uNearFar.y;
    vec3 c = skyColor(rd);
    float tm; vec4 v; vec3 nw;
    if (traceMoon(ro, rd, tm, v, nw)) { c = shadeMoon(v, nw, rd); tOut = tm; }
    float tc; vec3 cn;
    if (rd.z > 0.0 && traceClouds(ro, rd, tc, cn)) {
        float lit = cn.z > 0.5 ? 1.0 : (cn.z < -0.5 ? 0.45 : 0.68);
        vec3 md = normalize(uMoonC - (ro + rd * tc));
        lit += 0.35 * max(dot(cn, md), 0.0);
        vec3 cc = vec3(0.42, 0.36, 0.62) * lit;
        float fade = exp(-tc * 0.0025);
        // las nubes se apartan de la cara de la luna
        vec3 md2 = normalize(uMoonC - ro);
        float ang = acos(clamp(dot(rd, md2), -1.0, 1.0));
        float ar = atan(float(uMoonSize.x) * 0.5 * uMoonVox / length(uMoonC - ro));
        fade *= smoothstep(ar * 0.9, ar * 1.25, ang);
        c = mix(c, cc, 0.8 * fade);
        tOut = min(tOut, tc);
    }
    return c;
}

void main() {
    vec2 uv = (gl_FragCoord.xy + uJitter - 0.5 * uRes) / uRes.y;
    vec3 rd = normalize(uCamRot * vec3(uv * 2.0 * uTanHalf, 1.0));
    vec3 ro = uCamPos;

    Hit h;
    bool hw = traceWorld(ro, rd, 400.0, 0, h);
    float tw = hw ? h.t : 1e9;
    float tb; int bi, bf; vec3 blp;
    bool hb = traceBoxes(ro, rd, min(tw, 200.0), tb, bi, bf, blp);

    vec3 col; float tDepth;
    if (hb) {
        col = shadeSkin(bi, bf, blp, ro, rd, tb);
        col = applyFog(col, tb, rd, ro + rd * tb);
        tDepth = tb;
    } else if (hw) {
        vec3 hp;
        if (h.id == WATER) {
            hp = ro + rd * h.t;
            vec3 n = vec3(h.n);
            if (h.n.z > 0) {
                vec2 w = hp.xy * 0.9 + uTime * vec2(0.6, 0.4);
                n = normalize(vec3(0.06 * sin(w.x) * cos(w.y * 1.3), 0.06 * cos(w.x * 0.7 + w.y), 1.0));
            }
            // refracción: lo que hay bajo el agua
            Hit hu; vec3 under = vec3(0.01, 0.03, 0.08);
            vec3 hp2;
            if (traceWorld(hp + rd * 1e-3, rd, 20.0, 2, hu)) {
                float dep = hu.t;
                under = shadeBlock(hu, hp + rd * 1e-3, rd, hp2) * exp(-dep * vec3(0.9, 0.45, 0.25));
            }
            vec3 wtx = srgb(textureLod(uBlockTex, vec3(fract(hp.xy * 0.25 + uTime * 0.03), uFaceTex[17].x), 1.0).rgb);
            under = mix(under, wtx * lighting(hp, vec3(0, 0, 1), 1.0, rd, 0.0), 0.35);
            // reflejo
            vec3 rr = reflect(rd, n);
            vec3 refl;
            Hit hr;
            if (traceWorld(hp + n * 1e-3, rr, 160.0, 2, hr)) {
                vec3 hp3;
                refl = applyFog(shadeBlock(hr, hp + n * 1e-3, rr, hp3), hr.t, rr, hp3);
            } else {
                float ts;
                refl = shadeSky(hp, rr, ts);
            }
            float fr = 0.04 + 0.96 * pow(1.0 - max(dot(-rd, n), 0.0), 5.0);
            col = mix(under, refl, clamp(fr * 1.4 + 0.12, 0.0, 1.0));
        } else {
            col = shadeBlock(h, ro, rd, hp);
        }
        col = applyFog(col, h.t, rd, hp);
        tDepth = h.t;
    } else {
        col = shadeSky(ro, rd, tDepth);
    }

    float zview = tDepth * dot(rd, uCamRot[2]);
    float n = uNearFar.x, fa = uNearFar.y;
    float ndc = (fa + n) / (fa - n) - 2.0 * fa * n / ((fa - n) * max(zview, n));
    gl_FragDepth = clamp(0.5 * ndc + 0.5, 0.0, 1.0);
    fragColor = vec4(col, 1.0);
}
