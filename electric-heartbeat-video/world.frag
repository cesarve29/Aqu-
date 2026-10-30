#version 330
// Mundo 3D de "Electric Heartbeat" (raymarching con look de render tipo Cycles:
// oclusion ambiental, reflejos con Fresnel, sombras suaves, cromo y emision).
// uScene 0 = avenida de neon con portales de luz y laseres que reaccionan al bombo
//            (uDecay apaga la ciudad en la segunda estrofa),
// uScene 1 = tunel fractal de cromo que se pliega con cada golpe,
// uScene 2 = reactor: nucleo de metal liquido, anillos giroscopicos, laseres y arcos.
uniform vec2 uRes;
uniform float uTime;
uniform int uScene;
uniform vec3 uCamPos;
uniform vec3 uCamTgt;
uniform float uRoll;
uniform float uFov;
uniform float uBass;
uniform float uKick;
uniform float uBeat;      // envolvente del golpe 0..1
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
uniform vec4 uCore;       // reactor: xyz = centro, w = radio
uniform vec3 uRingRot;    // angulos de los anillos giroscopicos
uniform float uFold;      // pliegue del fractal (cambia con cada golpe)
uniform float uLasers;
uniform float uArcs;
uniform float uSeed;
out vec4 fragColor;

#define MAXT 520.0
const float CELL = 11.0;
const float GATE = 44.0;

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
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
float sdTorus(vec3 p, float R, float r) { return length(vec2(length(p.xz) - R, p.y)) - r; }
float smin(float a, float b, float k) { float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }

// ------------------------------------------------------------------ ciudad
float bHeight(vec2 id) {
    float h = hash12(id * 1.31 + 7.0);
    h = 12.0 + h * h * 75.0;
    return h * (1.0 + 0.35 * clamp(abs(id.x + 0.5) - 1.5, 0.0, 4.0));
}
vec2 bHalf(vec2 id) { float r = hash12(id + 3.1); return vec2(3.9 + 0.9 * r, 3.9 + 0.9 * fract(r * 7.3)); }

// portal: anillo octogonal de cromo sobre la avenida, uno cada GATE metros
float sdGate(vec3 p) {
    float gz = mod(p.z, GATE) - GATE * 0.5;
    vec2 q = abs(p.xy - vec2(0.0, 10.5));
    float oct = max(max(q.x, q.y), (q.x + q.y) * 0.7071) - 9.6;
    return length(vec2(oct, gz)) - 0.55;
}

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
    float dP = sdGate(p);
    float real = min(min(dB, dG), dP);
    float mat = dB < dG ? 1.0 : 2.0;
    if (dP <= real) mat = 3.0;
    float march = min(min(min(dB, max(bound, 0.25)), dG), dP);
    return vec3(real, march, mat);
}

// ------------------------------------------------------------------ tunel fractal
vec2 tPath(float z) { return vec2(7.0 * sin(z * 0.021) + 3.0 * sin(z * 0.047), 2.5 * sin(z * 0.017)); }
float gTrap;
vec3 mapFrac(vec3 p) {
    vec3 q = p;
    q.xy -= tPath(p.z);
    float r = length(q.xy);
    float tun = 3.6 + 0.4 * sin(p.z * 0.12) - r;
    q.xy *= rot(p.z * 0.02);
    q.z = mod(q.z, 14.0) - 7.0;
    // pliegue caleidoscopico (KIFS): estructuras de cromo que se repliegan con cada golpe
    float s = 1.0;
    float trap = 1e5;
    for (int i = 0; i < 4; i++) {
        q = abs(q) - vec3(3.6, 3.6, 2.6) / s;
        if (q.x < q.y) q.xy = q.yx;
        if (q.x < q.z) q.xz = q.zx;
        q.xy *= rot(uFold);
        q.yz *= rot(uFold * 0.6 + 0.3);
        trap = min(trap, abs(q.y));
        s *= 1.5;
    }
    gTrap = trap;
    float d = (sdBox(q, vec3(1.5, 0.45, 1.5)) - 0.04) / s;
    // pared exterior solida para que nunca se vea el vacio
    float dW = 9.5 - r;
    float mat = d < dW ? 4.0 : 5.0;
    d = min(d, dW);
    d = max(d, tun);
    return vec3(d * 0.8, d * 0.8, mat);
}

