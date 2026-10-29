// Texturas pixel-art procedurales (bloques 16x16 y skins de personajes).
import * as THREE from 'three';

export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hex(c) {
  return [(c >> 16) & 255, (c >> 8) & 255, c & 255];
}

function jit(c, r, amt) {
  const k = 1 + (r() - 0.5) * amt;
  return c.map((v) => Math.max(0, Math.min(255, Math.round(v * k))));
}

// fn(x, y, r) -> [r,g,b] o [r,g,b,a] o null (transparente)
export function paint(w, h, fn, seed = 1) {
  const cv = document.createElement('canvas');
  cv.width = w;
  cv.height = h;
  const ctx = cv.getContext('2d');
  const img = ctx.createImageData(w, h);
  const r = rng(seed);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const c = fn(x, y, r);
      const i = (y * w + x) * 4;
      if (!c) continue;
      img.data[i] = c[0];
      img.data[i + 1] = c[1];
      img.data[i + 2] = c[2];
      img.data[i + 3] = c.length > 3 ? c[3] : 255;
    }
  ctx.putImageData(img, 0, 0);
  return cv;
}

export function toTex(cv, mips = true) {
  const t = new THREE.CanvasTexture(cv);
  t.magFilter = THREE.NearestFilter;
  t.minFilter = mips ? THREE.NearestMipmapLinearFilter : THREE.NearestFilter;
  t.generateMipmaps = mips;
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

// ---------------------------------------------------------------------------
// Bloques
// ---------------------------------------------------------------------------
const noise = (base, amt = 0.25) => (x, y, r) => jit(hex(base), r, amt);
const pick = (cols) => (x, y, r) => jit(hex(cols[Math.floor(r() * cols.length)]), r, 0.12);

function bricks(mortar, brick, moss = 0) {
  return (x, y, r) => {
    if (y % 8 === 7 || ((y < 8 ? x : x + 4) % 8) === 7) return jit(hex(mortar), r, 0.15);
    if (moss && r() < moss) return jit(hex(0x3f5a26), r, 0.3);
    return jit(hex(brick), r, 0.18);
  };
}

function cobble(base, moss = 0) {
  return (x, y, r) => {
    const cx = Math.floor((x + (y >> 2) * 3) / 4), cy = Math.floor((y + (x >> 2) * 2) / 4);
    const edge = (x + (y >> 2) * 3) % 4 === 0 || (y + (x >> 2) * 2) % 4 === 0;
    const rr = rng(cx * 31 + cy * 17)();
    if (moss && r() < moss) return jit(hex(0x4a6b2a), r, 0.3);
    if (edge) return jit(hex(base), r, 0.1).map((v) => v * 0.55);
    return jit(hex(base), r, 0.15).map((v) => v * (0.85 + rr * 0.3));
  };
}

function planks(base) {
  return (x, y, r) => {
    if (y % 4 === 3) return jit(hex(base), r, 0.1).map((v) => v * 0.6);
    const seam = (y >> 2) % 2 ? x === 11 : x === 4;
    if (seam) return jit(hex(base), r, 0.1).map((v) => v * 0.68);
    return jit(hex(base), r, 0.12).map((v) => v * (x % 7 === 0 ? 0.92 : 1));
  };
}

function logSide(base) {
  return (x, y, r) => {
    const stripe = (x * 7 + (y >> 3) * 3) % 5 === 0;
    return jit(hex(base), r, 0.2).map((v) => v * (stripe ? 0.7 : 1));
  };
}

function logTop(bark, wood) {
  return (x, y, r) => {
    if (x === 0 || y === 0 || x === 15 || y === 15) return jit(hex(bark), r, 0.2);
    const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5));
    return jit(hex(wood), r, 0.1).map((v) => v * (Math.floor(d) % 2 ? 0.85 : 1));
  };
}

function leaves(cols) {
  return (x, y, r) => {
    const v = r();
    if (v < 0.12) return jit(hex(cols[0]), r, 0.2).map((q) => q * 0.4);
    return jit(hex(cols[Math.floor(r() * cols.length)]), r, 0.2);
  };
}

const FACE16 = [
  // Mascara del personaje (16x16), inspirada en la skin de referencia.
  '################',
  '#####......#####',
  '###..........###',
  '##............##',
  '##............##',
  '##.###....###.##',
  '##.####..####.##',
  '##..###..###..##',
  '###..#....#..###',
  '###....##....###',
  '####..####..####',
  '####..####..####',
  '#####.####.#####',
  '#####.####.#####',
  '######....######',
  '################',
];

function jackFace(x, y) {
  // Cara tallada de calabaza (pixeles encendidos)
  const eyes = (y >= 4 && y <= 6 && ((x >= 3 && x <= 5) || (x >= 10 && x <= 12)) && !(y === 4 && (x === 3 || x === 12)));
  const nose = y === 8 && (x === 7 || x === 8);
  const mouth = (y === 10 && x >= 3 && x <= 12) || (y === 11 && x >= 4 && x <= 11 && x !== 6 && x !== 9) || (y === 9 && (x === 3 || x === 12));
  return eyes || nose || mouth;
}

