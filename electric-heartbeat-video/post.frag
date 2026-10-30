#version 330
// Postproceso tipo "compositor de Blender": profundidad de campo con bokeh, bloom en
// varias capas, destellos anamorficos, aberracion cromatica, letras con halo neon,
// glitch, flash, grano de pelicula y vineta.
uniform sampler2D uWorld;   // rgb = color, a = profundidad
uniform sampler2D uText;
uniform vec2 uRes;
uniform float uTime;
uniform float uKick;
uniform float uBeat;
uniform float uChroma;
uniform float uGlitch;
uniform float uFlashScr;
uniform float uFade;
uniform float uGlow;
uniform float uFocus;
uniform float uAperture;
uniform vec3 uTint;
in vec2 vUV;
out vec4 fragColor;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec3 aces(vec3 x) { return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }

float coc(float d) { return clamp(abs(1.0 / max(d, 0.1) - 1.0 / uFocus) * uAperture, 0.0, 1.0); }

vec3 worldAt(vec2 uv, vec2 off) {
    vec3 c;
    c.r = texture(uWorld, uv + off).r;
    c.g = texture(uWorld, uv).g;
    c.b = texture(uWorld, uv - off).b;
    return c;
}

void main() {
    vec2 uv = vUV;
    float slot = floor(uTime * 24.0);
    float row = floor(uv.y * 34.0);
    float gk = step(1.0 - uGlitch * 0.55, hash12(vec2(row, slot)));
    uv.x += gk * (hash12(vec2(row * 3.1, slot)) - 0.5) * 0.14 * uGlitch;
    vec2 tuv = vec2(uv.x, 1.0 - uv.y);
    vec2 cc = uv - 0.5;
    // aberracion cromatica radial (mas fuerte en los bordes, como una lente real)
    vec2 off = cc * (uChroma * 0.006 + 0.0015) + vec2(gk * 0.012, 0.0);

    // profundidad de campo: disco de bokeh de 12 muestras con radio segun el circulo de confusion
    float c0 = coc(texture(uWorld, uv).a);
    vec3 w = worldAt(uv, off);
    if (c0 > 0.02) {
        vec3 acc = w;
        float wsum = 1.0;
        float rad = c0 * 0.011;
        for (int i = 0; i < 12; i++) {
            float a = float(i) * 2.39996 + 0.5;
            float r = sqrt((float(i) + 0.5) / 12.0);
            vec2 o = vec2(cos(a), sin(a)) * r * rad * vec2(uRes.y / uRes.x, 1.0);
            vec4 s = texture(uWorld, uv + o);
            float cs = coc(s.a);
            float wt = smoothstep(r - 0.15, r, cs / max(c0, 1e-3) + 0.3) + 0.05;
            // los puntos brillantes pesan mas: bokeh circular
            wt *= 1.0 + 2.0 * smoothstep(1.0, 4.0, dot(s.rgb, vec3(0.333)));
            acc += s.rgb * wt;
            wsum += wt;
        }
        w = mix(w, acc / wsum, smoothstep(0.02, 0.2, c0));
    }

    vec3 bloom = textureLod(uWorld, uv, 2.5).rgb * 0.14 + textureLod(uWorld, uv, 4.0).rgb * 0.18 +
                 textureLod(uWorld, uv, 5.5).rgb * 0.2 + textureLod(uWorld, uv, 7.0).rgb * 0.18;
    // destello anamorfico horizontal de las luces mas intensas
    vec3 streak = vec3(0.0);
    for (int i = -6; i <= 6; i++) {
        vec3 s = textureLod(uWorld, uv + vec2(float(i) * 0.028, 0.0), 3.5).rgb;
        streak += max(s - 1.4, 0.0) * exp(-abs(float(i)) * 0.35);
    }
    vec3 col = w + bloom * (0.85 + 0.6 * uKick + 0.4 * uBeat) + streak * vec3(0.35, 0.55, 1.0) * 0.06;

    // las letras oscurecen ligeramente el mundo detras (legibilidad)
    float sh = textureLod(uText, tuv, 5.5).a;
    col *= 1.0 - sh * 0.5;

    col *= uTint;
    col = aces(col * 0.95);

    // halo neon de las letras
    vec4 tg = textureLod(uText, tuv, 3.0) * 0.55 + textureLod(uText, tuv, 4.5) * 0.8 + textureLod(uText, tuv, 6.0) * 0.7;
    col += tg.rgb * uGlow * (0.45 + 0.4 * uKick + 0.25 * uBeat);

    vec2 o2 = vec2(off.x * 1.6 + uChroma * 0.002, 0.0);
    vec4 tR = texture(uText, tuv + o2);
    vec4 tG = texture(uText, tuv);
    vec4 tB = texture(uText, tuv - o2);
    col.r = mix(col.r, tR.r, tR.a);
    col.g = mix(col.g, tG.g, tG.a);
    col.b = mix(col.b, tB.b, tB.a);

    col += uFlashScr;
    // vineta optica + grano de pelicula
    col *= clamp(1.1 - dot(cc, cc) * 1.35, 0.0, 1.0);
    float grain = hash12(vUV * uRes + fract(uTime * 7.13) * 311.0) - 0.5;
    col += grain * (0.035 - 0.02 * dot(col, vec3(0.333)));
    col *= uFade;
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
