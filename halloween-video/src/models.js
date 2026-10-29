// Personajes con cajas estilo Minecraft (UV en layout de skin) y rigs simples.
import * as THREE from 'three';
import { skinCanvas, toTex, paint, hex, jit, FACE16, jackFace, rng, blockTex, blockEmit } from './textures.js';

export function mcBoxGeo(w, h, d, u, v, tw, th, ppu, inflate = 0) {
  const g = new THREE.BoxGeometry(w / ppu + inflate * 2, h / ppu + inflate * 2, d / ppu + inflate * 2);
  // orden de caras de BoxGeometry: +x, -x, +y, -y, +z, -z
  const rects = [
    [u + d + w, v + d, d, h], // +x = lado izquierdo del personaje (mira a +z)
    [u, v + d, d, h], // -x = lado derecho
    [u + d, v, w, d], // arriba
    [u + d + w, v, w, d], // abajo
    [u + d, v + d, w, h], // frente
    [u + 2 * d + w, v + d, w, h], // espalda
  ];
  const uv = g.attributes.uv;
  for (let f = 0; f < 6; f++) {
    const [x0, y0, fw, fh] = rects[f];
    const L = x0 / tw, R = (x0 + fw) / tw, T = 1 - y0 / th, Bm = 1 - (y0 + fh) / th;
    const q = [[L, T], [R, T], [L, Bm], [R, Bm]];
    for (let k = 0; k < 4; k++) uv.setXY(f * 4 + k, q[k][0], q[k][1]);
  }
  return g;
}

function part(parent, geo, mat, pivot, offset, name) {
  const p = new THREE.Object3D();
  p.position.set(...pivot);
  const m = new THREE.Mesh(geo, mat);
  m.position.set(...offset);
  m.castShadow = true;
  m.receiveShadow = true;
  p.add(m);
  p.name = name;
  parent.add(p);
  return p;
}

const C = (c, r, a = 0.12) => jit(hex(c), r, a);

// ---------------------------------------------------------------------------
// Figura encapuchada (protagonista)
// ---------------------------------------------------------------------------
const FACE_GRIN = FACE16.slice(0, 9).concat([
  '###....##....###',
  '##.#........#.##',
  '###.##....##.###',
  '####..####..####',
  '#####......#####',
  '######....######',
  '################',
]);

function robeFn(base = 0x15151a) {
  return (face, x, y, fw, fh, r) => {
    const fold = (x + (face === 'back' ? 2 : 0)) % 4 === 1;
    const shade = face === 'top' ? 0.8 : 1;
    const c = C(fold ? 0x2a2a31 : base, r, 0.25);
    return c.map((v) => v * shade);
  };
}

function maskFace(mode) {
  const rows = mode === 'grin' ? FACE_GRIN : FACE16;
  const r = rng(99);
  return (x, y) => {
    const ch = rows[y][x];
    if (ch === '#') {
      // capucha negra alrededor / huecos negros
      const inside = x > 1 && x < 14 && y > 0 && y < 15 && rows[y].slice(0, x).includes('.') && rows[y].slice(x).includes('.');
      return inside ? [8, 8, 10] : jit([22, 22, 27], r, 0.3);
    }
    let c = jit([228, 228, 222], r, 0.06);
    if ((x + y) % 7 === 0) c = c.map((v) => v * 0.9);
    if (mode === 'cracked') {
      const crack = (x === y - 1 && x > 2 && x < 9) || (x === 12 - Math.floor(y / 2) && y > 1 && y < 9) || (y === 12 && x > 9 && x < 13);
      if (crack) return [70, 70, 74];
    }
    return c;
  };
}

