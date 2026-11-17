// Personajes voxel articulados: Jon y Daenerys.
import * as THREE from 'three';
import { Grid, meshGrid, voxMaterial, jitter, shade, mix, hash3, lerp, clamp } from './voxel.js';
import { JON_FRONT, JON_BACK, DANY_FRONT, DANY_BACK } from './skins.js';

export const CV = 1 / 32; // tamano de voxel de personaje (m)

const MAT = voxMaterial({ roughness: 0.85, key: 'char' });

function partMesh(grid, pivot) {
  const m = new THREE.Mesh(meshGrid(grid, { scale: CV, origin: pivot }), MAT);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// ---------------------------------------------------------------------------
// Construccion a partir de skins estilo Minecraft (1 pixel de skin = 2x2 voxeles)
// ---------------------------------------------------------------------------

const PX = 2; // voxeles por pixel de skin
const HAIR_J = new Set([0x18181a, 0x2a2826]);
const FUR_J = new Set([0x9e9e9e, 0x858282, 0xc4c4c4]);
const isLight = (c) => c !== null && c !== undefined && (((c >> 16) & 255) + ((c >> 8) & 255) + (c & 255)) > 600;
const isDanyHair = (c) => isLight(c) && ((c >> 16) & 255) - (c & 255) < 40; // blanco crema
const isRedCloak = (c) => c === 0x510602 || c === 0x510603 || c === 0x5e0b06 || c === 0x350201;

/**
 * Crea una parte (caja) pintada con la skin.
 * F/B: grids front/back. fr/br: [col, row, cols, rows]. depth en pixeles.
 * opts.overlay(c) -> grosor de capa exterior (0 = nada); opts.fringe: flecos bajo la capa exterior
 * opts.face(g, ox, oy, oz, W, H, D): retoques en la cara frontal
 */
function skinPart(F, B, fr, br, depthPx, opts = {}) {
  const W = fr[2] * PX, H = fr[3] * PX, D = depthPx * PX;
  const M = opts.margin ?? 2, MB = opts.marginBottom ?? (opts.fringe ? 4 : 0);
  const g = new Grid(W + 2 * M, H + M + MB, D + 2 * M);
  const ox = M, oy = MB, oz = M;
  const front = (xc, yr) => F[fr[1] + yr][fr[0] + xc];
  const back = (xc, yr) => B[br[1] + yr][br[0] + (br[2] - 1 - xc)];
  const colAt = (x, y, z) => {
    const xc = Math.min(fr[2] - 1, Math.max(0, Math.floor(x / PX)));
    const yr = Math.min(fr[3] - 1, Math.max(0, fr[3] - 1 - Math.floor(y / PX)));
    const c = z >= D / 2 ? front(xc, yr) : back(xc, yr);
    return c ?? 0x202020;
  };
  for (let z = 0; z < D; z++) for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    g.set(x + ox, y + oy, z + oz, jitter(colAt(x, y, z), 0.06, x, y, z));
  }
  if (opts.face) opts.face(g, ox, oy, oz, W, H, D);
  // capa exterior (pelo, pelaje, capa)
  if (opts.overlay) {
    const add = [];
    for (let z = 0; z < D; z++) for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const onSurf = x === 0 || x === W - 1 || y === H - 1 || z === 0 || z === D - 1;
      if (!onSurf) continue;
      const c = colAt(x, y, z);
      const th = opts.overlay(c, x, y, z, W, H, D);
      if (!th) continue;
      const dirs = [];
      if (x === 0) dirs.push([-1, 0, 0]); if (x === W - 1) dirs.push([1, 0, 0]);
      if (y === H - 1 && opts.overlayTop !== false) dirs.push([0, 1, 0]);
      if (z === 0) dirs.push([0, 0, -1]); if (z === D - 1 && opts.overlayFront !== false) dirs.push([0, 0, 1]);
      if (!dirs.length) continue;
      // cascaron uniforme: vecinos fuera de la caja base dentro de la distancia th
      for (let dz = -th; dz <= th; dz++) for (let dy = -th; dy <= th; dy++) for (let dx = -th; dx <= th; dx++) {
        const nx = x + dx, ny = y + dy, nz = z + dz;
        const inside = nx >= 0 && nx < W && ny >= 0 && ny < H && nz >= 0 && nz < D;
        if (inside) continue;
        // solo hacia las caras permitidas
        if (ny >= H && opts.overlayTop === false) continue;
        if (nz >= D && opts.overlayFront === false) continue;
        if (ny < 0) continue;
        const ok = dirs.some(([ax, ay, az]) => (ax && Math.sign(dx) === ax) || (ay && Math.sign(dy) === ay) || (az && Math.sign(dz) === az));
        if (!ok) continue;
        add.push([nx + ox, ny + oy, nz + oz, jitter(c, 0.12, nx, ny, nz)]);
      }
      // flecos colgando bajo la capa
      if (opts.fringe && y <= 1 + (opts.fringeY ?? 0)) {
        const len = Math.floor(hash3(x, z, 77) * 4);
        for (const [dx, , dz] of dirs) for (let k = 1; k <= len; k++) add.push([x + ox + dx, y + oy - k, z + oz + dz, jitter(0xc8c8c8, 0.1, x, k, z)]);
      }
    }
    for (const [x, y, z, c] of add) if (!g.solid(x, y, z)) g.set(x, y, z, c);
  }
  if (opts.extra) opts.extra(g, ox, oy, oz, W, H, D);
  return { g, pivot: opts.pivot ? opts.pivot(ox, oy, oz, W, H, D) : [ox + W / 2, oy, oz + D / 2] };
}

