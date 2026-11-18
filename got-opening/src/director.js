// Director: monta los sets, aplica el plan de tomas y la capa de creditos.
import * as THREE from 'three';
import { loadFonts } from './kit.js';
import { Astro } from './astro.js';
import { drawCredits } from './credits.js';
import { shotAt } from './shots.js';

function skyMaterial() {
  return new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: {
      uTop: { value: new THREE.Color(0x0a0f18) }, uHor: { value: new THREE.Color(0x2a3240) },
      uGlowDir: { value: new THREE.Vector3(0, 0, -1) }, uGlow: { value: new THREE.Color(0, 0, 0) }, uGlowPow: { value: 8 },
      uCloud: { value: 0.6 }, uCloudCol: { value: new THREE.Color(0x5a6676) }, uTime: { value: 0 }, uMoon: { value: new THREE.Vector3(0, 0, 0) },
    },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_Position.z = gl_Position.w; }`,
    fragmentShader: `
      uniform vec3 uTop, uHor, uGlow, uCloudCol, uGlowDir, uMoon; uniform float uGlowPow, uCloud, uTime; varying vec3 vDir;
      float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,37.719))) * 43758.5453); }
      float n3(vec3 p){ vec3 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
        return mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x),mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),
                   mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x),mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y),f.z); }
      float fbm(vec3 p){ float a=0.5,s=0.0; for(int i=0;i<5;i++){ s+=a*n3(p); p*=2.07; a*=0.5;} return s; }
      void main(){
        vec3 d = normalize(vDir);
        float y = clamp(d.y*0.5+0.5, 0.0, 1.0);
        vec3 c = mix(uHor, uTop, smoothstep(0.45, 0.95, y));
        float cl = fbm(d*3.0 + vec3(uTime*0.01, 0.0, uTime*0.004));
        float cm = smoothstep(0.45, 0.75, cl) * uCloud;
        c = mix(c, uCloudCol * (0.7 + 0.6*cl), cm);
        // luna detras de nubes
        if (uMoon.x != 0.0 || uMoon.y != 0.0 || uMoon.z != 0.0) {
          float m = max(dot(d, normalize(uMoon)), 0.0);
          c += vec3(0.75,0.82,0.95) * (pow(m, 900.0)*1.2 + pow(m, 40.0)*0.25) * (1.0 - cm*0.6);
        }
        float g = max(dot(d, normalize(uGlowDir)), 0.0);
        c += uGlow * pow(g, uGlowPow);
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
}

export class Director {
  constructor(ctx) { this.ctx = ctx; }
  async init() {
    const { scene, over } = this.ctx;
    await loadFonts();
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(400, 32, 16), skyMaterial());
    this.sky.renderOrder = -1; this.sky.frustumCulled = false;
    scene.add(this.sky);
    scene.fog = new THREE.FogExp2(0x000000, 0.0);
    this.sets = {};
    this.sets.astro = new Astro(scene);
    const lazy = async (name, file, cls) => { try { const m = await import(file); this.sets[name] = new m[cls](scene, this.ctx); } catch (e) { console.warn('set', name, e.message); } };
    await lazy('north', './north.js', 'North');
    await lazy('south', './south.js', 'South');
    await lazy('poster', './poster.js', 'Poster');
    this.o2 = over.getContext('2d');
  }
  update(t) {
    const { camera, bokeh, bloom, grade, renderer, scene, W, H, overTex } = this.ctx;
    const s = shotAt(t);
    for (const k in this.sets) this.sets[k].root.visible = k === s.set;
    // camara
    const c = s.cam;
    camera.position.set(c.pos[0], c.pos[1], c.pos[2]);
    camera.up.set(0, 1, 0);
    if (c.up) camera.up.set(c.up[0], c.up[1], c.up[2]);
    camera.lookAt(c.look[0], c.look[1], c.look[2]);
    if (c.roll) camera.rotateZ(c.roll);
    camera.fov = c.fov || 40; camera.near = c.near || 0.05; camera.far = 900;
    camera.updateProjectionMatrix();
    this.sky.position.copy(camera.position);
    // postproceso
    const dist = s.focus ?? Math.hypot(c.pos[0] - c.look[0], c.pos[1] - c.look[1], c.pos[2] - c.look[2]);
    bokeh.enabled = (s.aperture ?? 0.0015) > 0;
    bokeh.uniforms.focus.value = dist;
    bokeh.uniforms.aperture.value = s.aperture ?? 0.0015;
    bokeh.uniforms.maxblur.value = s.maxblur ?? 0.012;
    bloom.strength = s.bloom ?? 0.5; bloom.threshold = s.bloomTh ?? 0.85; bloom.radius = s.bloomR ?? 0.6;
    renderer.toneMappingExposure = s.exposure ?? 1.0;
    const gu = grade.uniforms;
    gu.uFade.value = s.fade ?? 1;
    gu.uSat.value = s.sat ?? 1;
    gu.uContrast.value = s.contrast ?? 1.05;
    gu.uVignette.value = s.vignette ?? 0.45;
    gu.uGrain.value = s.grain ?? 0.03;
    gu.uTint.value.set(...(s.tint || [1, 1, 1]));
    gu.uLift.value.set(...(s.lift || [0, 0, 0]));
    // cielo
    const su = this.sky.material.uniforms;
    const sk = s.sky || {};
    su.uTop.value.set(sk.top ?? 0x0a0f18); su.uHor.value.set(sk.hor ?? 0x2a3240);
    su.uGlow.value.set(sk.glow ?? 0x000000); su.uGlowPow.value = sk.glowPow ?? 8;
    if (sk.glowDir) su.uGlowDir.value.set(...sk.glowDir);
    su.uCloud.value = sk.cloud ?? 0.6; su.uCloudCol.value.set(sk.cloudCol ?? 0x5a6676); su.uTime.value = t;
    su.uMoon.value.set(...(sk.moon || [0, 0, 0]));
    this.sky.visible = s.skyOn !== false;
    scene.fog.color.set(s.fogCol ?? 0x000000); scene.fog.density = s.fog ?? 0;
    scene.background = new THREE.Color(s.bg ?? 0x000000);
    // set activo
    const set = this.sets[s.set];
    if (set) set.update(s.lt, camera, s.state || {}, t);
    // creditos
    drawCredits(this.o2, W, H, t);
    overTex.needsUpdate = true;
  }
}