// ------------------------------------------------------------------ reactor
vec3 ringP(vec3 p, int i) {
    vec3 q = p - uCore.xyz;
    float a = uRingRot[i];
    if (i == 0) { q.xy *= rot(a); q.yz *= rot(a * 0.5); }
    else if (i == 1) { q.yz *= rot(a); q.xz *= rot(a * 0.7); }
    else { q.xz *= rot(a); q.xy *= rot(1.0 + a * 0.4); }
    return q;
}
float sdCore(vec3 p) {
    vec3 q = p - uCore.xyz;
    float R = uCore.w;
    float d = length(q) - R * 0.62;
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        vec3 c = vec3(sin(uTime * (0.7 + 0.13 * fi) + fi * 2.1), sin(uTime * (0.9 + 0.11 * fi) + fi * 1.3),
                      cos(uTime * (0.8 + 0.09 * fi) + fi * 0.7)) * R * (0.42 + 0.25 * uBass);
        d = smin(d, length(q - c) - R * 0.36, R * 0.35);
    }
    // ondas del metal liquido que se disparan con cada golpe
    d += sin(q.x * 0.9 + uTime * 2.0) * sin(q.y * 0.9 - uTime * 1.7) * sin(q.z * 0.9 + uTime) * (0.25 + 1.4 * uKick);
    return d * 0.7;
}
vec3 mapReactor(vec3 p) {
    float dF = p.y;
    float ang = atan(p.z, p.x);
    float sector = 6.2831853 / 10.0;
    float a = mod(ang + sector * 0.5, sector) - sector * 0.5;
    float r = length(p.xz);
    vec2 pp = vec2(cos(a), sin(a)) * r - vec2(72.0, 0.0);
    float dP = sdBox(vec3(pp.x, p.y - 30.0, pp.y), vec3(2.2, 30.0, 2.2)) - 0.3;
    float dRing = length(vec2(r - 72.0, p.y - 62.0)) - 1.6;
    float dC = sdCore(p);
    float R = uCore.w;
    float dG = min(min(sdTorus(ringP(p, 0), R * 1.55, 0.45), sdTorus(ringP(p, 1), R * 1.9, 0.45)),
                   sdTorus(ringP(p, 2), R * 2.25, 0.45));
    float real = min(min(dF, dP), min(dRing, min(dC, dG)));
    float mat = 6.0;
    if (dP <= real || dRing <= real) mat = 7.0;
    if (dG <= real) mat = 8.0;
    if (dC <= real) mat = 9.0;
    return vec3(real, real, mat);
}