function ghostSkin(mode) {
  const face = maskFace(mode);
  const robe = robeFn();
  return skinCanvas(128, 128, [
    { u: 0, v: 0, w: 16, h: 16, d: 16, fn: (f, x, y, fw, fh, r) => (f === 'front' ? face(x, y) : robe(f, x, y, fw, fh, r)) },
    {
      // capucha exterior: marco negro con hueco para la mascara
      u: 64, v: 0, w: 16, h: 16, d: 16,
      fn: (f, x, y, fw, fh, r) => {
        if (f === 'bottom') return null;
        if (f === 'front') {
          const edge = y === 0 || x === 0 || x === 15 || (y === 1 && (x < 4 || x > 11)) || (x === 1 && y < 12);
          return edge || x === 14 && y < 12 ? C(0x1c1c22, r, 0.3) : null;
        }
        return robe(f, x, y, fw, fh, r);
      },
    },
    { u: 0, v: 32, w: 16, h: 24, d: 8, fn: robe },
    { u: 48, v: 32, w: 8, h: 24, d: 8, fn: (f, x, y, fw, fh, r) => (y > fh - 4 && f !== 'top' ? C(0x0c0c0e, r) : robe(f, x, y, fw, fh, r)) },
    { u: 80, v: 32, w: 8, h: 24, d: 8, fn: (f, x, y, fw, fh, r) => (y > fh - 4 && f !== 'top' ? C(0x0c0c0e, r) : robe(f, x, y, fw, fh, r)) },
    { u: 0, v: 64, w: 18, h: 24, d: 10, fn: (f, x, y, fw, fh, r) => (y > fh - 2 ? C(0x0e0e11, r) : robe(f, x, y, fw, fh, r)) },
  ], 5);
}

function ghostEmit() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 128;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 128, 128);
  ctx.fillStyle = '#fff';
  // huecos de los ojos en la cara frontal (u+d=16, v+d=16)
  for (let y = 5; y <= 8; y++) for (let x = 0; x < 16; x++) if (FACE16[y][x] === '#' && x > 2 && x < 13) ctx.fillRect(16 + x, 16 + y, 1, 1);
  return cv;
}

export function makeGhost() {
  const ppu = 32;
  const skins = {};
  for (const m of ['normal', 'cracked', 'grin']) skins[m] = toTex(ghostSkin(m), false);
  const mat = new THREE.MeshStandardMaterial({
    map: skins.normal, roughness: 0.85, alphaTest: 0.5, side: THREE.FrontSide,
    emissiveMap: toTex(ghostEmit(), false), emissive: new THREE.Color(1, 1, 1), emissiveIntensity: 0,
  });
  const root = new THREE.Group();
  const body = new THREE.Object3D();
  body.position.y = 0.75;
  root.add(body);
  const torso = part(body, mcBoxGeo(16, 24, 8, 0, 32, 128, 128, ppu), mat, [0, 0, 0], [0, 0.375, 0], 'torso');
  const head = part(torso, mcBoxGeo(16, 16, 16, 0, 0, 128, 128, ppu), mat, [0, 0.75, 0], [0, 0.25, 0], 'head');
  part(head, mcBoxGeo(16, 16, 16, 64, 0, 128, 128, ppu, 0.035), mat, [0, 0, 0], [0, 0.25, 0.0], 'hood');
  const armR = part(torso, mcBoxGeo(8, 24, 8, 48, 32, 128, 128, ppu, 0.01), mat, [-0.375, 0.68, 0], [0, -0.3, 0], 'armR');
  const armL = part(torso, mcBoxGeo(8, 24, 8, 80, 32, 128, 128, ppu, 0.01), mat, [0.375, 0.68, 0], [0, -0.3, 0], 'armL');
  const skirt = part(body, mcBoxGeo(18, 24, 10, 0, 64, 128, 128, ppu), mat, [0, 0.02, 0], [0, -0.375, 0], 'skirt');
  const g = { root, body, torso, head, armR, armL, skirt, mat, skins };
  g.setFace = (m) => { if (mat.map !== skins[m]) { mat.map = skins[m]; mat.needsUpdate = true; } };
  g.reset = () => {
    for (const p of [body, torso, head, armR, armL, skirt]) p.rotation.set(0, 0, 0);
    body.position.set(0, 0.75, 0);
    root.scale.setScalar(1);
    root.visible = true;
    mat.emissiveIntensity = 0;
    mat.opacity = 1;
    g.setFace('normal');
  };
  // caminar lento y amenazante; ph = fase (metros recorridos)
  g.walk = (ph, amt = 1) => {
    const s = Math.sin(ph * 2.2);
    body.position.y = 0.75 + Math.abs(Math.cos(ph * 2.2)) * 0.03 * amt;
    skirt.rotation.x = s * 0.12 * amt;
    skirt.rotation.z = Math.cos(ph * 1.1) * 0.03 * amt;
    armR.rotation.x = s * 0.25 * amt;
    armL.rotation.x = -s * 0.25 * amt;
    torso.rotation.x = 0.06 * amt;
    head.rotation.x = -0.04 * amt;
  };
  return g;
}