export const BLOCK_TEX = {
  grass_top: leaves([0x2f5a22, 0x37682a, 0x2a5020, 0x3d7030]),
  grass_side: (x, y, r) => {
    const fringe = 3 + ((x * 5) % 3 === 0 ? 1 : 0);
    if (y < fringe) return jit(hex(0x37682a), r, 0.2);
    return jit(hex(0x6b4a2f), r, 0.25);
  },
  dirt: noise(0x6b4a2f, 0.3),
  path_top: noise(0x8f7444, 0.2),
  podzol_top: pick([0x5b3d1e, 0x4a3018, 0x6a4a22, 0x3b2a14]),
  mud: noise(0x3a3330, 0.25),
  gravel: pick([0x7a7470, 0x5f5a57, 0x8f8984, 0x4d4846]),
  stone: noise(0x7d7d7d, 0.18),
  cobble: cobble(0x7a7a7a),
  mossy_cobble: cobble(0x777a72, 0.25),
  stone_bricks: bricks(0x4f4f4f, 0x7b7b7b),
  mossy_bricks: bricks(0x4a4f45, 0x737870, 0.22),
  deepslate: (x, y, r) => jit(hex(0x3c3c44), r, 0.25).map((v) => v * ((y + (x >> 2)) % 4 === 0 ? 0.75 : 1)),
  deepslate_bricks: bricks(0x24242a, 0x45454e),
  oak_planks: planks(0x9c7f4e),
  spruce_planks: planks(0x6b5030),
  dark_planks: planks(0x45301a),
  oak_log: logSide(0x5e4a2e),
  oak_log_top: logTop(0x5e4a2e, 0xa98a55),
  dark_log: logSide(0x33261a),
  dark_log_top: logTop(0x33261a, 0x5c4428),
  leaves_orange: leaves([0xb5561c, 0xd2731f, 0x9e3f15, 0xe08c2a]),
  leaves_red: leaves([0x8e2015, 0xa83220, 0x6e1a10, 0xc0482a]),
  leaves_dark: leaves([0x24331b, 0x2c3d21, 0x1d2a16]),
  hay_side: (x, y, r) => (y === 3 || y === 12 ? jit(hex(0x8a4a1e), r, 0.2) : jit(hex(x % 2 ? 0xc9a43a : 0xb8922c), r, 0.2)),
  hay_top: (x, y, r) => jit(hex((x + y) % 3 ? 0xc9a43a : 0xa8812a), r, 0.2),
  pumpkin_side: (x, y, r) => jit(hex(x % 4 === 0 ? 0xb85f12 : 0xe08a1c), r, 0.15),
  pumpkin_top: (x, y, r) => (Math.abs(x - 7.5) < 1.5 && Math.abs(y - 7.5) < 1.5 ? jit(hex(0x5a6b23), r, 0.2) : jit(hex(0xd47d18), r, 0.15)),
  jack_face: (x, y, r) => (jackFace(x, y) ? jit(hex(0xffd75a), r, 0.15) : jit(hex(x % 4 === 0 ? 0xb85f12 : 0xe08a1c), r, 0.15)),
  soul_sand: (x, y, r) => {
    const face = ((x - 3) ** 2 + (y - 4) ** 2 < 3) || ((x - 11) ** 2 + (y - 10) ** 2 < 3) || ((x - 4) ** 2 + (y - 12) ** 2 < 2);
    return jit(hex(face ? 0x3b2a1e : 0x5c4535), r, 0.2);
  },
  soul_soil: noise(0x4a3a2c, 0.25),
  bone_side: (x, y, r) => jit(hex(x % 5 === 2 ? 0xbdb79a : 0xe5e1c8), r, 0.08),
  bone_top: (x, y, r) => {
    const d = Math.hypot(x - 7.5, y - 7.5);
    return jit(hex(d < 3 ? 0xc8c2a5 : d < 5 ? 0xe5e1c8 : 0xd6d0b5), r, 0.08);
  },
  window: (x, y, r) => {
    if (x === 0 || y === 0 || x === 15 || y === 15 || x === 7 || x === 8 || y === 7 || y === 8) return jit(hex(0x3b2a18), r, 0.2);
    return jit(hex(0xffc35a), r, 0.12);
  },
  door: (x, y, r) => {
    if (x === 0 || x === 15 || y % 8 === 0) return jit(hex(0x2a1c10), r, 0.1);
    if (y > 2 && y < 7 && x > 3 && x < 12) return jit(hex(0x1a120a), r, 0.1);
    return jit(hex(0x4b3420), r, 0.15);
  },
  black_wool: noise(0x18181c, 0.2),
  obsidian: pick([0x140f1f, 0x1d1530, 0x0e0a16, 0x2a1d45]),
  rune_stone: bricks(0x3f3f45, 0x6d6d72),
  water: noise(0x203a2a, 0.2),
  lily: (x, y, r) => (Math.hypot(x - 7.5, y - 7.5) < 7 && !(x > 7 && Math.abs(y - 7.5) < 1) ? jit(hex(0x2e6b22), r, 0.2) : null),
  // plantas en cruz (con transparencia)
  dead_bush: (x, y, r) => {
    const stem = (x === 7 && y > 6) || (Math.abs(x - 7 - (y - 10)) < 1 && y > 2 && y < 10) || (Math.abs(x - 7 + (y - 10)) < 1 && y > 4 && y < 10);
    return stem ? jit(hex(0x6b4a26), r, 0.2) : null;
  },
  tall_grass: (x, y, r) => ((x * 7 + 3) % 5 < 2 && y > ((x * 13) % 7) + 2 ? jit(hex(0x2e5a24), r, 0.25) : null),
  cobweb: (x, y, r) => {
    const d1 = x === y || x === 15 - y, d2 = x === 7 || y === 7;
    const ring = [3, 6].some((k) => Math.abs(Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5)) - k) < 0.6);
    return d1 || d2 || ring ? [220, 220, 225, 210] : null;
  },
  mushroom_glow: (x, y, r) => {
    if (y >= 9 && x >= 7 && x <= 8) return jit(hex(0xd8d0c0), r, 0.1);
    if (y >= 4 && y <= 8 && Math.abs(x - 7.5) < (y - 2)) return (x + y) % 5 === 0 ? [220, 255, 250] : jit(hex(0x2fd0c0), r, 0.15);
    return null;
  },
  mushroom_red: (x, y, r) => {
    if (y >= 10 && x >= 7 && x <= 8) return jit(hex(0xd8d0c0), r, 0.1);
    if (y >= 5 && y <= 9 && Math.abs(x - 7.5) < (y - 3)) return (x * 3 + y) % 7 === 0 ? [240, 240, 240] : jit(hex(0xc0281e), r, 0.15);
    return null;
  },
  dripstone: (x, y, r) => (Math.abs(x - 7.5) < (16 - y) / 3 ? jit(hex(0x8a6e5c), r, 0.2) : null),
  chain: (x, y, r) => ((x === 7 || x === 8) && (y % 4 !== 3 || x === 7) ? jit(hex(0x3a3f4a), r, 0.2) : null),
};