// --- caras: retoques de expresion sobre la cara frontal de la cabeza (z = oz + D - 1)
function faceEdits(kind, ex) {
  return (g, ox, oy, oz, W, H, D) => {
    const z = oz + D - 1;
    // vx: columna en voxeles (0..15) desde -x ; vy: fila en voxeles desde ARRIBA (0..15)
    const set = (vx, vy, c) => g.set(ox + vx, oy + H - 1 - vy, z, c);
    const get = (vx, vy) => g.get(ox + vx, oy + H - 1 - vy, z);
    if (kind === 'jon') {
      const SK = 0xeec08a, SKD = 0xd69a62, LASH = 0x2a1c14, WHITE = 0xecdcc3, IRIS = 0x3a2416, DARK = 0x24100c;
      const eyes = [[2, 3, 4, 5], [10, 11, 12, 13]]; // columnas voxel de cada ojo (blanco+iris)
      const ey = 10; // filas 10-11
      for (const cols of eyes) {
        if (ex.eyes === 'closed') {
          for (const c of cols) { set(c, ey, SK); set(c, ey + 1, LASH); }
        } else if (ex.eyes === 'squint') {
          for (const c of cols) set(c, ey, SKD);
        } else if (ex.eyes === 'up') {
          // pupila hacia arriba
          for (const c of cols) { const v = get(c, ey + 1); if (v !== -1 && v < 0x505050) { set(c, ey, IRIS); set(c, ey + 1, WHITE); } }
        } else if (ex.eyes === 'wide') {
          for (const c of cols) set(c, ey - 1, get(c, ey) === -1 ? WHITE : (get(c, ey) < 0x505050 ? IRIS : WHITE));
        }
        if (ex.tears) { set(cols[0], ey + 2, 0xb8d0e0); set(cols[3], ey + 3, 0xb8d0e0); }
      }
      if (ex.brow === 'sad') { set(5, 7, 0x3a2a1e); set(5, 8, SK); set(10, 7, 0x3a2a1e); set(10, 8, SK); }
      if (ex.brow === 'fear') { for (const c of [2, 3, 4, 5, 10, 11, 12, 13]) { set(c, 7, 0x3a2a1e); set(c, 8, SK); } }
      // boca (filas 14-15, columnas 6-9)
      if (ex.mouth === 'open') { for (let c = 6; c <= 9; c++) { set(c, 14, DARK); set(c, 15, 0x3a1612); } set(6, 14, 0xd8d0c4); set(7, 14, 0xd8d0c4); }
      else if (ex.mouth === 'grit') { for (let c = 5; c <= 10; c++) { set(c, 14, 0xd8d0c4); set(c, 15, DARK); } }
      else if (ex.mouth === 'part') { for (let c = 6; c <= 9; c++) set(c, 15, DARK); }
    } else {
      const SK = 0xffe0c4, LASH = 0x2e241f;
      // ojos: columnas voxel 2-5 (blanco 2-3, iris 4-5) y 10-13 ; filas 10-13
      const eyes = [[2, 3, 4, 5], [10, 11, 12, 13]];
      if (ex.eyes === 'closed') {
        for (const cols of eyes) for (const c of cols) { for (let r = 10; r <= 13; r++) set(c, r, SK); set(c, 12, LASH); }
      }
      // labios
      for (let c = 6; c <= 9; c++) set(c, 14, 0xe0a49a);
      if (ex.mouth === 'part' || ex.mouth === 'open') { set(7, 14, 0x8a4a48); set(8, 14, 0x8a4a48); }
    }
  };
}

