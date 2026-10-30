#version 330
// Mundo 3D de "Electric Heartbeat" (raymarching con look de render tipo Cycles:
// oclusion ambiental, reflejos con Fresnel, sombras suaves, vidrio emisivo).
// uScene 0 = ciudad de neon con un corazon gigante en el cielo (uDecay apaga la ciudad),
// uScene 1 = arteria electrica (tunel con venas de luz que laten),
// uScene 2 = camara del corazon (corazon colosal, pilares y arcos electricos).
uniform vec2 uRes;
uniform float uTime;
uniform int uScene;
uniform vec3 uCamPos;
uniform vec3 uCamTgt;
uniform float uRoll;
uniform float uFov;
uniform float uBass;
uniform float uKick;
uniform float uBeat;      // latido "lub-dub" 0..1
uniform float uFlash;
uniform vec3 uCol1;
uniform vec3 uCol2;
uniform vec3 uFog;
uniform float uPulseR;
uniform float uPulseA;
uniform vec3 uPulseC;
uniform float uWin;
uniform float uDecay;
uniform float uSpark;     // chispa que atraviesa el gris (verse 2)
uniform vec3 uSparkPos;
uniform vec4 uHeart;      // xyz = centro, w = escala
uniform float uArcs;
uniform float uSeed;
out vec4 fragColor;

