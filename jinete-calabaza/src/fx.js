// Efectos: fuego pixelado (azul de almas / naranja), particulas, ondas, haces de luz, cielo.
import * as THREE from 'three';
import { paint, toTex, rng } from './textures.js';

const NOISE = /* glsl */ `
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y);
}
float fbm(vec2 p){ return vnoise(p)*0.55 + vnoise(p*2.1+3.1)*0.3 + vnoise(p*4.3+7.7)*0.15; }
`;

// ---------------------------------------------------------------------------
// Fuego: planos cruzados instanciados. uWave + aDelay => ola azul -> naranja
// ---------------------------------------------------------------------------
export class Fire {
  constructor(list, opts = {}) {
    // list: [{x,y,z,w,h,delay}]
    const base = new THREE.PlaneGeometry(1, 1);
    base.translate(0, 0.5, 0);
    const b2 = base.clone().rotateY(Math.PI / 2);
    const b3 = base.clone().rotateY(Math.PI / 4);
    const b4 = base.clone().rotateY(-Math.PI / 4);
    const merged = mergeGeos([base, b2, b3, b4]);
    const geo = new THREE.InstancedBufferGeometry();
    geo.index = merged.index;
    geo.setAttribute('position', merged.attributes.position);
    geo.setAttribute('uv', merged.attributes.uv);
    const n = list.length;
    const off = new Float32Array(n * 3), sc = new Float32Array(n * 2), sd = new Float32Array(n), dl = new Float32Array(n), br = new Float32Array(n);
    const r = rng(opts.seed || 5);
    list.forEach((f, i) => {
      off.set([f.x, f.y, f.z], i * 3);
      sc.set([f.w || 1, f.h || 1.2], i * 2);
      sd[i] = r() * 100;
      dl[i] = f.delay || 0;
      br[i] = f.b ?? 1;
    });
    geo.setAttribute('iOff', new THREE.InstancedBufferAttribute(off, 3));
    geo.setAttribute('iScale', new THREE.InstancedBufferAttribute(sc, 2));
    geo.setAttribute('iSeed', new THREE.InstancedBufferAttribute(sd, 1));
    geo.setAttribute('iDelay', new THREE.InstancedBufferAttribute(dl, 1));
    geo.setAttribute('iB', new THREE.InstancedBufferAttribute(br, 1));
    geo.instanceCount = n;
    this.uniforms = {
      uTime: { value: 0 }, uWave: { value: opts.orange ? 99 : -99 }, uFlare: { value: 1 }, uBright: { value: opts.bright || 2.2 }, uOpacity: { value: 1 },
      uTint: { value: new THREE.Color(...(opts.tint || [1, 1, 1])) }, uGold: { value: opts.gold || 0 }, uSpeed: { value: opts.speed || 2.6 },
    };
    const mat = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      vertexShader: /* glsl */ `
        attribute vec3 iOff; attribute vec2 iScale; attribute float iSeed; attribute float iDelay; attribute float iB;
        uniform float uFlare;
        varying vec2 vUv; varying float vSeed; varying float vDelay; varying float vB;
        void main(){
          vUv = uv; vSeed = iSeed; vDelay = iDelay; vB = iB;
          vec3 p = position * vec3(iScale.x, iScale.y * uFlare, iScale.x) + iOff;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        uniform float uTime, uWave, uBright, uOpacity, uGold, uSpeed; uniform vec3 uTint;
        varying vec2 vUv; varying float vSeed; varying float vDelay; varying float vB;
        ${NOISE}
        void main(){
          vec2 p = floor(vUv * 16.0) / 16.0 + 1.0/32.0;
          float n = fbm(vec2(p.x * 3.0 + vSeed, p.y * 2.2 - uTime * uSpeed - vSeed));
          float shape = (1.0 - p.y) * 1.35 * (1.0 - pow(abs(p.x - 0.5) * 2.0, 2.0));
          float f = shape - n * 0.75;
          if (f < 0.08) discard;
          float m = smoothstep(vDelay, vDelay + 0.35, uWave);
          vec3 bc = f > 0.55 ? vec3(0.85, 1.0, 1.0) : f > 0.3 ? vec3(0.25, 0.8, 1.0) : vec3(0.05, 0.3, 1.0);
          vec3 oc = f > 0.55 ? vec3(1.0, 0.95, 0.65) : f > 0.3 ? vec3(1.0, 0.55, 0.08) : vec3(0.85, 0.2, 0.03);
          vec3 gc = f > 0.55 ? vec3(1.0, 1.0, 0.85) : f > 0.3 ? vec3(1.0, 0.78, 0.22) : vec3(0.9, 0.45, 0.05);
          float a = f > 0.3 ? 1.0 : 0.7;
          vec3 col = mix(mix(bc, oc, m), gc, uGold) * uTint;
          gl_FragColor = vec4(col * uBright * a * uOpacity * vB, 1.0);
        }`,
    });
    this.mesh = new THREE.Mesh(geo, mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 5;
  }
  set(t, { wave, flare, bright, opacity, gold, tint } = {}) {
    this.uniforms.uTime.value = t;
    if (gold !== undefined) this.uniforms.uGold.value = gold;
    if (tint !== undefined) this.uniforms.uTint.value.setRGB(...tint);
    if (wave !== undefined) this.uniforms.uWave.value = wave;
    if (flare !== undefined) this.uniforms.uFlare.value = flare;
    if (bright !== undefined) this.uniforms.uBright.value = bright;
    if (opacity !== undefined) this.uniforms.uOpacity.value = opacity;
  }
}