function buildHead(kind, ex) {
  const isJ = kind === 'jon';
  const F = isJ ? JON_FRONT : DANY_FRONT, B = isJ ? JON_BACK : DANY_BACK;
  const fr = isJ ? [4, 0, 8, 8] : [3, 0, 8, 8];
  const isHair = isJ ? (c) => HAIR_J.has(c) : isDanyHair;
  const r = skinPart(F, B, fr, fr, 8, {
    margin: 2, marginBottom: isJ ? 7 : 6,
    face: faceEdits(kind, ex),
    overlay: (c, x, y, z, W, H, D) => {
      if (!isHair(c)) return 0;
      if (z === D - 1 && y < H - 4) return 0; // en la cara solo el flequillo de arriba
      return 1;
    },
    extra: (g, ox, oy, oz, W, H, D) => {
      // melena trasera que cae por la nuca
      const hc = isJ ? 0x18181a : 0xf2eadd, hc2 = isJ ? 0x2a2826 : 0xe8e0d4;
      const len = isJ ? 7 : 6;
      for (let x = -1; x <= W; x++) for (let k = 1; k <= len; k++) {
        if (hash3(x, k, 3) < k / (len + 2) * 0.6) continue;
        g.set(ox + x, oy - k, oz - 1, jitter(hash3(x, k, 5) < 0.4 ? hc2 : hc, 0.1, x, k, 1));
        if (k < len - 1) g.set(ox + x, oy - k, oz, jitter(hc, 0.1, x, k, 2));
      }
      // mechones laterales que caen junto a la cara
      for (const sx of [-1, W]) for (let k = 0; k < (isJ ? 5 : 6); k++) for (let z = D - 6; z < D - 1; z++) {
        if (hash3(sx, k, z) < 0.25) continue;
        g.set(ox + sx, oy - k, oz + z, jitter(hc, 0.1, sx, k, z));
      }
    },
    pivot: (ox, oy, oz, W, H, D) => [ox + W / 2, oy, oz + D / 2],
  });
  return r;
}