// ---------------------------------------------------------------------------
// Aldeanos (incluye la nina disfrazada de calabaza y la bruja)
// ---------------------------------------------------------------------------
const VILLAGER_KINDS = {
  farmer: { robe: 0x6b4a2a, tunic: 0x8a6a3a, belt: 0x3a2a18, hat: 0xc9a43a },
  librarian: { robe: 0xe8e2d0, tunic: 0x9a3a2a, belt: 0x5a2a1a, hat: null },
  cleric: { robe: 0x6a2a8a, tunic: 0x4a1a6a, belt: 0xd0b040, hat: null },
  nitwit: { robe: 0x2f6a3a, tunic: 0x3a7a46, belt: 0x1a3a20, hat: null },
  butcher: { robe: 0xdedede, tunic: 0x7a3a2a, belt: 0x9a2020, hat: null },
  girl: { robe: 0xe07a1c, tunic: 0xd06a10, belt: 0x2a1a0a, hat: null, girl: true },
  witch: { robe: 0x3a1a4a, tunic: 0x2a1036, belt: 0x40a040, hat: null, witch: true, skin: 0x9ab07a },
};

function villagerSkin(k, eyesWide = false) {
  const skin = k.skin || 0xb88068;
  const head = (f, x, y, fw, fh, r) => {
    if (f === 'front') {
      if (k.girl && y < 2) return C(0x6b3a1a, r);
      if (y === 3 && x > 0 && x < 7) return C(0x3a2416, r);
      if (y === 4 || (eyesWide && y === 5)) {
        if (x === 1 || x === 6) return [245, 245, 245];
        if (x === 2 || x === 5) return eyesWide ? [20, 20, 20] : [30, 120, 50];
      }
      if (k.witch && y === 8 && x === 2) return [60, 120, 40];
      return C(skin, r, 0.08);
    }
    if (f === 'top' || y < 2) return C(k.girl ? 0x6b3a1a : skin * 1 === skin ? 0x7a5040 : skin, r, 0.2);
    return C(skin, r, 0.1);
  };
  const tunic = (f, x, y, fw, fh, r) => {
    if (k.girl && f === 'front') {
      // estampado de calabaza en el pecho
      const jx = Math.floor((x / fw) * 16), jy = Math.floor((y / fh) * 16);
      if (jackFace(jx, jy + 2)) return [20, 12, 6];
    }
    return C(k.tunic, r, 0.15);
  };
  const robe = (f, x, y, fw, fh, r) => {
    if (y === 6 || y === 7) return C(k.belt, r, 0.1);
    if (f === 'front' && x > 2 && x < 5 && y > 7) return C(k.robe, r, 0.1).map((v) => v * 0.8);
    if (k.girl && f === 'front' && y > 8) {
      const jx = Math.floor((x / fw) * 16), jy = (y - 8) * 2;
      if (jackFace(jx, jy)) return [25, 14, 6];
    }
    return C(k.robe, r, 0.15);
  };
  return skinCanvas(64, 64, [
    { u: 0, v: 0, w: 8, h: 10, d: 8, fn: head },
    { u: 32, v: 0, w: 2, h: 4, d: 2, fn: (f, x, y, fw, fh, r) => C(k.skin ? k.skin * 1 : 0xa87058, r, 0.1) },
    { u: 16, v: 20, w: 8, h: 12, d: 6, fn: tunic },
    { u: 0, v: 38, w: 8, h: 18, d: 6, fn: robe },
    { u: 40, v: 38, w: 8, h: 4, d: 4, fn: (f, x, y, fw, fh, r) => (f === 'front' && x > 2 && x < 5 ? C(skin, r) : C(k.tunic, r, 0.15)) },
    { u: 44, v: 22, w: 4, h: 8, d: 4, fn: (f, x, y, fw, fh, r) => (y > 5 ? C(skin, r) : C(k.tunic, r, 0.15)) },
    { u: 0, v: 22, w: 4, h: 12, d: 4, fn: (f, x, y, fw, fh, r) => C(0x3a2a1a, r, 0.2) },
  ], 11);
}

