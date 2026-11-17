// Director: arma la escena y aplica el plano correspondiente a cada instante t.
import * as THREE from 'three';
import { buildWorld, buildThroneGrid, THRONE_POS } from './world.js';
import { Character } from './characters.js';
import { Dragon } from './dragon.js';
import { Ash, FireStream, Flames, Embers, Smoke, Lava } from './fx.js';
import { SHOTS } from './shots.js';
import { meshGrid, voxMaterial, Grid, clamp, lerp, hash3, mix } from './voxel.js';

function makeSky() {
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { uTop: { value: new THREE.Color(0x5d6f80) }, uHor: { value: new THREE.Color(0xb4c0ca) }, uWarm: { value: new THREE.Color(0x000000) }, uTime: { value: 0 }, uCloud: { value: 1 } },
    vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); gl_Position.z = gl_Position.w; }`,
    fragmentShader: `
      uniform vec3 uTop; uniform vec3 uHor; uniform vec3 uWarm; uniform float uTime; uniform float uCloud; varying vec3 vDir;
      float h(vec3 p){ return fract(sin(dot(p, vec3(127.1,311.7,74.7)))*43758.5453); }
      float n(vec3 p){ vec3 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
        return mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x),mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),
                   mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x),mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y),f.z); }
      float fbm(vec3 p){ float s=0.0,a=0.5; for(int i=0;i<5;i++){ s+=a*n(p); p*=2.07; a*=0.5;} return s; }
      void main(){
        vec3 d = normalize(vDir);
        float t = clamp(d.y*1.6, 0.0, 1.0);
        vec3 c = mix(uHor, uTop, pow(t, 0.7));
        vec2 uv = d.xz / max(0.08, d.y + 0.15);
        float cl = fbm(vec3(uv*1.3 + vec2(uTime*0.01, 0.0), uTime*0.005));
        c = mix(c, c*0.72, smoothstep(0.42, 0.75, cl) * uCloud * (0.3 + 0.7*t));
        c = mix(c, c*1.12, smoothstep(0.55, 0.3, cl) * uCloud * 0.5);
        c += uWarm * pow(1.0 - t, 3.0);
        gl_FragColor = vec4(c, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`,
  });
  const m = new THREE.Mesh(new THREE.SphereGeometry(800, 32, 16), mat);
  m.frustumCulled = false;
  return m;
}

export class Director {
  constructor(ctx) { this.ctx = ctx; }
  async init() {
    const { scene } = this.ctx;
    this.sky = makeSky(); scene.add(this.sky);
    scene.fog = new THREE.FogExp2(0xa3b0bc, 0.012);
    this.world = buildWorld(scene);
    // trono
    const th = buildThroneGrid();
    this.throneData = th;
    this.throneMat = voxMaterial({ roughness: 0.45, metalness: 0.6, key: 'throne', emiGain: 6 });
    this.throne = new THREE.Mesh(meshGrid(th.grid, { scale: th.v, origin: th.origin }), this.throneMat);
    this.throne.castShadow = true; this.throne.receiveShadow = true;
    this.throne.position.copy(THRONE_POS);
    scene.add(this.throne);
    // personajes
    this.jon = new Character('jon'); scene.add(this.jon.root);
    this.dany = new Character('dany'); scene.add(this.dany.root);
    this.drogon = new Dragon(); scene.add(this.drogon.root);
    // luces
    this.hemi = new THREE.HemisphereLight(0xc4d2e0, 0x5e5a58, 1.25); scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xe2eaf2, 1.6);
    this.sun.castShadow = true; this.sun.shadow.mapSize.set(2048, 2048); this.sun.shadow.bias = -0.0004; this.sun.shadow.normalBias = 0.02;
    this.sun.shadow.radius = 4;
    scene.add(this.sun); scene.add(this.sun.target);
    this.fireLight = new THREE.PointLight(0xff7a2a, 0, 40, 1.6); scene.add(this.fireLight);
    this.fireLight2 = new THREE.PointLight(0xff8a3a, 0, 30, 1.6); scene.add(this.fireLight2);
    this.rim = new THREE.DirectionalLight(0xcfe0f0, 0); scene.add(this.rim); scene.add(this.rim.target);
    // efectos
    this.fx = {
      ash: new Ash(scene, 3000), fire: new FireStream(scene, 2600), flames: new Flames(scene, 2000),
      embers: new Embers(scene, 1500), smoke: new Smoke(scene, 300), lava: new Lava(scene, 80, 60, 0.12),
      fog: new Smoke(scene, 160, 0x8a949c, 0.18),
    };
    // mar (plano final)
    this.sea = new THREE.Mesh(new THREE.PlaneGeometry(3000, 3000, 1, 1), new THREE.MeshStandardMaterial({ color: 0x27323a, roughness: 0.35, metalness: 0.3 }));
    this.sea.rotation.x = -Math.PI / 2; this.sea.position.y = 0; scene.add(this.sea);
    this.shots = SHOTS;
  }

  shotAt(t) {
    for (let i = 0; i < this.shots.length; i++) if (t < this.shots[i].t1 || i === this.shots.length - 1) return this.shots[i];
    return this.shots[this.shots.length - 1];
  }

  resetState() {
    const { scene, bokeh, bloom, grade, renderer } = this.ctx;
    this.world.group.visible = true; if (this.sea) this.sea.visible = false;
    // visibilidad por defecto
    this.jon.root.visible = true; this.dany.root.visible = true; this.drogon.root.visible = false;
    this.throne.visible = true;
    for (const k in this.fx) this.fx[k].visible = false;
    this.fireLight.intensity = 0; this.fireLight2.intensity = 0; this.rim.intensity = 0;
    this.hemi.intensity = 1.25; this.hemi.color.set(0xc4d2e0); this.hemi.groundColor.set(0x5e5a58);
    this.sun.intensity = 1.6; this.sun.color.set(0xe2eaf2);
    scene.fog.color.set(0xa3b0bc); scene.fog.density = 0.012;
    this.sky.material.uniforms.uTop.value.set(0x5d6f80); this.sky.material.uniforms.uHor.value.set(0xb4c0ca); this.sky.material.uniforms.uWarm.value.set(0x000000);
    this.sky.visible = true;
    bokeh.enabled = true; bokeh.uniforms.aperture.value = 0.002; bokeh.uniforms.maxblur.value = 0.012;
    bloom.strength = 0.45; bloom.radius = 0.6; bloom.threshold = 0.85;
    const G = grade.uniforms;
    G.uTint.value.set(0.95, 1.0, 1.06); G.uLift.value.set(0.01, 0.015, 0.03); G.uSat.value = 0.85; G.uContrast.value = 1.06; G.uVignette.value = 0.4; G.uGrain.value = 0.03; G.uFade.value = 1;
    renderer.toneMappingExposure = 1.0;
  }

  // fundido del trono: m 0..1 (forma), h 0..1 (calor)
  setThroneMelt(m, h) {
    const q = Math.round(m * 40) / 40, qh = Math.round(h * 20) / 20;
    const key = q + '|' + qh;
    if (this.meltKey === key) return;
    this.meltKey = key;
    this.meltCache = this.meltCache || new Map();
    let geo = this.meltCache.get(key);
    if (!geo) {
      const src = this.throneData.grid, [cx, , cz] = this.throneData.origin;
      const g = new Grid(src.nx + 40, src.ny, src.nz + 40);
      for (let z = 0; z < src.nz; z++) for (let y = 0; y < src.ny; y++) for (let x = 0; x < src.nx; x++) {
        const c = src.get(x, y, z); if (c < 0) continue;
        const yn = y / src.ny;
        // los voxeles altos se funden antes; caen y se desparraman
        const local = clamp(q * 1.6 - (1 - yn) * 0.6 + (hash3(x, y, z) - 0.5) * 0.15);
        const ny = Math.floor(y * (1 - local * 0.97) * (1 - q * 0.6));
        const spread = 1 + q * 0.7 * (1 - ny / src.ny);
        const nx = Math.round(cx + (x - cx) * spread) + 20, nz = Math.round(cz + (z - cz) * spread) + 20;
        const heat = clamp(qh * (0.6 + local * 0.8) - yn * 0.15 * (1 - q));
        const col = heat > 0.02 ? mix(c, heat > 0.6 ? 0xffd27a : 0xff6a1a, Math.min(1, heat * 1.3)) : c;
        if (!g.solid(nx, ny, nz)) { g.set(nx, ny, nz, col); if (heat > 0.05) g.setE(nx, ny, nz, Math.round(heat * 255)); }
      }
      geo = meshGrid(g, { scale: this.throneData.v, origin: [cx + 20, 0, cz + 20] });
      this.meltCache.set(key, geo);
    }
    this.throne.geometry = geo;
    this.throneMat.userData.emiGain.value = 5;
  }

  setSun(dirFrom, target, halfSize = 6) {
    this.sun.position.set(target[0] + dirFrom[0], target[1] + dirFrom[1], target[2] + dirFrom[2]);
    this.sun.target.position.set(...target);
    const c = this.sun.shadow.camera;
    c.left = -halfSize; c.right = halfSize; c.top = halfSize; c.bottom = -halfSize; c.near = 0.5; c.far = 120;
    c.updateProjectionMatrix();
  }

  update(t) {
    this.resetState();
    const shot = this.shotAt(t);
    const lt = t - shot.t0;
    this.sky.material.uniforms.uTime.value = t;
    // estado global del trono (se funde con el fuego)
    const m = clamp((t - 141) / 21, 0, 1), h = t < 139 ? 0 : t < 166 ? clamp((t - 139) / 9) : lerp(1, 0.35, clamp((t - 166) / 40));
    this.setThroneMelt(m * m * (3 - 2 * m), h);
    if (h === 0) this.throneMat.userData.emiGain.value = 0;
    this.throne.visible = m < 0.97;
    shot.run(this, lt, t, shot);
    const dbg = new URLSearchParams(location.search).get('debug');
    if (dbg === 'tpose' || dbg === 'iso') {
      if (dbg === 'iso') { this.world.group.visible = false; this.throne.visible = false; }
      this.jon.root.position.set(0, 0.75, 0); this.jon.root.rotation.set(0, 0, 0); this.jon.pose({ expr: { eyes: 'open', mouth: 'closed', brow: 'sad', tears: true } });
      this.dany.root.position.set(1.0, 0.75, 0); this.dany.root.rotation.set(0, 0, 0); this.dany.pose({ expr: { eyes: 'closed', mouth: 'part', brow: 'neutral' }, dagger: true });
      this.drogon.root.visible = true; this.drogon.pose({ pos: [0, 0, -9], yaw: 0.6, wing: { raise: 0.3, sweep: 0.2, elbow: 0.3, spread: 1 } });
      for (const k in this.fx) this.fx[k].visible = false;
    }
    const cam = this.ctx.camera;
    cam.updateProjectionMatrix();
    this.sky.position.copy(cam.position);
  }

  // utilidades usadas por shots.js
  camera(pos, look, fov = 30, roll = 0) {
    const cam = this.ctx.camera;
    cam.position.set(...pos); cam.up.set(0, 1, 0); cam.lookAt(...look);
    if (roll) cam.rotateZ(roll);
    cam.fov = fov;
    const dist = Math.hypot(pos[0] - look[0], pos[1] - look[1], pos[2] - look[2]);
    this.ctx.bokeh.uniforms.focus.value = dist;
  }
  focus(dist, aperture = 0.002, maxblur = 0.012) {
    const b = this.ctx.bokeh.uniforms;
    b.focus.value = dist; b.aperture.value = aperture; b.maxblur.value = maxblur;
  }
}