function charParts(kind) {
  const isJ = kind === 'jon';
  const F = isJ ? JON_FRONT : DANY_FRONT, B = isJ ? JON_BACK : DANY_BACK;
  const aw = isJ ? 4 : 3; // ancho del brazo en pixeles
  const bx = aw, rx = aw + 8; // columna del cuerpo / brazo izquierdo en la skin
  const P = {};
  const furOv = (c) => (isJ && FUR_J.has(c) ? 2 : 0);
  const cloakOv = (c, x, y, z) => (!isJ && isRedCloak(c) && z === 0 ? 1 : 0);
  const topPivot = (ox, oy, oz, W, H, D) => [ox + W / 2, oy + H, oz + D / 2];
  // torso
  P.torso = skinPart(F, B, [bx, 8, 8, 12], [bx, 8, 8, 12], 4, {
    overlay: isJ ? furOv : (c, x, y, z) => (isRedCloak(c) && z === 0 ? 1 : (isDanyHair(c) && (x === 0 || x === 15 || z === 7) ? 1 : 0)),
    fringe: isJ, fringeY: 9, overlayTop: true,
    pivot: (ox, oy, oz, W, H, D) => [ox + W / 2, oy, oz + D / 2],
  });
  // brazos: superior (filas 8-13) e inferior (14-19). Derecho = -x = columnas izquierdas del frente.
  const armR_f = [0, 8, aw, 6], armR_b = [rx, 8, aw, 6], armL_f = [rx, 8, aw, 6], armL_b = [0, 8, aw, 6];
  const low = (r) => [r[0], 14, r[2], 6];
  P.uarmR = skinPart(F, B, armR_f, armR_b, 4, { overlay: furOv, fringe: isJ, fringeY: 1, pivot: (ox, oy, oz, W, H, D) => [ox + W / 2, oy + H - 2, oz + D / 2] });
  P.uarmL = skinPart(F, B, armL_f, armL_b, 4, { overlay: furOv, fringe: isJ, fringeY: 1, pivot: (ox, oy, oz, W, H, D) => [ox + W / 2, oy + H - 2, oz + D / 2] });
  P.farmR = skinPart(F, B, low(armR_f), low(armR_b), 4, { overlay: furOv, overlayTop: false, pivot: topPivot });
  P.farmL = skinPart(F, B, low(armL_f), low(armL_b), 4, { overlay: furOv, overlayTop: false, pivot: topPivot });
  // piernas: muslo filas 20-25, espinilla 26-31
  const legR_f = [bx, 20, 4, 6], legR_b = [bx + 4, 20, 4, 6], legL_f = [bx + 4, 20, 4, 6], legL_b = [bx, 20, 4, 6];
  const shin = (r) => [r[0], 26, 4, 6];
  P.thighR = skinPart(F, B, legR_f, legR_b, 4, { pivot: topPivot });
  P.thighL = skinPart(F, B, legL_f, legL_b, 4, { pivot: topPivot });
  P.shinR = skinPart(F, B, shin(legR_f), shin(legR_b), 4, { pivot: topPivot });
  P.shinL = skinPart(F, B, shin(legL_f), shin(legL_b), 4, { pivot: topPivot });
  // pelo largo de Daenerys / faldon trasero de Jon
  if (isJ) {
    const g = new Grid(16, 14, 2);
    g.box(0, 0, 0, 15, 13, 1, (x, y, z) => jitter(hash3(x, y >> 1, z) < 0.3 ? 0x222226 : 0x151619, 0.08, x, y, z));
    P.skirt = { g, pivot: [8, 13.5, 1] };
  } else {
    // melena: segun la skin trasera (pelo en la mitad izquierda de la espalda)
    const g = new Grid(16, 30, 3);
    for (let y = 0; y < 30; y++) for (let x = 0; x < 16; x++) {
      const row = 8 + Math.floor((29 - y) / 2); // fila de skin desde arriba
      const col = 3 + (7 - Math.floor(x / 2)); // espejo (vista trasera)
      const c = row < 22 ? DANY_BACK[row][col] : null;
      const top = y >= 24;
      if (top || (c !== null && isDanyHair(c))) {
        for (let z = 0; z < 3; z++) if (z < 2 || hash3(x, y, 1) < 0.5) g.set(x, y, z, jitter(hash3(x, y >> 1, z) < 0.35 ? 0xe8e0d4 : 0xf6eee2, 0.06, x, y, z));
      }
    }
    P.skirt = { g, pivot: [8, 29.5, 2.5] };
  }
  // espada (Jon) / daga (Daenerys)
  if (isJ) {
    const g = new Grid(4, 40, 4);
    g.box(1, 0, 1, 2, 29, 2, (x, y, z) => jitter(0x241a14, 0.1, x, y, z));
    g.box(0, 30, 0, 3, 30, 3, () => 0x777777);
    g.box(1, 31, 1, 2, 36, 2, (x, y, z) => jitter(0x3a2a1a, 0.15, x, y, z));
    g.box(0, 37, 0, 3, 39, 3, (x, y, z) => jitter(0xb8b8b0, 0.2, x, y, z));
    P.sword = { g, pivot: [2, 32, 2] };
  } else {
    const g = new Grid(3, 14, 3);
    g.box(1, 0, 1, 1, 8, 1, (x, y, z) => jitter(0x2a2420, 0.15, x, y, z));
    g.box(0, 9, 0, 2, 9, 2, () => 0x8a8a84);
    g.box(1, 10, 1, 1, 13, 1, () => 0x6f6a64);
    P.sword = { g, pivot: [1, 0, 1] };
  }
  return P;
}