const jackMats = [];
export function jackMaterials() {
  const side = new THREE.MeshStandardMaterial({ map: blockTex('pumpkin_side'), roughness: 0.8 });
  const top = new THREE.MeshStandardMaterial({ map: blockTex('pumpkin_top'), roughness: 0.8 });
  const face = new THREE.MeshStandardMaterial({
    map: blockTex('jack_face'), roughness: 0.8, emissiveMap: blockEmit('jack_face'), emissive: new THREE.Color(1, 0.75, 0.4), emissiveIntensity: 2.2,
  });
  const mats = [side, side, top, top, face, side];
  jackMats.push(face);
  return mats;
}

export function makeJack(size = 1) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(size, size, size), jackMaterials());
  m.castShadow = true;
  m.receiveShadow = true;
  m.userData.face = m.material[4];
  m.userData.setOn = (k) => { m.userData.face.emissiveIntensity = 1.8 * k; };
  return m;
}

export function makeVillager(kind = 'farmer', opts = {}) {
  const k = VILLAGER_KINDS[kind];
  const skins = { normal: toTex(villagerSkin(k), false), wide: toTex(villagerSkin(k, true), false) };
  const mat = new THREE.MeshStandardMaterial({ map: skins.normal, roughness: 0.9 });
  const ppu = 16;
  const root = new THREE.Group();
  const body = new THREE.Object3D();
  body.position.y = 0.75;
  root.add(body);
  const legR = part(body, mcBoxGeo(4, 12, 4, 0, 22, 64, 64, ppu), mat, [-0.125, 0, 0], [0, -0.375, 0], 'legR');
  const legL = part(body, mcBoxGeo(4, 12, 4, 0, 22, 64, 64, ppu), mat, [0.125, 0, 0], [0, -0.375, 0], 'legL');
  const torso = part(body, mcBoxGeo(8, 12, 6, 16, 20, 64, 64, ppu), mat, [0, 0, 0], [0, 0.375, 0], 'torso');
  part(torso, mcBoxGeo(8, 18, 6, 0, 38, 64, 64, ppu, 0.03), mat, [0, 0, 0], [0, 0.19, 0], 'robe');
  const arms = part(torso, mcBoxGeo(8, 4, 4, 40, 38, 64, 64, ppu), mat, [0, 0.6, 0.15], [0, -0.12, 0.08], 'arms');
  part(arms, mcBoxGeo(4, 8, 4, 44, 22, 64, 64, ppu), mat, [-0.375, 0, -0.05], [0, 0.05, -0.04], 'armSideR').rotation.x = -0.75;
  part(arms, mcBoxGeo(4, 8, 4, 44, 22, 64, 64, ppu), mat, [0.375, 0, -0.05], [0, 0.05, -0.04], 'armSideL').rotation.x = -0.75;
  const head = part(torso, mcBoxGeo(8, 10, 8, 0, 0, 64, 64, ppu), mat, [0, 0.75, 0], [0, 0.3125, 0], 'head');
  part(head, mcBoxGeo(2, 4, 2, 32, 0, 64, 64, ppu), mat, [0, 0.19, 0.25], [0, -0.07, 0.06], 'nose');
  const g = { root, body, torso, head, arms, legL, legR, mat, skins, kind };
  if (opts.pumpkinHead) {
    const jack = makeJack(0.62);
    jack.position.set(0, 0.32, 0);
    head.add(jack);
    head.children[0].visible = false;
    head.children[1].visible = false;
    g.jack = jack;
  }
  if (k.girl) {
    // gorrito de calabaza
    const hat = new THREE.Mesh(new THREE.BoxGeometry(0.56, 0.16, 0.56), new THREE.MeshStandardMaterial({ map: blockTex('pumpkin_side'), roughness: 0.8 }));
    hat.position.set(0, 0.68, 0);
    head.add(hat);
    const stem = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.14, 0.1), new THREE.MeshStandardMaterial({ color: 0x4a6a23 }));
    stem.position.set(0, 0.8, 0);
    head.add(stem);
  }
  if (k.witch) {
    const hm = new THREE.MeshStandardMaterial({ color: 0x24122e, roughness: 0.9 });
    const sizes = [[0.68, 0.12, 0.68, 0.66], [0.45, 0.22, 0.45, 0.82], [0.3, 0.2, 0.3, 1.0], [0.16, 0.18, 0.16, 1.15]];
    sizes.forEach(([w, h, d, y], i) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), hm);
      m.position.set(0, y, -0.03 * i);
      m.rotation.x = -0.08 * i;
      head.add(m);
    });
  }
  g.setEyes = (wide) => { mat.map = wide ? skins.wide : skins.normal; };
  g.reset = () => {
    for (const p of [body, torso, head, legL, legR, arms]) p.rotation.set(0, 0, 0);
    body.position.set(0, 0.75, 0);
    root.visible = true;
    g.setEyes(false);
  };
  g.walk = (ph, amt = 1) => {
    const s = Math.sin(ph * 4);
    legL.rotation.x = s * 0.7 * amt;
    legR.rotation.x = -s * 0.7 * amt;
    body.position.y = 0.75 + Math.abs(Math.cos(ph * 4)) * 0.04 * amt;
    torso.rotation.z = s * 0.04 * amt;
  };
  return g;
}