// Mapa de emision (solo pixeles que brillan)
export const BLOCK_EMIT = {
  jack_face: (x, y) => (jackFace(x, y) ? [255, 200, 90] : [0, 0, 0]),
  window: (x, y) => (x === 0 || y === 0 || x === 15 || y === 15 || x === 7 || x === 8 || y === 7 || y === 8 ? [0, 0, 0] : [255, 180, 80]),
  rune_stone: (x, y) => {
    const glyph = ((x * 3 + y * 5) % 11 === 0 || (x === 4 && y > 2 && y < 12) || (y === 6 && x > 8 && x < 13) || (x === 11 && y > 8 && y < 13)) && x > 1 && x < 14 && y > 1 && y < 14;
    return glyph ? [90, 200, 255] : [0, 0, 0];
  },
  mushroom_glow: (x, y) => (y >= 4 && y <= 8 && Math.abs(x - 7.5) < (y - 2) ? [40, 220, 200] : [0, 0, 0]),
};

const texCache = {};
export function blockTex(name) {
  if (!texCache[name]) texCache[name] = toTex(paint(16, 16, BLOCK_TEX[name], name.length * 977 + name.charCodeAt(0)));
  return texCache[name];
}
export function blockEmit(name) {
  const k = 'emit_' + name;
  if (!texCache[k]) texCache[k] = toTex(paint(16, 16, BLOCK_EMIT[name], 3));
  return texCache[k];
}

// ---------------------------------------------------------------------------
// Skins de personajes (layout tipo Minecraft)
// ---------------------------------------------------------------------------
// Pinta las 6 caras de una caja con layout Minecraft en (u,v), tamano w,h,d.
// fn(face, x, y, fw, fh, r) -> color | null ; face en {front,back,left,right,top,bottom}
export function paintBox(img, tw, u, v, w, h, d, fn, r) {
  const rects = {
    top: [u + d, v, w, d],
    bottom: [u + d + w, v, w, d],
    right: [u, v + d, d, h],
    front: [u + d, v + d, w, h],
    left: [u + d + w, v + d, d, h],
    back: [u + 2 * d + w, v + d, w, h],
  };
  for (const face in rects) {
    const [x0, y0, fw, fh] = rects[face];
    for (let y = 0; y < fh; y++)
      for (let x = 0; x < fw; x++) {
        const c = fn(face, x, y, fw, fh, r);
        if (!c) continue;
        const i = ((y0 + y) * tw + x0 + x) * 4;
        img.data[i] = c[0];
        img.data[i + 1] = c[1];
        img.data[i + 2] = c[2];
        img.data[i + 3] = c.length > 3 ? c[3] : 255;
      }
  }
}

export function skinCanvas(tw, th, boxes, seed = 7) {
  const cv = document.createElement('canvas');
  cv.width = tw;
  cv.height = th;
  const ctx = cv.getContext('2d');
  const img = ctx.createImageData(tw, th);
  const r = rng(seed);
  for (const b of boxes) paintBox(img, tw, b.u, b.v, b.w, b.h, b.d, b.fn, r);
  ctx.putImageData(img, 0, 0);
  return cv;
}

export { FACE16, jackFace, jit };
