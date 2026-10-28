// Atlas de texturas pixel-art 16x16 generado proceduralmente (4x4 baldosas).
import * as THREE from 'three';
import { rng, vnoise, hash2 } from './util.js';

export const TILE = {
  GRASS_TOP: 0, GRASS_SIDE: 1, DIRT: 2, STONE: 3, SAND: 4, LOG_SIDE: 5, LOG_TOP: 6, LEAVES: 7,
  PLANKS: 8, OBSIDIAN: 9, ENDSTONE: 10, COBBLE: 11, ORE: 12, SNOW: 13, TABLE_TOP: 14, GLOW: 15,
};
const T = 16, N = 4;

export function makeAtlas() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = T * N;
  const g = cv.getContext('2d');
  const img = g.createImageData(T * N, T * N);
  const avg = [];
  const jit = (c, r, a) => { const k = 1 + (r() - 0.5) * a; return [c[0] * k, c[1] * k, c[2] * k, 255]; };
  const grass = (r) => jit([100, 168, 60], r, 0.38);
  const dirt = (r) => (r() < 0.1 ? [98, 70, 48, 255] : jit([134, 96, 67], r, 0.35));
  const stone = (x, y, r) => {
    const n = vnoise(x / 3.2, y / 2.4, 5);
    const g0 = 112 + n * 40;
    return jit([g0, g0, g0 + 2], r, 0.16);
  };
  const painters = [
    (x, y, r) => grass(r),
    (x, y, r) => (y < 3 + (hash2(x, 1, 9) > 0.45 ? 1 : 0) + (hash2(x, 2, 9) > 0.8 ? 1 : 0) ? grass(r) : dirt(r)),
    (x, y, r) => dirt(r),
    stone,
    (x, y, r) => jit([219, 207, 163], r, 0.12),
    (x, y, r) => (x % 4 === 0 || (x % 4 === 2 && hash2(x, y >> 2, 3) > 0.6) ? jit([74, 58, 34], r, 0.2) : jit([108, 85, 52], r, 0.22)),
    (x, y, r) => {
      const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5));
      if (d > 6.5) return jit([104, 82, 50], r, 0.2);
      return Math.floor(d) % 2 ? jit([168, 136, 86], r, 0.1) : jit([136, 108, 66], r, 0.1);
    },
    (x, y, r) => (r() < 0.22 ? [0, 0, 0, 0] : jit([58, 122, 40], r, 0.5)),
    (x, y, r) => {
      const row = y >> 2;
      const seam = (x + row * 5) % 16 === 0;
      if (y % 4 === 3 || seam) return jit([112, 88, 52], r, 0.1);
      return jit([168, 135, 82], r, 0.14);
    },
    (x, y, r) => (r() < 0.12 ? jit([70, 42, 110], r, 0.3) : jit([22, 18, 34], r, 0.5)),
    (x, y, r) => (r() < 0.08 ? jit([188, 190, 136], r, 0.1) : jit([222, 224, 168], r, 0.1)),
    (x, y, r) => {
      const n = vnoise(x / 2.6, y / 2.6, 11);
      if (Math.abs(n - 0.5) < 0.06) return jit([62, 62, 64], r, 0.2);
      const g0 = 100 + Math.floor(vnoise(x / 2.6 + 50, y / 2.6, 12) * 4) * 16;
      return jit([g0, g0, g0], r, 0.15);
    },
    (x, y, r) => {
      const n = vnoise(x / 2, y / 2, 21);
      return n > 0.72 ? jit([90, 236, 226], r, 0.25) : stone(x, y, r);
    },
    (x, y, r) => jit([238, 244, 250], r, 0.05),
    (x, y, r) => {
      if (x === 0 || y === 0 || x === 15 || y === 15) return jit([90, 62, 34], r, 0.1);
      if (x === 5 || x === 10 || y === 5 || y === 10) return jit([120, 82, 44], r, 0.1);
      return jit([178, 132, 82], r, 0.12);
    },
    (x, y, r) => (r() < 0.3 ? jit([255, 176, 70], r, 0.1) : jit([255, 226, 140], r, 0.1)),
  ];
  painters.forEach((f, i) => {
    const tx = (i % N) * T, ty = Math.floor(i / N) * T;
    const r = rng(1000 + i);
    let s = [0, 0, 0], n = 0;
    for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
      const c = f(x, y, r);
      const p = ((ty + y) * T * N + tx + x) * 4;
      for (let k = 0; k < 3; k++) img.data[p + k] = Math.max(0, Math.min(255, c[k]));
      img.data[p + 3] = c[3] ?? 255;
      if ((c[3] ?? 255) > 0) { s[0] += c[0]; s[1] += c[1]; s[2] += c[2]; n++; }
    }
    avg.push(new THREE.Color(s[0] / n / 255, s[1] / n / 255, s[2] / n / 255).convertSRGBToLinear());
  });
  g.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(cv);
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = THREE.SRGBColorSpace;
  const e = 0.003;
  const uv = (i) => {
    const tx = i % N, ty = Math.floor(i / N);
    return [tx / N + e, 1 - (ty + 1) / N + e, (tx + 1) / N - e, 1 - ty / N - e];
  };
  return { canvas: cv, texture: tex, uv, avg };
}