// ---------------------------------------------------------------------------
// Zombi (rig normal)
// ---------------------------------------------------------------------------
function zombieSkin() {
  const green = 0x4f7a3a;
  return skinCanvas(64, 64, [
    {
      u: 0, v: 0, w: 8, h: 8, d: 8,
      fn: (f, x, y, fw, fh, r) => {
        if (f === 'front' && y === 4 && (x === 1 || x === 2 || x === 5 || x === 6)) return [10, 10, 10];
        if (f === 'front' && y === 6 && x > 2 && x < 5) return [30, 50, 25];
        if (y < 2 || f === 'top') return C(0x2a3a1e, r, 0.2);
        return C(green, r, 0.15);
      },
    },
    { u: 16, v: 16, w: 8, h: 12, d: 4, fn: (f, x, y, fw, fh, r) => (r() < 0.08 ? C(0x1a5a6a, r) : C(0x2a8a9a, r, 0.15)) },
    { u: 40, v: 16, w: 4, h: 12, d: 4, fn: (f, x, y, fw, fh, r) => (y < 4 ? C(0x2a8a9a, r, 0.15) : C(green, r, 0.15)) },
    { u: 0, v: 16, w: 4, h: 12, d: 4, fn: (f, x, y, fw, fh, r) => (y > 10 ? C(0x3a3a3a, r) : C(0x3a3a8a, r, 0.15)) },
  ], 21);
}

