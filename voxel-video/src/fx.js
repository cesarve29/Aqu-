// Shaders: cielo, nubes de bloques, agua, portales, particulas y post-procesado.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { rng } from './util.js';

const NOISE_GLSL = `
float h21(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
float h31(vec3 p){ p=fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float vn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(h21(i),h21(i+vec2(1,0)),f.x), mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x), f.y); }
float fbm2(vec2 p){ float v=0.0,a=0.5; for(int i=0;i<5;i++){ v+=a*vn(p); p*=2.03; a*=0.5; } return v; }
`;

// ---------------------------------------------------------------- cielo
export function makeSky(mode) {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: {
      sunDir: { value: new THREE.Vector3(0, 1, 0) }, uTime: { value: 0 },
      top: { value: new THREE.Color() }, hor: { value: new THREE.Color() }, glow: { value: new THREE.Color() },
      night: { value: 0 }, mode: { value: mode === 'end' ? 1 : 0 },
    },
    vertexShader: `varying vec3 vDir; void main(){ vDir = position; vec4 p = projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_Position = p.xyww; }`,
    fragmentShader: NOISE_GLSL + `
      varying vec3 vDir; uniform vec3 sunDir, top, hor, glow; uniform float night, uTime, mode;
      void main(){
        vec3 d = normalize(vDir);
        if (mode > 0.5) {
          // cielo del Fin: vacio violeta con nebulosas
          float n = fbm2(d.xz/(abs(d.y)+0.6)*3.0 + uTime*0.01);
          vec3 c = mix(vec3(0.012,0.006,0.02), vec3(0.09,0.03,0.13), smoothstep(0.35,0.85,n));
          c += vec3(0.18,0.06,0.25)*pow(fbm2(d.xy*2.0+7.0),3.0);
          vec3 sd = floor(d*220.0);
          float st = step(0.9965, h31(sd));
          c += st*vec3(0.8,0.7,1.0)*(0.5+0.5*sin(uTime*2.0+h31(sd+3.0)*30.0));
          gl_FragColor = vec4(c,1.0);
          return;
        }
        float h = d.y;
        vec3 c = mix(hor, top, pow(clamp(h,0.0,1.0),0.55));
        c = mix(c, hor*0.55, smoothstep(0.0,-0.35,h));
        float sd = max(dot(d, sunDir), 0.0);
        c += glow * pow(sd, 6.0) * 0.8 * (1.0-night);
        c += glow * pow(sd, 2.0) * 0.25 * smoothstep(0.3,-0.05,sunDir.y) * (1.0-night);
        // sol y luna cuadrados
        vec3 up = abs(sunDir.y)>0.99 ? vec3(1,0,0) : vec3(0,1,0);
        vec3 sx = normalize(cross(up, sunDir)); vec3 sy = cross(sunDir, sx);
        float dd = dot(d, sunDir);
        if (dd > 0.0) { vec2 q = vec2(dot(d,sx), dot(d,sy))/dd; float m = max(abs(q.x),abs(q.y));
          c = mix(c, vec3(1.0,0.97,0.82)*4.0, smoothstep(0.075,0.068,m)); c += vec3(1.0,0.8,0.5)*0.3*smoothstep(0.2,0.07,m)*(1.0-night); }
        if (dd < 0.0) { vec2 q = vec2(dot(d,sx), dot(d,sy))/(-dd); float m = max(abs(q.x),abs(q.y));
          float moon = smoothstep(0.06,0.054,m); float cr = step(0.62, h21(floor(q*40.0)));
          c = mix(c, vec3(0.85,0.88,1.0)*(1.6-cr*0.4), moon*night); }
        // estrellas
        vec3 s3 = floor(d*260.0);
        float st = step(0.997, h31(s3)) * smoothstep(0.0,0.2,h);
        c += st * night * vec3(0.9,0.95,1.0) * (0.6+0.4*sin(uTime*3.0+h31(s3+1.0)*40.0));
        gl_FragColor = vec4(c,1.0);
      }`,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(500, 48, 24), mat);
  m.frustumCulled = false;
  m.renderOrder = -10;
  return m;
}

