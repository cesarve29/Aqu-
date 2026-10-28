#version 330
// Mundo 3D del video (raymarching). uScene 0 = megaciudad bajo la tormenta,
// uScene 1 = laberinto digital con laseres (segunda estrofa).
uniform vec2 uRes;
uniform float uTime;
uniform int uScene;
uniform vec3 uCamPos;
uniform vec3 uCamTgt;
uniform float uRoll;
uniform float uFov;
uniform float uBass;
uniform float uKick;
uniform float uFlash;
uniform vec3 uCol1;
uniform vec3 uCol2;
uniform vec3 uFog;
uniform float uPulseR;
uniform float uPulseA;
uniform vec3 uPulseC;
uniform float uWin;
uniform float uStrobe;
uniform float uLaser;
uniform float uCars;
uniform sampler2D uSkyFx;
out vec4 fragColor;

#define MAXT 430.0
const float CELL = 11.0;
const float HC = 14.0;

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

// ------------------------------------------------------------------ ciudad
float bHeight(vec2 id) {
    float h = hash12(id * 1.31 + 7.0);
    h = 12.0 + h * h * 75.0;
    return h * (1.0 + 0.35 * clamp(abs(id.x + 0.5) - 1.5, 0.0, 4.0));
}
vec2 bHalf(vec2 id) { float r = hash12(id + 3.1); return vec2(3.9 + 0.9 * r, 3.9 + 0.9 * fract(r * 7.3)); }
float towerZ() { return uCamPos.z + 270.0; }

// x = distancia real, y = distancia segura para avanzar, z = material
vec3 mapCity(vec3 p) {
    vec2 id = floor(p.xz / CELL);
    vec2 q = p.xz - (id + 0.5) * CELL;
    float bound = min(CELL * 0.5 - abs(q.x), CELL * 0.5 - abs(q.y)) + 0.05;
    float dB = 1e5;
    if (abs(id.x + 0.5) > 1.0) {  // la avenida (id.x = -1, 0) queda libre
        float h = bHeight(id);
        vec2 hs = bHalf(id);
        dB = sdBox(vec3(q.x, p.y - h * 0.5, q.y), vec3(hs.x, h * 0.5, hs.y));
        float r = hash12(id + 11.7);
        if (r > 0.45) {
            float h2 = h * (0.2 + 0.35 * fract(r * 13.1));
            dB = min(dB, sdBox(vec3(q.x, p.y - h - h2 * 0.5, q.y), vec3(hs.x * 0.62, h2 * 0.5, hs.y * 0.62)));
            if (r > 0.8) dB = min(dB, sdBox(vec3(q.x, p.y - h - h2 - 6.0, q.y), vec3(0.15, 6.0, 0.15)));  // antena
        }
    }
    float dG = p.y;
    vec3 tp = p - vec3(0.0, 0.0, towerZ());
    float dT = max(length(tp.xz) - 7.0 + 1.5 * step(150.0, tp.y), abs(tp.y - 85.0) - 85.0);
    float real = min(min(dB, dG), dT);
    float mat = dB < dG ? 1.0 : 2.0;
    if (dT < min(dB, dG)) mat = 3.0;
    float march = min(min(min(dB, max(bound, 0.25)), dG), dT);
    return vec3(real, march, mat);
}

// ------------------------------------------------------------------ laberinto
vec3 mapHall(vec3 p) {
    vec2 id = floor((p.xz + HC * 0.5) / HC);
    vec2 q = p.xz - id * HC;
    float bound = min(HC * 0.5 - abs(q.x), HC * 0.5 - abs(q.y)) + 0.05;
    float dP = 1e5, dW = 1e5;
    if (id.x != 0.0) dP = sdBox(vec3(q.x, p.y - 8.0, q.y), vec3(1.1, 8.0, 1.1));
    float hw = hash12(id + 5.3), hz = hash12(id + 9.1);
    if (hw > 0.3) dW = min(dW, sdBox(vec3(q.x - 6.75, p.y - 3.6, q.y), vec3(0.12, 3.6, 5.6)));
    if (hz > 0.45 && id.x != 0.0) dW = min(dW, sdBox(vec3(q.x, p.y - 3.6, q.y - 6.75), vec3(5.6, 3.6, 0.12)));
    float dF = p.y, dC = 16.0 - p.y;
    float real = min(min(dP, dW), min(dF, dC));
    float mat = 2.0;
    if (dW <= real) mat = 4.0;
    if (dP <= real) mat = 5.0;
    if (dC <= real) mat = 6.0;
    float march = min(min(min(dP, dW), max(bound, 0.25)), min(dF, dC));
    return vec3(real, march, mat);
}