// Fuego con instancias movibles (huellas ardiendo, llamas de personajes).
// update(list) reescribe posiciones/escala/brillo: [{x,y,z,w,h,b}]
export class FireTrail extends Fire {
  constructor(n, opts = {}) {
    super(Array.from({ length: n }, () => ({ x: 0, y: -999, z: 0, w: 0, h: 0, b: 0 })), opts);
    this.n = n;
    const g = this.mesh.geometry;
    this.aOff = g.attributes.iOff; this.aSc = g.attributes.iScale; this.aB = g.attributes.iB;
  }
  update(list) {
    for (let i = 0; i < this.n; i++) {
      const f = list[i];
      if (!f) { this.aOff.setXYZ(i, 0, -999, 0); this.aB.setX(i, 0); this.aSc.setXY(i, 0, 0); continue; }
      this.aOff.setXYZ(i, f.x, f.y, f.z);
      this.aSc.setXY(i, f.w ?? 0.3, f.h ?? 0.4);
      this.aB.setX(i, f.b ?? 1);
    }
    this.aOff.needsUpdate = this.aSc.needsUpdate = this.aB.needsUpdate = true;
  }
}

function mergeGeos(geos) {
  const pos = [], uv = [], idx = [];
  let base = 0;
  for (const g of geos) {
    pos.push(...g.attributes.position.array);
    uv.push(...g.attributes.uv.array);
    for (const i of g.index.array) idx.push(i + base);
    base += g.attributes.position.count;
  }
  const m = new THREE.BufferGeometry();
  m.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  m.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  m.setIndex(idx);
  return m;
}