vec3 map(vec3 p) {
    if (uScene == 0) return mapCity(p);
    if (uScene == 1) return mapFrac(p);
    return mapReactor(p);
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

float calcAO(vec3 p, vec3 n) {
    float occ = 0.0, sca = 1.0;
    for (int i = 0; i < 5; i++) {
        float h = 0.05 + 0.9 * float(i) / 4.0;
        occ += (h - map(p + n * h).x) * sca;
        sca *= 0.72;
    }
    return clamp(1.0 - 1.4 * occ, 0.0, 1.0);
}

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

// ------------------------------------------------------------------ cielo
vec3 sky(vec3 ro, vec3 rd) {
    float h = clamp(rd.y, 0.0, 1.0);
    vec3 c = mix(uFog * 1.3 + uCol2 * 0.04, vec3(0.004, 0.0, 0.012), pow(h, 0.35));
    if (uScene == 1) return uFog * 1.5 + uCol1 * uBeat * 0.3;
    float st = hash12(floor(rd.xy * 520.0 + rd.z * 91.0));
    c += vec3(0.8, 0.85, 1.0) * step(0.9975, st) * smoothstep(0.05, 0.4, h) * 0.8 * (1.0 - uDecay * 0.8);
    if (rd.y > 0.0) {
        float dist = (260.0 - ro.y) / max(rd.y, 0.02);
        vec2 cp = (ro.xz + rd.xz * dist) * 0.0032 + vec2(uTime * 0.01, uTime * 0.03);
        float cl = fbm(cp);
        float cm = smoothstep(0.42, 0.85, cl) * exp(-dist * 0.0011);
        vec3 cc = uCol2 * 0.14 + uCol1 * (0.05 + 0.25 * uBeat) + vec3(0.8, 0.85, 1.0) * uFlash * 2.2 * cl;
        cc = mix(cc, vec3(0.05), uDecay * 0.7);
        c = mix(c, cc, cm);
    }
    // aurora de color que respira con los golpes sobre el reactor
    if (uScene == 2) c += mix(uCol1, uCol2, 0.5 + 0.5 * sin(rd.x * 3.0 + uTime * 0.4)) * smoothstep(0.0, 0.5, h) * (0.04 + 0.12 * uBeat);
    return c;
}

// ------------------------------------------------------------------ materiales
vec3 surf(vec3 p, vec3 n, vec3 rd, float mat, out float refl) {
    refl = 0.0;
    vec3 col = vec3(0.0);
    float fres = pow(1.0 - max(dot(-rd, n), 0.0), 3.0);
    if (uScene == 0) {
        float live = 1.0 - uDecay;
        if (mat == 1.0) {
            vec2 id = floor((p.xz - n.xz * 0.02) / CELL);
            vec3 base = vec3(0.022, 0.022, 0.035);
            col = base * (uFog * 2.0 * (0.4 + 0.3 * n.y) + uFlash * vec3(0.8, 0.85, 1.0) * 1.5);
            col += base * uCol2 * 3.0 * exp(-p.y * 0.06) * live;
            if (abs(n.y) < 0.5) {
                vec2 uv = abs(n.x) > 0.5 ? vec2(p.z, p.y) : vec2(p.x, p.y);
                vec2 g = uv / vec2(1.05, 1.5);
                vec2 wid = floor(g), wf = fract(g);
                float inW = step(0.2, wf.x) * step(wf.x, 0.8) * step(0.22, wf.y) * step(wf.y, 0.78);
                float hw = hash13(vec3(wid, id.x * 13.1 + id.y * 7.7));
                float alive = step(uDecay * 1.05, fract(hw * 53.1));
                float dying = step(abs(fract(hw * 53.1) - uDecay), 0.06) * step(0.0, sin(uTime * 37.0 + hw * 50.0));
                float lit = step(0.58, hw) * step(fract(hw * 91.7), uWin) * max(alive, dying);
                float flick = hw > 0.97 ? 0.4 + 0.6 * step(0.0, sin(uTime * 18.0 * hw)) : 1.0;
                // en cada golpe un grupo distinto de ventanas destella con el color principal
                float hit = step(0.82, fract(hw * 7.7 + uSeed * 0.618)) * uKick;
                vec3 wc = hw > 0.9 ? uCol1 : (hw > 0.8 ? uCol2 : mix(vec3(1.0, 0.72, 0.42), vec3(0.7, 0.85, 1.0), fract(hw * 13.0)));
                wc = mix(wc, uCol1 * 2.5, hit);
                col += wc * inW * lit * flick * (0.9 + 1.6 * uKick * step(0.8, hw)) * (0.6 + 0.4 * fract(hw * 37.0));
                col += vec3(0.015, 0.02, 0.04) * inW * (1.0 - lit);
                // bandas de neon que suben por las fachadas con el ritmo
                float bh = hash12(id + 21.0);
                if (bh > 0.4) {
                    float per = 8.0 + floor(bh * 12.0);
                    float yb = mod(p.y - uTime * (2.0 + 10.0 * step(0.75, bh)), per);
                    float band = smoothstep(0.3, 0.05, abs(yb - per * 0.5));
                    vec3 nc = fract(bh * 7.0 + floor(uSeed * 0.25) * 0.5) > 0.5 ? uCol1 : uCol2;
                    float on = mix(1.0, step(0.7, fract(bh * 11.0)) * (0.6 + 0.4 * step(0.0, sin(uTime * 23.0 + bh * 9.0))), uDecay);
                    col = mix(col, nc * (2.5 + 5.0 * uKick), band * on);
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
        } else if (mat == 2.0) {
            float lx = abs(p.x);
            float side = step(10.0, lx);
            col = vec3(0.012, 0.012, 0.02) * (uFog * 6.0 + uFlash * 1.5);
            float lane = (1.0 - side) * (smoothstep(0.14, 0.05, abs(lx - 3.7)) * step(0.45, fract(p.z * 0.08))
                                         + smoothstep(0.1, 0.03, abs(lx - 0.3)));
            col += lane * mix(vec3(1.0, 0.85, 0.6), vec3(1.0, 0.75, 0.2), step(lx, 1.0)) * 0.7 * (0.3 + 0.7 * live);
            col += smoothstep(0.25, 0.0, abs(lx - 10.0)) * uCol1 * (1.5 + 3.5 * uKick) * (0.25 + 0.75 * live);
            // luz de los portales sobre el asfalto
            float gz = mod(p.z, GATE) - GATE * 0.5;
            col += uCol2 * exp(-abs(gz) * 0.5) * (1.0 - side) * (0.4 + 2.5 * uKick) * (0.3 + 0.7 * live);
            float cz = mod(p.z, CELL);
            col += (1.0 - side) * step(cz, 2.2) * step(0.5, fract(p.x * 0.6)) * vec3(0.5) * 0.35;
            refl = mix(0.9, 0.55, side);
        } else {
            // portal: cromo con tubo de neon que se enciende con los golpes
            float gi = floor(p.z / GATE);
            float pick = hash12(vec2(gi, uSeed));
            vec3 nc = pick > 0.5 ? uCol1 : uCol2;
            vec2 q = p.xy - vec2(0.0, 10.5);
            float inner = smoothstep(0.0, -0.5, dot(n.xy, normalize(q)));
            float chase = smoothstep(0.7, 1.0, sin(atan(q.y, q.x) * 4.0 - uTime * 8.0));
            col = vec3(0.03) + nc * (0.8 + 7.0 * uKick + 2.0 * chase) * (0.35 + 0.65 * inner) * (0.2 + 0.8 * live);
            col += vec3(0.7, 0.8, 1.0) * fres * 0.6;
            refl = 0.6;
        }
        // onda expansiva del golpe
        float ring = exp(-abs(length(p.xz - uPulseC.xz) - uPulseR) * 0.55) * uPulseA;
        col += mix(uCol1, vec3(1.0), 0.35) * ring * 3.0 * exp(-max(p.y - 30.0, 0.0) * 0.04);
    } else if (uScene == 1) {
        // cromo oscuro + filos emisivos segun la trampa orbital del fractal
        map(p);
        float crack = smoothstep(0.05, 0.0, gTrap);
        float wave = exp(-abs(mod(p.z - uPulseC.z - uPulseR, 120.0) - 60.0) * 0.12);
        vec3 nc = mix(uCol1, uCol2, 0.5 + 0.5 * sin(p.z * 0.05 + uTime * 0.5));
        if (mat == 4.0) {
            col = vec3(0.02, 0.018, 0.025) * (0.5 + 0.5 * n.y);
            col += nc * crack * (0.4 + 3.0 * uKick + 4.0 * wave * uPulseA);
            col += uCol2 * fres * 0.4;
            refl = 0.7;
        } else {
            // pared exterior: paneles oscuros con lineas de neon que corren hacia la camara
            vec2 c = vec2(atan(p.y - tPath(p.z).y, p.x - tPath(p.z).x) * 3.0, p.z * 0.25 + uTime * 2.0);
            vec2 g = abs(fract(c) - 0.5);
            float line = smoothstep(0.03, 0.0, 0.5 - max(g.x, g.y));
            col = vec3(0.008) + uCol1 * line * (0.3 + 2.0 * uKick + 3.0 * wave * uPulseA);
            refl = 0.3;
        }
    } else {
        if (mat == 6.0) {
            vec2 h = p.xz / 3.0;
            vec2 r = vec2(1.0, 1.7320508);
            vec2 a = mod(h, r) - r * 0.5, b = mod(h - r * 0.5, r) - r * 0.5;
            vec2 g = dot(a, a) < dot(b, b) ? a : b;
            float edge = smoothstep(0.06, 0.0, 0.5 - max(abs(g.x) * 0.866 + abs(g.y) * 0.5, abs(g.y)));
            float rr = length(p.xz - uCore.xz);
            float wave = exp(-abs(rr - uPulseR) * 0.3) * uPulseA;
            col = vec3(0.006, 0.004, 0.01);
            col += mix(uCol2, uCol1, smoothstep(10.0, 70.0, rr)) * edge * (0.25 + 3.0 * wave + 0.6 * uKick * exp(-rr * 0.03));
            col += uCol1 * wave * 0.6;
            refl = 0.85;
        } else if (mat == 7.0) {
            float run = smoothstep(0.75, 1.0, fract(p.y * 0.05 - uTime * 0.8));
            float strip = smoothstep(0.15, 0.0, abs(fract(atan(p.z, p.x) * 10.0 / 6.2831853 * 4.0) - 0.5));
            col = vec3(0.015, 0.015, 0.02) + uCol2 * strip * (0.4 + 3.0 * run + 2.5 * uKick);
            col += uCol1 * smoothstep(1.0, 0.0, abs(p.y - 62.0)) * 3.0;
            refl = 0.25;
        } else if (mat == 8.0) {
            // anillos: cromo con franja de neon que corre a lo largo
            vec3 q = p - uCore.xyz;
            float run = smoothstep(0.6, 1.0, sin(dot(q, vec3(0.3, 0.2, 0.25)) * 2.0 - uTime * 6.0));
            col = vec3(0.05) + mix(uCol2, uCol1, run) * (1.0 + 3.0 * run + 5.0 * uKick);
            refl = 0.5;
        } else {
            // nucleo: metal liquido pulido (refleja todo) con energia en los valles
            vec3 q = p - uCore.xyz;
            float valley = smoothstep(0.35, -0.2, sin(q.x * 0.9 + uTime * 2.0) * sin(q.y * 0.9 - uTime * 1.7) * sin(q.z * 0.9 + uTime));
            col = vec3(0.02) + mix(uCol1, vec3(1.0, 0.9, 1.0), 0.2) * pow(valley, 3.0) * (0.3 + 4.0 * uBeat);
            col += uCol2 * fres * 1.6 + uCol1 * fres * 2.0 * uBeat;
            refl = 0.9;
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
    for (int i = 0; i < 22; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 1.3)), h2 = hash12(vec2(fi, 7.7)), h3 = hash12(vec2(fi, 4.1));
        float dir = h1 < 0.5 ? 1.0 : -1.0;
        float lx = (h2 - 0.5) * 17.0;
        float ly = 22.0 + h3 * 35.0;
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

// laseres: desde las azoteas barriendo el cielo (ciudad) o desde los pilares al nucleo (reactor)
vec3 lasers(vec3 ro, vec3 rd, float tmax) {
    if (uLasers < 0.01) return vec3(0.0);
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 10; i++) {
        float fi = float(i);
        vec3 a, b;
        vec3 c = mod(fi, 2.0) < 1.0 ? uCol1 : uCol2;
        if (uScene == 0) {
            float side = mod(fi, 2.0) < 1.0 ? -1.0 : 1.0;
            float zb = uCamPos.z + 30.0 + mod(fi * 37.0 - uCamPos.z, 360.0);
            a = vec3(side * 16.0, 70.0, zb);
            float ph = fi * 1.3 + uSeed * 0.9;
            vec3 dir = normalize(vec3(-side * 0.5 + 0.6 * sin(uTime * 1.3 + ph), 1.0, 0.7 * sin(uTime * 0.9 + ph * 2.0)));
            b = a + dir * 400.0;
        } else {
            if (hash12(vec2(fi, uSeed)) > 0.55) continue;
            float ang = fi * 6.2831853 / 10.0;
            a = vec3(cos(ang) * 70.0, 62.0, sin(ang) * 70.0);
            b = uCore.xyz;
        }
        vec2 r = segRay(ro, rd, a, b);
        if (r.y > tmax) continue;
        float w = 0.02 + r.y * 0.0012;
        acc += c * (exp(-r.x * r.x / (w * w)) * 2.0 + exp(-r.x / (w * 25.0)) * 0.08) * exp(-r.y * 0.004);
    }
    return acc * uLasers;
}

// arcos electricos entre el nucleo y los anillos
vec3 arcs(vec3 ro, vec3 rd, float tmax) {
    if (uArcs < 0.01) return vec3(0.0);
    vec3 acc = vec3(0.0);
    float slot = floor(uTime * 18.0);
    for (int k = 0; k < 4; k++) {
        float fk = float(k);
        float ang = hash12(vec2(fk, uSeed + slot * 0.01)) * 6.2831853;
        float el = (hash12(vec2(fk + 4.0, uSeed)) - 0.5) * 2.0;
        vec3 dirv = normalize(vec3(cos(ang), el, sin(ang)));
        vec3 a = uCore.xyz + dirv * uCore.w * 0.6;
        vec3 b = uCore.xyz + dirv * uCore.w * 2.25;
        vec3 prev = a;
        vec3 dir = b - a;
        vec3 sideA = normalize(cross(dir, vec3(0.0, 1.0, 0.3)));
        vec3 sideB = normalize(cross(dir, sideA));
        float jit = length(dir) * 0.08;
        for (int j = 1; j <= 9; j++) {
            float u = float(j) / 9.0;
            vec3 cur = a + dir * u;
            if (j < 9) cur += (sideA * (hash12(vec2(fk * 13.0 + float(j), slot)) - 0.5) +
                               sideB * (hash12(vec2(fk * 7.0 + float(j), slot + 3.0)) - 0.5)) * jit * 2.0;
            vec2 r = segRay(ro, rd, prev, cur);
            if (r.y < tmax) {
                float w = 0.003 * r.y + 0.03;
                acc += vec3(0.85, 0.9, 1.0) * exp(-r.x * r.x / (w * w)) * 2.5 + uCol2 * exp(-r.x / (w * 12.0)) * 0.25;
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
    vec2 r = segRay(ro, rd, uSparkPos, uSparkPos - vec3(0.0, -2.0, 40.0));
    return (c * (0.25 / (d * d + 0.05) + 0.4 * exp(-d * 0.4)) + uCol1 * exp(-r.x * 3.0) * 0.6) * uSpark;
}

// motas de luz que vuelan por el tunel
vec3 motes(vec3 ro, vec3 rd, float tmax) {
    vec3 acc = vec3(0.0);
    for (int i = 0; i < 18; i++) {
        float fi = float(i);
        float h1 = hash12(vec2(fi, 3.7)), h2 = hash12(vec2(fi, 8.1)), h3 = hash12(vec2(fi, 1.9));
        float z = uCamPos.z - 10.0 + mod(h1 * 200.0 - uTime * (20.0 + 30.0 * h2) - uCamPos.z, 200.0);
        float an = h3 * 6.2831853 + uTime * (0.3 + h2);
        vec3 c3 = vec3(tPath(z) + vec2(cos(an), sin(an)) * (0.8 + 1.6 * h2), z);
        vec3 w = c3 - ro;
        float t = dot(w, rd);
        if (t < 0.0 || t > tmax) continue;
        float d = length(w - rd * t);
        vec3 c = h1 > 0.5 ? uCol2 : uCol1;
        acc += c * (0.01 / (d * d + 0.01) + 0.04 * exp(-d * 1.5)) * exp(-t * 0.03);
    }
    return acc * (0.6 + 1.2 * uBeat);
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

    float dens = uScene == 0 ? 0.0030 + 0.004 * uDecay : (uScene == 1 ? 0.03 : 0.006);
    vec3 fogc = uFog + uFlash * vec3(0.25, 0.27, 0.35);
    float t;
    float mat = march(ro, rd, uScene == 1 ? 120 : 150, t);
    vec3 col;
    if (mat < 0.5) {
        col = sky(ro, rd);
        t = MAXT;
    } else {
        vec3 p = ro + rd * t;
        vec3 n = calcN(p);
        float refl;
        col = surf(p, n, rd, mat, refl);
        // luz clave del reactor con sombra suave
        if (uScene == 2 && mat < 8.0) {
            vec3 Lv = uCore.xyz - p;
            float Ld = length(Lv);
            vec3 L = Lv / Ld;
            float sh = softShadow(p + n * 0.05, L, Ld - uCore.w);
            col += 0.04 * mix(uCol1, uCol2, 0.3) * max(dot(n, L), 0.0) * sh * (3.0 + 10.0 * uBeat) * 600.0 / (Ld * Ld + 300.0);
        }
        float ao = calcAO(p, n);
        col *= 0.35 + 0.65 * ao;
        if (refl > 0.01) {
            vec3 nn = n;
            if (mat == 2.0) nn = normalize(n + vec3((noise(p.xz * 2.2 + uTime * 0.6) - 0.5) * 0.1, 0.0,
                                                   (noise(p.zx * 2.2 - uTime * 0.5) - 0.5) * 0.1));
            vec3 rr = reflect(rd, nn);
            float t2;
            float m2 = march(p + nn * 0.06, rr, uScene == 1 ? 40 : 64, t2);
            vec3 rc;
            float tl = m2 > 0.5 ? t2 : MAXT;
            if (m2 < 0.5) rc = sky(p, rr);
            else {
                vec3 p2 = p + rr * t2;
                float dummy;
                rc = surf(p2, calcN(p2), rr, m2, dummy);
                rc = mix(rc, fogc, 1.0 - exp(-t2 * dens));
            }
            if (uScene == 0) rc += lasers(p, rr, tl) * 0.5;
            if (uScene == 2) rc += (lasers(p, rr, tl) + arcs(p, rr, tl)) * 0.5;
            float fr = refl * (0.3 + 0.7 * pow(1.0 - max(dot(-rd, n), 0.0), 2.0));
            vec3 tintR = vec3(1.0);
            if (mat == 9.0) { fr = refl; tintR = mix(vec3(1.0), uCol2 * 0.6 + 0.5, 0.3); }
            col += rc * fr * tintR;
        }
        float hf = uScene == 0 ? 1.0 + 1.5 * exp(-p.y * 0.08) : 1.0;
        col = mix(col, fogc, 1.0 - exp(-t * dens * hf));
    }
    if (uScene == 0) col += cars(ro, rd, t) + spark(ro, rd, t) + lasers(ro, rd, t);
    if (uScene == 1) col += motes(ro, rd, t);
    if (uScene == 2) col += lasers(ro, rd, t) + arcs(ro, rd, t);
    fragColor = vec4(col, t);
}