vec3 map(vec3 p) { return uScene == 0 ? mapCity(p) : mapHall(p); }

float march(vec3 ro, vec3 rd, int steps, out float t) {
    t = 0.05;
    for (int i = 0; i < steps; i++) {
        vec3 m = map(ro + rd * t);
        if (m.x < 0.0015 * t + 0.004) return m.z;
        t += m.y * 0.92;
        if (t > MAXT) break;
    }
    return 0.0;
}

vec3 calcN(vec3 p) {
    const vec2 e = vec2(0.01, -0.01);
    return normalize(e.xyy * map(p + e.xyy).x + e.yyx * map(p + e.yyx).x +
                     e.yxy * map(p + e.yxy).x + e.xxx * map(p + e.xxx).x);
}

// ------------------------------------------------------------------ cielo
vec3 sky(vec3 ro, vec3 rd, float primary) {
    float h = clamp(rd.y, 0.0, 1.0);
    vec3 c = mix(uFog * 1.3 + uCol2 * 0.04, vec3(0.004, 0.0, 0.012), pow(h, 0.35));
    if (uScene == 1) return uFog * 1.5;
    float st = hash12(floor(rd.xy * 520.0 + rd.z * 91.0));
    c += vec3(0.8, 0.85, 1.0) * step(0.9975, st) * smoothstep(0.05, 0.4, h) * 0.8;
    if (rd.y > 0.0) {
        float dist = (260.0 - ro.y) / max(rd.y, 0.02);
        vec2 cp = (ro.xz + rd.xz * dist) * 0.0032 + vec2(uTime * 0.01, uTime * 0.03);
        float cl = fbm(cp);
        float cm = smoothstep(0.42, 0.85, cl) * exp(-dist * 0.0011);
        vec3 cc = uCol2 * 0.14 + vec3(1.0, 0.45, 0.25) * 0.05 + vec3(0.8, 0.85, 1.0) * uFlash * 2.2 * cl;
        c = mix(c, cc, cm);
    }
    vec2 suv = gl_FragCoord.xy / uRes;
    c += texture(uSkyFx, vec2(suv.x, 1.0 - suv.y)).rgb * 3.0 * primary;
    return c;
}