// ---------------------------------------------------------------------------
// Particulas sin estado (posicion = funcion del tiempo)
// mode 0: emisor en bucle dentro de una caja ; mode 1: explosion (burst)
// ---------------------------------------------------------------------------
export class Particles {
  constructor(count, o = {}) {
    const geo = new THREE.BufferGeometry();
    const r = rng(o.seed || 11);
    const s = new Float32Array(count * 4), d = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      s.set([r(), r(), r(), r()], i * 4);
      // direccion aleatoria (esfera) para explosiones
      let x, y, z, l;
      do { x = r() * 2 - 1; y = r() * 2 - 1; z = r() * 2 - 1; l = x * x + y * y + z * z; } while (l > 1 || l < 0.01);
      l = Math.sqrt(l);
      d.set([x / l, y / l, z / l], i * 3);
    }
    geo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(count * 3), 3));
    geo.setAttribute('aSeed', new THREE.Float32BufferAttribute(s, 4));
    geo.setAttribute('aDir', new THREE.Float32BufferAttribute(d, 3));
    this.u = {
      uTime: { value: 0 }, uCenter: { value: new THREE.Vector3(...(o.center || [0, 0, 0])) }, uSize3: { value: new THREE.Vector3(...(o.box || [1, 1, 1])) },
      uVel: { value: new THREE.Vector3(...(o.vel || [0, 1, 0])) }, uSpread: { value: new THREE.Vector3(...(o.spread || [0.3, 0.3, 0.3])) },
      uGrav: { value: o.grav || 0 }, uLife: { value: o.life || 3 }, uPx: { value: o.size || 0.08 },
      uColA: { value: new THREE.Color(o.colA || 0x66ccff) }, uColB: { value: new THREE.Color(o.colB || o.colA || 0x66ccff) },
      uMix: { value: 0 }, uBright: { value: o.bright || 2 }, uOpacity: { value: 1 }, uMode: { value: o.burst ? 1 : 0 },
      uSpeed: { value: o.speed || 6 }, uDrag: { value: o.drag || 1.2 }, uTwinkle: { value: o.twinkle || 0 }, uSwirl: { value: o.swirl || 0 },
      uScaleH: { value: 540 },
    };
    const mat = new THREE.ShaderMaterial({
      uniforms: this.u,
      transparent: true,
      depthWrite: false,
      blending: o.normal ? THREE.NormalBlending : THREE.AdditiveBlending,
      vertexShader: /* glsl */ `
        attribute vec4 aSeed; attribute vec3 aDir;
        uniform float uTime, uGrav, uLife, uPx, uMode, uSpeed, uDrag, uTwinkle, uSwirl, uScaleH;
        uniform vec3 uCenter, uSize3, uVel, uSpread;
        varying float vA; varying float vS;
        void main(){
          vec3 p; float a;
          if (uMode < 0.5) {
            float age = fract(uTime / uLife + aSeed.w);
            float tt = age * uLife;
            vec3 base = uCenter + (aSeed.xyz - 0.5) * uSize3;
            vec3 v = uVel + (vec3(aSeed.y, aSeed.z, aSeed.x) - 0.5) * 2.0 * uSpread;
            p = base + v * tt + vec3(0.0, -0.5 * uGrav * tt * tt, 0.0);
            p.x += sin(tt * 1.7 + aSeed.x * 20.0) * uSwirl;
            p.z += cos(tt * 1.3 + aSeed.y * 20.0) * uSwirl;
            a = sin(3.14159 * age);
            if (uTwinkle > 0.0) a *= 0.5 + 0.5 * sin(uTime * 3.0 + aSeed.x * 40.0);
          } else {
            float tt = max(uTime - aSeed.w * 0.15, 0.0);
            float life = uLife * (0.5 + aSeed.x);
            float k = (1.0 - exp(-uDrag * tt)) / uDrag;
            vec3 dir = aDir; dir.y = abs(dir.y) * 0.6 + 0.2 * aSeed.z;
            p = uCenter + (aSeed.xyz - 0.5) * uSize3 + dir * uSpeed * (0.4 + aSeed.y) * k + uVel * tt + vec3(0.0, -0.5 * uGrav * tt * tt, 0.0);
            a = uTime <= 0.0 ? 0.0 : clamp(1.0 - tt / life, 0.0, 1.0);
          }
          vA = a; vS = aSeed.z;
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_PointSize = max(uPx * uScaleH / -mv.z * (0.6 + aSeed.x * 0.8), 1.0);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        uniform vec3 uColA, uColB; uniform float uMix, uBright, uOpacity;
        varying float vA; varying float vS;
        void main(){
          if (vA <= 0.001) discard;
          vec3 c = mix(uColA, uColB, uMix);
          c *= 0.8 + 0.4 * vS;
          gl_FragColor = vec4(c * uBright, vA * uOpacity);
        }`,
    });
    if (o.normal) mat.blending = THREE.NormalBlending;
    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
    this.points.renderOrder = 6;
  }
  set(t, extra = {}) {
    this.u.uTime.value = t;
    for (const k in extra) {
      const key = 'u' + k[0].toUpperCase() + k.slice(1);
      if (!this.u[key]) continue;
      const v = extra[k];
      if (Array.isArray(v)) this.u[key].value.set(...v);
      else if (v && v.isColor) this.u[key].value.copy(v);
      else if (this.u[key].value && this.u[key].value.isColor) this.u[key].value.set(v);
      else this.u[key].value = v;
    }
  }
}

