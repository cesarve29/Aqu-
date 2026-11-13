import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Fonts are bundled in public/fonts so renders never depend on the network
export const display = "Anton";
export const body = "Unbounded";
loadFont({ family: display, url: staticFile("fonts/Anton.woff2") });
loadFont({ family: body, url: staticFile("fonts/Unbounded.woff2"), weight: "200 900" });

export const INK = "#070707";
export const BONE = "#f2ede4";
export const BLOOD = "#c1121f";

export type Piece = { file: string; style: string; w: number; h: number };

export const PIECES: Piece[] = [
  { file: "angel.jpg", style: "Realismo", w: 720, h: 1280 },
  { file: "mandala.jpg", style: "Geométrico", w: 787, h: 1400 },
  { file: "koi.jpg", style: "Oriental", w: 785, h: 1400 },
  { file: "lilies.jpg", style: "Floral", w: 720, h: 1280 },
  { file: "chest.jpg", style: "Black & Grey", w: 1400, h: 788 },
  { file: "dragon.jpg", style: "Fantasía", w: 1120, h: 1400 },
  { file: "botanical.jpg", style: "Botánico", w: 787, h: 1400 },
  { file: "ornamental.jpg", style: "Blackwork", w: 1400, h: 1400 },
  { file: "scorpion.jpg", style: "Tradicional", w: 787, h: 1400 },
  { file: "anime.jpg", style: "Anime", w: 1120, h: 1400 },
];