#define MAXT 520.0
const float CELL = 11.0;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p3) { p3 = fract(p3 * 0.1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
    float s = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { s += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
    return s;
}
float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
float smin(float a, float b, float k) { float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }

// trazo de electrocardiograma: 0 en reposo, picos P-QRS-T en cada periodo
float ecg(float x) {
    float f = fract(x);
    float v = 0.12 * exp(-pow((f - 0.18) * 28.0, 2.0));
    v -= 0.18 * exp(-pow((f - 0.30) * 70.0, 2.0));
    v += 1.0 * exp(-pow((f - 0.335) * 60.0, 2.0));
    v -= 0.32 * exp(-pow((f - 0.37) * 60.0, 2.0));
    v += 0.22 * exp(-pow((f - 0.58) * 16.0, 2.0));
    return v;
}

// ------------------------------------------------------------------ corazon
// corazon unitario: lobulos arriba (y ~ +0.6), punta abajo (y ~ -1.0)
float sdHeartU(vec3 p) {
    p.x = abs(p.x);
    p.z *= 1.55;
    vec3 a = p - vec3(0.43, 0.22, 0.0);
    float lobe = length(a) - 0.52;
    // cuerpo: capsula inclinada hacia la punta
    vec3 pa = p - vec3(0.32, 0.1, 0.0), ba = vec3(-0.32, -1.02, 0.0);
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    float body = length(pa - ba * h) - mix(0.46, 0.05, h);
    return smin(lobe, body, 0.22) * 0.62;
}
float heartScale() { return uHeart.w * (1.0 + 0.075 * uBeat); }
float sdHeart(vec3 p) {
    float s = heartScale();
    vec3 q = (p - uHeart.xyz) / s;
    // leve giro para que se lea en 3D
    float a = 0.35 * sin(uTime * 0.3);
    q.xz = mat2(cos(a), -sin(a), sin(a), cos(a)) * q.xz;
    return sdHeartU(q) * s;
}

// ------------------------------------------------------------------ ciudad
float bHeight(vec2 id) {
    float h = hash12(id * 1.31 + 7.0);
    h = 12.0 + h * h * 75.0;
    return h * (1.0 + 0.35 * clamp(abs(id.x + 0.5) - 1.5, 0.0, 4.0));
}
vec2 bHalf(vec2 id) { float r = hash12(id + 3.1); return vec2(3.9 + 0.9 * r, 3.9 + 0.9 * fract(r * 7.3)); }

// x = distancia real, y = distancia segura para avanzar, z = material
vec3 mapCity(vec3 p) {
    vec2 id = floor(p.xz / CELL);
    vec2 q = p.xz - (id + 0.5) * CELL;
    float bound = min(CELL * 0.5 - abs(q.x), CELL * 0.5 - abs(q.y)) + 0.05;
    float dB = 1e5;
    if (abs(id.x + 0.5) > 1.0) {
        float h = bHeight(id);
        vec2 hs = bHalf(id);
        dB = sdBox(vec3(q.x, p.y - h * 0.5, q.y), vec3(hs.x, h * 0.5, hs.y)) - 0.12;
        float r = hash12(id + 11.7);
        if (r > 0.45) {
            float h2 = h * (0.2 + 0.35 * fract(r * 13.1));
            dB = min(dB, sdBox(vec3(q.x, p.y - h - h2 * 0.5, q.y), vec3(hs.x * 0.62, h2 * 0.5, hs.y * 0.62)) - 0.1);
            if (r > 0.8) dB = min(dB, sdBox(vec3(q.x, p.y - h - h2 - 6.0, q.y), vec3(0.15, 6.0, 0.15)));
        }
    }
    float dG = p.y;
    float real = min(dB, dG);
    float mat = dB < dG ? 1.0 : 2.0;
    float march = min(min(dB, max(bound, 0.25)), dG);
    return vec3(real, march, mat);
}

// ------------------------------------------------------------------ arteria
vec2 tPath(float z) { return vec2(7.0 * sin(z * 0.021) + 3.0 * sin(z * 0.047), 2.5 * sin(z * 0.017)); }
const float TR = 6.5;
vec3 mapTunnel(vec3 p) {
    vec2 c = tPath(p.z);
    vec2 d = p.xy - c;
    float ang = atan(d.y, d.x);
    // paredes organicas: costillas que respiran con el latido
    float rib = 0.35 * smoothstep(0.6, 1.0, sin(p.z * 0.9)) * (1.0 + 0.6 * uBeat);
    float wob = 0.25 * sin(ang * 6.0 + p.z * 0.3) + 0.15 * sin(ang * 11.0 - p.z * 0.5 + uTime);
    float dT = (TR - rib + wob - length(d)) * 0.7;
    // anillos-valvula cada 24 m
    float rz = mod(p.z, 24.0) - 12.0;
    float ring = max(abs(rz) - 0.35, length(d) - TR + 0.2);
    ring = max(ring, -(length(d) - TR + 1.2));
    float real = min(dT, ring);
    float mat = dT < ring ? 4.0 : 5.0;
    return vec3(real, real, mat);
}

// ------------------------------------------------------------------ camara del corazon
vec3 mapChamber(vec3 p) {
    float dF = p.y;
    float ang = atan(p.z, p.x);
    float sector = 6.2831853 / 10.0;
    float a = mod(ang + sector * 0.5, sector) - sector * 0.5;
    float r = length(p.xz);
    vec2 pp = vec2(cos(a), sin(a)) * r - vec2(72.0, 0.0);
    float dP = sdBox(vec3(pp.x, p.y - 30.0, pp.y), vec3(2.2, 30.0, 2.2)) - 0.3;
    float dRing = length(vec2(r - 72.0, p.y - 62.0)) - 1.6;
    float dH = sdHeart(p);
    float real = min(min(dF, dP), min(dRing, dH));
    float mat = 6.0;
    if (dP <= real || dRing <= real) mat = 7.0;
    if (dH <= real) mat = 3.0;
    return vec3(real, real, mat);
}

vec3 map(vec3 p) {
    if (uScene == 0) return mapCity(p);
    if (uScene == 1) return mapTunnel(p);
    return mapChamber(p);
}

float march(vec3 ro, vec3 rd, int steps, out float t) {
    t = 0.05;
    for (int i = 0; i < steps; i++) {
        vec3 m = map(ro + rd * t);
        if (m.x < 0.0015 * t + 0.004) return m.z;
        t += m.y * 0.9;
        if (t > MAXT) break;
    }
    return 0.0;
}

vec3 calcN(vec3 p) {
    const vec2 e = vec2(0.01, -0.01);
    return normalize(e.xyy * map(p + e.xyy).x + e.yyx * map(p + e.yyx).x +
                     e.yxy * map(p + e.yxy).x + e.xxx * map(p + e.xxx).x);
}

// oclusion ambiental (5 muestras a lo largo de la normal)
float calcAO(vec3 p, vec3 n) {
    float occ = 0.0, sca = 1.0;
    for (int i = 0; i < 5; i++) {
        float h = 0.05 + 0.9 * float(i) / 4.0;
        occ += (h - map(p + n * h).x) * sca;
        sca *= 0.72;
    }
    return clamp(1.0 - 1.4 * occ, 0.0, 1.0);
}

// sombra suave hacia una luz puntual
float softShadow(vec3 ro, vec3 rd, float tmax) {
    float res = 1.0, t = 0.3;
    for (int i = 0; i < 28; i++) {
        float h = map(ro + rd * t).x;
        res = min(res, 10.0 * h / t);
        t += clamp(h, 0.2, 6.0);
        if (res < 0.02 || t > tmax) break;
    }
    return clamp(res, 0.0, 1.0);
}

vec3 heartMat(vec3 p, vec3 n, vec3 rd, out float refl);

float marchHeart(vec3 ro, vec3 rd) {
    float s = heartScale();
    // esfera envolvente para no gastar pasos
    vec3 oc = ro - uHeart.xyz;
    float b = dot(oc, rd), c = dot(oc, oc) - 1.3 * s * 1.3 * s;
    float disc = b * b - c;
    if (disc < 0.0) return -1.0;
    float t = max(-b - sqrt(disc), 0.0), tend = -b + sqrt(disc);
    for (int i = 0; i < 64; i++) {
        float d = sdHeart(ro + rd * t);
        if (d < 0.002 * t) return t;
        t += d;
        if (t > tend) break;
    }
    return -1.0;
}

vec3 heartN(vec3 p) {
    const vec2 e = vec2(0.02, -0.02);
    return normalize(e.xyy * sdHeart(p + e.xyy) + e.yyx * sdHeart(p + e.yyx) +
                     e.yxy * sdHeart(p + e.yxy) + e.xxx * sdHeart(p + e.xxx));
}

// ------------------------------------------------------------------ cielo
vec3 sky(vec3 ro, vec3 rd) {
    float h = clamp(rd.y, 0.0, 1.0);
    vec3 c = mix(uFog * 1.3 + uCol2 * 0.04, vec3(0.004, 0.0, 0.012), pow(h, 0.35));
    if (uScene == 1) return uFog * 1.5;
    float st = hash12(floor(rd.xy * 520.0 + rd.z * 91.0));
    c += vec3(0.8, 0.85, 1.0) * step(0.9975, st) * smoothstep(0.05, 0.4, h) * 0.8 * (1.0 - uDecay * 0.8);
    if (rd.y > 0.0) {
        float dist = (260.0 - ro.y) / max(rd.y, 0.02);
        vec2 cp = (ro.xz + rd.xz * dist) * 0.0032 + vec2(uTime * 0.01, uTime * 0.03);
        float cl = fbm(cp);
        float cm = smoothstep(0.42, 0.85, cl) * exp(-dist * 0.0011);
        vec3 cc = uCol2 * 0.14 + uCol1 * 0.04 + vec3(0.8, 0.85, 1.0) * uFlash * 2.2 * cl;
        cc = mix(cc, vec3(0.05), uDecay * 0.7);
        c = mix(c, cc, cm);
    }
    // halo del corazon en el cielo
    if (uScene != 1) {
        vec3 hc = uHeart.xyz - ro;
        float dd = length(hc);
        float cosA = dot(rd, hc / dd);
        float ang = acos(clamp(cosA, -1.0, 1.0)) * dd / heartScale();
        c += uCol1 * (0.3 + 0.9 * uBeat) * exp(-ang * 1.3) * 0.35;
        if (uScene == 0) {
            float th = marchHeart(ro, rd);
            if (th > 0.0) {
                vec3 p = ro + rd * th;
                float dummy;
                vec3 hcol = heartMat(p, heartN(p), rd, dummy);
                c = mix(hcol, uFog * 1.3, 1.0 - exp(-th * 0.0012));
            }
        }
    }
    return c;
}

// ------------------------------------------------------------------ materiales
vec3 heartMat(vec3 p, vec3 n, vec3 rd, out float refl) {
    float s = heartScale();
    vec3 q = (p - uHeart.xyz) / s;
    float fres = pow(1.0 - max(dot(-rd, n), 0.0), 3.0);
    // vidrio rubi con venas de energia internas
    float v1 = abs(fbm(q.xy * 3.0 + vec2(q.z * 2.0, uTime * 0.25)) - 0.5);
    float v2 = abs(fbm(q.zy * 4.5 - vec2(uTime * 0.3, q.x)) - 0.5);
    float vein = smoothstep(0.035, 0.0, v1) + 0.7 * smoothstep(0.03, 0.0, v2);
    float flow = 0.5 + 0.5 * sin(q.y * 9.0 - uTime * 6.0);
    vec3 core = mix(vec3(0.45, 0.0, 0.06), uCol1, 0.35);
    vec3 col = core * (0.25 + 1.6 * uBeat) * (0.6 + 0.4 * n.y);
    col += mix(uCol1, vec3(1.0, 0.9, 0.95), 0.3) * vein * (1.2 + 2.0 * flow + 6.0 * uBeat);
    col += uCol2 * fres * (1.5 + 2.0 * uBeat);
    // "subsurface": brillo interno hacia el centro
    col += vec3(1.0, 0.15, 0.3) * exp(-length(q) * 2.2) * (0.6 + 3.0 * uBeat);
    refl = 0.55;
    return col;
}

vec3 surf(vec3 p, vec3 n, vec3 rd, float mat, out float refl) {
    refl = 0.0;
    vec3 col = vec3(0.0);
    if (mat == 3.0) return heartMat(p, n, rd, refl);
    if (uScene == 0) {
        float live = 1.0 - uDecay;
        if (mat == 1.0) {
            vec2 id = floor((p.xz - n.xz * 0.02) / CELL);
            vec3 base = vec3(0.022, 0.022, 0.035);
            col = base * (uFog * 2.0 * (0.4 + 0.3 * n.y) + uFlash * vec3(0.8, 0.85, 1.0) * 1.5);
            col += base * uCol2 * 3.0 * exp(-p.y * 0.06) * live;
            // luz del corazon (rebote rojo sobre fachadas que miran hacia el)
            vec3 L = normalize(uHeart.xyz - p);
            col += base * uCol1 * max(dot(n, L), 0.0) * (1.5 + 5.0 * uBeat) * 1.2;
            if (abs(n.y) < 0.5) {
                vec2 uv = abs(n.x) > 0.5 ? vec2(p.z, p.y) : vec2(p.x, p.y);
                vec2 g = uv / vec2(1.05, 1.5);
                vec2 wid = floor(g), wf = fract(g);
                float inW = step(0.2, wf.x) * step(wf.x, 0.8) * step(0.22, wf.y) * step(wf.y, 0.78);
                float hw = hash13(vec3(wid, id.x * 13.1 + id.y * 7.7));
                // con uDecay las ventanas se van apagando (y parpadean antes de morir)
                float alive = step(uDecay * 1.05, fract(hw * 53.1));
                float dying = step(abs(fract(hw * 53.1) - uDecay), 0.06) * step(0.0, sin(uTime * 37.0 + hw * 50.0));
                float lit = step(0.58, hw) * step(fract(hw * 91.7), uWin) * max(alive, dying);
                float flick = hw > 0.97 ? 0.4 + 0.6 * step(0.0, sin(uTime * 18.0 * hw)) : 1.0;
                vec3 wc = hw > 0.9 ? uCol1 : (hw > 0.8 ? uCol2 : mix(vec3(1.0, 0.72, 0.42), vec3(0.7, 0.85, 1.0), fract(hw * 13.0)));
                col += wc * inW * lit * flick * (0.9 + 1.6 * uKick * step(0.8, hw)) * (0.6 + 0.4 * fract(hw * 37.0));
                col += vec3(0.015, 0.02, 0.04) * inW * (1.0 - lit);
                // letreros con trazo de electrocardiograma que recorre la fachada
                float bh = hash12(id + 21.0);
                if (bh > 0.4) {
                    float per = 10.0 + floor(bh * 14.0);
                    float yb = mod(p.y, per) - per * 0.5;
                    float u = (abs(n.x) > 0.5 ? p.z : p.x) * 0.09 - uTime * 0.9 * (fract(bh * 3.0) > 0.5 ? 1.0 : -1.0);
                    float tr = smoothstep(0.22, 0.0, abs(yb - 1.6 * ecg(u + bh)));
                    vec3 nc = fract(bh * 7.0) > 0.5 ? uCol1 : uCol2;
                    float on = mix(1.0, step(0.7, fract(bh * 11.0)) * (0.6 + 0.4 * step(0.0, sin(uTime * 23.0 + bh * 9.0))), uDecay);
                    col = mix(col, nc * (2.5 + 4.0 * uKick), tr * on);
                }
                refl = 0.07;
            } else {
                vec2 q = p.xz - (id + 0.5) * CELL;
                vec2 hs = bHalf(id);
                float e1 = min(abs(hs.x - abs(q.x)), abs(hs.y - abs(q.y)));
                float e2 = min(abs(hs.x * 0.62 - abs(q.x)), abs(hs.y * 0.62 - abs(q.y)));
                float rim = smoothstep(0.35, 0.0, min(e1, e2));
                col += mix(uCol1, uCol2, step(0.5, hash12(id + 2.0))) * rim * (1.5 + 2.5 * uKick) * live;
                float blink = step(0.85, fract(uTime * 0.7 + hash12(id) * 5.0));
                col += vec3(1.0, 0.05, 0.05) * blink * smoothstep(0.6, 0.0, length(q)) * 6.0;
            }
        } else {
            float lx = abs(p.x);
            float side = step(10.0, lx);
            col = vec3(0.012, 0.012, 0.02) * (uFog * 6.0 + uFlash * 1.5);
            float lane = (1.0 - side) * (smoothstep(0.14, 0.05, abs(lx - 3.7)) * step(0.45, fract(p.z * 0.08))
                                         + smoothstep(0.1, 0.03, abs(lx - 0.3)));
            col += lane * mix(vec3(1.0, 0.85, 0.6), vec3(1.0, 0.75, 0.2), step(lx, 1.0)) * 0.7 * (0.3 + 0.7 * live);
            // bordillo de neon que dibuja el latido
            float kerb = abs(lx - 10.0 - 0.9 * ecg(p.z * 0.035 - uTime * 1.2));
            col += smoothstep(0.22, 0.0, kerb) * uCol1 * (1.5 + 3.5 * uKick) * (0.25 + 0.75 * live);
            float cz = mod(p.z, CELL);
            col += (1.0 - side) * step(cz, 2.2) * step(0.5, fract(p.x * 0.6)) * vec3(0.5) * 0.35;
            refl = mix(0.9, 0.55, side);
        }
        // onda expansiva del latido
        float ring = exp(-abs(length(p.xz - uPulseC.xz) - uPulseR) * 0.55) * uPulseA;
        col += mix(uCol1, vec3(1.0), 0.35) * ring * 3.0 * exp(-max(p.y - 30.0, 0.0) * 0.04);
    } else if (uScene == 1) {
        vec2 c = tPath(p.z);
        vec2 d = p.xy - c;
        float ang = atan(d.y, d.x);
        if (mat == 4.0) {
            // tejido humedo + circuito de venas
            vec2 uv = vec2(ang * 3.0, p.z * 0.35);
            float cell = fbm(uv * 1.3);
            vec3 tissue = mix(vec3(0.05, 0.004, 0.02), vec3(0.12, 0.01, 0.05), cell);
            float v = abs(fbm(vec2(ang * 2.0, p.z * 0.08) * 2.0) - 0.5);
            float vein = smoothstep(0.03, 0.0, v);
            // pulso que viaja por la arteria desde cada latido
            float wave = exp(-abs(mod(p.z - uPulseC.z - uPulseR, 140.0) - 70.0) * 0.15);
            float trace = smoothstep(0.035, 0.0, abs(fract(ang / 6.2831853 * 6.0) - 0.5 - 0.35 * ecg(p.z * 0.04 - uTime * 1.5)));
            col = tissue * (0.6 + 1.2 * uBeat);
            col += uCol1 * vein * (0.8 + 2.5 * uBeat + 4.0 * wave * uPulseA);
            col += uCol2 * trace * (0.6 + 3.0 * uKick);
            col += mix(uCol1, uCol2, 0.5) * wave * uPulseA * 0.8;
            refl = 0.45;
        } else {
            float rz = mod(p.z, 24.0) - 12.0;
            float seg = smoothstep(0.9, 1.0, sin(ang * 12.0 + uTime * 4.0));
            col = vec3(0.02) + uCol2 * (0.6 + seg * 3.0) * (1.0 + 2.0 * uKick) + uCol1 * smoothstep(0.2, 0.0, abs(abs(rz) - 0.3)) * 2.0;
            refl = 0.2;
        }
    } else {
        if (mat == 6.0) {
            // suelo: obsidiana pulida con hexagonos y ondas del latido
            vec2 h = p.xz / 3.0;
            vec2 r = vec2(1.0, 1.7320508);
            vec2 a = mod(h, r) - r * 0.5, b = mod(h - r * 0.5, r) - r * 0.5;
            vec2 g = dot(a, a) < dot(b, b) ? a : b;
            float edge = smoothstep(0.06, 0.0, 0.5 - max(abs(g.x) * 0.866 + abs(g.y) * 0.5, abs(g.y)));
            float rr = length(p.xz);
            float wave = exp(-abs(rr - uPulseR) * 0.3) * uPulseA;
            col = vec3(0.006, 0.004, 0.01);
            col += mix(uCol2, uCol1, smoothstep(10.0, 70.0, rr)) * edge * (0.25 + 3.0 * wave + 0.6 * uKick * exp(-rr * 0.03));
            col += uCol1 * wave * 0.6;
            refl = 0.85;
        } else {
            float run = smoothstep(0.75, 1.0, fract(p.y * 0.05 - uTime * 0.8));
            float strip = smoothstep(0.15, 0.0, abs(fract(atan(p.z, p.x) * 10.0 / 6.2831853 * 4.0) - 0.5));
            col = vec3(0.015, 0.015, 0.02) + uCol2 * strip * (0.4 + 3.0 * run + 2.5 * uKick);
            col += uCol1 * smoothstep(1.0, 0.0, abs(p.y - 62.0)) * 3.0;
            refl = 0.25;
        }
    }
    return col;
}

// ------------------------------------------------------------------ luces volumetricas
vec2 segRay(vec3 ro, vec3 rd, vec3 a, vec3 b) {
    vec3 ba = b - a, w0 = ro - a;
    float bb = dot(rd, ba), cc = dot(ba, ba), dd = dot(rd, w0), ee = dot(ba, w0);
    float den = max(cc - bb * bb, 1e-5);
    float s = clamp((ee - bb * dd) / den, 0.0, 1.0);
    vec3 q = a + ba * s;
    float t = max(dot(q - ro, rd), 0.0);
    return vec2(length(ro + rd * t - q), t);
}

vec3 cars(vec3 ro, vec3 rd, float tmax) {
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 26; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 1.3)), h2 = hash12(vec2(fi, 7.7)), h3 = hash12(vec2(fi, 4.1));
        float dir = h1 < 0.5 ? 1.0 : -1.0;
        float lx = (h2 - 0.5) * 17.0;
        float ly = 9.0 + h3 * 40.0;
        float sp = 28.0 + h1 * 35.0;
        float z = uCamPos.z - 40.0 + mod(h2 * 400.0 + dir * sp * uTime - uCamPos.z + 40.0, 420.0);
        vec3 a = vec3(lx, ly, z);
        vec3 b = a - vec3(0.0, 0.0, dir * (3.0 + sp * 0.12));
        vec2 r = segRay(ro, rd, a, b);
        if (r.y > tmax) continue;
        vec3 c = dir < 0.0 ? vec3(1.0, 0.95, 0.85) : vec3(1.0, 0.12, 0.08);
        if (fract(h3 * 9.0) > 0.7) c = uCol1;
        acc += c * (0.012 / (r.x * r.x + 0.012) + 0.05 * exp(-r.x * 0.8)) * exp(-r.y * 0.006);
    }
    return acc * (1.0 - uDecay * 0.85);
}