// ------------------------------------------------------------------ materiales
vec3 surf(vec3 p, vec3 n, vec3 rd, float mat, out float refl) {
    refl = 0.0;
    vec3 col = vec3(0.0);
    if (uScene == 0) {
        if (mat == 1.0) {
            vec2 id = floor((p.xz - n.xz * 0.02) / CELL);
            vec3 base = vec3(0.022, 0.022, 0.035);
            col = base * (uFog * 2.0 * (0.4 + 0.3 * n.y) + uFlash * vec3(0.8, 0.85, 1.0) * 1.5);
            col += base * uCol2 * 3.0 * exp(-p.y * 0.06);
            if (abs(n.y) < 0.5) {
                vec2 uv = abs(n.x) > 0.5 ? vec2(p.z, p.y) : vec2(p.x, p.y);
                vec2 g = uv / vec2(1.05, 1.5);
                vec2 wid = floor(g), wf = fract(g);
                float inW = step(0.2, wf.x) * step(wf.x, 0.8) * step(0.22, wf.y) * step(wf.y, 0.78);
                float hw = hash13(vec3(wid, id.x * 13.1 + id.y * 7.7));
                float lit = step(0.58, hw) * step(fract(hw * 91.7), uWin);
                float flick = hw > 0.97 ? 0.4 + 0.6 * step(0.0, sin(uTime * 18.0 * hw)) : 1.0;
                vec3 wc = hw > 0.9 ? uCol1 : (hw > 0.8 ? uCol2 : mix(vec3(1.0, 0.72, 0.42), vec3(0.7, 0.85, 1.0), fract(hw * 13.0)));
                col += wc * inW * lit * flick * (0.9 + 1.6 * uKick * step(0.8, hw)) * (0.6 + 0.4 * fract(hw * 37.0));
                col += vec3(0.015, 0.02, 0.04) * inW * (1.0 - lit);
                float bh = hash12(id + 21.0);
                if (bh > 0.45) {
                    float per = 8.0 + floor(bh * 12.0);
                    float yb = mod(p.y + uTime * 4.0 * step(0.8, bh), per);
                    float band = smoothstep(0.3, 0.05, abs(yb - per * 0.5));
                    vec3 nc = fract(bh * 7.0) > 0.5 ? uCol1 : uCol2;
                    col = mix(col, nc * (2.5 + 4.0 * uKick), band);
                }
                refl = 0.06;
            } else {
                vec2 q = p.xz - (id + 0.5) * CELL;
                vec2 hs = bHalf(id);
                float e1 = min(abs(hs.x - abs(q.x)), abs(hs.y - abs(q.y)));
                float e2 = min(abs(hs.x * 0.62 - abs(q.x)), abs(hs.y * 0.62 - abs(q.y)));
                float rim = smoothstep(0.35, 0.0, min(e1, e2));
                col += mix(uCol1, uCol2, step(0.5, hash12(id + 2.0))) * rim * (1.5 + 2.5 * uKick);
                // luz roja intermitente de las azoteas
                float blink = step(0.85, fract(uTime * 0.7 + hash12(id) * 5.0));
                col += vec3(1.0, 0.05, 0.05) * blink * smoothstep(0.6, 0.0, length(q)) * 6.0;
            }
        } else if (mat == 2.0) {
            float lx = abs(p.x);
            float side = step(10.0, lx);
            col = vec3(0.012, 0.012, 0.02) * (uFog * 6.0 + uFlash * 1.5);
            float lane = (1.0 - side) * (smoothstep(0.14, 0.05, abs(lx - 3.7)) * step(0.45, fract(p.z * 0.08))
                                         + smoothstep(0.1, 0.03, abs(lx - 0.3)));
            col += lane * mix(vec3(1.0, 0.85, 0.6), vec3(1.0, 0.75, 0.2), step(lx, 1.0)) * 0.7;
            col += smoothstep(0.25, 0.0, abs(lx - 10.0)) * uCol1 * (1.5 + 2.5 * uKick);
            // paso de cebra en cada cruce
            float cz = mod(p.z, CELL);
            col += (1.0 - side) * step(cz, 2.2) * step(0.5, fract(p.x * 0.6)) * vec3(0.5) * 0.35;
            refl = mix(0.9, 0.55, side);
        } else {
            vec3 tp = p - vec3(0.0, 0.0, towerZ());
            float a = atan(tp.z, tp.x);
            float stripes = smoothstep(0.8, 1.0, sin(a * 14.0));
            float rings = smoothstep(0.88, 1.0, sin(tp.y * 0.5 - uTime * 7.0));
            col = vec3(0.02) + uCol1 * (stripes * 1.6 + rings * (2.0 + 7.0 * uKick)) + uCol2 * step(150.0, tp.y) * 3.0;
            refl = 0.1;
        }
        // onda expansiva del bombo
        float ring = exp(-abs(length(p.xz - uPulseC.xz) - uPulseR) * 0.55) * uPulseA;
        col += mix(uCol1, vec3(1.0), 0.35) * ring * 3.0 * exp(-max(p.y - 30.0, 0.0) * 0.04);
    } else {
        vec2 id = floor((p.xz + HC * 0.5) / HC);
        vec2 q = p.xz - id * HC;
        if (mat == 2.0) {
            vec2 g = abs(fract(p.xz / 2.0) - 0.5);
            float line = smoothstep(0.46, 0.5, max(g.x, g.y));
            float wave = 0.5 + 0.5 * sin(length(p.xz - vec2(0.0, uCamPos.z + 25.0)) * 0.35 - uTime * 9.0);
            float tileOn = step(0.93, hash12(floor(p.xz / 2.0) + floor(uTime * 4.0)));
            col = vec3(0.004, 0.004, 0.008);
            col += mix(uCol1, uCol2, wave) * line * (0.35 + 2.2 * wave * uKick);
            col += uCol2 * tileOn * (1.0 - line) * 0.6 * (0.5 + uKick);
            refl = 0.85;
        } else if (mat == 4.0) {
            vec2 uv = abs(n.x) > 0.5 ? vec2(p.z, p.y) : vec2(p.x, p.y);
            vec2 c = floor(uv / 0.7), f = fract(uv / 0.7);
            float hh = hash12(c + id * 7.0);
            float tr = hh > 0.5 ? smoothstep(0.08, 0.0, abs(f.y - 0.5)) : smoothstep(0.08, 0.0, abs(f.x - 0.5));
            tr *= step(0.25, fract(hh * 17.0));
            float flow = smoothstep(0.85, 1.0, fract(uv.x * 0.08 + uv.y * 0.05 - uTime * 0.9 + hh * 0.3));
            col = vec3(0.01, 0.008, 0.015) + uCol2 * tr * (0.25 + 3.0 * flow) + uCol1 * tr * flow * uKick * 2.0;
            col += uCol1 * smoothstep(0.12, 0.0, abs(p.y - 7.1)) * 3.0;
            refl = 0.15;
        } else if (mat == 5.0) {
            float u = abs(n.x) > 0.5 ? q.y : q.x;
            float strip = smoothstep(0.12, 0.0, abs(abs(u) - 0.85));
            float run = smoothstep(0.7, 1.0, fract(p.y * 0.12 + uTime * 1.5));
            col = vec3(0.01) + uCol1 * strip * (0.8 + 3.0 * run + 3.0 * uKick);
            refl = 0.1;
        } else {
            vec2 g = abs(fract(p.xz / 4.0) - 0.5);
            float panel = step(max(g.x, g.y), 0.3);
            col = vec3(0.005) + vec3(0.6, 0.65, 0.8) * panel * (0.05 + uStrobe * 1.5);
        }
        col += vec3(0.9, 0.9, 1.0) * uStrobe * 0.08;
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
    for (int i = 0; i < 30; i++) {
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
    return acc * uCars;
}

vec3 beam(vec3 ro, vec3 rd, float tmax) {
    vec2 c = vec2(0.0, towerZ());
    vec2 o = ro.xz, d = rd.xz;
    float t = dot(c - o, d) / max(dot(d, d), 1e-5);
    if (t < 0.0 || t > tmax) return vec3(0.0);
    float y = ro.y + rd.y * t;
    float dist = length(o + d * t - c);
    float k = smoothstep(165.0, 180.0, y);
    return mix(uCol1, vec3(1.0), 0.4) * k * (0.9 + 2.5 * uKick) * (exp(-dist * 0.35) * 1.2 + exp(-dist * 0.05) * 0.12);
}

vec3 lasers(vec3 ro, vec3 rd, float tmax) {
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float side = mod(fi, 2.0) < 1.0 ? -1.0 : 1.0;
        float zb = uCamPos.z - 12.0 + mod(fi * 11.0 - uCamPos.z + 12.0, 132.0);
        vec3 a = vec3(side * 5.0, 15.6, zb);
        float ph = fi * 1.7;
        vec3 dir = normalize(vec3(-side * 0.35 + 0.65 * sin(uTime * 1.4 + ph), -1.0, 0.8 * sin(uTime * 0.95 + ph * 2.0)));
        vec3 b = a + dir * (15.6 / -dir.y);
        vec2 r = segRay(ro, rd, a, b);
        if (r.y > tmax) continue;
        vec3 c = mod(fi, 3.0) < 1.0 ? uCol2 : uCol1;
        acc += c * (exp(-r.x * r.x * 60.0) * 1.6 + exp(-r.x * 2.5) * 0.12) * exp(-r.y * 0.012);
    }
    return acc * uLaser;
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

    float dens = uScene == 0 ? 0.0030 : 0.018;
    vec3 fogc = uFog + uFlash * vec3(0.25, 0.27, 0.35);
    float t;
    float mat = march(ro, rd, 150, t);
    vec3 col;
    if (mat < 0.5) {
        col = sky(ro, rd, 1.0);
        t = MAXT;
    } else {
        vec3 p = ro + rd * t;
        vec3 n = calcN(p);
        float refl;
        col = surf(p, n, rd, mat, refl);
        if (refl > 0.01) {
            vec3 nn = n;
            if (mat == 2.0 && uScene == 0) nn = normalize(vec3((noise(p.xz * 2.2 + uTime * 0.6) - 0.5) * 0.1, 1.0,
                                                (noise(p.zx * 2.2 - uTime * 0.5) - 0.5) * 0.1));
            vec3 rr = reflect(rd, nn);
            float t2;
            float m2 = march(p + nn * 0.05, rr, 64, t2);
            vec3 rc;
            if (m2 < 0.5) rc = sky(p, rr, 0.0);
            else {
                vec3 p2 = p + rr * t2;
                float dummy;
                rc = surf(p2, calcN(p2), rr, m2, dummy);
                rc = mix(rc, fogc, 1.0 - exp(-t2 * dens));
            }
            float fres = refl * (0.35 + 0.65 * pow(1.0 - max(dot(-rd, n), 0.0), 2.0));
            col += rc * fres;
        }
        float hf = uScene == 0 ? 1.0 + 1.5 * exp(-p.y * 0.08) : 1.0;
        col = mix(col, fogc, 1.0 - exp(-t * dens * hf));
    }
    if (uScene == 0) col += cars(ro, rd, t) + beam(ro, rd, t);
    else col += lasers(ro, rd, t);
    fragColor = vec4(col, 1.0);
}