export function makeZombie() {
  const mat = new THREE.MeshStandardMaterial({ map: toTex(zombieSkin(), false), roughness: 0.9 });
  const ppu = 16;
  const root = new THREE.Group();
  const body = new THREE.Object3D();
  body.position.y = 0.75;
  root.add(body);
  const legR = part(body, mcBoxGeo(4, 12, 4, 0, 16, 64, 64, ppu), mat, [-0.125, 0, 0], [0, -0.375, 0], 'legR');
  const legL = part(body, mcBoxGeo(4, 12, 4, 0, 16, 64, 64, ppu), mat, [0.125, 0, 0], [0, -0.375, 0], 'legL');
  const torso = part(body, mcBoxGeo(8, 12, 4, 16, 16, 64, 64, ppu), mat, [0, 0, 0], [0, 0.375, 0], 'torso');
  const head = part(torso, mcBoxGeo(8, 8, 8, 0, 0, 64, 64, ppu), mat, [0, 0.75, 0], [0, 0.25, 0], 'head');
  const armR = part(torso, mcBoxGeo(4, 12, 4, 40, 16, 64, 64, ppu), mat, [-0.375, 0.625, 0], [0, -0.25, 0], 'armR');
  const armL = part(torso, mcBoxGeo(4, 12, 4, 40, 16, 64, 64, ppu), mat, [0.375, 0.625, 0], [0, -0.25, 0], 'armL');
  return { root, body, torso, head, armR, armL, legL, legR, mat };
}

// ---------------------------------------------------------------------------
// Esqueletos: plantilla de partes (para ejercito instanciado y para el Rey)
// ---------------------------------------------------------------------------
function skeletonSkin(bone = 0xcfcfc8, dark = false) {
  return skinCanvas(64, 32, [
    {
      u: 0, v: 0, w: 8, h: 8, d: 8,
      fn: (f, x, y, fw, fh, r) => {
        if (f === 'front') {
          if ((y === 3 || y === 4) && (x === 1 || x === 2 || x === 5 || x === 6)) return [8, 8, 10];
          if (y === 5 && (x === 3 || x === 4)) return [30, 30, 30];
          if (y === 6 && x > 0 && x < 7) return x % 2 ? [40, 40, 40] : C(bone, r, 0.08);
        }
        return C(bone, r, 0.12).map((v) => v * (dark ? 0.85 : 1));
      },
    },
    {
      u: 16, v: 16, w: 8, h: 12, d: 4,
      fn: (f, x, y, fw, fh, r) => {
        const spine = f === 'front' || f === 'back' ? x === 3 || x === 4 : x === 1 || x === 2;
        const rib = y < 8 && y % 2 === 0;
        const hip = y >= 10;
        if (f === 'top' || f === 'bottom') return C(bone, r, 0.1);
        return spine || rib || hip ? C(bone, r, 0.12) : null;
      },
    },
    { u: 40, v: 16, w: 2, h: 12, d: 2, fn: (f, x, y, fw, fh, r) => C(bone, r, 0.12) },
    { u: 0, v: 16, w: 2, h: 12, d: 2, fn: (f, x, y, fw, fh, r) => C(bone, r, 0.12) },
  ], 31);
}

function skeletonEmit() {
  const cv = document.createElement('canvas');
  cv.width = 64;
  cv.height = 32;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 64, 32);
  ctx.fillStyle = '#fff';
  for (const x of [1, 2, 5, 6]) ctx.fillRect(8 + x, 8 + 3, 1, 2);
  return cv;
}

function bowTex() {
  return paint(16, 16, (x, y, r) => {
    const arc = Math.abs(Math.hypot(x - 2, y - 7.5) - 9) < 0.8 && x > 1;
    const str = x === 3 && y > 0 && y < 15;
    if (arc) return C(0x6b4a26, r);
    if (str) return [200, 200, 200];
    return null;
  });
}