// globulos de energia que fluyen por la arteria
vec3 cells(vec3 ro, vec3 rd, float tmax) {
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 22; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 3.7)), h2 = hash12(vec2(fi, 8.1)), h3 = hash12(vec2(fi, 1.9));
        float z = uCamPos.z - 10.0 + mod(h1 * 260.0 + uTime * (14.0 + 30.0 * h2) - uCamPos.z, 260.0);
        float an = h3 * 6.2831853 + uTime * (0.3 + h2);
        vec3 c3 = vec3(tPath(z) + vec2(cos(an), sin(an)) * (1.5 + 3.3 * h2), z);
        vec3 w = c3 - ro;
        float t = dot(w, rd);
        if (t < 0.0 || t > tmax) continue;
        float d = length(w - rd * t);
        vec3 c = h1 > 0.6 ? uCol2 : mix(uCol1, vec3(1.0, 0.3, 0.4), 0.4);
        acc += c * (0.02 / (d * d + 0.02) + 0.06 * exp(-d * 1.2)) * exp(-t * 0.02);
    }
    return acc * (0.7 + 1.0 * uBeat);
}

// arcos electricos: de los pilares al corazon (escena 2) o alrededor del corazon (escena 0)
vec3 arcs(vec3 ro, vec3 rd, float tmax) {
    if (uArcs < 0.01) return vec3(0.0);
    vec3 acc = vec3(0.0);
    float slot = floor(uTime * 18.0);
    for (int k = 0; k < 5; k++) {
        float fk = float(k);
        vec3 a, b;
        float s = heartScale();
        if (uScene == 2) {
            float ang = (floor(hash12(vec2(fk, uSeed)) * 10.0) + 0.0) * 6.2831853 / 10.0;
            a = vec3(cos(ang) * 70.0, 62.0, sin(ang) * 70.0);
            b = uHeart.xyz + normalize(a - uHeart.xyz) * s * 0.6;
        } else {
            float ang = hash12(vec2(fk, uSeed)) * 6.2831853;
            a = uHeart.xyz + vec3(cos(ang), sin(ang), 0.3) * s * 0.7;
            b = uHeart.xyz + vec3(cos(ang + 1.3), sin(ang + 1.3) - 0.4, -0.2) * s * 2.4;
        }
        vec3 prev = a;
        vec3 dir = b - a;
        vec3 sideA = normalize(cross(dir, vec3(0.0, 1.0, 0.3)));
        vec3 sideB = normalize(cross(dir, sideA));
        float jit = length(dir) * 0.06;
        for (int j = 1; j <= 11; j++) {
            float u = float(j) / 11.0;
            vec3 cur = a + dir * u;
            if (j < 11) cur += (sideA * (hash12(vec2(fk * 13.0 + float(j), slot)) - 0.5) +
                               sideB * (hash12(vec2(fk * 7.0 + float(j), slot + 3.0)) - 0.5)) * jit * 2.0;
            vec2 r = segRay(ro, rd, prev, cur);
            if (r.y < tmax) {
                float w = 0.004 * r.y + 0.03;
                acc += (vec3(0.85, 0.9, 1.0) * exp(-r.x * r.x / (w * w)) * 2.5 + uCol2 * exp(-r.x / (w * 12.0)) * 0.25);
            }
            prev = cur;
        }
    }
    return acc * uArcs;
}

