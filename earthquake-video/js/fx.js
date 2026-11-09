import * as THREE from 'three';
import * as TX from './textures.js';
import { rng, T, smooth, clamp, lerp, seaLevel, waveFront, waveHeight, shakeEnvelope } from './timeline.js';

// Instanced camera-facing soft particles (dust, smoke, spray)
class Billboards {
  constructor(scene, max, texture, blending = THREE.NormalBlending) {
    this.max = max;
    const g = new THREE.InstancedBufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array([-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0]), 3));
    g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]), 2));
    g.setIndex([0, 1, 2, 0, 2, 3]);
    this.off = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3);
    this.par = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3); // size, alpha, rot
    this.col = new THREE.InstancedBufferAttribute(new Float32Array(max * 3), 3);
    g.setAttribute('iOff', this.off); g.setAttribute('iPar', this.par); g.setAttribute('iCol', this.col);
    g.instanceCount = 0;
    this.mat = new THREE.ShaderMaterial({
      uniforms: { map: { value: texture }, fogColor: { value: new THREE.Color() }, fogDensity: { value: 0 } },
      vertexShader: `
        attribute vec3 iOff; attribute vec3 iPar; attribute vec3 iCol;
        varying vec2 vUv; varying float vA; varying vec3 vC; varying float vDist;
        void main(){
          vec4 mv = modelViewMatrix * vec4(iOff, 1.0);
          float c = cos(iPar.z), s = sin(iPar.z);
          vec2 p = mat2(c, -s, s, c) * position.xy * iPar.x;
          mv.xy += p;
          vUv = uv; vA = iPar.y; vC = iCol; vDist = -mv.z;
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: `
        uniform sampler2D map; uniform vec3 fogColor; uniform float fogDensity;
        varying vec2 vUv; varying float vA; varying vec3 vC; varying float vDist;
        void main(){
          vec4 t = texture2D(map, vUv);
          float f = 1.0 - exp(-fogDensity * fogDensity * vDist * vDist);
          vec3 col = mix(vC, fogColor, f);
          gl_FragColor = vec4(col, t.a * vA);
          #include <colorspace_fragment>
        }`,
      transparent: true, depthWrite: false, blending,
    });
    this.mesh = new THREE.Mesh(g, this.mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 5;
    scene.add(this.mesh);
    this.p = [];
  }
  add(o) { if (this.p.length < this.max) this.p.push(o); else { this.p.shift(); this.p.push(o); } }
  update(dt, camPos) {
    const alive = [];
    for (const q of this.p) {
      q.age += dt;
      if (q.age > q.life) continue;
      q.vx *= Math.exp(-q.drag * dt); q.vz *= Math.exp(-q.drag * dt); q.vy = q.vy * Math.exp(-q.drag * dt) + q.g * dt;
      q.x += q.vx * dt; q.y += q.vy * dt; q.z += q.vz * dt;
      if (q.y < q.floor) { q.y = q.floor; q.vy = 0; }
      q.size += q.grow * dt;
      q.rot += q.spin * dt;
      alive.push(q);
    }
    this.p = alive;
    // sort back-to-front
    if (camPos) alive.sort((a, b) => ((b.x - camPos.x) ** 2 + (b.y - camPos.y) ** 2 + (b.z - camPos.z) ** 2) - ((a.x - camPos.x) ** 2 + (a.y - camPos.y) ** 2 + (a.z - camPos.z) ** 2));
    let n = 0;
    for (let i = 0; i < Math.min(alive.length, this.max); i++) {
      const q = alive[i];
      if (camPos && Math.hypot(q.x - camPos.x, q.y - camPos.y, q.z - camPos.z) < q.size * 0.4) continue;
      const k = q.age / q.life;
      const cd = camPos ? Math.hypot(q.x - camPos.x, q.y - camPos.y, q.z - camPos.z) : 99;
      const a = q.alpha * Math.min(1, q.age / q.fadeIn) * (1 - smooth(0.55, 1, k)) * smooth(q.size * 0.4, q.size * 1.2, cd);
      this.off.setXYZ(n, q.x, q.y, q.z);
      this.par.setXYZ(n, q.size, a, q.rot);
      this.col.setXYZ(n, q.r, q.g2, q.b);
      n++;
    }
    this.mesh.geometry.instanceCount = n;
    this.off.needsUpdate = this.par.needsUpdate = this.col.needsUpdate = true;
  }
}

// Instanced rigid little pieces (debris, glass)
class Pieces {
  constructor(scene, max, geo, material) {
    this.mesh = new THREE.InstancedMesh(geo, material, max);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.castShadow = true;
    this.mesh.frustumCulled = false;
    this.mesh.count = 0;
    scene.add(this.mesh);
    this.max = max; this.p = [];
    this.m = new THREE.Matrix4(); this.q = new THREE.Quaternion(); this.e = new THREE.Euler(); this.s = new THREE.Vector3(); this.v = new THREE.Vector3();
  }
  add(o) { if (this.p.length >= this.max) this.p.shift(); this.p.push(o); }
  update(dt) {
    let n = 0;
    for (const q of this.p) {
      if (!q.rest) {
        q.vy -= 9.8 * dt;
        q.x += q.vx * dt; q.y += q.vy * dt; q.z += q.vz * dt;
        q.rx += q.sx * dt; q.ry += q.sy * dt; q.rz += q.sz * dt;
        if (q.y < q.floor) {
          q.y = q.floor;
          if (Math.abs(q.vy) > 2) { q.vy *= -0.25; q.vx *= 0.5; q.vz *= 0.5; q.sx *= 0.5; q.sz *= 0.5; }
          else { q.rest = true; }
        }
      }
      this.e.set(q.rx, q.ry, q.rz); this.q.setFromEuler(this.e);
      this.s.set(q.sc, q.sc * (q.sy2 || 1), q.sc); this.v.set(q.x, q.y, q.z);
      this.m.compose(this.v, this.q, this.s);
      this.mesh.setMatrixAt(n++, this.m);
    }
    this.mesh.count = n;
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}

export class FX {
  constructor(scene, envMap) {
    this.scene = scene;
    this.r = rng(4242);
    const smoke = TX.smokeTexture();
    this.dust = new Billboards(scene, 900, smoke);
    this.spray = new Billboards(scene, 900, smoke);
    this.sparkB = new Billboards(scene, 300, TX.softDotTexture(), THREE.AdditiveBlending);
    this.debris = new Pieces(scene, 700, new THREE.DodecahedronGeometry(0.35, 0), new THREE.MeshStandardMaterial({ color: 0x8c857a, roughness: 1, flatShading: true }));
    this.glass = new Pieces(scene, 900, new THREE.PlaneGeometry(0.22, 0.3), new THREE.MeshStandardMaterial({ color: 0xcfe6f2, roughness: 0.05, metalness: 0.9, side: THREE.DoubleSide, envMapIntensity: 2.5 }));
    this.glass.mesh.castShadow = false;
    this.haze = 0;
    this.makeSea(envMap);
    this.makeWave(envMap);
  }

  // --------- emitters
  puff(x, y, z, n) {
    const r = this.r;
    for (let i = 0; i < n; i++) this.dust.add({ x: x + (r() - 0.5) * 2, y: y + 0.5, z: z + (r() - 0.5) * 2, vx: (r() - 0.5) * 3, vy: 1 + r() * 2, vz: (r() - 0.5) * 3, g: -0.2, drag: 0.8, floor: 0.2, size: 2 + r() * 2, grow: 1.5, rot: r() * 6, spin: (r() - 0.5) * 0.5, age: 0, life: 6 + r() * 4, fadeIn: 0.3, alpha: 0.55, r: 0.66, g2: 0.6, b: 0.52 });
  }
  burstDust(x, y, z, n, rad, h) {
    const r = this.r;
    n = Math.ceil(n * 0.5);
    for (let i = 0; i < n; i++) {
      const a = r() * 6.28, s = 4 + r() * 12;
      this.dust.add({ x: x + Math.cos(a) * rad * 0.3, y: y + r() * h * 0.4, z: z + Math.sin(a) * rad * 0.3, vx: Math.cos(a) * s, vy: 1 + r() * 4, vz: Math.sin(a) * s, g: -0.1, drag: 0.6, floor: 0.5, size: 5 + r() * 6, grow: 3 + r() * 2, rot: r() * 6, spin: (r() - 0.5) * 0.3, age: 0, life: 14 + r() * 10, fadeIn: 0.4, alpha: 0.6, r: 0.7 + r() * 0.05, g2: 0.64, b: 0.55 });
    }
  }
  emitDustColumn(x, z, d, w, tc, dt) {
    const r = this.r;
    const n = Math.floor(30 * dt * 4);
    for (let i = 0; i < n; i++) {
      const px = x + (r() - 0.5) * d, pz = z + (r() - 0.5) * w;
      this.dust.add({ x: px, y: 1 + r() * 30 * (1 - tc / 3.5), z: pz, vx: (r() - 0.5) * 4 + (x < 0 ? 3 : -3), vy: r() * 2, vz: (r() - 0.5) * 4, g: -0.05, drag: 0.5, floor: 0.5, size: 4 + r() * 5, grow: 2.5, rot: r() * 6, spin: (r() - 0.5) * 0.3, age: 0, life: 12 + r() * 8, fadeIn: 0.5, alpha: 0.6, r: 0.72, g2: 0.66, b: 0.57 });
    }
  }
  debrisBurst(x, y, z, n, toward) {
    const r = this.r;
    for (let i = 0; i < n; i++) {
      this.debris.add({ x: x + (r() - 0.5) * 14, y: y + (r() - 0.5) * 20, z: z + (r() - 0.5) * 14, vx: toward * (2 + r() * 8), vy: r() * 3, vz: (r() - 0.5) * 6, rx: r() * 6, ry: r() * 6, rz: r() * 6, sx: (r() - 0.5) * 8, sy: (r() - 0.5) * 8, sz: (r() - 0.5) * 8, sc: 0.4 + r() * 1.4, floor: 0.2 });
    }
  }
  glassRain(x, y, z, n, toward, spread = 8) {
    const r = this.r;
    for (let i = 0; i < n; i++) {
      this.glass.add({ x: x + toward * 0.3, y: y + (r() - 0.5) * 6, z: z + (r() - 0.5) * spread, vx: toward * (0.5 + r() * 3), vy: r() * 1.5, vz: (r() - 0.5) * 1.5, rx: r() * 6, ry: r() * 6, rz: r() * 6, sx: (r() - 0.5) * 14, sy: (r() - 0.5) * 14, sz: (r() - 0.5) * 14, sc: 0.5 + r() * 1.3, floor: 0.17 });
    }
  }
  sparks(x, y, z, n) {
    const r = this.r;
    for (let i = 0; i < n; i++) this.sparkB.add({ x, y, z, vx: (r() - 0.5) * 8, vy: r() * 6, vz: (r() - 0.5) * 8, g: -9.8, drag: 0.3, floor: 0.2, size: 0.15 + r() * 0.15, grow: -0.05, rot: 0, spin: 0, age: 0, life: 0.6 + r() * 0.9, fadeIn: 0.01, alpha: 1, r: 1.0, g2: 0.75 + r() * 0.2, b: 0.35 });
  }

  // --------- sea
  makeSea(envMap) {
    const nrm = TX.waterNormalTexture();
    nrm.repeat.set(260, 160);
    this.seaNormal = nrm;
    this.waterMat = new THREE.MeshStandardMaterial({ color: 0x0b3a4f, roughness: 0.06, metalness: 0.15, normalMap: nrm, normalScale: new THREE.Vector2(0.3, 0.3), envMapIntensity: 1.3 });
    this.waterMat.onBeforeCompile = (sh) => {
      sh.fragmentShader = sh.fragmentShader.replace('#include <normal_fragment_maps>',
        THREE.ShaderChunk.normal_fragment_maps.replace('mapN.xy *= normalScale;', 'mapN.xy *= normalScale * (0.25 + 0.75 * exp(-length(vViewPosition) / 90.0));'));
    };
    const sea = new THREE.Mesh(new THREE.PlaneGeometry(4000, 2400), this.waterMat);
    sea.rotation.x = -Math.PI / 2;
    sea.position.set(0, -0.4, -1360);
    sea.receiveShadow = true;
    this.sea = sea;
    this.scene.add(sea);
  }

  makeWave(envMap) {
    // cross-section profile (u: meters behind the front, h: fraction of crest height)
    const prof = [];
    const N = 70;
    for (let i = 0; i <= N; i++) {
      const s = i / N; // 0 = far behind, 1 = front base
      let u, h;
      if (s < 0.55) { u = -900 + (s / 0.55) * 860; h = 0.35 + 0.12 * Math.sin(s * 40); }
      else if (s < 0.8) { const k = (s - 0.55) / 0.25; u = -40 + k * 36; h = 0.35 + 0.65 * Math.sin(k * Math.PI / 2); }
      else if (s < 0.9) { const k = (s - 0.8) / 0.1; u = -4 + k * 6; h = 1.0 - 0.15 * k; }   // lip curling forward
      else { const k = (s - 0.9) / 0.1; u = 2 - k * 2.5; h = 0.85 * (1 - k); }               // falling face
      prof.push([u, h, s]);
    }
    this.prof = prof;
    const NX = 160;
    const W = 1400;
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array((NX + 1) * (N + 1) * 3);
    const col = new Float32Array((NX + 1) * (N + 1) * 3);
    const idx = [];
    for (let i = 0; i < NX; i++) for (let j = 0; j < N; j++) {
      const a = i * (N + 1) + j, b = (i + 1) * (N + 1) + j;
      idx.push(a, b, a + 1, b, b + 1, a + 1);
    }
    g.setIndex(idx);
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    this.waveW = W; this.waveNX = NX;
    const m = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.25, metalness: 0.05, normalMap: this.seaNormal, normalScale: new THREE.Vector2(0.8, 0.8), envMapIntensity: 1.0, side: THREE.DoubleSide });
    this.wave = new THREE.Mesh(g, m);
    this.wave.frustumCulled = false;
    this.wave.visible = false;
    this.wave.castShadow = false;
    this.wave.receiveShadow = true;
    this.scene.add(this.wave);
    this.waveUV = new Float32Array((NX + 1) * (N + 1) * 2);
    g.setAttribute('uv', new THREE.BufferAttribute(this.waveUV, 2));
  }

  updateWave(t, dt) {
    const f = waveFront(t);
    const sl = seaLevel(t);
    this.sea.position.y = sl;
    this.seaNormal.offset.set(t * 0.004, t * 0.006);
    if (f === null) { this.wave.visible = false; return; }
    this.wave.visible = true;
    const H = waveHeight(t);
    const pos = this.wave.geometry.attributes.position.array;
    const col = this.wave.geometry.attributes.color.array;
    const uv = this.waveUV;
    const N = this.prof.length - 1, NX = this.waveNX, W = this.waveW;
    const inland = f > -170;
    let k = 0;
    for (let i = 0; i <= NX; i++) {
      const x = -W / 2 + (i / NX) * W;
      const var1 = 1 + 0.12 * Math.sin(x * 0.013 + t * 0.4) + 0.08 * Math.sin(x * 0.041 - t * 0.9);
      // front is slightly curved and uneven
      const fz = f + 25 * Math.sin(x * 0.004) + 6 * Math.sin(x * 0.023 + t);
      for (let j = 0; j <= N; j++) {
        const [u, h, s] = this.prof[j];
        const hh = H * var1 * h;
        let y = sl + hh;
        if (inland) y = Math.max(y, 0) ; // floodwater over land
        const turb = (s > 0.5 ? 1 : 0.3) * (0.5 * Math.sin(x * 0.3 + t * 6 + j) + 0.4 * Math.sin(x * 0.17 - t * 5 + j * 0.7));
        pos[k * 3] = x; pos[k * 3 + 1] = y + turb; pos[k * 3 + 2] = fz + u * (1 + (s > 0.55 ? 0 : 0.0));
        // colour: deep teal body, white foam at crest/front, brown when inland
        const foam = smooth(0.62, 0.86, s) * (1 - smooth(0.97, 1.0, s) * 0.3);
        let cr = 0.05, cg = 0.27, cb = 0.32;
        if (inland) { cr = lerp(cr, 0.36, 0.6); cg = lerp(cg, 0.31, 0.6); cb = lerp(cb, 0.22, 0.6); }
        const fo = clamp(foam + 0.25 * Math.max(0, Math.sin(x * 0.11 + j * 0.9 + t * 3)) * smooth(0.5, 0.65, s), 0, 1);
        col[k * 3] = lerp(cr, 0.92, fo); col[k * 3 + 1] = lerp(cg, 0.95, fo); col[k * 3 + 2] = lerp(cb, 0.96, fo);
        uv[k * 2] = x / 18; uv[k * 2 + 1] = (fz + u) / 18;
        k++;
      }
    }
    this.wave.geometry.attributes.position.needsUpdate = true;
    this.wave.geometry.attributes.color.needsUpdate = true;
    this.wave.geometry.attributes.uv.needsUpdate = true;
    this.wave.geometry.computeVertexNormals();
    // spray along the crest
    const r = this.r;
    const n = Math.floor(dt * 260);
    for (let i = 0; i < n; i++) {
      const x = (r() - 0.5) * 700;
      const fz = f + 25 * Math.sin(x * 0.004) + 6 * Math.sin(x * 0.023 + t);
      this.spray.add({ x, y: sl + H * (0.8 + r() * 0.3) + (inland ? 2 : 0), z: fz - r() * 4, vx: (r() - 0.5) * 3, vy: 3 + r() * 6, vz: 6 + r() * 8, g: -4, drag: 0.4, floor: -20, size: 6 + r() * 8, grow: 4, rot: r() * 6, spin: (r() - 0.5) * 0.5, age: 0, life: 2.5 + r() * 2, fadeIn: 0.2, alpha: 0.75, r: 0.93, g2: 0.95, b: 0.97 });
    }
    // dust/debris clouds where water smashes buildings
    if (inland && r() < dt * 6) this.burstDust((r() - 0.5) * 200, 3, f + 4, 4, 6, 10);
  }

  update(t, dt, camPos, fog) {
    this.dust.mat.uniforms.fogColor.value.copy(fog.color);
    this.dust.mat.uniforms.fogDensity.value = fog.density;
    this.spray.mat.uniforms.fogColor.value.copy(fog.color);
    this.spray.mat.uniforms.fogDensity.value = fog.density * 0.6;
    this.sparkB.mat.uniforms.fogDensity.value = 0;
    // ambient dust shaken loose from facades during the S waves
    const e = shakeEnvelope(t);
    const r = this.r;
    if (t > T.sStart && t < T.shakeEnd) {
      const n = Math.floor(e * dt * 18 + r());
      for (let i = 0; i < n; i++) {
        const side = r() < 0.5 ? -1 : 1;
        const z = camPos.z - 10 - r() * 60;
        this.dust.add({ x: side * (9.3 + r() * 2), y: 5 + r() * 25, z, vx: -side * (0.5 + r()), vy: -1.5, vz: 0, g: -0.3, drag: 0.4, floor: 0.4, size: 2 + r() * 3, grow: 1.2, rot: r() * 6, spin: 0.1, age: 0, life: 6 + r() * 4, fadeIn: 0.5, alpha: 0.35, r: 0.75, g2: 0.7, b: 0.62 });
        if (r() < 0.6) this.glassRain(side * 9.2, 6 + r() * 20, z, 3 + Math.floor(r() * 5), -side, 3);
        if (r() < 0.25) this.debrisBurst(side * 9.6, 8 + r() * 15, z, 2, -side * 0.2);
      }
    }
    this.dust.update(dt, camPos);
    this.spray.update(dt, camPos);
    this.sparkB.update(dt, camPos);
    this.debris.update(dt);
    this.glass.update(dt);
    this.updateWave(t, dt);
  }
}
