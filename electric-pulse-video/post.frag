#version 330
// Postproceso: bloom, letras con halo neon, aberracion cromatica, glitch, lluvia, flash y vineta.
uniform sampler2D uWorld;
uniform sampler2D uText;
uniform vec2 uRes;
uniform float uTime;
uniform float uKick;
uniform float uChroma;
uniform float uGlitch;
uniform float uFlashScr;
uniform float uFade;
uniform float uRain;
uniform float uGlow;
in vec2 vUV;
out vec4 fragColor;

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec3 aces(vec3 x) { return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }

float rainLayer(vec2 uv, float sc, float sp, float seed) {
    vec2 p = vec2(uv.x * sc + uv.y * sc * 0.1, uv.y);
    float c = floor(p.x);
    float h = hash12(vec2(c, seed));
    float y = fract(p.y * (0.5 + h * 0.5) + uTime * sp * (0.8 + h * 0.5) + h * 7.0);
    float streak = smoothstep(0.0, 0.01, y) * smoothstep(0.08, 0.0, y);
    float line = smoothstep(0.12, 0.0, abs(fract(p.x) - 0.5));
    return line * streak * step(0.6, h);
}

void main() {
    vec2 uv = vUV;
    float slot = floor(uTime * 24.0);
    float row = floor(uv.y * 34.0);
    float gk = step(1.0 - uGlitch * 0.55, hash12(vec2(row, slot)));
    uv.x += gk * (hash12(vec2(row * 3.1, slot)) - 0.5) * 0.14 * uGlitch;
    vec2 tuv = vec2(uv.x, 1.0 - uv.y);
    vec2 off = vec2(uChroma * 0.004 + gk * 0.012, 0.0);

    vec3 w;
    w.r = texture(uWorld, uv + off).r;
    w.g = texture(uWorld, uv).g;
    w.b = texture(uWorld, uv - off).b;
    vec3 bloom = textureLod(uWorld, uv, 2.5).rgb * 0.16 + textureLod(uWorld, uv, 4.5).rgb * 0.20 +
                 textureLod(uWorld, uv, 6.5).rgb * 0.22;
    vec3 col = w + bloom * (0.8 + 0.5 * uKick);

    // las letras oscurecen ligeramente el mundo detras (legibilidad)
    float sh = textureLod(uText, tuv, 5.5).a;
    col *= 1.0 - sh * 0.5;

    float r = rainLayer(uv, 150.0, 1.7, 1.0) * 0.5 + rainLayer(uv, 70.0, 1.2, 2.0) * 0.35;
    col += vec3(0.55, 0.65, 0.9) * r * uRain * 0.35;

    col = aces(col * 0.95);

    // halo neon de las letras (mipmaps del texto)
    vec4 tg = textureLod(uText, tuv, 3.0) * 0.55 + textureLod(uText, tuv, 4.5) * 0.8 + textureLod(uText, tuv, 6.0) * 0.7;
    col += tg.rgb * uGlow * (0.45 + 0.45 * uKick);

    vec2 o2 = off * 1.6;
    vec4 tR = texture(uText, tuv + vec2(o2.x, 0.0));
    vec4 tG = texture(uText, tuv);
    vec4 tB = texture(uText, tuv - vec2(o2.x, 0.0));
    col.r = mix(col.r, tR.r, tR.a);
    col.g = mix(col.g, tG.g, tG.a);
    col.b = mix(col.b, tB.b, tB.a);

    col += uFlashScr;
    vec2 q = vUV - 0.5;
    col *= clamp(1.12 - dot(q, q) * 1.5, 0.0, 1.0);
    col += (hash12(vUV * uRes + fract(uTime) * 100.0) - 0.5) * 0.025;
    col *= uFade;
    fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
