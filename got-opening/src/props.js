// Piezas reutilizables: suelo de mapa por shader, pinos instanciados, rotulos, engranajes, nubes.
import { THREE, Grid, vox, mat, bitmap, hash3, clamp, lerp, rng, jitter, shade, mix } from './kit.js';

// ---------------------------------------------------------------------------
// suelo del mapa: losas, costa/mar, rios, escarcha azul que avanza
// opts: tile, landFn(glsl), colors
// ---------------------------------------------------------------------------
export function mapGround(opts) {
  const size = opts.size || 600;
  const geo = new THREE.PlaneGeometry(size, size, 1, 1); geo.rotateX(-Math.PI / 2);
  const m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.85, metalness: 0.05 });
  const U = {
    uLand: { value: new THREE.Color(opts.land ?? 0xc9ccd0) }, uLand2: { value: new THREE.Color(opts.land2 ?? 0x9ea4aa) },
    uSea: { value: new THREE.Color(opts.sea ?? 0x14263c) }, uSea2: { value: new THREE.Color(opts.sea2 ?? 0x24425e) },
    uRiver: { value: new THREE.Color(opts.river ?? 0x2b3440) },
    uTile: { value: opts.tile ?? 1.0 },
    uFrostC: { value: new THREE.Vector2(0, -40) }, uFrostR: { value: 0 }, uFrostDir: { value: new THREE.Vector2(0, 1) },
    uSeaOn: { value: opts.seaOn ?? 1 },
  };
  m.userData.U = U;
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vW;')
      .replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvW = (modelMatrix * vec4(transformed,1.0)).xyz;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
      varying vec3 vW;
      uniform vec3 uLand, uLand2, uSea, uSea2, uRiver; uniform float uTile, uFrostR, uSeaOn; uniform vec2 uFrostC, uFrostDir;
      float hh(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453); }
      float nn(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f);
        return mix(mix(hh(i),hh(i+vec2(1,0)),f.x), mix(hh(i+vec2(0,1)),hh(i+vec2(1,1)),f.x), f.y); }
      float fb(vec2 p){ float a=0.5,s=0.0; for(int i=0;i<5;i++){ s+=a*nn(p); p*=2.03; a*=0.5; } return s; }
      ${opts.landGLSL || 'float landMask(vec2 p){ return 1.0; }'}
    `).replace('#include <color_fragment>', `#include <color_fragment>
      {
        vec2 p = vW.xz;
        // losas en hileras desplazadas
        vec2 q = p / uTile; q.x += mod(floor(q.y), 2.0) * 0.5;
        vec2 id = floor(q), f = fract(q);
        float seam = smoothstep(0.0, 0.06, f.x) * smoothstep(1.0, 0.94, f.x) * smoothstep(0.0, 0.08, f.y) * smoothstep(1.0, 0.92, f.y);
        float th = hh(id);
        vec3 c = mix(uLand2, uLand, 0.55 + 0.45 * th) * (0.92 + 0.16 * nn(p * 3.1));
        c *= mix(0.55, 1.0, seam);
        // rios
        float rv = abs(fb(p * 0.045 + 3.7) - 0.5);
        float river = 1.0 - smoothstep(0.004, 0.009, rv);
        c = mix(c, uRiver, river * 0.9);
        // escarcha azul que avanza desde la brecha
        vec2 tc = (id + 0.5); tc.x -= mod(floor(q.y), 2.0) * 0.5; tc *= uTile;
        vec2 dv = tc - uFrostC; float dd = length(dv);
        float cone = dot(normalize(dv + 1e-4), uFrostDir);
        float pick = step(0.55, hh(id + 7.3)) * step(0.55, cone);
        float lim = uFrostR * (0.55 + 0.45 * hh(id + 1.7)) * (0.6 + 0.4 * cone);
        float frost = pick * step(dd, lim) * (1.0 - smoothstep(lim - 0.6, lim, dd) * 0.5);
        c = mix(c, vec3(0.32, 0.5, 0.85), frost * 0.75);
        // mar
        float lm = landMask(p);
        float waves = 0.5 + 0.5 * sin((p.x * 0.35 + fb(p * 0.08) * 9.0) * 3.0);
        vec3 sea = mix(uSea, uSea2, waves * 0.6 + 0.2 * nn(p * 0.5));
        c = mix(sea, c, mix(1.0, lm, uSeaOn));
        diffuseColor.rgb *= c;
        frostE = frost;
      }`).replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\ntotalEmissiveRadiance += vec3(0.15,0.32,0.7) * frostE * 0.5;')
      .replace('void main() {', 'void main() {\nfloat frostE = 0.0;');
  };
  const mesh = new THREE.Mesh(geo, m);
  mesh.receiveShadow = true;
  return mesh;
}

// ---------------------------------------------------------------------------
// pino voxel (con nieve) -> InstancedMesh
// ---------------------------------------------------------------------------
export function pineGeometry(snow = true, dark = 0x2f3b33) {
  const g = new Grid(7, 14, 7);
  for (let y = 0; y < 3; y++) g.set(3, y, 3, 0x3a2c22);
  for (let y = 2; y < 14; y++) {
    const r = Math.max(0, Math.floor((14 - y) / 3.6));
    for (let x = 3 - r; x <= 3 + r; x++) for (let z = 3 - r; z <= 3 + r; z++) {
      if (Math.abs(x - 3) + Math.abs(z - 3) > r + 1) continue;
      const top = snow && (y % 3 === 0 || y > 11);
      g.set(x, y, z, top ? 0xe2e6ea : jitter(dark, 0.3, x, y, z));
    }
  }
  return g;
}
export function instanced(grid, v, origin, matKey, pts, opts = {}) {
  const tmp = vox(grid, v, origin, matKey, opts.mat || {});
  const im = new THREE.InstancedMesh(tmp.geometry, tmp.material, pts.length);
  const M = new THREE.Matrix4(), Q = new THREE.Quaternion(), S = new THREE.Vector3(), P = new THREE.Vector3(), E = new THREE.Euler();
  pts.forEach((p, i) => {
    E.set(0, p[3] || 0, 0); Q.setFromEuler(E); const s = p[4] || 1; S.set(s, s * (p[5] || 1), s); P.set(p[0], p[1], p[2]);
    M.compose(P, Q, S); im.setMatrixAt(i, M);
  });
  im.castShadow = opts.cast ?? true; im.receiveShadow = true;
  return im;
}

// ---------------------------------------------------------------------------
// rotulo dorado en relieve sobre el mapa (fuente uncial)
// ---------------------------------------------------------------------------
export function label(text, heightU, v = 0.05, font = 'Uncial') {
  const px = 40;
  const bm = bitmap(Math.ceil(text.length * px * 0.75) + 20, px + 16, (x, w, h) => {
    x.fillStyle = '#fff'; x.font = `${px}px ${font}`; x.textBaseline = 'middle'; x.textAlign = 'center'; x.fillText(text, w / 2, h / 2);
  });
  const k = heightU / v / bm.h; // voxeles por pixel
  const nx = Math.ceil(bm.w * k), nz = Math.ceil(bm.h * k);
  const g = new Grid(nx, 3, nz);
  for (let x = 0; x < nx; x++) for (let z = 0; z < nz; z++) {
    if (bm.at(x / k, z / k) > 0.5) for (let y = 0; y < 2; y++) g.set(x, y, z, jitter(0xc8962e, 0.25, x, y, z));
  }
  return vox(g, v, [nx / 2, 0, nz / 2], 'gold', { roughness: 0.35, metalness: 0.85 });
}

// ---------------------------------------------------------------------------
// engranaje voxel (plano XZ), radio en voxeles
// ---------------------------------------------------------------------------
export function gearGrid(R, teeth, thick, col, hub = true) {
  const n = Math.ceil(R + 3) * 2, c = n / 2;
  const g = new Grid(n, thick, n);
  for (let x = 0; x < n; x++) for (let z = 0; z < n; z++) {
    const dx = x + 0.5 - c, dz = z + 0.5 - c, r = Math.hypot(dx, dz), a = Math.atan2(dz, dx);
    const tooth = ((a / (Math.PI * 2)) * teeth % 1 + 1) % 1 < 0.5;
    const rOut = tooth ? R + 2 : R;
    const spoke = Math.abs(Math.sin(a * 3)) < 0.18;
    const inRim = r <= rOut && r > R - 2.5;
    const inHub = r < R * 0.25 + 1;
    if (inRim || (hub && (inHub || (spoke && r < R)))) for (let y = 0; y < thick; y++) g.set(x, y, z, jitter(col, 0.25, x, y, z));
  }
  return g;
}

// nubes: sprites grandes semitransparentes
export function cloudTexture(seed = 1) {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); const R = rng(seed);
  for (let i = 0; i < 40; i++) {
    const px = 128 + (R() - 0.5) * 140, py = 128 + (R() - 0.5) * 90, r = 30 + R() * 60;
    const g = x.createRadialGradient(px, py, 0, px, py, r);
    g.addColorStop(0, 'rgba(255,255,255,0.18)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, 256, 256);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