export function skeletonTemplate(variant = 'normal') {
  const map = toTex(skeletonSkin(variant === 'king' ? 0xbdb08a : 0xcfcfc8, variant === 'king'), false);
  const mat = new THREE.MeshStandardMaterial({
    map, roughness: 0.8, alphaTest: 0.5, side: THREE.DoubleSide,
    emissiveMap: toTex(skeletonEmit(), false), emissive: new THREE.Color(0.3, 0.7, 1.0), emissiveIntensity: 0,
  });
  const ppu = 16;
  return {
    mat,
    parts: {
      head: { geo: mcBoxGeo(8, 8, 8, 0, 0, 64, 32, ppu), pivot: [0, 1.5, 0], off: [0, 0.25, 0] },
      torso: { geo: mcBoxGeo(8, 12, 4, 16, 16, 64, 32, ppu), pivot: [0, 0.75, 0], off: [0, 0.375, 0] },
      armR: { geo: mcBoxGeo(2, 12, 2, 40, 16, 64, 32, ppu), pivot: [-0.3125, 1.375, 0], off: [0, -0.3125, 0] },
      armL: { geo: mcBoxGeo(2, 12, 2, 40, 16, 64, 32, ppu), pivot: [0.3125, 1.375, 0], off: [0, -0.3125, 0] },
      legR: { geo: mcBoxGeo(2, 12, 2, 0, 16, 64, 32, ppu), pivot: [-0.125, 0.75, 0], off: [0, -0.375, 0] },
      legL: { geo: mcBoxGeo(2, 12, 2, 0, 16, 64, 32, ppu), pivot: [0.125, 0.75, 0], off: [0, -0.375, 0] },
    },
  };
}

let bowMat;
export function bowMaterial() {
  if (!bowMat) bowMat = new THREE.MeshStandardMaterial({ map: toTex(bowTex(), false), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.9 });
  return bowMat;
}

// Rig individual de esqueleto (el Rey)
export function makeSkeletonRig(variant = 'normal') {
  const T = skeletonTemplate(variant);
  const root = new THREE.Group();
  const P = {};
  for (const n of ['torso', 'legR', 'legL']) P[n] = part(root, T.parts[n].geo, T.mat, T.parts[n].pivot, T.parts[n].off, n);
  for (const n of ['head', 'armR', 'armL']) {
    const p = T.parts[n];
    P[n] = part(P.torso, p.geo, T.mat, [p.pivot[0], p.pivot[1] - 0.75, p.pivot[2]], p.off, n);
  }
  return { root, ...P, mat: T.mat };
}

// ---------------------------------------------------------------------------
// Murcielago
// ---------------------------------------------------------------------------
export function makeBat() {
  const mat = new THREE.MeshStandardMaterial({ color: 0x2a1e18, roughness: 0.9 });
  const wingMat = new THREE.MeshStandardMaterial({
    map: toTex(paint(16, 8, (x, y) => (y < 8 - Math.abs(x - 8) * 0.5 && !(y > 4 && x % 4 === 0) ? [30, 22, 20] : null)), false),
    alphaTest: 0.5, side: THREE.DoubleSide,
  });
  const root = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.25, 0.2), mat);
  root.add(body);
  const wl = new THREE.Object3D(), wr = new THREE.Object3D();
  const geo = new THREE.PlaneGeometry(0.5, 0.25);
  geo.rotateX(-Math.PI / 2);
  const ml = new THREE.Mesh(geo, wingMat); ml.position.x = 0.27; wl.add(ml);
  const mr = new THREE.Mesh(geo, wingMat); mr.position.x = -0.27; wr.add(mr);
  root.add(wl, wr);
  root.userData.flap = (t) => { const a = Math.sin(t * 18) * 0.9; wl.rotation.z = a; wr.rotation.z = -a; };
  return root;
}

// ---------------------------------------------------------------------------
// Faroles (normal y de almas)
// ---------------------------------------------------------------------------
export function makeLantern(soul = true) {
  const g = new THREE.Group();
  const frame = new THREE.MeshStandardMaterial({ color: 0x2a2e36, roughness: 0.6, metalness: 0.6 });
  const glow = new THREE.MeshStandardMaterial({
    color: soul ? 0x9fe8ff : 0xffd080, emissive: soul ? new THREE.Color(0.35, 0.8, 1.0) : new THREE.Color(1.0, 0.7, 0.3), emissiveIntensity: 1.4,
  });
  const core = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.3, 0.26), glow);
  core.position.y = 0.2;
  const top = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.08, 0.34), frame);
  top.position.y = 0.38;
  const bot = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.06, 0.34), frame);
  bot.position.y = 0.03;
  g.add(core, top, bot);
  g.userData.glow = glow;
  return g;
}
