import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const displayFont = "Bangers";
export const bodyFont = "Poppins";

loadFont({
  family: displayFont,
  url: staticFile("fonts/Bangers-400.woff2"),
  weight: "400",
});
loadFont({
  family: bodyFont,
  url: staticFile("fonts/Poppins-600.woff2"),
  weight: "600",
});
loadFont({
  family: bodyFont,
  url: staticFile("fonts/Poppins-800.woff2"),
  weight: "800",
});