// chispa que corta el gris (verse 2)
vec3 spark(vec3 ro, vec3 rd, float tmax) {
    if (uSpark < 0.01) return vec3(0.0);
    vec3 w = uSparkPos - ro;
    float t = dot(w, rd);
    if (t < 0.0 || t > tmax) return vec3(0.0);
    float d = length(w - rd * t);
    vec3 c = mix(uCol1, vec3(1.0, 0.95, 0.9), 0.5);
    // estela hacia atras
    vec2 r = segRay(ro, rd, uSparkPos, uSparkPos - vec3(0.0, -2.0, 40.0));
    return (c * (0.25 / (d * d + 0.05) + 0.4 * exp(-d * 0.4)) + uCol1 * exp(-r.x * 3.0) * 0.6) * uSpark;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
    vec3 ro = uCamPos;
    vec3 fw = normalize(uCamTgt - ro);
    vec3 rt = normalize(cross(vec3(0.0, 1.0, 0.0), fw));
    vec3 up = cross(fw, rt);
    float cr = cos(uRoll), sr = sin(uRoll);
    vec3 rt2 = rt * cr + up * sr, up2 = up * cr - rt * sr;
    vec3 rd = normalize(fw * uFov + uv.x * rt2 + uv.y * up2);

    float dens = uScene == 0 ? 0.0030 + 0.004 * uDecay : (uScene == 1 ? 0.022 : 0.006);
    vec3 fogc = uFog + uFlash * vec3(0.25, 0.27, 0.35);
    float t;
    float mat = march(ro, rd, uScene == 1 ? 110 : 150, t);
    vec3 col;
    if (mat < 0.5) {
        col = sky(ro, rd);
        t = MAXT;
    } else {
        vec3 p = ro + rd * t;
        vec3 n = calcN(p);
        float refl;
        col = surf(p, n, rd, mat, refl);
        // luz clave: el corazon ilumina la escena (con sombra suave en la camara del corazon)
        if (uScene == 2 && mat != 3.0) {
            vec3 Lv = uHeart.xyz - p;
            float Ld = length(Lv);
            vec3 L = Lv / Ld;
            float sh = softShadow(p + n * 0.05, L, Ld - heartScale());
            col += vec3(0.04) * uCol1 * max(dot(n, L), 0.0) * sh * (3.0 + 10.0 * uBeat) * 600.0 / (Ld * Ld + 300.0);
        }
        float ao = calcAO(p, n);
        col *= 0.35 + 0.65 * ao;
        if (refl > 0.01) {
            vec3 nn = n;
            if (mat == 2.0 || mat == 4.0) nn = normalize(n + vec3((noise(p.xz * 2.2 + uTime * 0.6) - 0.5) * 0.1, 0.0,
                                                          (noise(p.zx * 2.2 - uTime * 0.5) - 0.5) * 0.1));
            vec3 rr = reflect(rd, nn);
            float t2;
            float m2 = march(p + nn * 0.06, rr, 64, t2);
            vec3 rc;
            if (m2 < 0.5) rc = sky(p, rr);
            else {
                vec3 p2 = p + rr * t2;
                float dummy;
                rc = surf(p2, calcN(p2), rr, m2, dummy);
                rc = mix(rc, fogc, 1.0 - exp(-t2 * dens));
            }
            float fres = refl * (0.3 + 0.7 * pow(1.0 - max(dot(-rd, n), 0.0), 2.0));
            col += rc * fres;
        }
        float hf = uScene == 0 ? 1.0 + 1.5 * exp(-p.y * 0.08) : 1.0;
        col = mix(col, fogc, 1.0 - exp(-t * dens * hf));
    }
    if (uScene == 0) col += cars(ro, rd, t) + spark(ro, rd, t);
    if (uScene == 1) col += cells(ro, rd, t);
    col += arcs(ro, rd, t);
    // alfa = profundidad (para la profundidad de campo del postproceso)
    fragColor = vec4(col, t);
}