// ---------------------------------------------------------------------------
// Ensamblado con esqueleto (unidades: CV)
// ---------------------------------------------------------------------------
export class Character {
  constructor(kind) {
    this.kind = kind;
    const isJ = kind === 'jon';
    const P = charParts(kind);
    const shoulderX = isJ ? 12 : 11;
    this.root = new THREE.Group();      // articulacion de la cadera (y = largo de pierna al estar de pie)
    this.hips = new THREE.Group(); this.root.add(this.hips);
    this.spine = new THREE.Group(); this.hips.add(this.spine);
    this.spine.add(partMesh(P.torso.g, P.torso.pivot));
    this.neck = new THREE.Group(); this.neck.position.set(0, 24 * CV, 0); this.spine.add(this.neck);
    this.head = new THREE.Group(); this.neck.add(this.head);
    this.headCache = new Map();
    this.headMesh = null;
    this.setExpr({ eyes: 'open', mouth: 'closed', brow: 'neutral' });
    const mkArm = (side, up, lo) => {
      const sh = new THREE.Group(); sh.position.set(side * shoulderX * CV, 22 * CV, 0); this.spine.add(sh);
      sh.add(partMesh(up.g, up.pivot));
      const el = new THREE.Group(); el.position.set(0, -10 * CV, 0); sh.add(el);
      el.add(partMesh(lo.g, lo.pivot));
      return { sh, el };
    };
    this.armL = mkArm(1, P.uarmL, P.farmL); this.armR = mkArm(-1, P.uarmR, P.farmR);
    const mkLeg = (side, th, sn) => {
      const hp = new THREE.Group(); hp.position.set(side * 4 * CV, 0, 0); this.hips.add(hp);
      hp.add(partMesh(th.g, th.pivot));
      const kn = new THREE.Group(); kn.position.set(0, -12 * CV, 0); hp.add(kn);
      kn.add(partMesh(sn.g, sn.pivot));
      return { hp, kn };
    };
    this.legL = mkLeg(1, P.thighL, P.shinL); this.legR = mkLeg(-1, P.thighR, P.shinR);
    this.skirt = new THREE.Group();
    if (isJ) { this.skirt.position.set(0, 0, -4.5 * CV); this.hips.add(this.skirt); }
    else { this.skirt.position.set(0, 24 * CV, -4.5 * CV); this.spine.add(this.skirt); }
    this.skirt.add(partMesh(P.skirt.g, P.skirt.pivot));
    this.sword = new THREE.Group();
    this.sword.add(partMesh(P.sword.g, P.sword.pivot));
    if (isJ) { this.sword.position.set(8.5 * CV, 1 * CV, 1 * CV); this.sword.rotation.set(0.15, 0, 0.3); this.hips.add(this.sword); }
    else { this.sword.position.set(1.5 * CV, 14 * CV, 4.5 * CV); this.sword.rotation.set(1.45, 0, 0.1); this.spine.add(this.sword); this.sword.visible = false; }
  }
  setExpr(ex) {
    const key = `${ex.eyes}|${ex.mouth}|${ex.brow}|${ex.tears ? 1 : 0}`;
    if (this.exprKey === key) return;
    this.exprKey = key;
    let m = this.headCache.get(key);
    if (!m) {
      const h = buildHead(this.kind, ex);
      m = partMesh(h.g, h.pivot);
      this.headCache.set(key, m);
    }
    if (this.headMesh) this.head.remove(this.headMesh);
    this.headMesh = m; this.head.add(m);
  }
  pose(p) {
    const e = (o, v) => { if (v) o.rotation.set(v[0] || 0, v[1] || 0, v[2] || 0, 'YXZ'); else o.rotation.set(0, 0, 0); };
    e(this.hips, p.hips); e(this.spine, p.spine); e(this.neck, p.neck); e(this.head, p.head);
    e(this.armL.sh, p.shL); e(this.armL.el, p.elL); e(this.armR.sh, p.shR); e(this.armR.el, p.elR);
    e(this.legL.hp, p.hpL); e(this.legL.kn, p.knL); e(this.legR.hp, p.hpR); e(this.legR.kn, p.knR);
    if (this.kind === 'jon') {
      const ax = Math.max(0, -Math.min((p.hpL || [0])[0], (p.hpR || [0])[0]));
      this.skirt.rotation.set(-Math.min(ax, 1.2) * 0.5 + 0.05, 0, 0);
    } else {
      this.skirt.rotation.set((p.hair || 0.06), 0, 0);
    }
    if (p.expr) this.setExpr(p.expr);
    if (p.dagger !== undefined && this.kind !== 'jon') this.sword.visible = p.dagger;
  }
}

// interpolacion de poses (lineal sobre angulos)
export function blendPose(a, b, t) {
  const out = {};
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if (k === 'expr' || k === 'dagger') { out[k] = t < 0.5 ? (a[k] ?? b[k]) : (b[k] ?? a[k]); continue; }
    const va = a[k], vb = b[k];
    if (typeof va === 'number' || typeof vb === 'number') { out[k] = lerp(va ?? 0, vb ?? 0, t); continue; }
    const A = va || [0, 0, 0], B = vb || [0, 0, 0];
    out[k] = [lerp(A[0] || 0, B[0] || 0, t), lerp(A[1] || 0, B[1] || 0, t), lerp(A[2] || 0, B[2] || 0, t)];
  }
  return out;
}