// ---------------------------------------------------------------------------
// Anillo / onda expansiva pixelada
// ---------------------------------------------------------------------------
export function makeRing(color = 0xffffff, bright = 3) {
  const u = { uColor: { value: new THREE.Color(color) }, uBright: { value: bright }, uOpacity: { value: 1 }, uThick: { value: 0.08 } };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform vec3 uColor; uniform float uBright, uOpacity, uThick; varying vec2 vUv;
      void main(){
        vec2 q = floor((vUv - 0.5) * 96.0) / 96.0;
        float d = length(q) * 2.0;
        float ring = smoothstep(1.0 - uThick, 1.0 - uThick * 0.4, d) * (1.0 - smoothstep(0.985, 1.0, d));
        float inner = (1.0 - smoothstep(0.0, 1.0, d)) * 0.12;
        float a = (ring + inner) * uOpacity;
        if (a < 0.01) discard;
        gl_FragColor = vec4(uColor * uBright * a, 1.0);
      }`,
  });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
  m.userData.u = u;
  m.renderOrder = 7;
  m.frustumCulled = false;
  return m;
}

// ---------------------------------------------------------------------------
// Haz de luz volumetrico (cono aditivo)
// ---------------------------------------------------------------------------
export function makeShaft(len, r0, r1, color, opacity = 0.25) {
  const geo = new THREE.CylinderGeometry(r0, r1, len, 24, 1, true);
  geo.translate(0, -len / 2, 0);
  const u = { uColor: { value: new THREE.Color(color) }, uOpacity: { value: opacity }, uTime: { value: 0 } };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: `
      varying float vY; varying float vF; varying vec3 vW;
      void main(){
        vY = uv.y;
        vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
        vec3 n = normalize(mat3(modelMatrix) * normal);
        vec3 v = normalize(cameraPosition - w.xyz);
        vF = pow(abs(dot(n, v)), 1.6);
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: `
      uniform vec3 uColor; uniform float uOpacity, uTime; varying float vY; varying float vF; varying vec3 vW;
      void main(){
        float dust = 0.85 + 0.15 * sin(vW.x * 3.0 + vW.y * 2.0 + uTime * 0.7);
        float a = vF * smoothstep(0.0, 0.5, vY) * uOpacity * dust;
        gl_FragColor = vec4(uColor * a, 1.0);
      }`,
  });
  const m = new THREE.Mesh(geo, mat);
  m.userData.u = u;
  m.renderOrder = 4;
  return m;
}

