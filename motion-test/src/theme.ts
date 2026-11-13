import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Fuentes locales (public/fonts) para que el render no dependa de la red.
export const display = "Unbounded";
export const mono = "DM Mono";

loadFont({
  family: display,
  url: staticFile("fonts/Unbounded.woff2"),
  weight: "200 900",
});
loadFont({
  family: mono,
  url: staticFile("fonts/DMMono-Medium.woff2"),
  weight: "500",
});

export const INK = "#141a3a";
export const YELLOW = "#ffc93c";
export const CORAL = "#ff5a4e";
export const TEAL = "#0f8f83";
export const PAPER = "#f6f4ee";

export const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;