// ---------------------------------------------------------------- nubes
export function makeClouds() {
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.DoubleSide,
    uniforms: { uTime: { value: 0 }, light: { value: new THREE.Color(1, 1, 1) }, camPos: { value: new THREE.Vector3() } },
    vertexShader: `varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW=w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: NOISE_GLSL + `
      varying vec3 vW; uniform float uTime; uniform vec3 light, camPos;
      void main(){
        vec2 p = vW.xz + vec2(uTime*1.2, 0.0);
        vec2 cell = floor(p/12.0);
        float n = vn(cell*0.35) * 0.65 + vn(cell*0.9+11.0)*0.35;
        if (n < 0.56) discard;
        vec2 f = fract(p/12.0);
        float edge = 1.0 - 0.12*step(0.92, max(f.x,f.y));
        float dist = length(vW.xz - camPos.xz);
        float a = 0.82 * smoothstep(420.0, 160.0, dist);
        gl_FragColor = vec4(light*edge, a);
      }`,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1400, 1400), mat);
  m.rotation.x = -Math.PI / 2;
  m.position.y = 64;
  m.renderOrder = 5;
  return m;
}

// ---------------------------------------------------------------- agua
export function makeWater(size, level) {
  const mat = new THREE.ShaderMaterial({
    transparent: true, fog: true,
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uTime: { value: 0 }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, top: { value: new THREE.Color() },
      hor: { value: new THREE.Color() }, sunCol: { value: new THREE.Color() }, night: { value: 0 },
    }]),
    vertexShader: `#include <common>
      #include <fog_pars_vertex>
      varying vec3 vW; uniform float uTime;
      void main(){ vec3 p = position; vec4 w = modelMatrix*vec4(p,1.0);
        w.y += sin(w.x*0.6+uTime*1.3)*0.03 + cos(w.z*0.7+uTime*1.1)*0.03;
        vW = w.xyz; vec4 mvPosition = viewMatrix*w; gl_Position = projectionMatrix*mvPosition;
        #include <fog_vertex>
      }`,
    fragmentShader: NOISE_GLSL + `#include <common>
      #include <fog_pars_fragment>
      varying vec3 vW; uniform float uTime, night; uniform vec3 sunDir, top, hor, sunCol;
      float wav(vec2 p){ vec2 q = p*0.35 + vec2(uTime*0.25, uTime*0.18);
        return vn(q) + 0.5*vn(q*2.03+3.1) + 0.35*vn(p*1.3 - uTime*0.3) + 0.18*vn(p*2.7 + uTime*0.4); }
      void main(){
        vec2 p = vW.xz;
        float e = 0.15;
        float w0 = wav(p), wx = wav(p + vec2(e, 0.0)), wz = wav(p + vec2(0.0, e));
        vec3 n = normalize(vec3((w0-wx)*2.2, 1.0, (w0-wz)*2.2));
        vec3 v = normalize(cameraPosition - vW);
        float fres = 0.04 + 0.96*pow(1.0 - max(dot(n,v),0.0), 5.0);
        vec3 r = reflect(-v, n);
        vec3 sky = mix(hor, top, pow(clamp(r.y,0.0,1.0),0.5));
        vec3 deep = mix(vec3(0.02,0.12,0.25), vec3(0.01,0.02,0.06), night);
        // pixelado sutil estilo bloque
        vec2 tile = floor(p*4.0)/4.0; float px = vn(tile*3.0 + uTime*0.5)*0.06;
        vec3 c = mix(deep + px, sky, clamp(fres*1.25,0.0,1.0));
        float spec = pow(max(dot(r, sunDir),0.0), 180.0);
        c += sunCol * spec * 3.0;
        gl_FragColor = vec4(c, mix(0.72, 0.96, fres));
        #include <fog_fragment>
      }`,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(size, size, 64, 64), mat);
  m.rotation.x = -Math.PI / 2;
  m.position.set(size / 2 - 200, level, size / 2 - 200);
  return m;
}

// ---------------------------------------------------------------- portales
export function portalMaterial(kind) {
  return new THREE.ShaderMaterial({
    transparent: true, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { uTime: { value: 0 }, open: { value: 0 }, kind: { value: kind === 'end' ? 1 : 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
    fragmentShader: NOISE_GLSL + `varying vec2 vUv; uniform float uTime, open, kind;
      void main(){
        vec2 p = vUv - 0.5;
        if (kind > 0.5) {
          float r = length(p)*2.0; if (r > 1.0) discard;
          vec2 q = floor(vUv*48.0);
          float st = step(0.93, h21(q + floor(uTime*3.0)));
          vec3 c = vec3(0.02,0.03,0.06) + st*vec3(0.4,0.9,0.85) + vec3(0.1,0.25,0.3)*fbm2(vUv*6.0+uTime*0.2);
          gl_FragColor = vec4(c*2.0*open, open);
          return;
        }
        if (vUv.y > open) discard;
        float a = atan(p.y, p.x), r = length(p);
        float sw = fbm2(vec2(a*2.0 + r*8.0 - uTime*2.0, r*6.0 - uTime*1.5));
        vec2 pix = floor(vUv*vec2(32.0,48.0))/vec2(32.0,48.0);
        float n = fbm2(pix*7.0 + vec2(0.0, -uTime*0.8)) + 0.5*sw;
        vec3 c = mix(vec3(0.25,0.0,0.6), vec3(0.85,0.35,1.0), smoothstep(0.4,1.1,n));
        c *= 1.8;
        gl_FragColor = vec4(c, 0.85);
      }`,
  });
}

// ---------------------------------------------------------------- particulas
// Cada emisor es una funcion pura del tiempo.
export class Particles {
  constructor(max = 12000, additive = false) {
    this.max = max;
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(max * 3);
    this.col = new Float32Array(max * 4);
    this.size = new Float32Array(max);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    g.setAttribute('color', new THREE.BufferAttribute(this.col, 4));
    g.setAttribute('size', new THREE.BufferAttribute(this.size, 1));
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      uniforms: { scale: { value: 1080 * 0.6 } },
      vertexShader: `attribute float size; attribute vec4 color; varying vec4 vC; uniform float scale;
        void main(){ vC = color; vec4 mv = modelViewMatrix*vec4(position,1.0); gl_PointSize = size*scale/(-mv.z); gl_Position = projectionMatrix*mv; }`,
      fragmentShader: `varying vec4 vC; void main(){ gl_FragColor = vC; }`,
    });
    this.points = new THREE.Points(g, mat);
    this.points.frustumCulled = false;
    this.emitters = [];
    this.n = 0;
  }
  // o: {t0, n, rate?, t1?, pos:[x,y,z], spread:[sx,sy,sz], vel:[vx,vy,vz], vs:[..], life, grav, size, colors, fade}
  add(o) {
    const r = rng(o.seed ?? Math.floor(o.t0 * 1000 + this.emitters.length * 7));
    const ps = [];
    const n = o.rate ? Math.floor((o.t1 - o.t0) * o.rate) : o.n;
    const sp = o.spread || [0, 0, 0], vs = o.vs || [1, 1, 1], v0 = o.vel || [0, 0, 0];
    for (let i = 0; i < n; i++) {
      const ts = o.rate ? o.t0 + i / o.rate : o.t0 + r() * (o.jitter || 0);
      const c = o.colors[Math.floor(r() * o.colors.length)];
      ps.push({
        ts, life: o.life * (0.6 + r() * 0.8),
        p: [o.pos[0] + (r() - 0.5) * 2 * sp[0], o.pos[1] + (r() - 0.5) * 2 * sp[1], o.pos[2] + (r() - 0.5) * 2 * sp[2]],
        v: [v0[0] + (r() - 0.5) * 2 * vs[0], v0[1] + (r() - 0.5) * 2 * vs[1], v0[2] + (r() - 0.5) * 2 * vs[2]],
        c, s: o.size * (0.6 + r() * 0.8),
      });
    }
    this.emitters.push({ t0: o.t0, t1: (o.t1 ?? o.t0 + (o.jitter || 0)) + o.life * 1.4, ps, grav: o.grav ?? -9, drag: o.drag ?? 0, fade: o.fade ?? 1, grow: o.grow ?? 0, posFn: o.posFn });
  }
  update(t) {
    let k = 0;
    for (const e of this.emitters) {
      if (t < e.t0 || t > e.t1) continue;
      const off = e.posFn ? e.posFn(t) : null;
      for (const q of e.ps) {
        const a = t - q.ts;
        if (a < 0 || a > q.life || k >= this.max) continue;
        const dr = e.drag ? (1 - Math.exp(-e.drag * a)) / e.drag : a;
        this.pos[k * 3] = q.p[0] + q.v[0] * dr + (off ? off.x : 0);
        this.pos[k * 3 + 1] = q.p[1] + q.v[1] * dr + 0.5 * e.grav * a * a + (off ? off.y : 0);
        this.pos[k * 3 + 2] = q.p[2] + q.v[2] * dr + (off ? off.z : 0);
        const u = a / q.life;
        const al = e.fade ? 1 - u * u : 1;
        this.col[k * 4] = q.c[0]; this.col[k * 4 + 1] = q.c[1]; this.col[k * 4 + 2] = q.c[2]; this.col[k * 4 + 3] = al;
        this.size[k] = q.s * (1 + e.grow * u);
        k++;
      }
    }
    for (let i = k; i < this.n; i++) this.size[i] = 0;
    this.n = k;
    const g = this.points.geometry;
    g.attributes.position.needsUpdate = true;
    g.attributes.color.needsUpdate = true;
    g.attributes.size.needsUpdate = true;
    g.setDrawRange(0, Math.max(k, 1));
  }
}

// ---------------------------------------------------------------- post-procesado
const GradeShader = {
  uniforms: {
    tDiffuse: { value: null }, uTime: { value: 0 }, fade: { value: 0 }, flash: { value: 0 }, flashCol: { value: new THREE.Color(1, 1, 1) },
    warp: { value: 0 }, hurt: { value: 0 }, sat: { value: 1.1 }, vig: { value: 0.35 }, tint: { value: new THREE.Color(1, 1, 1) },
    aspect: { value: 16 / 9 },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
  fragmentShader: NOISE_GLSL + `varying vec2 vUv; uniform sampler2D tDiffuse; uniform float uTime, fade, flash, warp, hurt, sat, vig, aspect; uniform vec3 flashCol, tint;
    void main(){
      vec2 uv = vUv; vec2 c = uv - 0.5; c.x *= aspect;
      float r = length(c);
      if (warp > 0.0) {
        float ang = warp*warp*6.0*(1.0 - smoothstep(0.0,0.9,r));
        float s = sin(ang), co = cos(ang);
        vec2 q = mat2(co,-s,s,co)*c; q *= 1.0 - warp*0.35*(1.0-r);
        q.x /= aspect; uv = q + 0.5;
      }
      float ca = 0.0012 + hurt*0.004 + warp*0.01;
      vec3 col;
      col.r = texture2D(tDiffuse, uv + (uv-0.5)*ca).r;
      col.g = texture2D(tDiffuse, uv).g;
      col.b = texture2D(tDiffuse, uv - (uv-0.5)*ca).b;
      float l = dot(col, vec3(0.299,0.587,0.114));
      col = mix(vec3(l), col, sat) * tint;
      col = mix(col, col*vec3(1.05,0.98,0.9), 0.3);
      col *= 1.0 - vig*smoothstep(0.45, 1.05, r);
      col = mix(col, vec3(0.8,0.0,0.0), hurt*0.45*smoothstep(0.35,1.0,r));
      if (warp > 0.0) col = mix(col, mix(vec3(0.45,0.1,0.8), vec3(0.9,0.6,1.0), fbm2(uv*8.0+uTime)), warp*warp*0.65);
      col = mix(col, flashCol, flash);
      col *= 1.0 - fade;
      gl_FragColor = vec4(col, 1.0);
    }`,
};

export function makePost(renderer, W, H) {
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType }));
  composer.setPixelRatio(1);
  composer.setSize(W, H);
  const rp = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
  composer.addPass(rp);
  const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.6, 0.5, 0.9);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const grade = new ShaderPass(GradeShader);
  composer.addPass(grade);
  return { composer, rp, bloom, grade };
}