// ---------------------------------------------------------------------------
// Cielo con gradiente, estrellas y halo del sol/luna
// ---------------------------------------------------------------------------
export function makeSky() {
  const u = {
    uTop: { value: new THREE.Color(0x05061a) }, uHor: { value: new THREE.Color(0x2a1a4a) }, uBot: { value: new THREE.Color(0x05040a) },
    uSunDir: { value: new THREE.Vector3(0, 0.3, -1).normalize() }, uSunCol: { value: new THREE.Color(0xff8a30) }, uGlow: { value: 0.6 },
    uStars: { value: 1 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: u, side: THREE.BackSide, depthWrite: false, fog: false,
    vertexShader: `varying vec3 vD; void main(){ vD = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; }`,
    fragmentShader: `
      uniform vec3 uTop, uHor, uBot, uSunDir, uSunCol; uniform float uGlow, uStars; varying vec3 vD;
      float h3(vec3 p){ return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
      void main(){
        vec3 d = normalize(vD);
        float y = d.y;
        vec3 c = y > 0.0 ? mix(uHor, uTop, pow(clamp(y, 0.0, 1.0), 0.55)) : mix(uHor, uBot, clamp(-y * 4.0, 0.0, 1.0));
        float s = max(dot(d, normalize(uSunDir)), 0.0);
        c += uSunCol * (pow(s, 6.0) * 0.18 + pow(s, 48.0) * 0.5) * uGlow;
        if (y > 0.05 && uStars > 0.0) {
          vec3 q = floor(d * 260.0);
          float st = h3(q);
          if (st > 0.9965) c += vec3(0.9, 0.9, 1.0) * (st - 0.9965) / 0.0035 * uStars * smoothstep(0.05, 0.3, y);
        }
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), mat);
  m.userData.u = u;
  m.renderOrder = -10;
  m.frustumCulled = false;
  return m;
}

// Luna cuadrada pixelada estilo Minecraft (naranja) + halo
export function makeMoon(color = [255, 150, 60]) {
  const tex = toTex(paint(32, 32, (x, y, r) => {
    const crater = [[9, 10, 3], [20, 8, 2], [22, 20, 4], [11, 22, 2], [16, 15, 1.5]].some(([cx, cy, cr]) => Math.hypot(x - cx, y - cy) < cr);
    const k = (crater ? 0.72 : 1) * (0.92 + r() * 0.08);
    return color.map((v) => Math.min(255, v * k));
  }), false);
  const g = new THREE.Group();
  const moon = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: tex, fog: false, color: new THREE.Color(1.15, 1.15, 1.15) }));
  const haloTex = toTex(paint(64, 64, (x, y) => {
    const d = Math.hypot(x - 31.5, y - 31.5) / 32;
    const a = Math.max(0, 1 - d) ** 2.2;
    return [255, 160, 80, Math.round(a * 255)];
  }), false);
  haloTex.magFilter = THREE.LinearFilter;
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 3.2), new THREE.MeshBasicMaterial({ map: haloTex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, opacity: 0.35 }));
  halo.position.z = -0.01;
  g.add(halo, moon);
  g.userData.moon = moon;
  g.userData.halo = halo;
  g.renderOrder = -5;
  return g;
}

// Nubes cubicas
export function makeClouds(seed, area, y, color = 0x3a3a55) {
  const r = rng(seed);
  const mat = new THREE.MeshStandardMaterial({ color, transparent: true, opacity: 0.7, roughness: 1, depthWrite: false });
  const geo = new THREE.BoxGeometry(1, 1, 1);
  const n = 70;
  const im = new THREE.InstancedMesh(geo, mat, n);
  const m = new THREE.Matrix4();
  for (let i = 0; i < n; i++) {
    const sx = 8 + Math.floor(r() * 20), sz = 6 + Math.floor(r() * 14);
    m.compose(new THREE.Vector3((r() - 0.5) * area, y + r() * 2, (r() - 0.5) * area), new THREE.Quaternion(), new THREE.Vector3(sx, 3, sz));
    im.setMatrixAt(i, m);
  }
  im.renderOrder = 2;
  return im;
}

// Bancos de niebla rasante (sprites suaves)
export function makeFogBank(count, center, size, color = 0x8090b0, opacity = 0.18, seed = 3) {
  const tex = toTex(paint(64, 64, (x, y, r) => {
    const d = Math.hypot(x - 31.5, y - 31.5) / 32;
    const a = Math.max(0, 1 - d) ** 1.6 * (0.75 + r() * 0.25);
    return [255, 255, 255, Math.round(a * 255)];
  }, seed), false);
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  const g = new THREE.Group();
  const r = rng(seed);
  const mat = new THREE.SpriteMaterial({ map: tex, color, transparent: true, opacity, depthWrite: false });
  for (let i = 0; i < count; i++) {
    const s = new THREE.Sprite(mat);
    const sc = 8 + r() * 10;
    s.scale.set(sc * 1.8, sc * 0.55, 1);
    s.position.set(center[0] + (r() - 0.5) * size[0], center[1] + r() * size[1], center[2] + (r() - 0.5) * size[2]);
    s.userData.base = s.position.clone();
    s.userData.ph = r() * 10;
    g.add(s);
  }
  g.userData.mat = mat;
  g.userData.update = (t) => {
    for (const s of g.children) s.position.x = s.userData.base.x + Math.sin(t * 0.08 + s.userData.ph) * 3 + t * 0.25;
  };
  g.renderOrder = 8;
  return g;
}

// Suelo lejano para que no se vea el borde del mundo
export function makeFarGround(color, y, tex) {
  const mat = new THREE.MeshLambertMaterial({ color });
  if (tex) { const t = tex.clone(); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1200, 1200); t.needsUpdate = true; mat.map = t; }
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1200, 1200), mat);
  m.rotation.x = -Math.PI / 2;
  m.position.y = y;
  m.receiveShadow = true;
  m.renderOrder = -1;
  return m;
}

// Siluetas de arboles muertos en el horizonte (anillo instanciado)
export function makeTreeRing(seed, rIn, rOut, count, color = 0x07060c, center = [0, 0, 0]) {
  const r = rng(seed);
  const mat = new THREE.MeshLambertMaterial({ color });
  const geo = new THREE.BoxGeometry(1, 1, 1);
  const im = new THREE.InstancedMesh(geo, mat, count * 4);
  const m = new THREE.Matrix4();
  let k = 0;
  for (let i = 0; i < count; i++) {
    const a = r() * Math.PI * 2, d = rIn + r() * (rOut - rIn);
    const x = center[0] + Math.cos(a) * d, z = center[2] + Math.sin(a) * d;
    const h = 8 + r() * 12;
    m.compose(new THREE.Vector3(x, center[1] + h / 2, z), new THREE.Quaternion(), new THREE.Vector3(1.2, h, 1.2));
    im.setMatrixAt(k++, m);
    for (let b = 0; b < 3; b++) {
      const bh = h * (0.5 + r() * 0.4), bl = 2 + r() * 4, ba = r() * Math.PI * 2;
      m.compose(new THREE.Vector3(x + Math.cos(ba) * bl / 2, center[1] + bh, z + Math.sin(ba) * bl / 2), new THREE.Quaternion().setFromEuler(new THREE.Euler(0, -ba, 0.4)), new THREE.Vector3(bl, 0.8, 0.8));
      im.setMatrixAt(k++, m);
    }
  }
  return im;
}
