// Atlas pixel-art 16x16 (8x8 baldosas) para la ciudad, generado proceduralmente.
import * as THREE from 'three';
import { rng, vnoise, hash2 } from '../../voxel-video/src/util.js';

export const T = {
  GRASS: 0, GRASS_SIDE: 1, DIRT: 2, STONE: 3, SAND: 4, LOG: 5, LOG_TOP: 6, LEAVES: 7,
  PLANKS: 8, DARK_PLANKS: 9, ASPHALT: 10, ROAD_LINE: 11, SIDEWALK: 12, CONCRETE: 13, CONCRETE_GRAY: 14, GLASS: 15,
  GLASS_DARK: 16, BRICK: 17, ROOF: 18, STONE_BRICK: 19, QUARTZ: 20, TERRACOTTA: 21, CHERRY: 22, LAMP: 23,
  FIELD: 24, FIELD_LINE: 25, GRAVEL: 26, HOUSE_WINDOW: 27, COPPER: 28, BLACK: 29, ROOF_RED: 30, SANDSTONE: 31,
  GLASS_BLUE: 32, HEDGE: 33, COBBLE: 34, CROSSWALK: 35,
};
const S = 16, N = 8;

export function makeCityAtlas() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = S * N;
  const g = cv.getContext('2d');
  const img = g.createImageData(S * N, S * N);
  const avg = [];
  const jit = (c, r, a) => { const k = 1 + (r() - 0.5) * a; return [c[0] * k, c[1] * k, c[2] * k, 255]; };
  const grass = (r) => jit([104, 170, 62], r, 0.34);
  const dirt = (r) => (r() < 0.1 ? [98, 70, 48, 255] : jit([134, 96, 67], r, 0.32));
  const stone = (x, y, r) => { const n = vnoise(x / 3.2, y / 2.4, 5); const v = 112 + n * 40; return jit([v, v, v + 2], r, 0.14); };
  const glassF = (base, frame, lite) => (x, y, r) => {
    if (x === 0 || y === 0 || x === 15 || y === 15 || x === 8 || y === 8) return jit(frame, r, 0.06);
    const shine = (x + y) % 11 < 2 ? 1.25 : 1;
    const v = 1 + (15 - y) * 0.012;
    return [base[0] * shine * v, base[1] * shine * v, base[2] * shine * v, 255];
  };
  const P = [];
  P[T.GRASS] = (x, y, r) => grass(r);
  P[T.GRASS_SIDE] = (x, y, r) => (y < 3 + (hash2(x, 1, 9) > 0.45 ? 1 : 0) ? grass(r) : dirt(r));
  P[T.DIRT] = (x, y, r) => dirt(r);
  P[T.STONE] = stone;
  P[T.SAND] = (x, y, r) => jit([219, 207, 163], r, 0.12);
  P[T.LOG] = (x, y, r) => (x % 4 === 0 ? jit([74, 58, 34], r, 0.2) : jit([108, 85, 52], r, 0.22));
  P[T.LOG_TOP] = (x, y, r) => { const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5)); return d > 6.5 ? jit([104, 82, 50], r, 0.2) : (Math.floor(d) % 2 ? jit([168, 136, 86], r, 0.1) : jit([136, 108, 66], r, 0.1)); };
  P[T.LEAVES] = (x, y, r) => (r() < 0.2 ? [0, 0, 0, 0] : jit([62, 128, 44], r, 0.5));
  P[T.PLANKS] = (x, y, r) => (y % 4 === 3 || (x + (y >> 2) * 5) % 16 === 0 ? jit([112, 88, 52], r, 0.1) : jit([168, 135, 82], r, 0.14));
  P[T.DARK_PLANKS] = (x, y, r) => (y % 4 === 3 ? jit([44, 30, 18], r, 0.1) : jit([72, 50, 30], r, 0.14));
  P[T.ASPHALT] = (x, y, r) => jit([58, 58, 62], r, 0.25);
  P[T.ROAD_LINE] = (x, y, r) => (x >= 7 && x <= 8 && y < 10 ? jit([236, 200, 60], r, 0.08) : jit([58, 58, 62], r, 0.25));
  P[T.SIDEWALK] = (x, y, r) => (x === 0 || y === 0 ? jit([140, 140, 140], r, 0.05) : jit([186, 186, 182], r, 0.06));
  P[T.CONCRETE] = (x, y, r) => jit([222, 224, 226], r, 0.05);
  P[T.CONCRETE_GRAY] = (x, y, r) => jit([120, 124, 130], r, 0.06);
  P[T.GLASS] = glassF([150, 200, 225], [200, 205, 210]);
  P[T.GLASS_DARK] = glassF([60, 84, 108], [40, 44, 50]);
  P[T.BRICK] = (x, y, r) => { const row = y >> 2, off = row % 2 ? 4 : 0; if (y % 4 === 3 || (x + off) % 8 === 0) return jit([190, 180, 170], r, 0.08); return jit([152, 64, 48], r, 0.18); };
  P[T.ROOF] = (x, y, r) => (y % 4 === 0 || (x + ((y >> 2) % 2) * 4) % 8 === 0 ? jit([34, 34, 40], r, 0.1) : jit([66, 66, 76], r, 0.14));
  P[T.STONE_BRICK] = (x, y, r) => { const row = y >> 3, off = row % 2 ? 8 : 0; if (y % 8 === 7 || (x + off) % 16 === 15) return jit([86, 86, 86], r, 0.08); return jit([128, 128, 126], r, 0.12); };
  P[T.QUARTZ] = (x, y, r) => jit([236, 230, 222], r, 0.04);
  P[T.TERRACOTTA] = (x, y, r) => jit([196, 128, 84], r, 0.08);
  P[T.CHERRY] = (x, y, r) => (r() < 0.18 ? [0, 0, 0, 0] : jit([240, 160, 200], r, 0.3));
  P[T.LAMP] = (x, y, r) => (x === 0 || y === 0 || x === 15 || y === 15 ? [40, 30, 20, 255] : jit([255, 214, 130], r, 0.12));
  P[T.FIELD] = (x, y, r) => (x < 8 ? jit([92, 168, 64], r, 0.12) : jit([110, 190, 76], r, 0.12));
  P[T.FIELD_LINE] = (x, y, r) => (x >= 6 && x <= 9 ? jit([245, 245, 245], r, 0.04) : jit([100, 180, 70], r, 0.12));
  P[T.GRAVEL] = (x, y, r) => jit([130 + (r() - 0.5) * 50, 124, 120], r, 0.2);
  P[T.HOUSE_WINDOW] = glassF([170, 205, 225], [236, 230, 222]);
  P[T.COPPER] = (x, y, r) => jit([88, 168, 140], r, 0.18);
  P[T.BLACK] = (x, y, r) => jit([28, 28, 32], r, 0.1);
  P[T.ROOF_RED] = (x, y, r) => (y % 4 === 0 ? jit([110, 40, 30], r, 0.1) : jit([164, 66, 46], r, 0.14));
  P[T.SANDSTONE] = (x, y, r) => (y < 3 || y > 12 ? jit([200, 182, 128], r, 0.06) : jit([216, 200, 150], r, 0.08));
  P[T.GLASS_BLUE] = glassF([90, 140, 190], [220, 220, 224]);
  P[T.HEDGE] = (x, y, r) => jit([46, 104, 40], r, 0.45);
  P[T.COBBLE] = (x, y, r) => { const n = vnoise(x / 2.6, y / 2.6, 11); if (Math.abs(n - 0.5) < 0.06) return jit([62, 62, 64], r, 0.2); const v = 100 + Math.floor(vnoise(x / 2.6 + 50, y / 2.6, 12) * 4) * 16; return jit([v, v, v], r, 0.15); };
  P[T.CROSSWALK] = (x, y, r) => (x % 6 < 3 ? jit([236, 236, 236], r, 0.05) : jit([58, 58, 62], r, 0.25));
  for (let i = 0; i < N * N; i++) {
    const f = P[i] || ((x, y, r) => [255, 0, 255, 255]);
    const tx = (i % N) * S, ty = Math.floor(i / N) * S;
    const r = rng(2000 + i);
    let s = [0, 0, 0], n = 0;
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const c = f(x, y, r);
      const p = ((ty + y) * S * N + tx + x) * 4;
      for (let k = 0; k < 3; k++) img.data[p + k] = Math.max(0, Math.min(255, c[k]));
      img.data[p + 3] = c[3] ?? 255;
      if ((c[3] ?? 255) > 0) { s[0] += c[0]; s[1] += c[1]; s[2] += c[2]; n++; }
    }
    avg.push(new THREE.Color(s[0] / n / 255, s[1] / n / 255, s[2] / n / 255).convertSRGBToLinear());
  }
  g.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(cv);
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.generateMipmaps = false;
  tex.colorSpace = THREE.SRGBColorSpace;
  const e = 0.0015;
  const uv = (i) => {
    const tx = i % N, ty = Math.floor(i / N);
    return [tx / N + e, 1 - (ty + 1) / N + e, (tx + 1) / N - e, 1 - ty / N - e];
  };
  return { canvas: cv, texture: tex, uv, avg, N, S };
}
